#!/usr/bin/env python3
"""
数据库图片路径迁移脚本
将深度分析结果中的旧图片路径从 imgs/ 格式转换为 /paper/{arxiv_id}/analysis_images/ 格式
"""
import os
import sys
import re
import logging
from typing import List, Tuple

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from database import DatabaseManager
from config import Config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImagePathMigrator:
    """图片路径迁移工具"""
    
    def __init__(self):
        """初始化迁移工具"""
        self.db_manager = DatabaseManager()
        logger.info("Image path migrator initialized")
    
    def get_papers_with_analysis(self) -> List[Tuple[str, str]]:
        """
        获取所有包含深度分析结果的论文
        
        Returns:
            List[Tuple[str, str]]: 论文ID和分析内容的列表
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT arxiv_id, deep_analysis_result 
                    FROM arxiv_papers 
                    WHERE deep_analysis_result IS NOT NULL 
                      AND deep_analysis_result != ''
                      AND deep_analysis_status = 'completed'
                    ORDER BY arxiv_id
                """)
                
                results = cursor.fetchall()
                logger.info(f"Found {len(results)} papers with deep analysis results")
                return results
                
        except Exception as e:
            logger.error(f"Failed to fetch papers with analysis: {e}")
            return []
    
    def needs_migration(self, content: str) -> bool:
        """
        检查内容是否需要迁移
        
        Args:
            content: 分析内容
            
        Returns:
            bool: 是否需要迁移
        """
        # 检查是否包含旧的 imgs/ 路径
        old_pattern = r'!\[([^\]]*)\]\((imgs/[^)]+)\)'
        return bool(re.search(old_pattern, content))
    
    def migrate_image_paths(self, content: str, arxiv_id: str) -> str:
        """
        迁移图片路径
        
        Args:
            content: 原始内容
            arxiv_id: ArXiv论文ID
            
        Returns:
            str: 迁移后的内容
        """
        try:
            # 使用正则表达式匹配并替换图片路径
            # 匹配 ![alt](imgs/filename) 格式
            img_pattern = r'!\[([^\]]*)\]\((imgs/[^)]+)\)'
            
            def replace_image_path(match):
                alt_text = match.group(1)
                relative_path = match.group(2)
                # 转换为Flask可访问的URL路径
                new_path = f"/paper/{arxiv_id}/analysis_images/{relative_path.replace('imgs/', '')}"
                return f"![{alt_text}]({new_path})"
            
            # 记录迁移信息
            original_matches = re.findall(img_pattern, content)
            logger.debug(f"Found {len(original_matches)} image references to migrate for {arxiv_id}")
            
            # 执行替换
            migrated_content = re.sub(img_pattern, replace_image_path, content)
            
            # 验证迁移结果
            migrated_matches = re.findall(r'!\[([^\]]*)\]\((/paper/[^)]+)\)', migrated_content)
            logger.debug(f"Migrated {len(migrated_matches)} image paths for {arxiv_id}")
            
            return migrated_content
            
        except Exception as e:
            logger.error(f"Failed to migrate image paths for {arxiv_id}: {e}")
            return content
    
    def update_paper_analysis(self, arxiv_id: str, new_content: str) -> bool:
        """
        更新论文的深度分析结果
        
        Args:
            arxiv_id: ArXiv论文ID
            new_content: 新的分析内容
            
        Returns:
            bool: 更新是否成功
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE arxiv_papers 
                    SET deep_analysis_result = %s,
                        deep_analysis_updated_at = CURRENT_TIMESTAMP
                    WHERE arxiv_id = %s
                """, (new_content, arxiv_id))
                
                success = cursor.rowcount > 0
                conn.commit()
                
                if success:
                    logger.info(f"Updated analysis result for {arxiv_id}")
                else:
                    logger.warning(f"No rows updated for {arxiv_id}")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to update analysis result for {arxiv_id}: {e}")
            return False
    
    def run_migration(self, dry_run: bool = True) -> dict:
        """
        运行迁移
        
        Args:
            dry_run: 是否为模拟运行（不实际修改数据库）
            
        Returns:
            dict: 迁移结果统计
        """
        logger.info(f"Starting image path migration (dry_run={dry_run})")
        
        # 统计信息
        stats = {
            'total_papers': 0,
            'papers_needing_migration': 0,
            'papers_migrated': 0,
            'papers_failed': 0,
            'total_images_migrated': 0
        }
        
        try:
            # 获取所有包含分析结果的论文
            papers = self.get_papers_with_analysis()
            stats['total_papers'] = len(papers)
            
            if not papers:
                logger.warning("No papers with analysis results found")
                return stats
            
            # 处理每篇论文
            for arxiv_id, content in papers:
                try:
                    logger.info(f"Processing paper: {arxiv_id}")
                    
                    # 检查是否需要迁移
                    if not self.needs_migration(content):
                        logger.debug(f"Paper {arxiv_id} does not need migration")
                        continue
                    
                    stats['papers_needing_migration'] += 1
                    
                    # 计算图片数量
                    old_pattern = r'!\[([^\]]*)\]\((imgs/[^)]+)\)'
                    image_count = len(re.findall(old_pattern, content))
                    
                    logger.info(f"Paper {arxiv_id} needs migration for {image_count} images")
                    
                    # 迁移图片路径
                    migrated_content = self.migrate_image_paths(content, arxiv_id)
                    
                    if migrated_content != content:
                        # 验证迁移结果
                        new_image_count = len(re.findall(r'!\[([^\]]*)\]\((/paper/[^)]+)\)', migrated_content))
                        
                        if not dry_run:
                            # 更新数据库
                            if self.update_paper_analysis(arxiv_id, migrated_content):
                                stats['papers_migrated'] += 1
                                stats['total_images_migrated'] += image_count
                                logger.info(f"Successfully migrated {arxiv_id} with {image_count} images")
                            else:
                                stats['papers_failed'] += 1
                                logger.error(f"Failed to update database for {arxiv_id}")
                        else:
                            # 模拟运行
                            stats['papers_migrated'] += 1
                            stats['total_images_migrated'] += image_count
                            logger.info(f"[DRY RUN] Would migrate {arxiv_id} with {image_count} images")
                    else:
                        logger.warning(f"No changes made for {arxiv_id}")
                        
                except Exception as e:
                    logger.error(f"Failed to process paper {arxiv_id}: {e}")
                    stats['papers_failed'] += 1
                    continue
            
            # 输出统计结果
            logger.info("Migration completed!")
            logger.info(f"Total papers checked: {stats['total_papers']}")
            logger.info(f"Papers needing migration: {stats['papers_needing_migration']}")
            logger.info(f"Papers migrated: {stats['papers_migrated']}")
            logger.info(f"Papers failed: {stats['papers_failed']}")
            logger.info(f"Total images migrated: {stats['total_images_migrated']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        
        finally:
            # 清理连接
            self.db_manager.close()

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate image paths in deep analysis results')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Run in dry-run mode (no actual database changes)')
    parser.add_argument('--execute', action='store_true', default=False,
                       help='Execute the migration (make actual database changes)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 确定运行模式
    if args.execute:
        dry_run = False
        logger.warning("EXECUTING MIGRATION - Database will be modified!")
        confirmation = input("Are you sure you want to proceed? (yes/no): ")
        if confirmation.lower() != 'yes':
            logger.info("Migration cancelled by user")
            return
    else:
        dry_run = True
        logger.info("Running in DRY RUN mode - no database changes will be made")
    
    try:
        # 运行迁移
        migrator = ImagePathMigrator()
        stats = migrator.run_migration(dry_run=dry_run)
        
        # 输出结果
        print("\n" + "="*50)
        print("MIGRATION SUMMARY")
        print("="*50)
        print(f"Total papers checked: {stats['total_papers']}")
        print(f"Papers needing migration: {stats['papers_needing_migration']}")
        print(f"Papers {'migrated' if not dry_run else 'would be migrated'}: {stats['papers_migrated']}")
        print(f"Papers failed: {stats['papers_failed']}")
        print(f"Total images {'migrated' if not dry_run else 'would be migrated'}: {stats['total_images_migrated']}")
        print("="*50)
        
        if dry_run and stats['papers_needing_migration'] > 0:
            print("\nTo execute the migration, run:")
            print("python migrate_image_paths.py --execute")
        
    except Exception as e:
        logger.error(f"Migration script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()