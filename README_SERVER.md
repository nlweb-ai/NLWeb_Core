# NLWeb Simple Server

## Running the Server

```bash
python -m nlweb_core.simple_server
```

The server will start on `http://localhost:8080` by default (configure via `config/config_webserver.yaml`).

## Endpoints

### GET /ask
Query the NLWeb system

**Query Parameters:**
- `query` (required) - The natural language query
- `site` (optional) - Site to search, defaults to "all"
- `num_results` (optional) - Number of results, defaults to 10
- `streaming` (optional) - true/false, defaults to true
- `db` (optional) - Database endpoint name to use

**Examples:**
```bash
# Streaming mode (default)
curl "http://localhost:8080/ask?query=best+pizza+restaurants"

# Non-streaming mode
curl "http://localhost:8080/ask?query=best+pizza&streaming=false"

# With specific site
curl "http://localhost:8080/ask?query=recipes&site=example.com"
```

### GET /health
Health check endpoint

```bash
curl "http://localhost:8080/health"
```

## Response Format

### Non-Streaming (streaming=false)
Complete JSON response following NLWeb spec v0.5:

```json
{
  "_meta": {
    "version": "0.5",
    "conversation_id": "..."
  },
  "content": [
    {
      "type": "text",
      "text": "Natural language description"
    },
    {
      "type": "resource",
      "resource": {
        "data": {
          "@type": "SearchResult",
          "name": "...",
          "description": "...",
          "grounding": "..."
        }
      }
    }
  ]
}
```

### Streaming (default)
Server-Sent Events (SSE) format:

```
data: {"_meta": {"version": "0.5"}}

data: {"content": [{"type": "text", "text": "..."}]}

data: {"content": [{"type": "resource", "resource": {"data": {...}}}]}

data: {"type": "done"}
```

## Configuration

The server uses configuration from `nlweb_core/config/`:
- `config_llm.yaml` - LLM provider configuration
- `config_retrieval.yaml` - Vector DB configuration
- `config_webserver.yaml` - Server host/port settings
- `config_nlweb.yaml` - NLWeb settings

## Dependencies

All logging has been removed to minimize dependencies. The server should run with just:
- aiohttp
- Python standard library
- Your configured LLM and vector DB clients
