# NLWeb Core

A Python library for building natural language web applications with vector database retrieval and LLM-based ranking.

## Features

- **Vector Database Support**: Azure AI Search, Qdrant, Elasticsearch, OpenSearch, PostgreSQL, Milvus, and more
- **Multiple LLM Providers**: OpenAI, Azure OpenAI, Anthropic, Google Gemini, Hugging Face, and more
- **Multiple Embedding Providers**: OpenAI, Azure OpenAI, Google Gemini, Ollama, Snowflake
- **Flexible Authentication**: API key and Azure Managed Identity support for Azure services
- **HTTP Server**: Simple server with streaming and non-streaming responses
- **MCP Protocol**: Model Context Protocol support via JSON-RPC 2.0
- **NLWeb Protocol v0.5**: Standardized response format with metadata and content

## Installation

### From PyPI (once published)

```bash
pip install nlweb-core
```

### From Git Repository

```bash
pip install git+https://github.com/yourusername/NLWeb_Core.git
```

### For Development

```bash
git clone https://github.com/yourusername/NLWeb_Core.git
cd NLWeb_Core
pip install -e .
```

## Quick Start

### 1. Configure your environment

Create a `.env` file with your API keys:

```env
# Azure AI Search (API Key)
NLWEB_WEST_API_KEY=your_api_key
NLWEB_WEST_ENDPOINT=https://your-search-service.search.windows.net

# Azure OpenAI
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com
```

### 2. Start the server

```bash
python -m nlweb_core.simple_server
```

### 3. Make a query

```bash
# Non-streaming query
curl "http://localhost:8000/ask?query=best+pizza+restaurants&streaming=false"

# With specific database
curl "http://localhost:8000/ask?query=spicy+snacks&site=seriouseats&db=nlweb_west"

# POST request
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"query": "best pizza", "site": "seriouseats"}'
```

## Authentication Options

### Azure AI Search with API Key

```yaml
nlweb_west:
  enabled: true
  api_key_env: NLWEB_WEST_API_KEY
  api_endpoint_env: NLWEB_WEST_ENDPOINT
  index_name: embeddings1536
  db_type: azure_ai_search
```

### Azure AI Search with Managed Identity

```yaml
nlweb_west_mi:
  enabled: true
  api_endpoint_env: NLWEB_WEST_ENDPOINT
  index_name: embeddings1536
  db_type: azure_ai_search
  auth_method: azure_ad  # Uses DefaultAzureCredential
```

### Azure OpenAI with Managed Identity

```yaml
azure_openai:
  llm_type: azure_openai
  endpoint: https://your-openai.openai.azure.com
  api_version: "2024-10-21"
  auth_method: azure_ad
  models:
    high: gpt-4
    low: gpt-35-turbo
```

## Configuration

Configuration files are located in `nlweb_core/config/`:

- `config_retrieval.yaml` - Vector database endpoints
- `config_llm.yaml` - LLM provider settings
- `config_embedding.yaml` - Embedding provider settings
- `config_webserver.yaml` - Server configuration
- `config_nlweb.yaml` - Application settings

## MCP (Model Context Protocol) Support

The server exposes an MCP endpoint for integration with MCP clients:

```bash
# Using MCP Inspector
npx @modelcontextprotocol/inspector http://localhost:8000/mcp

# Or via curl
curl -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

## API Endpoints

- `GET/POST /ask` - Query endpoint
  - Parameters: `query` (required), `site`, `num_results`, `streaming`, `db`
- `GET /health` - Health check
- `POST /mcp` - MCP protocol endpoint (JSON-RPC 2.0)

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

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Code Formatting

```bash
black nlweb_core/
flake8 nlweb_core/
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please open an issue on GitHub.
