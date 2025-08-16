# HomeSystem 常见问题解决 (FAQ)

本文档汇总了 HomeSystem 部署和使用过程中的常见问题及解决方案。

## 🔧 部署问题

### 1. 端口冲突问题

**问题描述：** 启动服务时提示端口被占用

**检查端口占用：**
```bash
# 检查特定端口
lsof -i :15432
netstat -tlnp | grep :15432
ss -tulpn | grep :15432

# 批量检查所有默认端口
for port in 15432 16379 8080 8081 5001 5002; do
  echo "=== 检查端口 $port ==="
  lsof -i :$port 2>/dev/null || echo "端口 $port 可用"
done

# 使用项目提供的端口检查工具
./check-ports.sh
```

**解决方案：**

**方案1：修改端口配置（推荐）**
```bash
# 数据库模块
cd database/
cat > .env << EOF
DB_PORT=25432
REDIS_PORT=26379
PGADMIN_PORT=8880
REDIS_COMMANDER_PORT=8881
EOF

# OCR模块
cd remote_app/
cat > .env << EOF
OCR_SERVICE_PORT=8080
NGINX_PORT=8000
EOF

# Web模块
cd Web/PaperAnalysis/
cat > .env << EOF
FLASK_PORT=8002
EOF
```

**方案2：停止占用端口的服务（谨慎使用）**
```bash
# 查找占用进程
lsof -i :15432
# 终止进程（请确认进程用途）
sudo kill -9 <PID>
```

### 2. 跨主机连接失败

**问题描述：** 不同主机之间的服务无法连接

**网络连通性测试：**
```bash
# 测试主机间连通性
ping 192.168.1.100
telnet 192.168.1.100 15432
nc -zv 192.168.1.100 15432

# 测试服务端口可达性
curl -f http://192.168.1.101:5001/api/health
curl -f http://192.168.1.102:5002/api/health
```

**解决方案：**

**检查防火墙设置：**
```bash
# Ubuntu/Debian
sudo ufw status
sudo ufw allow 15432/tcp  # PostgreSQL
sudo ufw allow 16379/tcp  # Redis
sudo ufw allow 5001/tcp   # OCR Service
sudo ufw allow 5002/tcp   # Web App

# CentOS/RHEL
sudo firewall-cmd --list-all
sudo firewall-cmd --permanent --add-port=15432/tcp
sudo firewall-cmd --permanent --add-port=16379/tcp
sudo firewall-cmd --permanent --add-port=5001/tcp
sudo firewall-cmd --permanent --add-port=5002/tcp
sudo firewall-cmd --reload
```

**检查服务监听状态：**
```bash
# 在服务器上检查服务是否正确监听
ss -tulpn | grep -E ":(15432|16379|5001|5002)"

# 检查 Docker 容器端口映射
docker compose ps
docker port <container_name>
```

**配置远程访问：**
```bash
# 修改全局配置文件
cd /path/to/homesystem
cat > .env << EOF
# 使用实际的主机IP地址
DB_HOST=192.168.1.100
DB_PORT=15432
REDIS_HOST=192.168.1.100
REDIS_PORT=16379
REMOTE_OCR_ENDPOINT=http://192.168.1.101:5001
EOF
```

### 3. 全局配置文件缺失

**问题描述：** PaperAnalysis 部署失败，提示缺少环境变量

**错误信息：**
```
ERROR: Missing required environment variables: DB_HOST, DEEPSEEK_API_KEY
```

**解决方案：**
```bash
# 确保根目录 .env 文件存在
cd /path/to/homesystem
ls -la .env

# 如果文件不存在，从模板创建
cp .env.example .env

# 配置必需的环境变量
cat > .env << EOF
# 数据库配置
DB_HOST=localhost
DB_PORT=15432
DB_NAME=homesystem
DB_USER=homesystem
DB_PASSWORD=your_secure_password_here

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=16379

# LLM API配置（至少配置一个）
DEEPSEEK_API_KEY=sk-your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 硅基流动 API
SILICONFLOW_API_KEY=sk-your_siliconflow_api_key_here
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1

# OCR服务配置
REMOTE_OCR_ENDPOINT=http://localhost:5001
EOF

# 验证配置是否正确加载
source .env && echo "DB_HOST: $DB_HOST"
```

## 🐳 Docker 问题

### 4. 容器无法启动

**问题诊断：**
```bash
# 检查Docker守护进程状态
systemctl status docker
sudo systemctl start docker

# 检查容器启动日志
docker compose logs postgres
docker compose logs redis
docker compose logs ocr-service
docker compose logs paper-analysis

# 检查docker-compose文件语法
docker compose config

# 查看容器退出代码
docker compose ps -a
```

**解决方案：**
```bash
# 强制重新创建容器
docker compose down
docker compose up -d --force-recreate

# 清理Docker资源（谨慎使用）
docker system prune -f
docker volume prune -f

# 重新构建镜像
docker compose build --no-cache
```

### 5. 权限问题

**问题描述：** 容器启动时提示权限错误

**错误信息：**
```
ls: can't open '/docker-entrypoint-initdb.d/': Permission denied
```

**解决方案：**
```bash
# 修复目录权限
sudo chmod -R 755 database/init/
sudo chmod -R 755 remote_app/volumes/

# 添加用户到docker组
sudo usermod -aG docker $USER
# 重新登录或执行
newgrp docker

# 检查数据目录权限
ls -la database/postgres/data/
ls -la remote_app/volumes/

# 如果问题持续，可尝试（谨慎使用）
sudo chmod -R 777 database/postgres/data/
```

### 6. 网络问题

**问题描述：** 容器间无法通信

**解决方案：**
```bash
# 检查Docker网络
docker network ls
docker network inspect homesystem-network

# 重建Docker网络
docker compose down
docker network prune
docker compose up -d

# 检查容器内部网络连通性
docker compose exec postgres ping redis
docker compose exec paper-analysis curl redis:6379
```

## 🔧 服务问题

### 7. 数据库连接失败

**诊断步骤：**
```bash
# 检查数据库容器状态
docker compose ps postgres
docker compose logs postgres

# 测试数据库连接
docker exec homesystem-postgres psql -U homesystem -d homesystem -c "SELECT 1;"

# 检查数据库配置
docker compose exec postgres env | grep POSTGRES
```

**解决方案：**
```bash
# 重置数据库密码
cd database/
cat > .env << EOF
DB_PASSWORD=new_secure_password
POSTGRES_PASSWORD=new_secure_password
EOF

# 重新创建数据库容器
docker compose down postgres
docker volume rm homesystem_postgres_data  # 注意：这会删除数据
docker compose up -d postgres

# 或恢复备份数据
./restore.sh backup_file.sql
```

### 8. OCR服务问题

**GPU支持问题：**
```bash
# 检查GPU驱动
nvidia-smi

# 检查Docker GPU支持
docker run --rm --gpus all nvidia/cuda:11.0-base-ubuntu20.04 nvidia-smi

# 检查OCR容器GPU访问
docker compose exec ocr-service nvidia-smi
```

**OCR服务无响应：**
```bash
# 检查OCR服务状态
curl http://localhost:5001/api/health
docker compose logs ocr-service

# 重启OCR服务
docker compose restart ocr-service

# 检查资源使用
docker stats ocr-service
```

### 9. Web应用访问问题

**服务无法访问：**
```bash
# 检查Web服务状态
curl http://localhost:5002/api/health
docker compose logs paper-analysis

# 检查端口映射
docker compose ps paper-analysis
docker port homesystem-paper-analysis

# 检查容器内部服务
docker compose exec paper-analysis curl localhost:5002/api/health
```

**API密钥问题：**
```bash
# 验证API密钥配置
docker compose exec paper-analysis env | grep API_KEY

# 测试API连接
docker compose exec paper-analysis python3 -c "
import os
from openai import OpenAI
client = OpenAI(api_key=os.getenv('DEEPSEEK_API_KEY'), base_url=os.getenv('DEEPSEEK_BASE_URL'))
try:
    response = client.chat.completions.create(
        model='deepseek-chat',
        messages=[{'role': 'user', 'content': 'Hello'}],
        max_tokens=10
    )
    print('API连接成功')
except Exception as e:
    print(f'API连接失败: {e}')
"
```

## 📊 性能问题

### 10. 资源不足

**检查系统资源：**
```bash
# 系统资源使用情况
free -h
df -h
htop

# Docker容器资源使用
docker stats
docker system df

# 检查特定服务资源
docker stats homesystem-postgres homesystem-redis homesystem-ocr
```

**解决方案：**
```bash
# 清理Docker资源
docker system prune -f
docker volume prune -f
docker image prune -f

# 限制容器资源使用
# 在docker-compose.yml中添加：
# deploy:
#   resources:
#     limits:
#       memory: 2G
#       cpus: '1.0'

# 优化数据库配置
# 编辑 database/postgres/postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
```

### 11. 数据库性能问题

**优化PostgreSQL：**
```bash
# 检查数据库连接数
docker exec homesystem-postgres psql -U homesystem -d homesystem -c "
SELECT count(*) as connections, state 
FROM pg_stat_activity 
GROUP BY state;
"

# 检查数据库大小
docker exec homesystem-postgres psql -U homesystem -d homesystem -c "
SELECT pg_size_pretty(pg_database_size('homesystem'));
"

# 分析慢查询
docker exec homesystem-postgres psql -U homesystem -d homesystem -c "
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
"
```

## 🧪 服务验证和测试

### 部署后验证

**基本连通性测试：**
```bash
# 数据库连接测试
docker exec homesystem-postgres psql -U homesystem -d homesystem -c "SELECT 1;"

# Redis连接测试
docker exec homesystem-redis redis-cli ping

# OCR服务测试
curl http://localhost:5001/api/health

# Web应用测试
curl http://localhost:5002/api/health
```

**功能测试：**
```bash
# OCR功能测试
curl -X POST http://localhost:5001/api/ocr \
  -F "file=@test.pdf" \
  -F "options={\"use_gpu\": true}"

# 访问Web界面
open http://localhost:5002
# 或在浏览器中打开: http://localhost:5002
```

**跨主机连接测试：**
```bash
# 测试远程数据库连接
docker exec homesystem-postgres psql -h 192.168.1.100 -p 15432 -U homesystem -d homesystem -c "SELECT 1;"

# 测试远程OCR服务
curl http://192.168.1.101:5001/api/health

# 测试远程Web服务
curl http://192.168.1.102:5002/api/health
```

**服务依赖关系验证：**
```bash
# 验证Web应用能访问数据库
docker compose exec paper-analysis python3 -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    print('✅ 数据库连接成功')
    conn.close()
except Exception as e:
    print(f'❌ 数据库连接失败: {e}')
"

# 验证Web应用能访问Redis
docker compose exec paper-analysis python3 -c "
import redis
import os
try:
    r = redis.Redis(
        host=os.getenv('REDIS_HOST'),
        port=int(os.getenv('REDIS_PORT')),
        db=0
    )
    r.ping()
    print('✅ Redis连接成功')
except Exception as e:
    print(f'❌ Redis连接失败: {e}')
"

# 验证Web应用能访问OCR服务
docker compose exec paper-analysis python3 -c "
import requests
import os
try:
    response = requests.get(f\"{os.getenv('REMOTE_OCR_ENDPOINT')}/api/health\")
    if response.status_code == 200:
        print('✅ OCR服务连接成功')
    else:
        print(f'❌ OCR服务返回状态码: {response.status_code}')
except Exception as e:
    print(f'❌ OCR服务连接失败: {e}')
"
```

## 🔍 日志分析

### 12. 查看和分析日志

**查看服务日志：**
```bash
# 实时日志
docker compose logs -f postgres
docker compose logs -f redis
docker compose logs -f ocr-service
docker compose logs -f paper-analysis

# 查看错误日志
docker compose logs --tail=100 postgres | grep ERROR
docker compose logs --tail=100 paper-analysis | grep -i error

# 保存日志到文件
docker compose logs postgres > postgres.log
docker compose logs paper-analysis > paper-analysis.log
```

**分析常见错误：**
```bash
# 连接错误
grep -i "connection.*failed\|connection.*refused" *.log

# 权限错误
grep -i "permission denied\|access denied" *.log

# 资源错误
grep -i "out of memory\|disk.*full\|no space" *.log

# API错误
grep -i "api.*error\|unauthorized\|forbidden" *.log
```

## 🛠️ 维护操作

### 13. 数据备份与恢复

**定期备份：**
```bash
cd database/

# 手动备份
./backup.sh

# 设置自动备份（crontab）
crontab -e
# 添加：每天凌晨2点备份
0 2 * * * /path/to/homesystem/database/backup.sh
```

**恢复数据：**
```bash
cd database/

# 从备份恢复
./restore.sh backup/homesystem_backup_20241216_020000.sql

# 检查恢复结果
./check-tables.sh
```

### 14. 系统更新

**更新镜像：**
```bash
# 拉取最新镜像
docker compose pull

# 重新构建并启动
docker compose up -d --build

# 清理旧镜像
docker image prune -f
```

**更新配置：**
```bash
# 备份现有配置
cp .env .env.backup

# 更新配置文件
# 编辑 .env 文件

# 重新启动服务
docker compose down
docker compose up -d
```

## 🆘 紧急处理

### 15. 服务完全无法访问

**紧急重启所有服务：**
```bash
# 停止所有服务
cd database && ./stop.sh
cd ../remote_app && ./deploy.sh --down
cd ../Web/PaperAnalysis && ./deploy.sh --down

# 清理Docker资源
docker system prune -f

# 重新启动所有服务
cd /path/to/homesystem
cd database && ./start.sh
cd ../remote_app && ./deploy.sh --build
cd ../Web/PaperAnalysis && ./deploy.sh --build
```

### 16. 数据损坏恢复

**检查数据完整性：**
```bash
# 检查数据库完整性
docker exec homesystem-postgres psql -U homesystem -d homesystem -c "
SELECT tablename, schemaname 
FROM pg_tables 
WHERE schemaname = 'public';
"

# 检查表数据
docker exec homesystem-postgres psql -U homesystem -d homesystem -c "
SELECT COUNT(*) FROM arxiv_papers;
SELECT COUNT(*) FROM paper_analysis_results;
"
```

**从备份恢复：**
```bash
cd database/

# 查看可用备份
ls -la backup/

# 停止服务
./stop.sh

# 删除损坏的数据
docker volume rm homesystem_postgres_data

# 重新启动数据库
./start.sh

# 恢复数据
./restore.sh backup/latest_backup.sql

# 验证恢复结果
./check-tables.sh
```

## 📞 获取帮助

如果以上解决方案都无法解决问题，请：

1. **收集信息：**
   ```bash
   # 收集系统信息
   docker --version
   docker compose version
   uname -a
   
   # 收集服务状态
   docker compose ps -a
   docker compose logs > all_services.log
   ```

2. **创建Issue时请包含：**
   - 操作系统版本
   - Docker和Docker Compose版本
   - 错误信息和完整日志
   - 部署配置（隐藏敏感信息）
   - 复现步骤

3. **联系方式：**
   - 项目GitHub Issues
   - 技术文档：`docs/` 目录
   - 相关模块README文件
