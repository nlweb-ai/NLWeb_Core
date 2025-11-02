# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Milvus Vector Database Client - Interface for Milvus operations.
"""

import os
import sys
import threading
import asyncio
import json
from typing import List, Dict, Union, Optional, Any, Tuple

from pymilvus import MilvusClient
import numpy as np

from nlweb_core.config import CONFIG
from nlweb_core.embedding import get_embedding
from nlweb_core.retriever import VectorDBClientInterface


class MilvusVectorClient(VectorDBClientInterface):
    """
    Client for Milvus vector database operations, providing a unified interface for 
    indexing, storing, and retrieving vector-based search results.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Milvus vector database client.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        super().__init__()  # Initialize the base class with caching
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint

        self._client_lock = threading.Lock()
        self._milvus_clients = {}  # Cache for Milvus clients
        
        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        
        self.uri = self.endpoint_config.api_endpoint
        self.token = self.endpoint_config.api_key

        if not self.uri:
            error_msg = f"Milvus URI is empty. Please check if you have set MILVUS_ENDPOINT env var or milvus.api_endpoint_env in config_retrieval.yaml properly."
            raise ValueError(error_msg)
            
        self.default_collection_name = self.endpoint_config.index_name or "prod_collection"
    
    def _get_endpoint_config(self):
        """Get the Milvus endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            raise ValueError(error_msg)
        
        # Verify this is a Milvus endpoint
        if endpoint_config.db_type != "milvus":
            error_msg = f"Endpoint {self.endpoint_name} is not a Milvus endpoint (type: {endpoint_config.db_type})"
            raise ValueError(error_msg)
            
        return endpoint_config
    
    def _get_milvus_client(self, embedding_size: str = "small") -> MilvusClient:
        """
        Get or create a Milvus client.
        
        Args:
            embedding_size: Size of the embeddings ("small"=1536 or "large"=3072)
            
        Returns:
            MilvusClient instance
        """
        client_key = f"{self.endpoint_name}_{embedding_size}"
        
        with self._client_lock:
            if client_key not in self._milvus_clients:
                
                # Initialize the client
                self._milvus_clients[client_key] = MilvusClient(self.uri, self.token)
                
                # Test client connection with a simple search
                try:
                    self._milvus_clients[client_key].list_collections()
                except Exception as e:
                    raise
                    
        return self._milvus_clients[client_key]
    
    async def search(self, query: str, site: Union[str, List[str]],
                   num_results: int = 50, collection_name: Optional[str] = None,
                   query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search the Milvus collection for records filtered by site and ranked by vector similarity.
        
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
            # Generate embedding for the query
            embedding = await get_embedding(query, query_params=query_params)
            
            # Run the search operation asynchronously
            results = await asyncio.get_event_loop().run_in_executor(
                None, self._search_sync, query, site, num_results, embedding, collection_name, query_params
            )
            
            return results

        except Exception as e:
            raise
    
    def _search_sync(self, query: str, site: Union[str, List[str]], num_results: int,
                   embedding: List[float], collection_name: str,
                   query_params: Optional[Dict[str, Any]]) -> List[List[str]]:
        """Synchronous implementation of search for thread execution"""
        
        try:
            client = self._get_milvus_client()
            
            # Perform the search based on the site parameter
            if site == "all":
                res = client.search(
                    collection_name=collection_name,
                    data=[embedding],
                    limit=num_results,
                    output_fields=["url", "text", "name", "site"],
                )
            elif isinstance(site, list):
                site_filter = " || ".join([f"site == '{s}'" for s in site])
                res = client.search(
                    collection_name=collection_name, 
                    data=[embedding],
                    filter=site_filter,
                    limit=num_results,
                    output_fields=["url", "text", "name", "site"],
                )
            else:
                res = client.search(
                    collection_name=collection_name,
                    data=[embedding],
                    filter=f"site == '{site}'",
                    limit=num_results,
                    output_fields=["url", "text", "name", "site"],
                )

            # Format the results
            retval = []
            if res and len(res) > 0:
                for item in res[0]:
                    ent = item["entity"]
                    try:
                        # Parse text field as JSON
                        schema_json = json.loads(ent["text"])
                        retval.append([ent["url"], schema_json, ent["name"], ent["site"]])
                    except json.JSONDecodeError as e:
                        continue
            
            return retval
        
        except Exception as e:
            raise