from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import List

from loguru import logger
from syft_client.sync.connections.drive.gdrive_transport import (
    GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX,
    GdriveInboxOutBoxFolder,
)

from syft_flwr.events.protocol import MessageHandler, SyftFlwrEvents


class P2PFileEvents(SyftFlwrEvents):
    """P2P File-based polling events for syft_client (Google Drive, OneDrive sync).

    This adapter:
    - Polls inbox folders for incoming .request files (from other participants)
    - Calls the registered handler with the message bytes
    - Writes the response to the outbox folder (back to sender)

    Uses syft-client inbox/outbox folder pattern for Google Drive sync:
        Inbox:  {syftbox_folder}/syft_outbox_inbox_{sender}_to_{client}/{app_name}/rpc/{endpoint}/*.request
        Outbox: {syftbox_folder}/syft_outbox_inbox_{client}_to_{sender}/{app_name}/rpc/{endpoint}/*.response
    """

    def __init__(
        self,
        app_name: str,
        client_email: str,
        syftbox_folder: Path,
        poll_interval: float = 2.0,
    ) -> None:
        self._client_email = client_email
        self._syftbox_folder = syftbox_folder
        self._app_name = app_name
        self._poll_interval = poll_interval

        # Handler registry: endpoint -> (handler, auto_decrypt, encrypt_reply)
        self._handlers: dict[str, tuple[MessageHandler, bool, bool]] = {}

        # Event loop control
        self._stop_event = Event()

        logger.debug(f"Initialized P2PFileEvents for {client_email}")

    @property
    def client_email(self) -> str:
        return self._client_email

    @property
    def app_dir(self) -> Path:
        # Return the client's own datasite app directory (for compatibility)
        return self._syftbox_folder / self._client_email / "app_data" / self._app_name

    def _get_inbox_folder_pattern(self) -> str:
        """Get the glob pattern to find all inbox folders for this client."""
        return f"{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}_*_to_{self._client_email}"

    def _get_inbox_folders(self) -> List[Path]:
        """Find all inbox folders for this client."""
        return list(self._syftbox_folder.glob(self._get_inbox_folder_pattern()))

    def on_request(
        self,
        endpoint: str,
        handler: MessageHandler,
        auto_decrypt: bool = True,
        encrypt_reply: bool = False,
    ) -> None:
        """Register a handler for an endpoint.

        Note: auto_decrypt and encrypt_reply are ignored for syft_client
        since Google Drive handles access control instead of X3DH encryption.
        """
        endpoint = endpoint.lstrip("/")
        self._handlers[endpoint] = (handler, auto_decrypt, encrypt_reply)
        logger.info(f"Registered handler for endpoint: /{endpoint}")

    def _process_request_file(
        self,
        request_path: Path,
        handler: MessageHandler,
        sender_email: str,
        endpoint: str,
    ) -> None:
        """Process a single request file and write response to outbox."""
        future_id = request_path.stem  # filename without extension

        # Response goes to our outbox (which is sender's inbox)
        outbox_folder = GdriveInboxOutBoxFolder(
            sender_email=self._client_email, recipient_email=sender_email
        )
        response_dir = (
            self._syftbox_folder
            / outbox_folder.as_string()
            / self._app_name
            / "rpc"
            / endpoint
        )
        response_dir.mkdir(parents=True, exist_ok=True)
        response_path = response_dir / f"{future_id}.response"

        # Skip if already processed
        if response_path.exists():
            return

        try:
            request_body = request_path.read_bytes()
            logger.debug(f"Processing request from {sender_email}: {request_path.name}")

            response = handler(request_body)

            if response is not None:
                if isinstance(response, str):
                    response_path.write_text(response)
                else:
                    response_path.write_bytes(response)
                logger.debug(f"Wrote response to outbox: {response_path}")

        except Exception as e:
            logger.error(f"Error processing request {request_path}: {e}")
            error_response = json.dumps(
                {
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            response_path.write_text(error_response)

    def _poll_loop(self) -> None:
        """Main polling loop that checks for new request files in inbox folders."""
        logger.info(
            f"Started polling loop for inbox folders matching: {self._get_inbox_folder_pattern()}"
        )

        while not self._stop_event.is_set():
            try:
                # Find all inbox folders (messages from other participants)
                inbox_folders = self._get_inbox_folders()

                for inbox_folder in inbox_folders:
                    if self._stop_event.is_set():
                        break

                    # Extract sender email from folder name using syft-client utility
                    try:
                        folder_info = GdriveInboxOutBoxFolder.from_name(
                            inbox_folder.name
                        )
                        sender_email = folder_info.sender_email
                    except Exception:
                        continue

                    # Check each registered endpoint
                    for endpoint, (handler, _, _) in self._handlers.items():
                        endpoint_dir = inbox_folder / self._app_name / "rpc" / endpoint

                        if not endpoint_dir.exists():
                            continue

                        for request_file in endpoint_dir.glob("*.request"):
                            if self._stop_event.is_set():
                                break
                            self._process_request_file(
                                request_file, handler, sender_email, endpoint
                            )

            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            self._stop_event.wait(timeout=self._poll_interval)

    def run_forever(self) -> None:
        """Start the polling loop and block until stopped."""
        logger.info("Starting P2PFileEvents")
        logger.info(f"  Client email: {self._client_email}")
        logger.info(f"  SyftBox folder: {self._syftbox_folder}")
        logger.info(f"  App name: {self._app_name}")
        logger.info(f"  Poll interval: {self._poll_interval}s")
        logger.info(f"  Watching inbox folders: {self._get_inbox_folder_pattern()}")

        self._poll_loop()

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        logger.info("Stopping P2PFileEvents")
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        return not self._stop_event.is_set()
