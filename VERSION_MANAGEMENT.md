# Version Management

## Single Source of Truth

All NLWeb packages now use a centralized version system. The version is stored in one place and automatically read by all packages.

## How to Update the Version

**Simply edit the `VERSION` file in the repository root:**

```bash
echo "0.5.5" > VERSION
```

That's it! All packages will automatically pick up the new version when built.

## Files Affected

The following files read from `VERSION`:

- **Root `VERSION` file**: Contains the version number (e.g., `0.5.4.post1`)
- **`version.py`**: Python module that reads VERSION and exports `__version__`
- **All `pyproject.toml` files**: Use `dynamic = ["version"]` with `tool.setuptools.dynamic` pointing to VERSION
- **Package `__init__.py` files**: Import version dynamically from VERSION

## Package Locations

All packages read from the root `VERSION` file using relative paths:

```toml
[tool.setuptools.dynamic]
version = {file = "../../VERSION"}  # for packages/*/
version = {file = "../../../VERSION"}  # for packages/bundles/*/
version = {file = "../../../../VERSION"}  # for packages/providers/*/*/
```

## Dependency Version Constraints

Package dependencies on `nlweb-core` are set to the minor version level to ensure protocol compatibility:

```toml
dependencies = [
    "nlweb-core>=0.5.4",  # Requires 0.5.4 or newer
]
```

**Version Strategy:**

- **Patch versions** (0.5.4 → 0.5.5): Bug fixes, no breaking changes
  - Dependencies: `>=0.5.4` accepts these automatically ✅
  - Only update `VERSION` file

- **Minor versions** (0.5.x → 0.6.0): New features, may have breaking changes
  - Dependencies: Update all `>=0.5.4` to `>=0.6.0` in pyproject.toml files
  - Update `VERSION` file

- **Major versions** (0.x → 1.0): Significant breaking changes
  - Dependencies: Update all `>=0.5.4` to `>=1.0` in pyproject.toml files
  - Update `VERSION` file

**When dependencies need updates:**

Since the protocol changed significantly between 5.2 and 5.3, dependencies specify the minimum compatible version. When you increment the minor version (e.g., 0.5.x → 0.6.0), you'll need to:

1. Update `VERSION` file: `echo "0.6.0" > VERSION`
2. Update dependency constraints in all pyproject.toml files: `>=0.5.4` → `>=0.6.0`

**Files with dependency constraints:**

- `packages/network/pyproject.toml`
- `packages/bundles/models/pyproject.toml`
- `packages/bundles/retrieval/pyproject.toml`
- `packages/providers/azure/models/pyproject.toml`
- `packages/providers/azure/vectordb/pyproject.toml`

## Benefits

- **Single update**: Change version in one place
- **Consistency**: All packages always have the same version
- **No duplication**: No need to update 8+ pyproject.toml files
- **Less error-prone**: Impossible to have version mismatches

## Example Workflow

To release version 0.5.5:

```bash
# 1. Update VERSION file
echo "0.5.5" > VERSION

# 2. Build all packages (they will use 0.5.5)
./scripts/build_all.sh

# 3. Commit
git add VERSION
git commit -m "Bump version to 0.5.5"
```

## Checking Current Version

```bash
# From command line
cat VERSION

# From Python
python -c "import version; print(version.__version__)"

# From any package
python -c "import nlweb_dataload; print(nlweb_dataload.__version__)"
```
