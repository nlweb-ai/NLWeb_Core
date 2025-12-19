# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Elasticsearch Client - Interface for Elasticsearch operations.
"""

import time
import threading
import asyncio
from typing import List, Dict, Union, Optional, Any

from elasticsearch import AsyncElasticsearch

from nlweb_core.embedding import get_embedding
from nlweb_core.retriever import VectorDBClientInterface


class ElasticsearchClient(VectorDBClientInterface):
    """
    Client for Elasticsearch operations, providing a unified interface for
    retrieving vector-based search results.
    """

    def __init__(self, endpoint_config):
        """
        Initialize the Elasticsearch client.

        Args:
            endpoint_config: Endpoint configuration object with api_endpoint, api_key, index_name, etc.
        """
        super().__init__()
        self.endpoint_config = endpoint_config
        self._client_lock = threading.Lock()
        self._es_clients = {}  # Cache for Elasticsearch clients

        # Handle None values from configuration
        self.api_endpoint = endpoint_config.api_endpoint if hasattr(endpoint_config, 'api_endpoint') else None
        self.api_key = endpoint_config.api_key if hasattr(endpoint_config, 'api_key') else None
        self.default_index_name = endpoint_config.index_name if hasattr(endpoint_config, 'index_name') and endpoint_config.index_name else "embeddings"

        if self.api_endpoint is None:
            raise ValueError("API endpoint not configured. Check environment variable configuration.")
        if self.api_key is None:
            raise ValueError("API key not configured. Check environment variable configuration.")

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
            except Exception:
                pass
            finally:
                self._es_clients = {}


    def _create_client_params(self):
        """Extract client parameters from endpoint config."""
        params = {
            "hosts": self.api_endpoint,
            "api_key": self.api_key,
        }
        return params

    def _create_vector_properties(self):
        """Extract embedding properties from endpoint config."""
        # Default to 1536 dimensions (OpenAI text-embedding-3-small)
        vector_dims = getattr(self.endpoint_config, "vector_dimensions", 1536)
        return {
            "dims": vector_dims,
            "index": True,
            "similarity": "cosine"
        }

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
            client = AsyncElasticsearch(**params)

            # Test connection by getting information
            await client.info()

            # Store in cache with lock
            with self._client_lock:
                self._es_clients[client_key] = client

            return client

        except Exception as e:
            raise Exception(f"Failed to initialize Elasticsearch client: {str(e)}")

    async def create_index_if_not_exists(self, index_name: Optional[str] = None) -> bool:
        """
        Create an index if it doesn't already exist.

        Args:
            index_name: Name of the index to create

        Returns:
            bool: True if index was created, False if it already existed
        """
        index_name = index_name or self.default_index_name
        client = await self._get_es_client()

        # Check if index exists
        exists = await client.indices.exists(index=index_name)
        if exists:
            return False

        # Get vector properties
        vector_props = self._create_vector_properties()

        # Create index with mappings
        mappings = {
            "properties": {
                "url": {"type": "keyword"},
                "site": {"type": "keyword"},
                "name": {"type": "text"},
                "schema_json": {"type": "text"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": vector_props["dims"],
                    "index": vector_props["index"],
                    "similarity": vector_props["similarity"]
                }
            }
        }

        await client.indices.create(index=index_name, mappings=mappings)
        return True

    async def delete_index(self, index_name: Optional[str] = None) -> bool:
        """
        Delete an index.

        Args:
            index_name: Name of the index to delete

        Returns:
            bool: True if index was deleted
        """
        index_name = index_name or self.default_index_name
        client = await self._get_es_client()

        await client.indices.delete(index=index_name, ignore_unavailable=True)
        return True

    async def _format_es_response(self, response: Dict[str, Any]) -> List[List[str]]:
        """
        Format Elasticsearch response to match expected API: [url, text_json, name, site].

        Args:
            response: Elasticsearch response

        Returns:
            List[List[str]]: Formatted results
        """
        results = []
        hits = response.get("hits", {}).get("hits", [])

        for hit in hits:
            source = hit["_source"]
            url = source.get("url", "")
            schema_json = source.get("schema_json", "")
            name = source.get("name", "")
            site = source.get("site", "")

            results.append([url, schema_json, name, site])

        return results

    async def _search_knn_filter(
        self,
        index_name: str,
        embedding: List[float],
        k: int,
        source: List[str],
        filter: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Perform KNN search with optional filtering.

        Args:
            index_name: Index name
            embedding: Query embedding vector
            k: Number of results
            source: Fields to return
            filter: Optional filter query

        Returns:
            Dict[str, Any]: Elasticsearch response
        """
        client = await self._get_es_client()

        # Build KNN query
        knn = {
            "field": "embedding",
            "query_vector": embedding,
            "k": k,
            "num_candidates": k * 2  # Oversample for better accuracy
        }

        # Add filter if provided
        if filter:
            knn["filter"] = filter

        # Execute search
        response = await client.search(
            index=index_name,
            knn=knn,
            source=source,
            size=k
        )

        return response

    async def search(
        self,
        query: str,
        site: Union[str, List[str]],
        num_results: int = 50,
        query_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[List[str]]:
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
        index_name = kwargs.get("index_name", self.default_index_name)

        # Get embedding for the query
        start_embed = time.time()
        embedding = await get_embedding(query, query_params=query_params)
        embed_time = time.time() - start_embed

        # Ensure index exists
        await self.create_index_if_not_exists(index_name)

        # Build site filter
        site_filter = None
        if isinstance(site, str):
            sites = [site]
        else:
            sites = site

        # Skip filter if "all"
        if sites != ["all"] and "all" not in sites:
            if len(sites) == 1:
                site_filter = {"term": {"site": sites[0]}}
            else:
                site_filter = {"terms": {"site": sites}}

        # Perform KNN search
        start_retrieve = time.time()
        response = await self._search_knn_filter(
            index_name=index_name,
            embedding=embedding,
            k=num_results,
            source=["url", "schema_json", "name", "site"],
            filter=site_filter
        )
        retrieve_time = time.time() - start_retrieve

        # Format and return results
        results = await self._format_es_response(response)

        return results

    async def search_by_url(
        self,
        url: str,
        **kwargs
    ) -> Optional[List[str]]:
        """
        Retrieve a specific item by URL from Elasticsearch database.

        Args:
            url: URL to search for
            **kwargs: Additional parameters

        Returns:
            Optional[List[str]]: Search result or None if not found
        """
        index_name = kwargs.get("index_name", self.default_index_name)
        client = await self._get_es_client()

        # Search by URL
        response = await client.search(
            index=index_name,
            query={"term": {"url": url}},
            size=1,
            source=["url", "schema_json", "name", "site"]
        )

        hits = response.get("hits", {}).get("hits", [])
        if not hits:
            return None

        source = hits[0]["_source"]
        return [
            source.get("url", ""),
            source.get("schema_json", ""),
            source.get("name", ""),
            source.get("site", "")
        ]

    async def search_all_sites(
        self,
        query: str,
        num_results: int = 50,
        query_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[List[str]]:
        """
        Search across all sites without filtering.

        Args:
            query: Search query string
            num_results: Maximum number of results to return
            query_params: Query parameters for embedding generation
            **kwargs: Additional parameters

        Returns:
            List[List[str]]: List of search results
        """
        return await self.search(query, "all", num_results, query_params, **kwargs)

    async def get_sites(self, **kwargs) -> List[str]:
        """
        Get a list of unique site names from the Elasticsearch index.

        Args:
            **kwargs: Additional parameters

        Returns:
            List[str]: Sorted list of unique site names
        """
        index_name = kwargs.get("index_name", self.default_index_name)
        client = await self._get_es_client()

        # Check if index exists
        exists = await client.indices.exists(index=index_name)
        if not exists:
            return []

        # Use aggregation to get unique sites
        response = await client.search(
            index=index_name,
            size=0,
            aggs={
                "unique_sites": {
                    "terms": {
                        "field": "site",
                        "size": 10000  # Max unique sites
                    }
                }
            }
        )

        buckets = response.get("aggregations", {}).get("unique_sites", {}).get("buckets", [])
        sites = [bucket["key"] for bucket in buckets]

        return sorted(sites)
