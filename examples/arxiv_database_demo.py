#!/usr/bin/env python3
"""
Arxiv数据库操作完整示例
演示如何使用HomeSystem进行Arxiv论文的数据库操作
"""

import os
import sys
import json
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DB_PORT', '15432')
os.environ.setdefault('DB_NAME', 'homesystem')
os.environ.setdefault('DB_USER', 'homesystem')
os.environ.setdefault('DB_PASSWORD', 'homesystem123')
os.environ.setdefault('REDIS_HOST', 'localhost')
os.environ.setdefault('REDIS_PORT', '16379')


def demo_basic_operations():
    """基础数据库操作示例"""
    print("=" * 60)
    print("📊 基础数据库操作示例")
    print("=" * 60)
    
    try:
        # 动态导入（避免null bytes问题）
        import importlib.util
        
        # 导入数据库操作模块
        connection_spec = importlib.util.spec_from_file_location(
            "connection", 
            "HomeSystem/integrations/database/connection.py"
        )
        connection_module = importlib.util.module_from_spec(connection_spec)
        connection_spec.loader.exec_module(connection_module)
        
        models_spec = importlib.util.spec_from_file_location(
            "models", 
            "HomeSystem/integrations/database/models.py"
        )
        models_module = importlib.util.module_from_spec(models_spec)
        models_spec.loader.exec_module(models_module)
        
        operations_spec = importlib.util.spec_from_file_location(
            "operations", 
            "HomeSystem/integrations/database/operations.py"
        )
        operations_module = importlib.util.module_from_spec(operations_spec)
        operations_spec.loader.exec_module(operations_module)
        
        # 获取类
        DatabaseOperations = operations_module.DatabaseOperations
        CacheOperations = operations_module.CacheOperations
        ArxivPaperModel = models_module.ArxivPaperModel
        
        print("✅ 模块导入成功")
        
        # 创建操作实例
        db_ops = DatabaseOperations()
        cache_ops = CacheOperations()
        
        # 1. 创建示例论文记录
        print("\n🔬 创建示例论文记录:")
        papers_data = [
            {
                'arxiv_id': '2024.01001',
                'title': '深度学习在自然语言处理中的最新进展',
                'authors': 'Zhang Wei, Li Ming, Wang Hao',
                'abstract': '本文综述了深度学习技术在自然语言处理领域的最新发展，包括Transformer架构、预训练模型和多模态学习等关键技术。我们分析了这些技术的理论基础，探讨了它们在文本分类、机器翻译、问答系统等任务中的应用效果。',
                'categories': 'cs.CL, cs.LG, cs.AI',
                'published_date': '2024-01-15',
                'pdf_url': 'https://arxiv.org/pdf/2024.01001.pdf',
                'tags': ['深度学习', 'NLP', 'Transformer', '预训练模型'],
                'metadata': {
                    'conference': 'AAAI 2024',
                    'citation_count': 156,
                    'download_count': 2341
                }
            },
            {
                'arxiv_id': '2024.01002', 
                'title': '计算机视觉中的对抗样本攻击与防御机制研究',
                'authors': 'Chen Xiaoli, Liu Qiang, Yang Feng',
                'abstract': '对抗样本是深度学习模型面临的重要安全威胁。本研究系统分析了计算机视觉领域中的对抗攻击方法，包括FGSM、PGD、C&W等经典算法，并提出了一种基于梯度正则化的新型防御策略。',
                'categories': 'cs.CV, cs.CR, cs.LG',
                'published_date': '2024-01-20',
                'pdf_url': 'https://arxiv.org/pdf/2024.01002.pdf',
                'tags': ['计算机视觉', '对抗样本', '安全', '防御'],
                'metadata': {
                    'conference': 'CVPR 2024',
                    'citation_count': 89,
                    'download_count': 1456
                }
            },
            {
                'arxiv_id': '2024.01003',
                'title': '量子机器学习算法的理论分析与实现',
                'authors': 'Wang Quantum, Li Superposition, Zhang Entanglement',
                'abstract': '量子计算为机器学习带来了新的可能性。本文研究了量子支持向量机、量子神经网络等算法的理论基础，分析了量子优势的来源，并在量子模拟器上验证了算法的有效性。',
                'categories': 'quant-ph, cs.LG, cs.ET',
                'published_date': '2024-01-25',
                'pdf_url': 'https://arxiv.org/pdf/2024.01003.pdf',
                'tags': ['量子计算', '机器学习', '量子算法', '理论分析'],
                'metadata': {
                    'conference': 'Nature Quantum Information',
                    'citation_count': 234,
                    'download_count': 3421
                }
            }
        ]
        
        created_papers = []
        for paper_data in papers_data:
            paper = ArxivPaperModel(**paper_data)
            success = db_ops.create(paper)
            if success:
                created_papers.append(paper)
                print(f"  ✅ 已创建: {paper.title[:40]}...")
            else:
                print(f"  ⚠️  已存在: {paper.arxiv_id}")
        
        print(f"\n📊 成功创建 {len(created_papers)} 篇论文记录")
        
        # 2. 查询操作示例
        print("\n🔍 查询操作示例:")
        
        # 根据arxiv_id查询
        paper = db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', '2024.01001')
        if paper:
            print(f"  ✅ 按ID查询成功: {paper.title}")
            print(f"     作者: {paper.authors}")
            print(f"     类别: {paper.categories}")
            print(f"     状态: {paper.processing_status}")
        
        # 列出所有论文
        all_papers = db_ops.list_all(ArxivPaperModel, limit=10)
        print(f"  ✅ 数据库中共有 {len(all_papers)} 篇论文")
        
        # 统计操作
        total_count = db_ops.count(ArxivPaperModel)
        pending_count = db_ops.count(ArxivPaperModel, 'processing_status = %s', ('pending',))
        print(f"  📈 统计信息: 总数={total_count}, 待处理={pending_count}")
        
        # 3. 更新操作示例
        print("\n📝 更新操作示例:")
        if paper:
            # 更新论文状态
            db_ops.update(paper, {
                'processing_status': 'completed',
                'tags': paper.tags + ['已处理']
            })
            print(f"  ✅ 论文状态已更新: {paper.arxiv_id}")
            
            # 验证更新
            updated_paper = db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', paper.arxiv_id)
            if updated_paper:
                print(f"     新状态: {updated_paper.processing_status}")
                print(f"     新标签: {updated_paper.tags}")
        
        # 4. 缓存操作示例
        print("\n💾 缓存操作示例:")
        
        # 基础键值缓存
        cache_ops.set("demo:key", "示例缓存值", expire=300)
        cached_value = cache_ops.get("demo:key")
        print(f"  ✅ 基础缓存: {cached_value}")
        
        # 集合操作 - 已处理论文集合
        processed_ids = ['2024.01001', '2024.01002']
        cache_ops.sadd("processed_papers", *processed_ids)
        
        is_processed = cache_ops.sismember("processed_papers", "2024.01001")
        print(f"  ✅ 集合操作: 论文2024.01001已处理 = {is_processed}")
        
        # 模型对象缓存
        if all_papers:
            sample_paper = all_papers[0]
            cache_success = cache_ops.cache_model(sample_paper, expire=600)
            print(f"  ✅ 模型缓存: {cache_success}")
            
            # 从缓存读取模型
            cached_paper = cache_ops.get_cached_model(ArxivPaperModel, sample_paper.id)
            if cached_paper:
                print(f"  ✅ 缓存读取: {cached_paper.title[:30]}...")
        
        # 5. 批量操作示例
        print("\n🚀 批量操作示例:")
        
        # 创建更多示例论文用于批量操作
        batch_papers = []
        for i in range(3):
            paper = ArxivPaperModel(
                arxiv_id=f'batch.{2024}.{1000+i}',
                title=f'批量测试论文 #{i+1}: 人工智能在{["医疗", "金融", "教育"][i]}领域的应用',
                abstract=f'这是第{i+1}篇批量测试论文，探讨人工智能技术的实际应用...',
                categories='cs.AI, cs.LG',
                published_date=f'2024-02-{10+i:02d}',
                tags=['人工智能', '应用研究', '批量测试'],
                metadata={'batch_id': f'batch_{i+1}'}
            )
            batch_papers.append(paper)
        
        batch_count = db_ops.batch_create(batch_papers)
        print(f"  ✅ 批量创建: {batch_count}/{len(batch_papers)} 条记录")
        
        print("\n🎉 基础操作示例完成！")
        return True
        
    except Exception as e:
        print(f"❌ 基础操作示例失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def demo_advanced_queries():
    """高级查询示例"""
    print("\n" + "=" * 60)
    print("🔍 高级查询示例") 
    print("=" * 60)
    
    try:
        import psycopg2
        import psycopg2.extras
        
        # 直接连接数据库进行高级查询
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 15432)),
            database=os.getenv('DB_NAME', 'homesystem'),
            user=os.getenv('DB_USER', 'homesystem'),
            password=os.getenv('DB_PASSWORD', 'homesystem123')
        )
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 1. 按类别分组统计
        print("\n📊 按类别分组统计:")
        cursor.execute("""
            SELECT 
                categories,
                COUNT(*) as paper_count,
                AVG(CAST(metadata->>'citation_count' AS INTEGER)) as avg_citations
            FROM arxiv_papers 
            WHERE metadata->>'citation_count' IS NOT NULL
            GROUP BY categories 
            ORDER BY paper_count DESC
            LIMIT 5
        """)
        
        results = cursor.fetchall()
        for row in results:
            print(f"  📁 {row['categories']}: {row['paper_count']} 篇论文, 平均引用 {row['avg_citations']:.1f} 次")
        
        # 2. 根据标签搜索
        print("\n🏷️  根据标签搜索:")
        cursor.execute("""
            SELECT arxiv_id, title, tags
            FROM arxiv_papers 
            WHERE tags @> '["深度学习"]'
            LIMIT 3
        """)
        
        results = cursor.fetchall()
        for row in results:
            print(f"  🔖 {row['arxiv_id']}: {row['title'][:50]}...")
            print(f"     标签: {', '.join(row['tags'])}")
        
        # 3. 时间范围查询
        print("\n📅 时间范围查询 (最近7天):")
        cursor.execute("""
            SELECT arxiv_id, title, created_at, processing_status
            FROM arxiv_papers 
            WHERE created_at >= NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        results = cursor.fetchall()
        for row in results:
            print(f"  📄 {row['arxiv_id']}: {row['title'][:40]}...")
            print(f"     创建时间: {row['created_at']}, 状态: {row['processing_status']}")
        
        # 4. 复杂条件查询
        print("\n🔎 复杂条件查询 (高引用论文):")
        cursor.execute("""
            SELECT 
                arxiv_id, 
                title, 
                authors,
                CAST(metadata->>'citation_count' AS INTEGER) as citations,
                CAST(metadata->>'download_count' AS INTEGER) as downloads
            FROM arxiv_papers 
            WHERE 
                metadata->>'citation_count' IS NOT NULL 
                AND CAST(metadata->>'citation_count' AS INTEGER) > 100
            ORDER BY CAST(metadata->>'citation_count' AS INTEGER) DESC
            LIMIT 3
        """)
        
        results = cursor.fetchall()
        for row in results:
            print(f"  🌟 {row['arxiv_id']}: {row['title'][:40]}...")
            print(f"     作者: {row['authors']}")
            print(f"     引用: {row['citations']}, 下载: {row['downloads']}")
        
        # 5. 全文搜索示例
        print("\n🔍 全文搜索示例:")
        cursor.execute("""
            SELECT arxiv_id, title, abstract
            FROM arxiv_papers 
            WHERE 
                title ILIKE '%深度学习%' 
                OR abstract ILIKE '%深度学习%'
                OR title ILIKE '%机器学习%'
                OR abstract ILIKE '%机器学习%'
            LIMIT 3
        """)
        
        results = cursor.fetchall()
        for row in results:
            print(f"  📝 {row['arxiv_id']}: {row['title']}")
            print(f"     摘要: {row['abstract'][:80]}...")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 高级查询示例完成！")
        return True
        
    except Exception as e:
        print(f"❌ 高级查询示例失败: {e}")
        return False


def demo_arxiv_integration():
    """Arxiv集成使用示例"""  
    print("\n" + "=" * 60)
    print("🔬 Arxiv集成使用示例")
    print("=" * 60)
    
    try:
        # 由于可能的导入问题，这里展示基本的使用模式
        print("📋 Arxiv集成使用模式:")
        print("""
        # 1. 创建增强版Arxiv工具
        from HomeSystem.utility.arxiv import EnhancedArxivTool
        
        arxiv_tool = EnhancedArxivTool(enable_database=True)
        
        # 2. 搜索并自动保存到数据库
        results = arxiv_tool.arxivSearch("machine learning", num_results=10)
        
        # 3. 跳过已处理的论文
        new_results = arxiv_tool.arxivSearch(
            "deep learning", 
            num_results=20,
            skip_processed=True
        )
        
        # 4. 处理论文并自动更新状态
        def process_paper(paper_data):
            # 您的处理逻辑
            return f"已处理: {paper_data.title}"
            
        for paper in results.results:
            result = arxiv_tool.process_paper(paper, process_paper)
            print(result)
        
        # 5. 获取统计信息
        stats = arxiv_tool.get_processing_statistics()
        print(f"总论文数: {stats['total']}")
        print(f"已完成: {stats['completed']}")
        
        # 6. 获取未处理的论文
        unprocessed = arxiv_tool.get_unprocessed_papers(limit=10)
        """)
        
        print("✅ Arxiv集成使用模式展示完成")
        return True
        
    except Exception as e:
        print(f"❌ Arxiv集成示例失败: {e}")
        return False


def demo_performance_tips():
    """性能优化提示"""
    print("\n" + "=" * 60)
    print("⚡ 性能优化提示")
    print("=" * 60)
    
    print("""
🚀 数据库性能优化建议:

1. 索引优化
   - arxiv_id: 主要查询字段，已创建唯一索引
   - processing_status: 状态查询，已创建索引
   - categories: 分类查询，已创建索引
   - created_at: 时间排序，已创建索引

2. 批量操作
   - 使用 batch_create() 进行批量插入
   - 避免频繁的单条记录操作
   - 合理使用事务

3. 缓存策略
   - 热点数据缓存到Redis
   - 查询结果缓存，减少数据库压力
   - 使用集合操作跟踪处理状态

4. 查询优化
   - 使用LIMIT限制结果集大小
   - 合理使用WHERE条件过滤
   - 避免SELECT *，只查询需要的字段

5. 连接管理
   - 使用连接池复用连接
   - 及时关闭游标和连接
   - 监控连接数量

6. JSON字段优化
   - 使用JSONB而非JSON (已使用)
   - 为常用JSON查询创建表达式索引
   - 避免复杂的JSON查询

💡 监控建议:
   - 定期检查数据库大小和增长率
   - 监控慢查询日志
   - 跟踪连接数和活跃查询
   - 设置合适的缓存过期时间
""")
    
    return True


def main():
    """主函数"""
    print("🎯 Arxiv数据库操作完整示例")
    print("🗄️  数据库: PostgreSQL + Redis")
    print("📊 功能: 论文管理、查询、缓存、统计")
    
    # 检查数据库连接
    print(f"\n🔧 数据库配置:")
    print(f"   PostgreSQL: {os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}")
    print(f"   Redis: {os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}")
    
    # 运行示例
    examples = [
        ("基础数据库操作", demo_basic_operations),
        ("高级查询示例", demo_advanced_queries), 
        ("Arxiv集成使用", demo_arxiv_integration),
        ("性能优化提示", demo_performance_tips),
    ]
    
    success_count = 0
    for name, func in examples:
        try:
            print(f"\n{'='*20} {name} {'='*20}")
            if func():
                success_count += 1
        except Exception as e:
            print(f"❌ {name} 执行失败: {e}")
    
    print(f"\n🎉 示例执行完成！成功: {success_count}/{len(examples)}")
    
    if success_count == len(examples):
        print("\n✅ 所有示例都执行成功！")
        print("🎯 您的Arxiv数据库已准备就绪，可以开始开发了！")
    else:
        print("\n⚠️  部分示例执行失败，请检查数据库连接和配置")
    
    print(f"""
📚 后续开发建议:

1. 基础操作
   - 使用 DatabaseOperations 类进行CRUD操作
   - 使用 CacheOperations 类进行缓存管理
   - 使用 ArxivPaperModel 类作为数据模型

2. 高级功能  
   - 集成 EnhancedArxivTool 实现自动化论文管理
   - 实现论文处理工作流
   - 添加全文搜索和智能推荐

3. 性能优化
   - 合理使用索引和缓存
   - 监控数据库性能
   - 优化查询语句

4. 扩展功能
   - 添加用户管理和权限控制
   - 实现论文分析和可视化
   - 集成机器学习模型

🔗 相关文件:
   - 模型定义: HomeSystem/integrations/database/models.py  
   - 数据库操作: HomeSystem/integrations/database/operations.py
   - Arxiv集成: HomeSystem/utility/arxiv/database_integration.py
   - 使用示例: examples/database_usage_example.py
""")


if __name__ == "__main__":
    main()