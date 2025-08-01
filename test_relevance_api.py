#!/usr/bin/env python3
"""
测试相关度评分API功能
"""
import sys
import os
import json

# 更改到正确的目录
os.chdir('/mnt/nfs_share/code/homesystem/Web/ExplorePaperData')
sys.path.append('/mnt/nfs_share/code/homesystem/Web/ExplorePaperData')

from database import PaperService
from app import app

def test_database_connection():
    """测试数据库连接和查询功能"""
    print("=== 测试数据库连接 ===")
    try:
        paper_service = PaperService()
        
        # 测试获取论文列表
        papers, total = paper_service.search_papers(page=1, per_page=5)
        print(f"✅ 成功获取论文列表: {total} 篇论文")
        
        if papers:
            paper = papers[0]
            print(f"测试论文: {paper['arxiv_id']} - {paper['title'][:50]}...")
            
            # 检查相关度字段是否存在
            relevance_score = paper.get('full_paper_relevance_score')
            relevance_justification = paper.get('full_paper_relevance_justification')
            
            print(f"当前相关度评分: {relevance_score}")
            print(f"当前相关度理由: {relevance_justification[:100] if relevance_justification else 'None'}...")
            
            return paper['arxiv_id']
        else:
            print("❌ 没有找到论文数据")
            return None
            
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return None

def test_update_relevance(arxiv_id):
    """测试相关度更新功能"""
    print(f"\n=== 测试相关度更新功能 ===")
    try:        
        paper_service = PaperService()
        
        # 测试更新相关度
        test_score = 0.85
        test_justification = "这是一个测试的相关度理由，用于验证API功能是否正常工作。"
        
        print(f"更新论文 {arxiv_id} 的相关度...")
        print(f"评分: {test_score}")
        print(f"理由: {test_justification}")
        
        success = paper_service.update_paper_relevance(
            arxiv_id=arxiv_id,
            relevance_score=test_score,
            relevance_justification=test_justification
        )
        
        if success:
            print("✅ 相关度更新成功!")
            
            # 验证更新结果
            paper = paper_service.get_paper_detail(arxiv_id)
            if paper:
                updated_score = paper.get('full_paper_relevance_score')
                updated_justification = paper.get('full_paper_relevance_justification')
                
                print(f"验证结果:")
                print(f"  评分: {updated_score} (期望: {test_score})")
                print(f"  理由: {updated_justification[:100]}...")
                
                if abs(float(updated_score) - test_score) < 0.001 and test_justification in updated_justification:
                    print("✅ 数据验证成功!")
                    return True
                else:
                    print("❌ 数据验证失败!")
                    return False
            else:
                print("❌ 无法获取更新后的论文详情")
                return False
        else:
            print("❌ 相关度更新失败!")
            return False
            
    except Exception as e:
        print(f"❌ 测试更新功能失败: {e}")
        return False

def test_template_filters():
    """测试模板过滤器功能"""
    print(f"\n=== 测试模板过滤器功能 ===")
    try:
        with app.app_context():
            # 测试评分显示过滤器
            from app import relevance_score_display, relevance_score_stars
            
            test_scores = [None, 0.0, 0.3, 0.5, 0.7, 0.9, 1.0]
            
            print("评分显示测试:")
            for score in test_scores:
                display = relevance_score_display(score)
                stars = relevance_score_stars(score)
                print(f"  评分 {score}: {display} | {stars}")
            
            # 测试理由显示过滤器
            from app import relevance_justification_display
            
            test_justifications = [None, "", "   ", "这是一个测试理由"]
            
            print("\n理由显示测试:")
            for justification in test_justifications:
                display = relevance_justification_display(justification)
                print(f"  理由 '{justification}': '{display}'")
            
            print("✅ 模板过滤器测试完成!")
            return True
            
    except Exception as e:
        print(f"❌ 模板过滤器测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试相关度评分功能...")
    
    # 测试数据库连接
    test_arxiv_id = test_database_connection()
    if not test_arxiv_id:
        print("❌ 数据库连接测试失败，退出测试")
        return False
    
    # 测试相关度更新
    update_success = test_update_relevance(test_arxiv_id)
    if not update_success:
        print("❌ 相关度更新测试失败")
    
    # 测试模板过滤器
    filter_success = test_template_filters()
    if not filter_success:
        print("❌ 模板过滤器测试失败")
    
    # 总结测试结果
    print(f"\n=== 测试总结 ===")
    print(f"数据库连接: ✅")
    print(f"相关度更新: {'✅' if update_success else '❌'}")
    print(f"模板过滤器: {'✅' if filter_success else '❌'}")
    
    if update_success and filter_success:
        print("🎉 所有测试通过！相关度评分功能已成功集成！")
        return True
    else:
        print("⚠️  部分测试失败，请检查相应功能")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)