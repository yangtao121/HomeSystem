# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.


## Architecture Overview

HomeSystem is a Python-based intelligent home automation system that integrates local and cloud LLMs for document management, paper collection, and workflow automation.

### Core Components

- **HomeSystem/graph/**: LangGraph-based agent system with chat capabilities
  - `base_graph.py`: Abstract base class for graph agents with chat interface and graph visualization
  - `chat_agent.py`: Chat agent implementation  
  - `llm_factory.py`: LLM provider factory (supports multiple providers via YAML config)
  - `paper_analysis_agent.py`: Specialized agent for paper analysis
  - `tool/`: Search and web content extraction tools

- **HomeSystem/workflow/**: Task scheduling and workflow framework
  - `engine.py`: Workflow engine with async task management and signal handling
  - `scheduler.py`: Task scheduler with interval-based execution
  - `task.py`: Base Task class for creating scheduled tasks
  - `paper_gather_task/`: Specialized paper collection workflow with LLM integration

- **HomeSystem/integrations/**: External service integrations
  - `database/`: PostgreSQL + Redis operations with ORM-like interface
    - `connection.py`: Database connection management with Docker auto-detection
    - `operations.py`: CRUD operations for all models
    - `models.py`: Data models including ArxivPaperModel with structured analysis fields
  - `paperless/`: Paperless-ngx document management integration
  - `dify/`: Dify AI workflow platform integration

- **HomeSystem/utility/**: Utility modules
  - `arxiv/`: ArXiv paper search and database integration with duplicate detection

- **Web/ExplorePaperData/**: Flask web application for paper data visualization
  - Provides dashboard, search, filtering, and detailed paper analysis views
  - Replaces command-line debug tools with intuitive web interface

### Database Architecture
- **PostgreSQL**: Primary storage for structured paper data with analysis fields
- **Redis**: Caching layer for improved performance and processing state tracking
- **Auto-detection**: System automatically detects Docker container ports
- **Structured Analysis**: Support for research objectives, methods, key findings, and contributions

## Key Development Patterns

### Database Operations
Use the centralized database operations for all data access:
```python
from HomeSystem.integrations.database import DatabaseOperations, ArxivPaperModel

# Initialize operations
db_ops = DatabaseOperations()

# Create and save paper data
paper = ArxivPaperModel()
paper.set_data({
    'id': 'arxiv_id',
    'title': 'Paper Title',
    'abstract': 'Abstract content',
    # ... structured analysis fields
})
success = db_ops.create(paper)
```

### Creating Custom Tasks
Extend the `Task` base class for scheduled operations:
```python
from HomeSystem.workflow.task import Task

class MyTask(Task):
    def __init__(self):
        super().__init__("my_task", interval_seconds=60)
    
    async def run(self):
        # Your task logic here
        return {"status": "completed"}
```

### LLM Integration
Use the factory pattern for LLM access:
```python
from HomeSystem.graph.llm_factory import LLMFactory

# Initialize factory
factory = LLMFactory()

# Get available models
chat_models = factory.get_available_chat_models()
embedding_models = factory.get_available_embedding_models()

# Create model instance
llm = factory.create_chat_model("deepseek.DeepSeek_V3")
embeddings = factory.create_embedding_model("ollama.BGE_M3")
```

### Graph Agents
Extend `BaseGraph` for custom LangGraph agents:
```python
from HomeSystem.graph.base_graph import BaseGraph

class MyAgent(BaseGraph):
    def __init__(self):
        super().__init__()
        # Initialize your agent with tools and nodes
```

## Configuration

### LLM Configuration
LLM providers are configured via YAML in `HomeSystem/graph/config/llm_providers.yaml`:
- Supports 2025 latest models including DeepSeek V3/R1, Qwen 2.5, Doubao 1.6
- Multiple providers: DeepSeek, SiliconFlow, Volcano Engine, MoonShot, Ollama
- Both cloud APIs and local Ollama models (14B+ parameters)
- Embedding models for semantic search capabilities


## Project Structure Notes

- Examples in `examples/` demonstrate usage patterns for each major component
- Documentation in `docs/` provides detailed integration guides including database setup
- The system uses async/await patterns extensively for concurrency
- Database integration supports both PostgreSQL (persistent) and Redis (caching) with automatic Docker detection
- Workflow system supports signal-based graceful shutdown
- Web interface provides modern alternative to command-line debugging tools
- LLM configuration supports both cloud APIs and local models with unified interface