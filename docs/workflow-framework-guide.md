# WorkFlow 定时任务框架

一个简单的 Python 定时任务框架，支持后台循环执行任务。

## 特性

- 🕒 **定时执行**: 支持按时间间隔自动执行任务
- 🔄 **后台运行**: 可在后台持续运行，无需人工干预
- 📊 **状态管理**: 实时监控任务状态和执行情况
- 🛠️ **简单易用**: 最小化设计，易于扩展和使用
- 🔧 **灵活配置**: 支持启用/禁用任务，动态调整执行间隔

## 核心组件

### 1. Task (任务基类)
```python
from HomeSystem.workflow import Task

class MyTask(Task):
    def __init__(self):
        super().__init__("my_task", interval_seconds=60)  # 每60秒执行一次
        
    async def run(self):
        # 实现你的任务逻辑
        return {"status": "completed", "data": "task result"}
```

### 2. WorkflowEngine (工作流引擎)
```python
from HomeSystem.workflow import WorkflowEngine

engine = WorkflowEngine()
engine.add_task(MyTask())
await engine.run()  # 启动引擎，开始执行任务
```

## 快速开始

### 1. 创建一个简单任务
```python
import asyncio
from typing import Dict, Any
from HomeSystem.workflow import Task, WorkflowEngine

class HelloTask(Task):
    def __init__(self):
        super().__init__("hello", interval_seconds=5)
        
    async def run(self) -> Dict[str, Any]:
        print("Hello from scheduled task!")
        return {"message": "Hello executed"}

async def main():
    engine = WorkflowEngine()
    engine.add_task(HelloTask())
    await engine.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. 运行示例
```bash
cd /mnt/nfs_share/code/homesystem
python examples/workflow_example.py
```

## API 参考

### Task 类

#### 构造函数
```python
Task(name: str, interval_seconds: int)
```
- `name`: 任务名称（唯一标识）
- `interval_seconds`: 执行间隔（秒）

#### 主要方法
- `async run() -> Dict[str, Any]`: 实现任务逻辑（必须重写）
- `should_run() -> bool`: 判断是否应该执行
- `enable()`: 启用任务
- `disable()`: 禁用任务
- `get_info() -> Dict`: 获取任务信息

#### 属性
- `name`: 任务名称
- `interval_seconds`: 执行间隔
- `is_running`: 是否正在运行
- `enabled`: 是否启用
- `last_run`: 上次运行时间戳

### WorkflowEngine 类

#### 主要方法
- `add_task(task: Task)`: 添加任务
- `remove_task(task_name: str) -> bool`: 移除任务
- `get_task(task_name: str) -> Task`: 获取任务
- `list_tasks() -> List[Dict]`: 列出所有任务
- `async run()`: 运行引擎（阻塞）
- `shutdown()`: 关闭引擎
- `get_status() -> Dict`: 获取引擎状态

## 实际应用示例

### 论文收集任务
```python
from HomeSystem.workflow import PaperGatherTask, WorkflowEngine

async def main():
    engine = WorkflowEngine()
    
    # 添加论文收集任务，每小时执行一次
    paper_task = PaperGatherTask(interval_seconds=3600)
    engine.add_task(paper_task)
    
    await engine.run()
```

### 数据库清理任务
```python
class DatabaseCleanupTask(Task):
    def __init__(self):
        super().__init__("db_cleanup", interval_seconds=86400)  # 每天一次
        
    async def run(self):
        # 清理过期数据
        deleted_count = await cleanup_expired_data()
        return {"deleted_records": deleted_count}
```

## 注意事项

1. **任务执行时间**: 如果任务执行时间超过间隔时间，下次执行会等待当前任务完成
2. **异常处理**: 任务中的异常会被自动捕获并记录，不会影响其他任务
3. **资源管理**: 长时间运行的任务应注意资源释放
4. **信号处理**: 支持 Ctrl+C (SIGINT) 和 SIGTERM 信号优雅关闭

## 扩展开发

基于这个框架，你可以轻松实现：
- 定时数据采集
- 日志清理
- 健康检查
- 数据同步
- 报告生成
- 等等...

只需继承 `Task` 类并实现 `run()` 方法即可！