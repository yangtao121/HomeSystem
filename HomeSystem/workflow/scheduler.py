"""
任务调度器
"""
import asyncio
import time
from typing import List, Dict, Any
import logging
from .task import Task

logger = logging.getLogger(__name__)


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, check_interval: int = 1):
        self.tasks: List[Task] = []
        self.check_interval = check_interval  # 检查间隔（秒）
        self.running = False
        self._stop_event = asyncio.Event()
        
    def add_task(self, task: Task):
        """添加任务"""
        self.tasks.append(task)
        logger.info(f"添加任务: {task.name}")
        
    def remove_task(self, task_name: str) -> bool:
        """移除任务"""
        for i, task in enumerate(self.tasks):
            if task.name == task_name:
                del self.tasks[i]
                logger.info(f"移除任务: {task_name}")
                return True
        return False
        
    def get_task(self, task_name: str) -> Task:
        """获取任务"""
        for task in self.tasks:
            if task.name == task_name:
                return task
        return None
        
    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有任务信息"""
        return [task.get_info() for task in self.tasks]
        
    async def run_once(self) -> Dict[str, Any]:
        """执行一轮检查"""
        results = []
        
        for task in self.tasks:
            if task.should_run():
                result = await task.execute()
                results.append({
                    "task_name": task.name,
                    "result": result
                })
                
        return {
            "timestamp": time.time(),
            "executed_tasks": len(results),
            "results": results
        }
        
    async def start(self):
        """启动调度器"""
        if self.running:
            logger.warning("调度器已在运行")
            return
            
        self.running = True
        self._stop_event.clear()
        logger.info("启动任务调度器")
        
        try:
            while self.running and not self._stop_event.is_set():
                await self.run_once()
                
                # 等待下次检查，但可以被停止事件中断
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), 
                        timeout=self.check_interval
                    )
                    break  # 如果等到了停止事件，退出循环
                except asyncio.TimeoutError:
                    continue  # 超时是正常的，继续下一轮
                    
        except Exception as e:
            logger.error(f"调度器运行出错: {e}")
        finally:
            self.running = False
            logger.info("任务调度器已停止")
            
    def stop(self):
        """停止调度器"""
        logger.info("请求停止任务调度器")
        self.running = False
        self._stop_event.set()
        
    async def stop_and_wait(self):
        """停止调度器并等待完成"""
        self.stop()
        while self.running:
            await asyncio.sleep(0.1)
            
    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        return {
            "running": self.running,
            "check_interval": self.check_interval,
            "total_tasks": len(self.tasks),
            "enabled_tasks": len([t for t in self.tasks if t.enabled]),
            "running_tasks": len([t for t in self.tasks if t.is_running])
        }