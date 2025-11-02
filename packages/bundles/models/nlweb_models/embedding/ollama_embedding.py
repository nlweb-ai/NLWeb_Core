# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Ollama embedding implementation.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import json
import asyncio
import threading
from typing import List, Optional
from ollama import AsyncClient
from nlweb_core.config import CONFIG



# Global client with thread-safe initialization
_client_lock = threading.Lock()
ollama_client = None


def get_ollama_endpoint():
    """Get the Ollama endpoint from configuration."""
    provider_config = CONFIG.get_embedding_provider("ollama")
    if provider_config and provider_config.endpoint:
        endpoint = provider_config.endpoint
        if endpoint:
            endpoint = endpoint.strip('"')  # Remove quotes if present
            return endpoint
        
    error_msg = "Ollama endpoint not found in config"
    raise ValueError(error_msg)


def get_ollama_client():
    """Get or initialize the Ollama client."""
    global ollama_client
    with _client_lock:  # Thread-safe client initialization
        if ollama_client is None:
            endpoint = get_ollama_endpoint()

            if not all([endpoint]):
                error_msg = "Missing required Ollama configuration"
                raise ValueError(error_msg)

            try:
                ollama_client = AsyncClient(host=endpoint)
            except Exception as e:
                raise

    return ollama_client


async def get_ollama_embedding(
    text: str, model: Optional[str] = None, timeout: float = 300.0
) -> List[float]:
    """
    Generate embeddings using Ollama.

    Args:
        text: The text to embed
        model: The model name to use (optional)
        timeout: Maximum time to wait for the embedding response in seconds

    Returns:
        List of floats representing the embedding vector
    """
    client = get_ollama_client()

    # If model is not provided, get from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("ollama")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common embedding model name
            model = "llama3"


    try:
        response = await asyncio.wait_for(
            client.embed(input=text, model=model), timeout=timeout
        )

        embedding = response.embeddings[0]

        return embedding
    except Exception as e:
        raise


async def get_ollama_batch_embeddings(
    texts: List[str], model: str = None, timeout: float = 300.0
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts using Ollama.

    Args:
        texts: List of texts to embed
        model: The model name to use (optional)
        timeout: Maximum time to wait for the batch embedding response in seconds

    Returns:
        List of embedding vectors, each a list of floats
    """
    client = get_ollama_client()

    # If model is not provided, get from config
    if model is None:
        provider_config = CONFIG.get_embedding_provider("ollama")
        if provider_config and provider_config.model:
            model = provider_config.model
        else:
            # Default to a common embedding model name
            model = "llama3"


    try:
        response = await asyncio.wait_for(
            client.embed(input=texts, model=model), timeout=timeout
        )

        # Extract embeddings in the same order as input texts
        # embeddings = response.embeddings
        embeddings = [data for data in response.embeddings]

        return embeddings
    except Exception as e:
        raise
