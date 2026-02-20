# Release Process

This project uses GitHub Actions to automate publishing to PyPI and creating GitHub Releases.

## Prerequisites
1.  **PyPI API Token**: Ensure `PYPI_API_TOKEN` is set in the GitHub Repository Secrets.
2.  **Clean State**: Ensure all tests, linting, and type checks pass.

## Step-by-Step Release

### 1. Update the Version
Modify the `version` field in `pyproject.toml`.

```toml
[project]
name = "pystackquery"
version = "0.1.0"  # Update this!
```

### 2. Commit the change
```bash
git add pyproject.toml
git commit -m "chore: bump version to 0.1.0"
git push origin main
```

### 3. Tag and Push
Creating a tag that matches the pattern `v*.*.*` will trigger the `Publish` workflow.

```bash
# Create the tag locally
git tag v0.1.0

# Push the tag to GitHub
git push origin v0.1.0
```

## What Happens Automatically?
Once the tag is pushed:
1.  **Test Job**: GitHub Actions runs the full test suite.
2.  **Publish Job**: If tests pass, it builds the package and uploads it to PyPI.
3.  **Release Job**: A GitHub Release is created automatically with:
    *   Automatic release notes (based on commit messages).
    *   Built wheel and source distribution files attached.
