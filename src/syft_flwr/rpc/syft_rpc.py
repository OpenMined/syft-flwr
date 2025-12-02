from __future__ import annotations

from typing import Optional

from loguru import logger
from syft_core import Client
from syft_rpc import rpc, rpc_db

from syft_flwr.rpc.protocol import SyftFlwrRpc


class SyftRpc(SyftFlwrRpc):
    """Adapter wrapping syft_rpc for traditional SyftBox.

    This adapter provides the full syft_rpc functionality including:
    - URL-based message routing
    - Futures database for response tracking
    - Optional encryption via syft_crypto
    """

    def __init__(self, client: Client, app_name: str) -> None:
        self._client = client
        self._app_name = app_name
        logger.debug(f"Initialized SyftRpc for {client.email}")

    def send(
        self,
        to_email: str,
        app_name: str,
        endpoint: str,
        body: bytes,
        encrypt: bool = False,
    ) -> str:
        url = rpc.make_url(to_email, app_name=app_name, endpoint=endpoint)
        future = rpc.send(
            url=url,
            body=body,
            client=self._client,
            encrypt=encrypt,
        )
        rpc_db.save_future(
            future=future,
            namespace=self._app_name,
            client=self._client,
        )
        logger.debug(f"Sent message to {to_email}, future_id={future.id}")
        return future.id

    def get_response(self, future_id: str) -> Optional[bytes]:
        future = rpc_db.get_future(future_id=future_id, client=self._client)
        if future is None:
            return None

        response = future.resolve()
        if response is not None:
            response.raise_for_status()  # Raise HTTPError if status code indicates failure
            logger.debug(f"Got response for future_id={future_id}")
            return response.body
        return None

    def delete_future(self, future_id: str) -> None:
        rpc_db.delete_future(future_id=future_id, client=self._client)
        logger.debug(f"Deleted future_id={future_id}")
