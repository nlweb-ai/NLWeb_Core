# NLWeb Azure Hello World Example

A simple example demonstrating NLWeb's core RAG (Retrieval-Augmented Generation) functionality with Azure OpenAI and Azure AI Search.

## What NLWeb Actually Does

**NLWeb is not just an API wrapper** - it's a complete RAG system with LLM-powered ranking:

1. **RETRIEVE** - Search your vector database (Azure AI Search) for relevant items
2. **RANK** - Use an LLM (Azure OpenAI) to score each item from 0-100 for relevance
3. **GENERATE** - Create natural language descriptions for relevant items using the LLM
4. **STREAM** - Send high-scoring results back to clients via Server-Sent Events

This hello world starts an HTTP server with an `/ask` endpoint that runs the complete RAG pipeline.

## Prerequisites

Before you begin, you need:

1. **Python 3.9+** installed on your system
2. **Azure OpenAI resource** with deployed models:
   - A GPT model (e.g., gpt-4.1, gpt-4.1-mini)
   - An embedding model (e.g., text-embedding-3-small)
3. **Azure AI Search resource** with an index containing your data
4. **API keys or managed identity** configured for authentication

## Quick Start

### Step 1: Install NLWeb Packages

```bash
pip install -r requirements.txt
```

This installs:
- `nlweb-core` - Core framework with RAG pipeline
- `nlweb-azure-vectordb` - Azure AI Search provider
- `nlweb-azure-models` - Azure OpenAI LLM and embedding providers

### Step 2: Configure Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` and add your Azure credentials:

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your_key_here

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://your-service.search.windows.net
AZURE_SEARCH_KEY=your_key_here
```

### Step 3: Update Configuration

The `config.yaml` file is pre-configured for Azure. Update it to match your deployments:

```yaml
llm:
  models:
    high: gpt-4.1           # Change to your deployment name
    low: gpt-4.1-mini       # Change to your deployment name

embedding:
  model: text-embedding-3-small  # Change to your deployment name

retrieval:
  index_name: your-index-name    # Change to your index name
```

### Step 4: Start the Server

```bash
python hello_world.py
```

You should see:

```
======================================================================
NLWeb Azure Hello World - RAG Server
======================================================================

✓ Configuration loaded successfully

Starting NLWeb server on http://localhost:8080

======================================================================
What NLWeb Does (RAG Pipeline)
======================================================================
1. RETRIEVE - Search Azure AI Search for relevant items
2. RANK     - Use Azure OpenAI LLM to score each item (0-100)
3. GENERATE - Create descriptions for relevant items with LLM
4. STREAM   - Send high-scoring results back via SSE

======================================================================
Available Endpoints
======================================================================
  GET/POST /ask - Natural language query with RAG
    Parameters:
      query       - Your natural language question (required)
      site        - Filter by site (optional, default: 'all')
      num_results - Number of results (optional, default: 50)
      streaming   - Enable SSE streaming (optional, default: true)

  GET /health - Health check
  POST /mcp   - MCP protocol endpoint (JSON-RPC 2.0)

======================================================================
Test with curl
======================================================================

Non-streaming (get complete JSON response):
  curl "http://localhost:8080/ask?query=best+pasta+recipe&streaming=false"

Streaming (Server-Sent Events):
  curl "http://localhost:8080/ask?query=best+pasta+recipe"

POST with JSON body:
  curl -X POST http://localhost:8080/ask \
       -H 'Content-Type: application/json' \
       -d '{"query": "best pasta recipe", "streaming": false}'

======================================================================
What to Expect
======================================================================
The response will contain:
  - Retrieved items from your Azure AI Search index
  - Each item ranked with a relevance score (0-100)
  - LLM-generated descriptions highlighting relevance
  - Items sorted by score (highest first)

This is the full NLWeb RAG pipeline in action!
======================================================================
```

### Step 5: Test with curl

Open a new terminal and test the `/ask` endpoint:

#### Non-Streaming Example

```bash
curl "http://localhost:8080/ask?query=what+are+the+best+pasta+recipes&streaming=false"
```

**Response format:**
```json
{
  "content": [
    {
      "@type": "Recipe",
      "name": "Classic Carbonara",
      "url": "https://example.com/carbonara",
      "site": "recipes",
      "description": "An authentic Italian pasta dish with eggs, cheese, and guanciale, highly relevant for traditional pasta preparation.",
      "grounding": "https://example.com/carbonara",
      "image": "https://example.com/images/carbonara.jpg",
      "recipeYield": "4 servings",
      "cookTime": "PT20M"
    },
    {
      "@type": "Recipe",
      "name": "Aglio e Olio",
      "url": "https://example.com/aglio",
      "site": "recipes",
      "description": "A simple yet flavorful garlic and oil pasta that's quick to make and demonstrates basic pasta techniques.",
      "grounding": "https://example.com/aglio"
    }
  ],
  "_meta": {
    "version": "0.5",
    "query": "what are the best pasta recipes"
  }
}
```

#### Streaming Example

```bash
curl "http://localhost:8080/ask?query=what+are+the+best+pasta+recipes"
```

**Response format (Server-Sent Events):**
```
data: {"_meta": {"version": "0.5"}}

data: {"content": [{"@type": "Recipe", "name": "Classic Carbonara", ...}]}

data: {"content": [{"@type": "Recipe", "name": "Aglio e Olio", ...}]}

data: {"_meta": {"nlweb/streaming_status": "finished"}}
```

#### POST Example

```bash
curl -X POST http://localhost:8080/ask \
     -H 'Content-Type: application/json' \
     -d '{
       "query": "what are the best pasta recipes",
       "site": "all",
       "num_results": 10,
       "streaming": false
     }'
```

## How the RAG Pipeline Works

When you send a query to `/ask?query=best+pasta+recipe`:

1. **Retrieval**: NLWeb searches your Azure AI Search index using vector similarity
   - Generates embedding for "best pasta recipe"
   - Finds top N similar items from your indexed data

2. **Ranking**: For each retrieved item, NLWeb uses Azure OpenAI to:
   - Assign a relevance score (0-100)
   - Generate a description highlighting why it's relevant
   - Filter out items with scores below 50

3. **Streaming**: High-scoring items (>59) are immediately streamed back
   - Low-latency responses for good results
   - Complete ranking happens in background

4. **Final Response**: All items sorted by score
   - Highest relevance first
   - Each with LLM-generated description
   - Schema.org metadata preserved

## Troubleshooting

### "Module not found" errors
Make sure you installed the requirements:
```bash
pip install -r requirements.txt
```

### "Invalid API key" or "Unauthorized" errors
Check your `.env` file:
- Verify your `AZURE_OPENAI_ENDPOINT` is correct (should include `https://` and trailing `/`)
- Verify your `AZURE_OPENAI_KEY` is correct
- Make sure the `.env` file is in the same directory as `hello_world.py`

### "Deployment not found" errors
Update `config.yaml` with your actual deployment names:
- Check your Azure OpenAI resource in the Azure Portal
- Find your deployment names under "Deployments"
- Update the `models` section in `config.yaml`
- **Important**: Use the deployment name, not the model name

### "Index not found" errors
Update `config.yaml` with your actual index name:
- Check your Azure AI Search resource in the Azure Portal
- Find your index name under "Indexes"
- Update the `index_name` in `config.yaml`

### "No results returned" or empty content
This usually means:
- Your index is empty or has no matching items
- The query doesn't match your indexed data well
- Try a query that matches your actual indexed content

### Server starts but curl fails
- Check the server is actually running (you should see startup messages)
- Verify you're using the correct URL: `http://localhost:8080`
- Check for firewall issues blocking port 8080

## Using Managed Identity Instead of API Keys

For production deployments, use managed identity instead of API keys:

1. **Update `config.yaml`**:
   ```yaml
   llm:
     auth_method: azure_ad  # Change from api_key

   embedding:
     auth_method: azure_ad

   retrieval:
     auth_method: azure_ad
   ```

2. **Update `.env`** (only need endpoints):
   ```bash
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_SEARCH_ENDPOINT=https://your-service.search.windows.net
   # No *_KEY variables needed
   ```

3. **Configure Azure identity**:
   - Assign managed identity to your application
   - Grant "Cognitive Services OpenAI User" role
   - Grant "Search Index Data Reader" role

## Advanced Usage

### Custom Prompts

The ranking prompt can be customized by modifying the `Ranking` class in your application.

### Multiple Sites

Filter by site using the `site` parameter:
```bash
curl "http://localhost:8080/ask?query=pasta+recipe&site=italian_cuisine"
```

### Adjusting Result Count

Control how many items are retrieved and ranked:
```bash
curl "http://localhost:8080/ask?query=pasta+recipe&num_results=20"
```

### MCP Protocol Support

NLWeb also supports the Model Context Protocol (MCP) for integration with Claude Desktop and other MCP clients:

```bash
# Test MCP endpoint
npx @modelcontextprotocol/inspector http://localhost:8080/mcp
```

## Next Steps

Once the hello world is working:

1. **Index your own data**: Load your content into Azure AI Search
   - Use the Azure AI Search SDK to create and populate indexes
   - Ensure schema.org markup for best results

2. **Customize ranking**: Adjust the ranking prompt for your use case
   - Modify scoring criteria
   - Change description generation

3. **Build a frontend**: Create a UI that calls the `/ask` endpoint
   - Use SSE for streaming responses
   - Display ranked results with descriptions

4. **Deploy to production**: Use managed identity and proper secrets management
   - Set up Azure App Service or Container Apps
   - Configure managed identity
   - Use Azure Key Vault for secrets

## File Structure

```
azure_hello_world/
├── README.md           # This file
├── requirements.txt    # Package dependencies
├── config.yaml         # NLWeb configuration (single unified file)
├── .env.example        # Example environment variables
├── .env               # Your actual credentials (create this)
└── hello_world.py     # Server startup script
```

## Learn More

- **Package Documentation**: See `packages/PACKAGE_STRUCTURE.md`
- **Core Framework**: See `packages/core/README.md`
- **Azure Providers**: See `packages/providers/azure/*/README.md`
- **Other Examples**: See `packages/examples/`
- **Installation Guide**: See `INSTALLATION_GUIDE.md`

## Support

If you encounter issues:
1. Check this README's troubleshooting section
2. Review the package documentation
3. Check the Azure Portal for resource configuration
4. Verify your environment variables are set correctly
5. Check the server logs for detailed error messages

## License

MIT License - Copyright (c) 2025 Microsoft Corporation
