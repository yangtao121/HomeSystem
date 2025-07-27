#!/usr/bin/env python3
"""
ArXiv API 结构化显示功能演示
演示如何使用新的结构化显示功能来美观地展示搜索结果
"""

from HomeSystem.utility.arxiv.arxiv import ArxivTool

def main():
    """主演示函数"""
    print("🚀 ArXiv API 结构化显示功能演示")
    print("=" * 60)
    
    # 创建工具实例
    arxiv = ArxivTool()
    
    # 1. 基础搜索演示
    print("\n🔍 演示1: 基础搜索 - 机器学习")
    results = arxiv.arxivSearch("machine learning", num_results=8)
    
    if results.num_results > 0:
        print(f"✅ 找到 {results.num_results} 篇论文")
        
        # 完整显示前3个结果
        print("\n📋 完整显示前3个结果:")
        results.display_results(display_range="limited", max_display=3)
        
        print("\n" + "="*60 + "\n")
        
        # 简洁显示模式
        print("📋 简洁显示模式 (前5个):")
        results.display_brief(max_display=5)
        
        print("\n" + "="*60 + "\n")
        
        # 仅显示标题
        print("📋 仅标题模式:")
        results.display_titles_only(max_display=8)
        
    else:
        print("❌ 未找到结果")
    
    # 2. 年份筛选演示
    print("\n\n🔍 演示2: 年份筛选功能")
    latest_results = arxiv.getLatestPapersDirectly("deep learning", num_results=15)
    
    if latest_results.num_results > 0:
        print(f"✅ 获取到 {latest_results.num_results} 篇最新论文")
        
        # 筛选2020年后的论文
        recent_papers = latest_results.get_papers_by_date_range(start_year=2020)
        
        if recent_papers.num_results > 0:
            print(f"\n📋 筛选出 {recent_papers.num_results} 篇2020年后的论文:")
            recent_papers.display_brief(max_display=4)
        else:
            print("\n⚠️ 未找到2020年后的论文")
    
    # 3. 小数据集完整显示演示
    print("\n\n🔍 演示3: 小数据集完整显示")
    small_results = arxiv.arxivSearch("quantum computing", num_results=3)
    
    if small_results.num_results > 0:
        print("📋 显示全部结果并包含统计信息:")
        small_results.display_results(display_range="all", show_summary=True)
    
    print("\n" + "="*60)
    print("🎉 演示完成！")
    print("\n📖 可用的显示方法:")
    print("   • display_results()      - 完整结构化显示")
    print("   • display_brief()        - 简洁显示")
    print("   • display_titles_only()  - 仅显示标题")
    print("   • get_papers_by_date_range() - 年份筛选")

if __name__ == "__main__":
    main()