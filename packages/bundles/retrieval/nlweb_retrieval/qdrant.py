# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Qdrant Vector Database Client - Interface for Qdrant operations.
"""

import os
import sys
import threading
import time
import uuid
import json
from typing import List, Dict, Union, Optional, Any, Tuple, Set

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from nlweb_core.config import CONFIG
from nlweb_core.embedding import get_embedding
from nlweb_core.retriever import VectorDBClientInterface


class QdrantVectorClient(VectorDBClientInterface):
    """
    Client for Qdrant vector database operations, providing a unified interface for 
    indexing, storing, and retrieving vector-based search results.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Qdrant vector database client.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        super().__init__()  # Initialize the base class with caching
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        self._client_lock = threading.Lock()
        self._qdrant_clients = {}  # Cache for Qdrant clients
        
        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        self.api_endpoint = self.endpoint_config.api_endpoint
        self.api_key = self.endpoint_config.api_key
        self.database_path = self.endpoint_config.database_path
        self.default_collection_name = self.endpoint_config.index_name or "nlweb_collection"
        
        if self.api_endpoint:
            pass
        elif self.database_path:
            pass

    def _get_endpoint_config(self):
        """Get the Qdrant endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            raise ValueError(error_msg)
        
        # Verify this is a Qdrant endpoint
        if endpoint_config.db_type != "qdrant":
            error_msg = f"Endpoint {self.endpoint_name} is not a Qdrant endpoint (type: {endpoint_config.db_type})"
            raise ValueError(error_msg)
            
        return endpoint_config
    
    def _resolve_path(self, path: str) -> str:
        """
        Resolve relative paths to absolute paths.
        
        Args:
            path: The path to resolve
            
        Returns:
            str: Absolute path
        """
        if os.path.isabs(path):
            return path
            
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up to the project root directory (assuming this file is in a subdirectory)
        project_root = os.path.dirname(current_dir)
        
        # Handle different relative path formats
        if path.startswith('./'):
            resolved_path = os.path.join(project_root, path[2:])
        elif path.startswith('../'):
            resolved_path = os.path.join(os.path.dirname(project_root), path[3:])
        else:
            resolved_path = os.path.join(project_root, path)
        
        # Ensure directory exists
        directory = os.path.dirname(resolved_path)
        os.makedirs(directory, exist_ok=True)
        
        return resolved_path
    
    def _create_client_params(self):
        """Extract client parameters from endpoint config."""
        params = {}

        # Check for URL-based connection
        url = self.api_endpoint
        api_key = self.api_key
        path = self.database_path

        # Decide whether to use URL or path-based connection
        if url and url.startswith(("http://", "https://")):
            params["url"] = url
            if api_key:
                params["api_key"] = api_key
        elif path:
            # Resolve relative paths for local file-based storage
            resolved_path = self._resolve_path(path)
            params["path"] = resolved_path
        else:
            # Default to a local path if neither URL nor path is specified
            default_path = self._resolve_path("../data/db")
            params["path"] = default_path
        
        return params
    
    async def _get_qdrant_client(self) -> AsyncQdrantClient:
        """
        Get or initialize Qdrant client.
        
        Returns:
            AsyncQdrantClient: Qdrant client instance
        """
        client_key = self.endpoint_name
        
        # First check if we already have a client
        with self._client_lock:
            if client_key in self._qdrant_clients:
                return self._qdrant_clients[client_key]
        
        # If not, create a new client (outside the lock to avoid deadlocks during async init)
        try:
            
            params = self._create_client_params()
            
            # Create client with the determined parameters
            client = AsyncQdrantClient(**params)
            
            # Test connection by getting collections
            collections = await client.get_collections()
            
            # Store in cache with lock
            with self._client_lock:
                self._qdrant_clients[client_key] = client
            
            return client
            
        except Exception as e:
            
            # If we failed with the URL endpoint, try a fallback to local file-based storage
            if self.api_endpoint and "Connection refused" in str(e):
                
                # Create a default local client as fallback
                default_path = self._resolve_path("../data/db")
                
                fallback_client = AsyncQdrantClient(path=default_path)
                
                # Test connection
                await fallback_client.get_collections()
                
                # Store in cache with lock
                with self._client_lock:
                    self._qdrant_clients[client_key] = fallback_client
                
                return fallback_client
            else:
                raise
    
    def _create_site_filter(self, site: Union[str, List[str]]):
        """
        Create a Qdrant filter for site filtering.
        
        Args:
            site: Site or list of sites to filter by
            
        Returns:
            Optional[models.Filter]: Qdrant filter object or None for all sites
        """
        if site == "all":
            return None

        if isinstance(site, list):
            sites = site
        elif isinstance(site, str):
            sites = [site]
        else:
            sites = []

        return models.Filter(
            must=[models.FieldCondition(key="site", match=models.MatchAny(any=sites))]
        )
    
    def _format_results(self, search_result: List[models.ScoredPoint]) -> List[List[str]]:
        """
        Format Qdrant search results to match expected API: [url, text_json, name, site].
        
        Args:
            search_result: Qdrant search results
            
        Returns:
            List[List[str]]: Formatted results
        """
        results = []
        for item in search_result:
            payload = item.payload
            url = payload.get("url", "")
            schema = payload.get("schema_json", "")
            name = payload.get("name", "")
            site_name = payload.get("site", "")

            results.append([url, schema, name, site_name])

        return results
    
    async def search(self, query: str, site: Union[str, List[str]],
                   num_results: int = 50, collection_name: Optional[str] = None,
                   query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search the Qdrant collection for records filtered by site and ranked by vector similarity.
        
        Args:
            query: The search query to embed and search with
            site: Site to filter by (string or list of strings)
            num_results: Maximum number of results to return
            collection_name: Optional collection name (defaults to configured name)
            query_params: Additional query parameters
            
        Returns:
            List[List[str]]: List of search results in format [url, text_json, name, site]
        """
        collection_name = collection_name or self.default_collection_name
        
        try:
            start_embed = time.time()
            embedding = await get_embedding(query, query_params=query_params)
            embed_time = time.time() - start_embed
            
            start_retrieve = time.time()
            
            # Get client and prepare filter
            client = await self._get_qdrant_client()
            filter_condition = self._create_site_filter(site)
            
            # Ensure collection exists before searching
            collection_created = not await self.ensure_collection_exists(collection_name, len(embedding))
            if collection_created:
                results = []
            else:
                # Perform the search
                search_result = (
                    await client.search(
                        collection_name=collection_name,
                        query_vector=embedding,
                        limit=num_results,
                        query_filter=filter_condition,
                        with_payload=True,
                    )
                )
                
                # Format the results
                results = self._format_results(search_result)

            retrieve_time = time.time() - start_retrieve

            return results
            
        except Exception as e:
            
            # Try fallback if we're using a URL endpoint and it fails
            if self.api_endpoint and "Connection refused" in str(e):
                # Create a new client with local path as fallback
                self.api_endpoint = None  # Disable URL for fallback
                
                # Clear client cache to force recreation
                with self._client_lock:
                    self._qdrant_clients = {}
                    
                # Try search again with new local client
                return await self.search(query, site, num_results, collection_name, query_params)

            raise