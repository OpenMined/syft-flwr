"""Shared test fixtures for syft_flwr tests."""

import shutil
import tempfile
from pathlib import Path

import pytest
from syft_core import Client
from syft_rds import init_session
from typing_extensions import Generator

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


@pytest.fixture
def ds_client(temp_workspace):
    """Get just the DS client for simple tests."""
    syftbox_client: Client = create_temp_client(DS_EMAIL, temp_workspace)
    rds_client = init_session(
        host=DS_EMAIL,
        email=DS_EMAIL,
        syftbox_client=syftbox_client,
        start_syft_event_server=True,
    )
    yield syftbox_client
    rds_client.stop_server()


@pytest.fixture
def do1_client(temp_workspace):
    """Get just the DO1 client for simple tests."""
    syftbox_client: Client = create_temp_client(DO1_EMAIL, temp_workspace)
    rds_client = init_session(
        host=DO1_EMAIL,
        email=DO1_EMAIL,
        syftbox_client=syftbox_client,
        start_syft_event_server=True,
    )
    yield syftbox_client
    rds_client.stop_server()
