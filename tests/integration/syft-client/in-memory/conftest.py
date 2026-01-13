"""
Shared fixtures for in-memory syft-client integration tests.

These tests use SyftboxManager.pair_with_in_memory_connection() to test
syft-flwr integration with syft-client without requiring Google Drive.

Benefits:
- Fast execution (no network I/O)
- No OAuth credentials needed
- Can run in CI
- Deterministic (no Google Drive sync delays)
"""

import pytest
from loguru import logger
from syft_client.sync.syftbox_manager import SyftboxManager

# Test emails (no real accounts needed for in-memory tests)
DS_EMAIL = "ds@test.openmined.org"
DO1_EMAIL = "do1@test.openmined.org"
DO2_EMAIL = "do2@test.openmined.org"


@pytest.fixture
def in_memory_managers_single_do():
    """Create DS and DO1 managers with in-memory connection.

    Returns:
        tuple: (ds_manager, do1_manager) with established peer connection
    """
    logger.info("Creating in-memory managers (single DO)...")

    ds_manager, do1_manager = SyftboxManager.pair_with_in_memory_connection(
        email1=DO1_EMAIL,  # email1 → DO (Data Owner)
        email2=DS_EMAIL,  # email2 → DS (Data Scientist)
        add_peers=True,  # Auto-establish peer relationship
        use_in_memory_cache=True,
    )

    logger.info(f"  DS: {ds_manager.email}")
    logger.info(f"  DO1: {do1_manager.email}")

    yield ds_manager, do1_manager

    logger.info("Cleaning up in-memory managers...")


@pytest.fixture
def in_memory_managers_two_dos():
    """Create DS, DO1, and DO2 managers with in-memory connections.

    Note: pair_with_in_memory_connection() only creates pairs, so we create
    two pairs that share backing stores appropriately.

    Returns:
        tuple: (ds_manager, do1_manager, do2_manager)
    """
    logger.info("Creating in-memory managers (two DOs)...")

    # Create DS <-> DO1 pair
    ds_manager, do1_manager = SyftboxManager.pair_with_in_memory_connection(
        email1=DO1_EMAIL,
        email2=DS_EMAIL,
        add_peers=True,
        use_in_memory_cache=True,
    )

    # Create separate DO2 manager and connect to DS
    # For two DOs, we need a slightly different approach
    _, do2_manager = SyftboxManager.pair_with_in_memory_connection(
        email1=DO2_EMAIL,
        email2=DS_EMAIL,
        add_peers=True,
        use_in_memory_cache=True,
    )

    logger.info(f"  DS: {ds_manager.email}")
    logger.info(f"  DO1: {do1_manager.email}")
    logger.info(f"  DO2: {do2_manager.email}")

    yield ds_manager, do1_manager, do2_manager

    logger.info("Cleaning up in-memory managers...")


@pytest.fixture
def in_memory_managers_no_peers():
    """Create DS and DO1 managers WITHOUT auto-established peers.

    Useful for testing the peer request/approval flow explicitly.

    Returns:
        tuple: (ds_manager, do1_manager) without peer connection
    """
    logger.info("Creating in-memory managers (no peers)...")

    ds_manager, do1_manager = SyftboxManager.pair_with_in_memory_connection(
        email1=DO1_EMAIL,
        email2=DS_EMAIL,
        add_peers=False,  # Don't auto-add peers
        use_in_memory_cache=True,
    )

    logger.info(f"  DS: {ds_manager.email}")
    logger.info(f"  DO1: {do1_manager.email}")
    logger.info("  Peers: NOT established (for testing peer flow)")

    yield ds_manager, do1_manager

    logger.info("Cleaning up in-memory managers...")
