from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from loguru import logger
from syft_core import Client as SyftCoreNativeClient

from syft_flwr.client.factory import create_client as create_flwr_client
from syft_flwr.client.protocol import SyftFlwrClient
from syft_flwr.client.syft_p2p_client import SyftP2PClient
from syft_flwr.events.protocol import SyftFlwrEvents

if TYPE_CHECKING:
    from syft_core import Client


def create_events_watcher(
    app_name: str,
    client: Optional[Union[Client, SyftFlwrClient]] = None,
    cleanup_expiry: str = "1d",
    cleanup_interval: str = "1d",
    poll_interval: float = 2.0,
) -> SyftFlwrEvents:
    """Factory function to create the appropriate events adapter.

    Auto-detection logic:
    - If client has get_client() returning syft_core.Client -> SyftEvents
    - If client has get_client() returning SyftP2PClient -> P2PFileEvents

    Args:
        app_name: Name of the FL app (e.g., "flwr/my_app")
        client: SyftFlwrClient or syft_core.Client instance (auto-created if None)
        cleanup_expiry: Expiry time for cleanup (SyftEvents only)
        cleanup_interval: Cleanup interval (SyftEvents only)
        poll_interval: Polling interval in seconds (P2PFileEvents only)

    Returns:
        SyftFlwrEvents instance (either SyftEvents or P2PFileEvents)
    """
    # Auto-create client if not provided
    if client is None:
        flwr_client = create_flwr_client()
    elif isinstance(client, SyftFlwrClient):
        flwr_client = client
    else:
        # Direct syft_core.Client passed - wrap it
        from syft_flwr.client.syft_core_client import SyftCoreClient

        flwr_client = SyftCoreClient(client)

    native_client = flwr_client.get_client()

    if isinstance(native_client, SyftCoreNativeClient):
        # syft_core path - use SyftEvents
        from syft_flwr.events.syft_events import SyftEvents

        logger.debug("Creating SyftEvents (syft_core path)")
        return SyftEvents(
            app_name=app_name,
            client=native_client,
            cleanup_expiry=cleanup_expiry,
            cleanup_interval=cleanup_interval,
        )
    elif isinstance(native_client, SyftP2PClient):
        # syft_client path - use P2PFileEvents
        from syft_flwr.events.p2p_fle_events import P2PFileEvents

        logger.debug("Creating P2PFileEvents (syft_client path)")
        return P2PFileEvents(
            app_name=app_name,
            client_email=flwr_client.email,
            poll_interval=poll_interval,
        )
    else:
        raise TypeError(f"Unknown client type: {type(native_client)}")
