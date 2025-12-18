"""Google Drive file I/O utilities for P2P transport.

This module provides a simple interface for reading/writing files to Google Drive
using syft-client's GDriveConnection. It handles:
- Creating inbox/outbox folders in SyftBox
- Writing request/response files
- Reading files from inbox folders
- Listing files in folders

Environment variables:
- GDRIVE_TOKEN_PATH: Path to OAuth token file (for non-Colab environments)
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import List, Optional

from loguru import logger
from syft_client.sync.connections.drive.gdrive_transport import (
    GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX,
    GDriveConnection,
    GdriveInboxOutBoxFolder,
)


class GDriveFileIO:
    """Simple file I/O wrapper around GDriveConnection for P2P RPC.

    Provides methods to:
    - Write files to outbox (for sending requests)
    - Read files from inbox (for receiving responses)
    - List files in folders
    """

    def __init__(self, email: str):
        """Initialize GDriveFileIO.

        Args:
            email: The user's email address
        """
        self._email = email
        self._connection: Optional[GDriveConnection] = None
        self._connection_ready: bool = False  # Flag to ensure setup() completes
        self._folder_id_cache: dict[str, str] = {}
        self._connection_lock = threading.Lock()
        self._api_lock = threading.Lock()  # Serialize all API operations for SSL safety

    def _ensure_connection(self) -> GDriveConnection:
        """Lazily initialize the GDriveConnection (thread-safe).

        Uses double-checked locking with a flag to ensure setup() completes
        before any other thread can use the connection.

        Authentication priority:
        1. GDRIVE_TOKEN_PATH env var (for local/test environments)
        2. Automatic OAuth (for Colab environments)
        """
        # First check without lock for performance (check both connection and setup flag)
        if self._connection is not None and self._connection_ready:
            return self._connection

        with self._connection_lock:
            # Double-check after acquiring lock
            if self._connection is None or not self._connection_ready:
                # Check for token path from environment variable
                token_path_str = os.environ.get("GDRIVE_TOKEN_PATH")

                if token_path_str:
                    # Use token file for authentication (local/test environment)
                    token_path = Path(token_path_str)
                    if not token_path.exists():
                        raise FileNotFoundError(
                            f"GDRIVE_TOKEN_PATH set but file not found: {token_path}"
                        )
                    logger.debug(
                        f"Initializing GDriveConnection for {self._email} with token: {token_path}"
                    )
                    self._connection = GDriveConnection.from_token_path(
                        email=self._email, token_path=token_path
                    )
                else:
                    # In Colab, this will use automatic OAuth
                    logger.debug(
                        f"Initializing GDriveConnection for {self._email} (automatic OAuth)"
                    )
                    self._connection = GDriveConnection(email=self._email)
                    self._connection.setup()

                self._connection_ready = True  # Mark as ready AFTER setup completes
                logger.debug(f"GDriveConnection ready for {self._email}")
        return self._connection

    def _get_or_create_folder(
        self, folder_name: str, share_with_email: Optional[str] = None
    ) -> str:
        """Get folder ID, creating it if necessary.

        First checks for folders owned by self. If not found and share_with_email
        is provided, also checks for folders shared by that email (the recipient
        may have pre-created the folder and shared it with us, e.g., in DS→DO workflow
        where DS pre-creates inbox folders for DOs to write responses).

        Args:
            folder_name: The folder name (e.g., syft_outbox_inbox_sender_to_recipient)
            share_with_email: If provided and folder is newly created, share it with
                this email address with write permissions. This is required for
                cross-account visibility in Google Drive.

        Returns:
            Google Drive folder ID
        """
        if folder_name in self._folder_id_cache:
            logger.debug(f"[GDrive] Cache hit for folder: {folder_name}")
            return self._folder_id_cache[folder_name]

        conn = self._ensure_connection()
        syftbox_id = conn.get_syftbox_folder_id()
        logger.debug(f"[GDrive] SyftBox folder ID: {syftbox_id}")

        # First, try to find folder owned by self
        logger.debug(
            f"[GDrive] Looking for folder: {folder_name} (owner: {self._email})"
        )
        folder_id = conn._find_folder_by_name(folder_name, owner_email=self._email)

        # If not found and we're sharing with someone, check if they pre-created it
        # This handles the case where DS pre-creates inbox folders for DOs
        if folder_id is None and share_with_email:
            logger.debug(
                f"[GDrive] Folder not found, checking if {share_with_email} shared it with us"
            )
            folder_id = conn._find_folder_by_name(
                folder_name, owner_email=share_with_email
            )
            if folder_id:
                logger.debug(
                    f"[GDrive] Found shared folder from {share_with_email} (id: {folder_id})"
                )
                self._folder_id_cache[folder_name] = folder_id
                return folder_id

        if folder_id is None:
            # Create the folder
            logger.debug(f"[GDrive] Creating folder: {folder_name}")
            folder_id = conn.create_folder(folder_name, syftbox_id)
            logger.debug(f"[GDrive] Created folder: {folder_name} (id: {folder_id})")

            # Share with recipient if specified (required for cross-account visibility)
            if share_with_email:
                try:
                    conn.add_permission(folder_id, share_with_email, write=True)
                    logger.debug(
                        f"[GDrive] Shared folder '{folder_name}' with {share_with_email}"
                    )
                except Exception as e:
                    logger.error(
                        f"[GDrive] Failed to share folder with {share_with_email}: {e}"
                    )
                    # Continue anyway - the folder exists, just not shared
        else:
            logger.debug(
                f"[GDrive] Found existing folder: {folder_name} (id: {folder_id})"
            )

        self._folder_id_cache[folder_name] = folder_id
        return folder_id

    def _get_nested_folder(
        self, parent_id: str, path_parts: List[str], create_if_missing: bool = True
    ) -> Optional[str]:
        """Get or create nested folders under parent.

        Args:
            parent_id: Parent folder ID
            path_parts: List of folder names to create/traverse
            create_if_missing: If True, create folders that don't exist.
                If False, return None if any folder in the path doesn't exist.
                Use False when reading from inbox (folders owned by others)
                to avoid creating duplicate folders.

        Returns:
            Final folder ID, or None if create_if_missing=False and path doesn't exist
        """
        conn = self._ensure_connection()
        current_id = parent_id

        for part in path_parts:
            cache_key = f"{current_id}/{part}"
            if cache_key in self._folder_id_cache:
                current_id = self._folder_id_cache[cache_key]
                continue

            # Try to find existing folder
            folder_id = conn._find_folder_by_name(part, parent_id=current_id)

            if folder_id is None:
                if create_if_missing:
                    # Create the folder
                    folder_id = conn.create_folder(part, current_id)
                    logger.debug(f"Created nested folder: {part}")
                else:
                    # Don't create - return None to indicate path doesn't exist yet
                    logger.debug(
                        f"[GDrive] Nested folder not found: {part} (not creating)"
                    )
                    return None

            self._folder_id_cache[cache_key] = folder_id
            current_id = folder_id

        return current_id

    def _find_inbox_folder(
        self, sender_email: str, conn: GDriveConnection
    ) -> Optional[str]:
        """Find an inbox folder (sender -> self).

        In P2P mode, the inbox folder can be owned by either:
        1. The sender (sender creates their own outbox)
        2. Self (DS pre-creates inbox folders for DOs to write responses)

        Args:
            sender_email: Email of the sender
            conn: GDriveConnection instance

        Returns:
            Folder ID if found, None otherwise
        """
        inbox_folder = GdriveInboxOutBoxFolder(
            sender_email=sender_email, recipient_email=self._email
        )
        inbox_folder_name = inbox_folder.as_string()

        # First try: folder owned by sender
        folder_id = conn._find_folder_by_name(
            inbox_folder_name, owner_email=sender_email
        )

        # Second try: folder owned by self (DS pre-created the inbox)
        if folder_id is None:
            folder_id = conn._find_folder_by_name(
                inbox_folder_name, owner_email=self._email
            )

        return folder_id

    def write_to_outbox(
        self,
        recipient_email: str,
        app_name: str,
        endpoint: str,
        filename: str,
        data: bytes,
    ) -> None:
        """Write a file to the outbox folder (sender -> recipient).

        Path: SyftBox/syft_outbox_inbox_{self._email}_to_{recipient}/{app_name}/rpc/{endpoint}/{filename}

        Args:
            recipient_email: Recipient's email
            app_name: Application name (e.g., "syft_flwr")
            endpoint: RPC endpoint name
            filename: File name (e.g., "{uuid}.request")
            data: File contents as bytes
        """
        logger.debug(f"[GDrive] write_to_outbox: {self._email} -> {recipient_email}")
        logger.debug(
            f"[GDrive]   app_name={app_name}, endpoint={endpoint}, filename={filename}"
        )
        logger.debug(f"[GDrive]   data size: {len(data)} bytes")

        with self._api_lock:
            conn = self._ensure_connection()

            # Get/create the outbox folder (shared with recipient for cross-account visibility)
            outbox_folder = GdriveInboxOutBoxFolder(
                sender_email=self._email, recipient_email=recipient_email
            )
            outbox_folder_name = outbox_folder.as_string()
            logger.debug(f"[GDrive]   outbox folder name: {outbox_folder_name}")
            outbox_folder_id = self._get_or_create_folder(
                outbox_folder_name, share_with_email=recipient_email
            )

            # Create nested path: {app_name}/rpc/{endpoint}
            path_parts = [app_name, "rpc", endpoint.lstrip("/")]
            logger.debug(f"[GDrive]   nested path: {'/'.join(path_parts)}")
            endpoint_folder_id = self._get_nested_folder(outbox_folder_id, path_parts)

            # Upload the file
            payload, _ = conn.create_file_payload(data)
            file_metadata = {
                "name": filename,
                "parents": [endpoint_folder_id],
            }

            result = (
                conn.drive_service.files()
                .create(body=file_metadata, media_body=payload, fields="id")
                .execute()
            )

            logger.debug(
                f"[GDrive] Wrote file to outbox: {filename} (id: {result.get('id')})"
            )

    def read_from_inbox(
        self,
        sender_email: str,
        app_name: str,
        endpoint: str,
        filename: str,
    ) -> Optional[bytes]:
        """Read a file from the inbox folder (sender -> self).

        Path: SyftBox/syft_outbox_inbox_{sender}_to_{self._email}/{app_name}/rpc/{endpoint}/{filename}

        Args:
            sender_email: Sender's email
            app_name: Application name
            endpoint: RPC endpoint name
            filename: File name to read

        Returns:
            File contents as bytes, or None if not found
        """
        logger.debug(f"[GDrive] read_from_inbox: {sender_email} -> {self._email}")
        logger.debug(
            f"[GDrive]   app_name={app_name}, endpoint={endpoint}, filename={filename}"
        )

        with self._api_lock:
            conn = self._ensure_connection()

            # Find the inbox folder
            inbox_folder_id = self._find_inbox_folder(sender_email, conn)

            if inbox_folder_id is None:
                logger.debug(
                    "[GDrive]   Inbox folder not found (sender may not have sent anything yet)"
                )
                return None

            logger.debug(f"[GDrive]   Found inbox folder: {inbox_folder_id}")

            # Navigate to endpoint folder (don't create - folders owned by sender)
            path_parts = [app_name, "rpc", endpoint.lstrip("/")]
            endpoint_folder_id = self._get_nested_folder(
                inbox_folder_id, path_parts, create_if_missing=False
            )
            if endpoint_folder_id is None:
                logger.debug(
                    f"[GDrive]   Endpoint folder not found yet: {'/'.join(path_parts)}"
                )
                return None
            logger.debug(f"[GDrive]   Found endpoint folder: {endpoint_folder_id}")

            # Find the file
            query = f"name='{filename}' and '{endpoint_folder_id}' in parents and trashed=false"
            results = (
                conn.drive_service.files()
                .list(q=query, fields="files(id)", pageSize=1)
                .execute()
            )
            items = results.get("files", [])

            if not items:
                logger.debug(f"[GDrive]   File not found: {filename}")
                return None

            file_id = items[0]["id"]
            logger.debug(f"[GDrive]   Downloading file: {filename} (id: {file_id})")
            data = conn.download_file(file_id)
            logger.debug(f"[GDrive]   Downloaded {len(data)} bytes")
            return data

    def list_inbox_folders(self) -> List[str]:
        """List all inbox folders for this user.

        Returns:
            List of sender emails who have sent messages to this user
        """
        logger.debug(f"[GDrive] list_inbox_folders for {self._email}")

        with self._api_lock:
            conn = self._ensure_connection()

            # Find all folders matching the inbox pattern
            query = (
                f"name contains '{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}' "
                f"and name contains '_to_{self._email}' "
                f"and mimeType='application/vnd.google-apps.folder' "
                f"and trashed=false"
            )
            logger.debug(f"[GDrive]   Query: {query}")

            # Handle pagination to get all folders
            sender_emails = []
            page_token = None
            page_count = 0

            while True:
                page_count += 1
                results = (
                    conn.drive_service.files()
                    .list(
                        q=query,
                        fields="files(name), nextPageToken",
                        pageSize=100,
                        pageToken=page_token,
                    )
                    .execute()
                )

                files_in_page = results.get("files", [])
                logger.debug(
                    f"[GDrive]   Page {page_count}: found {len(files_in_page)} folders"
                )

                for item in files_in_page:
                    try:
                        folder_info = GdriveInboxOutBoxFolder.from_name(item["name"])
                        if folder_info.recipient_email == self._email:
                            sender_emails.append(folder_info.sender_email)
                            logger.debug(
                                f"[GDrive]     Found inbox from: {folder_info.sender_email}"
                            )
                    except Exception as e:
                        logger.debug(
                            f"[GDrive]     Failed to parse folder name {item['name']}: {e}"
                        )
                        continue

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

            logger.debug(f"[GDrive]   Total senders found: {len(sender_emails)}")
            return sender_emails

    def list_files_in_inbox_endpoint(
        self,
        sender_email: str,
        app_name: str,
        endpoint: str,
        suffix: str = ".request",
    ) -> List[str]:
        """List files in an inbox endpoint folder.

        Args:
            sender_email: Sender's email
            app_name: Application name
            endpoint: RPC endpoint name
            suffix: File suffix to filter (e.g., ".request")

        Returns:
            List of filenames
        """
        logger.debug(f"[GDrive] list_files_in_inbox_endpoint: from {sender_email}")
        logger.debug(
            f"[GDrive]   app_name={app_name}, endpoint={endpoint}, suffix={suffix}"
        )

        with self._api_lock:
            conn = self._ensure_connection()

            # Find the inbox folder
            inbox_folder_id = self._find_inbox_folder(sender_email, conn)

            if inbox_folder_id is None:
                logger.debug("[GDrive]   Inbox folder not found")
                return []

            logger.debug(f"[GDrive]   Found inbox folder: {inbox_folder_id}")

            # Navigate to endpoint folder (don't create - folders may be owned by sender or self)
            path_parts = [app_name, "rpc", endpoint.lstrip("/")]
            endpoint_folder_id = self._get_nested_folder(
                inbox_folder_id, path_parts, create_if_missing=False
            )
            if endpoint_folder_id is None:
                logger.debug(
                    f"[GDrive]   Endpoint folder not found yet: {'/'.join(path_parts)}"
                )
                return []
            logger.debug(f"[GDrive]   Found endpoint folder: {endpoint_folder_id}")

            # List files with suffix
            query = (
                f"'{endpoint_folder_id}' in parents "
                f"and name contains '{suffix}' "
                f"and trashed=false"
            )

            results = (
                conn.drive_service.files().list(q=query, fields="files(name)").execute()
            )

            filenames = [item["name"] for item in results.get("files", [])]
            logger.debug(
                f"[GDrive]   Found {len(filenames)} files with suffix '{suffix}'"
            )
            if filenames:
                logger.debug(
                    f"[GDrive]   Files: {filenames[:5]}{'...' if len(filenames) > 5 else ''}"
                )

            return filenames

    def _delete_file_in_folder(
        self,
        folder_id: str,
        app_name: str,
        endpoint: str,
        filename: str,
    ) -> bool:
        """Delete a file from a folder given the folder ID.

        Args:
            folder_id: Google Drive folder ID
            app_name: Application name
            endpoint: RPC endpoint name
            filename: File name to delete

        Returns:
            True if deleted, False if not found
        """
        conn = self._ensure_connection()

        path_parts = [app_name, "rpc", endpoint.lstrip("/")]
        try:
            endpoint_folder_id = self._get_nested_folder(folder_id, path_parts)
            logger.debug(f"[GDrive]   Found endpoint folder: {endpoint_folder_id}")
        except Exception as e:
            logger.debug(
                f"[GDrive]   Failed to find endpoint folder {'/'.join(path_parts)}: {e}"
            )
            return False

        # Find and delete the file
        query = (
            f"name='{filename}' and '{endpoint_folder_id}' in parents and trashed=false"
        )
        try:
            results = (
                conn.drive_service.files()
                .list(q=query, fields="files(id)", pageSize=1)
                .execute()
            )
            items = results.get("files", [])

            if not items:
                logger.debug(f"[GDrive]   File not found for deletion: {filename}")
                return False

            file_id = items[0]["id"]
            conn.drive_service.files().delete(fileId=file_id).execute()
            logger.debug(f"[GDrive]   Deleted file: {filename} (id: {file_id})")
            return True
        except Exception as e:
            logger.error(f"[GDrive]   Failed to delete file {filename}: {e}")
            return False

    def delete_file_from_inbox(
        self,
        sender_email: str,
        app_name: str,
        endpoint: str,
        filename: str,
    ) -> bool:
        """Delete a file from inbox (files sent TO us FROM sender).

        Path: SyftBox/syft_outbox_inbox_{sender}_to_{self._email}/{app_name}/rpc/{endpoint}/{filename}

        Args:
            sender_email: Email of the sender who sent the file
            app_name: Application name
            endpoint: RPC endpoint name
            filename: File name to delete

        Returns:
            True if deleted, False if not found
        """
        logger.debug(
            f"[GDrive] delete_file_from_inbox: {sender_email} -> {self._email}"
        )
        logger.debug(
            f"[GDrive]   app_name={app_name}, endpoint={endpoint}, filename={filename}"
        )

        with self._api_lock:
            conn = self._ensure_connection()

            # Find the inbox folder
            folder_id = self._find_inbox_folder(sender_email, conn)

            if folder_id is None:
                logger.debug("[GDrive]   Inbox folder not found")
                return False

            logger.debug(f"[GDrive]   Found inbox folder: {folder_id}")
            return self._delete_file_in_folder(folder_id, app_name, endpoint, filename)

    def delete_file_from_outbox(
        self,
        recipient_email: str,
        app_name: str,
        endpoint: str,
        filename: str,
    ) -> bool:
        """Delete a file from outbox (files sent BY us TO recipient).

        Path: SyftBox/syft_outbox_inbox_{self._email}_to_{recipient}/{app_name}/rpc/{endpoint}/{filename}

        Args:
            recipient_email: Email of the recipient we sent the file to
            app_name: Application name
            endpoint: RPC endpoint name
            filename: File name to delete

        Returns:
            True if deleted, False if not found
        """
        logger.debug(
            f"[GDrive] delete_file_from_outbox: {self._email} -> {recipient_email}"
        )
        logger.debug(
            f"[GDrive]   app_name={app_name}, endpoint={endpoint}, filename={filename}"
        )

        with self._api_lock:
            conn = self._ensure_connection()

            folder = GdriveInboxOutBoxFolder(
                sender_email=self._email, recipient_email=recipient_email
            )
            folder_name = folder.as_string()
            folder_id = conn._find_folder_by_name(folder_name, owner_email=self._email)

            if folder_id is None:
                logger.debug(f"[GDrive]   Outbox folder not found: {folder_name}")
                return False

            logger.debug(f"[GDrive]   Found outbox folder: {folder_id}")
            return self._delete_file_in_folder(folder_id, app_name, endpoint, filename)
