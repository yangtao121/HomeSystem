"""
简单的定时任务框架
"""
import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Task(ABC):
    """定时任务基类"""
    
    def __init__(self, name: str, interval_seconds: int, delay_first_run: bool = False):
        self.name = name
        self.interval_seconds = interval_seconds
        self.last_run = 0
        self.is_running = False
        self.enabled = True
        self.delay_first_run = delay_first_run
        self.next_run_time: Optional[datetime] = None
        self.manual_trigger_requested = False
        
        # 如果启用延迟首次运行，设置下次运行时间为当前时间 + 间隔
        if delay_first_run:
            self.schedule_next_run()
        
    @abstractmethod
    async def run(self) -> Dict[str, Any]:
        """执行任务逻辑，返回结果字典"""
        pass
    
    def should_run(self) -> bool:
        """判断是否应该执行"""
        if not self.enabled or self.is_running:
            return False
        
        # 如果有手动触发请求，立即执行
        if self.manual_trigger_requested:
            return True
        
        # 如果设置了具体的下次运行时间，使用该时间判断
        if self.next_run_time is not None:
            return datetime.now() >= self.next_run_time
        
        # 传统的基于间隔时间的判断（向后兼容）
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
            
            # 重置手动触发标志
            if self.manual_trigger_requested:
                self.manual_trigger_requested = False
                logger.info(f"手动触发的任务执行完成: {self.name}")
            
            # 安排下次运行时间
            self.schedule_next_run()
    
    def enable(self):
        """启用任务"""
        self.enabled = True
        
    def disable(self):
        """禁用任务"""
        self.enabled = False
        
    def schedule_next_run(self):
        """安排下次运行时间"""
        if self.delay_first_run or self.next_run_time is not None:
            # 使用精确的时间调度
            self.next_run_time = datetime.now() + timedelta(seconds=self.interval_seconds)
            logger.debug(f"任务 {self.name} 下次运行时间: {self.next_run_time}")
    
    def trigger_manual_run(self):
        """手动触发任务执行"""
        if self.is_running:
            logger.warning(f"任务 {self.name} 正在运行中，无法手动触发")
            return False
        
        self.manual_trigger_requested = True
        logger.info(f"手动触发任务: {self.name}")
        return True
    
    def get_next_run_time(self) -> Optional[datetime]:
        """获取下次运行时间"""
        if self.next_run_time is not None:
            return self.next_run_time
        elif self.last_run > 0:
            # 基于上次运行时间计算
            return datetime.fromtimestamp(self.last_run + self.interval_seconds)
        else:
            # 首次运行
            if self.delay_first_run:
                return datetime.now() + timedelta(seconds=self.interval_seconds)
            else:
                return datetime.now()  # 立即运行
    
    def get_info(self) -> Dict[str, Any]:
        """获取任务信息"""
        next_run_time = self.get_next_run_time()
        next_run_in_seconds = 0
        
        if next_run_time:
            next_run_in_seconds = max(0, (next_run_time - datetime.now()).total_seconds())
        
        return {
            "name": self.name,
            "interval_seconds": self.interval_seconds,
            "last_run": datetime.fromtimestamp(self.last_run).isoformat() if self.last_run else None,
            "is_running": self.is_running,
            "enabled": self.enabled,
            "next_run_in": next_run_in_seconds,
            "next_run_time": next_run_time.isoformat() if next_run_time else None,
            "delay_first_run": self.delay_first_run,
            "manual_trigger_requested": self.manual_trigger_requested
        }