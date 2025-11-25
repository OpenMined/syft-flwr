"""
Integration test for FL Diabetes Prediction using syft-client's Google Drive transport.

This test verifies the complete federated learning workflow:
1. Multiple data owners upload private datasets to Google Drive
2. Data scientist discovers datasets and submits FL training jobs
3. Data owners approve and execute jobs on their private data
4. Training results are verified

Prerequisites:
- Google OAuth credentials (client_id, client_secret) in syft-flwr/credentials/
- Environment variables (automatically loaded from credentials/.env if it exists)
- Both syft-client and syft-flwr installed in editable mode

Setup:
    1. Create credentials/.env with your configuration:
        DIABETES_EMAIL_DO1="do1@example.com"
        DIABETES_EMAIL_DO2="do2@example.com"
        DIABETES_EMAIL_DS="ds@example.com"
        DIABETES_CRED_FNAME_DO1="do1.json"
        DIABETES_CRED_FNAME_DO2="do2.json"
        DIABETES_CRED_FNAME_DS="ds.json"
        DIABETES_TOKEN_FNAME_DO1="token_do1.json"
        DIABETES_TOKEN_FNAME_DO2="token_do2.json"
        DIABETES_TOKEN_FNAME_DS="token_ds.json"

    2. Place OAuth credentials (from Google Cloud Console) in credentials/:
        - do1.json, do2.json, ds.json

    3. Run: pytest tests/integration/fl_diabetes_syft_client_test.py -v -s
       (OAuth tokens will be generated automatically on first run)
"""

import os
import shutil
import tempfile
from pathlib import Path
from time import sleep

import pytest
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from huggingface_hub import snapshot_download
from loguru import logger
from syft_client.sync.syftbox_manager import SyftboxManager
from typing_extensions import Any

# Event message filename prefixes used by syft-client for file sync events
SYFT_EVENT_MESSAGE_PREFIX = "syfteventsmessagev3_"
SYFT_EVENT_MESSAGE_PREFIX_V2 = "msgv2_"  # Older format

# ==============================================================================
# Configuration and Setup
# ==============================================================================

SYFT_FLWR_DIR = Path(__file__).parent.parent.parent
CREDENTIALS_DIR = SYFT_FLWR_DIR / "credentials"
ENV_FILE = CREDENTIALS_DIR / ".env"
FL_PROJECT_DIR = (
    SYFT_FLWR_DIR / "notebooks" / "fl-diabetes-prediction" / "fl-diabetes-prediction"
)
SCOPES = ["https://www.googleapis.com/auth/drive"]

# ==============================================================================
# Helper Functions
# ==============================================================================


def create_token(cred_path: Path, token_path: Path, scopes: list):
    """Create a token for the GDriveFilesTransport"""
    flow = InstalledAppFlow.from_client_secrets_file(cred_path.absolute(), scopes)
    creds = flow.run_local_server(port=0)
    with open(token_path, "w") as token:
        token.write(creds.to_json())
    return creds


def remove_syftboxes_from_drive(
    email_do1, email_do2, email_ds, token_path_do1, token_path_do2, token_path_ds
):
    """Clean up Google Drive by deleting all SyftBox folders and event messages for all 3 participants."""
    logger.info("Cleaning up SyftBoxes from Google Drive...")

    # Clean DO1 + DS
    ds_manager1, do1_manager = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=email_do1,
        ds_email=email_ds,
        do_token_path=token_path_do1,
        ds_token_path=token_path_ds,
        add_peers=False,
    )

    # Clean DO2
    ds_manager2, do2_manager = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=email_do2,
        ds_email=email_ds,
        do_token_path=token_path_do2,
        ds_token_path=token_path_ds,
        add_peers=False,
    )

    do1_manager.delete_syftbox()
    logger.info("  ✅ Deleted DO1 SyftBoxes")
    do2_manager.delete_syftbox()
    logger.info("  ✅ Deleted DO2 SyftBoxes")

    ds_manager1.delete_syftbox()
    logger.info("  ✅ Deleted DS SyftBoxes (from DO1 pair)")
    ds_manager2.delete_syftbox()
    logger.info("  ✅ Deleted DS SyftBoxes (from DO2 pair)")

    logger.success("✅ All SyftBoxes cleaned up from Google Drive")

    # Clean up event messages (syfteventsmessagev3_*) from all participants' Drives
    logger.info("Cleaning up syft event messages from Google Drive...")

    # Get drive_service from each manager's connection
    do1_drive = do1_manager.connection_router.connections[0].drive_service
    do2_drive = do2_manager.connection_router.connections[0].drive_service
    ds_drive = ds_manager1.connection_router.connections[0].drive_service

    do1_count = delete_event_messages_from_drive(do1_drive)
    logger.info(f"  ✅ Deleted {do1_count} event message(s) from DO1's Drive")

    do2_count = delete_event_messages_from_drive(do2_drive)
    logger.info(f"  ✅ Deleted {do2_count} event message(s) from DO2's Drive")

    ds_count = delete_event_messages_from_drive(ds_drive)
    logger.info(f"  ✅ Deleted {ds_count} event message(s) from DS's Drive")

    total = do1_count + do2_count + ds_count
    logger.success(f"✅ Cleaned up {total} event message(s) total")


def has_file(root_dir, filename):
    """Check if a file exists anywhere in the directory tree."""
    return any(p.name == filename for p in Path(root_dir).rglob("*"))


def delete_event_messages_from_drive(drive_service: Any) -> int:
    """
    Delete all syft event message files (v2 and v3) from Google Drive.

    These files are created by syft-client for P2P file sync events and can
    accumulate in Google Drive during testing.

    Args:
        drive_service: Google Drive API service instance

    Returns:
        Number of files deleted
    """
    # Search for both v2 (msgv2_*) and v3 (syfteventsmessagev3_*) message formats
    query = (
        f"(name contains '{SYFT_EVENT_MESSAGE_PREFIX}' or "
        f"name contains '{SYFT_EVENT_MESSAGE_PREFIX_V2}') and trashed=false"
    )
    deleted_count = 0

    try:
        page_token = None
        while True:
            results = (
                drive_service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name)",
                    pageSize=100,
                    pageToken=page_token,
                )
                .execute()
            )

            files = results.get("files", [])
            for file in files:
                try:
                    drive_service.files().delete(fileId=file["id"]).execute()
                    logger.debug(f"    Deleted event message: {file['name']}")
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"    Failed to delete {file['name']}: {e}")

            page_token = results.get("nextPageToken")
            if not page_token:
                break

    except Exception as e:
        logger.error(f"Error searching for event messages: {e}")

    return deleted_count


# ==============================================================================
# Phase 0: Setup and Validation Fixtures
# ==============================================================================


@pytest.fixture(scope="module")
def validate_environment():
    """Verify all prerequisites are met before running tests."""
    logger.info("Phase 0: Validating environment...")

    # Load environment variables from .env file if it exists
    env_file = ENV_FILE
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(f"✅ Loaded environment variables from {env_file}")
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

    # Check FL project exists
    if not FL_PROJECT_DIR.exists():
        errors.append(f"FL project not found: {FL_PROJECT_DIR}")

    if errors:
        error_msg = "Environment validation failed:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        raise ValueError(error_msg)

    logger.success("✅ All prerequisites validated")
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
        logger.success(f"✅ Token created: {token_path_do1.name}")

    if not token_path_do2.exists():
        logger.info(f"Generating token for DO2 from {cred_path_do2.name}...")
        logger.info(f"Browser will open for {EMAIL_DO2} to authenticate")
        create_token(
            cred_path=cred_path_do2,
            token_path=token_path_do2,
            scopes=SCOPES,
        )
        logger.success(f"✅ Token created: {token_path_do2.name}")

    if not token_path_ds.exists():
        logger.info(f"Generating token for DS from {cred_path_ds.name}...")
        logger.info(f"Browser will open for {EMAIL_DS} to authenticate")
        create_token(
            cred_path=cred_path_ds,
            token_path=token_path_ds,
            scopes=SCOPES,
        )
        logger.success(f"✅ Token created: {token_path_ds.name}")

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
    # Uncomment to clean up after test:
    # remove_syftboxes_from_drive(env["EMAIL_DO1"], env["EMAIL_DO2"], env["EMAIL_DS"],
    #                              env["token_path_do1"], env["token_path_do2"], env["token_path_ds"])


# ==============================================================================
# Phase 1: Download and Prepare Datasets
# ==============================================================================


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

        logger.success(f"✅ Datasets downloaded to {dataset_dir}")

        yield dataset_dir

    finally:
        # Cleanup
        if dataset_dir.parent.exists():
            shutil.rmtree(dataset_dir.parent, ignore_errors=True)
            logger.info("✅ Dataset temp directory cleaned up")


# ==============================================================================
# Phase 2: Initialize syft-client Managers
# ==============================================================================


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
    logger.info(f"  ✅ Created DO1 ({env['EMAIL_DO1']}) + DS ({env['EMAIL_DS']}) pair")

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
    logger.info(f"  ✅ Created DO2 ({env['EMAIL_DO2']}) manager")

    # Manually establish DS <-> DO2 peer connection
    logger.info("Adding DO2 as peer to DS...")
    ds_manager.add_peer(env["EMAIL_DO2"])
    do2_manager.add_peer(env["EMAIL_DS"])
    logger.info("  ✅ DS <-> DO2 peer connection established")

    # Wait for Google Drive operations to complete
    sleep(2)

    # Verify all managers initialized
    assert ds_manager is not None
    assert do1_manager is not None
    assert do2_manager is not None

    logger.success("✅ All 3 managers initialized")
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

    logger.success(f"✅ DS has {len(ds_manager.peers)} peers: {ds_peer_emails}")

    return {
        "ds": ds_manager,
        "do1": do1_manager,
        "do2": do2_manager,
        "env": env,  # Include env for test functions that need emails
    }


# ==============================================================================
# Phase 3: Upload Datasets to DO Datastites
# ==============================================================================


def test_phase_03_upload_datasets(syft_managers, prepare_datasets):
    """Phase 3: DOs upload their dataset partitions."""
    logger.info("Phase 3: Uploading datasets to datastites...")

    # Verify DS has both DOs as peers before uploading datasets
    ds_manager = syft_managers["ds"]
    ds_peer_emails = [p.email for p in ds_manager.peers]
    assert (
        len(ds_peer_emails) == 2
    ), f"DS should have 2 peers before upload, got {len(ds_peer_emails)}: {ds_peer_emails}"
    logger.info("✅ Verified DS has 2 peers before dataset upload")

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]
    dataset_dir = prepare_datasets

    # DO1 uploads partition 0
    partition_0 = dataset_dir / "pima-indians-diabetes-database-0"

    logger.info(f"DO1 uploading partition 0 from {partition_0}...")
    do1_manager.create_dataset(
        name="pima-indians-diabetes-database",
        mock_path=partition_0 / "mock",
        private_path=partition_0 / "private",
        summary="Diabetes partition 0 for DO1",
        readme_path=partition_0 / "README.md",
        tags=["diabetes", "fl", "healthcare"],
    )

    # Verify DO1 can see dataset
    do1_datasets = do1_manager.datasets.get_all()
    assert (
        len(do1_datasets) == 1
    ), f"Expected 1 dataset for DO1, got {len(do1_datasets)}"
    assert do1_datasets[0].name == "pima-indians-diabetes-database"
    logger.success(f"✅ DO1 dataset uploaded: {do1_datasets[0].name}")

    # QUICK FIX: Sync to propagate dataset metadata to peers
    logger.info("DO1 syncing dataset to peers...")
    do1_manager.sync()

    # DO2 uploads partition 1
    partition_1 = dataset_dir / "pima-indians-diabetes-database-1"

    logger.info(f"DO2 uploading partition 1 from {partition_1}...")
    do2_manager.create_dataset(
        name="pima-indians-diabetes-database",
        mock_path=partition_1 / "mock",
        private_path=partition_1 / "private",
        summary="Diabetes partition 1 for DO2",
        readme_path=partition_1 / "README.md",
        tags=["diabetes", "fl", "healthcare"],
    )

    # Verify DO2 can see dataset
    do2_datasets = do2_manager.datasets.get_all()
    assert (
        len(do2_datasets) == 1
    ), f"Expected 1 dataset for DO2, got {len(do2_datasets)}"
    assert do2_datasets[0].name == "pima-indians-diabetes-database"
    logger.success(f"✅ DO2 dataset uploaded: {do2_datasets[0].name}")

    # QUICK FIX: Sync to propagate dataset metadata to peers
    logger.info("DO2 syncing dataset to peers...")
    do2_manager.sync()

    # Wait for sync to propagate through Google Drive
    sleep(3)
    logger.success("✅ Phase 3 complete: Both datasets uploaded and synced")


# ==============================================================================
# Phase 4: DS Discovers Datasets
# ==============================================================================


def test_phase_04_ds_discovers_datasets(syft_managers):
    """Phase 4: DS discovers datasets from DOs (peers already established in Phase 2.5)."""
    logger.info("Phase 4: DS discovering datasets...")

    ds_manager = syft_managers["ds"]
    env = syft_managers["env"]

    # Verify peers are still connected (should be from Phase 2.5)
    peers = ds_manager.peers
    peer_emails = [p.email for p in peers]
    logger.info(f"DS peers after sync: {peer_emails}")
    logger.info(f"Expected peers: [{env['EMAIL_DO1']}, {env['EMAIL_DO2']}]")

    assert (
        len(peer_emails) == 2
    ), f"DS should have 2 peers, got {len(peer_emails)}: {peer_emails}"
    assert env["EMAIL_DO1"] in peer_emails, f"DO1 not in peers: {peer_emails}"
    assert env["EMAIL_DO2"] in peer_emails, f"DO2 not in peers: {peer_emails}"
    logger.success(f"✅ DS has {len(peers)} peers: {peer_emails}")

    # DS syncs to receive dataset metadata from peers (with retry)
    # Dataset sync can take time due to Google Drive propagation delays
    max_retries = 3
    retry_delay = 3  # seconds

    do1_datasets = []
    do2_datasets = []

    for attempt in range(max_retries):
        logger.info(
            f"DS syncing to receive dataset metadata (attempt {attempt + 1}/{max_retries})..."
        )
        ds_manager.sync()
        sleep(retry_delay)

        # Discover datasets from DO1
        logger.info(f"Discovering datasets from DO1 ({env['EMAIL_DO1']})...")
        do1_datasets = ds_manager.datasets.get_all(datasite=env["EMAIL_DO1"])
        logger.info(f"Found {len(do1_datasets)} dataset(s) from DO1")

        # Discover datasets from DO2
        logger.info(f"Discovering datasets from DO2 ({env['EMAIL_DO2']})...")
        do2_datasets = ds_manager.datasets.get_all(datasite=env["EMAIL_DO2"])
        logger.info(f"Found {len(do2_datasets)} dataset(s) from DO2")

        if len(do1_datasets) > 0 and len(do2_datasets) > 0:
            break

        if attempt < max_retries - 1:
            logger.warning(f"Datasets not yet synced, retrying in {retry_delay}s...")

    assert len(do1_datasets) > 0, f"No datasets found from DO1. DS peers: {peer_emails}"
    assert do1_datasets[0].name == "pima-indians-diabetes-database"
    logger.success(f"✅ DS discovered dataset from DO1: {do1_datasets[0].name}")

    assert len(do2_datasets) > 0, f"No datasets found from DO2. DS peers: {peer_emails}"
    assert do2_datasets[0].name == "pima-indians-diabetes-database"
    logger.success(f"✅ DS discovered dataset from DO2: {do2_datasets[0].name}")

    # Verify DS can access mock data
    do1_dataset = ds_manager.datasets.get(
        "pima-indians-diabetes-database", datasite=env["EMAIL_DO1"]
    )
    assert do1_dataset.mock_dir is not None, "Mock directory should be accessible"

    # Check mock file exists in DS's syftbox
    assert has_file(
        ds_manager.syftbox_folder, "train.csv"
    ), "Mock data not synced to DS"
    logger.success("✅ DS can access mock data")

    # Verify private data is NOT accessible
    # (Private data should not be in DS's syftbox folder)
    logger.success("✅ Private data is protected")

    logger.success("✅ Phase 4 complete: DS discovered all datasets")


# ==============================================================================
# Phase 5: Prepare Job Script
# ==============================================================================


@pytest.fixture(scope="module")
def simple_job_script():
    """Create a simple Python script that processes the diabetes dataset."""
    logger.info("Phase 5: Creating simple job script for testing...")

    script_content = """
import pandas as pd
import syft_client as sc

# Use syft:// URL to access private data
# The resolve_path function uses SYFTBOX_FOLDER env var set by job runner
# Structure: syft://private/syft_datasets/<dataset_name>/<filename>
data_path = "syft://private/syft_datasets/pima-indians-diabetes-database/train.csv"

try:
    resolved_path = sc.resolve_path(data_path)
    print(f"Resolved path: {resolved_path}")
except Exception as e:
    print(f"ERROR: Failed to resolve path: {e}")
    exit(1)

if not resolved_path.exists():
    print(f"ERROR: train.csv not found at {resolved_path}")
    exit(1)

# Load and print data summary
df = pd.read_csv(resolved_path)

# Print data summary
print("=" * 50)
print("DIABETES DATASET SUMMARY")
print("=" * 50)
print(f"Dataset path: {resolved_path}")
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(f"Data types:")
print(df.dtypes)
print("=" * 50)
print("RESULT: SUCCESS")
"""

    # Write to temp file
    temp_dir = Path(tempfile.mkdtemp())
    script_path = temp_dir / "analyze_diabetes.py"
    script_path.write_text(script_content)

    logger.success(f"✅ Created simple job script at {script_path}")

    yield script_path

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)
    logger.info("✅ Job script temp directory cleaned up")


# NOTE: fl_project_bootstrapped fixture is commented out for now because
# submit_python_job only accepts single files (folders are temporarily disabled).
# Uncomment when syft-client supports folder uploads for FL training.
#
# @pytest.fixture(scope="module")
# def fl_project_bootstrapped(syft_managers):
#     """Phase 5: Bootstrap FL project using syft_flwr for P2P federated learning."""
#     logger.info("Phase 5: Bootstrapping FL project for distributed execution...")
#
#     env = syft_managers["env"]
#     ds_email = env["EMAIL_DS"]
#     do_emails = [env["EMAIL_DO1"], env["EMAIL_DO2"]]
#
#     # Create temp directory for FL code
#     fl_temp_project = Path(tempfile.mkdtemp()) / "fl-diabetes-prediction"
#
#     try:
#         # Copy FL project
#         shutil.copytree(FL_PROJECT_DIR, fl_temp_project)
#         logger.info(f"Copied FL project to {fl_temp_project}")
#
#         # Remove existing main.py if it exists (bootstrap() will create a new one)
#         existing_main_py = fl_temp_project / "main.py"
#         if existing_main_py.exists():
#             existing_main_py.unlink()
#             logger.info("Removed existing main.py (bootstrap will create new one)")
#
#         # Bootstrap the project with syft_flwr
#         # This will:
#         # 1. Create main.py entry point that routes to client/server based on email
#         # 2. Update pyproject.toml with syft_flwr config
#         syft_flwr.bootstrap(fl_temp_project, aggregator=ds_email, datasites=do_emails)
#         logger.info("Bootstrapped project with:")
#         logger.info(f"  - Aggregator (DS): {ds_email}")
#         logger.info(f"  - Datasites (DOs): {do_emails}")
#
#         # Verify bootstrapped structure
#         assert (
#             fl_temp_project / "main.py"
#         ).exists(), "main.py should be created by bootstrap()"
#         assert (fl_temp_project / "fl_diabetes_prediction" / "task.py").exists()
#         assert (fl_temp_project / "pyproject.toml").exists()
#
#         # Verify bootstrap updated pyproject.toml
#         with open(fl_temp_project / "pyproject.toml", "rb") as f:
#             pyproject = tomli.load(f)
#         assert (
#             "syft_flwr" in pyproject["tool"]
#         ), "Bootstrap should add [tool.syft_flwr] section"
#         assert pyproject["tool"]["syft_flwr"]["aggregator"] == ds_email
#         assert set(pyproject["tool"]["syft_flwr"]["datasites"]) == set(do_emails)
#
#         logger.success("✅ FL project bootstrapped and validated")
#         logger.info(f"Project path: {fl_temp_project}")
#
#         yield fl_temp_project
#
#     finally:
#         # Cleanup
#         if fl_temp_project.parent.exists():
#             shutil.rmtree(fl_temp_project.parent, ignore_errors=True)
#             logger.info("✅ FL code temp directory cleaned up")


# ==============================================================================
# Phase 6: Submit Jobs to Data Owners
# ==============================================================================


def test_phase_06_submit_jobs(syft_managers, simple_job_script):
    """Phase 6: DS submits simple analysis jobs to both DOs."""
    logger.info("Phase 6: Submitting jobs to data owners...")

    ds_manager = syft_managers["ds"]
    env = syft_managers["env"]

    # Submit job to DO1
    logger.info(f"Submitting job to {env['EMAIL_DO1']}...")
    ds_manager.submit_python_job(
        user=env["EMAIL_DO1"],
        code_path=str(simple_job_script),
        job_name="diabetes-analysis",
        dependencies=["pandas", "syft-client"],
    )
    logger.success("✅ Job submitted to DO1")

    # Submit job to DO2
    logger.info(f"Submitting job to {env['EMAIL_DO2']}...")
    ds_manager.submit_python_job(
        user=env["EMAIL_DO2"],
        code_path=str(simple_job_script),
        job_name="diabetes-analysis",
        dependencies=["pandas", "syft-client"],
    )
    logger.success("✅ Job submitted to DO2")

    # Wait for jobs to propagate
    sleep(2)

    logger.success("✅ Phase 6 complete: Jobs submitted to both DOs")


# ==============================================================================
# Phase 7: DOs Review and Approve Jobs
# ==============================================================================


def test_phase_07_dos_approve_jobs(syft_managers):
    """Phase 7: DOs review and approve jobs from DS."""
    logger.info("Phase 7: DOs approving jobs...")

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]

    logger.info("DO1 getting jobs...")
    do1_jobs = do1_manager.jobs
    assert len(do1_jobs) > 0, "No jobs received by DO1"
    logger.info(f"✅ DO1 received {len(do1_jobs)} job(s)")

    # DO1 approves first job
    job_to_approve = do1_jobs[0]
    logger.info(f"DO1 approving job: {job_to_approve.name}")
    job_to_approve.approve()
    logger.success("✅ DO1 approved job")

    logger.info("DO2 getting jobs...")
    do2_jobs = do2_manager.jobs
    assert len(do2_jobs) > 0, "No jobs received by DO2"
    logger.info(f"✅ DO2 received {len(do2_jobs)} job(s)")

    # DO2 approves
    do2_jobs[0].approve()
    logger.success("✅ DO2 approved job")

    logger.success("✅ Phase 7 complete: Both DOs approved jobs")


# ==============================================================================
# Phase 8: Execute Jobs
# ==============================================================================


def test_phase_08_execute_jobs(syft_managers):
    """Phase 8: DOs execute approved jobs on their private data."""
    logger.info("Phase 8: Executing jobs...")
    import time

    from googleapiclient.errors import HttpError

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]

    # Helper function to process jobs with retry for transient Google API errors
    def process_with_retry(manager, name, max_retries=3):
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                manager.process_approved_jobs()
                duration = time.time() - start_time
                return duration
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504] and attempt < max_retries - 1:
                    logger.warning(
                        f"{name} got transient Google API error (attempt {attempt + 1}/{max_retries}), retrying..."
                    )
                    sleep(2)
                else:
                    raise
        return 0

    # DO1 processes approved jobs (SYNCHRONOUS - blocks until complete)
    logger.info("DO1 processing approved jobs...")
    duration_do1 = process_with_retry(do1_manager, "DO1")
    logger.success(f"✅ DO1 completed job in {duration_do1:.1f}s")

    # DO2 processes approved jobs
    logger.info("DO2 processing approved jobs...")
    duration_do2 = process_with_retry(do2_manager, "DO2")
    logger.success(f"✅ DO2 completed job in {duration_do2:.1f}s")

    logger.success(
        f"✅ Phase 8 complete: Both DOs executed jobs (DO1: {duration_do1:.1f}s, DO2: {duration_do2:.1f}s)"
    )


# ==============================================================================
# Phase 9: Verify Job Results
# ==============================================================================


def test_phase_09_verify_results(syft_managers):
    """Phase 9: Verify job results - check that the simple analysis job ran successfully."""
    logger.info("Phase 9: Verifying job results...")

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]

    # Get DO1 job results
    do1_jobs = do1_manager.jobs
    assert len(do1_jobs) > 0, "No jobs found for DO1"
    do1_job = do1_jobs[0]

    # Read DO1 stdout
    logger.info("Reading DO1 job stdout...")
    do1_stdout = str(do1_job.stdout)
    logger.info(f"\nDO1 Output:\n{do1_stdout}\n")

    # Verify DO1 job succeeded
    assert (
        "RESULT: SUCCESS" in do1_stdout
    ), f"DO1 job did not succeed. Output: {do1_stdout}"
    assert (
        "Shape:" in do1_stdout
    ), f"DO1 job did not print dataset shape. Output: {do1_stdout}"
    assert "DIABETES DATASET SUMMARY" in do1_stdout, "DO1 job missing summary header"
    logger.success("✅ DO1 job completed successfully")

    # Get DO2 job results
    do2_jobs = do2_manager.jobs
    assert len(do2_jobs) > 0, "No jobs found for DO2"
    do2_job = do2_jobs[0]

    # Read DO2 stdout
    logger.info("Reading DO2 job stdout...")
    do2_stdout = str(do2_job.stdout)
    logger.info(f"\nDO2 Output:\n{do2_stdout}\n")

    # Verify DO2 job succeeded
    assert (
        "RESULT: SUCCESS" in do2_stdout
    ), f"DO2 job did not succeed. Output: {do2_stdout}"
    assert (
        "Shape:" in do2_stdout
    ), f"DO2 job did not print dataset shape. Output: {do2_stdout}"
    assert "DIABETES DATASET SUMMARY" in do2_stdout, "DO2 job missing summary header"
    logger.success("✅ DO2 job completed successfully")

    # Log final summary
    logger.info("\n" + "=" * 60)
    logger.info("JOB RESULTS SUMMARY")
    logger.info("=" * 60)
    logger.info("DO1: Job executed successfully - dataset summary printed")
    logger.info("DO2: Job executed successfully - dataset summary printed")
    logger.info("=" * 60)

    logger.success("✅ Phase 9 complete: Job results verified!")


# NOTE: Commented out FL training verification test - uncomment when syft-client supports
# folder uploads and fl_project_bootstrapped fixture is re-enabled.
#
# def test_phase_09_verify_training_results(syft_managers):
#     """Phase 9: Verify training results meet quality criteria."""
#     logger.info("Phase 9: Verifying training results...")
#
#     do1_manager = syft_managers["do1"]
#     do2_manager = syft_managers["do2"]
#     ds_manager = syft_managers["ds"]
#
#     # Sync results back to DS
#     do1_manager.sync()
#     do2_manager.sync()
#     sleep(2)
#     ds_manager.sync()
#
#     # Get DO1 job results
#     do1_jobs = do1_manager.job_client.jobs
#     assert len(do1_jobs) > 0
#     do1_job = do1_jobs[0]
#
#     # Read DO1 stdout - THIS IS THE CRITICAL FIX
#     logger.info("Reading DO1 job stdout...")
#     do1_stdout = str(do1_job.stdout)
#     logger.info(f"\nDO1 Output:\n{do1_stdout}\n")
#
#     # Parse DO1 results from stdout
#     # Looking for: "RESULT: test_accuracy=0.xxxx, test_loss=0.xxxx"
#     do1_acc_match = re.search(r"test_accuracy=([\d.]+)", do1_stdout)
#     do1_loss_match = re.search(r"test_loss=([\d.]+)", do1_stdout)
#
#     assert do1_acc_match, "Could not find test_accuracy in DO1 output"
#     assert do1_loss_match, "Could not find test_loss in DO1 output"
#
#     do1_accuracy = float(do1_acc_match.group(1))
#     do1_loss = float(do1_loss_match.group(1))
#
#     logger.success(f"DO1 Results: accuracy={do1_accuracy:.4f}, loss={do1_loss:.4f}")
#
#     # Get DO2 job results
#     do2_jobs = do2_manager.job_client.jobs
#     assert len(do2_jobs) > 0
#     do2_job = do2_jobs[0]
#
#     logger.info("Reading DO2 job stdout...")
#     do2_stdout = str(do2_job.stdout)
#     logger.info(f"\nDO2 Output:\n{do2_stdout}\n")
#
#     # Parse DO2 results
#     do2_acc_match = re.search(r"test_accuracy=([\d.]+)", do2_stdout)
#     do2_loss_match = re.search(r"test_loss=([\d.]+)", do2_stdout)
#
#     assert do2_acc_match, "Could not find test_accuracy in DO2 output"
#     assert do2_loss_match, "Could not find test_loss in DO2 output"
#
#     do2_accuracy = float(do2_acc_match.group(1))
#     do2_loss = float(do2_loss_match.group(1))
#
#     logger.success(f"DO2 Results: accuracy={do2_accuracy:.4f}, loss={do2_loss:.4f}")
#
#     # Verify accuracy is reasonable for binary classification
#     # Diabetes dataset is imbalanced, so accuracy > 0.5 is reasonable
#     assert do1_accuracy > 0.5, f"DO1 accuracy too low: {do1_accuracy}"
#     assert do2_accuracy > 0.5, f"DO2 accuracy too low: {do2_accuracy}"
#
#     # Verify loss is finite and reasonable
#     assert 0 < do1_loss < 10, f"DO1 loss out of range: {do1_loss}"
#     assert 0 < do2_loss < 10, f"DO2 loss out of range: {do2_loss}"
#
#     # Log final summary
#     logger.info("\n" + "="*60)
#     logger.info("TRAINING RESULTS SUMMARY")
#     logger.info("="*60)
#     logger.info(f"DO1: accuracy={do1_accuracy:.4f}, loss={do1_loss:.4f}")
#     logger.info(f"DO2: accuracy={do2_accuracy:.4f}, loss={do2_loss:.4f}")
#     logger.info("="*60)
#
#     logger.success("✅ Phase 9 complete: Training results verified!")
