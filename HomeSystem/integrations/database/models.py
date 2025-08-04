# 数据模型基类和ArXiv模型定义
import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List


class BaseModel(ABC):
    """数据模型基类，定义通用接口"""
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', str(uuid.uuid4()))
        self.created_at = kwargs.get('created_at', datetime.now())
        self.updated_at = kwargs.get('updated_at', datetime.now())
    
    @property
    @abstractmethod
    def table_name(self) -> str:
        """表名"""
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseModel':
        """从字典创建实例"""
        pass
    
    @abstractmethod
    def get_create_table_sql(self) -> str:
        """获取创建表的SQL语句"""
        pass
    
    def update_timestamp(self):
        """更新时间戳"""
        self.updated_at = datetime.now()


class ArxivPaperModel(BaseModel):
    """ArXiv论文数据模型"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.arxiv_id = kwargs.get('arxiv_id', '')
        self.title = kwargs.get('title', '')
        self.authors = kwargs.get('authors', '')
        self.abstract = kwargs.get('abstract', '')
        self.categories = kwargs.get('categories', '')
        self.published_date = kwargs.get('published_date', '')
        self.pdf_url = kwargs.get('pdf_url', '')
        self.processing_status = kwargs.get('processing_status', 'pending')  # pending, completed, failed
        self.tags = kwargs.get('tags', [])
        self.metadata = kwargs.get('metadata', {})
        
        # 任务追踪字段
        self.task_name = kwargs.get('task_name', None)
        self.task_id = kwargs.get('task_id', None)
        
        # 结构化摘要字段
        self.research_background = kwargs.get('research_background', None)
        self.research_objectives = kwargs.get('research_objectives', None)
        self.methods = kwargs.get('methods', None)
        self.key_findings = kwargs.get('key_findings', None)
        self.conclusions = kwargs.get('conclusions', None)
        self.limitations = kwargs.get('limitations', None)
        self.future_work = kwargs.get('future_work', None)
        self.keywords = kwargs.get('keywords', None)
        
        # 完整论文相关性评分字段
        self.full_paper_relevance_score = kwargs.get('full_paper_relevance_score', None)
        self.full_paper_relevance_justification = kwargs.get('full_paper_relevance_justification', None)
        
        # Dify知识库追踪字段
        self.dify_dataset_id = kwargs.get('dify_dataset_id', None)  # Dify数据集ID
        self.dify_document_id = kwargs.get('dify_document_id', None)  # Dify文档ID
        self.dify_upload_time = kwargs.get('dify_upload_time', None)  # 上传时间
        self.dify_document_name = kwargs.get('dify_document_name', None)  # 在Dify中的文档名
        self.dify_character_count = kwargs.get('dify_character_count', 0)  # Dify中的字符数
        self.dify_segment_count = kwargs.get('dify_segment_count', 0)  # 分片数量
        self.dify_metadata = kwargs.get('dify_metadata', {})  # Dify相关元数据
        
        # 深度分析字段
        self.deep_analysis_result = kwargs.get('deep_analysis_result', None)  # 深度分析结果内容
        self.deep_analysis_status = kwargs.get('deep_analysis_status', None)  # 分析状态 (pending, processing, completed, failed, cancelled)
        self.deep_analysis_created_at = kwargs.get('deep_analysis_created_at', None)  # 分析创建时间
        self.deep_analysis_updated_at = kwargs.get('deep_analysis_updated_at', None)  # 分析更新时间
    
    @property
    def table_name(self) -> str:
        return 'arxiv_papers'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'arxiv_id': self.arxiv_id,
            'title': self.title,
            'authors': self.authors,
            'abstract': self.abstract,
            'categories': self.categories,
            'published_date': self.published_date,
            'pdf_url': self.pdf_url,
            'processing_status': self.processing_status,
            'tags': json.dumps(self.tags) if isinstance(self.tags, list) else self.tags,
            'metadata': json.dumps(self.metadata) if isinstance(self.metadata, dict) else self.metadata,
            'task_name': self.task_name,
            'task_id': self.task_id,
            'research_background': self.research_background,
            'research_objectives': self.research_objectives,
            'methods': self.methods,
            'key_findings': self.key_findings,
            'conclusions': self.conclusions,
            'limitations': self.limitations,
            'future_work': self.future_work,
            'keywords': self.keywords,
            'full_paper_relevance_score': self.full_paper_relevance_score,
            'full_paper_relevance_justification': self.full_paper_relevance_justification,
            'dify_dataset_id': self.dify_dataset_id,
            'dify_document_id': self.dify_document_id,
            'dify_upload_time': self.dify_upload_time.isoformat() if self.dify_upload_time else None,
            'dify_document_name': self.dify_document_name,
            'dify_character_count': self.dify_character_count,
            'dify_segment_count': self.dify_segment_count,
            'dify_metadata': json.dumps(self.dify_metadata) if isinstance(self.dify_metadata, dict) else self.dify_metadata,
            'deep_analysis_result': self.deep_analysis_result,
            'deep_analysis_status': self.deep_analysis_status,
            'deep_analysis_created_at': self.deep_analysis_created_at.isoformat() if self.deep_analysis_created_at else None,
            'deep_analysis_updated_at': self.deep_analysis_updated_at.isoformat() if self.deep_analysis_updated_at else None,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArxivPaperModel':
        # 处理JSON字段
        if 'tags' in data and isinstance(data['tags'], str):
            try:
                data['tags'] = json.loads(data['tags'])
            except json.JSONDecodeError:
                data['tags'] = []
        
        if 'metadata' in data and isinstance(data['metadata'], str):
            try:
                data['metadata'] = json.loads(data['metadata'])
            except json.JSONDecodeError:
                data['metadata'] = {}
        
        # 处理dify_metadata JSON字段
        if 'dify_metadata' in data and isinstance(data['dify_metadata'], str):
            try:
                data['dify_metadata'] = json.loads(data['dify_metadata'])
            except json.JSONDecodeError:
                data['dify_metadata'] = {}
        
        # 处理dify_upload_time时间字段
        if 'dify_upload_time' in data and isinstance(data['dify_upload_time'], str):
            try:
                data['dify_upload_time'] = datetime.fromisoformat(data['dify_upload_time'])
            except (ValueError, TypeError):
                data['dify_upload_time'] = None
        
        # 处理深度分析时间字段
        if 'deep_analysis_created_at' in data and isinstance(data['deep_analysis_created_at'], str):
            try:
                data['deep_analysis_created_at'] = datetime.fromisoformat(data['deep_analysis_created_at'])
            except (ValueError, TypeError):
                data['deep_analysis_created_at'] = None
        
        if 'deep_analysis_updated_at' in data and isinstance(data['deep_analysis_updated_at'], str):
            try:
                data['deep_analysis_updated_at'] = datetime.fromisoformat(data['deep_analysis_updated_at'])
            except (ValueError, TypeError):
                data['deep_analysis_updated_at'] = None
        
        return cls(**data)
    
    def get_create_table_sql(self) -> str:
        return """
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
            research_background TEXT DEFAULT NULL,
            research_objectives TEXT DEFAULT NULL,
            methods TEXT DEFAULT NULL,
            key_findings TEXT DEFAULT NULL,
            conclusions TEXT DEFAULT NULL,
            limitations TEXT DEFAULT NULL,
            future_work TEXT DEFAULT NULL,
            keywords TEXT DEFAULT NULL,
            full_paper_relevance_score DECIMAL(5,3) DEFAULT NULL,
            full_paper_relevance_justification TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- 为已存在的表添加新字段（兼容现有数据库）
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS task_name VARCHAR(255) DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS task_id VARCHAR(100) DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS full_paper_relevance_score DECIMAL(5,3) DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS full_paper_relevance_justification TEXT DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS dify_dataset_id VARCHAR(255) DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS dify_document_id VARCHAR(255) DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS dify_upload_time TIMESTAMP DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS dify_document_name VARCHAR(500) DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS dify_character_count INTEGER DEFAULT 0;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS dify_segment_count INTEGER DEFAULT 0;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS dify_metadata JSONB DEFAULT '{}';
        
        -- 添加深度分析字段
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS deep_analysis_result TEXT DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS deep_analysis_status VARCHAR(20) DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS deep_analysis_created_at TIMESTAMP DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS deep_analysis_updated_at TIMESTAMP DEFAULT NULL;
        
        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_arxiv_papers_arxiv_id ON arxiv_papers(arxiv_id);
        CREATE INDEX IF NOT EXISTS idx_arxiv_papers_status ON arxiv_papers(processing_status);
        CREATE INDEX IF NOT EXISTS idx_arxiv_papers_categories ON arxiv_papers(categories);
        CREATE INDEX IF NOT EXISTS idx_arxiv_papers_created_at ON arxiv_papers(created_at);
        CREATE INDEX IF NOT EXISTS idx_arxiv_papers_published_date ON arxiv_papers(published_date);
        CREATE INDEX IF NOT EXISTS idx_arxiv_papers_status_created ON arxiv_papers(processing_status, created_at);
        CREATE INDEX IF NOT EXISTS idx_arxiv_papers_keywords ON arxiv_papers(keywords);
        CREATE INDEX IF NOT EXISTS idx_arxiv_papers_research_objectives ON arxiv_papers(research_objectives);
        
        -- 为新字段创建索引
        CREATE INDEX IF NOT EXISTS idx_arxiv_papers_task_name ON arxiv_papers(task_name);
        CREATE INDEX IF NOT EXISTS idx_arxiv_papers_task_id ON arxiv_papers(task_id);
        CREATE INDEX IF NOT EXISTS idx_arxiv_papers_task_name_id ON arxiv_papers(task_name, task_id);
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
        
        -- 创建更新时间戳触发器
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        DROP TRIGGER IF EXISTS update_arxiv_papers_updated_at ON arxiv_papers;
        CREATE TRIGGER update_arxiv_papers_updated_at
            BEFORE UPDATE ON arxiv_papers
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """
    
    def set_processing_status(self, status: str):
        """设置处理状态"""
        valid_statuses = ['pending', 'completed', 'failed']
        if status in valid_statuses:
            self.processing_status = status
            self.update_timestamp()
        else:
            raise ValueError(f"无效的处理状态: {status}, 有效值: {valid_statuses}")
    
    def add_tag(self, tag: str):
        """添加标签"""
        if tag not in self.tags:
            self.tags.append(tag)
            self.update_timestamp()
    
    def remove_tag(self, tag: str):
        """移除标签"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.update_timestamp()
    
    def set_tags(self, tags: List[str]):
        """设置标签列表"""
        self.tags = tags
        self.update_timestamp()
    
    def add_metadata(self, key: str, value: Any):
        """添加元数据"""
        self.metadata[key] = value
        self.update_timestamp()
    
    def get_formatted_info(self) -> str:
        """获取格式化的论文信息"""
        info = f"""
论文ID: {self.arxiv_id}
标题: {self.title}
作者: {self.authors}
分类: {self.categories}
发布时间: {self.published_date}
处理状态: {self.processing_status}
标签: {', '.join(self.tags) if self.tags else '无'}
任务名称: {self.task_name if self.task_name else '未知'}
任务ID: {self.task_id if self.task_id else '未知'}
创建时间: {self.created_at}
更新时间: {self.updated_at}
        """.strip()
        
        # 添加结构化摘要字段（如果有值）
        structured_fields = []
        if self.research_background:
            structured_fields.append(f"研究背景: {self.research_background}")
        if self.research_objectives:
            structured_fields.append(f"研究目标: {self.research_objectives}")
        if self.methods:
            structured_fields.append(f"研究方法: {self.methods}")
        if self.key_findings:
            structured_fields.append(f"主要发现: {self.key_findings}")
        if self.conclusions:
            structured_fields.append(f"结论: {self.conclusions}")
        if self.limitations:
            structured_fields.append(f"局限性: {self.limitations}")
        if self.future_work:
            structured_fields.append(f"未来工作: {self.future_work}")
        if self.keywords:
            structured_fields.append(f"关键词: {self.keywords}")
        if self.full_paper_relevance_score is not None:
            structured_fields.append(f"完整论文相关性评分: {self.full_paper_relevance_score}")
        if self.full_paper_relevance_justification:
            structured_fields.append(f"完整论文相关性理由: {self.full_paper_relevance_justification}")
        
        if structured_fields:
            info += "\n\n结构化信息:\n" + "\n".join(structured_fields)
        
        return info
    
    def set_structured_field(self, field_name: str, value: str):
        """设置结构化摘要字段"""
        valid_fields = [
            'research_background', 'research_objectives', 'methods', 
            'key_findings', 'conclusions', 'limitations', 'future_work', 'keywords',
            'full_paper_relevance_score', 'full_paper_relevance_justification'
        ]
        if field_name not in valid_fields:
            raise ValueError(f"无效的字段名: {field_name}, 有效值: {valid_fields}")
        
        setattr(self, field_name, value)
        self.update_timestamp()
    
    def get_structured_field(self, field_name: str) -> Optional[str]:
        """获取结构化摘要字段"""
        return getattr(self, field_name, None)
    
    def has_structured_data(self) -> bool:
        """检查是否有结构化摘要数据"""
        structured_fields = [
            self.research_background, self.research_objectives, self.methods,
            self.key_findings, self.conclusions, self.limitations, 
            self.future_work, self.keywords, self.full_paper_relevance_score,
            self.full_paper_relevance_justification
        ]
        return any(field for field in structured_fields)
    
    def get_structured_summary(self) -> Dict[str, Optional[str]]:
        """获取所有结构化摘要字段的摘要"""
        return {
            'research_background': self.research_background,
            'research_objectives': self.research_objectives,
            'methods': self.methods,
            'key_findings': self.key_findings,
            'conclusions': self.conclusions,
            'limitations': self.limitations,
            'future_work': self.future_work,
            'keywords': self.keywords,
            'full_paper_relevance_score': self.full_paper_relevance_score,
            'full_paper_relevance_justification': self.full_paper_relevance_justification
        }
    
    def update_dify_info(self, dataset_id: str, document_id: str, document_name: str,
                        character_count: int = 0, segment_count: int = 0,
                        metadata: Optional[Dict[str, Any]] = None):
        """
        更新 Dify 信息
        
        Args:
            dataset_id: Dify数据集ID
            document_id: Dify文档ID  
            document_name: Dify中的文档名
            character_count: 字符数
            segment_count: 分片数量
            metadata: 额外的元数据
        """
        self.dify_dataset_id = dataset_id
        self.dify_document_id = document_id
        self.dify_document_name = document_name
        self.dify_character_count = character_count
        self.dify_segment_count = segment_count
        self.dify_upload_time = datetime.now()
        
        if metadata:
            if not isinstance(self.dify_metadata, dict):
                self.dify_metadata = {}
            self.dify_metadata.update(metadata)
        
        self.update_timestamp()
    
    def clear_dify_info(self):
        """清除 Dify 信息（用于删除操作）"""
        self.dify_dataset_id = None
        self.dify_document_id = None
        self.dify_document_name = None
        self.dify_character_count = 0
        self.dify_segment_count = 0
        self.dify_upload_time = None
        self.dify_metadata = {}
        self.update_timestamp()
    
    def is_uploaded_to_dify(self) -> bool:
        """检查是否已上传到 Dify"""
        return bool(self.dify_dataset_id and self.dify_document_id)
    
    def get_dify_summary(self) -> Dict[str, Any]:
        """获取 Dify 追踪信息摘要"""
        return {
            'uploaded': self.is_uploaded_to_dify(),
            'dataset_id': self.dify_dataset_id,
            'document_id': self.dify_document_id,
            'document_name': self.dify_document_name,
            'upload_time': self.dify_upload_time.isoformat() if self.dify_upload_time else None,
            'character_count': self.dify_character_count,
            'segment_count': self.dify_segment_count,
            'metadata': self.dify_metadata or {}
        }
    
    def set_deep_analysis_result(self, result: str, status: str = 'completed'):
        """
        设置深度分析结果
        
        Args:
            result: 分析结果内容
            status: 分析状态 (默认为 'completed')
        """
        self.deep_analysis_result = result
        self.deep_analysis_status = status
        self.deep_analysis_updated_at = datetime.now()
        
        # 如果是第一次设置，也设置创建时间
        if not self.deep_analysis_created_at:
            self.deep_analysis_created_at = datetime.now()
        
        self.update_timestamp()
    
    def update_deep_analysis_status(self, status: str):
        """
        更新深度分析状态
        
        Args:
            status: 新的状态 (pending, processing, completed, failed, cancelled)
        """
        valid_statuses = ['pending', 'processing', 'completed', 'failed', 'cancelled']
        if status not in valid_statuses:
            raise ValueError(f"无效的深度分析状态: {status}, 有效值: {valid_statuses}")
        
        self.deep_analysis_status = status
        self.deep_analysis_updated_at = datetime.now()
        
        # 如果是第一次设置状态，也设置创建时间
        if not self.deep_analysis_created_at:
            self.deep_analysis_created_at = datetime.now()
        
        self.update_timestamp()
    
    def has_deep_analysis(self) -> bool:
        """检查是否有深度分析结果"""
        return bool(self.deep_analysis_result and self.deep_analysis_status == 'completed')
    
    def clear_deep_analysis(self):
        """清除深度分析结果"""
        self.deep_analysis_result = None
        self.deep_analysis_status = None
        self.deep_analysis_created_at = None
        self.deep_analysis_updated_at = None
        self.update_timestamp()
    
    def get_deep_analysis_summary(self) -> Dict[str, Any]:
        """获取深度分析摘要信息"""
        return {
            'has_analysis': self.has_deep_analysis(),
            'status': self.deep_analysis_status,
            'result_length': len(self.deep_analysis_result) if self.deep_analysis_result else 0,
            'created_at': self.deep_analysis_created_at.isoformat() if self.deep_analysis_created_at else None,
            'updated_at': self.deep_analysis_updated_at.isoformat() if self.deep_analysis_updated_at else None
        }


class UserModel(BaseModel):
    """用户模型示例，展示如何扩展BaseModel"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.username = kwargs.get('username', '')
        self.email = kwargs.get('email', '')
        self.preferences = kwargs.get('preferences', {})
        self.is_active = kwargs.get('is_active', True)
    
    @property
    def table_name(self) -> str:
        return 'users'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'preferences': json.dumps(self.preferences) if isinstance(self.preferences, dict) else self.preferences,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserModel':
        if 'preferences' in data and isinstance(data['preferences'], str):
            try:
                data['preferences'] = json.loads(data['preferences'])
            except json.JSONDecodeError:
                data['preferences'] = {}
        return cls(**data)
    
    def get_create_table_sql(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            preferences JSONB DEFAULT '{}',
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
        
        DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """