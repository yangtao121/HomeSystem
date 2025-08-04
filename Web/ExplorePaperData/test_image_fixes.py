#!/usr/bin/env python3
"""
测试图片路径修复的验证脚本
用于验证图片路径问题的修复是否生效
"""
import os
import sys
import re
import requests
import logging
from typing import List, Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from database import PaperService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImageFixTester:
    """图片修复测试工具"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        """
        初始化测试工具
        
        Args:
            base_url: Web应用的基础URL
        """
        self.base_url = base_url
        self.paper_service = PaperService()
        logger.info(f"Image fix tester initialized with base URL: {base_url}")
    
    def test_app_is_running(self) -> bool:
        """
        测试Web应用是否运行
        
        Returns:
            bool: 应用是否运行
        """
        try:
            response = requests.get(self.base_url, timeout=5)
            if response.status_code == 200:
                logger.info("✅ Web application is running")
                return True
            else:
                logger.error(f"❌ Web application returned status code: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Cannot connect to web application: {e}")
            return False
    
    def get_test_paper_with_images(self) -> Dict[str, Any]:
        """
        获取包含图片的测试论文
        
        Returns:
            Dict: 测试论文信息，如果没找到则为None
        """
        try:
            # 先检查指定的论文
            test_arxiv_id = "2508.00795"
            paper = self.paper_service.get_paper_detail(test_arxiv_id)
            
            if paper and self._has_image_references(paper.get('deep_analysis_result', '')):
                logger.info(f"✅ Found test paper with images: {test_arxiv_id}")
                return paper
            
            # 如果指定论文没有图片，寻找其他有图片的论文
            logger.info("Searching for papers with image references...")
            papers_with_analysis = self._get_papers_with_analysis()
            
            for paper_data in papers_with_analysis:
                arxiv_id, content = paper_data
                if self._has_image_references(content):
                    paper = self.paper_service.get_paper_detail(arxiv_id)
                    if paper:
                        logger.info(f"✅ Found alternative test paper with images: {arxiv_id}")
                        return paper
            
            logger.warning("❌ No papers with image references found")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get test paper: {e}")
            return None
    
    def _get_papers_with_analysis(self) -> List[tuple]:
        """获取所有包含深度分析结果的论文"""
        try:
            with self.paper_service.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT arxiv_id, deep_analysis_result 
                    FROM arxiv_papers 
                    WHERE deep_analysis_result IS NOT NULL 
                      AND deep_analysis_result != ''
                      AND deep_analysis_status = 'completed'
                    LIMIT 10
                """)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch papers: {e}")
            return []
    
    def _has_image_references(self, content: str) -> bool:
        """检查内容是否包含图片引用"""
        if not content:
            return False
        # 检查任何形式的图片引用
        img_patterns = [
            r'!\[([^\]]*)\]\((imgs/[^)]+)\)',  # 旧格式
            r'!\[([^\]]*)\]\((/paper/[^)]+/analysis_images/[^)]+)\)',  # 新格式
        ]
        for pattern in img_patterns:
            if re.search(pattern, content):
                return True
        return False
    
    def extract_image_urls(self, content: str, arxiv_id: str) -> List[str]:
        """
        从内容中提取图片URL
        
        Args:
            content: Markdown内容
            arxiv_id: ArXiv论文ID
            
        Returns:
            List[str]: 图片URL列表
        """
        urls = []
        
        # 匹配新格式的图片URL
        new_pattern = r'!\[([^\]]*)\]\((/paper/[^)]+/analysis_images/[^)]+)\)'
        new_matches = re.findall(new_pattern, content)
        urls.extend([match[1] for match in new_matches])
        
        # 匹配旧格式的图片路径（如果存在）
        old_pattern = r'!\[([^\]]*)\]\((imgs/[^)]+)\)'
        old_matches = re.findall(old_pattern, content)
        for alt_text, relative_path in old_matches:
            # 转换为测试URL
            filename = relative_path.replace('imgs/', '')
            url = f"/paper/{arxiv_id}/imgs/{filename}"  # 测试fallback路由
            urls.append(url)
        
        return urls
    
    def test_image_urls(self, urls: List[str]) -> Dict[str, Any]:
        """
        测试图片URL的可访问性
        
        Args:
            urls: 图片URL列表
            
        Returns:
            Dict: 测试结果
        """
        results = {
            'total_urls': len(urls),
            'successful': 0,
            'failed': 0,
            'redirected': 0,
            'details': []
        }
        
        for url in urls:
            try:
                full_url = f"{self.base_url}{url}"
                response = requests.get(full_url, timeout=10, allow_redirects=True)
                
                detail = {
                    'url': url,
                    'status_code': response.status_code,
                    'redirected': len(response.history) > 0,
                    'final_url': response.url if response.url != full_url else None,
                    'content_type': response.headers.get('content-type', ''),
                    'content_length': len(response.content) if response.content else 0
                }
                
                if response.status_code == 200:
                    results['successful'] += 1
                    logger.info(f"✅ Image accessible: {url}")
                    if detail['redirected']:
                        results['redirected'] += 1
                        logger.info(f"  🔄 Redirected to: {detail['final_url']}")
                else:
                    results['failed'] += 1
                    logger.error(f"❌ Image failed: {url} (Status: {response.status_code})")
                
                results['details'].append(detail)
                
            except Exception as e:
                results['failed'] += 1
                detail = {
                    'url': url,
                    'error': str(e)
                }
                results['details'].append(detail)
                logger.error(f"❌ Image request failed: {url} - {e}")
        
        return results
    
    def test_database_content(self, arxiv_id: str) -> Dict[str, Any]:
        """
        测试数据库中的内容是否已经修复
        
        Args:
            arxiv_id: ArXiv论文ID
            
        Returns:
            Dict: 内容分析结果
        """
        try:
            paper = self.paper_service.get_paper_detail(arxiv_id)
            if not paper:
                return {'error': 'Paper not found'}
            
            content = paper.get('deep_analysis_result', '')
            if not content:
                return {'error': 'No analysis content found'}
            
            # 分析图片路径
            old_pattern = r'!\[([^\]]*)\]\((imgs/[^)]+)\)'
            new_pattern = r'!\[([^\]]*)\]\((/paper/[^)]+/analysis_images/[^)]+)\)'
            
            old_matches = re.findall(old_pattern, content)
            new_matches = re.findall(new_pattern, content)
            
            result = {
                'arxiv_id': arxiv_id,
                'content_length': len(content),
                'old_format_images': len(old_matches),
                'new_format_images': len(new_matches),
                'total_images': len(old_matches) + len(new_matches),
                'needs_migration': len(old_matches) > 0,
                'sample_old_paths': [match[1] for match in old_matches[:3]],
                'sample_new_paths': [match[1] for match in new_matches[:3]]
            }
            
            logger.info(f"📊 Database content analysis for {arxiv_id}:")
            logger.info(f"  - Total images: {result['total_images']}")
            logger.info(f"  - Old format: {result['old_format_images']}")
            logger.info(f"  - New format: {result['new_format_images']}")
            logger.info(f"  - Needs migration: {result['needs_migration']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze database content: {e}")
            return {'error': str(e)}
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """
        运行综合测试
        
        Returns:
            Dict: 完整的测试结果
        """
        logger.info("🧪 Starting comprehensive image fix test")
        
        test_results = {
            'app_running': False,
            'test_paper_found': False,
            'database_analysis': None,
            'image_url_tests': None,
            'summary': {}
        }
        
        try:
            # 1. 测试应用是否运行
            test_results['app_running'] = self.test_app_is_running()
            if not test_results['app_running']:
                logger.error("❌ Cannot proceed without running web application")
                return test_results
            
            # 2. 获取测试论文
            test_paper = self.get_test_paper_with_images()
            test_results['test_paper_found'] = test_paper is not None
            
            if not test_paper:
                logger.error("❌ Cannot proceed without test paper")
                return test_results
            
            arxiv_id = test_paper['arxiv_id']
            logger.info(f"🎯 Using test paper: {arxiv_id}")
            
            # 3. 分析数据库内容
            test_results['database_analysis'] = self.test_database_content(arxiv_id)
            
            # 4. 测试图片URL
            content = test_paper.get('deep_analysis_result', '')
            image_urls = self.extract_image_urls(content, arxiv_id)
            
            if image_urls:
                logger.info(f"🔍 Testing {len(image_urls)} image URLs")
                test_results['image_url_tests'] = self.test_image_urls(image_urls[:5])  # 只测试前5个
            else:
                logger.warning("⚠️ No image URLs found to test")
                test_results['image_url_tests'] = {'total_urls': 0}
            
            # 5. 生成摘要
            test_results['summary'] = self._generate_summary(test_results)
            
            return test_results
            
        except Exception as e:
            logger.error(f"❌ Comprehensive test failed: {e}")
            test_results['error'] = str(e)
            return test_results
    
    def _generate_summary(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """生成测试摘要"""
        summary = {
            'overall_status': 'unknown',
            'issues_found': [],
            'fixes_working': [],
            'recommendations': []
        }
        
        try:
            # 检查应用状态
            if not test_results['app_running']:
                summary['issues_found'].append("Web application not accessible")
                summary['overall_status'] = 'failed'
                return summary
            
            # 检查数据库内容
            db_analysis = test_results.get('database_analysis', {})
            if db_analysis and not db_analysis.get('error'):
                if db_analysis.get('needs_migration', False):
                    summary['issues_found'].append(f"Database still contains {db_analysis['old_format_images']} old format images")
                    summary['recommendations'].append("Run database migration script")
                else:
                    summary['fixes_working'].append("Database content uses correct image paths")
            
            # 检查URL测试
            url_tests = test_results.get('image_url_tests', {})
            if url_tests and url_tests.get('total_urls', 0) > 0:
                success_rate = url_tests['successful'] / url_tests['total_urls']
                if success_rate >= 0.8:
                    summary['fixes_working'].append(f"Image URLs accessible ({url_tests['successful']}/{url_tests['total_urls']})")
                else:
                    summary['issues_found'].append(f"Low image accessibility rate ({url_tests['successful']}/{url_tests['total_urls']})")
                
                if url_tests.get('redirected', 0) > 0:
                    summary['fixes_working'].append(f"Fallback redirects working ({url_tests['redirected']} redirected)")
            
            # 确定总体状态
            if not summary['issues_found']:
                summary['overall_status'] = 'passed'
            elif summary['fixes_working']:
                summary['overall_status'] = 'partially_fixed'
            else:
                summary['overall_status'] = 'failed'
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            summary['error'] = str(e)
            return summary

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test image path fixes')
    parser.add_argument('--url', default='http://localhost:5000',
                       help='Base URL of the web application')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # 运行测试
        tester = ImageFixTester(base_url=args.url)
        results = tester.run_comprehensive_test()
        
        # 输出结果
        print("\n" + "="*60)
        print("IMAGE FIX TEST RESULTS")
        print("="*60)
        
        summary = results.get('summary', {})
        overall_status = summary.get('overall_status', 'unknown')
        
        print(f"Overall Status: {overall_status.upper()}")
        print(f"App Running: {'✅' if results.get('app_running') else '❌'}")
        print(f"Test Paper Found: {'✅' if results.get('test_paper_found') else '❌'}")
        
        # 数据库分析
        db_analysis = results.get('database_analysis', {})
        if db_analysis and not db_analysis.get('error'):
            print(f"Database Images - Old Format: {db_analysis.get('old_format_images', 0)}")
            print(f"Database Images - New Format: {db_analysis.get('new_format_images', 0)}")
            print(f"Migration Needed: {'Yes' if db_analysis.get('needs_migration') else 'No'}")
        
        # URL测试
        url_tests = results.get('image_url_tests', {})
        if url_tests and url_tests.get('total_urls', 0) > 0:
            print(f"Image URLs Tested: {url_tests['total_urls']}")
            print(f"Successful: {url_tests['successful']}")
            print(f"Failed: {url_tests['failed']}")
            print(f"Redirected: {url_tests['redirected']}")
        
        # 问题和修复
        if summary.get('issues_found'):
            print("\nIssues Found:")
            for issue in summary['issues_found']:
                print(f"  ❌ {issue}")
        
        if summary.get('fixes_working'):
            print("\nFixes Working:")
            for fix in summary['fixes_working']:
                print(f"  ✅ {fix}")
        
        if summary.get('recommendations'):
            print("\nRecommendations:")
            for rec in summary['recommendations']:
                print(f"  💡 {rec}")
        
        print("="*60)
        
        # 返回适当的退出码
        if overall_status == 'passed':
            sys.exit(0)
        elif overall_status == 'partially_fixed':
            sys.exit(1)
        else:
            sys.exit(2)
        
    except Exception as e:
        logger.error(f"Test script failed: {e}")
        sys.exit(3)

if __name__ == "__main__":
    main()