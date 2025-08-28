"""Shared test fixtures for syft_flwr tests."""

import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from syft_core import Client
from syft_rds.orchestra import SingleRDSStack

from syft_flwr.utils import create_temp_client

DS_EMAIL = "ds@openmined.org"
DO1_EMAIL = "do1@openmined.org"
DO2_EMAIL = "do2@openmined.org"


@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Create isolated temporary workspace for each test"""
    temp_dir: str = tempfile.mkdtemp()
    workspace: Path = Path(temp_dir) / "SyftBox"
    workspace.mkdir(parents=True, exist_ok=True)

    dot_syftbox_dir: Path = workspace.parent / ".syftbox"
    dot_syftbox_dir.mkdir(parents=True, exist_ok=True)

    yield workspace

    shutil.rmtree(temp_dir, ignore_errors=True)


# Helper functions for creating RDS server stacks
def _setup_single_rds_server(email: str, temp_workspace: Path):
    client: Client = create_temp_client(email, temp_workspace)
    stack = SingleRDSStack(client)

    return stack


@pytest.fixture
def ds_client(temp_workspace):
    """Get just the DS client for simple tests."""
    return _setup_single_rds_server(DS_EMAIL, temp_workspace).client


@pytest.fixture
def do1_client(temp_workspace):
    """Get just the DO1 client for simple tests."""
    return _setup_single_rds_server(DO1_EMAIL, temp_workspace).client


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
def full_fl_network(temp_workspace) -> Generator[dict, None, None]:
    """
    Setup a complete FL network with 1 DS (aggregator) and 2 DOs.
    This fixture sets up the full RDS stack for each participant.
    """
    # Setup all three RDS server stacks using helper function
    ds_stack = _setup_single_rds_server(DS_EMAIL, temp_workspace)
    do1_stack = _setup_single_rds_server(DO1_EMAIL, temp_workspace)
    do2_stack = _setup_single_rds_server(DO2_EMAIL, temp_workspace)

    yield {
        "ds": _create_participant_info(DS_EMAIL, ds_stack),
        "do1": _create_participant_info(DO1_EMAIL, do1_stack),
        "do2": _create_participant_info(DO2_EMAIL, do2_stack),
        "root_dir": temp_workspace,
    }

    # Cleanup using helper function
    _cleanup_stacks(ds_stack, do1_stack, do2_stack)
