# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Azure AI Search Writer - Write operations for Azure AI Search.

Implements VectorDBWriterInterface from nlweb_dataload for uploading and
deleting documents in Azure AI Search indexes.
"""

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)

# Import the writer interface - but handle case where nlweb_dataload isn't installed
try:
    from nlweb_dataload.writer import VectorDBWriterInterface
    from nlweb_dataload.config import CONFIG
    _has_dataload = True
except ImportError:
    # Fallback: create minimal interface if nlweb_dataload not installed
    from abc import ABC, abstractmethod
    class VectorDBWriterInterface(ABC):
        @abstractmethod
        async def upload_documents(self, documents: List[Dict[str, Any]], **kwargs):
            pass
        @abstractmethod
        async def delete_documents(self, filter_criteria: Dict[str, Any], **kwargs):
            pass
    CONFIG = None
    _has_dataload = False


class AzureSearchWriter(VectorDBWriterInterface):
    """Writer for Azure AI Search operations."""

    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Azure Search writer.

        Args:
            endpoint_name: Name of the endpoint to use (uses CONFIG.write_endpoint if not specified)
        """
        if not CONFIG:
            raise ValueError("nlweb_dataload not configured. Call nlweb_dataload.init(config_path='config.yaml') first")

        self.endpoint_name = endpoint_name or CONFIG.write_endpoint

        # Get endpoint configuration from dataload CONFIG
        self.endpoint_config = CONFIG.get_database_endpoint(self.endpoint_name)

        # Verify this is an Azure AI Search endpoint
        if self.endpoint_config.get('db_type') != "azure_ai_search":
            raise ValueError(
                f"Endpoint {self.endpoint_name} is not an Azure AI Search endpoint "
                f"(type: {self.endpoint_config.get('db_type')})"
            )

        # Get authentication method
        self.auth_method = self.endpoint_config.get('auth_method', 'api_key')

        # Get API endpoint
        self.api_endpoint = self.endpoint_config.get('api_endpoint')
        if not self.api_endpoint:
            raise ValueError(f"api_endpoint not configured for {self.endpoint_name}")
        self.api_endpoint = self.api_endpoint.strip('"')

        self.default_index_name = self.endpoint_config.get('index_name', 'embeddings1536')

        # API key is only required for api_key authentication
        if self.auth_method == "api_key":
            self.api_key = self.endpoint_config.get('api_key')
            if not self.api_key:
                raise ValueError(f"api_key not configured for {self.endpoint_name}")
            self.api_key = self.api_key.strip('"')
        elif self.auth_method == "azure_ad":
            self.api_key = None
        else:
            raise ValueError(
                f"Unsupported authentication method: {self.auth_method}. "
                f"Use 'api_key' or 'azure_ad'"
            )

    def _get_credential(self):
        """Get Azure credential based on authentication method."""
        if self.auth_method == "azure_ad":
            return DefaultAzureCredential()
        elif self.auth_method == "api_key":
            return AzureKeyCredential(self.api_key)
        else:
            raise ValueError(f"Unsupported authentication method: {self.auth_method}")

    def _get_search_client(self, index_name: Optional[str] = None) -> SearchClient:
        """
        Get the Azure AI Search client for a specific index.

        Args:
            index_name: Name of the index (defaults to configured index name)

        Returns:
            SearchClient: The Azure Search client for the specified index
        """
        index_name = index_name or self.default_index_name
        credential = self._get_credential()

        return SearchClient(
            endpoint=self.api_endpoint,
            index_name=index_name,
            credential=credential
        )

    def _get_index_client(self) -> SearchIndexClient:
        """Get the Azure AI Search index management client."""
        credential = self._get_credential()
        return SearchIndexClient(endpoint=self.api_endpoint, credential=credential)

    async def _ensure_index_exists(self, index_name: str, vector_dimensions: int = 1536):
        """
        Ensure the index exists, creating it if necessary.

        Args:
            index_name: Name of the index
            vector_dimensions: Dimension of the embedding vectors (default: 1536 for text-embedding-3-small)
        """
        index_client = self._get_index_client()

        def check_index():
            try:
                index_client.get_index(index_name)
                return True
            except Exception:
                return False

        exists = await asyncio.get_event_loop().run_in_executor(None, check_index)

        if exists:
            return

        # Create index with vector search configuration
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="url", type=SearchFieldDataType.String),
            SearchableField(name="site", type=SearchFieldDataType.String, filterable=True, sortable=True, facetable=True),
            SearchableField(name="type", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(name="timestamp", type=SearchFieldDataType.DateTimeOffset),
            SearchField(
                name="embedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=vector_dimensions,
                vector_search_profile_name="default-profile",
            ),
        ]

        # Configure vector search
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(name="default-hnsw")
            ],
            profiles=[
                VectorSearchProfile(
                    name="default-profile",
                    algorithm_configuration_name="default-hnsw",
                )
            ],
        )

        index = SearchIndex(
            name=index_name,
            fields=fields,
            vector_search=vector_search
        )

        def create_index():
            return index_client.create_index(index)

        await asyncio.get_event_loop().run_in_executor(None, create_index)

    def _generate_document_id(self, url: str, site: str) -> str:
        """
        Generate a unique document ID from URL and site.

        Args:
            url: Document URL
            site: Site identifier

        Returns:
            Unique document ID (hash)
        """
        # Use MD5 hash of URL + site for consistent IDs
        content = f"{url}:{site}"
        return hashlib.md5(content.encode()).hexdigest()

    async def upload_documents(
        self,
        documents: List[Dict[str, Any]],
        index_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Upload/upsert documents to Azure AI Search.

        Args:
            documents: List of document dicts with fields:
                - url (required)
                - type (required)
                - site (required)
                - content (required): Document content/schema JSON
                - embedding (required): List of floats
                - timestamp (optional): DateTimeOffset
                - id (optional): If not provided, generated from URL + site
            index_name: Optional index name (defaults to configured index name)
            **kwargs: Additional parameters

        Returns:
            Dict with upload results
        """
        index_name = index_name or self.default_index_name

        # Ensure index exists (create if necessary)
        if documents:
            # Determine vector dimensions from first document's embedding
            vector_dimensions = len(documents[0]['embedding'])
            await self._ensure_index_exists(index_name, vector_dimensions)

        search_client = self._get_search_client(index_name)

        # Prepare documents for Azure Search
        prepared_docs = []
        for doc in documents:
            # Generate ID if not provided
            doc_id = doc.get('id') or self._generate_document_id(doc['url'], doc['site'])

            prepared_doc = {
                'id': doc_id,
                'url': doc['url'],
                'site': doc['site'],
                'type': doc['type'],
                'content': doc['content'],
                'embedding': doc['embedding'],
                'timestamp': doc.get('timestamp') or datetime.now(timezone.utc).isoformat()
            }
            prepared_docs.append(prepared_doc)

        # Upload documents (upsert - insert or update)
        def upload_sync():
            return search_client.upload_documents(documents=prepared_docs)

        result = await asyncio.get_event_loop().run_in_executor(None, upload_sync)

        # Process results
        success_count = sum(1 for r in result if r.succeeded)
        error_count = sum(1 for r in result if not r.succeeded)

        return {
            'success_count': success_count,
            'error_count': error_count,
            'total': len(prepared_docs)
        }

    async def delete_documents(
        self,
        filter_criteria: Dict[str, Any],
        index_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Delete documents matching filter criteria.

        Args:
            filter_criteria: Filter dict (e.g., {"site": "example.com"})
            index_name: Optional index name
            **kwargs: Additional parameters

        Returns:
            Dict with deletion results
        """
        index_name = index_name or self.default_index_name
        search_client = self._get_search_client(index_name)

        # Build OData filter from criteria
        filters = []
        for key, value in filter_criteria.items():
            filters.append(f"{key} eq '{value}'")
        filter_str = " and ".join(filters)

        # Search for documents matching filter
        def search_sync():
            return list(search_client.search(
                search_text="*",
                filter=filter_str,
                select="id",
                top=10000  # Max documents to delete in one batch
            ))

        results = await asyncio.get_event_loop().run_in_executor(None, search_sync)

        if not results:
            return {'deleted_count': 0}

        # Delete documents by ID
        doc_ids = [{'id': r['id']} for r in results]

        def delete_sync():
            return search_client.delete_documents(documents=doc_ids)

        delete_result = await asyncio.get_event_loop().run_in_executor(None, delete_sync)

        deleted_count = sum(1 for r in delete_result if r.succeeded)

        return {'deleted_count': deleted_count}

    async def delete_site(
        self,
        site: str,
        index_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Delete all documents for a specific site.

        Args:
            site: Site identifier
            index_name: Optional index name
            **kwargs: Additional parameters

        Returns:
            Dict with deletion results
        """
        return await self.delete_documents({'site': site}, index_name=index_name, **kwargs)
