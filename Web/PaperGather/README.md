# PaperGather Web界面

PaperGather是HomeSystem集成的论文收集系统的Web界面，提供直观的任务配置、执行监控和结果展示功能。

## 功能特性

### 🚀 双模式执行
- **即时执行模式**: 立即执行任务并返回结果，适合一次性的论文搜索需求
- **定时执行模式**: 后台定时执行任务，适合持续监控最新论文

### 📊 智能配置
- 可视化配置界面，支持所有PaperGatherTaskConfig参数
- 实时参数验证和智能建议
- 动态LLM模型选择（自动从LLMFactory获取）

### 📈 实时监控
- 任务执行状态实时更新
- 进度条显示和统计数据
- 错误信息和日志查看

### 📑 结果展示
- 结构化论文分析结果展示
- 支持筛选、搜索和排序
- 论文详情页面，包含完整分析字段：
  - 论文标题、关键词
  - 研究背景、研究目标
  - 研究方法、主要发现
  - 结论、局限性、未来工作

## 系统架构

```
Web/PaperGather/
├── app.py                 # Flask主应用
├── config.py             # 配置文件
├── routes/               # 路由模块
│   ├── main.py          # 主页和配置路由
│   ├── task.py          # 任务执行路由
│   └── api.py           # API接口路由
├── services/            # 服务层
│   ├── task_service.py  # 任务执行服务（线程安全）
│   └── paper_service.py # 论文数据服务
├── templates/           # Jinja2模板
├── static/             # 静态资源
├── requirements.txt    # Python依赖
├── start.sh           # 启动脚本
└── README.md         # 本文档
```

## 安装和启动

### 环境要求
- Python 3.8+
- PostgreSQL数据库
- Redis缓存
- HomeSystem核心模块

### 快速启动

1. **使用启动脚本**（推荐）
```bash
cd Web/PaperGather
./start.sh
```

启动脚本会自动：
- 检查Python环境和依赖
- 验证数据库连接
- 创建默认配置文件
- 启动Web应用

2. **手动启动**
```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export FLASK_APP=app.py
export FLASK_ENV=development

# 启动应用
python app.py
```

### 配置文件

应用会自动创建`.env`文件，可根据需要修改：

```env
# 数据库配置
DB_HOST=localhost
DB_PORT=15432
DB_NAME=homesystem
DB_USER=homesystem
DB_PASSWORD=homesystem123

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=16379
REDIS_DB=0

# Flask配置
FLASK_HOST=0.0.0.0
FLASK_PORT=5001
FLASK_DEBUG=True
SECRET_KEY=papergather-dev-key-change-in-production
```

## 使用指南

### 1. 任务配置
- 访问 `/config` 页面
- 选择执行模式（即时/定时）
- 配置搜索参数、LLM模型、处理选项
- 点击"执行任务"

### 2. 监控任务
- 即时任务：自动跳转到状态页面
- 查看实时进度和统计数据
- 任务完成后查看详细结果

### 3. 查看结果
- 结果页面展示所有找到的论文
- 使用筛选器按相关性、分析状态等筛选
- 点击论文标题查看详情

### 4. 管理任务
- 执行历史：查看所有任务记录  
- 定时任务：管理后台运行的定时任务
- 任务控制：取消、停止正在运行的任务

## API接口

### 核心接口

- `GET /api/models` - 获取可用LLM模型
- `POST /task/execute` - 执行任务
- `GET /api/task/status/<task_id>` - 获取任务状态
- `GET /api/papers/search` - 搜索论文
- `GET /api/papers/<arxiv_id>` - 获取论文详情

### 任务执行示例

```javascript
// 即时执行任务
fetch('/task/execute', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        mode: 'immediate',
        config: {
            search_query: 'machine learning',
            llm_model_name: 'ollama.Qwen3_30B',
            max_papers_per_search: 20,
            // ... 其他配置
        }
    })
});
```

## 技术特点

### 🔧 线程安全设计
- 使用ThreadPoolExecutor执行任务，避免阻塞Web界面
- 线程锁保护共享数据结构
- 异步任务执行和状态管理

### 🎯 实时更新
- 基于AJAX的状态轮询
- 自动刷新任务进度和统计数据
- WebSocket支持（计划中）

### 📱 响应式设计
- Bootstrap 5.1.3 响应式布局
- 移动设备友好界面
- 现代化UI组件

### 🔌 模块化架构
- 分层架构：路由层、服务层、数据层
- 可扩展的插件式设计
- 清晰的关注点分离

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查PostgreSQL服务状态
   - 验证数据库配置和网络连接
   - 确保数据库已创建相关表

2. **任务执行失败**
   - 检查HomeSystem模块导入
   - 验证LLM模型可用性
   - 查看应用日志获取详细错误信息

3. **端口占用**
   - 使用`lsof -i :5001`查看端口占用
   - 修改配置文件中的端口设置
   - 或使用启动脚本自动处理

### 调试模式

启用调试模式获取详细日志：
```bash
export FLASK_DEBUG=True
python app.py
```

## 开发和扩展

### 添加新功能
1. 在`routes/`目录下创建新的路由模块
2. 在`services/`目录下添加业务逻辑
3. 创建对应的HTML模板
4. 更新导航和路由注册

### 自定义样式
- 修改`static/css/style.css`
- 使用CSS变量自定义主题色彩
- 添加响应式断点

### API扩展
- 在`routes/api.py`中添加新接口
- 遵循RESTful API设计原则
- 添加适当的错误处理和验证

## 许可证

本项目是HomeSystem的一部分，遵循相同的许可证条款。

## 贡献

欢迎提交Issue和Pull Request来改进PaperGather Web界面。

---

**注意**: 确保在生产环境中更改默认的SECRET_KEY和数据库密码。