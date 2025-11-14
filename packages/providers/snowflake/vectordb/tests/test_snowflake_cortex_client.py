# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Tests for Snowflake Cortex Search Client
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from nlweb_snowflake_vectordb.snowflake_cortex_client import SnowflakeCortexClient, ConfigurationError


@pytest.fixture
def snowflake_client(mock_config):
    """Create SnowflakeCortexClient with mocked config"""
    with patch('nlweb_snowflake_vectordb.snowflake_cortex_client.CONFIG', mock_config):
        client = SnowflakeCortexClient(endpoint_name="test_endpoint")
        return client


class TestSnowflakeCortexClientInit:
    """Tests for SnowflakeCortexClient initialization"""

    def test_init_with_valid_config(self, mock_config):
        """Test initialization with valid configuration"""
        with patch('nlweb_snowflake_vectordb.snowflake_cortex_client.CONFIG', mock_config):
            client = SnowflakeCortexClient(endpoint_name="test_endpoint")
            
            assert client.endpoint_name == "test_endpoint"
            assert client.account_url == "https://test-account.snowflakecomputing.com"
            assert client.pat == "test_pat_token"
            assert client.database == "TEST_DB"
            assert client.schema == "TEST_SCHEMA"
            assert client.service == "TEST_SERVICE"

    def test_init_without_endpoint_name(self, mock_config):
        """Test initialization without explicit endpoint name"""
        with patch('nlweb_snowflake_vectordb.snowflake_cortex_client.CONFIG', mock_config):
            client = SnowflakeCortexClient()
            assert client.endpoint_name == "test_endpoint"

    def test_init_wrong_db_type(self, mock_config):
        """Test initialization fails with wrong database type"""
        mock_config.retrieval_endpoints["test_endpoint"].db_type = "elasticsearch"
        
        with patch('nlweb_snowflake_vectordb.snowflake_cortex_client.CONFIG', mock_config):
            with pytest.raises(ValueError, match="not a Snowflake Cortex Search endpoint"):
                SnowflakeCortexClient(endpoint_name="test_endpoint")

    def test_init_missing_endpoint_config(self, mock_config):
        """Test initialization fails with missing endpoint config"""
        mock_config.retrieval_endpoints = {}
        
        with patch('nlweb_snowflake_vectordb.snowflake_cortex_client.CONFIG', mock_config):
            with pytest.raises(ValueError, match="No configuration found"):
                SnowflakeCortexClient(endpoint_name="test_endpoint")

    def test_init_missing_account_url(self, mock_config):
        """Test initialization fails without account URL"""
        mock_config.retrieval_endpoints["test_endpoint"].api_endpoint = None
        
        with patch('nlweb_snowflake_vectordb.snowflake_cortex_client.CONFIG', mock_config):
            with pytest.raises(ConfigurationError, match="api_endpoint is not configured"):
                SnowflakeCortexClient(endpoint_name="test_endpoint")

    def test_init_missing_pat(self, mock_config):
        """Test initialization fails without PAT"""
        mock_config.retrieval_endpoints["test_endpoint"].api_key = None
        
        with patch('nlweb_snowflake_vectordb.snowflake_cortex_client.CONFIG', mock_config):
            with pytest.raises(ConfigurationError, match="api_key is not configured"):
                SnowflakeCortexClient(endpoint_name="test_endpoint")

    def test_init_invalid_service_name(self, mock_config):
        """Test initialization fails with invalid service name format"""
        mock_config.retrieval_endpoints["test_endpoint"].index_name = "INVALID_FORMAT"
        
        with patch('nlweb_snowflake_vectordb.snowflake_cortex_client.CONFIG', mock_config):
            with pytest.raises(ConfigurationError, match="Invalid index_name format"):
                SnowflakeCortexClient(endpoint_name="test_endpoint")

    def test_init_missing_service_name(self, mock_config):
        """Test initialization fails without service name"""
        mock_config.retrieval_endpoints["test_endpoint"].index_name = None
        
        with patch('nlweb_snowflake_vectordb.snowflake_cortex_client.CONFIG', mock_config):
            with pytest.raises(ConfigurationError, match="index_name is not configured"):
                SnowflakeCortexClient(endpoint_name="test_endpoint")


class TestSnowflakeCortexClientMethods:
    """Tests for SnowflakeCortexClient methods"""

    @pytest.mark.asyncio
    async def test_search_single_site(self, snowflake_client):
        """Test search with single site filter"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "url": "https://example.com/doc1",
                    "site": "example.com",
                    "schema_json": '{"name": "Document 1"}'
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            results = await snowflake_client.search(
                query="test query",
                site="example.com",
                num_results=10
            )
            
            assert len(results) == 1
            assert results[0][0] == "https://example.com/doc1"
            assert results[0][3] == "example.com"
            
            # Verify API call
            call_args = mock_client.post.call_args
            assert "cortex-search-services/TEST_SERVICE:query" in call_args[0][0]
            assert call_args[1]["json"]["query"] == "test query"
            assert call_args[1]["json"]["limit"] == 10
            assert call_args[1]["json"]["filter"] == {"@eq": {"site": "example.com"}}

    @pytest.mark.asyncio
    async def test_search_multiple_sites(self, snowflake_client):
        """Test search with multiple site filter"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            await snowflake_client.search(
                query="test",
                site=["site1.com", "site2.com"],
                num_results=20
            )
            
            # Verify filter for multiple sites
            call_args = mock_client.post.call_args
            expected_filter = {
                "@or": [
                    {"@eq": {"site": "site1.com"}},
                    {"@eq": {"site": "site2.com"}}
                ]
            }
            assert call_args[1]["json"]["filter"] == expected_filter

    @pytest.mark.asyncio
    async def test_search_all_sites(self, snowflake_client):
        """Test search with 'all' sites (no filter)"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            await snowflake_client.search(
                query="test",
                site="all",
                num_results=50
            )
            
            # Verify no filter is applied
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["filter"] is None

    @pytest.mark.asyncio
    async def test_search_limit_clamping(self, snowflake_client):
        """Test that num_results is clamped to 1-1000"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            # Test upper limit
            await snowflake_client.search(query="test", site="example.com", num_results=2000)
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["limit"] == 1000
            
            # Test lower limit
            await snowflake_client.search(query="test", site="example.com", num_results=0)
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["limit"] == 1

    @pytest.mark.asyncio
    async def test_search_error_handling(self, snowflake_client):
        """Test error handling in search"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Bad request"}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            with pytest.raises(Exception):
                await snowflake_client.search(
                    query="test",
                    site="example.com",
                    num_results=10
                )

    @pytest.mark.asyncio
    async def test_search_by_url(self, snowflake_client):
        """Test search by URL"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "url": "https://example.com/specific",
                    "site": "example.com",
                    "schema_json": '{"name": "Specific Doc"}'
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            results = await snowflake_client.search_by_url(
                url="https://example.com/specific",
                query="test"
            )
            
            assert len(results) == 1
            assert results[0][0] == "https://example.com/specific"
            
            # Verify URL filter
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["filter"] == {"@eq": {"url": "https://example.com/specific"}}

    @pytest.mark.asyncio
    async def test_search_by_url_without_query(self, snowflake_client):
        """Test search by URL without explicit query"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            url = "https://example.com/page"
            await snowflake_client.search_by_url(url=url)
            
            # Verify URL is used as query
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["query"] == url

    @pytest.mark.asyncio
    async def test_get_sites(self, snowflake_client):
        """Test get_sites method"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                ["site1.com"],
                ["site2.com"],
                ["site3.com"]
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            sites = await snowflake_client.get_sites()
            
            assert sites == ["site1.com", "site2.com", "site3.com"]
            
            # Verify SQL statement
            call_args = mock_client.post.call_args
            assert "/api/v2/statements" in call_args[0][0]
            assert "CORTEX_SEARCH_DATA_SCAN" in call_args[1]["json"]["statement"]

    @pytest.mark.asyncio
    async def test_get_sites_empty(self, snowflake_client):
        """Test get_sites with empty result"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            sites = await snowflake_client.get_sites()
            assert sites == []


class TestSnowflakeCortexClientHelpers:
    """Tests for helper methods"""

    def test_create_site_filter_single_site(self, snowflake_client):
        """Test site filter creation for single site"""
        filter_obj = snowflake_client._create_site_filter("example.com")
        assert filter_obj == {"@eq": {"site": "example.com"}}

    def test_create_site_filter_multiple_sites(self, snowflake_client):
        """Test site filter creation for multiple sites"""
        filter_obj = snowflake_client._create_site_filter(["site1.com", "site2.com"])
        expected = {
            "@or": [
                {"@eq": {"site": "site1.com"}},
                {"@eq": {"site": "site2.com"}}
            ]
        }
        assert filter_obj == expected

    def test_create_site_filter_all(self, snowflake_client):
        """Test site filter returns None for 'all'"""
        assert snowflake_client._create_site_filter("all") is None

    def test_create_site_filter_all_in_list(self, snowflake_client):
        """Test site filter returns None when 'all' is in list"""
        assert snowflake_client._create_site_filter(["all", "site1.com"]) is None

    def test_create_site_filter_single_item_list(self, snowflake_client):
        """Test site filter for list with single item"""
        filter_obj = snowflake_client._create_site_filter(["example.com"])
        assert filter_obj == {"@eq": {"site": "example.com"}}

    def test_process_result(self, snowflake_client):
        """Test result processing"""
        result = {
            "url": "https://example.com/doc",
            "site": "example.com",
            "schema_json": '{"name": "Test Document", "type": "article"}'
        }
        
        processed = snowflake_client._process_result(result)
        
        assert processed[0] == "https://example.com/doc"
        assert processed[1] == '{"name": "Test Document", "type": "article"}'
        assert processed[2] == "Test Document"
        assert processed[3] == "example.com"

    def test_process_result_missing_fields(self, snowflake_client):
        """Test result processing with missing fields"""
        result = {}
        
        processed = snowflake_client._process_result(result)
        
        assert processed[0] == ""
        assert processed[1] == "{}"
        assert processed[2] == ""
        assert processed[3] == ""

    def test_name_from_schema_json_valid(self, snowflake_client):
        """Test extracting name from valid schema JSON"""
        schema_json = '{"name": "My Document", "type": "page"}'
        name = snowflake_client._name_from_schema_json(schema_json)
        assert name == "My Document"

    def test_name_from_schema_json_no_name(self, snowflake_client):
        """Test extracting name from schema JSON without name field"""
        schema_json = '{"type": "page"}'
        name = snowflake_client._name_from_schema_json(schema_json)
        assert name == ""

    def test_name_from_schema_json_invalid(self, snowflake_client):
        """Test extracting name from invalid JSON"""
        schema_json = "not valid json"
        name = snowflake_client._name_from_schema_json(schema_json)
        assert name == ""
