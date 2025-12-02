from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from loguru import logger
from syft_client.sync.connections.drive.gdrive_transport import GdriveInboxOutBoxFolder

from syft_flwr.rpc.protocol import SyftFlwrRpc


class P2PFileRpc(SyftFlwrRpc):
    """P2P File-based RPC adapter for syft_client (Google Drive / Microsoft 365... sync).

    Instead of using syft_rpc with its futures database, this adapter:
    - Writes .request files to the shared outbox folder (synced via Google Drive)
    - Polls for .response files in the inbox folder
    - Uses in-memory tracking for pending futures

    Directory structure (using syft-client inbox/outbox pattern):
        {syftbox_folder}/syft_outbox_inbox_{sender}_to_{recipient}/{app_name}/rpc/{endpoint}/*.request
        {syftbox_folder}/syft_outbox_inbox_{recipient}_to_{sender}/{app_name}/rpc/{endpoint}/*.response
    """

    def __init__(
        self,
        sender_email: str,
        syftbox_folder: Path,
        app_name: str,
    ) -> None:
        self._sender_email = sender_email
        self._syftbox_folder = syftbox_folder
        self._app_name = app_name
        self._pending_futures: dict[
            str, tuple[Path, str]
        ] = {}  # future_id -> (response_path, recipient)
        logger.debug(f"Initialized P2PFileRpc for {sender_email}")

    def send(
        self,
        to_email: str,
        app_name: str,
        endpoint: str,
        body: bytes,
        encrypt: bool = False,
    ) -> str:
        if encrypt:
            logger.warning(
                "Encryption not supported in FileRpcAdapter, sending unencrypted"
            )

        # Outbox path: {syftbox_folder}/syft_outbox_inbox_{sender}_to_{recipient}/{app_name}/rpc/{endpoint}/
        outbox_folder = GdriveInboxOutBoxFolder(
            sender_email=self._sender_email, recipient_email=to_email
        )
        target_dir = (
            self._syftbox_folder
            / outbox_folder.as_string()
            / app_name
            / "rpc"
            / endpoint.lstrip("/")
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        future_id = str(uuid.uuid4())
        request_path = target_dir / f"{future_id}.request"
        request_path.write_bytes(body)

        # Response will come back via inbox (recipient's outbox to us)
        inbox_folder = GdriveInboxOutBoxFolder(
            sender_email=to_email, recipient_email=self._sender_email
        )
        response_dir = (
            self._syftbox_folder
            / inbox_folder.as_string()
            / app_name
            / "rpc"
            / endpoint.lstrip("/")
        )
        response_path = response_dir / f"{future_id}.response"
        self._pending_futures[future_id] = (response_path, to_email)

        logger.debug(f"Sent message to {to_email}, future_id={future_id}")
        logger.debug(f"  Outbox: {target_dir}")
        logger.debug(f"  Expecting response in: {response_dir}")
        return future_id

    def get_response(self, future_id: str) -> Optional[bytes]:
        future_data = self._pending_futures.get(future_id)
        if future_data is None:
            logger.warning(f"Unknown future_id: {future_id}")
            return None

        response_path, _ = future_data
        if response_path.exists():
            body = response_path.read_bytes()
            logger.debug(f"Got response for future_id={future_id}")
            return body

        return None

    def delete_future(self, future_id: str) -> None:
        future_data = self._pending_futures.pop(future_id, None)
        if future_data is not None:
            response_path, _ = future_data
            # Clean up response file from inbox
            if response_path.exists():
                response_path.unlink()
            logger.debug(f"Deleted future_id={future_id}")
