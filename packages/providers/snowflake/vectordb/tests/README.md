# Snowflake Cortex Search Tests

This directory contains comprehensive tests for the Snowflake Cortex Search client.

## Test Structure

- `test_snowflake_cortex_client.py`: Client initialization, search, and filtering tests

## Running Tests

From the package root directory:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=nlweb_snowflake_vectordb --cov-report=html

# Run specific test file
pytest tests/test_snowflake_cortex_client.py

# Run with verbose output
pytest -v
```

## Test Coverage

Tests use mocked HTTP clients and configuration to avoid requiring actual Snowflake credentials or services.
