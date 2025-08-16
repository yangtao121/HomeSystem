# HomeSystem

基于 Docker 的模块化智能家庭自动化系统，集成本地和云端大模型，提供文档管理、论文收集和工作流自动化功能。

## ✨ 核心功能

- 🐳 **模块化部署**: 三大独立模块，支持分布式跨机器部署
- 📚 **智能论文分析**: 基于ArXiv的自动论文收集、分析和管理
- 🔍 **高级OCR处理**: 远程GPU加速的PaddleOCR文档识别服务
- 🗄️ **企业级数据库**: PostgreSQL + Redis 双数据库架构
- 🌐 **多LLM支持**: DeepSeek V3、Qwen、Doubao等多种大模型
- 📊 **可视化分析**: 论文数据的智能统计和趋势分析
- 🔄 **工作流自动化**: 定时任务调度和批处理功能

## 🏗️ 系统架构

HomeSystem 采用模块化设计，由三个独立的 Docker 服务组成，可在不同机器上部署：

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│     数据库服务        │    │    远程OCR服务       │    │   PaperAnalysis    │
│  (Database Module)  │    │ (Remote OCR Module) │    │   (Web Module)     │
├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤
│ • PostgreSQL:15432  │    │ • OCR Service:5001  │    │ • Web App:5002     │
│ • Redis:16379       │◄───┼─• GPU加速处理        │◄───┼─• 论文管理界面      │
│ • pgAdmin:8080      │    │ • PaddleOCR引擎     │    │ • API接口          │
│ • Redis Web:8081    │    │ • 批量文档处理       │    │ • 任务调度          │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                   │
                            网络连接支持
                          跨主机LAN部署
```

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 各模块可部署在不同主机上（支持LAN网络连接）

### 1. 数据库服务部署

**在数据库主机上：**

```bash
cd /path/to/homesystem/database

# 启动数据库服务
./start.sh

# 检查服务状态
docker compose ps
./check-tables.sh
```

**服务端点：**
- PostgreSQL: `localhost:15432`
- Redis: `localhost:16379`
- pgAdmin: `http://localhost:8080` (admin@homesystem.local / admin123)
- Redis Commander: `http://localhost:8081`

### 2. 远程OCR服务部署

**在GPU主机上：**

```bash
cd /path/to/homesystem/remote_app

# 构建并启动OCR服务
./deploy.sh --build

# 检查GPU支持
docker compose logs ocr-service
```

**服务端点：**
- OCR API: `http://gpu-host:5001`
- 健康检查: `http://gpu-host:5001/api/health`

### 3. PaperAnalysis Web服务部署

**在Web主机上：**

```bash
cd /path/to/homesystem/Web/PaperAnalysis

# 配置环境变量（连接远程服务）
cp .env.example .env
vim .env  # 配置数据库和OCR服务地址

# 部署Web服务
./deploy.sh --build

# 检查服务状态
docker compose ps
```

**服务端点：**
- Web界面: `http://web-host:5002`
- API接口: `http://web-host:5002/api/`

## 📦 模块详细部署

### 数据库模块 (Database Module)

```bash
# 进入数据库目录
cd database/

# 启动服务
./start.sh

# 管理命令
./stop.sh           # 停止服务
./backup.sh         # 备份数据库
./restore.sh        # 恢复数据库
./check-tables.sh   # 检查表结构

# Web管理界面（可选）
docker compose --profile tools up -d
```

### 远程OCR模块 (Remote OCR Module)

```bash
# 进入远程应用目录
cd remote_app/

# 部署服务
./deploy.sh --build

# 管理命令
./deploy.sh --status    # 检查状态
./deploy.sh --logs      # 查看日志
./deploy.sh --down      # 停止服务

# 配置选项
export OCR_SERVICE_PORT=5001
export PADDLEOCR_USE_GPU=true
```

### PaperAnalysis模块 (Web Module)

```bash
# 进入Web应用目录
cd Web/PaperAnalysis/

# 配置环境变量
cat > .env << EOF
# 数据库配置（远程）
DB_HOST=192.168.1.100
DB_PORT=15432
REDIS_HOST=192.168.1.100
REDIS_PORT=16379

# OCR服务配置（远程）
REMOTE_OCR_ENDPOINT=http://192.168.1.101:5001

# LLM API配置
DEEPSEEK_API_KEY=your_api_key
SILICONFLOW_API_KEY=your_api_key
EOF

# 部署服务
./deploy.sh --build

# 管理命令
./deploy.sh --status    # 检查状态
./deploy.sh --logs      # 查看日志
```

## 🔧 配置指南

### 网络连接配置

**跨主机部署配置示例：**

```bash
# 在PaperAnalysis模块的.env文件中配置远程服务
DB_HOST=192.168.5.118        # 数据库主机IP
DB_PORT=15432
REDIS_HOST=192.168.5.118     # Redis主机IP
REDIS_PORT=16379
REMOTE_OCR_ENDPOINT=http://192.168.5.118:5001  # OCR服务地址
```

### LLM模型配置

支持多种大语言模型提供商：

```bash
# DeepSeek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 硅基流动
SILICONFLOW_API_KEY=sk-xxx
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1

# 阿里云DashScope
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 本地Ollama（必须）
OLLAMA_BASE_URL=http://192.168.5.217:11434
```

### 权限配置

确保Docker容器有正确的文件权限：

```bash
# 在各模块目录下运行权限设置脚本
./setup-permissions.sh --fix
```

## 🔌 可选集成服务

### SiYuan 笔记系统

```bash
# 配置SiYuan API连接
SIYUAN_API_URL=http://192.168.5.54:6806
SIYUAN_API_TOKEN=your_token
```

### Dify 知识库

```bash
# 配置Dify服务
DIFY_BASE_URL=http://192.168.5.54:5001
DIFY_KB_API_KEY=your_api_key
```

## 🐳 Docker 管理命令

### 查看所有服务状态

```bash
# 数据库服务
cd database && docker compose ps

# OCR服务
cd remote_app && docker compose ps

# Web服务
cd Web/PaperAnalysis && docker compose ps
```

### 日志管理

```bash
# 查看实时日志
docker compose logs -f [service_name]

# 查看错误日志
docker compose logs --tail=100 [service_name]
```

### 资源监控

```bash
# 容器资源使用情况
docker stats

# 磁盘使用情况
docker system df
```

## 📚 详细文档

- **数据库部署**: `database/README.md` - 完整的数据库部署指南
- **OCR服务**: `remote_app/README.md` - OCR服务配置和使用
- **Web应用**: `Web/PaperAnalysis/README.md` - PaperAnalysis详细功能
- **开发指南**: `docs/` - 各组件开发文档

## 🧪 功能测试

### 数据库连接测试

```bash
# 测试PostgreSQL连接
docker exec homesystem-postgres psql -U homesystem -d homesystem -c "\l"

# 测试Redis连接
docker exec homesystem-redis redis-cli ping
```

### OCR服务测试

```bash
# 健康检查
curl http://your-ocr-host:5001/api/health

# OCR功能测试
curl -X POST http://your-ocr-host:5001/api/ocr \
  -F "file=@test.pdf" \
  -F "options={\"use_gpu\": true}"
```

### Web应用测试

```bash
# 访问Web界面
http://your-web-host:5002

# API测试
curl http://your-web-host:5002/api/health
curl http://your-web-host:5002/api/about/llm_models
```

## 💡 故障排除

### 常见问题

**1. 容器无法启动**
```bash
# 检查端口占用
netstat -tlnp | grep :15432

# 检查Docker守护进程
systemctl status docker
```

**2. 跨主机连接失败**
```bash
# 测试网络连通性
telnet 192.168.1.100 15432

# 检查防火墙设置
sudo ufw status
```

**3. 权限问题**
```bash
# 修复目录权限
./setup-permissions.sh --fix

# 检查Docker用户组
groups $USER | grep docker
```

**4. 资源不足**
```bash
# 检查系统资源
free -h
df -h
docker system prune  # 清理未使用的容器和镜像
```

### 服务健康检查

```bash
# 数据库健康检查
cd database && ./check-tables.sh

# OCR服务健康检查
curl http://ocr-host:5001/api/health

# Web服务健康检查
curl http://web-host:5002/api/health
```

## 📈 性能优化

### 资源配置建议

**数据库主机：**
- 内存: 8GB+
- 存储: SSD 100GB+
- CPU: 4核+

**OCR主机：**
- GPU: NVIDIA显卡 (建议)
- 内存: 8GB+
- 存储: 50GB+

**Web主机：**
- 内存: 4GB+
- 存储: 20GB+
- CPU: 2核+

## 🔒 安全建议

- 修改默认密码
- 配置防火墙规则
- 使用强API密钥
- 定期备份数据
- 监控访问日志

## 📄 许可证

MIT License - 详见 LICENSE 文件