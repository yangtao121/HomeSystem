# HomeSystem 项目结构

## 目录结构

```
HomeSystem/
├── graph/                  # LangGraph相关
│   ├── __init__.py
│   ├── base_graph.py      # 基础图定义
│   ├── nodes/             # 图节点定义
│   ├── edges/             # 边逻辑
│   └── tool/              # graph工具
│       ├── __init__.py
│       ├── obtain_web_content.py
│       └── search.py
├── workflow/              # 任务流制作
│   ├── __init__.py
│   ├── templates/         # 工作流模板
│   └── handlers/          # 处理器
├── integrations/          # 第三方服务集成
│   ├── __init__.py
│   ├── dify/              # Dify集成
│   │   ├── __init__.py
│   │   ├── client.py      # Dify客户端
│   │   ├── workflows.py   # Dify工作流
│   │   └── tools/         # Dify工具封装
│   ├── paperless_ngx/     # Paperless NGX集成
│   │   ├── __init__.py
│   │   ├── client.py      # API客户端
│   │   ├── documents.py   # 文档管理
│   │   └── tools/         # 相关工具
│   └── [其他服务]/        # 可扩展其他服务
├── utility/               # 工具模块
│   ├── __init__.py
│   ├── document/          # 文档处理功能
│   │   ├── __init__.py
│   │   ├── downloader.py  # 文档下载
│   │   ├── parser.py      # 文档解析
│   │   └── processor.py   # 文档处理
│   └── [其他工具]/        # 可扩展其他工具
├── config.py              # 配置管理
└── __init__.py
```

## 模块说明

### graph/
- 负责LangGraph的创建和管理
- 包含图节点、边逻辑和相关工具

### workflow/
- 任务流制作和管理
- 提供工作流模板和处理器

### integrations/
- 第三方服务集成模块
- 每个服务有独立文件夹，包含客户端和工具封装
- 如 Dify、Paperless NGX 等

### utility/
- 通用工具模块
- 包含下载、解析、处理等常用功能

## 设计原则

1. **模块化设计**: 每个功能模块独立，便于维护
2. **清晰分层**: 功能边界明确，职责单一
3. **易于扩展**: 支持新功能模块的添加
4. **配置统一**: 集中管理配置信息