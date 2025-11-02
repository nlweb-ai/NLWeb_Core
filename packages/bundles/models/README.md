# nlweb-models

Bundle package containing all LLM and embedding model providers for NLWeb.

## Included Providers

### LLM Providers

- **OpenAI** - GPT-3.5, GPT-4, and newer models
- **Anthropic** - Claude models
- **Google Gemini** - Gemini Pro and variants
- **Azure OpenAI** - Azure-hosted OpenAI models with managed identity support
- **Azure Llama** - Llama models via Azure
- **Azure DeepSeek** - DeepSeek models via Azure
- **HuggingFace** - Models from HuggingFace Hub
- **Snowflake** - Snowflake Cortex LLM
- **Ollama** - Local LLM serving
- **Inception** - Custom LLM provider

### Embedding Providers

- **OpenAI** - text-embedding-ada-002, text-embedding-3-small/large
- **Azure OpenAI** - Azure-hosted OpenAI embeddings
- **Google Gemini** - Gemini embedding models
- **Snowflake** - Snowflake Cortex embeddings
- **Ollama** - Local embedding models
- **Elasticsearch** - Elasticsearch ML embeddings

## Installation

```bash
pip install nlweb-core nlweb-models
```

## Configuration Examples

### OpenAI

```yaml
llm:
  provider: openai
  import_path: nlweb_models.llm.openai
  class_name: provider
  api_key_env: OPENAI_API_KEY
  models:
    high: gpt-4
    low: gpt-3.5-turbo

embedding:
  provider: openai
  import_path: nlweb_models.embedding.openai_embedding
  class_name: get_openai_embeddings
  api_key_env: OPENAI_API_KEY
  model: text-embedding-3-small
```

### Anthropic Claude

```yaml
llm:
  provider: anthropic
  import_path: nlweb_models.llm.anthropic
  class_name: provider
  api_key_env: ANTHROPIC_API_KEY
  models:
    high: claude-3-opus-20240229
    low: claude-3-haiku-20240307
```

### Azure OpenAI

```yaml
llm:
  provider: azure_openai
  import_path: nlweb_models.llm.azure_oai
  class_name: provider
  endpoint_env: AZURE_OPENAI_ENDPOINT
  api_key_env: AZURE_OPENAI_KEY
  api_version: 2024-02-01
  auth_method: azure_ad  # or api_key
  models:
    high: gpt-4
    low: gpt-35-turbo

embedding:
  provider: azure_openai
  import_path: nlweb_models.embedding.azure_oai_embedding
  class_name: get_azure_embedding
  endpoint_env: AZURE_OPENAI_ENDPOINT
  auth_method: azure_ad
  model: text-embedding-ada-002
```

### Google Gemini

```yaml
llm:
  provider: gemini
  import_path: nlweb_models.llm.gemini
  class_name: provider
  api_key_env: GOOGLE_API_KEY
  models:
    high: gemini-pro
    low: gemini-pro

embedding:
  provider: gemini
  import_path: nlweb_models.embedding.gemini_embedding
  class_name: get_gemini_embeddings
  model: models/embedding-001
```

## Usage

```python
import nlweb_core

# Initialize with config
nlweb_core.init(config_path="./config.yaml")

# Use LLM
from nlweb_core import llm

result = await llm.ask_llm(
    prompt="Summarize this text",
    schema={"type": "object", "properties": {"summary": {"type": "string"}}},
    level="high"
)

# Use embeddings
from nlweb_core import embedding

vector = await embedding.get_embedding(
    text="Text to embed"
)
```

## Provider Import Paths

### LLM Providers

| Provider | import_path | class_name |
|----------|-------------|------------|
| OpenAI | `nlweb_models.llm.openai` | `provider` |
| Anthropic | `nlweb_models.llm.anthropic` | `provider` |
| Gemini | `nlweb_models.llm.gemini` | `provider` |
| Azure OpenAI | `nlweb_models.llm.azure_oai` | `provider` |
| Azure Llama | `nlweb_models.llm.azure_llama` | `provider` |
| Azure DeepSeek | `nlweb_models.llm.azure_deepseek` | `provider` |
| HuggingFace | `nlweb_models.llm.huggingface` | `provider` |
| Snowflake | `nlweb_models.llm.snowflake` | `provider` |
| Ollama | `nlweb_models.llm.ollama` | `provider` |
| Inception | `nlweb_models.llm.inception` | `provider` |

### Embedding Providers

| Provider | import_path | class_name |
|----------|-------------|------------|
| OpenAI | `nlweb_models.embedding.openai_embedding` | `get_openai_embeddings` |
| Azure OpenAI | `nlweb_models.embedding.azure_oai_embedding` | `get_azure_embedding` |
| Gemini | `nlweb_models.embedding.gemini_embedding` | `get_gemini_embeddings` |
| Snowflake | `nlweb_models.embedding.snowflake_embedding` | `cortex_embed` |
| Ollama | `nlweb_models.embedding.ollama_embedding` | `get_ollama_embedding` |
| Elasticsearch | `nlweb_models.embedding.elasticsearch_embedding` | `ElasticsearchEmbedding` |

## License

MIT License - Copyright (c) 2025 Microsoft Corporation
