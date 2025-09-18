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
# Version Management Commands

# Show current version
[group('build')]
show-version:
    @echo "{{ _cyan }}Current syft-flwr version:{{ _nc }}"
    @grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'

# Bump version using commitizen and update notebook dependencies
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

        # Update notebook dependencies
        echo -e "{{ _cyan }}Updating notebook dependencies...{{ _nc }}"
        just update-notebook-deps

        # Add notebook changes and amend the commit
        git add notebooks/*/pyproject.toml
        git commit --amend --no-edit

        echo -e "{{ _green }}✅ Version and notebook dependencies updated!{{ _nc }}"
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

    # Update syft-flwr dependency in all notebook pyproject.toml files and update lock files
    for notebook_dir in notebooks/*/; do
        if [ -d "$notebook_dir" ] && [ -f "$notebook_dir/pyproject.toml" ]; then
            notebook_name=$(basename "$notebook_dir")

            # Update syft-flwr dependency to use the current version (handle both = and >= formats)
            sed -i.bak -E "s/\"syft-flwr(>=|=)[0-9]+\.[0-9]+\.[0-9]+\"/\"syft-flwr>=$CURRENT_VERSION\"/" "$notebook_dir/pyproject.toml" && rm "${notebook_dir}pyproject.toml.bak"
            echo "  • Updated $notebook_name/pyproject.toml"

            # Update the uv.lock file for this notebook
            echo "  • Updating $notebook_name/uv.lock..."
            (cd "$notebook_dir" && uv lock --upgrade-package syft-flwr)
        fi
    done

    echo -e "{{ _green }}✅ Notebook dependencies and lock files updated!{{ _nc }}"


# Build syft-flwr wheel to upload to pypi
[group('build')]
build:
    @echo "{{ _cyan }}Building syft-flwr wheel...{{ _nc }}"
    rm -rf dist/
    uv build
    @echo "{{ _green }}Build complete!{{ _nc }}"
    @echo "{{ _cyan }}Built packages:{{ _nc }}"
    @ls -la dist/