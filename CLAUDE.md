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
  - `siyuan/`: SiYuan Notes API integration for note management
    - `siyuan.py`: Complete SiYuan API client with CRUD operations, search, SQL queries
    - `models.py`: Data models for notes, notebooks, search results, sync operations

- **HomeSystem/utility/**: Utility modules
  - `arxiv/`: ArXiv paper search and database integration with duplicate detection

...existing code...

### Database Architecture
- **PostgreSQL**: Primary storage for structured paper data with analysis fields
- **Redis**: Caching layer for improved performance and processing state tracking
- **Auto-detection**: System automatically detects Docker container ports
- **Structured Analysis**: Support for research objectives, methods, key findings, and contributions

## Development Guidelines

### Core Principles
- Follow existing patterns and coding standards
- Use environment variables for configuration
- Handle errors appropriately with logging

### Documentation Updates
- Update documentation only after completing tasks when there are discrepancies with actual implementation
- Keep documentation changes minimal and focused on essential information

## Key Development Patterns

### Forward Compatibility Guidelines

**CRITICAL**: All major code changes must consider forward compatibility to ensure smooth system evolution and minimize breaking changes for existing users and integrations.

#### Core Principles
- **API Stability**: Maintain backward compatibility for public APIs, database schemas, and configuration formats
- **Deprecation Strategy**: Mark old features as deprecated before removal, provide migration paths
- **Version Management**: Use semantic versioning and clear upgrade documentation
- **Data Migration**: Ensure database schema changes include migration scripts and rollback procedures

#### Implementation Requirements
- **Database Changes**: Always include migration scripts in `HomeSystem/integrations/database/migrations/`
- **API Changes**: Maintain existing endpoints while introducing new versions (e.g., `/api/v1/` → `/api/v2/`)
- **Configuration**: Support old configuration formats with warnings, provide conversion utilities
- **Dependencies**: Pin major version dependencies, test compatibility before upgrades

#### Testing for Compatibility
- **Integration Tests**: Verify existing workflows continue to function after changes
- **Migration Testing**: Test upgrade paths from previous versions
- **Rollback Testing**: Ensure changes can be safely reverted if issues arise
- **Documentation**: Update all relevant documentation and migration guides

#### Examples of Forward-Compatible Changes
```python
# Good: Adding optional parameters with defaults
def create_task(name: str, interval: int, config: dict = None):
    if config is None:
        config = {}  # Maintain backward compatibility

# Good: Extending data models with optional fields
class ArxivPaperModel:
    def __init__(self):
        self.new_field = None  # Optional, doesn't break existing code

# Avoid: Breaking changes without migration path
# def create_task(config: TaskConfig):  # Breaks existing code
```

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

### SiYuan Notes Integration
Use the SiYuan client for note management:
```python
from HomeSystem.integrations.siyuan import SiYuanClient

# Create client from environment variables
client = SiYuanClient.from_environment()

# Test connection
is_connected = await client.test_connection()

# Create a note
note = await client.create_note(
    notebook_id="20240101-notebook-id",
    title="My Note Title",
    content="Note content in Markdown format",
    tags=["tag1", "tag2"]
)

# Search notes
search_result = await client.search_notes("keyword", limit=10)

# Execute SQL queries
results = await client.execute_sql("SELECT COUNT(*) FROM blocks WHERE type = 'd'")
```

## Common Development Commands

db_ops = DatabaseOperations()
...existing code...

...existing code...

...existing code...

### Database Management Commands
**Docker service management:**
```bash
# Start all services
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs postgres
docker compose logs redis

# Stop services
docker compose down

# Start with admin interfaces
docker compose --profile tools up -d
```

**Database debugging commands:**
```bash
# Connect to PostgreSQL
psql -h localhost -p 15432 -U homesystem -d homesystem

# Connect to Redis
redis-cli -p 16379

# Quick paper count check
python debug_show_arxiv_data.py

# Clear all paper data (use with caution)
python debug_clear_arxiv_data.py
```

## Configuration

### LLM Configuration
LLM providers are configured via YAML in `HomeSystem/graph/config/llm_providers.yaml`:
- Supports 2025 latest models including DeepSeek V3/R1, Qwen 2.5, Doubao 1.6
- Multiple providers: DeepSeek, SiliconFlow, Volcano Engine, MoonShot, Ollama
- Both cloud APIs and local Ollama models (14B+ parameters)
- Embedding models for semantic search capabilities

...existing code...
- Caching: 5-minute cache for searches, 15-minute cache for statistics
- Pagination: 20 papers per page by default

**Docker Service Configuration:**
Services are accessible at these ports:
- PostgreSQL: localhost:15432
- Redis: localhost:16379
- pgAdmin (optional): localhost:8080 (admin@homesystem.local / admin123)
- Redis Commander (optional): localhost:8081


## Architecture and Development Notes

### Web Application Architecture
- **PaperGather Web**: Modular Flask application with separation of concerns
  - `routes/`: Route handlers (main.py, task.py, api.py) for different functionality areas
  - `services/`: Business logic layer (task_service.py, paper_service.py) with thread-safe operations
  - `templates/`: Jinja2 templates with responsive Bootstrap UI
  - `static/`: CSS, JavaScript, and asset files
  - Thread-safe task execution using ThreadPoolExecutor and locks
  - Real-time status updates via AJAX polling
  - RESTful API endpoints for programmatic access

- **ExplorePaperData Web**: Single-file Flask application optimized for data visualization
  - `app.py`: Main application with route handlers and template filters
  - `database.py`: Data access layer with `PaperService` and `DatabaseManager` classes
  - `config.py`: Configuration management with environment variable support
  - Redis caching with intelligent cache key management and serialization
  - Advanced search with full-text capabilities across multiple fields
  - Chart.js integration for interactive data visualizations
  - Custom template filters for date formatting, text truncation, and status badges
  - Comprehensive error handling with user-friendly error pages


### Key Integration Points
- **LLMFactory**: Unified interface for multiple LLM providers (cloud + local)
- **DatabaseOperations**: Centralized database access with auto-detection of Docker containers
- **WorkflowEngine**: Background task scheduling and execution
- **ArXiv Integration**: Paper search with multiple modes (latest, relevant, date ranges)
- **SiYuan Integration**: Complete note management with CRUD operations, full-text search, SQL queries, and data sync

### Development Patterns
- Examples in `examples/` demonstrate usage patterns for each major component
- Documentation in `docs/` provides detailed integration guides:
  - `database-integration-guide.md`: Complete PostgreSQL + Redis setup, ArXiv paper management, Docker deployment
  - `llm-integration-guide.md`: Multi-provider LLM configuration (DeepSeek, SiliconFlow, Volcano, MoonShot, Ollama), embedding models
  - `vision-integration-guide.md`: Complete vision functionality guide with local model support, image processing, multimodal chat, and cloud model security restrictions
  - `arxiv-api-documentation.md`: ArXiv API tool usage, paper search and download functionality
  - `workflow-framework-guide.md`: Task scheduling system, background job management, workflow engine
  - `project-structure.md`: Detailed module organization and architectural overview
  - `siyuan-api-integration-guide.md`: Complete SiYuan Notes API integration guide with CRUD operations, search, SQL queries, and best practices
  - `papergather-web-architecture.md`: PaperGather web application architecture, components, and development patterns
  - `explore-paper-data-architecture.md`: ExplorePaperData web application architecture, data visualization, and UI components
  - `mcp-integration-guide.md`: Complete MCP (Model Context Protocol) integration guide for LangGraph agents, supporting stdio and SSE transport modes, with backward compatibility
  - **`local-services-api.md`**: **IMPORTANT** - Contains API credentials, tokens, and endpoint information for local services (SiYuan Notes, etc.). Always refer to this file when you need to integrate with external local applications or services. This is the central repository for all local service connection details.
- The system uses async/await patterns extensively for concurrency
- Database integration supports both PostgreSQL (persistent) and Redis (caching) with automatic Docker detection
- Workflow system supports signal-based graceful shutdown
- Web interface provides modern alternative to command-line debugging tools
- LLM configuration supports both cloud APIs and local models with unified interface

### Testing and Debugging
- Use the web interface at http://localhost:5001 for interactive task configuration and monitoring
- Check `Web/PaperGather/app.log` for application logs
- Database connectivity can be tested using the provided Python snippet
- Task execution can be monitored in real-time through the web interface
- **IMPORTANT**: Test files created during development must be deleted after testing is complete to maintain clean codebase