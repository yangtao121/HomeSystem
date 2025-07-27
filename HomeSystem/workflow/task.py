"""
简单的定时任务框架
"""
import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class Task(ABC):
    """定时任务基类"""
    
    def __init__(self, name: str, interval_seconds: int):
        self.name = name
        self.interval_seconds = interval_seconds
        self.last_run = 0
        self.is_running = False
        self.enabled = True
        
    @abstractmethod
    async def run(self) -> Dict[str, Any]:
        """执行任务逻辑，返回结果字典"""
        pass
    
    def should_run(self) -> bool:
        """判断是否应该执行"""
        if not self.enabled or self.is_running:
            return False
        return time.time() - self.last_run >= self.interval_seconds
    
    async def execute(self) -> Dict[str, Any]:
        """执行任务包装器"""
        if not self.should_run():
            return {"status": "skipped", "reason": "not ready to run"}
            
        self.is_running = True
        start_time = time.time()
        
        try:
            logger.info(f"开始执行任务: {self.name}")
            result = await self.run()
            result["status"] = "success"
            result["duration"] = time.time() - start_time
            logger.info(f"任务完成: {self.name}, 耗时: {result['duration']:.2f}秒")
            return result
            
        except Exception as e:
            error_result = {
                "status": "error",
                "error": str(e),
                "duration": time.time() - start_time
            }
            logger.error(f"任务执行失败: {self.name}, 错误: {e}")
            return error_result
            
        finally:
            self.last_run = time.time()
            self.is_running = False
    
    def enable(self):
        """启用任务"""
        self.enabled = True
        
    def disable(self):
        """禁用任务"""
        self.enabled = False
        
    def get_info(self) -> Dict[str, Any]:
        """获取任务信息"""
        return {
            "name": self.name,
            "interval_seconds": self.interval_seconds,
            "last_run": datetime.fromtimestamp(self.last_run).isoformat() if self.last_run else None,
            "is_running": self.is_running,
            "enabled": self.enabled,
            "next_run_in": max(0, self.interval_seconds - (time.time() - self.last_run))
        }