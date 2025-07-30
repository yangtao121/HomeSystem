"""
PaperGather Web应用配置文件
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库配置 - 复用现有配置
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

# Flask应用配置
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'papergather-dev-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_PORT', 5001))  # 避免与ExplorePaperData冲突
    
    # 分页配置
    PAPERS_PER_PAGE = 20
    MAX_SEARCH_RESULTS = 1000
    
    # 缓存配置
    CACHE_TIMEOUT = 300  # 5分钟
    TASK_STATUS_CACHE_TIMEOUT = 60  # 1分钟
    
    # 任务配置
    MAX_CONCURRENT_TASKS = 3
    TASK_TIMEOUT = 3600  # 1小时超时

# PaperGatherTask默认配置
DEFAULT_TASK_CONFIG = {
    'search_query': 'navigation, dataset, learning based',
    'max_papers_per_search': 20,
    'user_requirements': 'Methods for creating navigation datasets, how to generate simulation data.',
    'llm_model_name': 'ollama.Qwen3_30B',
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
    'start_year': None,
    'end_year': None,
    'after_year': None
}