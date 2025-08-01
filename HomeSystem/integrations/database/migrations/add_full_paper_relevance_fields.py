#!/usr/bin/env python3
"""
数据库迁移脚本：添加完整论文相关性评分字段

该脚本为arxiv_papers表添加以下字段：
- full_paper_relevance_score: DECIMAL(5,3) - 完整论文相关性评分(0.000-1.000)
- full_paper_relevance_justification: TEXT - 完整论文相关性评分理由

同时从现有metadata JSON字段中迁移相关数据。
"""

import sys
import os
import json
from loguru import logger

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from HomeSystem.integrations.database.connection import get_database_manager


def add_new_columns(cursor) -> bool:
    """添加新字段"""
    try:
        logger.info("开始添加新字段...")
        
        # 添加完整论文相关性评分字段
        cursor.execute("""
            ALTER TABLE arxiv_papers 
            ADD COLUMN IF NOT EXISTS full_paper_relevance_score DECIMAL(5,3) DEFAULT NULL
        """)
        
        # 添加完整论文相关性评分理由字段
        cursor.execute("""
            ALTER TABLE arxiv_papers 
            ADD COLUMN IF NOT EXISTS full_paper_relevance_justification TEXT DEFAULT NULL
        """)
        
        logger.info("新字段添加成功")
        return True
        
    except Exception as e:
        logger.error(f"添加新字段失败: {e}")
        return False


def create_indexes(cursor) -> bool:
    """创建新字段的索引"""
    try:
        logger.info("开始创建索引...")
        
        # 为相关性评分创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_arxiv_papers_full_paper_relevance_score 
            ON arxiv_papers(full_paper_relevance_score)
        """)
        
        # 为相关性评分创建降序索引（用于排序查询）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_arxiv_papers_full_paper_relevance_score_desc 
            ON arxiv_papers(full_paper_relevance_score DESC)
        """)
        
        logger.info("索引创建成功")
        return True
        
    except Exception as e:
        logger.error(f"创建索引失败: {e}")
        return False


def migrate_existing_data(cursor) -> int:
    """从metadata中迁移现有数据到新字段"""
    try:
        logger.info("开始迁移现有数据...")
        
        # 查询所有有metadata的记录
        cursor.execute("""
            SELECT id, metadata FROM arxiv_papers 
            WHERE metadata IS NOT NULL AND metadata != '{}' AND metadata != 'null'
        """)
        
        records = cursor.fetchall()
        migrated_count = 0
        
        for record in records:
            record_id, metadata_str = record
            
            try:
                # 解析metadata JSON
                if isinstance(metadata_str, str):
                    metadata = json.loads(metadata_str)
                else:
                    metadata = metadata_str
                
                if not isinstance(metadata, dict):
                    continue
                
                # 提取相关性评分和理由
                full_paper_score = metadata.get('full_paper_relevance_score')
                
                # 查找可能的理由字段（尝试多个可能的键名）
                justification_keys = [
                    'full_paper_analysis_justification',
                    'full_paper_justification', 
                    'full_analysis_justification',
                    'full_paper_reason'
                ]
                
                full_paper_justification = None
                for key in justification_keys:
                    if key in metadata:
                        full_paper_justification = metadata[key]
                        break
                
                # 只有当评分存在时才更新
                if full_paper_score is not None:
                    # 确保评分在有效范围内
                    if isinstance(full_paper_score, (int, float)) and 0 <= full_paper_score <= 1:
                        update_sql = """
                            UPDATE arxiv_papers 
                            SET full_paper_relevance_score = %s,
                                full_paper_relevance_justification = %s
                            WHERE id = %s
                        """
                        
                        cursor.execute(update_sql, (
                            float(full_paper_score),
                            full_paper_justification,
                            record_id
                        ))
                        
                        migrated_count += 1
                        logger.debug(f"迁移记录 {record_id}: 评分={full_paper_score}, 理由长度={len(full_paper_justification or '')}")
                    else:
                        logger.warning(f"记录 {record_id} 的评分无效: {full_paper_score}")
                        
            except json.JSONDecodeError as e:
                logger.warning(f"记录 {record_id} 的metadata JSON解析失败: {e}")
            except Exception as e:
                logger.error(f"迁移记录 {record_id} 时发生错误: {e}")
        
        logger.info(f"数据迁移完成，成功迁移 {migrated_count} 条记录")
        return migrated_count
        
    except Exception as e:
        logger.error(f"数据迁移失败: {e}")
        return 0


def validate_migration(cursor) -> bool:
    """验证迁移结果"""
    try:
        logger.info("开始验证迁移结果...")
        
        # 检查新字段是否存在
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'arxiv_papers' 
            AND column_name IN ('full_paper_relevance_score', 'full_paper_relevance_justification')
            ORDER BY column_name
        """)
        
        columns = cursor.fetchall()
        
        if len(columns) != 2:
            logger.error(f"新字段检查失败，找到 {len(columns)} 个字段，预期 2 个")
            return False
        
        for column in columns:
            column_name, data_type, is_nullable = column
            logger.info(f"字段 {column_name}: 类型={data_type}, 可空={is_nullable}")
        
        # 统计有评分数据的记录数
        cursor.execute("""
            SELECT COUNT(*) FROM arxiv_papers 
            WHERE full_paper_relevance_score IS NOT NULL
        """)
        
        count_with_score = cursor.fetchone()[0]
        logger.info(f"有完整论文相关性评分的记录数: {count_with_score}")
        
        # 统计有理由数据的记录数
        cursor.execute("""
            SELECT COUNT(*) FROM arxiv_papers 
            WHERE full_paper_relevance_justification IS NOT NULL 
            AND full_paper_relevance_justification != ''
        """)
        
        count_with_justification = cursor.fetchone()[0]
        logger.info(f"有完整论文相关性理由的记录数: {count_with_justification}")
        
        # 检查索引
        cursor.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'arxiv_papers' 
            AND indexname LIKE '%full_paper_relevance%'
            ORDER BY indexname
        """)
        
        indexes = [row[0] for row in cursor.fetchall()]
        logger.info(f"相关性评分索引: {indexes}")
        
        expected_indexes = [
            'idx_arxiv_papers_full_paper_relevance_score',
            'idx_arxiv_papers_full_paper_relevance_score_desc'
        ]
        
        missing_indexes = [idx for idx in expected_indexes if idx not in indexes]
        if missing_indexes:
            logger.warning(f"缺少索引: {missing_indexes}")
        else:
            logger.info("所有索引检查通过")
        
        logger.info("迁移验证完成")
        return True
        
    except Exception as e:
        logger.error(f"迁移验证失败: {e}")
        return False


def rollback_migration(cursor) -> bool:
    """回滚迁移（仅用于测试或紧急情况）"""
    try:
        logger.warning("开始回滚迁移...")
        
        # 删除索引
        cursor.execute("DROP INDEX IF EXISTS idx_arxiv_papers_full_paper_relevance_score")
        cursor.execute("DROP INDEX IF EXISTS idx_arxiv_papers_full_paper_relevance_score_desc")
        
        # 删除字段
        cursor.execute("ALTER TABLE arxiv_papers DROP COLUMN IF EXISTS full_paper_relevance_score")
        cursor.execute("ALTER TABLE arxiv_papers DROP COLUMN IF EXISTS full_paper_relevance_justification")
        
        logger.warning("迁移回滚完成")
        return True
        
    except Exception as e:
        logger.error(f"迁移回滚失败: {e}")
        return False


def main():
    """主函数"""
    logger.info("开始数据库迁移：添加完整论文相关性评分字段")
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
        logger.warning("执行回滚操作")
        rollback_mode = True
    else:
        rollback_mode = False
    
    try:
        # 获取数据库管理器
        db_manager = get_database_manager()
        
        with db_manager.get_postgres_sync() as cursor:
            if rollback_mode:
                # 执行回滚
                success = rollback_migration(cursor)
                if success:
                    logger.info("回滚成功完成")
                else:
                    logger.error("回滚失败")
                    sys.exit(1)
            else:
                # 执行迁移
                logger.info("开始正向迁移...")
                
                # 1. 添加新字段
                if not add_new_columns(cursor):
                    logger.error("添加字段失败，迁移终止")
                    sys.exit(1)
                
                # 2. 创建索引
                if not create_indexes(cursor):
                    logger.error("创建索引失败，迁移终止")
                    sys.exit(1)
                
                # 3. 迁移现有数据
                migrated_count = migrate_existing_data(cursor)
                logger.info(f"成功迁移 {migrated_count} 条记录的数据")
                
                # 4. 验证迁移结果
                if not validate_migration(cursor):
                    logger.error("迁移验证失败")
                    sys.exit(1)
                
                logger.info("数据库迁移成功完成！")
                logger.info("新增字段:")
                logger.info("  - full_paper_relevance_score: 完整论文相关性评分 (0.000-1.000)")
                logger.info("  - full_paper_relevance_justification: 完整论文相关性评分理由")
                
    except Exception as e:
        logger.error(f"迁移过程中发生异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()