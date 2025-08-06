"""
PaperAnalysis 统一配置文件
合并了PaperGather和ExplorePaperData的所有配置
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
    SECRET_KEY = os.getenv('SECRET_KEY', 'paper-analysis-dev-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_PORT', 5002))  # 使用5002避免冲突
    
    # 分页配置
    PAPERS_PER_PAGE = 20
    MAX_SEARCH_RESULTS = 1000
    
    # 缓存配置
    CACHE_TIMEOUT = 300  # 5分钟
    STATS_CACHE_TIMEOUT = 900  # 15分钟
    TASK_STATUS_CACHE_TIMEOUT = 60  # 1分钟
    
    # 任务配置
    MAX_CONCURRENT_TASKS = 3
    TASK_TIMEOUT = 3600  # 1小时超时

# PaperGatherTask默认配置
DEFAULT_TASK_CONFIG = {
    'search_query': 'navigation, dataset, learning based',
    'max_papers_per_search': 20,
    'user_requirements': 'Methods for creating navigation datasets, how to generate simulation data.',
    'llm_model_name': 'deepseek.DeepSeek_V3',  # 使用DeepSeek作为默认模型
    'abstract_analysis_model': None,  # 使用llm_model_name作为默认值
    'full_paper_analysis_model': None,  # 使用llm_model_name作为默认值
    'translation_model': None,  # 使用llm_model_name作为默认值
    'paper_analysis_model': None,  # 使用llm_model_name作为默认值
    'relevance_threshold': 0.7,
    'max_papers_in_response': 50,
    'max_relevant_papers_in_response': 10,
    'enable_paper_summarization': True,
    'summarization_threshold': 0.8,
    'enable_translation': True,
    # 新增搜索模式相关配置
    'search_mode': 'latest',  # ArxivSearchMode.LATEST.value
    'start_year': 2023,  # 提供默认的开始年份
    'end_year': 2024,    # 提供默认的结束年份
    'after_year': 2023,  # 提供默认的后续年份
    # 添加间隔配置（用于定时任务）
    'interval_seconds': 3600  # 默认1小时间隔
}