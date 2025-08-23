"""Shared test fixtures for syft_flwr tests."""

from pathlib import Path

import pytest
from syft_rds.orchestra import remove_rds_stack_dir, setup_rds_server

# Test emails for different roles
DS_EMAIL = "data_scientist@test.openmined.org"
DO1_EMAIL = "data_owner1@test.openmined.org"
DO2_EMAIL = "data_owner2@test.openmined.org"

# Shared data directory for testing
SHARED_DATA_DIR = "shared_data_dir"

# Test directories
TEST_DIR = Path(__file__).parent
ASSET_PATH = TEST_DIR / "assets"


# Helper functions for creating RDS server stacks
def _setup_single_rds_server(email: str, tmp_path: Path, key: str, reset: bool = False):
    """Helper function to setup a single RDS server."""
    return setup_rds_server(
        email=email,
        root_dir=tmp_path,
        key=key,
        reset=reset,
        log_level="INFO",
    )


def _create_participant_info(email: str, stack):
    """Helper to create participant info dict."""
    return {
        "email": email,
        "stack": stack,
        "client": stack.client,
    }


def _cleanup_stacks(*stacks):
    """Helper to cleanup multiple stacks."""
    for stack in stacks:
        if stack:
            stack.stop()


@pytest.fixture
def rds_stack_ds(tmp_path):
    """Setup DS (Data Scientist) RDS server stack."""
    stack = _setup_single_rds_server(DS_EMAIL, tmp_path, "ds_test", reset=True)
    yield stack
    stack.stop()


@pytest.fixture
def rds_stack_do1(tmp_path):
    """Setup DO1 (Data Owner 1) RDS server stack."""
    stack = _setup_single_rds_server(DO1_EMAIL, tmp_path, "do1_test", reset=True)
    yield stack
    stack.stop()


@pytest.fixture
def rds_stack_do2(tmp_path):
    """Setup DO2 (Data Owner 2) RDS server stack."""
    stack = _setup_single_rds_server(DO2_EMAIL, tmp_path, "do2_test", reset=True)
    yield stack
    stack.stop()


@pytest.fixture
def ds_client(rds_stack_ds):
    """Get just the DS client for simple tests."""
    return rds_stack_ds.client


@pytest.fixture
def full_fl_network(tmp_path):
    """
    Setup a complete FL network with 1 DS (aggregator) and 2 DOs.
    This fixture sets up the full RDS stack for each participant.
    """
    # Clean up any existing network first
    remove_rds_stack_dir(root_dir=tmp_path, key="fl_network")

    # Setup all three RDS server stacks using helper function
    ds_stack = _setup_single_rds_server(DS_EMAIL, tmp_path, "fl_network", reset=True)
    do1_stack = _setup_single_rds_server(DO1_EMAIL, tmp_path, "fl_network", reset=False)
    do2_stack = _setup_single_rds_server(DO2_EMAIL, tmp_path, "fl_network", reset=False)

    yield {
        "ds": _create_participant_info(DS_EMAIL, ds_stack),
        "do1": _create_participant_info(DO1_EMAIL, do1_stack),
        "do2": _create_participant_info(DO2_EMAIL, do2_stack),
        "root_dir": tmp_path,
    }

    # Cleanup using helper function
    _cleanup_stacks(ds_stack, do1_stack, do2_stack)


@pytest.fixture
def mock_flwr_context():
    """Create a mock Flower context for testing."""
    from unittest.mock import MagicMock

    context = MagicMock()
    context.node_id = 0
    context.node_config = {}
    context.state = MagicMock()
    return context


@pytest.fixture
def mock_flwr_server_app():
    """Create a mock Flower ServerApp for testing."""
    from unittest.mock import MagicMock

    server_app = MagicMock()
    server_app.config = {}
    return server_app


@pytest.fixture
def mock_flwr_client_app():
    """Create a mock Flower ClientApp for testing."""
    from unittest.mock import MagicMock

    client_app = MagicMock()
    client_app.config = {}
    return client_app
