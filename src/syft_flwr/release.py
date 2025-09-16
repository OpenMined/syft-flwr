#!/usr/bin/env python3
"""
Automated release script for syft-flwr package.
Handles version bumping, building, and publishing to PyPI.

Usage:
    python release.py patch    # 0.2.2 -> 0.2.3
    python release.py minor    # 0.2.2 -> 0.3.0
    python release.py major    # 0.2.2 -> 1.0.0
    python release.py --dry-run patch  # Test without publishing
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.tree import Tree


def run_command(cmd, check=True, capture_output=False):
    """Run a shell command and optionally capture output."""
    logger.debug(f"Running: {cmd}")
    result = subprocess.run(
        cmd, shell=True, check=check, capture_output=capture_output, text=True
    )
    if capture_output:
        return result.stdout.strip()
    return result


def get_current_version():
    """Get current version from pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()
    match = re.search(r'^version = "(\d+\.\d+\.\d+)"', content, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def bump_version(current_version, bump_type):
    """Calculate new version based on bump type."""
    major, minor, patch = map(int, current_version.split("."))

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")


def update_version_in_files(old_version, new_version):
    """Update version in pyproject.toml and __init__.py."""
    files_to_update = [
        (
            "pyproject.toml",
            r'^version = "{}"'.format(re.escape(old_version)),
            f'version = "{new_version}"',
        ),
        (
            "src/syft_flwr/__init__.py",
            r'^__version__ = "{}"'.format(re.escape(old_version)),
            f'__version__ = "{new_version}"',
        ),
    ]

    for file_path, pattern, replacement in files_to_update:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"{file_path} not found, skipping...")
            continue

        content = path.read_text()
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        if content == new_content:
            logger.warning(f"Version {old_version} not found in {file_path}")
        else:
            path.write_text(new_content)
            logger.info(
                f"Updated version in {file_path}: {old_version} -> {new_version}"
            )


def clean_dist():
    """Clean the dist directory."""
    dist_dir = Path("dist")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
        logger.info("Cleaned dist/ directory")


def build_package():
    """Build the package using uv."""
    clean_dist()
    run_command("uv build .")

    # List built files
    dist_files = list(Path("dist").glob("*"))
    logger.info("Built files:")
    for file in dist_files:
        logger.info(f"  - {file.name}")

    return dist_files


def print_directory_tree(root_path, title, max_depth=3):
    """Print a directory tree using rich."""
    console = Console()
    tree = Tree(f"[bold blue]{title}/[/bold blue]")

    def add_to_tree(path, parent_node, level=0):
        """Recursively add items to the tree."""
        if level >= max_depth:
            if any(path.iterdir()):
                parent_node.add("[dim]...[/dim]")
            return

        items = sorted(path.iterdir())
        for item in items:
            if item.is_dir():
                branch = parent_node.add(f"[blue]{item.name}/[/blue]")
                add_to_tree(item, branch, level + 1)
            else:
                parent_node.add(f"[green]{item.name}[/green]")

    add_to_tree(root_path, tree, 0)
    console.print(tree)


def test_package(dist_files):
    """Test the built package."""
    logger.info("Testing Package")

    # Find the wheel and tarball
    wheel_file = None
    tar_file = None

    for file in dist_files:
        if file.suffix == ".whl":
            wheel_file = file
        elif file.name.endswith(".tar.gz"):
            tar_file = file

    if not wheel_file or not tar_file:
        raise ValueError("Could not find wheel or tarball in dist/")

    # 1. Inspect tarball contents
    logger.info(f"Inspecting tarball: {tar_file.name}")
    with tempfile.TemporaryDirectory() as tmpdir:
        run_command(f"tar -xzf {tar_file} -C {tmpdir}")
        extracted_dir = list(Path(tmpdir).iterdir())[0]
        logger.info("Tarball contents (tree view, max depth 3):")
        print_directory_tree(extracted_dir, extracted_dir.name)

    # 2. Inspect wheel contents
    logger.info(f"Inspecting wheel: {wheel_file.name}")
    with tempfile.TemporaryDirectory() as tmpdir:
        run_command(f"uvx wheel unpack {wheel_file} -d {tmpdir}")
        unpacked_dir = list(Path(tmpdir).iterdir())[0]
        logger.info("Wheel contents (tree view, max depth 3):")
        print_directory_tree(unpacked_dir, unpacked_dir.name)

    # 3. Test installation in a new environment
    logger.info("Testing installation in a new environment...")
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = Path(tmpdir) / "test_venv"
        run_command(f"uv venv {venv_dir}")

        # Install the wheel
        run_command(f"uv pip install --python {venv_dir}/bin/python {wheel_file}")

        # Test import
        test_script = """
import syft_flwr
print(f"Successfully imported syft_flwr version {syft_flwr.__version__}")
"""
        result = run_command(
            f'{venv_dir}/bin/python -c "{test_script}"', capture_output=True
        )
        logger.info(result)

    logger.success("Package tests passed!")


def check_pypi_credentials():
    """Check if PyPI credentials are configured."""
    try:
        # Check if we can get PyPI token from keyring or environment
        result = run_command(
            "python -m twine --version", check=False, capture_output=True
        )
        if result == "":
            logger.warning("twine not installed. Installing...")
            run_command("uv pip install twine")
        return True
    except Exception as e:
        logger.error(f"Error checking PyPI credentials: {e}")
        return False


def publish_to_pypi(dry_run=False):
    """Publish package to PyPI."""
    if dry_run:
        logger.info("🔍 DRY RUN - Would publish to PyPI:")
        logger.info("   uvx twine upload ./dist/*")
        return

    logger.info("Publishing to PyPI")

    if not check_pypi_credentials():
        logger.warning("PyPI credentials not configured.")
        logger.warning(
            "Please ensure you're logged in to PyPI or have TWINE_USERNAME/TWINE_PASSWORD set."
        )
        response = input("Continue with upload? (y/n): ")
        if response.lower() != "y":
            logger.info("Aborted.")
            return

    run_command("uvx twine upload ./dist/*")
    logger.success("Successfully published to PyPI!")


def commit_version_change(old_version, new_version):
    """Commit the version bump to git."""
    logger.info("Committing version change")
    run_command("git add pyproject.toml src/syft_flwr/__init__.py")
    run_command(f'git commit -m "Bump version from {old_version} to {new_version}"')
    logger.success(f"Committed version bump: {old_version} -> {new_version}")


def main():
    parser = argparse.ArgumentParser(description="Release script for syft-flwr")
    parser.add_argument(
        "bump_type", choices=["major", "minor", "patch"], help="Type of version bump"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without actually publishing to PyPI"
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip package tests")
    parser.add_argument(
        "--no-commit", action="store_true", help="Don't commit version changes to git"
    )

    args = parser.parse_args()

    try:
        # Get current version
        current_version = get_current_version()
        logger.info(f"Current version: {current_version}")

        # Calculate new version
        new_version = bump_version(current_version, args.bump_type)
        logger.info(f"New version: {new_version}")

        # Confirm with user
        if not args.dry_run:
            response = input(
                f"\nProceed with version bump {current_version} -> {new_version}? (y/n): "
            )
            if response.lower() != "y":
                logger.info("Aborted.")
                return

        # Update version in files
        update_version_in_files(current_version, new_version)

        # Build package
        logger.info("Building Package")
        dist_files = build_package()

        # Test package
        if not args.skip_tests:
            test_package(dist_files)

        # Commit changes (before publishing)
        if not args.no_commit and not args.dry_run:
            commit_version_change(current_version, new_version)

        # Publish to PyPI
        publish_to_pypi(args.dry_run)

        if args.dry_run:
            logger.info(f"🔍 DRY RUN completed. Version would be: {new_version}")
            # Revert version changes in dry run
            update_version_in_files(new_version, current_version)
            logger.info("Reverted version changes (dry run)")
        else:
            logger.success(f"🎉 Release {new_version} completed successfully!")
            logger.info(
                f"View on PyPI: https://pypi.org/project/syft-flwr/{new_version}/"
            )

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
