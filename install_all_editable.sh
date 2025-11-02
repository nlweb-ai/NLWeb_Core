#!/bin/bash
# Script to install all NLWeb packages in editable mode for local testing

set -e  # Exit on error

PACKAGES_DIR="$(cd "$(dirname "$0")/packages" && pwd)"

echo "============================================"
echo "Installing NLWeb packages in editable mode"
echo "============================================"
echo ""

# Install core first (required by all others)
echo "1/5 Installing nlweb-core..."
cd "$PACKAGES_DIR/core"
pip install -e .
echo "    ✓ nlweb-core installed"
echo ""

# Install bundles
echo "2/5 Installing nlweb-retrieval..."
cd "$PACKAGES_DIR/bundles/retrieval"
pip install -e .
echo "    ✓ nlweb-retrieval installed"
echo ""

echo "3/5 Installing nlweb-models..."
cd "$PACKAGES_DIR/bundles/models"
pip install -e .
echo "    ✓ nlweb-models installed"
echo ""

# Install Azure packages
echo "4/5 Installing nlweb-azure-vectordb..."
cd "$PACKAGES_DIR/providers/azure/vectordb"
pip install -e .
echo "    ✓ nlweb-azure-vectordb installed"
echo ""

echo "5/5 Installing nlweb-azure-models..."
cd "$PACKAGES_DIR/providers/azure/models"
pip install -e .
echo "    ✓ nlweb-azure-models installed"
echo ""

echo "============================================"
echo "✓ All packages installed successfully!"
echo "============================================"
echo ""
echo "Installed packages:"
pip list | grep nlweb
echo ""
echo "To test: cd examples/azure_hello_world && python hello_world.py"
