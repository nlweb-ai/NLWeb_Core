# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
PostgreSQL Vector Database Client using pgvector - Interface for PostgreSQL operations.
This client provides vector similarity search functionality using the pgvector extension.
Uses psycopg3 for improved async support and performance.
"""

import json
import os
import asyncio
import time
from typing import List, Dict, Union, Optional, Any, Tuple, Set

from urllib.parse import urlparse, parse_qs

# PostgreSQL client library (psycopg3)
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
import pgvector.psycopg

from nlweb_core.config import CONFIG
from nlweb_core.retriever import VectorDBClientInterface
from nlweb_core.embedding import get_embedding


class PgVectorClient(VectorDBClientInterface):
    """
    Client for PostgreSQL vector database operations with pgvector extension.
    Provides a unified interface for indexing, storing, and retrieving vector-based search results.

    Requirements:
    - PostgreSQL database with pgvector extension installed
    - A configured table with vector type column for embeddings
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the PostgreSQL vector database client.

        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        super().__init__()  # Initialize the base class with caching
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        self._conn_lock = asyncio.Lock()
        self._pool = None
        self._pool_init_lock = asyncio.Lock()
        
        
        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        self.api_endpoint = self.endpoint_config.api_endpoint
        self.api_key = self.endpoint_config.api_key
        self.database_path = self.endpoint_config.database_path
        self.default_collection_name = self.endpoint_config.index_name or "nlweb_collection"

        self.pg_raw_config = self._get_config_from_postgres_connection_string(self.api_endpoint)
        
        self.host = self.pg_raw_config.get("host")
        self.port = self.pg_raw_config.get("port", 5432)  # Default PostgreSQL port
        self.dbname = self.pg_raw_config.get("database") 
        self.username = self.pg_raw_config.get("username") 
        self.password = self.api_key or self.pg_raw_config.get("password")
        self.table_name = self.default_collection_name or "documents"

        # Validate critical configuration
        if not self.host:
            error_msg = f"Missing 'host' in PostgreSQL configuration for endpoint '{self.endpoint_name}'"
            raise ValueError(error_msg)
        if not self.dbname:
            error_msg = f"Missing 'database_name' in PostgreSQL configuration for endpoint '{self.endpoint_name}'"
            raise ValueError(error_msg)
        
    
    def _get_config_from_postgres_connection_string(self, connection_string: str) -> Dict[str, Any]:
        """
        Parse the PostgreSQL connection string and return a dictionary of configuration parameters.
        
        Args:
            connection_string: PostgreSQL connection string
        Returns:
            Dictionary of configuration parameters
        """
        parsed_url = urlparse(connection_string)
        
        host = parsed_url.hostname
        port = parsed_url.port
        database = parsed_url.path[1:]  # remove leading slash
        query_params = parse_qs(parsed_url.query)
        
        username = query_params.get('user', [None])[0]
        password = query_params.get('password', [None])[0]
        
        return {
            'host': host,
            'port': port,
            'database': database,
            'username': username,
            'password': password
        }

    def _get_endpoint_config(self):
        """
        Get the PostgreSQL endpoint configuration from CONFIG
        
        Returns:
            Tuple of (RetrievalProviderConfig)
        """
        # Get the endpoint configuration object
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            raise ValueError(error_msg)
        
        # Verify this is a PostgreSQL endpoint
        if endpoint_config.db_type != "postgres":
            error_msg = f"Endpoint {self.endpoint_name} is not a PostgreSQL endpoint (type: {endpoint_config.db_type})"
            raise ValueError(error_msg)
        
        # Get the raw configuration dictionary from the YAML file
        config_dir = os.path.dirname(os.path.abspath(os.path.join(os.path.dirname(__file__), "../config")))
        config_path = os.path.join(config_dir, "config_retrieval.yaml")

        return endpoint_config
    
    async def _get_connection_pool(self):
        """
        Get or create the connection pool for PostgreSQL.
        Connection pooling is used for better performance and resource management.
        
        Returns:
            A PostgreSQL connection pool
        """
        if self._pool is None:
            async with self._pool_init_lock:
                if self._pool is None:
                    
                    try:
                        # Make sure we have all required connection parameters
                        if not self.host:
                            raise ValueError("Missing host in PostgreSQL configuration")
                        if not self.dbname:
                            raise ValueError("Missing database_name in PostgreSQL configuration")
                        if not self.username:
                            raise ValueError("Missing username or username_env in PostgreSQL configuration")
                        if not self.password:
                            raise ValueError("Missing password or password_env in PostgreSQL configuration")
                            
                        # Log connection attempt (without sensitive information)
                        
                        # Set up async connection pool with reasonable defaults
                        conninfo = f"host={self.host} port={self.port} dbname={self.dbname} user={self.username} password={self.password}"
                        self._pool = AsyncConnectionPool(
                            conninfo=conninfo,
                            min_size=1,
                            max_size=10, 
                            open=False # Don't open immediately, we will do it explicitly later
                        )
                        # Explicitly open the pool as recommended in newer psycopg versions
                        await self._pool.open()
                        
                        # Verify pgvector extension is installed
                        async with self._pool.connection() as conn:
                            # Register vector type
                            await pgvector.psycopg.register_vector_async(conn)
                            
                            async with conn.cursor() as cur:
                                await cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
                                row = await cur.fetchone()
                                if not row:
                                    pass

                    except Exception as e:
                        raise
        
        return self._pool

    async def close(self):
        """Close the connection pool when done"""
        if self._pool:
            await self._pool.close()
    
    async def _execute_with_retry(self, query_func, max_retries=3, initial_backoff=0.1):
        """
        Execute a database query with retry logic for transient failures.
        
        Args:
            query_func: Function that performs the database query
            max_retries: Maximum number of retry attempts
            initial_backoff: Initial backoff time in seconds (doubles with each retry)
            
        Returns:
            Query result
        """
        retry_count = 0
        backoff_time = initial_backoff
        
        while True:
            try:
                # With psycopg3, we can use async directly
                async with (await self._get_connection_pool()).connection() as conn:
                    # Register vector type
                    await pgvector.psycopg.register_vector_async(conn)
                    return await query_func(conn)
            
            except (psycopg.OperationalError, psycopg.InternalError) as e:
                # Handle transient errors like connection issues
                retry_count += 1
                
                if retry_count > max_retries:
                    raise
                
                
                await asyncio.sleep(backoff_time)
                backoff_time *= 2  # Exponential backoff
            
            except Exception as e:
                # Non-transient errors are raised immediately
                raise

    async def search(self, query: str, site: Union[str, List[str]],
                    num_results: int = 50, query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search for documents matching the query and site.
        
        Args:
            query: Search query string
            site: Site identifier or list of sites
            num_results: Maximum number of results to return
            **kwargs: Additional parameters (e.g., similarity_metric)
            
        Returns:
            List of search results, where each result is a list of strings:
            [url, schema_json, name, site]
        """
        start_time = time.time()
        
        # Get vector embedding for the query
        try:
            query_embedding = await get_embedding(query, query_params=query_params)
        except Exception as e:
            raise
        
        # Process site parameter
        sites = []
        if isinstance(site, list):
            sites = site
        elif isinstance(site, str) and site != "all":
            sites = [site]
        
        similarity_metric = kwargs.get("similarity_metric", "cosine")  # Default to cosine similarity
        
        # Select appropriate similarity function based on metric
        similarity_func = {
            "cosine": "<=>",          # Cosine distance
            "inner_product": "<#>",    # Negative inner product
            "euclidean": "<->",        # Euclidean distance
        }.get(similarity_metric, "<=>")  # Default to cosine
        
        async def _search_docs(conn):
            # Use dict_row to get results as dictionaries
            async with conn.cursor(row_factory=dict_row) as cur:
                # Build WHERE clause for site filtering if needed
                where_clause = ""
                params = [query_embedding]
                
                if sites:
                    # Create placeholders for site parameters
                    site_placeholders = ", ".join(["%s"] * len(sites))
                    where_clause = f"WHERE site IN ({site_placeholders})"
                    params.extend(sites)
                
                # Construct and execute query
                query_sql = f"""
                    SELECT 
                        name,
                        url,
                        embedding {similarity_func} %s::vector AS similarity_score,
                        site,
                        schema_json
                    FROM {self.table_name}
                    {where_clause}
                    ORDER BY similarity_score
                    LIMIT %s
                """
                
                params.append(num_results)
                await cur.execute(query_sql, params)
                rows = await cur.fetchall()
                
                # Format results
                results = []
                for row in rows:
                    result = [
                        row["url"],
                        json.dumps(row["schema_json"], indent=4),
                        row["name"],
                        row["site"],
                    ]
                    results.append(result)
                
                return results
        
        try:
            results = await self._execute_with_retry(_search_docs)
            
            end_time = time.time()
            search_duration = end_time - start_time
            
            return results
        except Exception as e:
            raise

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection to the PostgreSQL database and return diagnostic information.
        This is useful for debugging connection issues.
        
        Returns:
            Dict with connection status and diagnostic information
        """
        
        async def _test_connection(conn):
            result = {
                "success": False,
                "database_version": None,
                "pgvector_installed": False,
                "table_exists": False,
                "document_count": 0,
                "configuration": {
                    "host": self.host,
                    "port": self.port,
                    "database": self.dbname,
                    "username": self.username,
                    "table": self.table_name
                }
            }
            
            try:
                # Test basic connection and get PostgreSQL version
                async with conn.cursor() as cur:
                    await cur.execute("SELECT version()")
                    row = await cur.fetchone()
                    version = row[0]
                    result["database_version"] = version
                    result["success"] = True
                    
                    # Check if pgvector extension is installed
                    await cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
                    row = await cur.fetchone()
                    result["pgvector_installed"] = row is not None
                    
                    # Check if our table exists
                    await cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = %s
                        )
                    """, (self.table_name,))
                    row = await cur.fetchone()
                    result["table_exists"] = row[0]
                    
                    # If table exists, get document count
                    if result["table_exists"]:
                        await cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                        row = await cur.fetchone()
                        result["document_count"] = row[0]
                        
            except Exception as e:
                result["error"] = str(e)
                
            return result
        
        try:
            return await self._execute_with_retry(_test_connection)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "configuration": {
                    "host": self.host,
                    "port": self.port,
                    "database": self.dbname,
                    "username": self.username,
                    "table": self.table_name
                }
            }

    async def check_table_schema(self) -> Dict[str, Any]:
        """
        Check if the database table schema is correctly set up.
        This helps diagnose issues with table schema that could prevent document uploads.
        
        Returns:
            Dict with table schema information
        """
        
        async def _check_schema(conn):
            schema_info = {
                "table_exists": False,
                "columns": {},
                "has_vector_column": False,
                "vector_indexes": [],
                "primary_key": None,
                "needs_corrections": []
            }
            
            try:
                async with conn.cursor(row_factory=dict_row) as cur:
                    # Check if table exists
                    await cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = %s
                        )
                    """, (self.table_name,))
                    row = await cur.fetchone()
                    schema_info["table_exists"] = row["exists"]
                    
                    if not schema_info["table_exists"]:
                        schema_info["needs_corrections"].append(
                            f"Table '{self.table_name}' does not exist. Create it using the setup SQL script."
                        )
                        return schema_info
                    
                    # Get column information
                    await cur.execute("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = %s
                    """, (self.table_name,))
                    
                    columns = await cur.fetchall()
                    for col in columns:
                        schema_info["columns"][col["column_name"]] = {
                            "data_type": col["data_type"],
                            "is_nullable": col["is_nullable"]
                        }
                    
                    # Check for required columns
                    required_columns = {
                        "id": "text",
                        "name": "text",
                        "url": "text",
                        "schema_json": "jsonb",
                        "site": "text",
                        "embedding": "vector",  # Adjust dimension to match your model
                        }
                    
                    for col_name, col_type in required_columns.items():
                        if col_name not in schema_info["columns"]:
                            schema_info["needs_corrections"].append(
                                f"Missing required column '{col_name}' of type '{col_type}'"
                            )
                    
                    # Check for vector column (pgvector special handling)
                    await cur.execute("""
                        SELECT a.attname, format_type(a.atttypid, a.atttypmod) as data_type
                        FROM pg_attribute a
                        JOIN pg_class c ON a.attrelid = c.oid
                        JOIN pg_namespace n ON c.relnamespace = n.oid
                        WHERE c.relname = %s
                        AND a.attnum > 0
                        AND NOT a.attisdropped
                    """, (self.table_name,))
                    
                    pg_columns = await cur.fetchall()
                    for col in pg_columns:
                        if "vector" in col["data_type"]:
                            schema_info["has_vector_column"] = True
                            schema_info["vector_column"] = col["attname"]
                            schema_info["vector_dimension"] = col["data_type"]
                    
                    if not schema_info["has_vector_column"]:
                        schema_info["needs_corrections"].append(
                            "Missing vector column for embeddings. Add a column of type vector(1536)."
                        )
                    
                    # Check for indexes (including vector indexes)
                    await cur.execute("""
                        SELECT
                            i.relname as index_name,
                            array_agg(a.attname) as column_names,
                            ix.indisprimary as is_primary
                        FROM
                            pg_class t,
                            pg_class i,
                            pg_index ix,
                            pg_attribute a
                        WHERE
                            t.oid = ix.indrelid
                            AND i.oid = ix.indexrelid
                            AND a.attrelid = t.oid
                            AND a.attnum = ANY(ix.indkey)
                            AND t.relkind = 'r'
                            AND t.relname = %s
                        GROUP BY
                            i.relname,
                            ix.indisprimary
                    """, (self.table_name,))
                    
                    indexes = await cur.fetchall()
                    for idx in indexes:
                        if idx["is_primary"]:
                            schema_info["primary_key"] = idx["column_names"]
                        
                        # Vector indexes have special naming patterns
                        if any("embedding" in str(col).lower() for col in idx["column_names"]):
                            schema_info["vector_indexes"].append({
                                "name": idx["index_name"],
                                "columns": idx["column_names"]
                            })
                    
                    # Check if primary key exists and is on id column
                    if not schema_info["primary_key"]:
                        schema_info["needs_corrections"].append(
                            "Table is missing a primary key. Add PRIMARY KEY constraint on the id column."
                        )
                    elif "id" not in schema_info["primary_key"]:
                        schema_info["needs_corrections"].append(
                            f"Primary key is not on 'id' column. Current PK: {schema_info['primary_key']}"
                        )
                    
                    # Check if vector index exists
                    if not schema_info["vector_indexes"]:
                        schema_info["needs_corrections"].append(
                            "No vector index found. Create an index on the embedding column for better performance."
                        )
                    
            except Exception as e:
                schema_info["error"] = str(e)
            
            return schema_info
        
        try:
            return await self._execute_with_retry(_check_schema)
        except Exception as e:
            return {
                "error": str(e),
                "table_exists": False,
                "needs_corrections": [f"Exception occurred: {e}"]
            }


# Example usage and testing (disabled in production)
if __name__ == "__main__":
    async def test_pgvector_client():
        """Example test function for the PgVector client"""
        client = PgVectorClient()
        
        # Test connection first
        connection_info = await client.test_connection()
        print("Connection test results:")
        print(f"  Success: {connection_info['success']}")
        if connection_info.get("error"):
            print(f"  Error: {connection_info['error']}")
            return
            
        print(f"  PostgreSQL version: {connection_info['database_version']}")
        print(f"  pgvector installed: {connection_info['pgvector_installed']}")
        print(f"  Table exists: {connection_info['table_exists']}")
        print(f"  Document count: {connection_info['document_count']}")
        
        # Only continue if the connection test was successful
        if connection_info["success"] and connection_info["table_exists"]:
            # Example: Search for a query
            results = await client.search("What is Azure?", site="docs", num_results=3)
            print(f"\nSearch results: Found {len(results)} results")
            for i, result in enumerate(results):
                print(f"Result {i+1}:")
                print(f"  Text: {result[0][:50]}...")
                print(f"  URL: {result[1]}")
                print(f"  Context: {result[2][:30]}..." if result[2] else "  No context")
        
        # Close connection pool
        await client.close()
    
    # Run the test
    # asyncio.run(test_pgvector_client())
