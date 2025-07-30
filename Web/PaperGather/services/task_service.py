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
from HomeSystem.workflow.paper_gather_task.data_manager import PaperGatherDataManager, ConfigVersionManager
from HomeSystem.utility.arxiv.arxiv import ArxivSearchMode
from HomeSystem.workflow.engine import WorkflowEngine
from HomeSystem.workflow.scheduler import TaskScheduler
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
        self.task_scheduler: Optional[TaskScheduler] = None
        self.scheduled_tasks: Dict[str, PaperGatherTask] = {}
        self.task_results: Dict[str, TaskResult] = {}
        
        # 数据管理器
        self.data_manager = PaperGatherDataManager()
        
        # 线程池用于执行任务
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # 线程锁保证数据安全
        self.lock = threading.Lock()
        
        # 后台调度器线程
        self.scheduler_thread: Optional[threading.Thread] = None
        self.scheduler_running = False
        self.scheduler_shutdown_event = None
        
        # 启动时加载历史数据
        self._load_historical_data()
    
    def _load_historical_data(self):
        """加载历史数据到内存"""
        try:
            # 加载最近的任务结果到内存（用于状态查询）
            recent_tasks = self.data_manager.load_task_history(limit=50)
            
            with self.lock:
                for task_data in recent_tasks:
                    task_id = task_data.get("task_id")
                    if task_id:
                        # 创建TaskResult对象
                        start_time = datetime.fromisoformat(task_data.get("start_time"))
                        end_time_str = task_data.get("end_time")
                        end_time = datetime.fromisoformat(end_time_str) if end_time_str else None
                        
                        task_result = TaskResult(
                            task_id=task_id,
                            status=TaskStatus(task_data.get("status", "completed")),
                            start_time=start_time,
                            end_time=end_time,
                            result_data=task_data.get("result", {}),
                            progress=1.0 if task_data.get("status") == "completed" else 0.0
                        )
                        
                        self.task_results[task_id] = task_result
            
            logger.info(f"加载了 {len(recent_tasks)} 个历史任务到内存")
            
        except Exception as e:
            logger.error(f"加载历史数据失败: {e}")
    
    def get_available_models(self) -> List[str]:
        """获取可用的LLM模型列表"""
        try:
            chat_models = self.llm_factory.get_available_llm_models()
            return chat_models
        except Exception as e:
            logger.error(f"获取可用模型失败: {e}")
            return ["ollama.Qwen3_30B"]  # 返回默认模型作为备选
    
    def get_available_search_modes(self) -> List[Dict[str, str]]:
        """获取可用的搜索模式列表"""
        return [
            {'value': ArxivSearchMode.LATEST.value, 'label': '最新论文', 'description': '按提交日期降序排列'},
            {'value': ArxivSearchMode.MOST_RELEVANT.value, 'label': '最相关', 'description': '按相关性排序'},
            {'value': ArxivSearchMode.RECENTLY_UPDATED.value, 'label': '最近更新', 'description': '按更新日期降序排列'},
            {'value': ArxivSearchMode.DATE_RANGE.value, 'label': '日期范围', 'description': '搜索指定年份范围的论文'},
            {'value': ArxivSearchMode.AFTER_YEAR.value, 'label': '某年之后', 'description': '搜索某年之后的论文'}
        ]
    
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
            
            # 验证搜索模式相关参数
            search_mode = config_dict.get('search_mode', 'latest')
            try:
                mode_enum = ArxivSearchMode(search_mode)
            except ValueError:
                return False, f"无效的搜索模式: {search_mode}"
            
            # 验证日期范围搜索参数
            if mode_enum == ArxivSearchMode.DATE_RANGE:
                start_year = config_dict.get('start_year')
                end_year = config_dict.get('end_year')
                if start_year is None or end_year is None:
                    return False, "日期范围搜索模式需要提供起始年份和结束年份"
                if not isinstance(start_year, int) or not isinstance(end_year, int):
                    return False, "起始年份和结束年份必须是整数"
                if start_year > end_year:
                    return False, "起始年份不能大于结束年份"
                if start_year < 1991:  # ArXiv 1991年开始
                    return False, "起始年份不能早于1991年"
                
            # 验证某年之后搜索参数
            elif mode_enum == ArxivSearchMode.AFTER_YEAR:
                after_year = config_dict.get('after_year')
                if after_year is None:
                    return False, "某年之后搜索模式需要提供after_year参数"
                if not isinstance(after_year, int):
                    return False, "after_year必须是整数"
                if after_year < 1991:
                    return False, "after_year不能早于1991年"
                from datetime import datetime
                if after_year > datetime.now().year:
                    return False, f"after_year ({after_year}) 不能大于当前年份 ({datetime.now().year})"
            
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
                'user_requirements', 'llm_model_name', 'abstract_analysis_model',
                'full_paper_analysis_model', 'translation_model', 'paper_analysis_model',
                'relevance_threshold', 'max_papers_in_response', 'max_relevant_papers_in_response',
                'enable_paper_summarization', 'summarization_threshold', 
                'enable_translation', 'custom_settings',
                # 新增搜索模式相关参数
                'search_mode', 'start_year', 'end_year', 'after_year'
            }
            filtered_config = {k: v for k, v in config_dict_copy.items() if k in valid_params}
            
            # 转换搜索模式字符串为枚举
            if 'search_mode' in filtered_config and isinstance(filtered_config['search_mode'], str):
                filtered_config['search_mode'] = ArxivSearchMode(filtered_config['search_mode'])
            
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
            
            # 保存到持久化存储
            self._save_task_to_persistent_storage(task_id, config_dict_copy, result, 
                                                 task_result.start_time, task_result.end_time, "completed")
            
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
            
            # 保存失败任务到持久化存储
            self._save_task_to_persistent_storage(task_id, config_dict_copy, {"error": error_msg}, 
                                                 task_result.start_time, task_result.end_time, "failed")
            
            return task_result
    
    def _save_task_to_persistent_storage(self, task_id: str, config_dict: Dict[str, Any], 
                                       result_data: Dict[str, Any], start_time: datetime, 
                                       end_time: datetime, status: str):
        """保存任务到持久化存储"""
        try:
            # 在后台线程中异步保存，避免阻塞主流程
            def save_async():
                self.data_manager.save_task_complete(
                    task_id=task_id,
                    config_dict=config_dict,
                    result_data=result_data,
                    start_time=start_time,
                    end_time=end_time,
                    status=status
                )
            
            # 提交到线程池执行
            self.executor.submit(save_async)
            
        except Exception as e:
            logger.error(f"提交持久化存储任务失败: {e}")
    
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
                'user_requirements', 'llm_model_name', 'abstract_analysis_model',
                'full_paper_analysis_model', 'translation_model', 'paper_analysis_model',
                'relevance_threshold', 'max_papers_in_response', 'max_relevant_papers_in_response',
                'enable_paper_summarization', 'summarization_threshold', 
                'enable_translation', 'custom_settings',
                # 新增搜索模式相关参数
                'search_mode', 'start_year', 'end_year', 'after_year'
            }
            filtered_config = {k: v for k, v in config_dict.items() if k in valid_params}
            
            # 转换搜索模式字符串为枚举
            if 'search_mode' in filtered_config and isinstance(filtered_config['search_mode'], str):
                filtered_config['search_mode'] = ArxivSearchMode(filtered_config['search_mode'])
            
            config = PaperGatherTaskConfig(**filtered_config)
            
            # 创建任务
            paper_task = PaperGatherTask(config=config)
            
            with self.lock:
                self.scheduled_tasks[task_id] = paper_task
            
            # 如果TaskScheduler未初始化或未运行，则启动
            if not self.scheduler_running:
                self._start_task_scheduler()
            
            # 等待调度器初始化完成（最多等待5秒）
            import time
            max_wait = 5.0
            wait_interval = 0.1
            waited = 0.0
            
            while self.task_scheduler is None and waited < max_wait:
                time.sleep(wait_interval)
                waited += wait_interval
            
            # 添加任务到调度器
            if self.task_scheduler:
                self.task_scheduler.add_task(paper_task)
            else:
                raise Exception("任务调度器初始化超时")
            
            logger.info(f"后台定时任务已启动: {task_id}, 间隔: {config.interval_seconds}秒")
            return True, task_id, None
            
        except Exception as e:
            error_msg = f"启动后台任务失败: {str(e)}"
            logger.error(error_msg)
            return False, "", error_msg
    
    def _start_task_scheduler(self):
        """启动TaskScheduler在后台线程（不使用信号处理）"""
        if self.scheduler_running:
            return
        
        def run_scheduler():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                self.task_scheduler = TaskScheduler()
                self.scheduler_shutdown_event = asyncio.Event()
                self.scheduler_running = True
                logger.info("TaskScheduler已启动")
                
                # 启动调度器
                loop.run_until_complete(self._run_scheduler_loop())
            except Exception as e:
                logger.error(f"TaskScheduler运行异常: {e}")
            finally:
                self.scheduler_running = False
                loop.close()
        
        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
    
    async def _run_scheduler_loop(self):
        """运行调度器循环（不使用信号处理）"""
        try:
            # 启动调度器任务
            scheduler_task = asyncio.create_task(self.task_scheduler.start())
            
            # 在Web环境中，我们不使用信号处理，而是让任务持续运行
            # 调度器会在守护线程中运行，当主进程结束时自动终止
            await scheduler_task
            
        except Exception as e:
            logger.error(f"调度器循环出错: {e}")
        finally:
            logger.info("TaskScheduler已停止")
    
    def stop_scheduled_task(self, task_id: str) -> tuple[bool, Optional[str]]:
        """停止后台定时任务"""
        try:
            with self.lock:
                if task_id not in self.scheduled_tasks:
                    return False, "任务不存在"
                
                task = self.scheduled_tasks[task_id]
                
                # 从调度器中移除任务
                if self.task_scheduler:
                    self.task_scheduler.remove_task(task.name)
                
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
    
    def get_running_tasks_count(self) -> int:
        """获取运行中任务的总数（包括即时任务和定时任务）"""
        running_count = 0
        
        with self.lock:
            # 统计运行中的即时任务
            for task_result in self.task_results.values():
                if task_result.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    running_count += 1
            
            # 统计定时任务（都视为运行中）
            running_count += len(self.scheduled_tasks)
        
        return running_count
    
    def get_running_tasks_detail(self) -> List[Dict[str, Any]]:
        """获取所有运行中任务的详细信息"""
        running_tasks = []
        
        with self.lock:
            # 添加运行中的即时任务
            for task_id, task_result in self.task_results.items():
                if task_result.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    running_tasks.append({
                        'task_id': task_id,
                        'type': 'immediate',
                        'status': task_result.status.value,
                        'start_time': task_result.start_time.isoformat(),
                        'progress': task_result.progress,
                        'name': f"即时任务 {task_id[:8]}..."
                    })
            
            # 添加定时任务
            for task_id, task in self.scheduled_tasks.items():
                running_tasks.append({
                    'task_id': task_id,
                    'type': 'scheduled',
                    'status': 'running',
                    'name': task.name,
                    'interval_seconds': task.interval_seconds
                })
        
        return running_tasks
    
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
    
    def get_task_history(self, limit: int = 100, start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取任务历史记录"""
        try:
            return self.data_manager.load_task_history(
                limit=limit,
                start_date=start_date,
                end_date=end_date,
                status_filter=status_filter
            )
        except Exception as e:
            logger.error(f"获取任务历史失败: {e}")
            return []
    
    def get_task_config_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取指定任务的配置（支持版本兼容性）"""
        try:
            return self.data_manager.get_task_config_compatible(task_id)
        except Exception as e:
            logger.error(f"获取任务配置失败: {e}")
            return None
    
    def save_config_preset(self, name: str, config_dict: Dict[str, Any], description: str = "") -> tuple[bool, Optional[str]]:
        """保存配置预设"""
        try:
            # 配置验证
            is_valid, error_msg = self.validate_config(config_dict)
            if not is_valid:
                return False, error_msg
            
            success = self.data_manager.save_config_preset(name, config_dict, description)
            return success, None if success else "保存预设失败"
            
        except Exception as e:
            error_msg = f"保存配置预设失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def load_config_presets(self) -> List[Dict[str, Any]]:
        """加载所有配置预设"""
        try:
            return self.data_manager.load_config_presets()
        except Exception as e:
            logger.error(f"加载配置预设失败: {e}")
            return []
    
    def delete_config_preset(self, preset_id: str) -> tuple[bool, Optional[str]]:
        """删除配置预设"""
        try:
            success = self.data_manager.delete_config_preset(preset_id)
            return success, None if success else "删除预设失败"
            
        except Exception as e:
            error_msg = f"删除配置预设失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def delete_task_history(self, task_id: str) -> tuple[bool, Optional[str]]:
        """删除历史任务记录"""
        try:
            success = self.data_manager.delete_task_history(task_id)
            return success, None if success else "删除历史任务失败，未找到指定任务"
            
        except Exception as e:
            error_msg = f"删除历史任务失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def start_task_from_config(self, config_dict: Dict[str, Any], mode: TaskMode = TaskMode.IMMEDIATE) -> tuple[bool, str, Optional[str]]:
        """基于配置启动任务"""
        try:
            # 应用配置兼容性处理
            compatible_config = ConfigVersionManager.ensure_config_compatibility(config_dict)
            
            # 配置验证
            is_valid, error_msg = self.validate_config(compatible_config)
            if not is_valid:
                return False, "", error_msg
            
            # 根据模式启动任务
            if mode == TaskMode.IMMEDIATE:
                task_id = self.start_immediate_task(compatible_config)
                return True, task_id, None
            else:
                success, task_id, error_msg = self.start_scheduled_task(compatible_config)
                return success, task_id, error_msg
                
        except Exception as e:
            error_msg = f"启动任务失败: {str(e)}"
            logger.error(error_msg)
            return False, "", error_msg
    
    def get_data_statistics(self) -> Dict[str, Any]:
        """获取数据统计信息"""
        try:
            stats = self.data_manager.get_statistics()
            
            # 添加运行时统计
            with self.lock:
                stats["memory_tasks"] = len(self.task_results)
                stats["running_tasks"] = len([r for r in self.task_results.values() 
                                            if r.status in [TaskStatus.PENDING, TaskStatus.RUNNING]])
                stats["scheduled_tasks"] = len(self.scheduled_tasks)
            
            return stats
            
        except Exception as e:
            logger.error(f"获取数据统计失败: {e}")
            return {}
    
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