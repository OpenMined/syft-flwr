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
    uv run --frozen --with "jupyterlab" \
        jupyter lab {{ jupyter_args }} --ContentsManager.allow_hidden=True

# ---------------------------------------------------------------------------------------------------------------------

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

    # Update syft-flwr dependency in all notebook pyproject.toml files
    for notebook_config in notebooks/*/pyproject.toml; do
        if [ -f "$notebook_config" ]; then
            notebook_name=$(basename $(dirname "$notebook_config"))
            # Update syft-flwr dependency to use the current version
            sed -i.bak "s/\"syft-flwr>=[0-9]\+\.[0-9]\+\.[0-9]\+\"/\"syft-flwr>=$CURRENT_VERSION\"/" "$notebook_config" && rm "${notebook_config}.bak"
            echo "  • Updated $notebook_name"
        fi
    done

    echo -e "{{ _green }}✅ Notebook dependencies updated!{{ _nc }}"

# Revert a version bump (delete tag and revert version changes)
[group('build')]
revert version:
    #!/bin/bash
    set -eou pipefail

    if [ -z "{{ version }}" ]; then
        echo -e "{{ _red }}Error: Version required{{ _nc }}"
        echo "Usage: just revert <version>"
        echo "Example: just revert 0.2.3"
        exit 1
    fi

    TAG_NAME="v{{ version }}"

    echo -e "{{ _yellow }}⚠️  WARNING: This will revert syft-flwr version {{ version }}{{ _nc }}"
    echo -e "{{ _yellow }}This will:{{ _nc }}"
    echo -e "{{ _yellow }}  1. Delete git tag: v{{ version }}{{ _nc }}"
    echo -e "{{ _yellow }}  2. Revert version in pyproject.toml and __init__.py{{ _nc }}"
    echo ""
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "{{ _cyan }}Operation cancelled{{ _nc }}"
        exit 0
    fi

    echo -e "{{ _cyan }}Reverting syft-flwr version {{ version }}...{{ _nc }}"

    # Delete the git tag
    if git tag -l | grep -q "^v{{ version }}$"; then
        git tag -d "v{{ version }}"
        echo -e "{{ _green }}✅ Deleted git tag: v{{ version }}{{ _nc }}"
    else
        echo -e "{{ _yellow }}⚠️  Git tag v{{ version }} not found{{ _nc }}"
    fi

    echo -e "{{ _yellow }}⚠️  Manual steps required:{{ _nc }}"
    echo -e "{{ _yellow }}  1. Revert version in pyproject.toml{{ _nc }}"
    echo -e "{{ _yellow }}  2. Revert version in src/syft_flwr/__init__.py{{ _nc }}"
    echo -e "{{ _yellow }}  3. Revert notebook dependencies if needed{{ _nc }}"
    echo -e "{{ _yellow }}  4. Commit the changes{{ _nc }}"
    echo ""
    echo -e "{{ _cyan }}Use 'just show-version' to check current version{{ _nc }}"

# Build syft-flwr wheel to upload to pypi
[group('build')]
build:
    @echo "{{ _cyan }}Building syft-flwr wheel...{{ _nc }}"
    rm -rf dist/
    uv build
    @echo "{{ _green }}Build complete!{{ _nc }}"
    @echo "{{ _cyan }}Built packages:{{ _nc }}"
    @ls -la dist/