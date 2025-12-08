from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

from loguru import logger

from syft_flwr.events.protocol import MessageHandler, SyftFlwrEvents
from syft_flwr.gdrive_io import GDriveFileIO

# Maximum number of processed requests to track (LRU eviction)
MAX_PROCESSED_REQUESTS = 10000


class P2PFileEvents(SyftFlwrEvents):
    """P2P File-based polling events using Google Drive API via syft-client.

    This adapter:
    - Polls inbox folders for incoming .request files (from other participants) via Google Drive API
    - Calls the registered handler with the message bytes
    - Writes the response to the outbox folder (back to sender) via Google Drive API

    Directory structure in Google Drive:
        Inbox:  SyftBox/syft_outbox_inbox_{sender}_to_{client}/{app_name}/rpc/{endpoint}/*.request
        Outbox: SyftBox/syft_outbox_inbox_{client}_to_{sender}/{app_name}/rpc/{endpoint}/*.response
    """

    def __init__(
        self,
        app_name: str,
        client_email: str,
        poll_interval: float = 2.0,
        max_processed_requests: int = MAX_PROCESSED_REQUESTS,
    ) -> None:
        self._client_email = client_email
        self._app_name = app_name
        self._poll_interval = poll_interval
        self._gdrive_io = GDriveFileIO(email=client_email)

        # Handler registry: endpoint -> (handler, auto_decrypt, encrypt_reply)
        self._handlers: dict[str, tuple[MessageHandler, bool, bool]] = {}

        # Track processed requests to avoid reprocessing (LRU with max size)
        self._processed_requests: OrderedDict[str, bool] = OrderedDict()
        self._max_processed_requests = max_processed_requests

        # Event loop control
        self._stop_event = Event()

        logger.debug(f"Initialized P2PFileEvents for {client_email}")

    @property
    def client_email(self) -> str:
        return self._client_email

    @property
    def app_dir(self) -> Path:
        # Return logical path in Google Drive (for compatibility with protocol)
        # Note: This is a logical path, actual I/O happens via GDriveFileIO
        return Path("SyftBox") / self._client_email / "app_data" / self._app_name

    def on_request(
        self,
        endpoint: str,
        handler: MessageHandler,
        auto_decrypt: bool = True,
        encrypt_reply: bool = False,
    ) -> None:
        """Register a handler for an endpoint.

        Note: auto_decrypt and encrypt_reply are ignored for P2P mode
        since Google Drive handles access control instead of X3DH encryption.
        """
        endpoint = endpoint.lstrip("/")
        self._handlers[endpoint] = (handler, auto_decrypt, encrypt_reply)
        logger.info(f"Registered handler for endpoint: /{endpoint}")

    def _mark_as_processed(self, request_key: str) -> None:
        """Mark a request as processed with LRU eviction."""
        # Add to processed set
        self._processed_requests[request_key] = True
        # Move to end (most recently used)
        self._processed_requests.move_to_end(request_key)

        # Evict oldest entries if over limit
        while len(self._processed_requests) > self._max_processed_requests:
            self._processed_requests.popitem(last=False)

    def _process_request(
        self,
        sender_email: str,
        endpoint: str,
        filename: str,
        handler: MessageHandler,
    ) -> None:
        """Process a single request file and write response to outbox."""
        # Create a unique key for tracking
        request_key = f"{sender_email}:{endpoint}:{filename}"

        # Skip if already processed
        if request_key in self._processed_requests:
            return

        future_id = filename.rsplit(".", 1)[0]  # Remove .request extension

        # Read request from inbox
        request_body = self._gdrive_io.read_from_inbox(
            sender_email=sender_email,
            app_name=self._app_name,
            endpoint=endpoint,
            filename=filename,
        )

        if request_body is None:
            return

        logger.debug(f"Processing request from {sender_email}: {filename}")

        try:
            response = handler(request_body)

            if response is not None:
                response_filename = f"{future_id}.response"

                if isinstance(response, str):
                    response_bytes = response.encode("utf-8")
                else:
                    response_bytes = response

                # Write response to outbox
                self._gdrive_io.write_to_outbox(
                    recipient_email=sender_email,
                    app_name=self._app_name,
                    endpoint=endpoint,
                    filename=response_filename,
                    data=response_bytes,
                )
                logger.debug(f"Wrote response to outbox: {response_filename}")

        except Exception as e:
            logger.error(f"Error processing request {filename}: {e}")
            # Write error response
            error_response = json.dumps(
                {
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            response_filename = f"{future_id}.response"

            try:
                self._gdrive_io.write_to_outbox(
                    recipient_email=sender_email,
                    app_name=self._app_name,
                    endpoint=endpoint,
                    filename=response_filename,
                    data=error_response.encode("utf-8"),
                )
            except Exception as write_error:
                logger.error(f"Failed to write error response: {write_error}")

        finally:
            # Always delete request file and mark as processed
            try:
                self._gdrive_io.delete_file_from_inbox(
                    sender_email=sender_email,
                    app_name=self._app_name,
                    endpoint=endpoint,
                    filename=filename,
                )
            except Exception as delete_error:
                logger.debug(f"Could not delete request file: {delete_error}")

            self._mark_as_processed(request_key)

    def _poll_loop(self) -> None:
        """Main polling loop that checks for new request files in inbox folders."""
        logger.info("Started polling loop for inbox folders via Google Drive API")

        while not self._stop_event.is_set():
            try:
                # Find all senders who have sent messages to us
                sender_emails = self._gdrive_io.list_inbox_folders()

                for sender_email in sender_emails:
                    if self._stop_event.is_set():
                        break

                    # Check each registered endpoint
                    for endpoint, (handler, _, _) in self._handlers.items():
                        if self._stop_event.is_set():
                            break

                        # List request files in this endpoint
                        request_files = self._gdrive_io.list_files_in_inbox_endpoint(
                            sender_email=sender_email,
                            app_name=self._app_name,
                            endpoint=endpoint,
                            suffix=".request",
                        )

                        for filename in request_files:
                            if self._stop_event.is_set():
                                break
                            self._process_request(
                                sender_email, endpoint, filename, handler
                            )

            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            self._stop_event.wait(timeout=self._poll_interval)

    def run_forever(self) -> None:
        """Start the polling loop and block until stopped."""
        logger.info("Starting P2PFileEvents")
        logger.info(f"  Client email: {self._client_email}")
        logger.info(f"  App name: {self._app_name}")
        logger.info(f"  Poll interval: {self._poll_interval}s")
        logger.info("  Using Google Drive API for file access")

        self._poll_loop()

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        logger.info("Stopping P2PFileEvents")
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        return not self._stop_event.is_set()
