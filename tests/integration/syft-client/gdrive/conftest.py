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
from syft_client.sync.syftbox_manager import SyftboxManager, SyftboxManagerConfig
from utils import (
    SCOPES,
    create_token,
    remove_syftbox_single_do_from_drive,
    remove_syftboxes_from_drive,
)

# ==============================================================================
# Pytest Hooks - Test Logging
# ==============================================================================


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Log a nicely formatted banner before each test runs."""
    test_name = item.name
    test_file = item.fspath.basename if item.fspath else "unknown"

    logger.info("")
    logger.info("=" * 70)
    logger.info(f"  RUNNING: {test_name}")
    logger.info(f"  FILE: {test_file}")
    logger.info("=" * 70)


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
TEST_LOGS_DIR = Path("/tmp/syft_flwr_test_logs")


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


def create_single_manager(
    email: str,
    token_path: Path,
    is_ds: bool = False,
) -> SyftboxManager:
    """Create a single SyftboxManager for testing.

    This function creates managers individually to avoid the cross-contamination
    issues that can occur when using pair_with_google_drive_testing_connection()
    multiple times (which creates duplicate DS managers).

    Args:
        email: User email
        token_path: Path to OAuth token
        is_ds: True for Data Scientist, False for Data Owner

    Returns:
        Configured SyftboxManager instance with appropriate callbacks
    """
    logger.debug(f"[DEBUG] Creating manager for {email} (is_ds={is_ds})")

    config = SyftboxManagerConfig.for_google_drive_testing_connection(
        email=email,
        token_path=token_path,
        use_in_memory_cache=False,
        only_ds=is_ds,
        only_datasite_owner=not is_ds,
    )
    logger.debug(
        f"[DEBUG] Config created for {email}, syftbox_folder={config.syftbox_folder}"
    )

    manager = SyftboxManager.from_config(config)
    logger.debug(
        f"[DEBUG] Manager created for {email}, syftbox_folder={manager.syftbox_folder}"
    )

    # DEBUG: Check what SyftBox folder ID the connection is using
    try:
        conn = manager.connection_router.connections[0]
        syftbox_id = conn.get_syftbox_folder_id()
        personal_id = conn.get_personal_syftbox_folder_id()
        logger.debug(f"[DEBUG] {email}: SyftBox folder ID = {syftbox_id}")
        logger.debug(f"[DEBUG] {email}: Personal folder ID = {personal_id}")

        # List what folders are in the SyftBox
        drive_service = conn.drive_service
        query = f"'{syftbox_id}' in parents and trashed=false"
        results = (
            drive_service.files()
            .list(q=query, fields="files(id, name, owners)")
            .execute()
        )
        items = results.get("files", [])
        logger.debug(f"[DEBUG] {email}: Folders in SyftBox ({len(items)}):")
        for item in items:
            owners = [o.get("emailAddress", "?") for o in item.get("owners", [])]
            logger.debug(
                f"[DEBUG]   - {item['name']} (id={item['id'][:8]}..., owners={owners})"
            )
    except Exception as e:
        logger.debug(f"[DEBUG] Error getting folder info for {email}: {e}")

    manager.clear_caches()

    # Setup callbacks based on role
    if is_ds:
        # DS: file writes trigger push to outbox
        manager.file_writer.add_callback(
            "write_file",
            manager.proposed_file_change_pusher.on_file_change,
        )
    else:
        # DO: received events trigger job handler
        manager.proposed_file_change_handler.event_cache.add_callback(
            "on_event_local_write",
            manager.job_file_change_handler._handle_file_change,
        )

    logger.info(f"   Created {'DS' if is_ds else 'DO'} manager for {email}")
    return manager


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
        email_env_var="SYFT_EMAIL_DO1",
        cred_env_var="SYFT_CRED_FNAME_DO1",
        token_env_var="SYFT_TOKEN_FNAME_DO1",
        default_cred_file="do1.json",
        default_token_file="token_do1.json",
    )

    do2 = validate_user_credentials(
        user_id="DO2",
        email_env_var="SYFT_EMAIL_DO2",
        cred_env_var="SYFT_CRED_FNAME_DO2",
        token_env_var="SYFT_TOKEN_FNAME_DO2",
        default_cred_file="do2.json",
        default_token_file="token_do2.json",
    )

    ds = validate_user_credentials(
        user_id="DS",
        email_env_var="SYFT_EMAIL_DS",
        cred_env_var="SYFT_CRED_FNAME_DS",
        token_env_var="SYFT_TOKEN_FNAME_DS",
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
    """Initialize syft-client instances for DO1, DO2, DS.

    Creates each manager individually using SyftboxManagerConfig to avoid
    the cross-contamination issues that occur when pair_with_google_drive_testing_connection()
    is called multiple times (which creates duplicate DS managers).
    """
    logger.info("Phase 2: Initializing syft-client managers...")

    env = validate_environment

    # Create each manager individually - NO duplicates
    ds_manager = create_single_manager(
        email=env["EMAIL_DS"],
        token_path=env["token_path_ds"],
        is_ds=True,
    )

    do1_manager = create_single_manager(
        email=env["EMAIL_DO1"],
        token_path=env["token_path_do1"],
        is_ds=False,
    )

    do2_manager = create_single_manager(
        email=env["EMAIL_DO2"],
        token_path=env["token_path_do2"],
        is_ds=False,
    )

    # DS adds both DOs as peers (creates outbox AND inbox folders for each)
    logger.info(f"Adding peer connection: {env['EMAIL_DS']} <-> {env['EMAIL_DO1']}")
    ds_manager.add_peer(env["EMAIL_DO1"])
    logger.info(f"Adding peer connection: {env['EMAIL_DS']} <-> {env['EMAIL_DO2']}")
    ds_manager.add_peer(env["EMAIL_DO2"])

    # Wait for Google Drive operations to complete
    sleep(2)

    # DOs must approve peer requests from DS
    logger.info("DOs approving peer requests from DS...")
    do1_manager.load_peers()
    do1_manager.approve_peer_request(env["EMAIL_DS"])
    logger.info(f"  DO1 approved peer request from {env['EMAIL_DS']}")

    do2_manager.load_peers()
    do2_manager.approve_peer_request(env["EMAIL_DS"])
    logger.info(f"  DO2 approved peer request from {env['EMAIL_DS']}")

    # Wait for approval to propagate
    sleep(2)

    # Verify all managers initialized
    assert ds_manager is not None
    assert do1_manager is not None
    assert do2_manager is not None

    logger.success(" All 3 managers initialized")
    logger.info(f"  - DO1: {env['EMAIL_DO1']}")
    logger.info(f"  - DO2: {env['EMAIL_DO2']}")
    logger.info(f"  - DS: {env['EMAIL_DS']}")

    # Verify DS has both DOs as peers
    ds_peer_emails = [p.email for p in ds_manager.peers]
    logger.info(f"  - DS peers: {ds_peer_emails}")
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
        email_env_var="SYFT_EMAIL_DO1",
        cred_env_var="SYFT_CRED_FNAME_DO1",
        token_env_var="SYFT_TOKEN_FNAME_DO1",
        default_cred_file="do1.json",
        default_token_file="token_do1.json",
    )

    ds = validate_user_credentials(
        user_id="DS",
        email_env_var="SYFT_EMAIL_DS",
        cred_env_var="SYFT_CRED_FNAME_DS",
        token_env_var="SYFT_TOKEN_FNAME_DS",
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
    Creates each manager individually using SyftboxManagerConfig.
    """
    logger.info("Phase 2: Initializing syft-client managers (single DO)...")

    env = validate_environment_single_do

    # Create each manager individually
    ds_manager = create_single_manager(
        email=env["EMAIL_DS"],
        token_path=env["token_path_ds"],
        is_ds=True,
    )

    do1_manager = create_single_manager(
        email=env["EMAIL_DO1"],
        token_path=env["token_path_do1"],
        is_ds=False,
    )

    # DS adds DO1 as peer
    logger.info(f"Adding peer connection: {env['EMAIL_DS']} <-> {env['EMAIL_DO1']}")
    ds_manager.add_peer(env["EMAIL_DO1"])

    # Wait for Google Drive operations to complete
    sleep(2)

    # DO1 must approve peer request from DS
    logger.info("DO1 approving peer request from DS...")
    do1_manager.load_peers()
    do1_manager.approve_peer_request(env["EMAIL_DS"])
    logger.info(f"  DO1 approved peer request from {env['EMAIL_DS']}")

    # Wait for approval to propagate
    sleep(2)

    # Verify managers initialized
    assert ds_manager is not None
    assert do1_manager is not None

    logger.success(" 2 managers initialized (single DO mode)")
    logger.info(f"  - DO1: {env['EMAIL_DO1']}")
    logger.info(f"  - DS: {env['EMAIL_DS']}")

    # Verify DS has DO1 as peer
    ds_peer_emails = [p.email for p in ds_manager.peers]
    logger.info(f"  - DS peers: {ds_peer_emails}")
    assert (
        env["EMAIL_DO1"] in ds_peer_emails
    ), f"DO1 not in DS peers after sync: {ds_peer_emails}"

    return {
        "ds": ds_manager,
        "do1": do1_manager,
        "env": env,
    }
