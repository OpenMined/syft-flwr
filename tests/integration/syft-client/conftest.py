"""
Shared fixtures for syft-client integration tests.

This module provides reusable fixtures for:
- Environment validation and credential management
- Google Drive cleanup
- SyftboxManager initialization (DO1, DO2, DS)
- Dataset preparation (HuggingFace download)

Prerequisites:
- Google OAuth credentials in syft-flwr/credentials/
- Environment variables (from credentials/.env)
"""

import os
import shutil
import tempfile
from pathlib import Path
from time import sleep

import pytest
from dotenv import load_dotenv
from huggingface_hub import snapshot_download
from loguru import logger
from syft_client.sync.syftbox_manager import SyftboxManager
from utils import (
    SCOPES,
    create_token,
    remove_syftbox_single_do_from_drive,
    remove_syftboxes_from_drive,
)

# ==============================================================================
# Constants
# ==============================================================================

# Paths
SYFT_FLWR_DIR = Path(__file__).parent.parent.parent.parent
CREDENTIALS_DIR = SYFT_FLWR_DIR / "credentials"
ENV_FILE = CREDENTIALS_DIR / ".env"
FL_PROJECT_DIR = (
    SYFT_FLWR_DIR / "notebooks" / "fl-diabetes-prediction" / "fl-diabetes-prediction"
)


# ==============================================================================
# Helper Functions
# ==============================================================================


def _load_env_file():
    """Load environment variables from .env file if it exists."""
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
        logger.info(f" Loaded environment variables from {ENV_FILE}")
    else:
        logger.info(
            f"No .env file found at {ENV_FILE}, using existing environment variables"
        )


def validate_user_credentials(
    user_id: str,
    email_env_var: str,
    cred_env_var: str,
    token_env_var: str,
    default_cred_file: str,
    default_token_file: str,
) -> dict:
    """Validate and setup credentials for a single user (DO or DS).

    Args:
        user_id: User identifier for logging (e.g., "DO1", "DO2", "DS")
        email_env_var: Environment variable name for email
        cred_env_var: Environment variable name for credentials file
        token_env_var: Environment variable name for token file
        default_cred_file: Default credentials filename
        default_token_file: Default token filename

    Returns:
        Dict with 'email', 'cred_path', 'token_path' for the user

    Raises:
        ValueError: If email or credentials are missing
    """
    errors = []

    # Get email from environment
    email = os.environ.get(email_env_var)
    if not email:
        errors.append(f"Missing environment variable: {email_env_var}")

    # Get credential and token file names
    cred_file = os.environ.get(cred_env_var, default_cred_file)
    token_file = os.environ.get(token_env_var, default_token_file)

    # Build paths
    cred_path = CREDENTIALS_DIR / cred_file
    token_path = CREDENTIALS_DIR / token_file

    # Check credentials exist
    if not cred_path.exists():
        errors.append(f"Missing {user_id} credentials: {cred_path}")

    if errors:
        raise ValueError(
            f"{user_id} validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    # Log user info
    logger.info(f"  - {user_id}: {email}")
    logger.info(f"    Credentials: {cred_path.name}")
    logger.info(f"    Token: {token_path.name}")

    # Auto-generate token if it doesn't exist
    if not token_path.exists():
        logger.info(f"Generating token for {user_id} from {cred_path.name}...")
        logger.info(f"Browser will open for {email} to authenticate")
        create_token(
            cred_path=cred_path,
            token_path=token_path,
            scopes=SCOPES,
        )
        logger.success(f" Token created: {token_path.name}")

    return {
        "email": email,
        "cred_path": cred_path,
        "token_path": token_path,
    }


def create_ds_do_pair(
    ds_email: str,
    ds_token_path: Path,
    do_email: str,
    do_token_path: Path,
    add_peers: bool = False,
) -> tuple[SyftboxManager, SyftboxManager]:
    """Create a DS + DO manager pair with Google Drive connection.

    Args:
        ds_email: Data Scientist email
        ds_token_path: Path to DS OAuth token
        do_email: Data Owner email
        do_token_path: Path to DO OAuth token
        add_peers: Whether to auto-add peers (default False, add manually for control)

    Returns:
        Tuple of (ds_manager, do_manager)
    """
    ds_manager, do_manager = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=do_email,
        ds_email=ds_email,
        do_token_path=do_token_path,
        ds_token_path=ds_token_path,
        use_in_memory_cache=False,
        add_peers=add_peers,
        load_peers=False,
        clear_caches=True,
    )
    logger.info(f"   Created DS ({ds_email}) + DO ({do_email}) pair")
    return ds_manager, do_manager


def add_peer_connection(ds_manager: SyftboxManager, do_manager: SyftboxManager):
    """Establish bidirectional peer connection between DS and DO.

    Args:
        ds_manager: Data Scientist SyftboxManager
        do_manager: Data Owner SyftboxManager
    """
    ds_email = ds_manager.email
    do_email = do_manager.email
    logger.info(f"Adding peer connection: {ds_email} <-> {do_email}")
    ds_manager.add_peer(do_email)
    do_manager.add_peer(ds_email)
    logger.info(f"   {ds_email} <-> {do_email} peer connection established")


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture(scope="module")
def validate_environment():
    """Verify all prerequisites are met before running tests."""
    logger.info("Phase 0: Validating environment...")

    _load_env_file()

    # Validate each user
    do1 = validate_user_credentials(
        user_id="DO1",
        email_env_var="DIABETES_EMAIL_DO1",
        cred_env_var="DIABETES_CRED_FNAME_DO1",
        token_env_var="DIABETES_TOKEN_FNAME_DO1",
        default_cred_file="do1.json",
        default_token_file="token_do1.json",
    )

    do2 = validate_user_credentials(
        user_id="DO2",
        email_env_var="DIABETES_EMAIL_DO2",
        cred_env_var="DIABETES_CRED_FNAME_DO2",
        token_env_var="DIABETES_TOKEN_FNAME_DO2",
        default_cred_file="do2.json",
        default_token_file="token_do2.json",
    )

    ds = validate_user_credentials(
        user_id="DS",
        email_env_var="DIABETES_EMAIL_DS",
        cred_env_var="DIABETES_CRED_FNAME_DS",
        token_env_var="DIABETES_TOKEN_FNAME_DS",
        default_cred_file="ds.json",
        default_token_file="token_ds.json",
    )

    logger.success(" All prerequisites validated")

    # Store in fixture for other tests to use
    return {
        "EMAIL_DO1": do1["email"],
        "EMAIL_DO2": do2["email"],
        "EMAIL_DS": ds["email"],
        "token_path_do1": do1["token_path"],
        "token_path_do2": do2["token_path"],
        "token_path_ds": ds["token_path"],
    }


@pytest.fixture(scope="module")
def cleanup_drive(validate_environment):
    """Clean up Google Drive before and after tests."""
    logger.info("Running cleanup fixture...")

    env = validate_environment

    # Cleanup before test
    remove_syftboxes_from_drive(
        env["EMAIL_DO1"],
        env["EMAIL_DO2"],
        env["EMAIL_DS"],
        env["token_path_do1"],
        env["token_path_do2"],
        env["token_path_ds"],
    )

    yield

    # Cleanup after test (optional - comment out for debugging)
    logger.info("Test completed. Keeping artifacts for inspection.")
    logger.info(f"  - DO1 workspace: {env['EMAIL_DO1']}")
    logger.info(f"  - DO2 workspace: {env['EMAIL_DO2']}")
    logger.info(f"  - DS workspace: {env['EMAIL_DS']}")


@pytest.fixture(scope="module")
def prepare_datasets():
    """Download diabetes dataset partitions from HuggingFace."""
    logger.info("Phase 1: Downloading datasets from HuggingFace...")

    dataset_dir = Path(tempfile.mkdtemp()) / "diabetes_dataset"

    try:
        snapshot_download(
            repo_id="khoaguin/pima-indians-diabetes-database-partitions",
            repo_type="dataset",
            local_dir=dataset_dir,
        )

        # Verify structure
        partition_0 = dataset_dir / "pima-indians-diabetes-database-0"
        partition_1 = dataset_dir / "pima-indians-diabetes-database-1"

        required_files = [
            partition_0 / "private" / "train.csv",
            partition_0 / "mock" / "train.csv",
            partition_1 / "private" / "train.csv",
            partition_1 / "mock" / "train.csv",
        ]

        missing = [f for f in required_files if not f.exists()]
        if missing:
            raise FileNotFoundError(f"Missing dataset files: {missing}")

        logger.success(f" Datasets downloaded to {dataset_dir}")

        yield dataset_dir

    finally:
        # Cleanup
        if dataset_dir.parent.exists():
            shutil.rmtree(dataset_dir.parent, ignore_errors=True)
            logger.info(" Dataset temp directory cleaned up")


@pytest.fixture(scope="module")
def syft_managers(cleanup_drive, validate_environment):
    """Initialize syft-client instances for DO1, DO2, DS."""
    logger.info("Phase 2: Initializing syft-client managers...")

    env = validate_environment

    # Create DS + DO1 pair (without auto-adding peers)
    ds_manager, do1_manager = create_ds_do_pair(
        ds_email=env["EMAIL_DS"],
        ds_token_path=env["token_path_ds"],
        do_email=env["EMAIL_DO1"],
        do_token_path=env["token_path_do1"],
    )

    # Create DS + DO2 pair (we only need the DO2 manager)
    _, do2_manager = create_ds_do_pair(
        ds_email=env["EMAIL_DS"],
        ds_token_path=env["token_path_ds"],
        do_email=env["EMAIL_DO2"],
        do_token_path=env["token_path_do2"],
    )

    # Add peers after all managers created
    add_peer_connection(ds_manager, do1_manager)
    add_peer_connection(ds_manager, do2_manager)

    # Wait for Google Drive operations to complete
    sleep(2)

    # Verify all managers initialized
    assert ds_manager is not None
    assert do1_manager is not None
    assert do2_manager is not None

    logger.success(" All 3 managers initialized")
    logger.info(f"  - DO1: {env['EMAIL_DO1']}")
    logger.info(f"  - DO2: {env['EMAIL_DO2']}")
    logger.info(f"  - DS: {env['EMAIL_DS']}")
    logger.info(f"  - DS peers (initial): {[p.email for p in ds_manager.peers]}")

    # Verify DS has both DOs as peers
    ds_peer_emails = [p.email for p in ds_manager.peers]
    assert (
        env["EMAIL_DO1"] in ds_peer_emails
    ), f"DO1 not in DS peers after sync: {ds_peer_emails}"
    assert (
        env["EMAIL_DO2"] in ds_peer_emails
    ), f"DO2 not in DS peers after sync: {ds_peer_emails}"

    logger.success(f" DS has {len(ds_manager.peers)} peers: {ds_peer_emails}")

    return {
        "ds": ds_manager,
        "do1": do1_manager,
        "do2": do2_manager,
        "env": env,  # Include env for test functions that need emails
    }


@pytest.fixture(scope="module")
def validate_environment_single_do():
    """Verify prerequisites for single-DO tests (DO1 + DS only)."""
    logger.info("Phase 0: Validating environment (single DO)...")

    _load_env_file()

    # Validate DO1 and DS only
    do1 = validate_user_credentials(
        user_id="DO1",
        email_env_var="DIABETES_EMAIL_DO1",
        cred_env_var="DIABETES_CRED_FNAME_DO1",
        token_env_var="DIABETES_TOKEN_FNAME_DO1",
        default_cred_file="do1.json",
        default_token_file="token_do1.json",
    )

    ds = validate_user_credentials(
        user_id="DS",
        email_env_var="DIABETES_EMAIL_DS",
        cred_env_var="DIABETES_CRED_FNAME_DS",
        token_env_var="DIABETES_TOKEN_FNAME_DS",
        default_cred_file="ds.json",
        default_token_file="token_ds.json",
    )

    logger.success(" All prerequisites validated (single DO)")

    return {
        "EMAIL_DO1": do1["email"],
        "EMAIL_DS": ds["email"],
        "token_path_do1": do1["token_path"],
        "token_path_ds": ds["token_path"],
    }


@pytest.fixture(scope="module")
def cleanup_drive_single_do(validate_environment_single_do):
    """Clean up Google Drive for single-DO tests (DO1 + DS only)."""
    logger.info("Running cleanup fixture (single DO)...")

    env = validate_environment_single_do

    # Cleanup before test
    remove_syftbox_single_do_from_drive(
        env["EMAIL_DO1"],
        env["EMAIL_DS"],
        env["token_path_do1"],
        env["token_path_ds"],
    )

    yield

    # Cleanup after test (optional - comment out for debugging)
    logger.info("Test completed. Keeping artifacts for inspection.")
    logger.info(f"  - DO1 workspace: {env['EMAIL_DO1']}")
    logger.info(f"  - DS workspace: {env['EMAIL_DS']}")


@pytest.fixture(scope="module")
def syft_managers_single_do(cleanup_drive_single_do, validate_environment_single_do):
    """Initialize syft-client instances for single DO (DO1) + DS only.

    This fixture is optimized for single-DO tests that don't need DO2.
    """
    logger.info("Phase 2: Initializing syft-client managers (single DO)...")

    env = validate_environment_single_do

    # Create DS + DO1 pair only
    ds_manager, do1_manager = create_ds_do_pair(
        ds_email=env["EMAIL_DS"],
        ds_token_path=env["token_path_ds"],
        do_email=env["EMAIL_DO1"],
        do_token_path=env["token_path_do1"],
    )

    # Add peer connection
    add_peer_connection(ds_manager, do1_manager)

    # Wait for Google Drive operations to complete
    sleep(2)

    # Verify managers initialized
    assert ds_manager is not None
    assert do1_manager is not None

    logger.success(" 2 managers initialized (single DO mode)")
    logger.info(f"  - DO1: {env['EMAIL_DO1']}")
    logger.info(f"  - DS: {env['EMAIL_DS']}")
    logger.info(f"  - DS peers: {[p.email for p in ds_manager.peers]}")

    # Verify DS has DO1 as peer
    ds_peer_emails = [p.email for p in ds_manager.peers]
    assert (
        env["EMAIL_DO1"] in ds_peer_emails
    ), f"DO1 not in DS peers after sync: {ds_peer_emails}"

    return {
        "ds": ds_manager,
        "do1": do1_manager,
        "env": env,
    }
