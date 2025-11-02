# PyPI Setup and Upload Guide

## 🚨 IMPORTANT: Your API Token Was Exposed

The token you shared (`pypi-AgENdGVzdC5weXBpLm9yZw...`) needs to be revoked immediately:

1. Go to https://test.pypi.org/manage/account/token/
2. Delete the exposed token
3. Generate a new one
4. **Never share it again** - not in chat, not in code, not anywhere public

## Setup Steps

### 1. Install Build Tools

```bash
pip install --upgrade build twine
```

### 2. Configure ~/.pypirc

Create or edit `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR_NEW_PRODUCTION_TOKEN_HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR_NEW_TEST_TOKEN_HERE
```

Then secure it:
```bash
chmod 600 ~/.pypirc
```

### 3. Test Upload to TestPyPI First

```bash
# Upload to test environment
./scripts/upload_to_pypi.sh test

# Verify packages uploaded
# Visit: https://test.pypi.org/project/nlweb-dataload/
# Visit: https://test.pypi.org/project/nlweb-core/
# Visit: https://test.pypi.org/project/nlweb-network/

# Test installation
pip install --index-url https://test.pypi.org/simple/ nlweb-dataload
```

### 4. Upload to Production PyPI

```bash
# Upload to production (use with caution!)
./scripts/upload_to_pypi.sh prod
```

## Package Names to Reserve

These package names will be uploaded:
- ✅ `nlweb-dataload` - Standalone data loading
- ✅ `nlweb-core` - Core framework
- ✅ `nlweb-network` - Network interfaces (HTTP/MCP/A2A)
- ✅ `nlweb-azure-vectordb` - Azure AI Search provider
- ✅ `nlweb-azure-models` - Azure OpenAI provider
- ✅ `nlweb-retrieval` - All retrieval providers bundle
- ✅ `nlweb-models` - All model providers bundle

## Manual Upload (Alternative)

If you prefer to upload manually:

```bash
# Build a single package
cd packages/dataload
python -m build

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to Production PyPI
twine upload dist/*
```

## Version Management

Current version: `0.5.0` (in all pyproject.toml files)

To release new versions:
1. Update version in all `pyproject.toml` files
2. Rebuild and upload
3. You **cannot** re-upload the same version

## Security Best Practices

❌ **NEVER**:
- Share API tokens in chat/email/code
- Commit tokens to git
- Use same token for test and production

✅ **ALWAYS**:
- Use separate tokens for TestPyPI and PyPI
- Enable 2FA on your PyPI account
- Revoke tokens if accidentally exposed
- Use scoped tokens (per-project) after first upload
- Store tokens in secure password manager

## Troubleshooting

**"Package already exists"**: You can't replace an existing version. Increment version number.

**"Invalid credentials"**: Check your `~/.pypirc` has correct token format (starts with `pypi-`)

**"403 Forbidden"**: Token may be expired or revoked. Generate new one.

**Missing dependencies**: Make sure to upload in order (dataload → core → network → providers → bundles)
