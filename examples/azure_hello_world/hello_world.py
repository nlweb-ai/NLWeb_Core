#!/usr/bin/env python3
"""
NLWeb Azure Hello World Example

This example demonstrates NLWeb's core RAG (Retrieval-Augmented Generation) functionality:
1. Retrieves relevant items from Azure AI Search based on natural language queries
2. Uses Azure OpenAI LLM to rank each item (0-100 relevance score)
3. Generates descriptions for relevant items using the LLM
4. Streams high-scoring results back to the client via Server-Sent Events

This is what NLWeb does - it's not just calling LLM/embedding APIs,
it's a complete RAG pipeline with LLM-powered ranking!
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import NLWeb core
import nlweb_core
from nlweb_core.simple_server import create_app
from aiohttp import web


def main():
    """Start the NLWeb server."""

    # Check if .env file exists
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("WARNING: .env file not found!")
        print("Please copy .env.example to .env and fill in your Azure credentials")
        print()
        return

    # Initialize NLWeb with config
    print("=" * 70)
    print("NLWeb Azure Hello World - RAG Server")
    print("=" * 70)
    print()

    config_path = Path(__file__).parent / "config.yaml"
    nlweb_core.init(config_path=str(config_path))
    print("✓ Configuration loaded successfully")
    print()

    # Get config for display
    from nlweb_core.config import CONFIG
    host = CONFIG.server.host
    port = CONFIG.port

    # Create and start the server
    print(f"Starting NLWeb server on http://{host}:{port}")
    print()
    print("=" * 70)
    print("What NLWeb Does (RAG Pipeline)")
    print("=" * 70)
    print("1. RETRIEVE - Search Azure AI Search for relevant items")
    print("2. RANK     - Use Azure OpenAI LLM to score each item (0-100)")
    print("3. GENERATE - Create descriptions for relevant items with LLM")
    print("4. STREAM   - Send high-scoring results back via SSE")
    print()
    print("=" * 70)
    print("Available Endpoints")
    print("=" * 70)
    print(f"  GET/POST /ask - Natural language query with RAG")
    print(f"    Parameters:")
    print(f"      query       - Your natural language question (required)")
    print(f"      site        - Filter by site (optional, default: 'all')")
    print(f"      num_results - Number of results (optional, default: 50)")
    print(f"      streaming   - Enable SSE streaming (optional, default: true)")
    print()
    print(f"  GET /health - Health check")
    print(f"  POST /mcp   - MCP protocol endpoint (JSON-RPC 2.0)")
    print()
    print("=" * 70)
    print("Test with curl")
    print("=" * 70)
    print()
    print("Non-streaming (get complete JSON response):")
    print(f"  curl \"http://{host}:{port}/ask?query=best+pasta+recipe&streaming=false\"")
    print()
    print("Streaming (Server-Sent Events):")
    print(f"  curl \"http://{host}:{port}/ask?query=best+pasta+recipe\"")
    print()
    print("POST with JSON body:")
    print(f"  curl -X POST http://{host}:{port}/ask \\")
    print(f"       -H 'Content-Type: application/json' \\")
    print(f"       -d '{{\"query\": \"best pasta recipe\", \"streaming\": false}}'")
    print()
    print("=" * 70)
    print("What to Expect")
    print("=" * 70)
    print("The response will contain:")
    print("  - Retrieved items from your Azure AI Search index")
    print("  - Each item ranked with a relevance score (0-100)")
    print("  - LLM-generated descriptions highlighting relevance")
    print("  - Items sorted by score (highest first)")
    print()
    print("This is the full NLWeb RAG pipeline in action!")
    print("=" * 70)
    print()

    # Create and run the app
    app = create_app()
    web.run_app(app, host=host, port=port, print=lambda x: None)  # Suppress aiohttp's own startup message


if __name__ == "__main__":
    main()
