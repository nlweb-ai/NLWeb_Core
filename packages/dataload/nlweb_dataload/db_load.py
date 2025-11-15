# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Database loading functions for NLWeb.

Load schema.org JSON files or RSS feeds into vector databases with
automatic embedding generation.
"""

import json
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path

from .embedding import get_embedding
from .writer import get_vector_db_writer
from .rss2schema import parse_rss_to_schema
from .csv2schema import parse_csv_to_schema


async def load_to_db(
    file_path: str,
    site: str,
    endpoint_name: Optional[str] = None,
    batch_size: int = 100,
    file_type: Optional[str] = None,
    csv_name_column: Optional[str] = None,
    csv_identifier_column: Optional[str] = None
) -> Dict[str, Any]:
    """
    Load schema.org data from JSON, RSS, or CSV file into vector database.

    Args:
        file_path: Path to JSON, RSS, or CSV file (local or URL)
        site: Site identifier for all documents
        endpoint_name: Optional endpoint name (defaults to write_endpoint from config)
        batch_size: Number of documents to upload per batch
        file_type: Optional file type hint ('json', 'rss', or 'csv'), auto-detected if not provided
        csv_name_column: For CSV: column name to use as name (default: first column)
        csv_identifier_column: For CSV: column to use as unique identifier (default: row index)

    Returns:
        Dict with loading results (total_loaded, errors)

    Example:
        # Load JSON file
        result = await load_to_db("recipes.json", site="seriouseats")

        # Load RSS feed
        result = await load_to_db("https://example.com/feed.xml", site="example", file_type="rss")
        
        # Load CSV file (auto-detects columns, no URLs needed)
        result = await load_to_db("companies.csv", site="companies", file_type="csv")
        
        # Load CSV with custom name and identifier columns.
        result = await load_to_db(
            "companies.csv", 
            site="companies",
            csv_name_column="company_name",
            csv_identifier_column="company_id"
        )
    """
    # Detect file type if not specified
    if not file_type:
        file_type = _detect_file_type(file_path)

    # Load documents based on file type
    if file_type == 'rss':
        documents = await _load_from_rss(file_path, site)
    elif file_type == 'json':
        documents = await _load_from_json(file_path, site)
    elif file_type == 'csv':
        documents = await _load_from_csv(
            file_path, 
            site,
            csv_name_column,
            csv_identifier_column
        )
    else:
        raise ValueError(f"Unsupported file type: {file_type}. Use 'json', 'rss', or 'csv'")

    if not documents:
        return {'total_loaded': 0, 'errors': []}

    # Compute embeddings for all documents
    documents_with_embeddings = await _compute_embeddings(documents)

    # Get writer and upload in batches
    writer = get_vector_db_writer(endpoint_name)
    total_loaded = 0
    errors = []

    for i in range(0, len(documents_with_embeddings), batch_size):
        batch = documents_with_embeddings[i:i + batch_size]
        batch_num = i//batch_size + 1
        try:
            result = await writer.upload_documents(batch)
            success = result.get('success_count', 0)
            errors_count = result.get('error_count', 0)
            total_loaded += success
            if errors_count > 0:
                errors.append(f"Batch {batch_num}: {errors_count} errors")
        except Exception as e:
            error_msg = f"Batch {batch_num} failed: {str(e)}"
            errors.append(error_msg)

    return {
        'total_loaded': total_loaded,
        'errors': errors
    }


async def delete_site(
    site: str,
    endpoint_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Delete all documents for a specific site.

    Args:
        site: Site identifier
        endpoint_name: Optional endpoint name (defaults to write_endpoint from config)

    Returns:
        Dict with deletion results

    Example:
        result = await delete_site("old-site.com")
    """
    writer = get_vector_db_writer(endpoint_name)
    result = await writer.delete_site(site)
    return result


def _detect_file_type(file_path: str) -> str:
    """
    Detect file type from file path/URL.

    Args:
        file_path: Path or URL to file

    Returns:
        File type ('json', 'rss', or 'csv')
    """
    path_lower = file_path.lower()

    # CSV file patterns
    if path_lower.endswith('.csv'):
        return 'csv'

    # RSS/Atom feed patterns
    if any(pattern in path_lower for pattern in ['.xml', '.rss', '.atom', '/feed', '/rss']):
        return 'rss'

    # JSON file patterns
    if path_lower.endswith('.json') or path_lower.endswith('.jsonl'):
        return 'json'

    # Default to JSON
    return 'json'


async def _load_from_json(file_path: str, site: str) -> List[Dict[str, Any]]:
    """
    Load documents from JSON file.

    Args:
        file_path: Path to JSON file
        site: Site identifier

    Returns:
        List of document dicts
    """
    # Handle URLs
    if file_path.startswith('http://') or file_path.startswith('https://'):
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(file_path) as response:
                content = await response.text()
                data = json.loads(content)
    else:
        # Local file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

    # Handle both single object and array
    if isinstance(data, dict):
        data = [data]
    elif not isinstance(data, list):
        raise ValueError(f"JSON file must contain an object or array, got {type(data)}")

    # Convert to document format
    documents = []
    for item in data:
        # Expect schema.org formatted data
        if not isinstance(item, dict):
            continue

        # Extract required fields
        url = item.get('url') or item.get('@id') or item.get('isBasedOn')
        name = item.get('name') or item.get('headline') or 'Untitled'
        item_type = item.get('@type', 'Unknown')

        if not url:
            continue

        # Create document with schema matching retrieval expectations
        doc = {
            'url': url,
            'type': item_type,
            'site': site,
            'content': json.dumps(item),  # Store full schema.org JSON as content
            'timestamp': None  # Will be set during upload if needed
        }
        documents.append(doc)

    return documents


async def _load_from_rss(file_path: str, site: str) -> List[Dict[str, Any]]:
    """
    Load documents from RSS/Atom feed.

    Args:
        file_path: Path or URL to RSS feed
        site: Site identifier

    Returns:
        List of document dicts
    """
    # Parse RSS to schema.org format
    schema_items = await parse_rss_to_schema(file_path)

    # Convert to document format
    documents = []
    for item in schema_items:
        url = item.get('url') or item.get('@id')
        name = item.get('name') or item.get('headline') or 'Untitled'
        item_type = item.get('@type', 'Unknown')

        if not url:
            continue

        doc = {
            'url': url,
            'type': item_type,
            'site': site,
            'content': json.dumps(item),  # Store full schema.org JSON as content
            'timestamp': None  # Will be set during upload if needed
        }
        documents.append(doc)

    return documents


async def _load_from_csv(
    file_path: str, 
    site: str,
    name_column: Optional[str] = None,
    identifier_column: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Load documents from CSV file.

    Args:
        file_path: Path or URL to CSV file
        site: Site identifier
        name_column: Column name to use as name/title (default: first column)
        identifier_column: Column name to use as unique identifier (default: row index)

    Returns:
        List of document dicts
    """
    # Parse CSV to schema.org format
    schema_items = await parse_csv_to_schema(
        file_path,
        name_column=name_column,
        identifier_column=identifier_column
    )

    # Convert to document format
    documents = []
    for item in schema_items:
        # Use @id as the unique identifier (no URL required)
        identifier = item.get('@id', 'unknown')
        name = item.get('name', 'Untitled')

        doc = {
            'url': f"{site}/{identifier}",  # Generate a reference URL from site and ID
            'name': name,
            'site': site,
            'schema_json': json.dumps(item)
        }
        documents.append(doc)

    return documents


async def _compute_embeddings(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compute embeddings for all documents.

    Args:
        documents: List of document dicts (without embeddings)

    Returns:
        List of document dicts with embeddings added
    """
    # Compute embeddings for all documents
    tasks = []
    for doc in documents:
        # Use content for embedding (it contains the full schema.org JSON)
        schema_data = json.loads(doc['content'])
        text_for_embedding = schema_data.get('description', '') or schema_data.get('name', '') or 'Untitled'
        tasks.append(get_embedding(text_for_embedding))

    # Get all embeddings concurrently
    embeddings = await asyncio.gather(*tasks)

    # Add embeddings to documents
    for doc, embedding in zip(documents, embeddings):
        doc['embedding'] = embedding

    return documents


def main():
    """
    Command-line interface for nlweb-dataload.

    Usage:
        python -m nlweb_dataload.db_load --file <path> --site <site> [options]
        python -m nlweb_dataload.db_load --delete-site <site> [options]
    """
    import argparse
    from .config import init

    parser = argparse.ArgumentParser(
        description='Load schema.org data, RSS feeds, or CSV files into vector databases'
    )
    parser.add_argument('--file', help='Path to JSON, RSS, or CSV file (local or URL)')
    parser.add_argument('--site', help='Site identifier for documents')
    parser.add_argument('--type', choices=['json', 'rss', 'csv'], help='File type (auto-detected if not specified)')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for uploads (default: 100)')
    parser.add_argument('--endpoint', help='Database endpoint name (uses write_endpoint if not specified)')
    parser.add_argument('--config', help='Path to config.yaml (default: ./config.yaml)')
    parser.add_argument('--delete-site', help='Delete all documents for the specified site')
    
    # CSV-specific options
    parser.add_argument('--csv-name-column', help='CSV column name to use as name/title (default: first column)')
    parser.add_argument('--csv-identifier-column', help='CSV column name to use as unique identifier (default: row index)')

    args = parser.parse_args()

    # Initialize config
    init(args.config)

    # Run delete or load
    if args.delete_site:
        result = asyncio.run(delete_site(
            site=args.delete_site,
            endpoint_name=args.endpoint
        ))
        print(f"\n✅ Deleted {result['deleted_count']} documents for site '{args.delete_site}'")
    elif args.file and args.site:
        result = asyncio.run(load_to_db(
            file_path=args.file,
            site=args.site,
            endpoint_name=args.endpoint,
            batch_size=args.batch_size,
            file_type=args.type,
            csv_name_column=args.csv_name_column,
            csv_identifier_column=args.csv_identifier_column
        ))
        print(f"\n✅ Successfully loaded {result['total_loaded']} documents")
        if result['errors']:
            print(f"⚠️  {len(result['errors'])} errors occurred:")
            for error in result['errors'][:5]:  # Show first 5 errors
                print(f"  - {error}")
    else:
        parser.print_help()
        print("\nError: Must specify either --file and --site, or --delete-site")
        exit(1)


if __name__ == '__main__':
    main()
