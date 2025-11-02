# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the vector database ranking handler.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from nlweb_core.NLWebRankingHandler import NLWebRankingHandler
from nlweb_core.retriever import VectorDBClient


class VectorDBRetriever:
    """
    Retriever that uses vector database search.

    Configuration can come from either:
    a) query_params (vectordb_type, query_endpoint, query_key)
    b) config_retrieval.yaml (default)
    """

    def __init__(self, handler):
        """
        Initialize the vector DB retriever.

        Args:
            handler: The NLWebHandler instance
        """
        self.handler = handler

    async def do(self):
        """
        Perform vector database search and return results.

        Returns:
            List of tuples (url, json_str, name, site)
        """
        # Get search parameters from handler
        query = self.handler.query
        site = self.handler.get_param('site', str, 'all')
        num_results = self.handler.get_param('num_results', int, 50)

        print(f"\n[RETRIEVER] Query: '{query}', Site: '{site}', Num results: {num_results}")

        # Determine endpoint configuration
        # Option (a): Check if query_params specifies vectordb configuration
        endpoint_name = None
        if 'vectordb_type' in self.handler.query_params or 'query_endpoint' in self.handler.query_params:
            # Query params specify vector DB configuration
            # This will be used by VectorDBClient to override config
            pass
        # Option (b): Use default from config_retrieval.yaml
        else:
            endpoint_name = self.handler.get_param('endpoint_name', str, None)

        # Create the vector DB client
        # If query_params has vectordb config, VectorDBClient will use it
        # Otherwise, it will use the endpoint_name or default from config
        client = VectorDBClient(
            endpoint_name=endpoint_name,
            query_params=self.handler.query_params
        )

        print(f"[RETRIEVER] Using endpoint: {client.endpoint_name} (type: {client.db_type})")

        # Perform the search
        results = await client.search(query, site, num_results)

        print(f"[RETRIEVER] Retrieved {len(results)} results")

        return results


class NLWebVectorDBRankingHandler(NLWebRankingHandler):
    """
    Concrete ranking handler that uses vector database for retrieval.

    This handler retrieves items from a vector database and then ranks them.

    Configuration can be specified in two ways:
    a) Via query_params: vectordb_type, query_endpoint, query_key
    b) Via config_retrieval.yaml (default)
    """

    def __init__(self, query_params, output_method):
        """
        Initialize the vector DB ranking handler.

        Args:
            query_params: Query parameters dict (may contain vectordb config)
            output_method: Method to send output
        """
        super().__init__(query_params, output_method, VectorDBRetriever)
