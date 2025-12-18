# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Unified vector database interface with support for Azure AI Search, Milvus, and Qdrant.
This module provides abstract base classes and concrete implementations for database operations.
"""

import os
import time
import asyncio
from abc import ABC, abstractmethod
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from typing import List, Dict, Any, Optional, Union, Tuple, Type
import json
from nlweb_core.config import CONFIG

# Client cache for reusing instances
_client_cache = {}
_client_cache_lock = asyncio.Lock()

# Preloaded client modules
_preloaded_modules = {}

# Object lookup client cache
_object_lookup_client = None
_object_lookup_lock = asyncio.Lock()

def init():
    """Initialize retrieval clients based on configuration."""
    # Preload modules for enabled endpoints using config-driven dynamic imports
    for endpoint_name, endpoint_config in CONFIG.retrieval_endpoints.items():
        if endpoint_config.enabled and endpoint_config.import_path and endpoint_config.class_name:
            try:
                # Preload using config
                import_path = endpoint_config.import_path
                class_name = endpoint_config.class_name
                module = __import__(import_path, fromlist=[class_name])
                client_class = getattr(module, class_name)
                _preloaded_modules[endpoint_config.db_type] = client_class
            except Exception as e:
                # Silently skip preload failures - will load on demand
                pass


class VectorDBClientInterface(ABC):
    """
    Abstract base class defining the interface for vector database clients.
    All vector database implementations should implement the search method.
    """

    @abstractmethod
    async def search(self, query: str, site: Union[str, List[str]],
                    num_results: int = 50, **kwargs) -> List[List[str]]:
        """
        Search for documents matching the query and site.

        Args:
            query: Search query string
            site: Site identifier or list of sites
            num_results: Maximum number of results to return
            **kwargs: Additional parameters

        Returns:
            List of search results, where each result is [url, json_str, name, site]
        """
        pass


class ObjectLookupInterface(ABC):
    """
    Abstract base class for looking up full objects by their ID.
    Implementations should fetch complete object data from storage (e.g., Cosmos DB).
    """

    @abstractmethod
    async def get_by_id(self, object_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a complete object by its ID.

        Args:
            object_id: The unique identifier for the object (e.g., URL/@id)

        Returns:
            Complete object as dictionary, or None if not found
        """
        pass


class CosmosObjectLookup(ObjectLookupInterface):
    """
    Cosmos DB implementation for object lookup.
    Uses Azure AD authentication (DefaultAzureCredential).
    """

    def __init__(self):
        """Initialize Cosmos DB client using CONFIG.object_storage."""
        if not CONFIG.object_storage or not CONFIG.object_storage.enabled:
            raise ValueError("Object storage is not enabled in configuration")



        self.config = CONFIG.object_storage
        
        if not self.config.endpoint:
            raise ValueError("Cosmos DB endpoint not configured")

        # Always use Azure AD authentication
        credential = DefaultAzureCredential()
        self.client = CosmosClient(self.config.endpoint, credential=credential)
        
        # Get database and container
        self.database = self.client.get_database_client(self.config.database_name)
        self.container = self.database.get_container_client(self.config.container_name)

    async def get_by_id(self, object_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve object from Cosmos DB by @id field.

        Args:
            object_id: The @id value (typically a URL)

        Returns:
            Complete object dictionary or None if not found
        """
        try:
            # Query by @id field
            query = "SELECT * FROM c WHERE c['@id'] = @object_id"
            parameters = [{"name": "@object_id", "value": object_id}]

            # Execute query in executor to avoid blocking
            def execute_query():
                items = list(self.container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=True
                ))
                return items[0] if items else None

            result = await asyncio.get_event_loop().run_in_executor(None, execute_query)
            return result

        except Exception as e:
            print(f"Error fetching object {object_id} from Cosmos DB: {e}")
            return None


async def get_object_lookup_client() -> Optional[ObjectLookupInterface]:
    """
    Get or create the object lookup client based on configuration.
    
    Returns:
        ObjectLookupInterface instance or None if not configured
    """
    global _object_lookup_client
    # Check if object storage is enabled
    if not CONFIG.object_storage or not CONFIG.object_storage.enabled:
        return None
    
    async with _object_lookup_lock:
        if _object_lookup_client is None:
            # Only Cosmos DB is supported for now
            if CONFIG.object_storage.type == "cosmos":
                _object_lookup_client = CosmosObjectLookup()
            else:
                raise ValueError(f"Unsupported object storage type: {CONFIG.object_storage.type}")
        
        return _object_lookup_client


async def enrich_results_from_object_storage(results: List[List[str]]) -> List[List[str]]:
    """
    Enrich vector DB results with full content from object storage.
    Replaces the potentially empty content with complete object data from Cosmos DB.

    Args:
        results: Vector DB results in format [url, json_str, name, site]

    Returns:
        Enriched results with full content from object storage
    """
    client = await get_object_lookup_client()
    if not client:
        return results
    enriched_results = []
    for result in results:
        url, json_str, name, site = result
        
        # Fetch full object from Cosmos DB using URL as @id
        full_object = await client.get_by_id(url)
        
        if full_object:
            # Replace content with full object JSON
            full_json_str = json.dumps(full_object)
            enriched_results.append([url, full_json_str, name, site])
        else:
            # Keep original if not found in object storage
            enriched_results.append(result)
    
    return enriched_results




class VectorDBClient:
    """
    Client for vector database operations using a single retrieval endpoint.
    """

    def __init__(self, endpoint_name: Optional[str] = None, query_params: Optional[Dict[str, Any]] = None):
        """
        Initialize the database client with a single endpoint.

        Args:
            endpoint_name: Name of the endpoint to use
            query_params: Optional query parameters (kept for backward compatibility)
        """
        self.query_params = query_params or {}

        # Require an endpoint name
        if not endpoint_name:
            # Use first enabled endpoint with valid credentials
            for name, config in CONFIG.retrieval_endpoints.items():
                if config.enabled and self._has_valid_credentials(name, config):
                    endpoint_name = name
                    break

            if not endpoint_name:
                raise ValueError("No endpoint specified and no enabled endpoints with valid credentials found")

        # Validate the endpoint
        if endpoint_name not in CONFIG.retrieval_endpoints:
            available_endpoints = list(CONFIG.retrieval_endpoints.keys())
            raise ValueError(f"Invalid endpoint: '{endpoint_name}'. Available endpoints: {', '.join(available_endpoints)}")

        endpoint_config = CONFIG.retrieval_endpoints[endpoint_name]

        # Validate credentials
        if not self._has_valid_credentials(endpoint_name, endpoint_config):
            raise ValueError(f"Endpoint '{endpoint_name}' is missing required credentials")

        self.endpoint_name = endpoint_name
        self.endpoint_config = endpoint_config
        self.db_type = endpoint_config.db_type

        
    def _has_valid_credentials(self, name: str, config) -> bool:
        """
        Check if an endpoint has valid credentials based on its database type.
        
        Args:
            name: Endpoint name
            config: Endpoint configuration
            
        Returns:
            True if endpoint has required credentials
        """
        db_type = config.db_type
        
        # Generic credential validation:
        # - If has database_path, assume local storage (always valid)
        # - Otherwise, check for api_endpoint (remote storage needs endpoint)
        # - api_key is optional for most providers
        if config.database_path:
            return True  # Local file-based storage
        elif config.api_endpoint:
            return True  # Remote storage with endpoint
        elif config.import_path:
            # If import_path is configured, assume it's valid (provider may not need credentials)
            return True
        else:
            return False
    
    async def get_client(self) -> VectorDBClientInterface:
        """
        Get or initialize the vector database client for this endpoint.
        Uses a cache to avoid creating duplicate client instances.

        Returns:
            Appropriate vector database client
        """
        # Use cache key combining db_type and endpoint
        cache_key = f"{self.db_type}_{self.endpoint_name}"

        # Check if client already exists in cache
        async with _client_cache_lock:
            if cache_key in _client_cache:
                return _client_cache[cache_key]

            # Create the appropriate client using config-driven dynamic import
            try:
                # Use preloaded module if available
                if self.db_type in _preloaded_modules:
                    client_class = _preloaded_modules[self.db_type]
                # Otherwise use config to dynamically import
                elif self.endpoint_config.import_path and self.endpoint_config.class_name:
                    # Dynamic import based on config
                    import_path = self.endpoint_config.import_path
                    class_name = self.endpoint_config.class_name
                    module = __import__(import_path, fromlist=[class_name])
                    client_class = getattr(module, class_name)
                else:
                    error_msg = f"No import_path and class_name configured for: {self.db_type}"
                    raise ValueError(error_msg)

                # Instantiate the client
                client = client_class(self.endpoint_name)
            except ImportError as e:
                raise ValueError(f"Failed to load client for {self.db_type}: {e}")

            # Store in cache and return
            _client_cache[cache_key] = client
            return client
    
    
    async def search(self, query: str, site: Union[str, List[str]],
                    num_results: int = 50, enrich_from_storage: bool = True, **kwargs) -> List[List[str]]:
        """
        Search for documents matching the query and site.

        Args:
            query: Search query string
            site: Site identifier or list of sites
            num_results: Maximum number of results to return
            enrich_from_storage: If True, fetch full content from object storage (default: True)
            **kwargs: Additional parameters

        Returns:
            List of search results
        """
        client = await self.get_client()
        results = await client.search(query, site, num_results, **kwargs)
        # Optionally enrich with full content from object storage
        if enrich_from_storage:
            results = await enrich_results_from_object_storage(results)
        
        return results


# Factory function to make it easier to get a client with the right type
def get_vector_db_client(endpoint_name: Optional[str] = None, 
                        query_params: Optional[Dict[str, Any]] = None) -> VectorDBClient:
    """
    Factory function to create a vector database client with the appropriate configuration.
    Uses a global cache to avoid repeated initialization and site queries.
    
    Args:
        endpoint_name: Optional name of the endpoint to use
        query_params: Optional query parameters for overriding endpoint
        
    Returns:
        Configured VectorDBClient instance (cached if possible)
    """
    global _client_cache
    
    # Create a cache key based on endpoint_name
    # Note: We don't include query_params in the key since they're typically the same
    cache_key = endpoint_name or 'default'
    
    # Check if we have a cached client
    if cache_key in _client_cache:
        return _client_cache[cache_key]
    
    # Create a new client and cache it
    client = VectorDBClient(endpoint_name=endpoint_name, query_params=query_params)
    _client_cache[cache_key] = client
    
    return client




async def search(query: str,
                site: str = "all",
                num_results: int = 50,
                endpoint_name: Optional[str] = None,
                query_params: Optional[Dict[str, Any]] = None,
                handler: Optional[Any] = None,
                enrich_from_storage: bool = True,
                **kwargs) -> List[Dict[str, Any]]:
    """
    Simplified search interface that combines client creation and search in one call.
    
    Args:
        query: The search query
        site: Site to search in (default: "all")
        num_results: Number of results to return (default: 50)
        endpoint_name: Optional name of the endpoint to use
        query_params: Optional query parameters for overriding endpoint
        handler: Optional handler with http_handler for sending messages
        enrich_from_storage: If True, fetch full content from object storage (default: True)
        **kwargs: Additional parameters passed to the search method
        
    Returns:
        List of search results
        
    Example:
        results = await search("climate change", site="example.com", num_results=5)
    """
    client = get_vector_db_client(endpoint_name=endpoint_name, query_params=query_params)

    return await client.search(query, site, num_results, enrich_from_storage=enrich_from_storage, **kwargs)


