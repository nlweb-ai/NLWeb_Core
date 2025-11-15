# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Centralized version number for all NLWeb packages.

This file contains the single source of truth for version numbers across
all NLWeb packages. Update the VERSION file to bump the version for all packages.
"""

from pathlib import Path

# Read version from VERSION file
_version_file = Path(__file__).parent / "VERSION"
__version__ = _version_file.read_text().strip()
