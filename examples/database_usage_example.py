#!/usr/bin/env python3
"""
Home System 数据库集成使用示例

演示如何使用数据库集成功能进行ArXiv论文管理
"""

import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def example_basic_database_operations():
    """基础数据库操作示例"""
    print("📊 基础数据库操作示例")
    print("-" * 50)
    
    from HomeSystem.integrations.database import DatabaseOperations, ArxivPaperModel
    
    # 创建数据库操作实例
    db_ops = DatabaseOperations()
    
    # 初始化表结构
    arxiv_model = ArxivPaperModel()
    success = db_ops.init_tables([arxiv_model])
    print(f"表结构初始化: {'✅' if success else '❌'}")
    
    # 创建示例论文
    paper = ArxivPaperModel(
        arxiv_id="2024.01001",
        title="示例论文：深度学习在自然语言处理中的应用",
        abstract="这是一篇关于深度学习在NLP领域应用的示例论文...",
        categories="cs.CL, cs.LG",
        published_date="2024年01月",
        tags=["深度学习", "NLP"],
        metadata={"conference": "示例会议"}
    )
    
    # 保存论文
    if db_ops.create(paper):
        print(f"✅ 论文已保存: {paper.title}")
    else:
        print("⚠️  论文已存在或保存失败")
    
    # 查询论文
    retrieved = db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', '2024.01001')
    if retrieved:
        print(f"✅ 查询成功: {retrieved.title}")
        print(f"   状态: {retrieved.processing_status}")
        print(f"   标签: {', '.join(retrieved.tags)}")
    
    # 更新论文状态
    if retrieved:
        db_ops.update(retrieved, {'processing_status': 'completed'})
        print("✅ 论文状态已更新为已完成")
    
    return True

def example_cache_operations():
    """缓存操作示例"""
    print("\n💾 缓存操作示例")
    print("-" * 50)
    
    from HomeSystem.integrations.database import CacheOperations, ArxivPaperModel
    
    cache_ops = CacheOperations()
    
    # 基础键值缓存
    cache_ops.set("example_key", "示例值", expire=300)
    value = cache_ops.get("example_key")
    print(f"缓存操作: {'✅' if value == '示例值' else '❌'}")
    
    # 集合操作 - 已处理论文集合
    cache_ops.sadd("processed_papers", "2024.01001", "2024.01002")
    is_processed = cache_ops.sismember("processed_papers", "2024.01001")
    print(f"集合操作: {'✅' if is_processed else '❌'}")
    
    # 模型缓存
    paper = ArxivPaperModel(
        arxiv_id="cache.test",
        title="缓存测试论文",
        abstract="用于测试缓存功能的论文"
    )
    
    success = cache_ops.cache_model(paper, expire=600)
    print(f"模型缓存: {'✅' if success else '❌'}")
    
    cached_paper = cache_ops.get_cached_model(ArxivPaperModel, paper.id)
    print(f"模型读取: {'✅' if cached_paper and cached_paper.title == paper.title else '❌'}")
    
    return True

def example_arxiv_integration():
    """ArXiv集成示例"""
    print("\n🔬 ArXiv集成使用示例")
    print("-" * 50)
    
    try:
        from HomeSystem.utility.arxiv import EnhancedArxivTool
        
        # 创建增强版ArXiv工具（启用数据库）
        arxiv_tool = EnhancedArxivTool(enable_database=True)
        print("✅ 增强版ArXiv工具已创建")
        
        # 搜索论文（自动保存到数据库）
        print("🔍 搜索论文: 'machine learning'...")
        results = arxiv_tool.arxivSearch("machine learning", num_results=5)
        
        if results.num_results > 0:
            print(f"✅ 找到 {results.num_results} 篇论文")
            
            # 显示第一篇论文
            first_paper = results.results[0]
            print(f"   示例论文: {first_paper.title[:60]}...")
            print(f"   ArXiv ID: {first_paper.arxiv_id}")
            print(f"   发布时间: {first_paper.published_date}")
            
            # 演示去重搜索
            print("\n🔍 搜索相同关键词（跳过已处理）...")
            filtered_results = arxiv_tool.arxivSearch(
                "machine learning", 
                num_results=5, 
                skip_processed=True
            )
            print(f"✅ 过滤后剩余 {filtered_results.num_results} 篇新论文")
            
            # 演示论文处理
            def sample_processor(paper):
                """示例处理函数"""
                print(f"   正在处理: {paper.title[:40]}...")
                # 这里可以添加实际的处理逻辑，如下载PDF、提取信息等
                return f"已处理论文: {paper.arxiv_id}"
            
            if results.results:
                paper_to_process = results.results[0]
                result = arxiv_tool.process_paper(paper_to_process, sample_processor)
                print(f"✅ {result}")
            
            # 获取统计信息
            stats = arxiv_tool.get_processing_statistics()
            print(f"\n📊 数据库统计:")
            print(f"   总论文数: {stats.get('total', 0)}")
            print(f"   待处理: {stats.get('pending', 0)}")
            print(f"   已完成: {stats.get('completed', 0)}")
            print(f"   失败: {stats.get('failed', 0)}")
            
        return True
        
    except ImportError as e:
        print(f"⚠️  ArXiv集成不可用: {e}")
        return False
    except Exception as e:
        print(f"❌ ArXiv集成示例失败: {e}")
        return False

def example_advanced_usage():
    """高级用法示例"""
    print("\n🚀 高级用法示例")
    print("-" * 50)
    
    try:
        from HomeSystem.utility.arxiv.database_integration import ArxivDatabaseManager
        
        # 直接使用数据库管理器
        db_manager = ArxivDatabaseManager()
        
        # 获取未处理的论文
        unprocessed = db_manager.get_unprocessed_papers(limit=3)
        print(f"✅ 找到 {len(unprocessed)} 篇待处理论文")
        
        for paper in unprocessed[:2]:  # 只显示前2篇
            print(f"   - {paper.title[:50]}... ({paper.arxiv_id})")
        
        # 批量标记为已处理
        for paper in unprocessed[:1]:  # 只处理第一篇
            success = db_manager.mark_processed(paper.arxiv_id, 'completed')
            if success:
                print(f"✅ 已标记论文为已处理: {paper.arxiv_id}")
        
        # 获取按状态分组的论文
        completed_papers = db_manager.get_papers_by_status('completed', limit=3)
        print(f"✅ 已完成的论文: {len(completed_papers)} 篇")
        
        return True
        
    except Exception as e:
        print(f"❌ 高级用法示例失败: {e}")
        return False

def main():
    """主函数"""
    print("🎯 Home System 数据库集成使用示例")
    print("=" * 60)
    
    # 加载环境变量
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ 环境变量已加载")
    except ImportError:
        print("⚠️  python-dotenv 未安装")
    
    # 运行示例
    examples = [
        ("基础数据库操作", example_basic_database_operations),
        ("缓存操作", example_cache_operations),
        ("ArXiv集成", example_arxiv_integration),
        ("高级用法", example_advanced_usage),
    ]
    
    for name, func in examples:
        try:
            print(f"\n{'='*20} {name} {'='*20}")
            success = func()
            if not success:
                print(f"⚠️  {name} 示例未完全成功")
        except Exception as e:
            print(f"❌ {name} 示例执行失败: {e}")
        
        print()  # 添加空行分隔
    
    print("🎉 所有示例执行完成！")
    print("\n💡 提示:")
    print("- 使用 docker-compose up -d 启动数据库服务")
    print("- 查看 docs/database-integration-guide.md 了解详细用法")
    print("- 运行 python quick_test.py 快速测试连接")

if __name__ == "__main__":
    main()