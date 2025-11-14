# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Pytest configuration and fixtures for Snowflake Cortex Search tests
"""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_config():
    """Mock CONFIG object for testing"""
    config = MagicMock()
    config.write_endpoint = "test_endpoint"
    
    # Mock endpoint config
    endpoint_config = MagicMock()
    endpoint_config.db_type = "snowflake_cortex_search"
    endpoint_config.api_endpoint = "https://test-account.snowflakecomputing.com"
    endpoint_config.api_key = "test_pat_token"
    endpoint_config.index_name = "TEST_DB.TEST_SCHEMA.TEST_SERVICE"
    endpoint_config.vector_dimensions = 1024
    
    config.retrieval_endpoints = {"test_endpoint": endpoint_config}
    
    return config
