"""
配置文件 - 数据库连接和应用配置
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库配置
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 15432)),
    'database': os.getenv('DB_NAME', 'homesystem'),
    'user': os.getenv('DB_USER', 'homesystem'),
    'password': os.getenv('DB_PASSWORD', 'homesystem123')
}

# Redis配置
REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', 16379)),
    'db': int(os.getenv('REDIS_DB', 0))
}

# Dify知识库配置
DIFY_CONFIG = {
    'base_url': os.getenv('DIFY_BASE_URL', 'http://localhost:80/v1'),
    'api_key': os.getenv('DIFY_KB_API_KEY', ''),
    'timeout': int(os.getenv('DIFY_TIMEOUT', 30)),
    'max_retries': int(os.getenv('DIFY_MAX_RETRIES', 3)),
    'retry_delay': float(os.getenv('DIFY_RETRY_DELAY', 1.0)),
    'enabled': os.getenv('DIFY_ENABLED', 'false').lower() == 'true'
}

# Flask应用配置
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_PORT', 5000))
    
    # 分页配置
    PAPERS_PER_PAGE = 20
    MAX_SEARCH_RESULTS = 1000
    
    # 缓存配置
    CACHE_TIMEOUT = 300  # 5分钟
    STATS_CACHE_TIMEOUT = 900  # 15分钟