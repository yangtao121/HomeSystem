#!/usr/bin/env python3
"""
简化版Arxiv数据库操作示例
直接使用SQL操作，避免导入问题
"""

import os
import json
import psycopg2
import psycopg2.extras
import redis
from datetime import datetime
import uuid

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
    'db': 0,
    'decode_responses': True
}


def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(**DB_CONFIG)


def get_redis_connection():
    """获取Redis连接"""
    return redis.Redis(**REDIS_CONFIG)


def demo_insert_papers():
    """插入示例论文数据"""
    print("📊 插入示例论文数据")
    print("-" * 50)
    
    # 示例论文数据
    papers = [
        {
            'arxiv_id': '2024.01001',
            'title': 'Deep Learning Advances in Natural Language Processing',
            'authors': 'Zhang Wei, Li Ming, Wang Hao',
            'abstract': 'This paper surveys the latest developments in deep learning for NLP, including Transformer architectures, pre-trained models, and multimodal learning.',
            'categories': 'cs.CL, cs.LG, cs.AI',
            'published_date': '2024-01-15',
            'pdf_url': 'https://arxiv.org/pdf/2024.01001.pdf',
            'processing_status': 'pending',
            'tags': ['深度学习', 'NLP', 'Transformer', '预训练模型'],
            'metadata': {
                'conference': 'AAAI 2024',
                'citation_count': 156,
                'download_count': 2341
            }
        },
        {
            'arxiv_id': '2024.01002',
            'title': 'Adversarial Attacks and Defense Mechanisms in Computer Vision',
            'authors': 'Chen Xiaoli, Liu Qiang, Yang Feng',
            'abstract': 'Adversarial examples pose significant security threats to deep learning models. This study systematically analyzes adversarial attack methods in computer vision.',
            'categories': 'cs.CV, cs.CR, cs.LG',
            'published_date': '2024-01-20',
            'pdf_url': 'https://arxiv.org/pdf/2024.01002.pdf',
            'processing_status': 'pending',
            'tags': ['计算机视觉', '对抗样本', '安全', '防御'],
            'metadata': {
                'conference': 'CVPR 2024',
                'citation_count': 89,
                'download_count': 1456
            }
        },
        {
            'arxiv_id': '2024.01003',
            'title': 'Quantum Machine Learning: Theory and Implementation',
            'authors': 'Wang Quantum, Li Superposition, Zhang Entanglement',
            'abstract': 'Quantum computing brings new possibilities to machine learning. This paper studies quantum support vector machines and quantum neural networks.',
            'categories': 'quant-ph, cs.LG, cs.ET',
            'published_date': '2024-01-25',
            'pdf_url': 'https://arxiv.org/pdf/2024.01003.pdf',
            'processing_status': 'pending',
            'tags': ['量子计算', '机器学习', '量子算法', '理论分析'],
            'metadata': {
                'conference': 'Nature Quantum Information',
                'citation_count': 234,
                'download_count': 3421
            }
        }
    ]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    inserted_count = 0
    for paper in papers:
        try:
            cursor.execute("""
                INSERT INTO arxiv_papers (
                    arxiv_id, title, authors, abstract, categories, 
                    published_date, pdf_url, processing_status, tags, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (arxiv_id) DO NOTHING
            """, (
                paper['arxiv_id'],
                paper['title'],
                paper['authors'],
                paper['abstract'],
                paper['categories'],
                paper['published_date'],
                paper['pdf_url'],
                paper['processing_status'],
                json.dumps(paper['tags']),
                json.dumps(paper['metadata'])
            ))
            
            if cursor.rowcount > 0:
                inserted_count += 1
                print(f"  ✅ 已插入: {paper['title'][:50]}...")
            else:
                print(f"  ⚠️  已存在: {paper['arxiv_id']}")
                
        except Exception as e:
            print(f"  ❌ 插入失败: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n📊 成功插入 {inserted_count} 篇论文")
    return True


def demo_query_operations():
    """查询操作示例"""
    print("\n🔍 查询操作示例")
    print("-" * 50)
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # 1. 查询所有论文
    cursor.execute("SELECT COUNT(*) as total FROM arxiv_papers")
    total = cursor.fetchone()['total']
    print(f"📈 数据库中共有 {total} 篇论文")
    
    # 2. 根据arxiv_id查询
    cursor.execute("""
        SELECT arxiv_id, title, authors, categories, processing_status 
        FROM arxiv_papers 
        WHERE arxiv_id = %s
    """, ('2024.01001',))
    
    paper = cursor.fetchone()
    if paper:
        print(f"\n✅ 根据ID查询成功:")
        print(f"   标题: {paper['title']}")
        print(f"   作者: {paper['authors']}")
        print(f"   类别: {paper['categories']}")
        print(f"   状态: {paper['processing_status']}")
    
    # 3. 按类别分组统计
    cursor.execute("""
        SELECT 
            categories,
            COUNT(*) as count,
            AVG(CAST(metadata->>'citation_count' AS INTEGER)) as avg_citations
        FROM arxiv_papers 
        WHERE metadata->>'citation_count' IS NOT NULL
        GROUP BY categories 
        ORDER BY count DESC
    """)
    
    print(f"\n📊 按类别分组统计:")
    for row in cursor.fetchall():
        print(f"   📁 {row['categories']}: {row['count']} 篇, 平均引用 {row['avg_citations']:.1f} 次")
    
    # 4. 搜索包含特定关键词的论文
    cursor.execute("""
        SELECT arxiv_id, title 
        FROM arxiv_papers 
        WHERE title ILIKE %s OR abstract ILIKE %s
        LIMIT 3
    """, ('%learning%', '%learning%'))
    
    print(f"\n🔍 包含'learning'的论文:")
    for row in cursor.fetchall():
        print(f"   📄 {row['arxiv_id']}: {row['title']}")
    
    # 5. 根据标签查询
    cursor.execute("""
        SELECT arxiv_id, title, tags
        FROM arxiv_papers 
        WHERE tags @> %s
        LIMIT 3
    """, (json.dumps(['深度学习']),))
    
    print(f"\n🏷️  标签包含'深度学习'的论文:")
    results = cursor.fetchall()
    for row in results:
        tags = json.loads(row['tags']) if isinstance(row['tags'], str) else row['tags']
        print(f"   🔖 {row['arxiv_id']}: {row['title'][:50]}...")
        print(f"      标签: {', '.join(tags)}")
    
    cursor.close()
    conn.close()
    return True


def demo_update_operations():
    """更新操作示例"""
    print("\n📝 更新操作示例")
    print("-" * 50)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 更新论文状态
    cursor.execute("""
        UPDATE arxiv_papers 
        SET processing_status = 'completed', 
            updated_at = CURRENT_TIMESTAMP
        WHERE arxiv_id = %s
    """, ('2024.01001',))
    
    if cursor.rowcount > 0:
        print("✅ 论文状态已更新为 'completed'")
    
    # 2. 添加标签
    cursor.execute("""
        UPDATE arxiv_papers 
        SET tags = tags || %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE arxiv_id = %s
    """, (json.dumps(['已处理']), '2024.01001'))
    
    if cursor.rowcount > 0:
        print("✅ 已添加'已处理'标签")
    
    # 3. 批量更新处理状态
    cursor.execute("""
        UPDATE arxiv_papers 
        SET processing_status = 'completed',
            updated_at = CURRENT_TIMESTAMP
        WHERE processing_status = 'pending' 
        AND arxiv_id IN ('2024.01002', '2024.01003')
    """)
    
    print(f"✅ 批量更新了 {cursor.rowcount} 篇论文的状态")
    
    conn.commit()
    cursor.close()
    conn.close()
    return True


def demo_redis_operations():
    """Redis缓存操作示例"""
    print("\n💾 Redis缓存操作示例")
    print("-" * 50)
    
    try:
        redis_client = get_redis_connection()
        
        # 1. 基础键值操作
        redis_client.set("demo:example", "示例缓存值", ex=300)  # 5分钟过期
        value = redis_client.get("demo:example")
        print(f"✅ 基础缓存操作: {value}")
        
        # 2. 集合操作 - 已处理论文集合
        processed_papers = ['2024.01001', '2024.01002', '2024.01003']
        redis_client.sadd("processed_papers", *processed_papers)
        
        # 检查论文是否已处理
        is_processed = redis_client.sismember("processed_papers", "2024.01001")
        print(f"✅ 集合操作: 论文2024.01001已处理 = {is_processed}")
        
        # 获取所有已处理论文
        all_processed = redis_client.smembers("processed_papers")
        print(f"✅ 已处理论文: {', '.join(sorted(all_processed))}")
        
        # 3. 哈希操作 - 论文元数据缓存
        paper_meta = {
            "title": "Deep Learning Advances in NLP",
            "citations": "156",
            "downloads": "2341",
            "status": "completed"
        }
        redis_client.hset("paper:2024.01001", mapping=paper_meta)
        
        # 获取论文元数据
        cached_meta = redis_client.hgetall("paper:2024.01001")
        print(f"✅ 哈希操作: 论文元数据缓存成功")
        print(f"   标题: {cached_meta.get('title')}")
        print(f"   引用: {cached_meta.get('citations')}")
        
        # 4. 计数器操作
        redis_client.incr("stats:total_papers")
        redis_client.incr("stats:processed_today", amount=3)
        
        total_papers = redis_client.get("stats:total_papers")
        processed_today = redis_client.get("stats:processed_today")
        print(f"✅ 计数器: 总论文={total_papers}, 今日处理={processed_today}")
        
        # 5. 列表操作 - 处理队列
        queue_items = ['2024.01004', '2024.01005', '2024.01006']
        redis_client.lpush("processing_queue", *queue_items)
        
        # 获取队列长度
        queue_length = redis_client.llen("processing_queue")
        print(f"✅ 队列操作: 处理队列长度 = {queue_length}")
        
        # 从队列取出任务
        next_task = redis_client.rpop("processing_queue")
        print(f"✅ 队列操作: 下一个处理任务 = {next_task}")
        
        return True
        
    except Exception as e:
        print(f"❌ Redis操作失败: {e}")
        return False


def demo_advanced_analytics():
    """高级分析示例"""
    print("\n📈 高级分析示例")
    print("-" * 50)
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # 1. 论文发布趋势分析
    cursor.execute("""
        SELECT 
            DATE_TRUNC('month', created_at) as month,
            COUNT(*) as paper_count
        FROM arxiv_papers 
        GROUP BY DATE_TRUNC('month', created_at)
        ORDER BY month DESC
        LIMIT 6
    """)
    
    print("📊 论文发布趋势:")
    for row in cursor.fetchall():
        print(f"   📅 {row['month'].strftime('%Y-%m')}: {row['paper_count']} 篇")
    
    # 2. 高引用论文排行
    cursor.execute("""
        SELECT 
            arxiv_id,
            title,
            CAST(metadata->>'citation_count' AS INTEGER) as citations,
            CAST(metadata->>'download_count' AS INTEGER) as downloads
        FROM arxiv_papers 
        WHERE metadata->>'citation_count' IS NOT NULL
        ORDER BY CAST(metadata->>'citation_count' AS INTEGER) DESC
        LIMIT 3
    """)
    
    print(f"\n🌟 高引用论文排行:")
    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"   {i}. {row['title'][:50]}...")
        print(f"      ID: {row['arxiv_id']}, 引用: {row['citations']}, 下载: {row['downloads']}")
    
    # 3. 分类分布统计
    cursor.execute("""
        SELECT 
            UNNEST(string_to_array(categories, ', ')) as category,
            COUNT(*) as count
        FROM arxiv_papers 
        GROUP BY category
        ORDER BY count DESC
        LIMIT 5
    """)
    
    print(f"\n📁 分类分布统计:")
    for row in cursor.fetchall():
        print(f"   📂 {row['category']}: {row['count']} 篇")
    
    # 4. 处理状态统计
    cursor.execute("""
        SELECT 
            processing_status,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
        FROM arxiv_papers 
        GROUP BY processing_status
        ORDER BY count DESC
    """)
    
    print(f"\n⚙️ 处理状态统计:")
    for row in cursor.fetchall():
        print(f"   📊 {row['processing_status']}: {row['count']} 篇 ({row['percentage']}%)")
    
    cursor.close()
    conn.close()
    return True


def main():
    """主函数"""
    print("🎯 Arxiv数据库操作完整示例")
    print("🗄️  数据库: PostgreSQL (localhost:15432) + Redis (localhost:16379)")
    print("📊 功能: 论文管理、查询、缓存、分析")
    print("=" * 70)
    
    # 运行所有示例
    examples = [
        ("插入示例数据", demo_insert_papers),
        ("查询操作", demo_query_operations),
        ("更新操作", demo_update_operations),
        ("Redis缓存操作", demo_redis_operations),
        ("高级分析", demo_advanced_analytics),
    ]
    
    success_count = 0
    for name, func in examples:
        try:
            print(f"\n{'='*20} {name} {'='*20}")
            if func():
                success_count += 1
                print(f"✅ {name} 完成")
            else:
                print(f"⚠️  {name} 部分失败")
        except Exception as e:
            print(f"❌ {name} 执行失败: {e}")
    
    print(f"\n🎉 示例执行完成！成功: {success_count}/{len(examples)}")
    
    if success_count == len(examples):
        print("\n✅ 所有示例都执行成功！")
        print("🎯 您的Arxiv数据库已准备就绪，可以开始开发了！")
    
    # 显示使用建议
    print(f"""
📚 数据库使用建议:

1. 基础操作示例:
   - 插入论文: INSERT INTO arxiv_papers (arxiv_id, title, ...) VALUES (...)
   - 查询论文: SELECT * FROM arxiv_papers WHERE arxiv_id = '...'
   - 更新状态: UPDATE arxiv_papers SET processing_status = '...' WHERE ...
   - 删除论文: DELETE FROM arxiv_papers WHERE arxiv_id = '...'

2. 高级查询示例:
   - 全文搜索: WHERE title ILIKE '%keyword%' OR abstract ILIKE '%keyword%'
   - JSON查询: WHERE tags @> '["tag"]' 或 WHERE metadata->>'key' = 'value'
   - 分组统计: GROUP BY categories, COUNT(*), AVG(...)
   - 时间查询: WHERE created_at >= NOW() - INTERVAL '7 days'

3. 索引优化:
   - arxiv_id (唯一索引): 快速按ID查询
   - processing_status: 按状态筛选
   - categories: 按分类查询  
   - created_at: 时间排序
   - tags (JSONB): JSON标签查询

4. Redis缓存模式:
   - 键值缓存: SET/GET 热点数据
   - 集合操作: SADD/SISMEMBER 处理状态跟踪
   - 哈希缓存: HSET/HGET 结构化数据
   - 队列操作: LPUSH/RPOP 任务队列

5. 扩展建议:
   - 添加全文搜索索引 (PostgreSQL FTS)
   - 实现论文去重逻辑
   - 添加用户和权限管理
   - 集成机器学习推荐算法
   - 实现实时数据分析看板

🔗 相关文件:
   - 数据库配置: docker-compose.yml
   - 表结构: 已在PostgreSQL中创建
   - 使用示例: {__file__}
""")


if __name__ == "__main__":
    main()