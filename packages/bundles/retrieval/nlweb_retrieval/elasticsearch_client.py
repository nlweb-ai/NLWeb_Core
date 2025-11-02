# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Elasticsearch Client - Interface for Elasticsearch operations.
"""

import time
import uuid
import threading
from typing import List, Dict, Union, Optional, Any

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from nlweb_core.config import CONFIG
from nlweb_core.retriever import VectorDBClientInterface
from nlweb_core.embedding import get_embedding


class ElasticsearchClient(VectorDBClientInterface):
    """
    Client for Elasticsearch operations, providing a unified interface for 
    vector-based search results using the Elasticsearch Python client.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Elasticsearch client.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        super().__init__()  # Initialize the base class with caching
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        self._client_lock = threading.Lock()
        self._es_clients = {}  # Cache for Elasticsearch clients

        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        # Handle None values from configuration
        self.api_endpoint = self.endpoint_config.api_endpoint
        self.api_key = self.endpoint_config.api_key
        self.default_index_name = self.endpoint_config.index_name or "embeddings"
        
        if self.api_endpoint is None:
            raise ValueError(f"API endpoint not configured for {self.endpoint_name}. Check environment variable configuration.")
        if self.api_key is None:
            raise ValueError(f"API key not configured for {self.endpoint_name}. Check environment variable configuration.")
            
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def close(self):
        """Close the Elasticsearch client connections"""
        if self._es_clients:
            try:
                for each_client in self._es_clients.values():
                    await each_client.close()
            except Exception as e:
                pass
            finally:
                self._es_clients = {}
    
    def _get_endpoint_config(self):
        """Get the Elasticsearch endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)

        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            raise ValueError(error_msg)
        
        # Verify this is an Elasticsearch endpoint
        if endpoint_config.db_type != "elasticsearch":
            error_msg = f"Endpoint {self.endpoint_name} is not an Elasticsearch endpoint (type: {endpoint_config.db_type})"
            raise ValueError(error_msg)
            
        return endpoint_config
    
    def _create_client_params(self):
        """Extract client parameters from endpoint config."""
        params = {}

        # Check for URL-based connection
        params["hosts"] = self.api_endpoint
        params["api_key"] = self.api_key

        return params
    
    def _create_vector_properties(self):
        """Extract embedding properties from endpoint config."""
        params = {}
        
        params = self.endpoint_config.vector_type
        if params is None:
            # Set the default as dense_vector
            return {
                'type': 'dense_vector'
            }
        
        return params
    
    async def _get_es_client(self) -> AsyncElasticsearch:
        """
        Get or initialize Elasticsearch client.
        
        Returns:
            AsyncElasticsearch: Elasticsearch async client instance
        """
        client_key = self.endpoint_name
        
        # First check if we already have a client
        with self._client_lock:
            if client_key in self._es_clients:
                return self._es_clients[client_key]
        
        # If not, create a new client (outside the lock to avoid deadlocks during async init)
        try:
            
            params = self._create_client_params()
            # Create client with the determined parameters
            client = AsyncElasticsearch(**params)
            
            # Test connection by getting information
            await client.info()
            
            # Store in cache with lock
            with self._client_lock:
                self._es_clients[client_key] = client
            
            return client
            
        except Exception as e:
            raise
            
    async def _format_es_response(self, response: Dict[str, Any]) -> List[List[str]]:
        """ 
        Converts the Elasticsearch response in a list of values [url, schema_json, name, site_name]

        Args:
            response (List[Dict[str, Any]]): the Elasticsearch response

        Returns:
            List[List[str]]: the list of values [url, schema_json, name, site_name]
        """
        processed_results = []
        for hit in response['hits']['hits']:
            source = hit.get('_source', {})
            url = source.get('url', '')
            schema_json = source.get('schema_json', '{}')
            name = source.get('name', '')
            site_name = source.get('site', '')
            processed_results.append([url, schema_json, name, site_name])
            
        return processed_results
    
    async def _search_knn_filter(self, index_name: str, embedding: List[float],
                                 k: int, source: List[str], filter: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Search in Elasticsearch using kNN and filter
        
        Args:
            index_name: The index name
            embedding: The vector embedding to search
            k: The maximum number of documents to be returned
            source: The list of fields to be returned
            filter: Optional filter in kNN (e.g. {'terms': {'site' : '...'}})
        Returns:
            Dict[str, Any]: Elasticsearch response
        """
        client = await self._get_es_client()
        
        search_query = {
            "knn": {
                "field": "embedding",
                "query_vector": embedding,
                "k": k
            }
        }
        if filter:
            search_query['knn']['filter'] = filter

        try:
            return await client.search(index=index_name, query=search_query, source=source, size=k)
        except Exception as e:
            raise
        
    async def search(self, query: str, site: Union[str, List[str]],
                    num_results: int = 50, query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search for documents matching the query and site using vector similarity.
        
        Args:
            query: Search query string
            site: Site identifier or list of sites
            num_results: Maximum number of results to return
            query_params: Query parameters for embedding generation
            **kwargs: Additional parameters
            
        Returns:
            List[List[str]]: List of search results [url, schema_json, name, site]
        """
        index_name = kwargs.get('index_name', self.default_index_name)
        
        start_embed = time.time()
        embedding = await get_embedding(query, query_params=query_params)
        embed_time = time.time() - start_embed
        
        # Handle both single site and multiple sites
        if isinstance(site, str):
            sites = [site]
        else:
            sites = site
        
        # Build site filter
        if len(sites) == 1:
            filter = {"term": {"site": sites[0]}}
        else:
            filter = {"terms": {"site": sites}}
                
        source = ["url", "site", "schema_json", "name"]
        start_retrieve = time.time()
        # Execute Elasticsearch query with kNN vector search and filter
        response = await self._search_knn_filter(
            index_name=index_name,
            embedding=embedding,
            k=num_results,
            source=source,
            filter=filter
        )
        retrieve_time = time.time() - start_retrieve

        results = await self._format_es_response(response)
        return results
    
