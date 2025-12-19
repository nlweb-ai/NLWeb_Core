# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Qdrant Vector Database Client - Interface for Qdrant operations.
"""

import os
import threading
import time
import uuid
from typing import List, Dict, Union, Optional, Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

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
        super().__init__()
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
            pass  # Using remote Qdrant
        elif self.database_path:
            pass  # Using local Qdrant
        else:
            # Default to local path if neither is specified
            self.database_path = self._resolve_path("../data/db")

    def _get_endpoint_config(self):
        """Get the Qdrant endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)

        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            raise ValueError(error_msg)

        # Verify this is a Qdrant endpoint
        if endpoint_config.db_type != "qdrant":
            error_msg = (
                f"Endpoint {self.endpoint_name} is not a Qdrant endpoint "
                f"(type: {endpoint_config.db_type})"
            )
            raise ValueError(error_msg)

        return endpoint_config

    def _resolve_path(self, path: str) -> str:
        """
        Resolve a path relative to the current file's directory.

        Args:
            path: Path to resolve (can be relative or absolute)

        Returns:
            str: Absolute path
        """
        if os.path.isabs(path):
            return path

        # Get the directory of the current file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        resolved_path = os.path.abspath(os.path.join(current_dir, path))
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

            # Create async client
            client = AsyncQdrantClient(**params)

            # Test connection by getting collections
            await client.get_collections()

            # Store in cache with lock
            with self._client_lock:
                self._qdrant_clients[client_key] = client

            return client

        except Exception as e:
            raise Exception(f"Failed to initialize Qdrant client: {str(e)}")

    async def collection_exists(self, collection_name: Optional[str] = None) -> bool:
        """
        Check if a collection exists in Qdrant.

        Args:
            collection_name: Name of the collection to check

        Returns:
            bool: True if the collection exists, False otherwise
        """
        collection_name = collection_name or self.default_collection_name
        client = await self._get_qdrant_client()

        try:
            return await client.collection_exists(collection_name)
        except Exception:
            return False

    async def create_collection(
        self,
        collection_name: Optional[str] = None,
        vector_size: int = 1536
    ) -> bool:
        """
        Create a collection in Qdrant if it doesn't exist.

        Args:
            collection_name: Name of the collection to create
            vector_size: Size of the embedding vectors

        Returns:
            bool: True if created, False if already exists
        """
        collection_name = collection_name or self.default_collection_name
        client = await self._get_qdrant_client()

        try:
            # Check if collection exists
            if await client.collection_exists(collection_name):
                return False

            # Create collection
            await client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                ),
            )

            return True

        except Exception as e:
            raise Exception(f"Error creating collection '{collection_name}': {str(e)}")

    async def ensure_collection_exists(
        self,
        collection_name: Optional[str] = None,
        vector_size: int = 1536
    ) -> bool:
        """
        Ensure a collection exists, creating it if necessary.

        Args:
            collection_name: Name of the collection
            vector_size: Size of the embedding vectors

        Returns:
            bool: True if collection was created, False if it already existed
        """
        collection_name = collection_name or self.default_collection_name
        client = await self._get_qdrant_client()

        # Check if collection exists
        if await client.collection_exists(collection_name):
            return False

        # Create collection
        await self.create_collection(collection_name, vector_size)
        return True

    def _create_site_filter(self, site: Union[str, List[str]]):
        """
        Create a Qdrant filter for site filtering.

        Args:
            site: Site or list of sites to filter by

        Returns:
            Optional filter condition
        """
        if site == "all":
            return None

        if isinstance(site, list):
            sites = site
        elif isinstance(site, str):
            sites = [site]
        else:
            sites = []

        # Filter out "all"
        sites = [s for s in sites if s != "all"]
        if not sites:
            return None

        return models.Filter(
            must=[models.FieldCondition(key="site", match=models.MatchAny(any=sites))]
        )

    def _format_results(self, search_result: List[models.ScoredPoint]) -> List[List[str]]:
        """
        Format Qdrant search results to match expected API: [url, content_json, type, site].

        Args:
            search_result: Qdrant search results

        Returns:
            List[List[str]]: Formatted results
        """
        results = []
        for item in search_result:
            payload = item.payload
            url = payload.get("url", "")
            # Content is stored as JSON string in Qdrant payload
            content = payload.get("content", "")
            type_name = payload.get("type", "")
            site_name = payload.get("site", "")

            results.append([url, content, type_name, site_name])

        return results

    async def search(
        self,
        query: str,
        site: Union[str, List[str]],
        num_results: int = 50,
        collection_name: Optional[str] = None,
        query_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[List[str]]:
        """
        Search the Qdrant collection for records filtered by site and ranked by vector similarity.

        Args:
            query: The search query to embed and search with
            site: Site to filter by (string or list of strings)
            num_results: Maximum number of results to return
            collection_name: Optional collection name (defaults to configured name)
            query_params: Additional query parameters

        Returns:
            List[List[str]]: List of search results in format [url, content_json, type, site]
        """
        collection_name = collection_name or self.default_collection_name

        try:
            # Embed the query using NLWeb's embedding function
            start_embed = time.time()
            embedding = await get_embedding(query, query_params=query_params)
            embed_time = time.time() - start_embed

            start_retrieve = time.time()

            # Get client and prepare filter
            client = await self._get_qdrant_client()
            filter_condition = self._create_site_filter(site)

            # Ensure collection exists before searching
            if not await client.collection_exists(collection_name):
                # Collection doesn't exist, return empty results
                return []
            
            # Perform the search using async client query_points method
            search_response = await client.query_points(
                collection_name=collection_name,
                query=embedding,
                limit=num_results,
                query_filter=filter_condition,
                with_payload=True,  # Critical: fetches the content back
            )
            
            # Extract points from response
            search_result = search_response.points

            # Format the results
            results = self._format_results(search_result)

            retrieve_time = time.time() - start_retrieve

            return results

        except Exception as e:
            raise Exception(f"Error in Qdrant search: {str(e)}")

    async def search_by_url(
        self,
        url: str,
        collection_name: Optional[str] = None
    ) -> Optional[List[str]]:
        """
        Retrieve a specific item by URL from Qdrant database.

        Args:
            url: URL to search for
            collection_name: Optional collection name (defaults to configured name)

        Returns:
            Optional[List[str]]: Search result or None if not found
        """
        collection_name = collection_name or self.default_collection_name

        try:
            client = await self._get_qdrant_client()

            filter_condition = models.Filter(
                must=[models.FieldCondition(key="url", match=models.MatchValue(value=url))]
            )

            try:
                # Use scroll to find the item by URL
                points, _offset = await client.scroll(
                    collection_name=collection_name,
                    scroll_filter=filter_condition,
                    limit=1,
                    with_payload=True,
                )

                if not points:
                    return None

                item = points[0]
                payload = item.payload
                formatted_result = [
                    payload.get("url", ""),
                    payload.get("content", ""),  # Content as JSON string
                    payload.get("type", ""),
                    payload.get("site", ""),
                ]

                return formatted_result

            except Exception as e:
                # Collection might not exist
                if "not found" in str(e).lower():
                    return None
                raise

        except Exception as e:
            raise Exception(f"Error retrieving item by URL: {str(e)}")

    async def search_all_sites(
        self,
        query: str,
        num_results: int = 50,
        collection_name: Optional[str] = None,
        query_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[List[str]]:
        """
        Search across all sites without filtering.

        Args:
            query: Search query string
            num_results: Maximum number of results to return
            collection_name: Optional collection name
            query_params: Query parameters for embedding generation
            **kwargs: Additional parameters

        Returns:
            List[List[str]]: List of search results
        """
        return await self.search(
            query, "all", num_results, collection_name, query_params, **kwargs
        )

    async def get_sites(self, collection_name: Optional[str] = None) -> List[str]:
        """
        Get a list of unique site names from the Qdrant collection.

        Args:
            collection_name: Optional collection name (defaults to configured name)

        Returns:
            List[str]: Sorted list of unique site names
        """
        collection_name = collection_name or self.default_collection_name

        try:
            client = await self._get_qdrant_client()

            # Check if collection exists
            if not await client.collection_exists(collection_name):
                return []

            # Use scroll to get all points with site field
            sites = set()
            offset = None
            batch_size = 1000

            while True:
                points, next_offset = await client.scroll(
                    collection_name=collection_name,
                    limit=batch_size,
                    offset=offset,
                    with_payload=["site"]
                )

                if not points:
                    break

                # Extract site values
                for point in points:
                    site = point.payload.get("site")
                    if site:
                        sites.add(site)

                offset = next_offset
                if offset is None:
                    break

            # Convert to sorted list
            site_list = sorted(list(sites))
            return site_list

        except Exception as e:
            raise Exception(f"Error retrieving sites: {str(e)}")
