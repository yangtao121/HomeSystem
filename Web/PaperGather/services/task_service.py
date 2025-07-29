"""
论文收集任务服务
支持两种执行模式：即时执行和后台定时执行
使用线程分离防止Web界面阻塞
"""
import asyncio
import threading
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
import sys
import os
from concurrent.futures import ThreadPoolExecutor

# 添加HomeSystem到路径
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from HomeSystem.workflow.paper_gather_task.paper_gather_task import PaperGatherTask, PaperGatherTaskConfig
from HomeSystem.workflow.engine import WorkflowEngine
from HomeSystem.graph.llm_factory import LLMFactory
from loguru import logger


class TaskMode(Enum):
    """任务执行模式"""
    IMMEDIATE = "immediate"  # 即时执行
    SCHEDULED = "scheduled"  # 后台定时执行


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class TaskResult:
    """任务执行结果"""
    def __init__(self, task_id: str, status: TaskStatus, 
                 start_time: datetime, end_time: Optional[datetime] = None,
                 result_data: Optional[Dict[str, Any]] = None,
                 error_message: Optional[str] = None,
                 progress: float = 0.0):
        self.task_id = task_id
        self.status = status
        self.start_time = start_time
        self.end_time = end_time
        self.result_data = result_data or {}
        self.error_message = error_message
        self.progress = progress  # 0.0 - 1.0
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'task_id': self.task_id,
            'status': self.status.value,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'result_data': self.result_data,
            'error_message': self.error_message,
            'progress': self.progress,
            'duration': (self.end_time - self.start_time).total_seconds() if self.end_time else None
        }


class PaperGatherService:
    """论文收集服务 - 线程安全的任务管理"""
    
    def __init__(self):
        self.llm_factory = LLMFactory()
        self.workflow_engine: Optional[WorkflowEngine] = None
        self.scheduled_tasks: Dict[str, PaperGatherTask] = {}
        self.task_results: Dict[str, TaskResult] = {}
        
        # 线程池用于执行任务
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # 线程锁保证数据安全
        self.lock = threading.Lock()
        
        # 后台引擎线程
        self.engine_thread: Optional[threading.Thread] = None
        self.engine_running = False
        
    def get_available_models(self) -> List[str]:
        """获取可用的LLM模型列表"""
        try:
            chat_models = self.llm_factory.get_available_llm_models()
            return chat_models
        except Exception as e:
            logger.error(f"获取可用模型失败: {e}")
            return ["ollama.Qwen3_30B"]  # 返回默认模型作为备选
    
    def validate_config(self, config_dict: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证配置参数"""
        try:
            # 检查必需参数
            required_fields = ['search_query', 'user_requirements', 'llm_model_name']
            for field in required_fields:
                if not config_dict.get(field):
                    return False, f"缺少必需参数: {field}"
            
            # 检查数值范围
            if not (0.0 <= config_dict.get('relevance_threshold', 0.7) <= 1.0):
                return False, "relevance_threshold 必须在 0.0-1.0 范围内"
            
            if not (0.0 <= config_dict.get('summarization_threshold', 0.8) <= 1.0):
                return False, "summarization_threshold 必须在 0.0-1.0 范围内"
            
            if not (1 <= config_dict.get('max_papers_per_search', 20) <= 100):
                return False, "max_papers_per_search 必须在 1-100 范围内"
            
            # 检查模型是否可用
            available_models = self.get_available_models()
            if config_dict.get('llm_model_name') not in available_models:
                return False, f"LLM模型不可用: {config_dict.get('llm_model_name')}"
            
            return True, None
            
        except Exception as e:
            return False, f"配置验证失败: {str(e)}"
    
    def _run_task_async(self, task_id: str, config_dict: Dict[str, Any]):
        """在单独线程中异步运行任务"""
        def run_in_thread():
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # 运行异步任务
                result = loop.run_until_complete(self._execute_task_internal(task_id, config_dict))
                return result
            finally:
                loop.close()
        
        return run_in_thread
    
    async def _execute_task_internal(self, task_id: str, config_dict: Dict[str, Any]) -> TaskResult:
        """内部任务执行逻辑"""
        task_result = None
        
        with self.lock:
            task_result = self.task_results.get(task_id)
        
        if not task_result:
            return None
        
        try:
            logger.info(f"开始执行任务: {task_id}")
            
            # 更新状态为运行中
            with self.lock:
                task_result.status = TaskStatus.RUNNING
                task_result.progress = 0.1
            
            # 创建PaperGatherTaskConfig
            # 为即时执行设置interval_seconds为0，避免重复参数
            config_dict_copy = config_dict.copy()
            config_dict_copy['interval_seconds'] = 0  # 即时执行不需要间隔
            
            # 过滤掉非PaperGatherTaskConfig参数
            valid_params = {
                'interval_seconds', 'search_query', 'max_papers_per_search', 
                'user_requirements', 'llm_model_name', 'relevance_threshold',
                'max_papers_in_response', 'max_relevant_papers_in_response',
                'enable_paper_summarization', 'summarization_threshold', 
                'enable_translation', 'custom_settings'
            }
            filtered_config = {k: v for k, v in config_dict_copy.items() if k in valid_params}
            
            config = PaperGatherTaskConfig(**filtered_config)
            
            # 创建并执行任务
            paper_task = PaperGatherTask(config=config)
            
            # 更新进度
            with self.lock:
                task_result.progress = 0.3
            
            # 执行任务
            result = await paper_task.run()
            
            # 任务完成，更新结果
            with self.lock:
                task_result.status = TaskStatus.COMPLETED
                task_result.end_time = datetime.now()
                task_result.result_data = result
                task_result.progress = 1.0
            
            logger.info(f"任务执行完成: {task_id}")
            return task_result
            
        except Exception as e:
            error_msg = f"任务执行失败: {str(e)}"
            logger.error(f"{error_msg} (任务ID: {task_id})")
            
            with self.lock:
                task_result.status = TaskStatus.FAILED
                task_result.end_time = datetime.now()
                task_result.error_message = error_msg
                task_result.progress = 0.0
            
            return task_result
    
    def start_immediate_task(self, config_dict: Dict[str, Any]) -> str:
        """
        启动即时执行任务 - 非阻塞方式
        返回任务ID，任务在后台线程中执行
        """
        task_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # 创建任务结果记录
        task_result = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
            start_time=start_time
        )
        
        with self.lock:
            self.task_results[task_id] = task_result
        
        # 提交任务到线程池执行
        future = self.executor.submit(self._run_task_async(task_id, config_dict))
        
        logger.info(f"即时任务已提交到线程池: {task_id}")
        return task_id
    
    def start_scheduled_task(self, config_dict: Dict[str, Any]) -> tuple[bool, str, Optional[str]]:
        """
        启动后台定时任务 - 使用WorkflowEngine
        """
        try:
            task_id = str(uuid.uuid4())
            
            # 创建PaperGatherTaskConfig，包含定时间隔
            # 过滤掉非PaperGatherTaskConfig参数
            valid_params = {
                'interval_seconds', 'search_query', 'max_papers_per_search', 
                'user_requirements', 'llm_model_name', 'relevance_threshold',
                'max_papers_in_response', 'max_relevant_papers_in_response',
                'enable_paper_summarization', 'summarization_threshold', 
                'enable_translation', 'custom_settings'
            }
            filtered_config = {k: v for k, v in config_dict.items() if k in valid_params}
            config = PaperGatherTaskConfig(**filtered_config)
            
            # 创建任务
            paper_task = PaperGatherTask(config=config)
            
            with self.lock:
                self.scheduled_tasks[task_id] = paper_task
            
            # 如果WorkflowEngine未初始化或未运行，则启动
            if not self.engine_running:
                self._start_workflow_engine()
            
            # 添加任务到引擎
            self.workflow_engine.add_task(paper_task)
            
            logger.info(f"后台定时任务已启动: {task_id}, 间隔: {config.interval_seconds}秒")
            return True, task_id, None
            
        except Exception as e:
            error_msg = f"启动后台任务失败: {str(e)}"
            logger.error(error_msg)
            return False, "", error_msg
    
    def _start_workflow_engine(self):
        """启动WorkflowEngine在后台线程"""
        if self.engine_running:
            return
        
        def run_engine():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                self.workflow_engine = WorkflowEngine()
                self.engine_running = True
                logger.info("WorkflowEngine已启动")
                loop.run_until_complete(self.workflow_engine.run())
            except Exception as e:
                logger.error(f"WorkflowEngine运行异常: {e}")
            finally:
                self.engine_running = False
                loop.close()
        
        self.engine_thread = threading.Thread(target=run_engine, daemon=True)
        self.engine_thread.start()
    
    def stop_scheduled_task(self, task_id: str) -> tuple[bool, Optional[str]]:
        """停止后台定时任务"""
        try:
            with self.lock:
                if task_id not in self.scheduled_tasks:
                    return False, "任务不存在"
                
                # 清理任务记录
                del self.scheduled_tasks[task_id]
            
            logger.info(f"后台定时任务已停止: {task_id}")
            return True, None
            
        except Exception as e:
            error_msg = f"停止后台任务失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """获取所有后台定时任务状态"""
        tasks = []
        with self.lock:
            for task_id, task in self.scheduled_tasks.items():
                tasks.append({
                    'task_id': task_id,
                    'name': task.name,
                    'interval_seconds': task.interval_seconds,
                    'config': task.config.get_config_dict() if hasattr(task.config, 'get_config_dict') else {}
                })
        return tasks
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务执行结果"""
        with self.lock:
            task_result = self.task_results.get(task_id)
            return task_result.to_dict() if task_result else None
    
    def get_all_task_results(self) -> List[Dict[str, Any]]:
        """获取所有任务执行结果"""
        with self.lock:
            return [result.to_dict() for result in self.task_results.values()]
    
    def cleanup_old_results(self, keep_last_n: int = 50):
        """清理旧的任务结果，只保留最近的N个"""
        with self.lock:
            if len(self.task_results) <= keep_last_n:
                return
            
            # 按时间排序，保留最新的
            sorted_results = sorted(
                self.task_results.items(), 
                key=lambda x: x[1].start_time, 
                reverse=True
            )
            
            # 保留最新的N个结果
            keep_results = dict(sorted_results[:keep_last_n])
            self.task_results = keep_results
            
            logger.info(f"清理旧任务结果，保留最近的 {keep_last_n} 个")
    
    def cancel_task(self, task_id: str) -> tuple[bool, Optional[str]]:
        """取消正在运行的任务"""
        try:
            with self.lock:
                task_result = self.task_results.get(task_id)
                if not task_result:
                    return False, "任务不存在"
                
                if task_result.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    return False, "任务已完成或失败，无法取消"
                
                # 更新任务状态
                task_result.status = TaskStatus.STOPPED
                task_result.end_time = datetime.now()
                task_result.error_message = "用户取消任务"
            
            logger.info(f"任务已取消: {task_id}")
            return True, None
            
        except Exception as e:
            error_msg = f"取消任务失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg


# 全局服务实例
paper_gather_service = PaperGatherService()