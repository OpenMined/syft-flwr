set dotenv-load := true

# ---------------------------------------------------------------------------------------------------------------------
# Private vars

[private]
_red := '\033[1;31m'
[private]
_cyan := '\033[1;36m'
[private]
_green := '\033[1;32m'
[private]
_yellow := '\033[1;33m'
[private]
_nc := '\033[0m'

# ---------------------------------------------------------------------------------------------------------------------
# Aliases

alias rj := run-jupyter

# ---------------------------------------------------------------------------------------------------------------------

@default:
    just --list

[group('utils')]
run-jupyter jupyter_args="":
    # uv sync

    uv run --frozen --with "jupyterlab" \
        jupyter lab {{ jupyter_args }} --ContentsManager.allow_hidden=True

# ---------------------------------------------------------------------------------------------------------------------

# Run tests for syft-flwr
[group('test')]
test:
    @echo "{{ _cyan }}Running syft-flwr tests...{{ _nc }}"
    bash scripts/test.sh

# ---------------------------------------------------------------------------------------------------------------------

# Bump version in pyproject.toml, __init__.py, and all notebook dependencies
# Usage: just bump-version patch/minor/major
[group('build')]
bump-version version_type="patch":
    #!/bin/bash
    set -eou pipefail

    # Check if version_type is valid
    if [[ "{{ version_type }}" != "patch" && "{{ version_type }}" != "minor" && "{{ version_type }}" != "major" ]]; then
        echo "{{ _red }}Error: Invalid version type '{{ version_type }}'. Use: patch, minor, or major{{ _nc }}"
        exit 1
    fi

    # Get current version from pyproject.toml
    CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

    # Parse version components
    IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

    # Bump version based on type
    if [[ "{{ version_type }}" == "major" ]]; then
        NEW_MAJOR=$((MAJOR + 1))
        NEW_VERSION="${NEW_MAJOR}.0.0"
    elif [[ "{{ version_type }}" == "minor" ]]; then
        NEW_MINOR=$((MINOR + 1))
        NEW_VERSION="${MAJOR}.${NEW_MINOR}.0"
    else  # patch
        NEW_PATCH=$((PATCH + 1))
        NEW_VERSION="${MAJOR}.${MINOR}.${NEW_PATCH}"
    fi

    # Update version in pyproject.toml
    sed -i.bak "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml && rm pyproject.toml.bak

    # Update version in __init__.py
    sed -i.bak "s/^__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" src/syft_flwr/__init__.py && rm src/syft_flwr/__init__.py.bak

    # Update syft-flwr dependency in all notebook pyproject.toml files
    echo -e "{{ _cyan }}Updating notebook dependencies...{{ _nc }}"
    for notebook_config in notebooks/*/pyproject.toml; do
        if [ -f "$notebook_config" ]; then
            notebook_name=$(basename $(dirname "$notebook_config"))
            # Update syft-flwr dependency to use the new version
            sed -i.bak "s/\"syft-flwr>=[0-9]\+\.[0-9]\+\.[0-9]\+\"/\"syft-flwr>=$NEW_VERSION\"/" "$notebook_config" && rm "${notebook_config}.bak"
            echo "  • Updated $notebook_name"
        fi
    done

    echo ""
    echo -e "{{ _green }}✓ Version bumped: $CURRENT_VERSION → $NEW_VERSION{{ _nc }}"
    echo ""
    echo -e "{{ _cyan }}Updated files:{{ _nc }}"
    echo "  • pyproject.toml"
    echo "  • src/syft_flwr/__init__.py"

    # List updated notebooks
    for notebook_config in notebooks/*/pyproject.toml; do
        if [ -f "$notebook_config" ]; then
            notebook_name=$(basename $(dirname "$notebook_config"))
            echo "  • notebooks/$notebook_name/pyproject.toml"
        fi
    done

    echo ""
    echo -e "{{ _cyan }}Next steps:{{ _nc }}"
    echo "  1. just test"
    echo "  2. git add -A"
    echo "  3. git commit -m \"Bump version to $NEW_VERSION\""
    echo "  4. git tag v$NEW_VERSION"
    echo "  5. git push && git push --tags"
    echo "  6. just build"

# Build syft-flwr wheel to upload to pypi
[group('build')]
build:
    @echo "{{ _cyan }}Building syft-flwr wheel...{{ _nc }}"
    rm -rf dist/
    uv build
    @echo "{{ _green }}Build complete!{{ _nc }}"
    @echo "{{ _cyan }}Before uploading to pypi, please inspect the build:{{ _nc }}"
    @echo "{{ _cyan }}1. Go to the build directory and unzip the .tar.gz file to inspect the contents{{ _nc }}"
    @echo "{{ _cyan }}2. Inspect the .whl file with: uvx wheel unpack <path_to_whl_file>{{ _nc }}"
    @echo "{{ _cyan }}3. Install the wheel with: uv pip install <path_to_whl_file> and do some tests if possible, e.g. import syft_flwr and check the version{{ _nc }}"
    @echo "{{ _cyan }}To upload to pypi, run: uvx twine upload ./dist/*{{ _nc }}"
