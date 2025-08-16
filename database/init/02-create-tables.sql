-- 创建 HomeSystem 数据库表结构
-- 基于 HomeSystem/integrations/database/models.py

-- 创建 arxiv_papers 表（主要论文数据表）
CREATE TABLE IF NOT EXISTS arxiv_papers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    arxiv_id VARCHAR(50) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    authors TEXT DEFAULT '',
    abstract TEXT DEFAULT '',
    categories VARCHAR(255) DEFAULT '',
    published_date VARCHAR(50) DEFAULT '',
    pdf_url TEXT DEFAULT '',
    processing_status VARCHAR(20) DEFAULT 'pending',
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    
    -- 任务追踪字段
    task_name VARCHAR(255) DEFAULT NULL,
    task_id VARCHAR(100) DEFAULT NULL,
    
    -- 结构化摘要字段
    research_background TEXT DEFAULT NULL,
    research_objectives TEXT DEFAULT NULL,
    methods TEXT DEFAULT NULL,
    key_findings TEXT DEFAULT NULL,
    conclusions TEXT DEFAULT NULL,
    limitations TEXT DEFAULT NULL,
    future_work TEXT DEFAULT NULL,
    keywords TEXT DEFAULT NULL,
    
    -- 完整论文相关性评分字段
    full_paper_relevance_score DECIMAL(5,3) DEFAULT NULL,
    full_paper_relevance_justification TEXT DEFAULT NULL,
    
    -- Dify知识库追踪字段
    dify_dataset_id VARCHAR(255) DEFAULT NULL,
    dify_document_id VARCHAR(255) DEFAULT NULL,
    dify_upload_time TIMESTAMP DEFAULT NULL,
    dify_document_name VARCHAR(500) DEFAULT NULL,
    dify_character_count INTEGER DEFAULT 0,
    dify_segment_count INTEGER DEFAULT 0,
    dify_metadata JSONB DEFAULT '{}',
    
    -- 深度分析字段
    deep_analysis_result TEXT DEFAULT NULL,
    deep_analysis_status VARCHAR(20) DEFAULT NULL,
    deep_analysis_created_at TIMESTAMP DEFAULT NULL,
    deep_analysis_updated_at TIMESTAMP DEFAULT NULL,
    
    -- 时间戳字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_arxiv_id ON arxiv_papers(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_status ON arxiv_papers(processing_status);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_categories ON arxiv_papers(categories);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_created_at ON arxiv_papers(created_at);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_published_date ON arxiv_papers(published_date);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_status_created ON arxiv_papers(processing_status, created_at);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_keywords ON arxiv_papers(keywords);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_research_objectives ON arxiv_papers(research_objectives);

-- 任务追踪字段索引
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_task_name ON arxiv_papers(task_name);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_task_id ON arxiv_papers(task_id);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_task_name_id ON arxiv_papers(task_name, task_id);

-- 完整论文相关性评分字段索引
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_full_paper_relevance_score ON arxiv_papers(full_paper_relevance_score);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_full_paper_relevance_score_desc ON arxiv_papers(full_paper_relevance_score DESC);

-- Dify知识库追踪字段索引
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_dify_dataset_id ON arxiv_papers(dify_dataset_id);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_dify_document_id ON arxiv_papers(dify_document_id);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_dify_mapping ON arxiv_papers(dify_dataset_id, dify_document_id);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_dify_upload_time ON arxiv_papers(dify_upload_time);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_dify_document_name ON arxiv_papers(dify_document_name);

-- 深度分析字段索引
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_deep_analysis_status ON arxiv_papers(deep_analysis_status);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_deep_analysis_created_at ON arxiv_papers(deep_analysis_created_at);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_deep_analysis_updated_at ON arxiv_papers(deep_analysis_updated_at);

-- 创建更新时间戳触发器函数（如果不存在）
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 创建更新时间戳触发器
DROP TRIGGER IF EXISTS update_arxiv_papers_updated_at ON arxiv_papers;
CREATE TRIGGER update_arxiv_papers_updated_at
    BEFORE UPDATE ON arxiv_papers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 全文搜索索引（可选，用于高级搜索功能）
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_title_fts 
    ON arxiv_papers USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_abstract_fts 
    ON arxiv_papers USING gin(to_tsvector('english', abstract));

-- 创建用于统计的视图（可选）
CREATE OR REPLACE VIEW arxiv_papers_stats AS
SELECT 
    COUNT(*) as total_papers,
    COUNT(CASE WHEN processing_status = 'pending' THEN 1 END) as pending_papers,
    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_papers,
    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed_papers,
    COUNT(CASE WHEN research_objectives IS NOT NULL THEN 1 END) as structured_papers,
    COUNT(CASE WHEN full_paper_relevance_score IS NOT NULL THEN 1 END) as scored_papers,
    COUNT(CASE WHEN dify_dataset_id IS NOT NULL THEN 1 END) as dify_uploaded_papers,
    COUNT(CASE WHEN deep_analysis_status = 'completed' THEN 1 END) as analyzed_papers,
    AVG(full_paper_relevance_score) as avg_relevance_score
FROM arxiv_papers;

-- 插入示例数据（可选，仅用于测试）
-- INSERT INTO arxiv_papers (arxiv_id, title, authors, abstract, categories) 
-- VALUES ('test.00001', 'Test Paper', 'Test Author', 'Test abstract for verification', 'cs.AI')
-- ON CONFLICT (arxiv_id) DO NOTHING;

-- 验证表创建
SELECT 'arxiv_papers table created successfully' as status, 
       COUNT(*) as existing_records 
FROM arxiv_papers;