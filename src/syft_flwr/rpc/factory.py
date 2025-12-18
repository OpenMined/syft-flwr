from __future__ import annotations

from loguru import logger
from syft_core import Client as SyftCoreNativeClient

from syft_flwr.client.protocol import SyftFlwrClient
from syft_flwr.client.syft_p2p_client import SyftP2PClient
from syft_flwr.rpc.p2p_file_rpc import P2PFileRpc
from syft_flwr.rpc.protocol import SyftFlwrRpc
from syft_flwr.rpc.syft_rpc import SyftRpc


def create_rpc(
    client: SyftFlwrClient,
    app_name: str,
) -> SyftFlwrRpc:
    """Create the appropriate RPC adapter based on client type.

    Args:
        client: SyftFlwrClient instance
        app_name: Name of the FL application

    Returns:
        SyftFlwrRpc instance (SyftRpc or P2PFileRpc)

    Note:
        - syft_core path: get_client() returns syft_core.Client
        - syft_client path: get_client() returns SyftP2PClient (file-based RPC)
    """
    native_client = client.get_client()

    if isinstance(native_client, SyftCoreNativeClient):
        logger.debug("Creating SyftRpc (syft_core path)")
        return SyftRpc(client=native_client, app_name=app_name)
    elif isinstance(native_client, SyftP2PClient):
        logger.debug("Creating P2PFileRpc (syft_client path)")
        return P2PFileRpc(
            sender_email=client.email,
            app_name=app_name,
        )
    else:
        raise TypeError(f"Unknown client type: {type(native_client)}")
