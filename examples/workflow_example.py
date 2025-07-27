"""
工作流框架使用示例
"""
import asyncio
import logging
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))  # 添加上级目录到路径，以便导入 HomeSystem
from HomeSystem.workflow.task import Task
from HomeSystem.workflow.engine import WorkflowEngine
from HomeSystem.workflow import PaperGatherTask

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class HelloTask(Task):
    """简单的问候任务示例"""
    
    def __init__(self):
        super().__init__("hello_task", interval_seconds=5)  # 每5秒执行一次
        
    async def run(self) -> Dict[str, Any]:
        """执行问候逻辑"""
        return {"message": "Hello from scheduled task!"}


class CounterTask(Task):
    """计数器任务示例"""
    
    def __init__(self):
        super().__init__("counter_task", interval_seconds=10)  # 每10秒执行一次
        self.count = 0
        
    async def run(self) -> Dict[str, Any]:
        """执行计数逻辑"""
        self.count += 1
        return {"count": self.count, "message": f"Counter is now: {self.count}"}


async def main():
    """主函数"""
    # 创建工作流引擎
    engine = WorkflowEngine()
    
    # 添加任务
    engine.add_task(HelloTask())
    engine.add_task(CounterTask())
    engine.add_task(PaperGatherTask())  # 每30秒执行一次（用于测试）
    
    print("工作流引擎已启动，任务列表：")
    for task_info in engine.list_tasks():
        print(f"- {task_info['name']}: 每{task_info['interval_seconds']}秒执行一次")
    
    print("\n按 Ctrl+C 停止引擎...")
    
    # 运行引擎
    await engine.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"程序出错: {e}")
        logging.exception("程序异常")