# 数据库连接管理模块
import os
import asyncio
from typing import Dict, Any, Optional, AsyncContextManager, ContextManager
from contextlib import asynccontextmanager, contextmanager
import asyncpg
import psycopg2
import psycopg2.extras
import redis
from loguru import logger


class DatabaseManager:
    """数据库连接管理器，支持 PostgreSQL 和 Redis"""
    
    def __init__(self):
        self._config = self._load_config()
        self.postgres_sync_conn = None
        self.postgres_pool = None
        self.redis_client = None
        
    def _load_config(self) -> Dict[str, Any]:
        """加载数据库配置"""
        return {
            'postgres': {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'database': os.getenv('DB_NAME', 'homesystem'),
                'user': os.getenv('DB_USER', 'homesystem'),
                'password': os.getenv('DB_PASSWORD', 'homesystem123'),
            },
            'redis': {
                'host': os.getenv('REDIS_HOST', 'localhost'),
                'port': int(os.getenv('REDIS_PORT', 6379)),
                'db': int(os.getenv('REDIS_DB', 0)),
                'decode_responses': True,
            }
        }
    
    @contextmanager
    def get_postgres_sync(self):
        """获取 PostgreSQL 同步连接上下文管理器"""
        conn = None
        cursor = None
        try:
            if not self.postgres_sync_conn or self.postgres_sync_conn.closed:
                self.postgres_sync_conn = psycopg2.connect(**self._config['postgres'])
                self.postgres_sync_conn.autocommit = False
                logger.debug("创建新的 PostgreSQL 同步连接")
            
            conn = self.postgres_sync_conn
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            yield cursor
            
            # 如果没有异常，提交事务
            conn.commit()
            logger.debug("PostgreSQL 事务已提交")
            
        except Exception as e:
            if conn:
                conn.rollback()
                logger.error(f"PostgreSQL 事务已回滚: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
    
    async def init_postgres_async(self):
        """初始化 PostgreSQL 异步连接池"""
        if self.postgres_pool is None:
            try:
                self.postgres_pool = await asyncpg.create_pool(
                    **self._config['postgres'],
                    min_size=5,
                    max_size=20,
                    command_timeout=60
                )
                logger.info("PostgreSQL 异步连接池已初始化")
            except Exception as e:
                logger.error(f"PostgreSQL 异步连接池初始化失败: {e}")
                raise
    
    @asynccontextmanager
    async def get_postgres_async(self):
        """获取 PostgreSQL 异步连接上下文管理器"""
        if self.postgres_pool is None:
            await self.init_postgres_async()
        
        async with self.postgres_pool.acquire() as conn:
            async with conn.transaction():
                yield conn
    
    def get_redis(self) -> redis.Redis:
        """获取 Redis 客户端"""
        if self.redis_client is None:
            try:
                self.redis_client = redis.Redis(**self._config['redis'])
                # 测试连接
                self.redis_client.ping()
                logger.info("Redis 连接已建立")
            except Exception as e:
                logger.error(f"Redis 连接失败: {e}")
                raise
        
        return self.redis_client
    
    def close_connections(self):
        """关闭所有连接"""
        if self.postgres_sync_conn and not self.postgres_sync_conn.closed:
            self.postgres_sync_conn.close()
            logger.info("PostgreSQL 同步连接已关闭")
        
        if self.postgres_pool:
            asyncio.create_task(self.postgres_pool.close())
            logger.info("PostgreSQL 异步连接池已关闭")
        
        if self.redis_client:
            self.redis_client.close()
            logger.info("Redis 连接已关闭")
    
    def health_check(self) -> Dict[str, bool]:
        """检查数据库连接健康状态"""
        health = {
            'postgres_sync': False,
            'postgres_async': False,
            'redis': False
        }
        
        # 检查 PostgreSQL 同步连接
        try:
            with self.get_postgres_sync() as cursor:
                cursor.execute("SELECT 1")
                health['postgres_sync'] = True
        except Exception as e:
            logger.warning(f"PostgreSQL 同步连接健康检查失败: {e}")
        
        # 检查 Redis 连接
        try:
            redis_client = self.get_redis()
            redis_client.ping()
            health['redis'] = True
        except Exception as e:
            logger.warning(f"Redis 连接健康检查失败: {e}")
        
        return health


# 全局数据库管理器实例
db_manager = DatabaseManager()


def get_database_manager() -> DatabaseManager:
    """获取数据库管理器实例"""
    return db_manager


def close_all_connections():
    """关闭所有数据库连接"""
    db_manager.close_connections()


def check_database_health() -> Dict[str, bool]:
    """检查数据库健康状态"""
    return db_manager.health_check()