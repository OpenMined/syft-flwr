"""Test run_simulation functionality with test assets."""

import shutil
import tempfile
from pathlib import Path

# Set matplotlib to non-interactive backend to prevent popup figures
import matplotlib
import pytest
from loguru import logger

from syft_flwr.bootstrap import MAIN_TEMPLATE_PATH, bootstrap
from syft_flwr.run_simulation import (
    run,
    validate_bootstraped_project,
)

matplotlib.use("Agg")  # Use non-interactive backend


# Test asset paths (assets are in tests/assets/)
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
CODE_DIR = ASSETS_DIR / "code" / "fed-analytics-diabetes"
DATA_DIR = ASSETS_DIR / "data"
PARTITIONED_DATA_DIRS = [
    DATA_DIR / "pima-indians-diabetes-database-0",
    DATA_DIR / "pima-indians-diabetes-database-1",
]

# Test configurations
DS_EMAIL = "ds@openmined.org"
DO1_EMAIL = "do1@openmined.org"
DO2_EMAIL = "do2@openmined.org"

# Test cases for different configurations
test_configurations = [
    {
        "id": "encryption_enabled",
        "env_vars": {"SYFT_FLWR_ENCRYPTION_ENABLED": "True"},
        "expected_encryption": True,
    },
    {
        "id": "encryption_disabled",
        "env_vars": {"SYFT_FLWR_ENCRYPTION_ENABLED": "False"},
        "expected_encryption": False,
    },
]


def test_assets_directories_exist():
    """Test that all required test asset directories exist."""
    # Test that main assets directory exists
    assert ASSETS_DIR.exists(), f"Assets directory does not exist: {ASSETS_DIR}"
    assert ASSETS_DIR.is_dir(), f"Assets path is not a directory: {ASSETS_DIR}"

    # Test that code directory exists
    assert CODE_DIR.exists(), f"Code directory does not exist: {CODE_DIR}"
    assert CODE_DIR.is_dir(), f"Code path is not a directory: {CODE_DIR}"

    # Test code directory structure
    assert (
        CODE_DIR / "pyproject.toml"
    ).exists(), f"pyproject.toml not found in {CODE_DIR}"
    assert (
        CODE_DIR / "fed_analytics_diabetes"
    ).exists(), f"fed_analytics_diabetes package not found in {CODE_DIR}"
    assert (
        CODE_DIR / "fed_analytics_diabetes" / "__init__.py"
    ).exists(), "__init__.py not found in package"
    assert (
        CODE_DIR / "fed_analytics_diabetes" / "client_app.py"
    ).exists(), "client_app.py not found in package"
    assert (
        CODE_DIR / "fed_analytics_diabetes" / "server_app.py"
    ).exists(), "server_app.py not found in package"

    # Test data directory structure
    data_dir = ASSETS_DIR / "data"
    assert data_dir.exists(), f"Data directory does not exist: {data_dir}"
    assert data_dir.is_dir(), f"Data path is not a directory: {data_dir}"

    # Test that mock data directories exist
    for data_dir in PARTITIONED_DATA_DIRS:
        assert (
            data_dir / "mock"
        ).exists(), f"Mock data directory does not exist: {data_dir}"
        assert (
            data_dir / "private"
        ).exists(), f"Private data directory does not exist: {data_dir}"
        assert (
            data_dir / "mock" / "train.csv"
        ).exists(), f"train.csv not found in {data_dir}"
        assert (
            data_dir / "mock" / "test.csv"
        ).exists(), f"test.csv not found in {data_dir}"
        assert (
            data_dir / "private" / "train.csv"
        ).exists(), f"train.csv not found in {data_dir}"
        assert (
            data_dir / "private" / "test.csv"
        ).exists(), f"test.csv not found in {data_dir}"


@pytest.fixture
def project_workspace():
    """Create a temporary workspace with the test project."""
    temp_dir = tempfile.mkdtemp()
    # Add unique suffix to avoid parallel test conflicts
    import uuid

    unique_suffix = str(uuid.uuid4())[:8]
    project_dir = Path(temp_dir) / f"fed-analytics-diabetes-{unique_suffix}"

    logger.info(f"Created project workspace at {project_dir}")

    # Copy test project to workspace
    shutil.copytree(CODE_DIR, project_dir)

    # Clean up any existing artifacts
    main_py = project_dir / "main.py"
    if main_py.exists():
        main_py.unlink()

    for pycache_dir in project_dir.rglob("__pycache__"):
        shutil.rmtree(pycache_dir)

    yield project_dir

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_bootstrap_syft_flwr_project(project_workspace: Path) -> None:
    """Test bootstrapping creates correct project structure."""
    # Should fail before bootstrapping
    with pytest.raises(FileNotFoundError, match="main.py not found"):
        validate_bootstraped_project(project_workspace)

    # Bootstrap the project
    bootstrap(project_workspace, aggregator=DS_EMAIL, datasites=[DO1_EMAIL, DO2_EMAIL])

    # Should pass after bootstrapping
    validate_bootstraped_project(project_workspace)

    # Verify main.py was created
    assert (project_workspace / "main.py").exists()
    main_content = (project_workspace / "main.py").read_text()

    # Verify main.py matches the template exactly
    template_content = MAIN_TEMPLATE_PATH.read_text()
    assert main_content == template_content, "Generated main.py does not match template"

    # Verify pyproject.toml was updated
    pyproject_content = (project_workspace / "pyproject.toml").read_text()
    assert "[tool.syft_flwr]" in pyproject_content
    assert f'aggregator = "{DS_EMAIL}"' in pyproject_content
    assert f'"{DO1_EMAIL}"' in pyproject_content
    assert f'"{DO2_EMAIL}"' in pyproject_content
    assert "app_name" in pyproject_content


def test_run_simulation_encryption_enabled(
    project_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test run simulation with different encryption settings."""
    monkeypatch.setenv("SYFT_FLWR_ENCRYPTION_ENABLED", "True")
    monkeypatch.setenv("SYFT_FLWR_SKIP_MODULE_CHECK", "true")

    # Bootstrap the project
    bootstrap(project_workspace, aggregator=DS_EMAIL, datasites=[DO1_EMAIL, DO2_EMAIL])
    mock_dataset_paths = [p / "mock" for p in PARTITIONED_DATA_DIRS]

    # Run the simulation - will return bool in sync mode
    success = run(project_workspace, mock_dataset_paths)

    # Assert simulation completed successfully
    assert success is True
    assert (project_workspace / "figures").exists()
    assert (project_workspace / "simulation_logs").exists()


def test_run_simulation_encryption_disabled(
    project_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test run simulation with different encryption settings."""
    monkeypatch.setenv("SYFT_FLWR_ENCRYPTION_ENABLED", "False")
    monkeypatch.setenv("SYFT_FLWR_SKIP_MODULE_CHECK", "true")

    # Bootstrap the project
    bootstrap(project_workspace, aggregator=DS_EMAIL, datasites=[DO1_EMAIL, DO2_EMAIL])
    mock_dataset_paths = [p / "mock" for p in PARTITIONED_DATA_DIRS]

    # Run the simulation - will return bool in sync mode
    success = run(project_workspace, mock_dataset_paths)

    # Assert simulation completed successfully
    assert success is True
    assert (project_workspace / "figures").exists()
    assert (project_workspace / "simulation_logs").exists()


@pytest.mark.asyncio
async def test_run_simulation_async(
    project_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test run simulation works in async context."""
    monkeypatch.setenv("SYFT_FLWR_ENCRYPTION_ENABLED", "True")
    monkeypatch.setenv("SYFT_FLWR_SKIP_MODULE_CHECK", "true")

    # Bootstrap the project
    bootstrap(project_workspace, aggregator=DS_EMAIL, datasites=[DO1_EMAIL, DO2_EMAIL])
    mock_dataset_paths = [p / "mock" for p in PARTITIONED_DATA_DIRS]

    # Run the simulation in async context - returns Task, not bool
    task = run(project_workspace, mock_dataset_paths)

    # Wait for the task to complete and get the result
    success = await task

    # Assert simulation completed successfully
    assert success is True
    assert (project_workspace / "figures").exists()
    assert (project_workspace / "simulation_logs").exists()
