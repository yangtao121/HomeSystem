# PaperGather 数据存储目录

此目录用于存储PaperGather任务的持久化数据。

## 目录结构

```
data/paper_gather/
├── task_history/           # 任务历史记录
│   ├── 2024_01_tasks.json  # 按月分文件存储
│   └── 2024_02_tasks.json
├── config_presets/         # 配置预设
│   ├── user_presets.json   # 用户保存的配置预设
│   └── default_templates.json
├── scheduled_tasks.json    # 定时任务状态
├── config_schema_version.json  # 配置版本追踪
└── .gitignore             # Git忽略文件
```

## 数据格式

### 任务历史记录
每个任务包含完整的配置信息和执行结果，支持配置版本兼容性。

### 配置预设
用户可以保存常用的任务配置，方便快速重用。

### 定时任务
保存当前运行的定时任务状态，重启后可以恢复。

## 注意事项

- 数据文件自动按月分割，避免单文件过大
- 支持配置版本兼容性，老版本配置自动升级
- 所有数据文件被git忽略，保护用户隐私