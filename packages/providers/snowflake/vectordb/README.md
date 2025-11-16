# NLWeb Snowflake Cortex Search Provider

Snowflake Cortex Search vector database provider for NLWeb, enabling hybrid search capabilities using Snowflake's Cortex Search Service.

## Features

- **Cortex Search Integration**: Native integration with Snowflake Cortex Search Service
- **REST API Based**: Uses Snowflake's REST API for search operations
- **Hybrid Search**: Combines vector similarity with keyword search
- **Site Filtering**: Filter search results by site or URL
- **PAT Authentication**: Secure authentication using Programmatic Access Tokens
- **Async Support**: Built with async/await for high performance

## Installation

```bash
pip install nlweb-snowflake-vectordb
```

## Configuration

Configure the Snowflake Cortex Search endpoint in your `config.yaml`:

```yaml
retrieval_endpoints:
  snowflake_prod:
    db_type: snowflake_cortex_search
    api_endpoint: "https://your-account.snowflakecomputing.com"
    api_key: "${SNOWFLAKE_PAT}"
    index_name: "MY_DATABASE.MY_SCHEMA.MY_SEARCH_SERVICE"
    vector_dimensions: 1024
```

The `index_name` should be in the format: `<database>.<schema>.<service>`

## Usage

### Basic Search

```python
from nlweb_snowflake_vectordb import SnowflakeCortexClient

# Initialize client
client = SnowflakeCortexClient(endpoint_name="snowflake_prod")

# Search for documents
results = await client.search(
    query="machine learning models",
    site="docs.example.com",
    num_results=10
)

# Process results
for url, schema_json, name, site in results:
    print(f"{name}: {url}")
```

### Search by URL

```python
# Find a specific document by URL
results = await client.search_by_url(
    url="https://docs.example.com/ml-guide",
    query="machine learning"
)
```

### Get Available Sites

```python
# Get list of all indexed sites
sites = await client.get_sites()
print(f"Available sites: {sites}")
```

## API Reference

### SnowflakeCortexClient

Main client for Snowflake Cortex Search operations.

#### Methods

- `search(query, site, num_results, **kwargs)`: Search for documents by query and site
- `search_by_url(url, query, **kwargs)`: Search for a specific document by URL
- `get_sites(**kwargs)`: Get list of unique site names

## Snowflake Cortex Search Service

This provider requires a Snowflake Cortex Search Service with the following columns:
- `url`: Document URL (TEXT)
- `site`: Site name (TEXT)
- `schema_json`: Schema metadata (TEXT/VARIANT)

The search service should be created with vector embeddings enabled.

## Requirements

- Python 3.10+
- nlweb-core >= 0.5.5
- httpx >= 0.28.1
- Active Snowflake account with Cortex Search enabled
- Valid Programmatic Access Token (PAT)

## Note on Data Ingestion

Unlike other vector database providers, Snowflake Cortex Search does not support programmatic document upload through this client. Data must be loaded into Snowflake tables using Snowflake's native data loading tools (COPY INTO, Snowpipe, etc.) before creating the Cortex Search Service.

This package provides **read-only** access to existing Cortex Search Services.

## License

MIT License - see LICENSE file for details.

## Links

- [Snowflake Cortex Search Documentation](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search)
- [Cortex Search REST API](https://docs.snowflake.com/developer-guide/snowflake-rest-api/reference/cortex-search-service)
- [NLWeb Core](https://github.com/nlweb-ai/NLWeb_Core)
