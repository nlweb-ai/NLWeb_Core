# NLWeb Package Installation Guide

This guide explains how to make the NLWeb packages pip-installable, first for local testing, then for PyPI publication.

## Overview

We have 5 packages to install:
1. `nlweb-core` - Core framework
2. `nlweb-retrieval` - Retrieval providers bundle
3. `nlweb-models` - LLM/embedding providers bundle
4. `nlweb-azure-vectordb` - Azure AI Search provider
5. `nlweb-azure-models` - Azure OpenAI providers

## Local Installation for Testing

### Method 1: Editable Install (Recommended for Development)

Editable installs allow you to modify the code and see changes immediately without reinstalling.

#### Step 1: Install Core Package First

```bash
cd /Users/rvguha/code/NLWeb_Core/packages/core
pip install -e .
```

This installs `nlweb-core` in editable mode. The `-e` flag means changes to the source code are immediately reflected.

#### Step 2: Install Provider Bundles

```bash
# Install retrieval bundle
cd /Users/rvguha/code/NLWeb_Core/packages/bundles/retrieval
pip install -e .

# Install models bundle
cd /Users/rvguha/code/NLWeb_Core/packages/bundles/models
pip install -e .
```

#### Step 3: Install Azure Blueprint Packages (Optional)

```bash
# Install Azure vector DB
cd /Users/rvguha/code/NLWeb_Core/packages/providers/azure/vectordb
pip install -e .

# Install Azure models
cd /Users/rvguha/code/NLWeb_Core/packages/providers/azure/models
pip install -e .
```

#### Step 4: Verify Installation

```bash
# Check all packages are installed
pip list | grep nlweb

# Should show:
# nlweb-azure-models      0.5.0    /Users/rvguha/code/NLWeb_Core/packages/providers/azure/models
# nlweb-azure-vectordb    0.5.0    /Users/rvguha/code/NLWeb_Core/packages/providers/azure/vectordb
# nlweb-core              0.5.0    /Users/rvguha/code/NLWeb_Core/packages/core
# nlweb-models            0.5.0    /Users/rvguha/code/NLWeb_Core/packages/bundles/models
# nlweb-retrieval         0.5.0    /Users/rvguha/code/NLWeb_Core/packages/bundles/retrieval
```

### Method 2: Local Build and Install

If you want to test the actual installation process (not editable):

#### Step 1: Build Packages

```bash
# Install build tools
pip install build twine

# Build core package
cd /Users/rvguha/code/NLWeb_Core/packages/core
python -m build

# Build other packages
cd /Users/rvguha/code/NLWeb_Core/packages/bundles/retrieval
python -m build

cd /Users/rvguha/code/NLWeb_Core/packages/bundles/models
python -m build

cd /Users/rvguha/code/NLWeb_Core/packages/providers/azure/vectordb
python -m build

cd /Users/rvguha/code/NLWeb_Core/packages/providers/azure/models
python -m build
```

This creates `dist/` directories with `.whl` and `.tar.gz` files for each package.

#### Step 2: Install from Built Packages

```bash
# Install core first
pip install /Users/rvguha/code/NLWeb_Core/packages/core/dist/nlweb_core-0.5.0-py3-none-any.whl

# Install bundles
pip install /Users/rvguha/code/NLWeb_Core/packages/bundles/retrieval/dist/nlweb_retrieval-0.5.0-py3-none-any.whl
pip install /Users/rvguha/code/NLWeb_Core/packages/bundles/models/dist/nlweb_models-0.5.0-py3-none-any.whl

# Install Azure packages
pip install /Users/rvguha/code/NLWeb_Core/packages/providers/azure/vectordb/dist/nlweb_azure_vectordb-0.5.0-py3-none-any.whl
pip install /Users/rvguha/code/NLWeb_Core/packages/providers/azure/models/dist/nlweb_azure_models-0.5.0-py3-none-any.whl
```

### Method 3: Install All at Once (Quick Script)

Create a script `install_all_editable.sh`:

```bash
#!/bin/bash
# Script to install all NLWeb packages in editable mode

set -e  # Exit on error

PACKAGES_DIR="/Users/rvguha/code/NLWeb_Core/packages"

echo "Installing NLWeb packages in editable mode..."
echo ""

# Install core first (required by all others)
echo "1/5 Installing nlweb-core..."
cd "$PACKAGES_DIR/core"
pip install -e .
echo ""

# Install bundles
echo "2/5 Installing nlweb-retrieval..."
cd "$PACKAGES_DIR/bundles/retrieval"
pip install -e .
echo ""

echo "3/5 Installing nlweb-models..."
cd "$PACKAGES_DIR/bundles/models"
pip install -e .
echo ""

# Install Azure packages
echo "4/5 Installing nlweb-azure-vectordb..."
cd "$PACKAGES_DIR/providers/azure/vectordb"
pip install -e .
echo ""

echo "5/5 Installing nlweb-azure-models..."
cd "$PACKAGES_DIR/providers/azure/models"
pip install -e .
echo ""

echo "✓ All packages installed successfully!"
echo ""
echo "Verify with: pip list | grep nlweb"
```

Run it:
```bash
chmod +x install_all_editable.sh
./install_all_editable.sh
```

## Testing the Installation

### Test 1: Import Test

```python
# test_imports.py
import nlweb_core
from nlweb_core import config, retriever, llm, embedding

# Test Azure imports
from nlweb_azure_vectordb import azure_search_client
from nlweb_azure_models.llm import azure_oai
from nlweb_azure_models.embedding import azure_oai_embedding

# Test bundle imports
from nlweb_retrieval import elasticsearch_client, qdrant
from nlweb_models.llm import openai, anthropic
from nlweb_models.embedding import openai_embedding

print("✓ All imports successful!")
```

Run:
```bash
python test_imports.py
```

### Test 2: Run Example Application

```bash
cd /Users/rvguha/code/NLWeb_Core/examples/azure_hello_world
python hello_world.py
```

### Test 3: Verify Package Dependencies

```bash
# Check that dependencies were installed
pip list | grep -E "openai|anthropic|azure|elasticsearch|qdrant"

# Should show all provider packages installed automatically
```

## Uninstalling for Clean Testing

To start fresh:

```bash
# Uninstall all NLWeb packages
pip uninstall -y nlweb-core nlweb-retrieval nlweb-models nlweb-azure-vectordb nlweb-azure-models

# Verify they're gone
pip list | grep nlweb
```

## Publishing to PyPI (Production)

Once local testing is complete, publish to PyPI.

### Step 1: Create PyPI Account

1. Go to https://pypi.org/account/register/
2. Create an account
3. Verify your email
4. Set up 2FA (required)

### Step 2: Create API Token

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Name it (e.g., "NLWeb Packages")
4. Scope: "Entire account" or per-project
5. Copy the token (starts with `pypi-`)

### Step 3: Configure PyPI Credentials

Create `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-your-token-here
```

Or use environment variable:
```bash
export TWINE_PASSWORD=pypi-your-token-here
```

### Step 4: Build All Packages

```bash
cd /Users/rvguha/code/NLWeb_Core/packages

# Build each package
for package in core bundles/retrieval bundles/models providers/azure/vectordb providers/azure/models; do
    echo "Building $package..."
    cd "$package"
    rm -rf dist build *.egg-info  # Clean old builds
    python -m build
    cd /Users/rvguha/code/NLWeb_Core/packages
done
```

### Step 5: Check Packages Before Upload

```bash
# Check packages for issues
twine check packages/core/dist/*
twine check packages/bundles/retrieval/dist/*
twine check packages/bundles/models/dist/*
twine check packages/providers/azure/vectordb/dist/*
twine check packages/providers/azure/models/dist/*
```

### Step 6: Upload to TestPyPI (Optional but Recommended)

Test on TestPyPI first:

```bash
# Upload to TestPyPI
twine upload --repository testpypi packages/core/dist/*
twine upload --repository testpypi packages/bundles/retrieval/dist/*
twine upload --repository testpypi packages/bundles/models/dist/*
twine upload --repository testpypi packages/providers/azure/vectordb/dist/*
twine upload --repository testpypi packages/providers/azure/models/dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ nlweb-core
```

Note: `--extra-index-url https://pypi.org/simple/` is needed because dependencies are on real PyPI.

### Step 7: Upload to Real PyPI

Once TestPyPI works:

```bash
# Upload core first
twine upload packages/core/dist/*

# Upload bundles
twine upload packages/bundles/retrieval/dist/*
twine upload packages/bundles/models/dist/*

# Upload Azure packages
twine upload packages/providers/azure/vectordb/dist/*
twine upload packages/providers/azure/models/dist/*
```

### Step 8: Verify PyPI Publication

```bash
# Check packages are available
pip search nlweb  # (if search is enabled)

# Or visit:
# https://pypi.org/project/nlweb-core/
# https://pypi.org/project/nlweb-retrieval/
# https://pypi.org/project/nlweb-models/
# https://pypi.org/project/nlweb-azure-vectordb/
# https://pypi.org/project/nlweb-azure-models/
```

### Step 9: Test Installation from PyPI

In a clean environment:

```bash
# Create new virtual environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install from PyPI
pip install nlweb-core nlweb-azure-vectordb nlweb-azure-models

# Test
python -c "import nlweb_core; print('Success!')"
```

## Publishing Updates

When you make changes and want to publish a new version:

### Step 1: Update Version Numbers

Edit `pyproject.toml` in each package:

```toml
[project]
name = "nlweb-core"
version = "0.5.1"  # Increment version
```

### Step 2: Rebuild and Upload

```bash
cd /Users/rvguha/code/NLWeb_Core/packages/core
rm -rf dist build *.egg-info
python -m build
twine check dist/*
twine upload dist/*
```

Repeat for all packages that changed.

## Troubleshooting

### Issue: "Package already exists"

You can't re-upload the same version. Increment the version number in `pyproject.toml`.

### Issue: "ModuleNotFoundError" after installation

Make sure dependencies are installed:
```bash
pip install --upgrade nlweb-core nlweb-retrieval nlweb-models
```

### Issue: Editable install not reflecting changes

Restart Python interpreter or:
```bash
pip install -e . --force-reinstall --no-deps
```

### Issue: Dependency conflicts

Create a fresh virtual environment:
```bash
python -m venv fresh_env
source fresh_env/bin/activate
pip install nlweb-core nlweb-azure-vectordb nlweb-azure-models
```

### Issue: Can't import from packages

Check package structure:
```bash
# Verify __init__.py files exist
find packages -name "__init__.py"
```

## Best Practices

1. **Always test locally first** - Use editable installs during development
2. **Use TestPyPI** - Test the full installation process before real PyPI
3. **Version consistently** - Update all dependent packages together
4. **Document changes** - Keep a CHANGELOG.md
5. **Tag releases** - Use git tags matching version numbers
6. **Test in clean environment** - Always test final packages in fresh venv
7. **Check dependencies** - Ensure all dependencies are available on PyPI

## Automation (CI/CD)

For automated publishing, create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install build tools
        run: pip install build twine

      - name: Build packages
        run: |
          cd packages/core && python -m build && cd ../..
          cd packages/bundles/retrieval && python -m build && cd ../../..
          cd packages/bundles/models && python -m build && cd ../../..
          cd packages/providers/azure/vectordb && python -m build && cd ../../../..
          cd packages/providers/azure/models && python -m build && cd ../../../..

      - name: Publish to PyPI
        env:
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: |
          twine upload packages/core/dist/*
          twine upload packages/bundles/retrieval/dist/*
          twine upload packages/bundles/models/dist/*
          twine upload packages/providers/azure/vectordb/dist/*
          twine upload packages/providers/azure/models/dist/*
```

## Quick Reference

### Local Testing Commands
```bash
# Editable install all packages
pip install -e packages/core
pip install -e packages/bundles/retrieval
pip install -e packages/bundles/models
pip install -e packages/providers/azure/vectordb
pip install -e packages/providers/azure/models

# Test
python examples/azure_hello_world/hello_world.py
```

### Build Commands
```bash
cd packages/core && python -m build
cd packages/bundles/retrieval && python -m build
cd packages/bundles/models && python -m build
cd packages/providers/azure/vectordb && python -m build
cd packages/providers/azure/models && python -m build
```

### Publish Commands
```bash
twine upload packages/core/dist/*
twine upload packages/bundles/retrieval/dist/*
twine upload packages/bundles/models/dist/*
twine upload packages/providers/azure/vectordb/dist/*
twine upload packages/providers/azure/models/dist/*
```

## Summary

**For Testing**: Use Method 1 (editable installs) - allows immediate code changes
**For Publishing**: Follow the PyPI publication steps after thorough local testing

The key is to always install `nlweb-core` first, then the provider packages, since they depend on core.
