"""
工作流引擎
"""
import asyncio
import signal
import logging
from typing import Dict, Any, List
from .scheduler import TaskScheduler
from .task import Task

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self):
        self.scheduler = TaskScheduler()
        self._shutdown_event = asyncio.Event()
        
    def add_task(self, task: Task):
        """添加任务到调度器"""
        self.scheduler.add_task(task)
        
    def remove_task(self, task_name: str) -> bool:
        """从调度器移除任务"""
        return self.scheduler.remove_task(task_name)
        
    def get_task(self, task_name: str) -> Task:
        """获取任务"""
        return self.scheduler.get_task(task_name)
        
    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有任务"""
        return self.scheduler.list_tasks()
        
    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        return {
            "engine_running": not self._shutdown_event.is_set(),
            "scheduler": self.scheduler.get_status()
        }
        
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，开始关闭...")
            self._shutdown_event.set()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    async def run(self):
        """运行工作流引擎"""
        logger.info("启动工作流引擎")
        self._setup_signal_handlers()
        
        try:
            # 启动调度器任务
            scheduler_task = asyncio.create_task(self.scheduler.start())
            
            # 等待关闭信号
            await self._shutdown_event.wait()
            
            logger.info("开始关闭工作流引擎...")
            
            # 停止调度器
            await self.scheduler.stop_and_wait()
            
            # 取消调度器任务
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass
                
        except Exception as e:
            logger.error(f"引擎运行出错: {e}")
        finally:
            logger.info("工作流引擎已停止")
            
    def shutdown(self):
        """关闭引擎"""
        self._shutdown_event.set()
        
    async def run_in_background(self):
        """在后台运行引擎"""
        return asyncio.create_task(self.run())