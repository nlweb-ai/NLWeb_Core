# NLWeb Core

A modular Python framework for building natural language web applications with vector database retrieval, LLM-based ranking, and multiple protocol support (HTTP, MCP, A2A).

## Features

- **Modular Package Architecture**: Install only what you need - core, network, data loading, and provider packages
- **Vector Database Support**: Azure AI Search, Qdrant, Elasticsearch, OpenSearch, PostgreSQL, Milvus, Snowflake, and more
- **Multiple LLM Providers**: OpenAI, Azure OpenAI, Anthropic, Google Gemini, Hugging Face, and more
- **Multiple Embedding Providers**: OpenAI, Azure OpenAI, Google Gemini, Ollama, Snowflake
- **Flexible Authentication**: API key and Azure Managed Identity support for Azure services
- **Multiple Protocol Support**:
  - **HTTP**: REST API with JSON and Server-Sent Events (SSE) streaming
  - **MCP (Model Context Protocol)**: JSON-RPC 2.0 for AI model integration
  - **A2A (Agent-to-Agent)**: JSON-RPC 2.0 for multi-agent communication
- **NLWeb Protocol v0.5**: Standardized response format with metadata and content

## Installation

### From PyPI

```bash
# Core packages
pip install nlweb-dataload  # Standalone data loading tools
pip install nlweb-core      # Core framework
pip install nlweb-network   # Network interfaces (HTTP/MCP/A2A)

# Provider packages (optional)
pip install nlweb-azure-vectordb  # Azure AI Search
pip install nlweb-azure-models    # Azure OpenAI

# Or install bundles
pip install nlweb-retrieval  # All vector database providers
pip install nlweb-models     # All LLM/embedding providers
```

### From Source

```bash
git clone https://github.com/nlweb-ai/NLWeb_Core.git
cd NLWeb_Core
pip install -e packages/dataload
pip install -e packages/core
pip install -e packages/network
```

## Quick Start

### 1. Create a configuration file

Create `config.yaml`:

```yaml
# Vector database
retrieval:
  nlweb_azure:
    enabled: true
    api_key_env: AZURE_VECTOR_SEARCH_API_KEY
    api_endpoint_env: AZURE_VECTOR_SEARCH_ENDPOINT
    index_name: your-index-name
    db_type: azure_ai_search

# LLM provider
llm:
  azure_openai:
    llm_type: azure_openai
    api_key_env: AZURE_OPENAI_API_KEY
    endpoint_env: AZURE_OPENAI_ENDPOINT
    api_version: "2024-10-21"
    models:
      high: gpt-4o
      low: gpt-4o-mini

# Embedding provider
embedding:
  azure_openai:
    embedding_type: azure_openai
    api_key_env: AZURE_OPENAI_API_KEY
    endpoint_env: AZURE_OPENAI_ENDPOINT
    api_version: "2024-10-21"
    deployment_name: text-embedding-3-large

# Server
server:
  host: localhost
  port: 8080
  enable_cors: true
```

### 2. Set environment variables

```bash
export AZURE_VECTOR_SEARCH_API_KEY=your_key
export AZURE_VECTOR_SEARCH_ENDPOINT=https://your-search.search.windows.net
export AZURE_OPENAI_API_KEY=your_key
export AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com
```

### 3. Start the server

```bash
# Using the network package
python -m nlweb_network.server.main config.yaml

# Or programmatically
from nlweb_core import init
from nlweb_network.server import main

init('config.yaml')
main()
```

### 4. Query via HTTP

```bash
# Health check
curl http://localhost:8080/health

# Non-streaming query
curl "http://localhost:8080/ask?query=pasta+recipes&streaming=false&num_results=5"

# Streaming query (SSE)
curl "http://localhost:8080/ask?query=pasta+recipes&streaming=true"

# With site filter
curl "http://localhost:8080/ask?query=spicy+snacks&site=seriouseats"

# POST request
curl -X POST http://localhost:8080/ask \
  -H 'Content-Type: application/json' \
  -d '{"query": "best pizza recipes", "num_results": 10}'
```

### 5. Query via MCP (Model Context Protocol)

```bash
# List available tools
curl -X POST http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }'

# Call a tool
curl -X POST http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "ask",
      "arguments": {
        "query": "healthy breakfast recipes",
        "num_results": 5
      }
    },
    "id": 2
  }'
```

### 6. Query via A2A (Agent-to-Agent Protocol)

```bash
# Get agent card
curl -X POST http://localhost:8080/a2a \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "method": "agent/card",
    "id": 1
  }'

# Send message to agent
curl -X POST http://localhost:8080/a2a \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "vegan desserts"}]
      }
    },
    "id": 2
  }'
```

## Data Loading

Use `nlweb-dataload` to index content into your vector database:

```bash
# Load from JSON file
python -m nlweb_dataload.load_from_json \
  --json-file recipes.json \
  --config config.yaml

# Load from sitemap
python -m nlweb_dataload.load_from_sitemap \
  --sitemap-url https://example.com/sitemap.xml \
  --config config.yaml
```

See the [dataload README](packages/dataload/README.md) for more details.

## Authentication Options

### Azure AI Search with API Key

```yaml
nlweb_azure:
  enabled: true
  api_key_env: AZURE_VECTOR_SEARCH_API_KEY
  api_endpoint_env: AZURE_VECTOR_SEARCH_ENDPOINT
  index_name: embeddings
  db_type: azure_ai_search
```

### Azure AI Search with Managed Identity

```yaml
nlweb_azure:
  enabled: true
  api_endpoint_env: AZURE_VECTOR_SEARCH_ENDPOINT
  index_name: embeddings
  db_type: azure_ai_search
  auth_method: azure_ad  # Uses DefaultAzureCredential
```

### Azure OpenAI with Managed Identity

```yaml
azure_openai:
  llm_type: azure_openai
  endpoint_env: AZURE_OPENAI_ENDPOINT
  api_version: "2024-10-21"
  auth_method: azure_ad
  models:
    high: gpt-4o
    low: gpt-4o-mini
```

## Package Structure

- **nlweb-dataload**: Standalone data loading tools (no dependencies on other NLWeb packages)
- **nlweb-core**: Core framework and abstractions
- **nlweb-network**: HTTP/MCP/A2A server and interfaces
- **nlweb-azure-vectordb**: Azure AI Search provider
- **nlweb-azure-models**: Azure OpenAI LLM and embedding providers
- **nlweb-retrieval**: Bundle of all retrieval providers
- **nlweb-models**: Bundle of all LLM and embedding providers

## API Endpoints

### HTTP Endpoints

- `GET/POST /ask` - Query endpoint
  - Parameters: `query` (required), `site`, `num_results`, `streaming`, `db`
- `GET /health` - Health check

### MCP Endpoints (JSON-RPC 2.0)

- `tools/list` - List available tools
- `tools/call` - Call a tool with arguments

### A2A Endpoints (JSON-RPC 2.0)

- `agent/card` - Get agent capabilities
- `message/send` - Send message to agent

## Supported Vector Databases

- Azure AI Search
- Qdrant (local or cloud)
- Elasticsearch
- OpenSearch
- PostgreSQL with pgvector
- Milvus
- Snowflake Cortex Search
- Cloudflare AutoRAG
- Bing Search API

## Supported LLM Providers

- OpenAI
- Azure OpenAI
- Anthropic (Claude)
- Google Gemini
- Hugging Face
- Azure Llama
- Azure DeepSeek
- Snowflake Cortex
- Inception

## Testing

We provide comprehensive test scripts to verify end-to-end functionality:

```bash
# Test all protocols (HTTP, MCP, A2A) from PyPI packages
./scripts/test_packages.sh

# Test from TestPyPI
./scripts/test_from_testpypi.sh

# Test from production PyPI
./scripts/test_from_pypi.sh
```

See [scripts/](scripts/) for all available test scripts.

## Examples

Complete examples are available in the [examples/](examples/) directory:

- **azure_hello_world**: Minimal Azure setup with API key auth
- **azure_managed_identity**: Using Azure Managed Identity
- **multi_provider**: Multiple LLM and vector database providers

## Development

### Running Tests

```bash
pip install -e "packages/core[dev]"
pytest
```

### Code Formatting

```bash
black packages/
flake8 packages/
```

### Publishing to PyPI

See [scripts/setup_pypi.md](scripts/setup_pypi.md) for detailed instructions.

```bash
# Upload to TestPyPI
./scripts/upload_to_pypi.sh test

# Upload to production PyPI
./scripts/upload_to_pypi.sh prod
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please open an issue on [GitHub](https://github.com/nlweb-ai/NLWeb_Core/issues).
