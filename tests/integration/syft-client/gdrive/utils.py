"""
Utility functions for syft-client integration tests.

This module provides reusable helper functions for:
- Google Drive token creation
- SyftBox cleanup
- Event message deletion
- File utilities
"""

from pathlib import Path

from loguru import logger
from syft_client.sync.syftbox_manager import SyftboxManager
from typing_extensions import Any

# ==============================================================================
# Constants
# ==============================================================================

# Event message filename prefixes used by syft-client for file sync events
SYFT_EVENT_MESSAGE_PREFIX = "syfteventsmessagev3_"
SYFT_EVENT_MESSAGE_PREFIX_V2 = "msgv2_"  # Older format

# Google Drive OAuth scopes
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Project paths
SYFT_FLWR_DIR = Path(__file__).parent.parent.parent.parent.parent  # syft-flwr root
CREDENTIALS_DIR = SYFT_FLWR_DIR / "credentials"
ENV_FILE = CREDENTIALS_DIR / ".env"
FL_PROJECT_DIR = (
    SYFT_FLWR_DIR / "notebooks" / "fl-diabetes-prediction" / "fl-diabetes-prediction"
)
TEST_LOGS_DIR = Path("/tmp/syft_flwr_test_logs")


# ==============================================================================
# Token Management
# ==============================================================================


def create_token(cred_path: Path, token_path: Path, scopes: list = None):
    """Create a token for the GDriveFilesTransport.

    Args:
        cred_path: Path to OAuth credentials file (client_id, client_secret)
        token_path: Path where token will be saved
        scopes: OAuth scopes (defaults to Drive full access)
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    if scopes is None:
        scopes = SCOPES

    flow = InstalledAppFlow.from_client_secrets_file(cred_path.absolute(), scopes)
    creds = flow.run_local_server(port=0)
    with open(token_path, "w") as token:
        token.write(creds.to_json())
    return creds


# ==============================================================================
# Google Drive Cleanup
# ==============================================================================


def remove_syftbox_single_do_from_drive(
    email_do, email_ds, token_path_do, token_path_ds
):
    """Clean up Google Drive for single DO + DS.

    Args:
        email_do: Data Owner email
        email_ds: Data Scientist email
        token_path_do: Path to DO OAuth token
        token_path_ds: Path to DS OAuth token
    """
    logger.info("Cleaning up SyftBoxes from Google Drive (single DO)...")

    ds_manager, do_manager = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=email_do,
        ds_email=email_ds,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
    )

    do_manager.delete_syftbox()
    logger.info("  ✅ Deleted DO SyftBoxes")

    ds_manager.delete_syftbox()
    logger.info("  ✅ Deleted DS SyftBoxes")

    logger.success("✅ SyftBoxes cleaned up from Google Drive (single DO)")

    # Clean up event messages
    logger.info("Cleaning up syft event messages from Google Drive...")

    do_drive = do_manager.connection_router.connections[0].drive_service
    ds_drive = ds_manager.connection_router.connections[0].drive_service

    do_count = delete_event_messages_from_drive(do_drive)
    logger.info(f"  ✅ Deleted {do_count} event message(s) from DO's Drive")

    ds_count = delete_event_messages_from_drive(ds_drive)
    logger.info(f"  ✅ Deleted {ds_count} event message(s) from DS's Drive")

    total = do_count + ds_count
    logger.success(f"✅ Cleaned up {total} event message(s) total")


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
# File Utilities
# ==============================================================================


def has_file(root_dir, filename):
    """Check if a file exists anywhere in the directory tree.

    Args:
        root_dir: Root directory to search
        filename: Filename to find

    Returns:
        True if file exists, False otherwise
    """
    return any(p.name == filename for p in Path(root_dir).rglob("*"))
