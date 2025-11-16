# Version Management

## How to Update the Version

All NLWeb packages use **explicit version numbers** in their pyproject.toml files. When bumping the version, you need to update multiple files.

## Files to Update for Version Changes

### 1. Package Version Numbers (all must match)

Update the `version = "X.Y.Z"` line in these pyproject.toml files:

- **Root**: `/pyproject.toml`
- **Core**: `/packages/core/pyproject.toml`
- **Dataload**: `/packages/dataload/pyproject.toml`
- **Network**: `/packages/network/pyproject.toml`
- **Models**: `/packages/bundles/models/pyproject.toml`
- **Retrieval**: `/packages/bundles/retrieval/pyproject.toml`
- **Azure Models**: `/packages/providers/azure/models/pyproject.toml`
- **Azure VectorDB**: `/packages/providers/azure/vectordb/pyproject.toml`

### 2. Python __version__ Variables

Update `__version__` in:

- `/packages/dataload/nlweb_dataload/__init__.py`

### 3. User-Agent Headers (if applicable)

Check and update version references in:

- `/packages/dataload/nlweb_dataload/rss2schema.py` (User-Agent header)

## Version Bump Workflow

### For Patch/Post Releases (e.g., 0.5.4.post1 → 0.5.4.post2)

**No breaking changes - bug fixes only**

```bash
# 1. Update all version numbers to new version (e.g., 0.5.4.post2)
#    Edit each file listed in section 1 above

# 2. Search and replace across the repo to catch any you missed:
grep -r "0.5.4.post1" --include="*.toml" --include="*.py"

# 3. Commit changes
git add .
git commit -m "Bump version to 0.5.4.post2"
```

**Note**: For patch releases, dependency constraints (e.g., `nlweb-core>=0.5.4`) do NOT need to be updated.

### For Minor Version Changes (e.g., 0.5.x → 0.6.0)

**May include breaking changes**

```bash
# 1. Update all version numbers to 0.6.0 (section 1 above)

# 2. Update dependency constraints in these files:
#    Change "nlweb-core>=0.5.4" to "nlweb-core>=0.6.0"
```

**Files with dependency constraints:**

- `/packages/network/pyproject.toml`
- `/packages/bundles/models/pyproject.toml`
- `/packages/bundles/retrieval/pyproject.toml`
- `/packages/providers/azure/models/pyproject.toml`
- `/packages/providers/azure/vectordb/pyproject.toml`

### For Major Version Changes (e.g., 0.x → 1.0.0)

**Significant breaking changes**

Follow the same process as minor version changes, but update dependency constraints to the new major version (e.g., `nlweb-core>=1.0`).

## Quick Reference: Current Version

**Current version: 0.5.4.post2**

## Checking Package Versions

```bash
# Check a specific package version
grep "^version = " pyproject.toml
grep "^version = " packages/core/pyproject.toml

# Check all versions at once
grep -r "^version = " --include="pyproject.toml" | grep -v ".venv"

# From Python
python -c "import nlweb_dataload; print(nlweb_dataload.__version__)"
```

## Important Notes

- All 8 packages should have the **same version number**
- Dependency constraints (`nlweb-core>=0.5.4`) only change for minor/major versions
- Always search the repo after updating to catch any missed references
- Test builds locally before pushing: `pip install -e packages/dataload`
