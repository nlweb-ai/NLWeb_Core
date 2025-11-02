# nlweb-retrieval

Bundle package containing all retrieval providers for NLWeb.

## Included Providers

This package includes clients for:

- **Azure AI Search** - Azure's vector search service with managed identity support
- **Elasticsearch** - Popular open-source search and analytics engine
- **Milvus** - Open-source vector database
- **Qdrant** - Vector similarity search engine
- **PostgreSQL** (pgvector) - PostgreSQL with vector extension
- **OpenSearch** - Open-source search and analytics suite
- **Snowflake Cortex Search** - Snowflake's vector search
- **Shopify MCP** - Shopify Model Context Protocol
- **Cloudflare AutoRAG** - Cloudflare's RAG service
- **Bing Search** - Microsoft Bing web search

## Installation

```bash
pip install nlweb-core nlweb-retrieval
```

## Configuration Example

Create `config.yaml`:

```yaml
retrieval:
  provider: elasticsearch
  import_path: nlweb_retrieval.elasticsearch_client
  class_name: ElasticsearchClient
  api_endpoint_env: ELASTICSEARCH_URL
  index_name: my_index
  use_knn: true
```

### Azure AI Search Example

```yaml
retrieval:
  provider: azure_ai_search
  import_path: nlweb_retrieval.azure_search_client
  class_name: AzureSearchClient
  api_endpoint_env: AZURE_SEARCH_ENDPOINT
  auth_method: azure_ad  # or api_key
  index_name: my-search-index
```

### Qdrant Example

```yaml
retrieval:
  provider: qdrant
  import_path: nlweb_retrieval.qdrant
  class_name: QdrantVectorClient
  database_path: ./data/qdrant_db  # for local storage
  # OR for remote:
  # api_endpoint_env: QDRANT_URL
  # api_key_env: QDRANT_API_KEY
```

## Usage

```python
import nlweb_core

# Initialize with config
nlweb_core.init(config_path="./config.yaml")

# Use retrieval
from nlweb_core import retriever

# Search
results = await retriever.search(
    query="example query",
    site="example.com",
    num_results=10
)
```

## Provider Import Paths

Use these in your config file:

| Provider | import_path | class_name |
|----------|-------------|------------|
| Azure AI Search | `nlweb_retrieval.azure_search_client` | `AzureSearchClient` |
| Elasticsearch | `nlweb_retrieval.elasticsearch_client` | `ElasticsearchClient` |
| Milvus | `nlweb_retrieval.milvus_client` | `MilvusVectorClient` |
| Qdrant | `nlweb_retrieval.qdrant` | `QdrantVectorClient` |
| PostgreSQL | `nlweb_retrieval.postgres_client` | `PgVectorClient` |
| OpenSearch | `nlweb_retrieval.opensearch_client` | `OpenSearchClient` |
| Snowflake | `nlweb_retrieval.snowflake_client` | `SnowflakeCortexSearchClient` |
| Shopify MCP | `nlweb_retrieval.shopify_mcp` | `ShopifyMCPClient` |
| Cloudflare | `nlweb_retrieval.cf_autorag_client` | `CloudflareAutoRAGClient` |
| Bing Search | `nlweb_retrieval.bing_search_client` | `BingSearchClient` |

## License

MIT License - Copyright (c) 2025 Microsoft Corporation
