#!/usr/bin/env python3
"""
Arxiv 数据库调试脚本 - 清除所有数据
用于删除数据库中的所有 Arxiv 论文数据，方便测试和重新开始
"""

import psycopg2
import redis
import json
from datetime import datetime
from typing import List, Dict, Any

# 数据库配置
DB_CONFIG = {
    'host': '192.168.5.54',
    'port': 15432,
    'database': 'homesystem',
    'user': 'homesystem',
    'password': 'homesystem123'
}

REDIS_CONFIG = {
    'host': '192.168.5.54',
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

def get_data_stats(conn):
    """获取当前数据统计"""
    try:
        with conn.cursor() as cur:
            # 检查表是否存在
            cur.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' AND tablename = 'arxiv_papers'
            """)
            if not cur.fetchone():
                return None, "表不存在"
            
            # 获取总数
            cur.execute("SELECT COUNT(*) FROM arxiv_papers")
            total_count = cur.fetchone()[0]
            
            # 按状态统计
            cur.execute("""
                SELECT processing_status, COUNT(*) 
                FROM arxiv_papers 
                GROUP BY processing_status
            """)
            status_stats = dict(cur.fetchall())
            
            return total_count, status_stats
    
    except Exception as e:
        return None, f"获取统计失败: {e}"

def clear_postgres_data(conn, confirm=False):
    """清除PostgreSQL中的Arxiv数据"""
    print("\n" + "=" * 60)
    print("🗑️ PostgreSQL 数据清理")
    print("=" * 60)
    
    # 获取当前数据统计
    total_count, status_info = get_data_stats(conn)
    
    if total_count is None:
        print(f"❌ {status_info}")
        return False
    
    if total_count == 0:
        print("📭 数据库中没有数据需要清理")
        return True
    
    print(f"📊 当前数据统计:")
    print(f"   总论文数量: {total_count}")
    if isinstance(status_info, dict):
        print(f"   按状态分布:")
        for status, count in status_info.items():
            print(f"     {status}: {count}")
    
    if not confirm:
        print(f"\n⚠️ 即将删除 {total_count} 篇论文数据")
        response = input("❓ 确认删除所有数据？(输入 'YES' 确认): ").strip()
        if response != 'YES':
            print("❌ 操作已取消")
            return False
    
    try:
        with conn.cursor() as cur:
            print("\n🔄 开始清理数据...")
            
            # 删除所有数据
            cur.execute("DELETE FROM arxiv_papers")
            deleted_count = cur.rowcount
            
            # 重置自动递增序列（如果有的话）
            cur.execute("""
                SELECT sequence_name FROM information_schema.sequences 
                WHERE sequence_schema = 'public'
            """)
            sequences = cur.fetchall()
            for (seq_name,) in sequences:
                if 'arxiv' in seq_name.lower():
                    cur.execute(f"ALTER SEQUENCE {seq_name} RESTART WITH 1")
                    print(f"   重置序列: {seq_name}")
            
            # 提交事务
            conn.commit()
            
            print(f"✅ 成功删除 {deleted_count} 条记录")
            
            # 验证删除结果
            cur.execute("SELECT COUNT(*) FROM arxiv_papers")
            remaining_count = cur.fetchone()[0]
            
            if remaining_count == 0:
                print("✅ 数据库清理完成，所有数据已删除")
                return True
            else:
                print(f"⚠️ 警告：仍有 {remaining_count} 条记录未删除")
                return False
    
    except Exception as e:
        print(f"❌ 删除数据失败: {e}")
        conn.rollback()
        return False

def clear_redis_cache(redis_conn, confirm=False):
    """清除Redis中的Arxiv相关缓存"""
    print("\n" + "=" * 60)
    print("🗑️ Redis 缓存清理")
    print("=" * 60)
    
    if not redis_conn:
        print("⚠️ Redis 未连接，跳过缓存清理")
        return True
    
    try:
        # 查找 Arxiv 相关的键
        arxiv_patterns = ['arxiv:*', 'paper:*', 'cache:arxiv:*', 'arxiv_*']
        all_arxiv_keys = []
        
        for pattern in arxiv_patterns:
            keys = redis_conn.keys(pattern)
            all_arxiv_keys.extend(keys)
        
        # 去重
        unique_keys = list(set(all_arxiv_keys))
        
        if not unique_keys:
            print("📭 没有找到 Arxiv 相关的缓存数据")
            return True
        
        print(f"🔍 找到 {len(unique_keys)} 个 Arxiv 相关缓存键:")
        for key in sorted(unique_keys)[:10]:  # 显示前10个键
            key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)
            print(f"   {key_str}")
        
        if len(unique_keys) > 10:
            print(f"   ... 还有 {len(unique_keys) - 10} 个键")
        
        if not confirm:
            response = input(f"\n❓ 确认删除这 {len(unique_keys)} 个缓存键？(输入 'YES' 确认): ").strip()
            if response != 'YES':
                print("❌ 缓存清理已取消")
                return False
        
        print("\n🔄 开始清理缓存...")
        
        # 删除所有相关键
        deleted_count = 0
        for key in unique_keys:
            try:
                redis_conn.delete(key)
                deleted_count += 1
            except Exception as e:
                print(f"⚠️ 删除键失败 {key}: {e}")
        
        print(f"✅ 成功删除 {deleted_count} 个缓存键")
        return True
    
    except Exception as e:
        print(f"❌ 清理 Redis 缓存失败: {e}")
        return False

def clear_all_redis_cache(redis_conn, confirm=False):
    """清除Redis中的所有缓存（慎用）"""
    print("\n" + "=" * 60)
    print("🗑️ Redis 完全清理 (所有数据)")
    print("=" * 60)
    
    if not redis_conn:
        print("⚠️ Redis 未连接，跳过清理")
        return True
    
    try:
        # 获取当前数据库键数量
        info = redis_conn.info()
        total_keys = info.get('db0', {}).get('keys', 0)
        
        if total_keys == 0:
            print("📭 Redis 数据库为空")
            return True
        
        print(f"⚠️ 警告：这将删除 Redis 数据库中的所有 {total_keys} 个键")
        print("   这包括所有缓存数据，不仅仅是 Arxiv 相关的")
        
        if not confirm:
            response = input("❓ 确认清空整个 Redis 数据库？(输入 'FLUSH ALL' 确认): ").strip()
            if response != 'FLUSH ALL':
                print("❌ 完全清理已取消")
                return False
        
        print("\n🔄 开始清空 Redis 数据库...")
        redis_conn.flushdb()
        
        # 验证结果
        new_info = redis_conn.info()
        remaining_keys = new_info.get('db0', {}).get('keys', 0)
        
        if remaining_keys == 0:
            print("✅ Redis 数据库已完全清空")
            return True
        else:
            print(f"⚠️ 警告：仍有 {remaining_keys} 个键未删除")
            return False
    
    except Exception as e:
        print(f"❌ 清空 Redis 失败: {e}")
        return False

def backup_data_before_clear(conn):
    """在清理前备份重要数据"""
    print("\n" + "=" * 60)
    print("💾 数据备份（可选）")
    print("=" * 60)
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"/tmp/arxiv_backup_{timestamp}.sql"
        
        # 导出数据到SQL文件
        import subprocess
        cmd = [
            'docker', 'exec', 'homesystem-postgres',
            'pg_dump', '-U', 'homesystem', '-d', 'homesystem',
            '-t', 'arxiv_papers', '--data-only', '--inserts'
        ]
        
        with open(backup_file, 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            print(f"✅ 数据已备份到: {backup_file}")
            return backup_file
        else:
            print(f"⚠️ 备份失败: {result.stderr}")
            return None
    
    except Exception as e:
        print(f"⚠️ 备份过程出错: {e}")
        return None

def main():
    """主函数"""
    print("🗑️ Arxiv 数据库调试工具 - 数据清理")
    print(f"⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n⚠️ 警告：此工具将删除所有 Arxiv 论文数据，请谨慎使用！")
    
    # 连接数据库
    conn = connect_db()
    if not conn:
        return
    
    redis_conn = connect_redis()
    
    try:
        # 显示当前数据状态
        total_count, status_info = get_data_stats(conn)
        if total_count is None:
            print(f"❌ {status_info}")
            return
        
        if total_count == 0:
            print("📭 数据库中没有数据，无需清理")
            if redis_conn:
                arxiv_keys = []
                for pattern in ['arxiv:*', 'paper:*', 'cache:arxiv:*']:
                    arxiv_keys.extend(redis_conn.keys(pattern))
                if not arxiv_keys:
                    print("📭 Redis 中也没有 Arxiv 相关缓存")
                    return
            else:
                return
        
        print("\n" + "=" * 60)
        print("🔧 选择清理选项")
        print("=" * 60)
        print("1. 仅清理 PostgreSQL 数据")
        print("2. 仅清理 Redis Arxiv 相关缓存")
        print("3. 清理 PostgreSQL 数据 + Redis Arxiv 缓存")
        print("4. 完全清理 (PostgreSQL + 所有 Redis 数据)")
        print("5. 先备份再清理 (选项3 + 备份)")
        print("0. 取消操作")
        
        try:
            choice = input("\n❓ 请选择操作 (0-5): ").strip()
        except KeyboardInterrupt:
            print("\n❌ 操作已取消")
            return
        
        success = True
        
        if choice == '1':
            success = clear_postgres_data(conn)
        elif choice == '2':
            success = clear_redis_cache(redis_conn)
        elif choice == '3':
            success = clear_postgres_data(conn) and clear_redis_cache(redis_conn)
        elif choice == '4':
            success = clear_postgres_data(conn) and clear_all_redis_cache(redis_conn)
        elif choice == '5':
            backup_file = backup_data_before_clear(conn)
            if backup_file:
                print(f"💾 备份完成: {backup_file}")
            success = clear_postgres_data(conn) and clear_redis_cache(redis_conn)
        elif choice == '0':
            print("❌ 操作已取消")
            return
        else:
            print("❌ 无效选择")
            return
        
        print("\n" + "=" * 60)
        if success:
            print("✅ 数据清理完成")
        else:
            print("❌ 数据清理过程中出现错误")
        print("=" * 60)
        
    finally:
        if conn:
            conn.close()
        if redis_conn:
            redis_conn.close()

if __name__ == "__main__":
    main()