#!/bin/bash
# Upload NLWeb packages to PyPI
# Usage: ./scripts/upload_to_pypi.sh [test|prod]

set -e

MODE=${1:-test}

if [ "$MODE" = "test" ]; then
    REPO="testpypi"
    echo "📦 Uploading to TestPyPI..."
elif [ "$MODE" = "prod" ]; then
    REPO="pypi"
    echo "📦 Uploading to Production PyPI..."
    read -p "⚠️  Are you sure you want to upload to PRODUCTION PyPI? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Upload cancelled."
        exit 1
    fi
else
    echo "Usage: $0 [test|prod]"
    exit 1
fi

# Check if twine is installed
if ! command -v twine &> /dev/null; then
    echo "❌ twine not found. Installing..."
    pip install twine
fi

# Package upload order (respects dependencies)
PACKAGES=(
    "packages/core"               # Core framework
    "packages/dataload"           # Standalone, depends on core for Azure providers
    "packages/network"            # Depends on core
    "packages/providers/azure/models"     # Depends on core (optional)
    "packages/providers/azure/vectordb"   # Depends on core (optional)
    "packages/bundles/retrieval"  # Depends on core + all retrieval providers
    "packages/bundles/models"     # Depends on core + all model providers
)

echo ""
echo "🏗️  Building and uploading packages in dependency order..."
echo ""

for package in "${PACKAGES[@]}"; do
    if [ ! -d "$package" ]; then
        echo "⚠️  Skipping $package (not found)"
        continue
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📦 Processing: $package"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    cd "$package"

    # Extract package name and version from pyproject.toml
    PACKAGE_NAME=$(grep '^name = ' pyproject.toml | sed 's/name = "\(.*\)"/\1/')
    PACKAGE_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

    echo "Package: $PACKAGE_NAME"
    echo "Version: $PACKAGE_VERSION"

    # Check if version already exists on PyPI
    echo "🔍 Checking if version $PACKAGE_VERSION already exists on PyPI..."
    if pip index versions "$PACKAGE_NAME" 2>/dev/null | grep -q "$PACKAGE_VERSION"; then
        echo "⏭️  Version $PACKAGE_VERSION already exists on PyPI, skipping upload"
        cd - > /dev/null
        echo ""
        continue
    fi

    # Clean old builds
    rm -rf dist/ build/ *.egg-info

    # Build package
    echo "🔨 Building..."
    python -m build

    # Upload
    if [ "$REPO" = "testpypi" ]; then
        echo "📤 Uploading to TestPyPI..."
        python -m twine upload --repository testpypi dist/* || echo "⚠️  Upload failed (package may already exist)"
    else
        echo "📤 Uploading to PyPI..."
        python -m twine upload dist/* || echo "⚠️  Upload failed (package may already exist)"
    fi

    cd - > /dev/null

    echo ""
done

echo "✅ All packages processed!"
echo ""

if [ "$REPO" = "testpypi" ]; then
    echo "🧪 Test installation with:"
    echo "   pip install --index-url https://test.pypi.org/simple/ nlweb-dataload"
    echo "   pip install --index-url https://test.pypi.org/simple/ nlweb-core"
    echo "   pip install --index-url https://test.pypi.org/simple/ nlweb-network"
else
    echo "✅ Test installation with:"
    echo "   pip install nlweb-dataload"
    echo "   pip install nlweb-core"
    echo "   pip install nlweb-network"
fi
