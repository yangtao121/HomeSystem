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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- 为已存在的表添加新字段（兼容现有数据库）
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS task_name VARCHAR(255) DEFAULT NULL;
        ALTER TABLE arxiv_papers ADD COLUMN IF NOT EXISTS task_id VARCHAR(100) DEFAULT NULL;
        
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
        
        if structured_fields:
            info += "\n\n结构化信息:\n" + "\n".join(structured_fields)
        
        return info
    
    def set_structured_field(self, field_name: str, value: str):
        """设置结构化摘要字段"""
        valid_fields = [
            'research_background', 'research_objectives', 'methods', 
            'key_findings', 'conclusions', 'limitations', 'future_work', 'keywords'
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
            self.future_work, self.keywords
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
            'keywords': self.keywords
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