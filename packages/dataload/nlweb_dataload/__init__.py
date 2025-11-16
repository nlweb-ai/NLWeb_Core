# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
NLWeb Data Loading - Standalone tools for loading schema.org data into vector databases.

This package provides utilities for loading schema.org JSON files and RSS feeds
into vector databases with automatic embedding generation.

Does not depend on nlweb-core - includes its own minimal config and embedding wrapper.
"""

__version__ = "0.5.5"

from .config import init
from .db_load import (
    load_to_db,
    delete_site
)

__all__ = [
    'init',
    'load_to_db',
    'delete_site'
]
