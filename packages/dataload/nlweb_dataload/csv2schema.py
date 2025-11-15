# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
CSV parser that converts CSV files to schema.org Article format.

Converts CSV rows into schema.org Article objects for consistent 
processing in NLWeb. Supports flexible column mapping.
"""

import csv
import aiohttp
from typing import List, Dict, Any, Optional
from pathlib import Path


async def parse_csv_to_schema(
    file_path: str,
    name_column: Optional[str] = None,
    identifier_column: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Parse CSV file and convert to schema.org 'Thing' format.
    
    Automatically uses the first row as column headers and includes all columns
    as properties in the schema.org Thing. This is ideal for structured data
    like companies, products, people, etc.
    
    Args:
        file_path: Path or URL to CSV file
        name_column: Optional column to use as the name/title. 
                    If not specified, uses the first column.
        identifier_column: Optional column to use as unique identifier.
                          If not specified, uses row index.
    
    Returns:
        List of schema.org Thing dicts
    
    Example:
        # Load CSV with automatic column detection
        things = await parse_csv_to_schema("companies.csv")
        
        # Specify which column to use as the name
        things = await parse_csv_to_schema(
            "companies.csv",
            name_column="company_name"
        )
        
        # Specify identifier column for unique IDs
        things = await parse_csv_to_schema(
            "companies.csv",
            name_column="company_name",
            identifier_column="company_id"
        )
    """
    try:
        print(f"[CSV2SCHEMA] Loading CSV from {file_path}")
        
        # Determine if this is a URL or local file
        is_url = file_path.startswith('http://') or file_path.startswith('https://')
        
        if is_url:
            # Fetch CSV content from URL
            async with aiohttp.ClientSession() as session:
                async with session.get(file_path) as response:
                    print(f"[CSV2SCHEMA] HTTP status: {response.status}")
                    
                    if response.status >= 400:
                        print(f"[CSV2SCHEMA] Error: HTTP {response.status} when fetching CSV")
                        return []
                    
                    csv_content = await response.text()
                    print(f"[CSV2SCHEMA] Downloaded {len(csv_content)} bytes")
            
            # Parse CSV content from string
            rows = list(csv.DictReader(csv_content.splitlines()))
        else:
            # Local file - read directly
            with open(file_path, 'r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
        
        if not rows:
            print(f"[CSV2SCHEMA] No rows found in CSV: {file_path}")
            return []
        
        print(f"[CSV2SCHEMA] Found {len(rows)} rows in CSV")
        columns = list(rows[0].keys())
        print(f"[CSV2SCHEMA] Columns: {columns}")
        
        # Determine which column to use as name
        if name_column:
            if name_column not in columns:
                print(f"[CSV2SCHEMA] Warning: Specified name column '{name_column}' not found")
                print(f"[CSV2SCHEMA] Available columns: {columns}")
                print(f"[CSV2SCHEMA] Using first column '{columns[0]}' as name")
                name_column = columns[0]
        else:
            # Use first column as name by default
            name_column = columns[0]
            print(f"[CSV2SCHEMA] Using first column '{name_column}' as name")
        
        # Determine identifier column
        if identifier_column and identifier_column not in columns:
            print(f"[CSV2SCHEMA] Warning: Specified identifier column '{identifier_column}' not found")
            print(f"[CSV2SCHEMA] Will use row index as identifier")
            identifier_column = None
        
        if identifier_column:
            print(f"[CSV2SCHEMA] Using column '{identifier_column}' as unique identifier")
        else:
            print(f"[CSV2SCHEMA] Using row index as unique identifier")
        
        # Convert each row to schema.org Thing
        things = []
        for i, row in enumerate(rows, start=1):
            thing = _row_to_schema_thing(
                row,
                i,
                name_column,
                identifier_column,
                columns
            )
            if thing:
                things.append(thing)
        
        print(f"[CSV2SCHEMA] Converted {len(things)} rows to schema.org format")
        return things
        
    except Exception as e:
        print(f"[CSV2SCHEMA] Error parsing CSV {file_path}: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def _row_to_schema_thing(
    row: Dict[str, str],
    row_index: int,
    name_column: str,
    identifier_column: Optional[str],
    all_columns: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Convert a CSV row to schema.org Thing format.
    
    Args:
        row: Dictionary representing a CSV row
        row_index: Row number (for fallback identifier)
        name_column: Name of the column to use as name
        identifier_column: Column to use as unique identifier (optional)
        all_columns: List of all column names from the CSV
    
    Returns:
        schema.org Thing dict or None if name is missing
    """
    # Get the name from the specified column
    name = row.get(name_column, '').strip()
    
    # Skip rows without a name
    if not name:
        return None
    
    # Get identifier (use specified column or row index)
    if identifier_column:
        identifier = row.get(identifier_column, '').strip() or str(row_index)
    else:
        identifier = str(row_index)
    
    # Build schema.org Thing with basic fields
    thing = {
        '@context': 'http://schema.org',
        '@type': 'Thing',
        '@id': identifier,  # Unique identifier for this thing
        'name': name,
    }
    
    # Add all CSV columns as properties
    # This preserves all your data in the schema.org format
    for col in all_columns:
        if col in row and row[col].strip():
            value = row[col].strip()
            # Use the original column name as the property name
            thing[col] = value
            
            # Map common column names to standard schema.org properties
            col_lower = col.lower()
            if col_lower == 'description' and 'description' not in thing:
                thing['description'] = value
            elif col_lower == 'url' and 'url' not in thing:
                thing['url'] = value
            elif col_lower in ['id', 'identifier'] and col != identifier_column:
                thing['identifier'] = value
    
    return thing
