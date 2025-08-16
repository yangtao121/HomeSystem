#!/bin/bash

# HomeSystem Database Table Verification Script
# 检查所有必需的表是否存在

echo "🔍 HomeSystem Database Table Verification"

# 检查当前目录
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found in current directory"
    echo "Please run this script from the database directory"
    exit 1
fi

# 检查 PostgreSQL 容器是否运行
if ! docker ps | grep -q "homesystem-postgres"; then
    echo "❌ Error: PostgreSQL container is not running"
    echo "Please start the database services first: ./start.sh"
    exit 1
fi

echo "📊 Checking database connection..."

# 测试数据库连接
if ! docker exec homesystem-postgres pg_isready -U homesystem -d homesystem > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to PostgreSQL database"
    exit 1
fi

echo "✅ Database connection successful"
echo ""

# 检查数据库是否存在
echo "🗄️  Checking database existence..."
DB_EXISTS=$(docker exec homesystem-postgres psql -U homesystem -t -c "SELECT 1 FROM pg_database WHERE datname='homesystem';" | tr -d ' ')
if [ "$DB_EXISTS" = "1" ]; then
    echo "✅ Database 'homesystem' exists"
else
    echo "❌ Database 'homesystem' does not exist"
    exit 1
fi

echo ""
echo "📋 Checking required tables..."

# 检查 arxiv_papers 表
TABLE_EXISTS=$(docker exec homesystem-postgres psql -U homesystem -d homesystem -t -c "SELECT 1 FROM information_schema.tables WHERE table_name='arxiv_papers';" | tr -d ' ')
if [ "$TABLE_EXISTS" = "1" ]; then
    echo "✅ Table 'arxiv_papers' exists"
    
    # 获取表结构信息
    COLUMN_COUNT=$(docker exec homesystem-postgres psql -U homesystem -d homesystem -t -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='arxiv_papers';" | tr -d ' ')
    RECORD_COUNT=$(docker exec homesystem-postgres psql -U homesystem -d homesystem -t -c "SELECT COUNT(*) FROM arxiv_papers;" | tr -d ' ')
    
    echo "   - Columns: $COLUMN_COUNT"
    echo "   - Records: $RECORD_COUNT"
else
    echo "❌ Table 'arxiv_papers' does not exist"
    echo "   Run the initialization script to create tables"
    exit 1
fi

echo ""
echo "🔧 Checking table structure..."

# 检查关键字段
REQUIRED_COLUMNS=(
    "id"
    "arxiv_id"
    "title"
    "authors"
    "abstract"
    "categories"
    "processing_status"
    "task_name"
    "task_id"
    "research_objectives"
    "full_paper_relevance_score"
    "dify_dataset_id"
    "dify_document_id"
    "deep_analysis_status"
    "created_at"
    "updated_at"
)

missing_columns=()
for column in "${REQUIRED_COLUMNS[@]}"; do
    COLUMN_EXISTS=$(docker exec homesystem-postgres psql -U homesystem -d homesystem -t -c "SELECT 1 FROM information_schema.columns WHERE table_name='arxiv_papers' AND column_name='$column';" | tr -d ' ')
    if [ "$COLUMN_EXISTS" = "1" ]; then
        echo "✅ Column '$column' exists"
    else
        echo "❌ Column '$column' missing"
        missing_columns+=("$column")
    fi
done

echo ""
echo "🔍 Checking indexes..."

# 检查关键索引
REQUIRED_INDEXES=(
    "idx_arxiv_papers_arxiv_id"
    "idx_arxiv_papers_status"
    "idx_arxiv_papers_categories"
    "idx_arxiv_papers_created_at"
    "idx_arxiv_papers_task_name"
    "idx_arxiv_papers_task_id"
    "idx_arxiv_papers_full_paper_relevance_score"
    "idx_arxiv_papers_dify_dataset_id"
)

missing_indexes=()
for index in "${REQUIRED_INDEXES[@]}"; do
    INDEX_EXISTS=$(docker exec homesystem-postgres psql -U homesystem -d homesystem -t -c "SELECT 1 FROM pg_indexes WHERE indexname='$index';" | tr -d ' ')
    if [ "$INDEX_EXISTS" = "1" ]; then
        echo "✅ Index '$index' exists"
    else
        echo "❌ Index '$index' missing"
        missing_indexes+=("$index")
    fi
done

echo ""
echo "🔧 Checking triggers..."

# 检查更新时间戳触发器
TRIGGER_EXISTS=$(docker exec homesystem-postgres psql -U homesystem -d homesystem -t -c "SELECT 1 FROM information_schema.triggers WHERE trigger_name='update_arxiv_papers_updated_at';" | tr -d ' ')
if [ "$TRIGGER_EXISTS" = "1" ]; then
    echo "✅ Trigger 'update_arxiv_papers_updated_at' exists"
else
    echo "❌ Trigger 'update_arxiv_papers_updated_at' missing"
fi

echo ""
echo "📊 Database Statistics:"

# 生成统计信息
docker exec homesystem-postgres psql -U homesystem -d homesystem -c "
SELECT 
    'Total papers' as metric, 
    COUNT(*)::text as value 
FROM arxiv_papers
UNION ALL
SELECT 
    'Pending papers' as metric, 
    COUNT(*)::text as value 
FROM arxiv_papers 
WHERE processing_status = 'pending'
UNION ALL
SELECT 
    'Completed papers' as metric, 
    COUNT(*)::text as value 
FROM arxiv_papers 
WHERE processing_status = 'completed'
UNION ALL
SELECT 
    'Papers with structured data' as metric, 
    COUNT(*)::text as value 
FROM arxiv_papers 
WHERE research_objectives IS NOT NULL
UNION ALL
SELECT 
    'Papers with relevance scores' as metric, 
    COUNT(*)::text as value 
FROM arxiv_papers 
WHERE full_paper_relevance_score IS NOT NULL
UNION ALL
SELECT 
    'Papers in Dify' as metric, 
    COUNT(*)::text as value 
FROM arxiv_papers 
WHERE dify_dataset_id IS NOT NULL;
"

echo ""
echo "📝 Summary:"

# 总结检查结果
if [ ${#missing_columns[@]} -eq 0 ] && [ ${#missing_indexes[@]} -eq 0 ] && [ "$TRIGGER_EXISTS" = "1" ]; then
    echo "✅ All required database components are present and configured correctly!"
    echo "🎉 Database is ready for HomeSystem applications"
else
    echo "⚠️  Database setup is incomplete:"
    
    if [ ${#missing_columns[@]} -gt 0 ]; then
        echo "   - Missing columns: ${missing_columns[*]}"
    fi
    
    if [ ${#missing_indexes[@]} -gt 0 ]; then
        echo "   - Missing indexes: ${missing_indexes[*]}"
    fi
    
    if [ "$TRIGGER_EXISTS" != "1" ]; then
        echo "   - Missing trigger: update_arxiv_papers_updated_at"
    fi
    
    echo ""
    echo "🔧 To fix these issues, run the initialization scripts:"
    echo "   docker exec -i homesystem-postgres psql -U homesystem homesystem < init/02-create-tables.sql"
fi

echo ""
echo "✅ Database verification completed!"