# PaperAnalysis

**论文收集与分析系统** - 整合版本

PaperAnalysis 是 HomeSystem 智能家庭自动化系统的一部分，集成了原来的 PaperGather（论文收集）和 ExplorePaperData（论文浏览分析）两个应用的所有功能，提供一站式的学术论文管理解决方案。

## 🌟 主要特性

### 📥 论文收集 (来自PaperGather)
- **智能论文收集**: 基于ArXiv API的自动化论文获取
- **多种搜索模式**: 最新论文、相关性搜索、日期范围搜索
- **定时任务支持**: 自动化的定期论文收集
- **LLM模型配置**: 支持多种大语言模型进行论文分析
- **实时任务监控**: Web界面实时显示任务执行状态
- **去重处理**: 自动检测和处理重复论文

### 🔍 论文浏览 (来自ExplorePaperData)
- **高级搜索**: 全文搜索、分类过滤、任务分组
- **数据可视化**: Chart.js驱动的统计图表和趋势分析
- **论文详情**: 完整的论文信息展示和导航
- **批量操作**: 支持批量任务分配、删除等操作
- **任务管理**: 论文任务分配和迁移功能
- **研究洞察**: 关键词分析、方法趋势、影响力论文发现

### 🧠 深度分析 (增强功能)
- **AI驱动分析**: 使用视觉模型和语言模型进行深度论文理解
- **公式纠错**: 智能识别和纠正论文中的数学公式错误
- **内容提取**: 自动提取论文的关键信息和结构
- **多模态理解**: 结合文本和图像进行全面分析
- **分析配置**: 灵活的模型选择和参数配置

### 🔗 外部集成
- **Dify知识库**: 支持将论文上传到Dify知识库
- **数据导出**: 多种格式的数据导出功能
- **API接口**: RESTful API支持第三方集成

## 🏗️ 技术架构

### 后端技术栈
- **Web框架**: Flask 3.0+
- **数据库**: PostgreSQL (持久化) + Redis (缓存)
- **AI引擎**: 多LLM模型支持 (DeepSeek, Qwen, Doubao等)
- **异步处理**: ThreadPoolExecutor + 定时任务调度
- **数据处理**: pandas + numpy

### 前端技术栈
- **UI框架**: Bootstrap 5.3
- **图表库**: Chart.js
- **图标**: Bootstrap Icons + Font Awesome
- **交互**: 原生JavaScript + AJAX

### 系统集成
- **HomeSystem**: 核心模块和工具库
- **Docker**: 容器化部署支持
- **ArXiv API**: 论文数据源
- **多模态AI**: 视觉理解和文本分析

## 📁 项目结构

```
PaperAnalysis/
├── app.py                 # Flask应用主文件
├── config.py             # 统一配置文件
├── requirements.txt      # Python依赖
├── start.sh              # 启动脚本
├── README.md            # 项目文档
│
├── routes/              # 路由模块
│   ├── main.py          # 主页和基础路由
│   ├── collect.py       # 论文收集功能
│   ├── explore.py       # 论文浏览功能
│   ├── analysis.py      # 深度分析功能
│   └── api.py           # API接口
│
├── services/            # 服务层
│   ├── task_service.py      # 任务管理服务
│   ├── paper_gather_service.py  # 论文收集服务
│   ├── paper_explore_service.py # 论文浏览服务
│   └── analysis_service.py     # 深度分析服务
│
├── templates/           # 模板文件
│   ├── base.html        # 基础模板
│   ├── index.html       # 综合仪表板
│   ├── collect/         # 收集功能模板
│   ├── explore/         # 浏览功能模板
│   ├── analysis/        # 分析功能模板
│   └── shared/          # 共享组件
│
├── static/              # 静态资源
│   ├── css/
│   │   └── style.css    # 统一样式文件
│   └── js/
│       ├── main.js      # 主要JavaScript功能
│       └── paper-analysis.js # 扩展功能脚本
│
└── utils/               # 工具模块
    └── markdown_utils.py # Markdown处理工具
```

## 🚀 快速开始

### 环境要求
- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- HomeSystem 核心模块

### 安装步骤

1. **克隆项目**
   ```bash
   cd HomeSystem/Web/PaperAnalysis
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置环境变量**
   ```bash
   # 创建 .env 文件或使用根目录的 .env
   cp .env.example .env
   # 编辑配置
   vim .env
   ```

4. **启动数据库服务**
   ```bash
   cd ../../..  # 返回HomeSystem根目录
   docker compose up -d
   ```

5. **启动应用**
   ```bash
   ./start.sh
   ```

6. **访问应用**
   - 打开浏览器访问: http://localhost:5002
   - 默认用户界面提供完整的功能访问

### 配置说明

主要配置项（.env文件）：

```env
# Flask应用配置
FLASK_HOST=0.0.0.0
FLASK_PORT=5002
FLASK_DEBUG=True
SECRET_KEY=your-secret-key

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

# Dify集成配置（可选）
DIFY_BASE_URL=http://localhost:80/v1
DIFY_KB_API_KEY=your-dify-api-key
DIFY_ENABLED=false
```

## 📋 功能使用指南

### 论文收集功能
1. **配置收集任务**: 访问 `/collect/config` 配置搜索参数和模型
2. **执行模式选择**: 支持即时执行和定时执行两种模式
3. **监控任务状态**: 实时查看任务执行进度和结果
4. **查看历史记录**: 浏览所有任务的执行历史

### 论文浏览功能
1. **搜索论文**: 使用高级搜索功能查找特定论文
2. **查看详情**: 点击论文标题查看完整信息
3. **批量操作**: 选择多篇论文进行批量任务分配
4. **数据分析**: 查看统计图表和研究洞察

### 深度分析功能
1. **配置分析模型**: 在分析配置页面选择AI模型
2. **启动分析**: 在论文详情页面点击"深度分析"
3. **查看结果**: 分析完成后查看详细报告
4. **下载报告**: 支持Markdown+图片的打包下载

### API使用
- 收集API: `/api/collect/...`
- 浏览API: `/api/explore/...`  
- 分析API: `/api/analysis/...`

详细API文档请参考各路由文件中的接口定义。

## 🔧 开发指南

### 添加新功能
1. 在相应的routes文件中添加路由
2. 在services中实现业务逻辑
3. 创建对应的模板文件
4. 更新静态资源（如需要）

### 自定义配置
- 修改 `config.py` 添加新的配置项
- 在 `.env` 文件中设置环境变量
- 重启应用使配置生效

### 调试技巧
- 启用DEBUG模式: `FLASK_DEBUG=True`
- 查看应用日志: `tail -f app.log`
- 监控数据库连接: 检查PostgreSQL和Redis状态

## 📊 系统监控

### 健康检查
- 应用状态: `/api/explore/stats`
- 数据库连接: 启动日志中会显示连接状态
- 任务状态: Web界面实时显示

### 性能监控  
- 内存使用: 监控Flask进程内存占用
- 数据库性能: 查看PostgreSQL慢查询日志
- Redis缓存: 监控缓存命中率

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开Pull Request

## 📄 许可证

本项目是HomeSystem系统的一部分，遵循相同的许可协议。

## 🆘 故障排除

### 常见问题

**应用无法启动**
- 检查Python依赖是否完整安装
- 确认数据库服务正在运行
- 验证环境变量配置正确

**数据库连接失败**
- 检查PostgreSQL服务状态
- 确认连接参数正确
- 查看防火墙设置

**Redis连接问题**
- 确认Redis服务运行正常
- 检查端口是否被占用
- 验证Redis配置

**模型加载失败**
- 检查HomeSystem核心模块路径
- 确认模型配置文件存在
- 验证网络连接（对于在线模型）

### 联系支持
如遇到问题，请查看HomeSystem项目的issue或创建新的issue。

---

**PaperAnalysis** - 让学术论文管理变得简单高效! 🎓✨