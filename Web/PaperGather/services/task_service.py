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
import signal
import time


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
        # 初始化超时设置 (30秒)
        self.initialization_timeout = 30
        
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
        
        # 持久化的定时任务数据 (task_id -> persistent_task_data)
        self.persistent_scheduled_tasks: Dict[str, Dict[str, Any]] = {}
        
        # 任务状态存储
        self.task_scheduler: Optional[TaskScheduler] = None
        self.scheduled_tasks: Dict[str, PaperGatherTask] = {}
        self.task_results: Dict[str, TaskResult] = {}
        
        # 延迟初始化LLM工厂以避免启动阻塞
        self.llm_factory = None
        
        # 启动时快速加载数据，延迟初始化服务
        self._load_historical_data()
        self._load_persistent_scheduled_tasks_non_blocking()
    
    def _initialize_llm_factory_with_timeout(self) -> bool:
        """带超时保护的LLM工厂初始化"""
        if self.llm_factory is not None:
            return True
            
        def timeout_handler(signum, frame):
            raise TimeoutError("LLM工厂初始化超时")
        
        try:
            # 设置超时信号
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.initialization_timeout)
            
            logger.info("正在初始化LLM工厂...")
            self.llm_factory = LLMFactory()
            logger.info("✅ LLM工厂初始化成功")
            
            # 取消超时
            signal.alarm(0)
            return True
            
        except TimeoutError:
            logger.error(f"❌ LLM工厂初始化超时 ({self.initialization_timeout}秒)")
            return False
        except Exception as e:
            logger.error(f"❌ LLM工厂初始化失败: {e}")
            return False
        finally:
            # 确保取消超时信号
            signal.alarm(0)
    
    def _load_persistent_scheduled_tasks_non_blocking(self):
        """非阻塞加载持久化定时任务"""
        try:
            persistent_tasks = self.data_manager.load_scheduled_tasks()
            logger.info(f"从持久化存储获取到 {len(persistent_tasks)} 个定时任务")
            
            with self.lock:
                loaded_count = 0
                for task_data in persistent_tasks:
                    try:
                        task_id = task_data.get("task_id")
                        status = task_data.get("status", "running")
                        
                        if not task_id:
                            continue
                        
                        # 只加载状态信息，不立即重启任务
                        if status in ["running", "paused"]:
                            self.persistent_scheduled_tasks[task_id] = task_data
                            loaded_count += 1
                            logger.info(f"记录定时任务 {task_id}，状态: {status} (稍后重启)")
                    
                    except Exception as e:
                        logger.warning(f"加载单个定时任务失败: {e}")
                        continue
                
                if loaded_count > 0:
                    logger.info(f"✅ 记录了 {loaded_count} 个定时任务，将在后台启动")
                    
        except Exception as e:
            logger.error(f"❌ 加载定时任务列表失败: {e}")
    
    def initialize_background_services(self):
        """在应用启动后初始化后台服务"""
        def init_in_background():
            try:
                # 初始化LLM工厂
                if not self._initialize_llm_factory_with_timeout():
                    logger.warning("LLM工厂初始化失败，部分功能可能不可用")
                
                # 重启持久化的定时任务
                self._restart_persistent_scheduled_tasks()
                
                logger.info("✅ 后台服务初始化完成")
                
            except Exception as e:
                logger.error(f"❌ 后台服务初始化失败: {e}")
        
        # 在后台线程中执行
        background_thread = threading.Thread(target=init_in_background)
        background_thread.daemon = True
        background_thread.start()
    
    def _restart_persistent_scheduled_tasks(self):
        """重启持久化的定时任务"""
        with self.lock:
            tasks_to_restart = list(self.persistent_scheduled_tasks.items())
        
        for task_id, task_data in tasks_to_restart:
            try:
                if task_data.get("status") == "running":
                    success = self._restart_scheduled_task_from_persistence_timeout(task_id, task_data)
                    if success:
                        logger.info(f"✅ 成功重启定时任务: {task_id}")
                    else:
                        logger.warning(f"⚠️  定时任务重启失败: {task_id}")
            except Exception as e:
                logger.error(f"❌ 重启定时任务 {task_id} 时出错: {e}")
    
    def _load_historical_data(self):
        """加载历史数据到内存 - 增强版本，支持错误恢复和数据兼容性"""
        loaded_count = 0
        error_count = 0
        
        try:
            # 加载最近的任务结果到内存（用于状态查询）
            recent_tasks = self.data_manager.load_task_history(limit=50)
            logger.info(f"从数据库获取到 {len(recent_tasks)} 个历史任务记录")
            
            with self.lock:
                for task_data in recent_tasks:
                    try:
                        task_id = task_data.get("task_id")
                        if not task_id:
                            logger.warning(f"跳过无效任务记录: 缺少task_id - {task_data}")
                            error_count += 1
                            continue
                        
                        # 数据兼容性处理 - 安全解析时间字段
                        start_time = self._safe_parse_datetime(
                            task_data.get("start_time"), 
                            f"任务 {task_id} 的start_time"
                        )
                        if not start_time:
                            error_count += 1
                            continue
                        
                        end_time_str = task_data.get("end_time")
                        end_time = None
                        if end_time_str:
                            end_time = self._safe_parse_datetime(
                                end_time_str, 
                                f"任务 {task_id} 的end_time"
                            )
                        
                        # 安全解析状态字段
                        status_str = task_data.get("status", "completed")
                        try:
                            status = TaskStatus(status_str)
                        except ValueError:
                            logger.warning(f"任务 {task_id} 状态无效: {status_str}, 使用默认状态 'completed'")
                            status = TaskStatus.COMPLETED
                        
                        # 计算进度
                        progress = 1.0 if status == TaskStatus.COMPLETED else 0.0
                        if status == TaskStatus.FAILED:
                            progress = 0.0
                        elif status == TaskStatus.RUNNING:
                            progress = 0.5  # 运行中任务设置为50%进度
                        
                        # 创建TaskResult对象
                        task_result = TaskResult(
                            task_id=task_id,
                            status=status,
                            start_time=start_time,
                            end_time=end_time,
                            result_data=task_data.get("result", {}),
                            error_message=task_data.get("error_message"),
                            progress=progress
                        )
                        
                        self.task_results[task_id] = task_result
                        loaded_count += 1
                        
                    except Exception as task_error:
                        error_count += 1
                        logger.warning(f"加载单个历史任务失败: {task_error}, 任务数据: {task_data}")
                        continue
            
            if loaded_count > 0:
                logger.info(f"✅ 成功加载了 {loaded_count} 个历史任务到内存")
            if error_count > 0:
                logger.warning(f"⚠️  跳过了 {error_count} 个无效的历史任务记录")
            
            # 如果所有任务都加载失败，记录详细错误但不阻止应用启动
            if loaded_count == 0 and len(recent_tasks) > 0:
                logger.error(f"❌ 所有 {len(recent_tasks)} 个历史任务记录都无法加载，但应用将继续启动")
                
        except Exception as e:
            logger.error(f"❌ 加载历史数据失败: {e}")
            logger.info("🔄 应用将在没有历史数据的情况下继续启动")
            # 不抛出异常，让应用继续启动
    
    
    def _restart_scheduled_task_from_persistence(self, task_id: str, task_data: Dict[str, Any]):
        """从持久化数据重启定时任务（用于初始化时调用）"""
        return self._restart_scheduled_task_from_persistence_timeout(task_id, task_data)
    
    def _restart_scheduled_task_from_persistence_timeout(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """带超时保护的任务重启"""
        try:
            # 注意：在后台线程中不能使用signal，所以这里使用简单的超时逻辑
            start_time = time.time()
            timeout_seconds = 15
            
            config_dict = task_data.get("config", {})
            
            # 验证配置有效性
            is_valid, error_msg = self.validate_config(config_dict)
            if not is_valid:
                logger.error(f"定时任务 {task_id} 配置无效，无法重启: {error_msg}")
                self.data_manager.update_scheduled_task(task_id, {
                    "status": "error",
                    "error_message": f"配置验证失败: {error_msg}"
                })
                return False
            
            # 检查是否超时
            if time.time() - start_time > timeout_seconds:
                raise TimeoutError("任务重启超时")
            
            # 重新创建任务
            success, _, error_msg = self._create_scheduled_task_internal(task_id, config_dict)
            if success:
                logger.info(f"✅ 成功重启持久化定时任务: {task_id}")
                return True
            else:
                logger.error(f"❌ 重启定时任务 {task_id} 失败: {error_msg}")
                self.data_manager.update_scheduled_task(task_id, {
                    "status": "error", 
                    "error_message": f"重启失败: {error_msg}"
                })
                return False
                
        except TimeoutError:
            logger.error(f"❌ 重启定时任务 {task_id} 超时")
            self.data_manager.update_scheduled_task(task_id, {
                "status": "error",
                "error_message": "重启超时"
            })
            return False
        except Exception as e:
            logger.error(f"❌ 重启定时任务 {task_id} 时发生异常: {e}")
            self.data_manager.update_scheduled_task(task_id, {
                "status": "error",
                "error_message": f"重启异常: {str(e)}"
            })
            return False
    
    def _safe_parse_datetime(self, date_str, field_description):
        """安全解析日期时间字符串，支持多种格式"""
        if not date_str:
            return None
        
        try:
            # 如果已经是datetime对象，直接返回
            if isinstance(date_str, datetime):
                return date_str
            
            # 尝试解析ISO格式
            if isinstance(date_str, str):
                # 处理带Z结尾的UTC时间
                if date_str.endswith('Z'):
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                # 处理标准ISO格式
                elif 'T' in date_str:
                    return datetime.fromisoformat(date_str)
                # 处理其他常见格式
                else:
                    # 尝试常见的日期格式
                    formats = [
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d %H:%M:%S.%f',
                        '%Y-%m-%dT%H:%M:%S',
                        '%Y-%m-%dT%H:%M:%S.%f',
                        '%Y-%m-%d'
                    ]
                    
                    for fmt in formats:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
            
            logger.warning(f"无法解析日期时间: {field_description} = {date_str}")
            return None
            
        except Exception as e:
            logger.warning(f"解析日期时间时出错: {field_description} = {date_str}, 错误: {e}")
            return None
    
    def get_available_models(self) -> List[str]:
        """获取可用的LLM模型列表 - 增强版本，支持错误恢复和详细诊断"""
        try:
            # 如果LLMFactory未初始化，尝试初始化
            if not self.llm_factory:
                logger.info("LLMFactory未初始化，尝试初始化...")
                if not self._initialize_llm_factory_with_timeout():
                    logger.error("❌ LLMFactory 初始化失败")
                    return self._get_fallback_models("LLMFactory初始化失败")
            
            # 尝试获取模型列表
            chat_models = self.llm_factory.get_available_llm_models()
            
            if not chat_models:
                logger.warning("⚠️  LLMFactory 返回了空的模型列表")
                # 尝试诊断原因
                self._diagnose_llm_config_issues()
                return self._get_fallback_models("没有可用的模型")
            
            logger.info(f"✅ 成功获取 {len(chat_models)} 个可用LLM模型")
            return chat_models
            
        except ImportError as e:
            logger.error(f"❌ LLM依赖包导入失败: {e}")
            return self._get_fallback_models(f"依赖包导入失败: {e}")
        except FileNotFoundError as e:
            logger.error(f"❌ LLM配置文件不存在: {e}")
            return self._get_fallback_models(f"配置文件不存在: {e}")
        except Exception as e:
            logger.error(f"❌ 获取可用模型失败: {e}")
            # 尝试诊断问题
            self._diagnose_llm_config_issues()
            return self._get_fallback_models(f"未知错误: {e}")
    
    def _get_fallback_models(self, reason: str) -> List[str]:
        """获取备用模型列表"""
        fallback_models = [
            "deepseek.DeepSeek_V3",
            "ollama.Qwen3_30B", 
            "ollama.DeepSeek_R1_14B"
        ]
        logger.info(f"🔄 使用备用模型列表: {fallback_models} (原因: {reason})")
        return fallback_models
    
    def _diagnose_llm_config_issues(self):
        """诊断LLM配置问题"""
        try:
            import os
            from pathlib import Path
            
            # 检查配置文件
            config_path = Path(__file__).parent.parent.parent / "HomeSystem" / "graph" / "config" / "llm_providers.yaml"
            if not config_path.exists():
                logger.error(f"❌ LLM配置文件不存在: {config_path}")
            else:
                logger.info(f"✅ LLM配置文件存在: {config_path}")
            
            # 检查环境变量
            api_keys = {
                'DEEPSEEK_API_KEY': os.getenv('DEEPSEEK_API_KEY'),
                'SILICONFLOW_API_KEY': os.getenv('SILICONFLOW_API_KEY'),
                'VOLCANO_API_KEY': os.getenv('VOLCANO_API_KEY'),
                'MOONSHOT_API_KEY': os.getenv('MOONSHOT_API_KEY'),
                'OLLAMA_BASE_URL': os.getenv('OLLAMA_BASE_URL')
            }
            
            logger.info("🔍 环境变量检查:")
            for key, value in api_keys.items():
                if key == 'OLLAMA_BASE_URL':
                    # Ollama URL可以为空，使用默认值
                    status = "✅ 已设置" if value else "ℹ️  使用默认值(http://localhost:11434)"
                else:
                    # API密钥检查
                    if not value:
                        status = "❌ 未设置"
                    elif value.startswith('your_'):
                        status = "⚠️  未配置(使用示例值)"
                    else:
                        status = "✅ 已设置"
                
                logger.info(f"  {key}: {status}")
            
            # 检查Ollama连接
            self._check_ollama_connection()
            
        except Exception as e:
            logger.error(f"诊断LLM配置时出错: {e}")
    
    def _check_ollama_connection(self):
        """检查Ollama服务连接"""
        try:
            import requests
            import os
            
            ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
            
            # 尝试连接Ollama
            response = requests.get(f"{ollama_url}/api/tags", timeout=5)
            
            if response.status_code == 200:
                models_data = response.json()
                model_count = len(models_data.get('models', []))
                logger.info(f"✅ Ollama服务连接正常，发现 {model_count} 个本地模型")
                
                # 列出可用的本地模型
                if model_count > 0:
                    model_names = [model.get('name', 'unknown') for model in models_data.get('models', [])]
                    logger.info(f"   本地模型: {', '.join(model_names[:5])}{'...' if model_count > 5 else ''}")
            else:
                logger.warning(f"⚠️  Ollama服务响应异常: HTTP {response.status_code}")
                
        except requests.ConnectionError:
            logger.warning(f"⚠️  无法连接到Ollama服务 ({ollama_url})")
            logger.info("   请检查Ollama是否已启动: ollama serve")
        except requests.Timeout:
            logger.warning(f"⚠️  连接Ollama服务超时 ({ollama_url})")
        except ImportError:
            logger.warning("⚠️  requests包未安装，无法检查Ollama连接")
        except Exception as e:
            logger.warning(f"⚠️  检查Ollama连接时出错: {e}")
    
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
        """验证配置参数 - 增强版本，支持类型转换和详细错误信息"""
        try:
            if not isinstance(config_dict, dict):
                return False, "配置必须是字典格式"
            
            # 检查必需参数
            required_fields = ['search_query', 'user_requirements', 'llm_model_name', 'task_name']
            for field in required_fields:
                value = config_dict.get(field)
                if not value or (isinstance(value, str) and not value.strip()):
                    if field == 'task_name':
                        return False, "任务名称不能为空，请输入有意义的任务名称"
                    return False, f"缺少必需参数或参数为空: {field}"
            
            # 特殊验证任务名称长度
            task_name = config_dict.get('task_name', '').strip()
            if len(task_name) < 1 or len(task_name) > 100:
                return False, "任务名称长度必须在1-100个字符之间"
            
            # 数值范围验证 - 支持字符串转换
            validation_rules = [
                {
                    'field': 'relevance_threshold',
                    'default': 0.7,
                    'min': 0.0,
                    'max': 1.0,
                    'type': float,
                    'description': '相关性阈值'
                },
                {
                    'field': 'summarization_threshold', 
                    'default': 0.8,
                    'min': 0.0,
                    'max': 1.0,
                    'type': float,
                    'description': '摘要生成阈值'
                },
                {
                    'field': 'max_papers_per_search',
                    'default': 20,
                    'min': 1,
                    'max': 100,
                    'type': int,
                    'description': '每次搜索的最大论文数'
                },
                {
                    'field': 'max_papers_in_response',
                    'default': 50,
                    'min': 1,
                    'max': 200,
                    'type': int,
                    'description': '响应中的最大论文数'
                },
                {
                    'field': 'max_relevant_papers_in_response',
                    'default': 10,
                    'min': 1,
                    'max': 50,
                    'type': int,
                    'description': '响应中的最大相关论文数'
                }
            ]
            
            for rule in validation_rules:
                field = rule['field']
                value = config_dict.get(field, rule['default'])
                
                # 类型转换和验证
                try:
                    if rule['type'] == float:
                        converted_value = float(value)
                    elif rule['type'] == int:
                        converted_value = int(float(value))  # 支持 "20.0" -> 20
                    else:
                        converted_value = value
                    
                    # 范围检查
                    if not (rule['min'] <= converted_value <= rule['max']):
                        return False, f"{rule['description']} 必须在 {rule['min']}-{rule['max']} 范围内，当前值: {converted_value}"
                    
                    # 更新配置中的值（确保类型正确）
                    config_dict[field] = converted_value
                    
                except (ValueError, TypeError) as e:
                    return False, f"{rule['description']} 格式无效: {value} (错误: {e})"
            
            # 布尔值验证和转换
            boolean_fields = ['enable_paper_summarization', 'enable_translation']
            for field in boolean_fields:
                if field in config_dict:
                    value = config_dict[field]
                    if isinstance(value, str):
                        if value.lower() in ['true', '1', 'yes', 'on']:
                            config_dict[field] = True
                        elif value.lower() in ['false', '0', 'no', 'off']:
                            config_dict[field] = False
                        else:
                            return False, f"{field} 必须是布尔值"
                    elif not isinstance(value, bool):
                        return False, f"{field} 必须是布尔值"
            
            # 模型可用性检查（使用更宽松的检查）
            llm_model_name = config_dict.get('llm_model_name')
            available_models = self.get_available_models()
            
            if llm_model_name not in available_models:
                # 记录警告但不阻止配置（允许用户使用新模型）
                logger.warning(f"⚠️  LLM模型 '{llm_model_name}' 当前不在可用列表中")
                logger.info(f"   可用模型: {', '.join(available_models[:5])}{'...' if len(available_models) > 5 else ''}")
                # 不返回错误，允许用户使用未在列表中的模型
            
            # 验证搜索模式相关参数
            search_mode = config_dict.get('search_mode', 'latest')
            try:
                mode_enum = ArxivSearchMode(search_mode)
            except ValueError:
                available_modes = [mode.value for mode in ArxivSearchMode]
                return False, f"无效的搜索模式: {search_mode}，可用模式: {', '.join(available_modes)}"
            
            # 验证日期范围搜索参数
            if mode_enum == ArxivSearchMode.DATE_RANGE:
                start_year = config_dict.get('start_year')
                end_year = config_dict.get('end_year')
                
                if start_year is None or end_year is None:
                    return False, "日期范围搜索模式需要提供起始年份和结束年份"
                
                # 类型转换
                try:
                    start_year = int(start_year)
                    end_year = int(end_year)
                    config_dict['start_year'] = start_year
                    config_dict['end_year'] = end_year
                except (ValueError, TypeError):
                    return False, "起始年份和结束年份必须是整数"
                
                # 逻辑检查
                if start_year > end_year:
                    return False, f"起始年份 ({start_year}) 不能大于结束年份 ({end_year})"
                if start_year < 1991:  # ArXiv 1991年开始
                    return False, f"起始年份 ({start_year}) 不能早于1991年"
                
                current_year = datetime.now().year
                if end_year > current_year:
                    return False, f"结束年份 ({end_year}) 不能大于当前年份 ({current_year})"
                
            # 验证某年之后搜索参数
            elif mode_enum == ArxivSearchMode.AFTER_YEAR:
                after_year = config_dict.get('after_year')
                if after_year is None:
                    return False, "某年之后搜索模式需要提供after_year参数"
                
                try:
                    after_year = int(after_year)
                    config_dict['after_year'] = after_year
                except (ValueError, TypeError):
                    return False, "after_year必须是整数"
                
                if after_year < 1991:
                    return False, f"after_year ({after_year}) 不能早于1991年"
                
                current_year = datetime.now().year
                if after_year > current_year:
                    return False, f"after_year ({after_year}) 不能大于当前年份 ({current_year})"
            
            logger.info("✅ 配置验证通过")
            return True, None
            
        except Exception as e:
            error_msg = f"配置验证时发生异常: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
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
                'search_mode', 'start_year', 'end_year', 'after_year',
                # 任务追踪相关参数
                'task_name', 'task_id'
            }
            filtered_config = {k: v for k, v in config_dict_copy.items() if k in valid_params}
            
            # 添加任务追踪信息
            filtered_config['task_id'] = task_id  # 使用生成的任务ID
            if 'task_name' not in filtered_config:
                filtered_config['task_name'] = 'paper_gather'  # 默认任务名称
            
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
        启动后台定时任务 - 增强版本，支持持久化
        """
        try:
            task_id = str(uuid.uuid4())
            
            # 先保存到持久化存储
            success = self.data_manager.save_scheduled_task(task_id, config_dict, "running")
            if not success:
                return False, "", "保存定时任务到持久化存储失败"
            
            # 创建运行时任务
            success, _, error_msg = self._create_scheduled_task_internal(task_id, config_dict)
            if success:
                # 更新持久化数据缓存
                with self.lock:
                    self.persistent_scheduled_tasks[task_id] = {
                        "task_id": task_id,
                        "config": config_dict,
                        "status": "running",
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                        "execution_count": 0,
                        "last_executed_at": None,
                        "next_execution_at": None,
                        "error_message": None
                    }
                
                logger.info(f"后台定时任务已启动并持久化: {task_id}")
                return True, task_id, None
            else:
                # 创建失败，删除持久化数据
                self.data_manager.delete_scheduled_task(task_id)
                return False, "", error_msg
            
        except Exception as e:
            error_msg = f"启动后台任务失败: {str(e)}"
            logger.error(error_msg)
            return False, "", error_msg
    
    def _create_scheduled_task_internal(self, task_id: str, config_dict: Dict[str, Any]) -> tuple[bool, str, Optional[str]]:
        """
        内部方法：创建定时任务的运行时实例
        """
        try:
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
                'search_mode', 'start_year', 'end_year', 'after_year',
                # 任务追踪相关参数
                'task_name', 'task_id'
            }
            filtered_config = {k: v for k, v in config_dict.items() if k in valid_params}
            
            # 添加任务追踪信息
            filtered_config['task_id'] = task_id  # 使用指定的任务ID
            if 'task_name' not in filtered_config:
                filtered_config['task_name'] = 'paper_gather_scheduled'  # 定时任务名称
            
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
            
            logger.info(f"运行时定时任务已创建: {task_id}, 间隔: {config.interval_seconds}秒")
            return True, task_id, None
            
        except Exception as e:
            error_msg = f"创建运行时定时任务失败: {str(e)}"
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
        """停止后台定时任务 - 增强版本，支持持久化"""
        try:
            with self.lock:
                # 检查运行时任务
                if task_id in self.scheduled_tasks:
                    task = self.scheduled_tasks[task_id]
                    
                    # 从调度器中移除任务
                    if self.task_scheduler:
                        self.task_scheduler.remove_task(task.name)
                    
                    # 清理运行时任务记录
                    del self.scheduled_tasks[task_id]
                
                # 检查持久化任务
                if task_id in self.persistent_scheduled_tasks:
                    # 清理持久化缓存
                    del self.persistent_scheduled_tasks[task_id]
            
            # 更新持久化存储状态
            success = self.data_manager.update_scheduled_task(task_id, {
                "status": "stopped",
                "error_message": None
            })
            
            if not success:
                logger.warning(f"更新持久化定时任务状态失败: {task_id}")
            
            logger.info(f"后台定时任务已停止: {task_id}")
            return True, None
            
        except Exception as e:
            error_msg = f"停止后台任务失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """获取所有后台定时任务状态 - 增强版本，包含持久化信息"""
        tasks = []
        with self.lock:
            # 遍历持久化任务数据（这是权威数据源）
            for task_id, persistent_data in self.persistent_scheduled_tasks.items():
                task_info = {
                    'task_id': task_id,
                    'name': persistent_data.get('config', {}).get('task_name', 'paper_gather_scheduled'),
                    'interval_seconds': persistent_data.get('config', {}).get('interval_seconds', 3600),
                    'config': persistent_data.get('config', {}),
                    'status': persistent_data.get('status', 'unknown'),
                    'created_at': persistent_data.get('created_at'),
                    'updated_at': persistent_data.get('updated_at'),
                    'execution_count': persistent_data.get('execution_count', 0),
                    'last_executed_at': persistent_data.get('last_executed_at'),
                    'next_execution_at': persistent_data.get('next_execution_at'),
                    'error_message': persistent_data.get('error_message'),
                    'is_running': task_id in self.scheduled_tasks  # 运行时状态
                }
                tasks.append(task_info)
            
            # 检查是否有运行时任务但没有持久化数据的情况（异常情况）
            for task_id, task in self.scheduled_tasks.items():
                if task_id not in self.persistent_scheduled_tasks:
                    logger.warning(f"发现未持久化的运行时任务: {task_id}")
                    task_info = {
                        'task_id': task_id,
                        'name': task.name,
                        'interval_seconds': task.interval_seconds,
                        'config': task.config.get_config_dict() if hasattr(task.config, 'get_config_dict') else {},
                        'status': 'running',
                        'created_at': None,
                        'updated_at': None,
                        'execution_count': 0,
                        'last_executed_at': None,
                        'next_execution_at': None,
                        'error_message': None,
                        'is_running': True
                    }
                    tasks.append(task_info)
        
        # 按创建时间排序
        tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
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
            config = self.data_manager.get_task_config_compatible(task_id)
            if config:
                # 处理枚举序列化问题
                config = self._serialize_config_for_json(config)
            return config
        except Exception as e:
            logger.error(f"获取任务配置失败: {e}")
            return None
    
    def _serialize_config_for_json(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """将配置中的特殊对象序列化为JSON可序列化的格式"""
        serialized_config = config.copy()
        
        # 处理ArxivSearchMode枚举
        if 'search_mode' in serialized_config and isinstance(serialized_config['search_mode'], ArxivSearchMode):
            serialized_config['search_mode'] = serialized_config['search_mode'].value
        
        return serialized_config
    
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
            presets = self.data_manager.load_config_presets()
            # 处理每个预设中的序列化问题
            for preset in presets:
                if 'config' in preset:
                    preset['config'] = self._serialize_config_for_json(preset['config'])
            return presets
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
    
    def update_task_history(self, task_id: str, updated_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """更新历史任务记录"""
        try:
            # 验证更新数据
            if "config" in updated_data:
                # 验证配置的有效性
                is_valid, error_msg = self.validate_config(updated_data["config"])
                if not is_valid:
                    return False, f"配置验证失败: {error_msg}"
            
            # 更新持久化存储
            success = self.data_manager.update_task_history(task_id, updated_data)
            
            if success and "config" in updated_data:
                # 同步更新内存缓存中的任务（如果存在）
                with self.lock:
                    if task_id in self.task_results:
                        # 这里暂不更新内存中的任务配置，因为TaskResult对象不包含config字段
                        # 内存中主要是运行时状态，历史配置存储在持久化层
                        logger.info(f"任务 {task_id} 配置已在持久化存储中更新")
            
            return success, None if success else "更新历史任务失败，未找到指定任务"
            
        except Exception as e:
            error_msg = f"更新历史任务失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def delete_task_history(self, task_id: str) -> tuple[bool, Optional[str]]:
        """删除历史任务记录"""
        try:
            # 从持久化存储删除
            success = self.data_manager.delete_task_history(task_id)
            
            if success:
                # 同步删除内存缓存中的任务
                with self.lock:
                    if task_id in self.task_results:
                        del self.task_results[task_id]
                        logger.info(f"已从内存缓存中删除任务: {task_id}")
                
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
    
    # === 新增定时任务管理方法 ===
    
    def pause_scheduled_task(self, task_id: str) -> tuple[bool, Optional[str]]:
        """暂停定时任务"""
        try:
            with self.lock:
                # 检查并停止运行时任务
                if task_id in self.scheduled_tasks:
                    task = self.scheduled_tasks[task_id]
                    
                    # 从调度器中移除任务
                    if self.task_scheduler:
                        self.task_scheduler.remove_task(task.name)
                    
                    # 清理运行时任务记录
                    del self.scheduled_tasks[task_id]
            
            # 更新持久化存储状态为暂停
            success = self.data_manager.update_scheduled_task(task_id, {
                "status": "paused",
                "error_message": None
            })
            
            if success:
                # 更新内存缓存
                with self.lock:
                    if task_id in self.persistent_scheduled_tasks:
                        self.persistent_scheduled_tasks[task_id]["status"] = "paused"
                        self.persistent_scheduled_tasks[task_id]["updated_at"] = datetime.now().isoformat()
                
                logger.info(f"定时任务已暂停: {task_id}")
                return True, None
            else:
                return False, "更新任务状态失败"
            
        except Exception as e:
            error_msg = f"暂停定时任务失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def resume_scheduled_task(self, task_id: str) -> tuple[bool, Optional[str]]:
        """恢复定时任务"""
        try:
            # 获取持久化任务数据
            task_data = self.data_manager.get_scheduled_task(task_id)
            if not task_data:
                return False, "任务不存在"
            
            if task_data.get("status") != "paused":
                return False, f"任务状态不是暂停状态，当前状态: {task_data.get('status')}"
            
            # 验证配置有效性
            config_dict = task_data.get("config", {})
            is_valid, error_msg = self.validate_config(config_dict)
            if not is_valid:
                return False, f"任务配置无效: {error_msg}"
            
            # 重新创建运行时任务
            success, _, error_msg = self._create_scheduled_task_internal(task_id, config_dict)
            if success:
                # 更新持久化存储状态
                self.data_manager.update_scheduled_task(task_id, {
                    "status": "running",
                    "error_message": None
                })
                
                # 更新内存缓存
                with self.lock:
                    if task_id in self.persistent_scheduled_tasks:
                        self.persistent_scheduled_tasks[task_id]["status"] = "running"
                        self.persistent_scheduled_tasks[task_id]["updated_at"] = datetime.now().isoformat()
                
                logger.info(f"定时任务已恢复: {task_id}")
                return True, None
            else:
                return False, f"重新创建任务失败: {error_msg}"
            
        except Exception as e:
            error_msg = f"恢复定时任务失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def update_scheduled_task_config(self, task_id: str, new_config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """更新定时任务配置"""
        try:
            # 验证新配置
            is_valid, error_msg = self.validate_config(new_config)
            if not is_valid:
                return False, f"新配置验证失败: {error_msg}"
            
            # 获取现有任务数据
            task_data = self.data_manager.get_scheduled_task(task_id)
            if not task_data:
                return False, "任务不存在"
            
            old_status = task_data.get("status")
            was_running = old_status == "running" and task_id in self.scheduled_tasks
            
            # 如果任务正在运行，先停止它
            if was_running:
                self.pause_scheduled_task(task_id)
            
            # 更新持久化配置
            success = self.data_manager.update_scheduled_task(task_id, {
                "config": new_config,
                "status": old_status,  # 保持原状态
                "error_message": None
            })
            
            if not success:
                return False, "更新持久化配置失败"
            
            # 更新内存缓存
            with self.lock:
                if task_id in self.persistent_scheduled_tasks:
                    self.persistent_scheduled_tasks[task_id]["config"] = new_config
                    self.persistent_scheduled_tasks[task_id]["updated_at"] = datetime.now().isoformat()
            
            # 如果之前在运行，重新启动
            if was_running:
                resume_success, resume_error = self.resume_scheduled_task(task_id)
                if not resume_success:
                    logger.warning(f"配置更新成功但恢复任务失败: {resume_error}")
                    return True, f"配置已更新，但恢复任务失败: {resume_error}"
            
            logger.info(f"定时任务配置已更新: {task_id}")
            return True, None
            
        except Exception as e:
            error_msg = f"更新定时任务配置失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_scheduled_task_detail(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取定时任务详情"""
        try:
            # 从持久化存储获取最新数据
            task_data = self.data_manager.get_scheduled_task(task_id)
            if not task_data:
                return None
            
            # 添加运行时状态信息
            with self.lock:
                task_data["is_running"] = task_id in self.scheduled_tasks
            
            return task_data
            
        except Exception as e:
            logger.error(f"获取定时任务详情失败: {e}")
            return None
    
    def delete_scheduled_task_permanently(self, task_id: str) -> tuple[bool, Optional[str]]:
        """永久删除定时任务（包括持久化数据）"""
        try:
            # 先停止任务
            self.stop_scheduled_task(task_id)
            
            # 删除持久化数据
            success = self.data_manager.delete_scheduled_task(task_id)
            
            # 清理内存缓存
            with self.lock:
                if task_id in self.persistent_scheduled_tasks:
                    del self.persistent_scheduled_tasks[task_id]
            
            if success:
                logger.info(f"定时任务已永久删除: {task_id}")
                return True, None
            else:
                return False, "删除持久化数据失败"
            
        except Exception as e:
            error_msg = f"永久删除定时任务失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg


# 全局服务实例
paper_gather_service = PaperGatherService()