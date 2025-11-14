# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Snowflake Cortex Search Client for NLWeb

Provides read-only access to Snowflake Cortex Search Services for hybrid
vector and keyword search capabilities.
"""

import json
import httpx
from typing import List, Dict, Union, Optional, Any, Tuple

from nlweb_core.config import CONFIG
from nlweb_core.retriever import VectorDBClientInterface
from nlweb_core.embedding import get_embedding


class ConfigurationError(RuntimeError):
    """Raised when configuration is missing or invalid"""
    pass


class SnowflakeCortexClient(VectorDBClientInterface):
    """
    Client for Snowflake Cortex Search operations.
    
    This client provides read-only access to Snowflake Cortex Search Services,
    which combine vector similarity search with traditional keyword search.
    
    Note: Data ingestion is not supported. Data must be loaded into Snowflake
    using native tools (COPY INTO, Snowpipe, etc.) before creating the search service.
    """

    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Snowflake Cortex Search client.

        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        super().__init__()
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        
        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        
        # Get connection parameters
        self.account_url = self._get_account_url()
        self.pat = self._get_pat()
        
        # Parse the search service name (database.schema.service)
        self.database, self.schema, self.service = self._parse_service_name()

    def _get_endpoint_config(self):
        """Get the Snowflake endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            raise ValueError(f"No configuration found for endpoint {self.endpoint_name}")
        
        # Verify this is a Snowflake Cortex Search endpoint
        if endpoint_config.db_type != "snowflake_cortex_search":
            raise ValueError(
                f"Endpoint {self.endpoint_name} is not a Snowflake Cortex Search endpoint "
                f"(type: {endpoint_config.db_type})"
            )
        
        return endpoint_config

    def _get_account_url(self) -> str:
        """Get the Snowflake account URL from configuration"""
        if not self.endpoint_config.api_endpoint:
            raise ConfigurationError(
                f"api_endpoint is not configured for endpoint {self.endpoint_name}. "
                "Set SNOWFLAKE_ACCOUNT_URL in your environment."
            )
        return self.endpoint_config.api_endpoint.strip('"')

    def _get_pat(self) -> str:
        """Get the Programmatic Access Token from configuration"""
        if not self.endpoint_config.api_key:
            raise ConfigurationError(
                f"api_key is not configured for endpoint {self.endpoint_name}. "
                "Set SNOWFLAKE_PAT in your environment."
            )
        return self.endpoint_config.api_key.strip('"')

    def _parse_service_name(self) -> Tuple[str, str, str]:
        """
        Parse the Cortex Search Service name into database, schema, and service components.
        
        Returns:
            Tuple of (database, schema, service)
        """
        if not self.endpoint_config.index_name:
            raise ConfigurationError(
                "index_name is not configured. Expected format: <database>.<schema>.<service>"
            )
        
        parts = self.endpoint_config.index_name.split(".")
        if len(parts) != 3:
            raise ConfigurationError(
                f"Invalid index_name format. Expected <database>.<schema>.<service>, "
                f"got: {self.endpoint_config.index_name}"
            )
        
        return parts[0], parts[1], parts[2]

    async def search(
        self,
        query: str,
        site: Union[str, List[str]],
        num_results: int = 50,
        query_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[List[str]]:
        """
        Search the Snowflake Cortex Search Service.

        Args:
            query: The search query text
            site: Site name(s) to filter by. Use "all" to search all sites
            num_results: Maximum number of results to return (1-1000)
            query_params: Optional additional query parameters
            **kwargs: Additional keyword arguments

        Returns:
            List of results, each containing [url, schema_json, name, site]
        """
        # Build filter based on site parameter
        filter_obj = self._create_site_filter(site)
        
        # Prepare request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.account_url}/api/v2/databases/{self.database}/schemas/{self.schema}/"
                f"cortex-search-services/{self.service}:query",
                json={
                    "query": query,
                    "limit": max(1, min(num_results, 1000)),
                    "columns": ["url", "site", "schema_json"],
                    "filter": filter_obj,
                },
                headers={
                    "Authorization": f"Bearer {self.pat}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=60,
            )
            
            if response.status_code == 400:
                raise Exception(response.json())
            response.raise_for_status()
            
            results = response.json().get("results", [])
            return [self._process_result(r) for r in results]

    async def search_by_url(
        self,
        url: str,
        query: Optional[str] = None,
        **kwargs
    ) -> List[List[str]]:
        """
        Search for a specific document by URL.

        Args:
            url: The URL to search for
            query: Optional query text for relevance ranking
            **kwargs: Additional keyword arguments

        Returns:
            List of results, each containing [url, schema_json, name, site]
        """
        # Build filter for URL
        filter_obj = {"@eq": {"url": url}}
        
        # Use a generic query if none provided
        search_query = query or url
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.account_url}/api/v2/databases/{self.database}/schemas/{self.schema}/"
                f"cortex-search-services/{self.service}:query",
                json={
                    "query": search_query,
                    "limit": 10,
                    "columns": ["url", "site", "schema_json"],
                    "filter": filter_obj,
                },
                headers={
                    "Authorization": f"Bearer {self.pat}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=60,
            )
            
            if response.status_code == 400:
                raise Exception(response.json())
            response.raise_for_status()
            
            results = response.json().get("results", [])
            return [self._process_result(r) for r in results]

    async def get_sites(self, **kwargs) -> List[str]:
        """
        Get a list of unique site names from the Cortex Search Service.

        Uses CORTEX_SEARCH_DATA_SCAN to query unique sites.

        Returns:
            Sorted list of unique site names
        """
        query = (
            f"SELECT DISTINCT site FROM TABLE("
            f"CORTEX_SEARCH_DATA_SCAN("
            f"SERVICE_NAME=>'{self.database}.{self.schema}.{self.service}'"
            f")) ORDER BY site"
        )
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.account_url}/api/v2/statements",
                json={
                    "statement": query,
                    "timeout": 60,
                },
                headers={
                    "Authorization": f"Bearer {self.pat}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=60,
            )
            
            if response.status_code == 400:
                raise Exception(response.json())
            response.raise_for_status()
            
            # Extract site names from response
            return [x[0] for x in response.json().get("data", [])]

    def _create_site_filter(self, site: Union[str, List[str]]) -> Optional[Dict[str, Any]]:
        """
        Create a filter object for site filtering.

        Args:
            site: Site name(s) to filter by. Use "all" to return None (no filter)

        Returns:
            Filter dictionary or None for no filtering
        """
        if site == "all" or (isinstance(site, list) and "all" in site):
            return None
        
        if isinstance(site, str):
            return {"@eq": {"site": site}}
        elif isinstance(site, list) and len(site) == 1:
            return {"@eq": {"site": site[0]}}
        elif isinstance(site, list) and len(site) > 1:
            # Multiple sites - use OR filter
            return {
                "@or": [{"@eq": {"site": s}} for s in site]
            }
        
        return None

    def _process_result(self, result: Dict[str, str]) -> List[str]:
        """
        Process a single search result into the expected format.

        Args:
            result: Raw result from Cortex Search

        Returns:
            List containing [url, schema_json, name, site]
        """
        url = result.get("url", "")
        schema_json = result.get("schema_json", "{}")
        name = self._name_from_schema_json(schema_json)
        site = result.get("site", "")
        
        return [url, schema_json, name, site]

    def _name_from_schema_json(self, schema_json: str) -> str:
        """
        Extract the name field from schema JSON.

        Args:
            schema_json: JSON string containing schema data

        Returns:
            Name extracted from schema, or empty string if not found
        """
        try:
            return json.loads(schema_json).get("name", "")
        except Exception:
            return ""
