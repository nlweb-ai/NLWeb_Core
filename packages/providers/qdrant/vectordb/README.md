# nlweb-qdrant-vectordb

Qdrant provider for NLWeb.

## Overview

This package provides Qdrant vector database support for NLWeb, demonstrating how to create third-party provider packages.

## Installation

```bash
pip install nlweb-core nlweb-qdrant-vectordb
```

For LLM and embedding, you'll also need a model provider:
```bash
pip install nlweb-azure-models
```

Or use the bundle packages:
```bash
pip install nlweb-core nlweb-retrieval nlweb-models
```

## Configuration

Create `config.yaml`:

```yaml
retrieval:
  provider: qdrant
  import_path: nlweb_qdrant_vectordb.qdrant_client
  class_name: QdrantVectorClient
  api_endpoint_env: QDRANT_URL  # Optional for remote Qdrant
  api_key_env: QDRANT_API_KEY  # Optional for remote Qdrant
  database_path_env: QDRANT_PATH  # Optional for local Qdrant
  index_name: my-collection
```

### Authentication

For remote Qdrant:
```bash
export QDRANT_URL=https://your-cluster.qdrant.tech
export QDRANT_API_KEY=your_api_key_here
```

For local Qdrant:
```bash
export QDRANT_PATH=./data/qdrant
```

## Usage

```python
import nlweb_core

# Initialize
nlweb_core.init(config_path="./config.yaml")

# Search
from nlweb_core import retriever

results = await retriever.search(
    query="example query",
    site="example.com",
    num_results=10
)
```

## Features

- Vector similarity search with Qdrant using 1536-dimensional embeddings
- Support for both remote and local Qdrant instances
- HNSW-based efficient similarity search
- Configurable collection names
- API key authentication for remote instances
- Local file-based storage option
- Automatic query embedding using NLWeb's embedding providers
- Compatible with NLWeb Protocol v0.5

## Data Format

The Qdrant provider expects documents with the following payload structure:
- `url`: Document URL (string)
- `content`: Full document content as JSON string (string)
- `type`: Document type (string)
- `site`: Site identifier for filtering (string)
- `embedding`: 1536-dimensional vector (stored separately in Qdrant)

Example payload:
```json
{
  "url": "https://example.com/page",
  "content": "{\"@type\": \"Article\", \"name\": \"Title\", \"description\": \"...\"}", 
  "type": "Article",
  "site": "example.com"
}
```

## Creating Your Own Provider Package

Use this package as a template:

1. **Create package structure**:
   ```
   nlweb-yourprovider/
   ├── pyproject.toml
   ├── README.md
   └── nlweb_yourprovider/
       ├── __init__.py
       └── your_client.py
   ```

2. **Implement VectorDBClientInterface**:
   ```python
   from nlweb_core.retriever import VectorDBClientInterface

   class YourClient(VectorDBClientInterface):
       async def search(self, query, site, num_results, **kwargs):
           # Your implementation
           pass
   ```

3. **Declare dependencies** in `pyproject.toml`:
   ```toml
   dependencies = [
       "nlweb-core>=0.5.0",
       "your-provider-sdk>=1.0.0",
   ]
   ```

4. **Publish to PyPI**:
   ```bash
   python -m build
   twine upload dist/*
   ```

## License

MIT License - Copyright (c) 2025 Microsoft Corporation
