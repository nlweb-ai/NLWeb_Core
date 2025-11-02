# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
OpenSearch Client - Interface for OpenSearch operations.
"""

import time
import threading
import base64
import json
from typing import List, Dict, Union, Optional, Any
import httpx

from nlweb_core.config import CONFIG
from nlweb_core.retriever import VectorDBClientInterface
from nlweb_core.embedding import get_embedding



class OpenSearchClient(VectorDBClientInterface):
    """
    Client for OpenSearch operations, providing a unified interface for 
    vector-based search results using OpenSearch REST API.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the OpenSearch client.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        self._client_lock = threading.Lock()
        
        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        
        # Handle None values from configuration
        api_endpoint_raw = self.endpoint_config.api_endpoint
        credentials_raw = self.endpoint_config.api_key
        
        if api_endpoint_raw is None:
            raise ValueError(f"API endpoint not configured for {self.endpoint_name}. Check environment variable configuration.")
        if credentials_raw is None:
            raise ValueError(f"API credentials not configured for {self.endpoint_name}. Check environment variable configuration.")
            
        self.api_endpoint = api_endpoint_raw.strip('"').rstrip('/')
        self.credentials = credentials_raw.strip('"')
        self.default_index_name = self.endpoint_config.index_name or "embeddings"
        # Handle use_knn configuration - default based on endpoint name
        use_knn_config = getattr(self.endpoint_config, 'use_knn', None)
        if use_knn_config is not None:
            self.use_knn = use_knn_config
        else:
            # Default based on endpoint name for backward compatibility
            self.use_knn = 'script' not in self.endpoint_name.lower()
        
    
    def _get_endpoint_config(self):
        """Get the OpenSearch endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            raise ValueError(error_msg)
        
        # Verify this is an OpenSearch endpoint
        if endpoint_config.db_type != "opensearch":
            error_msg = f"Endpoint {self.endpoint_name} is not an OpenSearch endpoint (type: {endpoint_config.db_type})"
            raise ValueError(error_msg)
            
        return endpoint_config
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for OpenSearch requests.
        Supports both basic auth (username:password) and API key authentication.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if ':' in self.credentials:
            # Basic authentication (username:password)
            encoded_credentials = base64.b64encode(self.credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded_credentials}"
        else:
            # API key authentication
            headers["Authorization"] = f"Bearer {self.credentials}"
        
        return headers
    
    async def create_index_if_not_exists(self, index_name: Optional[str] = None,
                                       vector_dimension: int = 1536) -> bool:
        """
        Create the OpenSearch index with proper kNN vector mapping if it doesn't exist.
        
        Args:
            index_name: Optional index name (defaults to configured index name)
            vector_dimension: Dimension of the embedding vectors (default 1536)
            
        Returns:
            bool: True if index was created, False if it already existed
        """
        index_name = index_name or self.default_index_name
        
        # Check if index already exists
        try:
            async with httpx.AsyncClient() as client:
                response = await client.head(
                    f"{self.api_endpoint}/{index_name}",
                    headers=self._get_auth_headers(),
                    timeout=30
                )
                if response.status_code == 200:
                    return False
        except Exception:
            pass  # Index doesn't exist, proceed to create
        
        # Define index mapping based on k-NN availability
        base_properties = {
            "url": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 2048
                    }
                }
            },
            "site": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "name": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 512
                    }
                }
            },
            "schema_json": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            }
        }
        
        if self.use_knn:
            # k-NN mapping with vector field
            index_mapping = {
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 100
                    }
                },
                "mappings": {
                    "properties": {
                        **base_properties,
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": vector_dimension,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "lucene",
                                "parameters": {
                                    "ef_construction": 128,
                                    "m": 24
                                }
                            }
                        }
                    }
                }
            }
        else:
            # Standard mapping with float array for script_score (compatible with basic OpenSearch)
            index_mapping = {
                "mappings": {
                    "properties": {
                        **base_properties,
                        "embedding": {
                            "type": "float"
                        }
                    }
                }
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.api_endpoint}/{index_name}",
                    json=index_mapping,
                    headers=self._get_auth_headers(),
                    timeout=60
                )
                response.raise_for_status()
                
                return True
                
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
            site_filter = {"term": {"site": sites[0]}}
        else:
            site_filter = {"terms": {"site": sites}}
        
        # Build OpenSearch query with kNN vector search and site filtering
        search_query = {
            "size": num_results,
            "_source": ["url", "site", "schema_json", "name"],
            "query": {
                "bool": {
                    "must": [
                        {
                            "knn": {
                                "embedding": {
                                    "vector": embedding,
                                    "k": num_results
                                }
                            }
                        }
                    ],
                    "filter": [site_filter]
                }
            }
        }
        
        start_retrieve = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_endpoint}/{index_name}/_search",
                    json=search_query,
                    headers=self._get_auth_headers(),
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                hits = result.get('hits', {}).get('hits', [])
                
                # Process results into the expected format
                processed_results = []
                for hit in hits:
                    source = hit.get('_source', {})
                    url = source.get('url', '')
                    schema_json = source.get('schema_json', '{}')
                    name = source.get('name', '')
                    site_name = source.get('site', '')
                    
                    processed_result = [url, schema_json, name, site_name]
                    processed_results.append(processed_result)
                
                retrieve_time = time.time() - start_retrieve

                return processed_results

        except Exception as e:
            raise
    
    async def _search_by_site_and_vector(self, sites: Union[str, List[str]],
                                       vector_embedding: List[float],
                                       top_n: int = 10,
                                       index_name: Optional[str] = None) -> List[List[str]]:
        """
        Internal method to retrieve top n records filtered by site and ranked by vector similarity
        
        Args:
            sites: Site or list of sites to filter by
            vector_embedding: The embedding vector to search with
            top_n: Maximum number of results to return
            index_name: Optional index name (defaults to configured index name)
            
        Returns:
            List[List[str]]: List of search results
        """
        index_name = index_name or self.default_index_name
        
        # Handle both single site and multiple sites
        if isinstance(sites, str):
            sites = [sites]
        
        # Build site filter
        if len(sites) == 1:
            site_filter = {"term": {"site": sites[0]}}
        else:
            site_filter = {"terms": {"site": sites}}
        
        # Build OpenSearch query based on k-NN availability
        if self.use_knn:
            # Use k-NN plugin query
            search_query = {
                "size": top_n,
                "_source": ["url", "site", "schema_json", "name"],
                "query": {
                    "bool": {
                        "must": [
                            {
                                "knn": {
                                    "embedding": {
                                        "vector": vector_embedding,
                                        "k": top_n
                                    }
                                }
                            }
                        ],
                        "filter": [site_filter]
                    }
                }
            }
        else:
            # Use script_score for vector similarity
            search_query = {
                "size": top_n,
                "_source": ["url", "site", "schema_json", "name"],
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": [site_filter]
                            }
                        },
                        "script": {
                            "source": """
                                double dotProduct = 0.0;
                                double normA = 0.0;
                                double normB = 0.0;
                                for (int i = 0; i < params.query_vector.length; i++) {
                                    dotProduct += params.query_vector[i] * doc['embedding'][i];
                                    normA += params.query_vector[i] * params.query_vector[i];
                                    normB += doc['embedding'][i] * doc['embedding'][i];
                                }
                                return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB)) + 1.0;
                            """,
                            "params": {
                                "query_vector": vector_embedding
                            }
                        }
                    }
                }
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_endpoint}/{index_name}/_search",
                    json=search_query,
                    headers=self._get_auth_headers(),
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                hits = result.get('hits', {}).get('hits', [])
                
                # Process results into the expected format
                processed_results = []
                for hit in hits:
                    source = hit.get('_source', {})
                    url = source.get('url', '')
                    schema_json = source.get('schema_json', '{}')
                    name = source.get('name', '')
                    site = source.get('site', '')
                    
                    processed_result = [url, schema_json, name, site]
                    processed_results.append(processed_result)
                
                return processed_results

        except Exception as e:
            raise
