from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

from syft_flwr.rpc.protocol import SyftFlwrRpc


class P2PFileRpc(SyftFlwrRpc):
    """P2P File-based RPC adapter for syft_client (Google Drive / Microsoft 365... sync).

    Instead of using syft_rpc with its futures database, this adapter:
    - Writes .request files directly to the flat path structure
    - Polls for .response files at the same location
    - Uses in-memory tracking for pending futures

    Directory structure:
        {syftbox_folder}/{to_email}/app_data/{app_name}/rpc/{endpoint}/{sender}/*.request
        {syftbox_folder}/{to_email}/app_data/{app_name}/rpc/{endpoint}/{sender}/*.response
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
        self._pending_futures: dict[str, Path] = {}
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

        # Flat path: {syftbox_folder}/{to_email}/app_data/{app_name}/rpc/{endpoint}/{sender}/
        target_dir = (
            self._syftbox_folder
            / to_email
            / "app_data"
            / app_name
            / "rpc"
            / endpoint.lstrip("/")
            / self._sender_email
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        future_id = str(uuid.uuid4())
        request_path = target_dir / f"{future_id}.request"
        request_path.write_bytes(body)

        response_path = request_path.with_suffix(".response")
        self._pending_futures[future_id] = response_path

        logger.debug(f"Sent message to {to_email}, future_id={future_id}")
        return future_id

    def get_response(self, future_id: str) -> Optional[bytes]:
        response_path = self._pending_futures.get(future_id)
        if response_path is None:
            logger.warning(f"Unknown future_id: {future_id}")
            return None

        if response_path.exists():
            body = response_path.read_bytes()
            logger.debug(f"Got response for future_id={future_id}")
            return body

        return None

    def delete_future(self, future_id: str) -> None:
        response_path = self._pending_futures.pop(future_id, None)
        if response_path is not None:
            # Optionally clean up request/response files
            request_path = response_path.with_suffix(".request")
            if request_path.exists():
                request_path.unlink()
            if response_path.exists():
                response_path.unlink()
            logger.debug(f"Deleted future_id={future_id}")
