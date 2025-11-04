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

# Import NLWeb
import nlweb_core
from nlweb_network.server import main as run_server


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
    config_path = Path(__file__).parent / "config.yaml"
    nlweb_core.init(config_path=str(config_path))

    # Get config for display
    from nlweb_core.config import CONFIG
    host = CONFIG.server.host
    port = CONFIG.port

    # Create and start the server
    print(f"NLWeb server starting on http://{host}:{port}")

    # Start the NLWeb network server
    run_server()


if __name__ == "__main__":
    main()
