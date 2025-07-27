#!/usr/bin/env python3
"""
Arxiv 数据库调试脚本 - 显示现有数据
用于查看当前数据库中的 Arxiv 论文数据，方便调试和开发
"""

import psycopg2
import redis
import json
from datetime import datetime
from typing import List, Dict, Any

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 15432,
    'database': 'homesystem',
    'user': 'homesystem',
    'password': 'homesystem123'
}

REDIS_CONFIG = {
    'host': 'localhost',
    'port': 16379,
    'db': 0
}

def connect_db():
    """连接PostgreSQL数据库"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return None

def connect_redis():
    """连接Redis缓存"""
    try:
        r = redis.Redis(**REDIS_CONFIG)
        r.ping()
        return r
    except Exception as e:
        print(f"⚠️ Redis连接失败: {e}")
        return None

def show_table_stats(conn):
    """显示表统计信息"""
    print("=" * 60)
    print("📊 数据库表统计信息")
    print("=" * 60)
    
    try:
        with conn.cursor() as cur:
            # 检查表是否存在
            cur.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' AND tablename = 'arxiv_papers'
            """)
            if not cur.fetchone():
                print("❌ arxiv_papers 表不存在")
                return
            
            # 总数据量
            cur.execute("SELECT COUNT(*) FROM arxiv_papers")
            total_count = cur.fetchone()[0]
            print(f"📚 总论文数量: {total_count}")
            
            if total_count == 0:
                print("📭 数据库为空，没有论文数据")
                return
            
            # 按状态统计
            cur.execute("""
                SELECT processing_status, COUNT(*) 
                FROM arxiv_papers 
                GROUP BY processing_status 
                ORDER BY COUNT(*) DESC
            """)
            print(f"\n🔄 按处理状态统计:")
            for status, count in cur.fetchall():
                print(f"   {status}: {count}")
            
            # 按类别统计 (top 10)
            cur.execute("""
                SELECT categories, COUNT(*) 
                FROM arxiv_papers 
                WHERE categories IS NOT NULL AND categories != ''
                GROUP BY categories 
                ORDER BY COUNT(*) DESC 
                LIMIT 10
            """)
            categories_stats = cur.fetchall()
            if categories_stats:
                print(f"\n🏷️ 热门类别 (Top 10):")
                for category, count in categories_stats:
                    print(f"   {category}: {count}")
            
            # 最近添加的论文
            cur.execute("""
                SELECT created_at::date, COUNT(*) 
                FROM arxiv_papers 
                GROUP BY created_at::date 
                ORDER BY created_at::date DESC 
                LIMIT 7
            """)
            recent_stats = cur.fetchall()
            if recent_stats:
                print(f"\n📅 最近7天添加统计:")
                for date, count in recent_stats:
                    print(f"   {date}: {count}")
    
    except Exception as e:
        print(f"❌ 获取统计信息失败: {e}")

def show_sample_papers(conn, limit=5):
    """显示样本论文数据"""
    print("\n" + "=" * 60)
    print(f"📄 最新 {limit} 篇论文样本")
    print("=" * 60)
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, arxiv_id, title, authors, categories, 
                       processing_status, created_at
                FROM arxiv_papers 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (limit,))
            
            papers = cur.fetchall()
            
            if not papers:
                print("📭 没有找到论文数据")
                return
            
            for i, paper in enumerate(papers, 1):
                id, arxiv_id, title, authors, categories, status, created_at = paper
                print(f"\n📋 论文 {i}:")
                print(f"   ID: {id}")
                print(f"   ArXiv ID: {arxiv_id}")
                print(f"   标题: {title[:80]}{'...' if len(title) > 80 else ''}")
                print(f"   作者: {authors[:60]}{'...' if len(authors) > 60 else ''}")
                print(f"   类别: {categories}")
                print(f"   状态: {status}")
                print(f"   创建时间: {created_at}")
    
    except Exception as e:
        print(f"❌ 获取样本数据失败: {e}")

def show_detailed_paper(conn, arxiv_id=None):
    """显示详细的论文信息"""
    if not arxiv_id:
        # 随机选择一篇论文
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT arxiv_id FROM arxiv_papers ORDER BY RANDOM() LIMIT 1")
                result = cur.fetchone()
                if result:
                    arxiv_id = result[0]
                else:
                    print("📭 没有论文数据可显示")
                    return
        except Exception as e:
            print(f"❌ 获取随机论文失败: {e}")
            return
    
    print("\n" + "=" * 60)
    print(f"🔍 论文详细信息: {arxiv_id}")
    print("=" * 60)
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM arxiv_papers WHERE arxiv_id = %s
            """, (arxiv_id,))
            
            paper = cur.fetchone()
            if not paper:
                print(f"❌ 未找到论文: {arxiv_id}")
                return
            
            # 获取列名
            cur.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'arxiv_papers' 
                ORDER BY ordinal_position
            """)
            columns = [row[0] for row in cur.fetchall()]
            
            # 显示详细信息
            for col, value in zip(columns, paper):
                if col in ['tags', 'metadata'] and value:
                    try:
                        formatted_value = json.dumps(value, indent=2, ensure_ascii=False)
                        print(f"   {col}: {formatted_value}")
                    except:
                        print(f"   {col}: {value}")
                elif col in ['abstract', 'title'] and value and len(str(value)) > 100:
                    print(f"   {col}: {str(value)[:100]}...")
                    print(f"   {col}_full: {value}")
                else:
                    print(f"   {col}: {value}")
    
    except Exception as e:
        print(f"❌ 获取详细信息失败: {e}")

def show_redis_cache(redis_conn):
    """显示Redis缓存信息"""
    print("\n" + "=" * 60)
    print("💾 Redis 缓存信息")
    print("=" * 60)
    
    if not redis_conn:
        print("⚠️ Redis 未连接，跳过缓存信息显示")
        return
    
    try:
        # Redis 基本信息
        info = redis_conn.info()
        print(f"🔧 Redis 版本: {info.get('redis_version', 'Unknown')}")
        print(f"💾 使用内存: {info.get('used_memory_human', 'Unknown')}")
        print(f"🔑 总键数量: {info.get('db0', {}).get('keys', 0)}")
        
        # 查找 Arxiv 相关的键
        arxiv_keys = []
        for pattern in ['arxiv:*', 'paper:*', 'cache:arxiv:*']:
            keys = redis_conn.keys(pattern)
            arxiv_keys.extend(keys)
        
        if arxiv_keys:
            print(f"\n🏷️ Arxiv 相关缓存键 ({len(arxiv_keys)}):")
            for key in sorted(arxiv_keys)[:10]:  # 只显示前10个
                key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)
                ttl = redis_conn.ttl(key)
                ttl_str = f"TTL: {ttl}s" if ttl > 0 else "永久" if ttl == -1 else "已过期"
                print(f"   {key_str} ({ttl_str})")
            
            if len(arxiv_keys) > 10:
                print(f"   ... 还有 {len(arxiv_keys) - 10} 个键")
        else:
            print("📭 没有找到 Arxiv 相关的缓存数据")
    
    except Exception as e:
        print(f"❌ 获取 Redis 信息失败: {e}")

def show_database_schema(conn):
    """显示数据库表结构"""
    print("\n" + "=" * 60)
    print("🏗️ 数据库表结构")
    print("=" * 60)
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'arxiv_papers'
                ORDER BY ordinal_position
            """)
            
            columns = cur.fetchall()
            
            print("📋 arxiv_papers 表结构:")
            print(f"{'列名':<20} {'类型':<15} {'可空':<8} {'默认值'}")
            print("-" * 60)
            
            for col_name, data_type, is_nullable, default in columns:
                nullable = "是" if is_nullable == "YES" else "否"
                default_str = str(default)[:20] if default else ""
                print(f"{col_name:<20} {data_type:<15} {nullable:<8} {default_str}")
            
            # 显示索引信息
            cur.execute("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = 'arxiv_papers'
            """)
            
            indexes = cur.fetchall()
            if indexes:
                print(f"\n🔍 索引信息:")
                for idx_name, idx_def in indexes:
                    print(f"   {idx_name}: {idx_def}")
    
    except Exception as e:
        print(f"❌ 获取表结构失败: {e}")

def main():
    """主函数"""
    print("🔍 Arxiv 数据库调试工具 - 数据显示")
    print(f"⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 连接数据库
    conn = connect_db()
    if not conn:
        return
    
    redis_conn = connect_redis()
    
    try:
        # 显示各种信息
        show_table_stats(conn)
        show_sample_papers(conn, 5)
        show_detailed_paper(conn)
        show_redis_cache(redis_conn)
        show_database_schema(conn)
        
        print("\n" + "=" * 60)
        print("✅ 数据显示完成")
        print("=" * 60)
        
    finally:
        if conn:
            conn.close()
        if redis_conn:
            redis_conn.close()

if __name__ == "__main__":
    main()