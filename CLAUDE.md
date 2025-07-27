# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

HomeSystem is a Python-based intelligent home automation system that integrates local and cloud LLMs for document management, paper collection, and workflow automation.

### Core Components

- **HomeSystem/graph/**: LangGraph-based agent system with chat capabilities
  - `base_graph.py`: Abstract base class for graph agents with chat interface and graph visualization
  - `chat_agent.py`: Chat agent implementation  
  - `llm_factory.py`: LLM provider factory (supports multiple providers via YAML config)
  - `tool/`: Search and web content extraction tools

- **HomeSystem/workflow/**: Task scheduling and workflow framework
  - `engine.py`: Workflow engine with async task management and signal handling
  - `scheduler.py`: Task scheduler with interval-based execution
  - `task.py`: Base Task class for creating scheduled tasks
  - `paper_gather_task/`: Specialized paper collection workflow

- **HomeSystem/integrations/**: External service integrations
  - `database/`: PostgreSQL + Redis operations with ORM-like interface
  - `paperless/`: Paperless-ngx document management integration
  - `dify/`: Dify AI workflow platform integration

- **HomeSystem/utility/**: Utility modules
  - `arxiv/`: ArXiv paper search and database integration


## Configuration

### Service Endpoints
Key service URLs that may need adjustment:
- SearxNG: `http://localhost:8080` 
- Ollama: `http://localhost:11434`
- Dify: Configure in respective integration files
- Paperless-ngx: Configure in respective integration files

### LLM Configuration
LLM providers are configured via YAML in `HomeSystem/graph/config/llm_providers.yaml`

## Key Development Patterns

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

### Database Operations
Use the database operations classes for PostgreSQL/Redis:
```python
from HomeSystem.integrations.database import DatabaseOperations, CacheOperations

db_ops = DatabaseOperations()
cache_ops = CacheOperations()
```

### Graph Agents
Extend `BaseGraph` for custom LangGraph agents:
```python
from HomeSystem.graph.base_graph import BaseGraph

class MyAgent(BaseGraph):
    def __init__(self):
        super().__init__()
        # Initialize your agent
```

## Project Structure Notes

- Examples in `examples/` demonstrate usage patterns for each major component
- Documentation in `docs/` provides detailed integration guides
- The system uses async/await patterns extensively for concurrency
- Database integration supports both PostgreSQL (persistent) and Redis (caching)
- Workflow system supports signal-based graceful shutdown
- All external services are containerized for easy deployment