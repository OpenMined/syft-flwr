from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

from loguru import logger

from syft_flwr.events.protocol import MessageHandler, SyftFlwrEvents


class P2PFileEvents(SyftFlwrEvents):
    """P2P File-based polling events for syft_client (Google Drive, OneDrive sync).

    This adapter:
    - Polls a directory for incoming .request files
    - Calls the registered handler with the message bytes
    - Writes the response to a .response file

    Google Drive (and other sync services) handle the actual transport of these
    files between the FL server and client.

    Directory structure:
        {app_dir}/rpc/{endpoint}/{sender}/*.request  <- Incoming messages
        {app_dir}/rpc/{endpoint}/{sender}/*.response <- Outgoing responses
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

        # App directory: {syftbox_folder}/{email}/app_data/{app_name}
        self._app_dir = syftbox_folder / client_email / "app_data" / app_name
        self._rpc_dir = self._app_dir / "rpc"

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
        return self._app_dir

    def _ensure_directories(self) -> None:
        """Ensure the app and RPC directories exist."""
        self._app_dir.mkdir(parents=True, exist_ok=True)
        self._rpc_dir.mkdir(parents=True, exist_ok=True)

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

        endpoint_dir = self._rpc_dir / endpoint
        endpoint_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Registered handler for endpoint: /{endpoint}")

    def _process_request_file(
        self, request_path: Path, handler: MessageHandler
    ) -> None:
        """Process a single request file and write response."""
        response_path = request_path.with_suffix(".response")

        # Skip if already processed
        if response_path.exists():
            return

        try:
            request_body = request_path.read_bytes()
            logger.debug(f"Processing request: {request_path.name}")

            response = handler(request_body)

            if response is not None:
                if isinstance(response, str):
                    response_path.write_text(response)
                else:
                    response_path.write_bytes(response)
                logger.debug(f"Wrote response: {response_path.name}")

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
        """Main polling loop that checks for new request files."""
        logger.info(f"Started polling loop for {self._rpc_dir}")

        while not self._stop_event.is_set():
            try:
                for endpoint, (handler, _, _) in self._handlers.items():
                    endpoint_dir = self._rpc_dir / endpoint

                    if not endpoint_dir.exists():
                        continue

                    for request_file in endpoint_dir.glob("**/*.request"):
                        if self._stop_event.is_set():
                            break
                        self._process_request_file(request_file, handler)

            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            self._stop_event.wait(timeout=self._poll_interval)

    def run_forever(self) -> None:
        """Start the polling loop and block until stopped."""
        self._ensure_directories()

        logger.info("Starting P2PFileEvents")
        logger.info(f"  Client email: {self._client_email}")
        logger.info(f"  App directory: {self._app_dir}")
        logger.info(f"  Poll interval: {self._poll_interval}s")

        self._poll_loop()

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        logger.info("Stopping P2PFileEvents")
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        return not self._stop_event.is_set()
