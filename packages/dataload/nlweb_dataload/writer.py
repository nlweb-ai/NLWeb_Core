# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Vector database writer interface - separate from read-only retriever interface.

This module provides write operations (upload/delete) for vector databases.
Kept separate from nlweb_core.retriever to maintain read/write separation.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .config import CONFIG

# Client cache for reusing instances
_writer_cache = {}
_writer_cache_lock = asyncio.Lock()


class VectorDBWriterInterface(ABC):
    """
    Abstract base class for vector database write operations.
    Separate from VectorDBClientInterface (read-only) to maintain clean separation.
    """

    @abstractmethod
    async def upload_documents(self, documents: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        Upload/upsert documents to the vector database.

        Args:
            documents: List of document dictionaries with fields like:
                - id: Unique document identifier (optional, auto-generated if not provided)
                - url: Document URL
                - type: Document type (e.g., "Movie", "Article", "Product")
                - site: Site identifier
                - content: Document content (typically JSON string of schema.org data)
                - embedding: Vector embedding (list of floats)
                - timestamp: Optional timestamp
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict with upload results (e.g., count, errors)
        """
        pass

    @abstractmethod
    async def delete_documents(self, filter_criteria: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Delete documents matching filter criteria.

        Args:
            filter_criteria: Provider-specific filter (e.g., {"site": "example.com"})
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict with deletion results (e.g., count)
        """
        pass

    async def delete_site(self, site: str, **kwargs) -> Dict[str, Any]:
        """
        Delete all documents for a specific site.

        Default implementation uses delete_documents with site filter.
        Providers can override for more efficient implementations.

        Args:
            site: Site identifier
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict with deletion results
        """
        return await self.delete_documents({"site": site}, **kwargs)


class VectorDBWriter:
    """
    Writer client for vector database operations using a single endpoint.
    Parallel to VectorDBClient but for write operations.
    """

    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the writer client with an endpoint.

        Args:
            endpoint_name: Name of the endpoint to use
        """
        # Use write_endpoint from config if not specified
        if not endpoint_name:
            endpoint_name = CONFIG.write_endpoint

        if not endpoint_name:
            raise ValueError("No endpoint specified and no write_endpoint configured")

        # Get endpoint config (this validates it exists)
        self.endpoint_config = CONFIG.get_database_endpoint(endpoint_name)
        self.endpoint_name = endpoint_name
        self.db_type = self.endpoint_config.get('db_type')

    async def get_writer(self) -> VectorDBWriterInterface:
        """
        Get or initialize the vector database writer for this endpoint.
        Uses a cache to avoid creating duplicate writer instances.

        Returns:
            Appropriate vector database writer
        """
        cache_key = f"{self.db_type}_{self.endpoint_name}"

        async with _writer_cache_lock:
            if cache_key in _writer_cache:
                return _writer_cache[cache_key]

            # Get writer configuration from endpoint
            writer_config = self.endpoint_config.get('writer')
            if not writer_config:
                raise ValueError(
                    f"No writer configuration found for endpoint {self.endpoint_name}. "
                    f"Add 'writer' section with import_path and class_name to config."
                )

            # Dynamic import based on config
            import_path = writer_config.get('import_path')
            class_name = writer_config.get('class_name')

            if not import_path or not class_name:
                raise ValueError(
                    f"Writer configuration for {self.endpoint_name} missing "
                    f"import_path or class_name"
                )

            try:
                module = __import__(import_path, fromlist=[class_name])
                writer_class = getattr(module, class_name)
                writer = writer_class(self.endpoint_name)
            except ImportError as e:
                raise ValueError(f"Failed to load writer for {self.db_type}: {e}")

            # Store in cache and return
            _writer_cache[cache_key] = writer
            return writer

    async def upload_documents(self, documents: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """Upload documents to the database."""
        writer = await self.get_writer()
        return await writer.upload_documents(documents, **kwargs)

    async def delete_documents(self, filter_criteria: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Delete documents matching filter criteria."""
        writer = await self.get_writer()
        return await writer.delete_documents(filter_criteria, **kwargs)

    async def delete_site(self, site: str, **kwargs) -> Dict[str, Any]:
        """Delete all documents for a site."""
        writer = await self.get_writer()
        return await writer.delete_site(site, **kwargs)


def get_vector_db_writer(endpoint_name: Optional[str] = None) -> VectorDBWriter:
    """
    Factory function to create a vector database writer.
    Parallel to get_vector_db_client from nlweb_core.retriever.

    Args:
        endpoint_name: Optional name of the endpoint to use

    Returns:
        Configured VectorDBWriter instance (cached)
    """
    global _writer_cache

    # Create a cache key
    cache_key = f"writer_{endpoint_name or 'default'}"

    # Check if we have a cached writer
    if cache_key in _writer_cache:
        return _writer_cache[cache_key]

    # Create a new writer and cache it
    writer = VectorDBWriter(endpoint_name=endpoint_name)
    _writer_cache[cache_key] = writer

    return writer
