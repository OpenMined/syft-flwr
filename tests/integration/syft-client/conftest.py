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
from utils import SCOPES, create_token, remove_syftboxes_from_drive

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
# Fixtures
# ==============================================================================


@pytest.fixture(scope="module")
def validate_environment():
    """Verify all prerequisites are met before running tests."""
    logger.info("Phase 0: Validating environment...")

    # Load environment variables from .env file if it exists
    env_file = ENV_FILE
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(f" Loaded environment variables from {env_file}")
    else:
        logger.info(
            f"No .env file found at {env_file}, using existing environment variables"
        )

    # Get environment variables - email addresses
    EMAIL_DO1 = os.environ.get("DIABETES_EMAIL_DO1")
    EMAIL_DO2 = os.environ.get("DIABETES_EMAIL_DO2")
    EMAIL_DS = os.environ.get("DIABETES_EMAIL_DS")

    # Credentials file names (OAuth client credentials from Google Cloud Console)
    CRED_FILE_DO1 = os.environ.get("DIABETES_CRED_FNAME_DO1", "do1.json")
    CRED_FILE_DO2 = os.environ.get("DIABETES_CRED_FNAME_DO2", "do2.json")
    CRED_FILE_DS = os.environ.get("DIABETES_CRED_FNAME_DS", "ds.json")

    # Token file names (OAuth tokens generated after user authentication)
    TOKEN_FILE_DO1 = os.environ.get("DIABETES_TOKEN_FNAME_DO1", "token_do1.json")
    TOKEN_FILE_DO2 = os.environ.get("DIABETES_TOKEN_FNAME_DO2", "token_do2.json")
    TOKEN_FILE_DS = os.environ.get("DIABETES_TOKEN_FNAME_DS", "token_ds.json")

    # Credentials paths (input files with client_id and client_secret)
    cred_path_do1 = CREDENTIALS_DIR / CRED_FILE_DO1
    cred_path_do2 = CREDENTIALS_DIR / CRED_FILE_DO2
    cred_path_ds = CREDENTIALS_DIR / CRED_FILE_DS

    # Token paths (output files with access_token and refresh_token)
    token_path_do1 = CREDENTIALS_DIR / TOKEN_FILE_DO1
    token_path_do2 = CREDENTIALS_DIR / TOKEN_FILE_DO2
    token_path_ds = CREDENTIALS_DIR / TOKEN_FILE_DS

    errors = []

    # Check credentials exist (these are required to generate tokens)
    if not cred_path_do1.exists():
        errors.append(f"Missing DO1 credentials: {cred_path_do1}")
    if not cred_path_do2.exists():
        errors.append(f"Missing DO2 credentials: {cred_path_do2}")
    if not cred_path_ds.exists():
        errors.append(f"Missing DS credentials: {cred_path_ds}")

    # Check environment variables
    if not EMAIL_DO1:
        errors.append("Missing environment variable: DIABETES_EMAIL_DO1")
    if not EMAIL_DO2:
        errors.append("Missing environment variable: DIABETES_EMAIL_DO2")
    if not EMAIL_DS:
        errors.append("Missing environment variable: DIABETES_EMAIL_DS")

    if errors:
        error_msg = "Environment validation failed:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        raise ValueError(error_msg)

    logger.success(" All prerequisites validated")
    logger.info(f"  - DO1: {EMAIL_DO1}")
    logger.info(f"    Credentials: {cred_path_do1.name}")
    logger.info(f"    Token: {token_path_do1.name}")
    logger.info(f"  - DO2: {EMAIL_DO2}")
    logger.info(f"    Credentials: {cred_path_do2.name}")
    logger.info(f"    Token: {token_path_do2.name}")
    logger.info(f"  - DS: {EMAIL_DS}")
    logger.info(f"    Credentials: {cred_path_ds.name}")
    logger.info(f"    Token: {token_path_ds.name}")

    # Auto-generate tokens if they don't exist
    if not token_path_do1.exists():
        logger.info(f"Generating token for DO1 from {cred_path_do1.name}...")
        logger.info(f"Browser will open for {EMAIL_DO1} to authenticate")
        create_token(
            cred_path=cred_path_do1,
            token_path=token_path_do1,
            scopes=SCOPES,
        )
        logger.success(f" Token created: {token_path_do1.name}")

    if not token_path_do2.exists():
        logger.info(f"Generating token for DO2 from {cred_path_do2.name}...")
        logger.info(f"Browser will open for {EMAIL_DO2} to authenticate")
        create_token(
            cred_path=cred_path_do2,
            token_path=token_path_do2,
            scopes=SCOPES,
        )
        logger.success(f" Token created: {token_path_do2.name}")

    if not token_path_ds.exists():
        logger.info(f"Generating token for DS from {cred_path_ds.name}...")
        logger.info(f"Browser will open for {EMAIL_DS} to authenticate")
        create_token(
            cred_path=cred_path_ds,
            token_path=token_path_ds,
            scopes=SCOPES,
        )
        logger.success(f" Token created: {token_path_ds.name}")

    # Store in fixture for other tests to use
    return {
        "EMAIL_DO1": EMAIL_DO1,
        "EMAIL_DO2": EMAIL_DO2,
        "EMAIL_DS": EMAIL_DS,
        "token_path_do1": token_path_do1,
        "token_path_do2": token_path_do2,
        "token_path_ds": token_path_ds,
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

    # Create DO1 + DS pair
    ds_manager, do1_manager = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=env["EMAIL_DO1"],
        ds_email=env["EMAIL_DS"],
        do_token_path=env["token_path_do1"],
        ds_token_path=env["token_path_ds"],
        use_in_memory_cache=False,  # CRITICAL: Must be False for file access
        add_peers=True,  # Establishes DS <-> DO1 connection
        load_peers=False,
        clear_caches=True,
    )
    logger.info(f"   Created DO1 ({env['EMAIL_DO1']}) + DS ({env['EMAIL_DS']}) pair")

    # Create DO2 manager (WITHOUT creating new DS manager)
    _, do2_manager = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=env["EMAIL_DO2"],
        ds_email=env["EMAIL_DS"],
        do_token_path=env["token_path_do2"],
        ds_token_path=env["token_path_ds"],
        use_in_memory_cache=False,
        add_peers=False,  # DON'T auto-add peers (would create new DS manager)
        load_peers=False,
        clear_caches=True,
    )
    logger.info(f"   Created DO2 ({env['EMAIL_DO2']}) manager")

    # Manually establish DS <-> DO2 peer connection
    logger.info("Adding DO2 as peer to DS...")
    ds_manager.add_peer(env["EMAIL_DO2"])
    do2_manager.add_peer(env["EMAIL_DS"])
    logger.info("   DS <-> DO2 peer connection established")

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
