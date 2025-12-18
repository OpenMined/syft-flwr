from __future__ import annotations

import uuid
from typing import Optional

from loguru import logger

from syft_flwr.gdrive_io import GDriveFileIO
from syft_flwr.rpc.protocol import SyftFlwrRpc


class P2PFileRpc(SyftFlwrRpc):
    """P2P File-based RPC adapter using Google Drive API via syft-client.

    Instead of using filesystem paths, this adapter uses GDriveFileIO to:
    - Write .request files to the shared outbox folder via Google Drive API
    - Poll for .response files in the inbox folder via Google Drive API
    - Uses in-memory tracking for pending futures

    Directory structure in Google Drive:
        SyftBox/syft_outbox_inbox_{sender}_to_{recipient}/{app_name}/rpc/{endpoint}/*.request
        SyftBox/syft_outbox_inbox_{recipient}_to_{sender}/{app_name}/rpc/{endpoint}/*.response
    """

    def __init__(
        self,
        sender_email: str,
        app_name: str,
    ) -> None:
        self._sender_email = sender_email
        self._app_name = app_name
        self._gdrive_io = GDriveFileIO(email=sender_email)
        self._pending_futures: dict[
            str, tuple[str, str, str]
        ] = {}  # future_id -> (recipient, app_name, endpoint)
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
                "Encryption not supported in P2PFileRpc, sending unencrypted"
            )

        future_id = str(uuid.uuid4())
        filename = f"{future_id}.request"

        # Write request to outbox via Google Drive API
        self._gdrive_io.write_to_outbox(
            recipient_email=to_email,
            app_name=app_name,
            endpoint=endpoint.lstrip("/"),
            filename=filename,
            data=body,
        )

        # Track pending future for response polling
        self._pending_futures[future_id] = (to_email, app_name, endpoint.lstrip("/"))

        logger.debug(f"Sent message to {to_email}, future_id={future_id}")
        return future_id

    def get_response(self, future_id: str) -> Optional[bytes]:
        future_data = self._pending_futures.get(future_id)
        if future_data is None:
            logger.warning(f"Unknown future_id: {future_id}")
            return None

        recipient, app_name, endpoint = future_data
        filename = f"{future_id}.response"

        # Response comes from recipient's outbox (which is our inbox)
        body = self._gdrive_io.read_from_inbox(
            sender_email=recipient,
            app_name=app_name,
            endpoint=endpoint,
            filename=filename,
        )

        if body is not None:
            logger.debug(f"Got response for future_id={future_id}")

        return body

    def delete_future(self, future_id: str) -> None:
        # Only clear in-memory tracking
        # Response files are owned by DO and cannot be deleted by DS
        if self._pending_futures.pop(future_id, None) is not None:
            logger.debug(f"Cleared future_id={future_id} from tracking")
