# HomeSystem 云端镜像部署指南

> 🌟 **推荐部署方式**：使用预构建的Docker镜像，无需克隆代码，快速启动

## 📋 前置要求

### 系统要求
- Docker 20.10+ 和 Docker Compose 2.0+
- 4GB+ 内存（一体化部署）或分布式环境

### 必须配置Ollama本地模型服务
- **在一台机器上配置好ollama，实现局域网内的访问**
- **ollama要拉取以下模型**：
  ```bash
  ollama pull qwen3:30b 
  ollama pull qwen2.5vl:7b
  ```
  VL模型为必须，如果配置不够可以拉取qwen2.5vl:3b，包括qwen3:4b

> ⚠️ **重要**：无论选择哪种部署方式，Ollama都是必需的，系统依赖本地模型进行视觉分析

## 📋 部署方式概览

| 部署方式 | 适用场景 | 配置复杂度 | 资源要求 |
|---------|---------|-----------|----------|
| **一体化部署** | 快速体验、小规模使用、开发测试 | ⭐ 简单 | 单机 4GB+ 内存 |
| **分离部署** | 生产环境、大规模使用、资源优化 | ⭐⭐ 中等 | 多机分布式 |

## 🚀 一体化部署（推荐新用户）

### 快速开始

```bash
# 1. 创建项目目录
mkdir homesystem && cd homesystem

# 2. 下载配置文件
curl -o docker-compose.yml https://raw.githubusercontent.com/yangtao121/homesystem/main/deploy/docker-compose.yml

# 3. 修改配置（重要！）
vim docker-compose.yml
# 必须修改：
# - POSTGRES_PASSWORD: 设置安全的数据库密码
# - DEEPSEEK_API_KEY: 填写您的 DeepSeek API 密钥
# - OLLAMA_BASE_URL: 修改为您的Ollama服务地址

# 4. 启动服务
docker compose up -d

# 5. 检查服务状态
docker compose ps
```

### 服务访问地址

- **Web应用**: http://localhost:5002
- **数据库**: localhost:15432 (用户: homesystem)
- **Redis**: localhost:16379
- **OCR服务**: http://localhost:5001

### 管理界面（可选）

```bash
# 启动数据库和Redis管理界面
docker compose --profile tools up -d

# 访问地址：
# - pgAdmin: http://localhost:8080 (admin@homesystem.local / admin123)
# - Redis Commander: http://localhost:8081
```

## 🏗️ 分离部署（高级用户）

适合多机器部署，优化资源利用和性能。

### 部署架构

```
机器A (数据库)          机器B (OCR)           机器C (Web)          机器D (Ollama)
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐   ┌─────────────────┐
│ PostgreSQL:15432│◄───┼─OCR Service:5001│◄───┼─PaperAnalysis   │◄──┼─Ollama:11434    │
│ Redis:16379     │    │ (GPU加速可选)    │    │ :5002           │   │ qwen3:30b       │
└─────────────────┘    └─────────────────┘    └─────────────────┘   │ qwen2.5vl:7b    │
   192.168.1.100        192.168.1.101         192.168.1.102       └─────────────────┘
                                                                     192.168.1.104
```

### 1. 部署数据库服务 (机器A)

```bash
# 下载数据库配置
curl -o docker-compose.database.yml https://raw.githubusercontent.com/yangtao121/homesystem/main/deploy/docker-compose.database.yml

# 修改密码配置
vim docker-compose.database.yml
# 修改 POSTGRES_PASSWORD 为安全密码

# 启动数据库服务
docker compose -f docker-compose.database.yml up -d

# 验证服务
docker compose -f docker-compose.database.yml ps
```

### 2. 部署OCR服务 (机器B)

```bash
# 下载OCR配置
curl -o docker-compose.ocr.yml https://raw.githubusercontent.com/yangtao121/homesystem/main/deploy/docker-compose.ocr.yml

# GPU服务器配置（可选）
vim docker-compose.ocr.yml
# 取消注释：runtime: nvidia
# 取消注释：NVIDIA_VISIBLE_DEVICES: all  
# 修改：PADDLEOCR_USE_GPU: true

# 启动OCR服务
docker compose -f docker-compose.ocr.yml up -d

# 验证服务
curl http://localhost:5001/api/health
```

### 3. 部署Web服务 (机器C)

```bash
# 下载Web配置
curl -o docker-compose.web.yml https://raw.githubusercontent.com/yangtao121/homesystem/main/deploy/docker-compose.web.yml

# 修改连接配置
vim docker-compose.web.yml
# 必须修改：
# - DB_HOST: 192.168.1.100 (数据库服务器IP)
# - REDIS_HOST: 192.168.1.100 (Redis服务器IP)
# - REMOTE_OCR_ENDPOINT: http://192.168.1.101:5001 (OCR服务器地址)
# - DEEPSEEK_API_KEY: sk-xxx (您的API密钥)
# - OLLAMA_BASE_URL: http://192.168.1.104:11434 (Ollama服务器地址)

# 启动Web服务
docker compose -f docker-compose.web.yml up -d

# 验证服务
curl http://localhost:5002/api/health
```

## ⚙️ 配置说明

### LLM API 配置

系统支持多种LLM提供商，至少需要配置一个：

```yaml
# DeepSeek (推荐)
DEEPSEEK_API_KEY: sk-xxx
DEEPSEEK_BASE_URL: https://api.deepseek.com

# 硅基流动
SILICONFLOW_API_KEY: sk-xxx
SILICONFLOW_BASE_URL: https://api.siliconflow.cn/v1

# 火山引擎/豆包
VOLCANO_API_KEY: xxx
VOLCANO_BASE_URL: https://ark.cn-beijing.volces.com/api/v3

# 月之暗面/Kimi
MOONSHOT_API_KEY: sk-xxx
MOONSHOT_BASE_URL: https://api.moonshot.cn/v1
```

### 可选服务配置

```yaml
# Ollama 本地模型
OLLAMA_BASE_URL: http://192.168.1.104:11434

# Dify 知识库
DIFY_BASE_URL: http://192.168.1.105/v1
DIFY_KB_API_KEY: xxx

# SiYuan 笔记
SIYUAN_API_URL: http://192.168.1.106:6806
SIYUAN_API_TOKEN: xxx
```

## 🔧 常用操作

### 查看服务状态

```bash
# 一体化部署
docker compose ps
docker compose logs paper-analysis

# 分离部署
docker compose -f docker-compose.database.yml ps
docker compose -f docker-compose.ocr.yml ps  
docker compose -f docker-compose.web.yml ps
```

### 更新服务

```bash
# 拉取最新镜像
docker compose pull

# 重启服务
docker compose up -d
```

### 备份数据

```bash
# 备份数据库
docker compose exec postgres pg_dump -U homesystem homesystem > backup.sql

# 备份数据卷
docker run --rm -v homesystem-postgres-data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres-backup.tar.gz -C /data .
```

### 清理环境

```bash
# 停止服务
docker compose down

# 清理数据（⚠️ 谨慎操作）
docker compose down -v
```

## 🐛 故障排查

### 常见问题

1. **服务无法启动**
   ```bash
   # 查看详细日志
   docker compose logs -f 服务名
   
   # 检查端口占用
   netstat -tlnp | grep :5002
   ```

2. **无法连接数据库**
   ```bash
   # 测试数据库连接
   docker compose exec postgres psql -U homesystem -d homesystem -c "SELECT 1;"
   
   # 检查网络连通性
   ping 数据库服务器IP
   telnet 数据库服务器IP 15432
   ```

3. **OCR服务异常**
   ```bash
   # 测试OCR服务
   curl http://OCR服务器IP:5001/api/health
   
   # 查看OCR日志
   docker compose logs ocr-service
   ```

4. **LLM API 调用失败**
   - 检查API密钥是否正确
   - 确认网络能访问API地址
   - 查看应用日志中的错误信息

### 性能优化

- **数据库**: 根据数据量调整 PostgreSQL 配置
- **OCR**: GPU服务器启用GPU加速，提升处理速度
- **Web**: 根据并发量调整资源限制
- **网络**: 确保服务器间网络延迟低

## 📚 更多文档

- [项目主页](https://github.com/yangtao121/homesystem)
- [功能介绍](../README.md)
- [开发文档](../docs/)
- [常见问题](../FAQ.md)

## 🆘 获取帮助

- QQ交流群：963812265
- GitHub Issues：[提交问题](https://github.com/yangtao121/homesystem/issues)
- 知乎专栏：[HomeSystem智能体](https://www.zhihu.com/column/c_1935713729351221271)