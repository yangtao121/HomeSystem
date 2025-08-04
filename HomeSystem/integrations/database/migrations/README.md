# 数据库迁移脚本

本目录包含HomeSystem数据库迁移脚本，用于管理数据库架构的变更。

## 迁移脚本列表

### add_full_paper_relevance_fields.py

**目的**: 为arxiv_papers表添加完整论文相关性评分字段

**新增字段**:
- `full_paper_relevance_score`: DECIMAL(5,3) - 完整论文相关性评分(0.000-1.000)
- `full_paper_relevance_justification`: TEXT - 完整论文相关性评分理由

**功能**:
1. 添加新字段到arxiv_papers表
2. 创建性能优化索引
3. 从现有metadata JSON中迁移相关数据
4. 验证迁移结果

**使用方法**:

```bash
# 执行迁移
cd homesystem  # 进入项目根目录
python HomeSystem/integrations/database/migrations/add_full_paper_relevance_fields.py

# 回滚迁移（仅用于紧急情况）
python HomeSystem/integrations/database/migrations/add_full_paper_relevance_fields.py --rollback
```

**前置条件**:
- 数据库服务正在运行
- 有足够的数据库权限执行DDL操作
- ArxivPaperModel已更新到最新版本

**影响**:
- 对现有数据无破坏性影响
- 提升相关性评分查询性能
- 支持结构化相关性数据存储

## 注意事项

1. **备份**: 执行迁移前请备份数据库
2. **测试**: 在生产环境前先在测试环境验证
3. **监控**: 迁移过程中监控数据库性能
4. **回滚**: 如遇问题可使用--rollback参数回滚

## 迁移最佳实践

1. 迁移脚本应当是幂等的（可重复执行）
2. 使用IF NOT EXISTS确保安全性
3. 包含完整的验证逻辑
4. 提供清晰的日志输出
5. 支持回滚操作