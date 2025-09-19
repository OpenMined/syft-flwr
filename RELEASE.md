# Release Process

This document describes how to release new versions of syft-flwr.

## Overview

The release process is fully automated using GitHub Actions. It handles version bumping, dependency updates, testing, building, and publishing to PyPI in a single workflow.

## Quick Release

1. **Go to Actions tab** → **Release** workflow
2. **Click "Run workflow"**
3. **Select options:**
   - **bump_type**: `patch`, `minor`, or `major`
   - **skip_publish**: `false` (uncheck for production release)
4. **Click "Run workflow"**

The workflow will automatically:
- Bump the version and create a git tag
- Update all lock files and dependencies
- Run tests to ensure everything works
- Build and validate the package
- Push changes to main
- Publish to PyPI
- Create a GitHub release
- Update notebook lock files with the published version

## Testing a Release

To test the release process without making any permanent changes:

1. Set **skip_publish** to `true` (check the box)
2. The workflow will:
   - ✅ Test version bumping and dependency updates
   - ✅ Build and validate the package
   - ❌ Skip git commits/pushes (no permanent changes)
   - ❌ Skip PyPI upload
   - ❌ Skip GitHub release creation
   - ❌ Skip notebook lock file updates
3. Review the workflow logs to ensure everything works correctly
4. **No cleanup needed** - no permanent changes are made

## What the Workflow Does

### Step-by-step process:

1. **Setup Environment**
   - Checkout main branch
   - Install Python, uv, just, and dependencies

2. **Version Bump**
   - Uses `just bump <type>` which internally:
     - Runs `cz bump` to update version and create commit/tag
     - Updates main project's `uv.lock`
     - Updates notebook `pyproject.toml` files (but not their locks yet)
     - Amends everything into a single atomic commit

3. **Testing & Building**
   - Runs full test suite (`just test`)
   - Builds package (`just build`)
   - Tests the built package can be imported and has correct version

4. **Publishing**
   - Pushes commit and tags to main
   - Uploads to PyPI (unless `skip_publish=true`)
   - Creates GitHub release with auto-generated changelog

5. **Post-publish Updates**
   - Waits 30 seconds for PyPI to index
   - Updates notebook lock files with the published version
   - Commits and pushes the lock file updates

## Manual Release Steps (if needed)

If you need to release manually:

```bash
# 1. Bump version
just bump patch  # or minor/major

# 2. Run tests
just test

# 3. Build package
just build

# 4. Push to GitHub
git push origin main --tags

# 5. Upload to PyPI
uvx twine upload dist/* --username __token__ --password <token>

# 6. Update notebook locks (after PyPI publication)
just update-notebook-locks
git add notebooks/*/uv.lock
git commit -m "chore: update notebook locks"
git push origin main
```

## Troubleshooting

### Common Issues:

**Notebook lock updates fail:**
- The new version might not be available on PyPI yet
- Wait a few minutes and run `just update-notebook-locks` manually

**Tests fail:**
- Fix the failing tests before attempting release
- The workflow will abort if tests fail

**PyPI upload fails:**
- Ensure `OM_PYPI_TOKEN` secret is set in repository settings
- Check if the version already exists on PyPI

**Version conflicts:**
- If the version already exists, you'll need to bump to a higher version
- Never reuse version numbers

## Version Strategy

- **Patch** (0.3.1 → 0.3.2): Bug fixes, small improvements
- **Minor** (0.3.1 → 0.4.0): New features, backward compatible
- **Major** (0.3.1 → 1.0.0): Breaking changes

## Development Workflow

1. **Feature development** happens in feature branches
2. **Merge to main** when ready
3. **Run release workflow** to publish new version
4. **Notebook updates** are handled automatically

This ensures main branch is always releasable and dependencies stay in sync.