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

# Build syft-flwr wheel to upload to pypi
# Before build, please bump the version in pyproject.toml and src/syft_flwr/__init__.py
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

# ---------------------------------------------------------------------------------------------------------------------

# Release syft-flwr to PyPI with automated version bumping
# Usage: just release patch/minor/major [--dry-run] [--skip-tests] [--no-commit]
# patch    # 0.2.2 -> 0.2.3
# minor    # 0.2.2 -> 0.3.0
# major    # 0.2.2 -> 1.0.0
[group('release')]
release bump_type="patch" *args="":
    @echo "{{ _cyan }}Starting release process...{{ _nc }}"
    uv run python src/syft_flwr/release.py {{ bump_type }} {{ args }}

# Dry-run release to test without publishing
[group('release')]
release-dry bump_type="patch":
    @echo "{{ _yellow }}Running release in DRY-RUN mode...{{ _nc }}"
    uv run python src/syft_flwr/release.py {{ bump_type }} --dry-run
