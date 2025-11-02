# Publishing to PyPI

This guide explains how to publish the `nlweb-core` package to PyPI.

## Prerequisites

1. **Create PyPI accounts:**
   - Test PyPI: https://test.pypi.org/account/register/
   - Production PyPI: https://pypi.org/account/register/

2. **Install build tools:**
   ```bash
   pip install build twine
   ```

3. **Configure API tokens:**
   - Go to https://pypi.org/manage/account/token/
   - Create a new API token with scope for this project
   - Save it securely (you'll need it for publishing)

## Publishing Process

### 1. Update Version Number

Update the version in both files:
- `setup.py` (line 10): `version="0.1.0"`
- `pyproject.toml` (line 7): `version = "0.1.0"`

Follow [Semantic Versioning](https://semver.org/):
- `0.1.0` → `0.1.1` (patch: bug fixes)
- `0.1.0` → `0.2.0` (minor: new features, backward compatible)
- `0.1.0` → `1.0.0` (major: breaking changes)

### 2. Clean Previous Builds

```bash
rm -rf dist/ build/ *.egg-info
```

### 3. Build the Package

```bash
python -m build
```

This creates:
- `dist/nlweb_core-0.1.0.tar.gz` (source distribution)
- `dist/nlweb_core-0.1.0-py3-none-any.whl` (wheel distribution)

### 4. Test on Test PyPI (Recommended)

```bash
# Upload to Test PyPI
python -m twine upload --repository testpypi dist/*

# Test installation from Test PyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ nlweb-core
```

Note: The `--extra-index-url` is needed because Test PyPI doesn't have all dependencies.

### 5. Publish to Production PyPI

```bash
python -m twine upload dist/*
```

You'll be prompted for:
- Username: `__token__`
- Password: Your API token (starts with `pypi-`)

### 6. Verify Installation

```bash
pip install nlweb-core
```

## Using GitHub Actions (Automated)

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine

    - name: Build package
      run: python -m build

    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: python -m twine upload dist/*
```

Then add your PyPI API token to GitHub Secrets:
1. Go to repository Settings → Secrets and variables → Actions
2. Add new repository secret:
   - Name: `PYPI_API_TOKEN`
   - Value: Your PyPI API token

Now, whenever you create a GitHub release, it will automatically publish to PyPI!

## Installation Options After Publishing

Once published, users can install with:

```bash
# Basic installation
pip install nlweb-core

# With optional dependencies
pip install nlweb-core[anthropic]
pip install nlweb-core[qdrant]
pip install nlweb-core[all]  # All optional dependencies

# Specific version
pip install nlweb-core==0.1.0

# Latest pre-release
pip install --pre nlweb-core
```

## Checklist Before Publishing

- [ ] Update version number in `setup.py` and `pyproject.toml`
- [ ] Update `CHANGELOG.md` (if exists)
- [ ] Test installation locally: `pip install -e .`
- [ ] Run tests: `pytest`
- [ ] Clean build directories: `rm -rf dist/ build/ *.egg-info`
- [ ] Build package: `python -m build`
- [ ] Test on Test PyPI first
- [ ] Create git tag: `git tag v0.1.0 && git push --tags`
- [ ] Upload to PyPI: `twine upload dist/*`
- [ ] Verify on PyPI: https://pypi.org/project/nlweb-core/
- [ ] Test installation: `pip install nlweb-core`

## Troubleshooting

**Error: "File already exists"**
- You're trying to upload a version that already exists
- Increment the version number and rebuild

**Error: "Invalid credentials"**
- Check your API token is correct
- Username should be `__token__` (not your PyPI username)

**Error: "Package name already taken"**
- Choose a different package name
- Update `name` in both `setup.py` and `pyproject.toml`

**Missing dependencies during install**
- Users need to install extras: `pip install nlweb-core[all]`
- Or add dependencies to the main `install_requires` list

## Resources

- PyPI: https://pypi.org/
- Test PyPI: https://test.pypi.org/
- Python Packaging Guide: https://packaging.python.org/
- Twine Documentation: https://twine.readthedocs.io/
