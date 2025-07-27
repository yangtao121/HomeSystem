# 数据库操作接口
import json
import time
from typing import List, Optional, Dict, Any, Type, Union
from loguru import logger

from .connection import DatabaseManager, get_database_manager
from .models import BaseModel


class DatabaseOperations:
    """PostgreSQL数据库操作类"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or get_database_manager()
    
    def init_tables(self, models: List[BaseModel]) -> bool:
        """初始化数据库表结构"""
        try:
            with self.db_manager.get_postgres_sync() as cursor:
                for model in models:
                    sql = model.get_create_table_sql()
                    cursor.execute(sql)
                    logger.info(f"表 {model.table_name} 初始化完成")
            return True
        except Exception as e:
            logger.error(f"数据库表初始化失败: {e}")
            return False
    
    def create(self, model: BaseModel) -> bool:
        """创建记录"""
        try:
            data = model.to_dict()
            table_name = model.table_name
            
            # 构建INSERT语句
            columns = list(data.keys())
            placeholders = ['%s'] * len(columns)
            values = list(data.values())
            
            sql = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT (id) DO NOTHING
            """
            
            with self.db_manager.get_postgres_sync() as cursor:
                cursor.execute(sql, values)
                if cursor.rowcount > 0:
                    logger.debug(f"成功创建记录: {table_name}, ID: {model.id}")
                    return True
                else:
                    logger.warning(f"记录已存在: {table_name}, ID: {model.id}")
                    return False
                    
        except Exception as e:
            logger.error(f"创建记录失败: {e}")
            return False
    
    def get_by_id(self, model_class: Type[BaseModel], record_id: str) -> Optional[BaseModel]:
        """根据ID获取记录"""
        try:
            model_instance = model_class()
            table_name = model_instance.table_name
            
            sql = f"SELECT * FROM {table_name} WHERE id = %s"
            
            with self.db_manager.get_postgres_sync() as cursor:
                cursor.execute(sql, (record_id,))
                result = cursor.fetchone()
                
                if result:
                    return model_class.from_dict(dict(result))
                return None
                
        except Exception as e:
            logger.error(f"根据ID获取记录失败: {e}")
            return None
    
    def get_by_field(self, model_class: Type[BaseModel], field_name: str, value: Any) -> Optional[BaseModel]:
        """根据字段获取记录"""
        try:
            model_instance = model_class()
            table_name = model_instance.table_name
            
            sql = f"SELECT * FROM {table_name} WHERE {field_name} = %s"
            
            with self.db_manager.get_postgres_sync() as cursor:
                cursor.execute(sql, (value,))
                result = cursor.fetchone()
                
                if result:
                    return model_class.from_dict(dict(result))
                return None
                
        except Exception as e:
            logger.error(f"根据字段获取记录失败: {e}")
            return None
    
    def list_all(self, model_class: Type[BaseModel], limit: int = 100, offset: int = 0, 
                 order_by: str = 'created_at DESC') -> List[BaseModel]:
        """列出所有记录"""
        try:
            model_instance = model_class()
            table_name = model_instance.table_name
            
            sql = f"SELECT * FROM {table_name} ORDER BY {order_by} LIMIT %s OFFSET %s"
            
            with self.db_manager.get_postgres_sync() as cursor:
                cursor.execute(sql, (limit, offset))
                results = cursor.fetchall()
                
                return [model_class.from_dict(dict(row)) for row in results]
                
        except Exception as e:
            logger.error(f"列出记录失败: {e}")
            return []
    
    def update(self, model: BaseModel, updates: Dict[str, Any]) -> bool:
        """更新记录"""
        try:
            table_name = model.table_name
            
            # 更新模型属性
            for key, value in updates.items():
                if hasattr(model, key):
                    setattr(model, key, value)
            
            model.update_timestamp()
            
            # 构建UPDATE语句
            set_clauses = []
            values = []
            for key, value in updates.items():
                set_clauses.append(f"{key} = %s")
                values.append(value)
            
            # 添加updated_at
            set_clauses.append("updated_at = %s")
            values.append(model.updated_at)
            values.append(model.id)
            
            sql = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE id = %s"
            
            with self.db_manager.get_postgres_sync() as cursor:
                cursor.execute(sql, values)
                if cursor.rowcount > 0:
                    logger.debug(f"成功更新记录: {table_name}, ID: {model.id}")
                    return True
                else:
                    logger.warning(f"未找到要更新的记录: {table_name}, ID: {model.id}")
                    return False
                    
        except Exception as e:
            logger.error(f"更新记录失败: {e}")
            return False
    
    def delete(self, model: BaseModel) -> bool:
        """删除记录"""
        try:
            table_name = model.table_name
            sql = f"DELETE FROM {table_name} WHERE id = %s"
            
            with self.db_manager.get_postgres_sync() as cursor:
                cursor.execute(sql, (model.id,))
                if cursor.rowcount > 0:
                    logger.debug(f"成功删除记录: {table_name}, ID: {model.id}")
                    return True
                else:
                    logger.warning(f"未找到要删除的记录: {table_name}, ID: {model.id}")
                    return False
                    
        except Exception as e:
            logger.error(f"删除记录失败: {e}")
            return False
    
    def exists(self, model_class: Type[BaseModel], field_name: str, value: Any) -> bool:
        """检查记录是否存在"""
        try:
            model_instance = model_class()
            table_name = model_instance.table_name
            
            sql = f"SELECT 1 FROM {table_name} WHERE {field_name} = %s LIMIT 1"
            
            with self.db_manager.get_postgres_sync() as cursor:
                cursor.execute(sql, (value,))
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"检查记录存在性失败: {e}")
            return False
    
    def count(self, model_class: Type[BaseModel], where_clause: str = None, params: tuple = None) -> int:
        """统计记录数量"""
        try:
            model_instance = model_class()
            table_name = model_instance.table_name
            
            sql = f"SELECT COUNT(*) FROM {table_name}"
            if where_clause:
                sql += f" WHERE {where_clause}"
            
            with self.db_manager.get_postgres_sync() as cursor:
                cursor.execute(sql, params or ())
                result = cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            logger.error(f"统计记录数量失败: {e}")
            return 0
    
    def batch_create(self, models: List[BaseModel]) -> int:
        """批量创建记录"""
        if not models:
            return 0
        
        try:
            table_name = models[0].table_name
            data_list = [model.to_dict() for model in models]
            
            if not data_list:
                return 0
            
            # 获取列名
            columns = list(data_list[0].keys())
            placeholders = ['%s'] * len(columns)
            
            # 构建批量INSERT语句
            sql = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT (id) DO NOTHING
            """
            
            # 准备数据
            values_list = [list(data.values()) for data in data_list]
            
            with self.db_manager.get_postgres_sync() as cursor:
                cursor.executemany(sql, values_list)
                count = cursor.rowcount
                logger.info(f"批量创建记录完成: {table_name}, 成功: {count}/{len(models)}")
                return count
                
        except Exception as e:
            logger.error(f"批量创建记录失败: {e}")
            return 0


class CacheOperations:
    """Redis缓存操作类"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or get_database_manager()
        self.redis_client = None
    
    def _get_redis(self):
        """获取Redis客户端"""
        if self.redis_client is None:
            self.redis_client = self.db_manager.get_redis()
        return self.redis_client
    
    def set(self, key: str, value: str, expire: int = None) -> bool:
        """设置键值对"""
        try:
            redis_client = self._get_redis()
            result = redis_client.set(key, value, ex=expire)
            return result is True
        except Exception as e:
            logger.error(f"Redis SET 操作失败: {e}")
            return False
    
    def get(self, key: str) -> Optional[str]:
        """获取值"""
        try:
            redis_client = self._get_redis()
            return redis_client.get(key)
        except Exception as e:
            logger.error(f"Redis GET 操作失败: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """删除键"""
        try:
            redis_client = self._get_redis()
            return redis_client.delete(key) > 0
        except Exception as e:
            logger.error(f"Redis DELETE 操作失败: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            redis_client = self._get_redis()
            return redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis EXISTS 操作失败: {e}")
            return False
    
    def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        try:
            redis_client = self._get_redis()
            return redis_client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis EXPIRE 操作失败: {e}")
            return False
    
    def ttl(self, key: str) -> int:
        """获取剩余生存时间"""
        try:
            redis_client = self._get_redis()
            return redis_client.ttl(key)
        except Exception as e:
            logger.error(f"Redis TTL 操作失败: {e}")
            return -1
    
    def sadd(self, key: str, *values) -> int:
        """向集合添加元素"""
        try:
            redis_client = self._get_redis()
            return redis_client.sadd(key, *values)
        except Exception as e:
            logger.error(f"Redis SADD 操作失败: {e}")
            return 0
    
    def sismember(self, key: str, value: str) -> bool:
        """检查元素是否在集合中"""
        try:
            redis_client = self._get_redis()
            return redis_client.sismember(key, value)
        except Exception as e:
            logger.error(f"Redis SISMEMBER 操作失败: {e}")
            return False
    
    def smembers(self, key: str) -> set:
        """获取集合所有成员"""
        try:
            redis_client = self._get_redis()
            return redis_client.smembers(key)
        except Exception as e:
            logger.error(f"Redis SMEMBERS 操作失败: {e}")
            return set()
    
    def srem(self, key: str, *values) -> int:
        """从集合移除元素"""
        try:
            redis_client = self._get_redis()
            return redis_client.srem(key, *values)
        except Exception as e:
            logger.error(f"Redis SREM 操作失败: {e}")
            return 0
    
    def hset(self, name: str, mapping: Dict[str, str]) -> int:
        """设置哈希表字段"""
        try:
            redis_client = self._get_redis()
            return redis_client.hset(name, mapping=mapping)
        except Exception as e:
            logger.error(f"Redis HSET 操作失败: {e}")
            return 0
    
    def hget(self, name: str, key: str) -> Optional[str]:
        """获取哈希表字段值"""
        try:
            redis_client = self._get_redis()
            return redis_client.hget(name, key)
        except Exception as e:
            logger.error(f"Redis HGET 操作失败: {e}")
            return None
    
    def hgetall(self, name: str) -> Dict[str, str]:
        """获取哈希表所有字段"""
        try:
            redis_client = self._get_redis()
            return redis_client.hgetall(name)
        except Exception as e:
            logger.error(f"Redis HGETALL 操作失败: {e}")
            return {}
    
    def cache_model(self, model: BaseModel, expire: int = 600) -> bool:
        """缓存模型对象"""
        try:
            key = f"model:{model.table_name}:{model.id}"
            value = json.dumps(model.to_dict(), default=str)
            return self.set(key, value, expire)
        except Exception as e:
            logger.error(f"缓存模型失败: {e}")
            return False
    
    def get_cached_model(self, model_class: Type[BaseModel], model_id: str) -> Optional[BaseModel]:
        """获取缓存的模型对象"""
        try:
            model_instance = model_class()
            key = f"model:{model_instance.table_name}:{model_id}"
            cached_data = self.get(key)
            
            if cached_data:
                data = json.loads(cached_data)
                return model_class.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"获取缓存模型失败: {e}")
            return None
    
    def invalidate_model_cache(self, model: BaseModel) -> bool:
        """使模型缓存失效"""
        try:
            key = f"model:{model.table_name}:{model.id}"
            return self.delete(key)
        except Exception as e:
            logger.error(f"使模型缓存失效失败: {e}")
            return False