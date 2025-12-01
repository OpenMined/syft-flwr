import os
from typing import Optional

from loguru import logger

from syft_flwr.client.protocol import SyftFlwrClient
from syft_flwr.client.syft_core_client import SyftCoreClient
from syft_flwr.client.syft_p2p_client import SyftP2PClient


def create_client(
    client_type: Optional[str] = None,
    **kwargs,
) -> SyftFlwrClient:
    """Factory function to create the appropriate client:
    - If SYFTBOX_EMAIL and SYFTBOX_FOLDER are set -> syft_client (P2P communication)
    - Otherwise -> syft_core (traditional SyftBox)
    """
    # Auto-detect from environment if not specified
    if client_type is None:
        # If SYFTBOX_EMAIL is set, we're running as a job via syft_client
        if os.getenv("SYFTBOX_EMAIL") and os.getenv("SYFTBOX_FOLDER"):
            client_type = "syft_client"
        else:
            client_type = "syft_core"

    if client_type == "syft_core":
        logger.info("Creating SyftCoreClient from config file")
        return SyftCoreClient.load(kwargs.get("filepath"))
    elif client_type == "syft_client":
        logger.info("Creating SyftP2PClient from environment")
        return SyftP2PClient.from_env()
    else:
        raise ValueError(f"Unknown client type: {client_type}")
