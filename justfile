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


# ---------------------------------------------------------------------------------------------------------------------

@default:
    just --list

# Run tests for syft-flwr
[group('test')]
test:
    @echo "{{ _cyan }}Running syft-flwr tests...{{ _nc }}"
    bash scripts/test.sh

# ---------------------------------------------------------------------------------------------------------------------

[group('utils')]
clean:
    #!/bin/sh
    echo "{{ _cyan }}Cleaning up local files and directories...{{ _nc }}"

    # Function to remove directories by name pattern
    remove_dirs() {
        dir_name=$1
        dirs=$(find . -type d -name "$dir_name" 2>/dev/null)
        if [ -n "$dirs" ]; then
            echo "$dirs" | while read -r dir; do
                echo "  {{ _red }}✗{{ _nc }} Removing $dir"
                rm -rf "$dir"
            done
        fi
    }

    # Remove root directories if they exist
    for dir in ./.clients ./dist ./.e2e ./.logs ./.pytest_cache; do
        if [ -d "$dir" ]; then
            echo "  {{ _red }}✗{{ _nc }} Removing $dir"
            rm -rf "$dir"
        fi
    done

    # Remove directories by name pattern
    remove_dirs ".server"
    remove_dirs ".clients"
    remove_dirs ".syftbox"
    remove_dirs "local_syftbox_network"

    # Remove __pycache__ directories
    pycache_count=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
    if [ "$pycache_count" -gt 0 ]; then
        echo "  {{ _red }}✗{{ _nc }} Removing $pycache_count __pycache__ directories"
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    fi

    echo "{{ _green }}✓ Clean complete!{{ _nc }}"

# ---------------------------------------------------------------------------------------------------------------------
# Version Management Commands

# Show current version
[group('build')]
show-version:
    @echo "{{ _cyan }}Current syft-flwr version:{{ _nc }}"
    @grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'

# Bump version using commitizen, update the main project's uv.lock file,
# update notebook dependencies, which updates their uv.lock files
# Usage: just bump patch/minor/major
[group('build')]
bump increment="patch":
    #!/bin/bash
    set -eou pipefail

    # Check if increment is valid
    if [[ "{{ increment }}" != "patch" && "{{ increment }}" != "minor" && "{{ increment }}" != "major" ]]; then
        echo -e "{{ _red }}Error: Invalid increment '{{ increment }}'. Use: patch, minor, or major{{ _nc }}"
        exit 1
    fi

    echo -e "{{ _cyan }}Bumping syft-flwr {{ increment }} version...{{ _nc }}"

    # Bump the version using commitizen
    uv run cz bump --increment "{{ increment }}" --yes

    if [ $? -eq 0 ]; then
        echo -e "{{ _green }}✅ Version bumped successfully!{{ _nc }}"

        # Get the new version
        NEW_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
        echo -e "{{ _green }}New version: $NEW_VERSION{{ _nc }}"

        # Update main project's uv.lock
        echo -e "{{ _cyan }}Updating main project uv.lock...{{ _nc }}"
        uv lock
        echo -e "{{ _green }}✅ Main project uv.lock updated!{{ _nc }}"

        # Add and amend the lock file update to the commit created by cz
        git add uv.lock
        git commit --amend --no-edit

        echo -e "{{ _green }}✅ Version bump and lock file updated in single commit!{{ _nc }}"
        echo -e "{{ _yellow }}Note: Notebook lock files will be updated after publishing to PyPI{{ _nc }}"
    else
        echo -e "{{ _red }}Error: Version bump failed{{ _nc }}"
        exit 1
    fi

# Dry run version bump
# Usage: just bump-dry patch/minor/major
[group('build')]
bump-dry increment="patch":
    @echo "{{ _cyan }}DRY RUN: Bumping syft-flwr {{ increment }} version...{{ _nc }}"
    @uv run cz bump --increment "{{ increment }}" --yes --dry-run

# Update notebook dependencies to current version
[group('build')]
update-notebook-deps:
    #!/bin/bash
    set -eou pipefail

    # Get current version from pyproject.toml
    CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

    echo -e "{{ _cyan }}Updating notebook dependencies to syft-flwr>=$CURRENT_VERSION...{{ _nc }}"

    # Update syft-flwr dependency in all notebook pyproject.toml files
    for notebook_dir in notebooks/*/; do
        if [ -d "$notebook_dir" ] && [ -f "$notebook_dir/pyproject.toml" ]; then
            notebook_name=$(basename "$notebook_dir")

            # Update syft-flwr dependency to use the current version (handle both = and >= formats)
            sed -i.bak -E "s/\"syft-flwr(>=|=)[0-9]+\.[0-9]+\.[0-9]+\"/\"syft-flwr>=$CURRENT_VERSION\"/" "$notebook_dir/pyproject.toml" && rm "${notebook_dir}pyproject.toml.bak"
            echo "  • Updated $notebook_name/pyproject.toml to syft-flwr>=$CURRENT_VERSION"

            # Note: We DON'T update uv.lock here because the new version doesn't exist on PyPI yet
            echo "  • Note: uv.lock will be updated after publishing to PyPI"
        fi
    done

    echo -e "{{ _green }}✅ Notebook pyproject.toml files updated!{{ _nc }}"
    echo -e "{{ _yellow }}Note: Notebook uv.lock files will be updated after publishing to PyPI{{ _nc }}"


# Update notebook lock files after publishing to PyPI
# This should be run after the new version is available on PyPI
[group('build')]
update-notebook-locks:
    #!/bin/bash
    set -eou pipefail

    echo -e "{{ _cyan }}Updating notebook uv.lock files with published syft-flwr version...{{ _nc }}"

    for notebook_dir in notebooks/*/; do
        if [ -d "$notebook_dir" ] && [ -f "$notebook_dir/pyproject.toml" ]; then
            notebook_name=$(basename "$notebook_dir")
            echo "  • Updating $notebook_name/uv.lock..."
            (cd "$notebook_dir" && uv lock --upgrade-package syft-flwr)
        fi
    done

    echo -e "{{ _green }}✅ Notebook lock files updated with published version!{{ _nc }}"

# Build syft-flwr wheel to upload to pypi
[group('build')]
build:
    @echo "{{ _cyan }}Building syft-flwr wheel...{{ _nc }}"
    rm -rf dist/
    uv build
    @echo "{{ _green }}Build complete!{{ _nc }}"
    @echo "{{ _cyan }}Built packages:{{ _nc }}"
    @ls -la dist/
