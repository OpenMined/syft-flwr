import os
from typing import Optional

from .protocol import SyftFlwrClient
from .syft_core_adapter import SyftCoreClientAdapter


def create_client(
    client_type: Optional[str] = None,
    **kwargs,
) -> SyftFlwrClient:
    """Factory function to create the appropriate client.

    Auto-detection logic:
    - If SYFTBOX_EMAIL and SYFTBOX_FOLDER are set -> syft_client (running as job)
    - Otherwise -> syft_core (traditional SyftBox)

    Args:
        client_type: Explicit type ("syft_core", "syft_client") or None for auto-detect
        **kwargs: Additional arguments for client creation
            - filepath: Config file path for syft_core

    Returns:
        SyftFlwrClient instance

    Example:
        # Auto-detect (most common)
        client = create_client()

        # Explicit type
        client = create_client("syft_core", filepath="/path/to/config.json")
    """
    # Auto-detect from environment if not specified
    if client_type is None:
        # If SYFTBOX_EMAIL is set, we're running as a job via syft_client
        if os.getenv("SYFTBOX_EMAIL") and os.getenv("SYFTBOX_FOLDER"):
            client_type = "syft_client"
        else:
            client_type = "syft_core"

    if client_type == "syft_core":
        return SyftCoreClientAdapter.load(kwargs.get("filepath"))
    elif client_type == "syft_client":
        from .syft_client_adapter import SyftClientAdapter

        return SyftClientAdapter.from_env()
    else:
        raise ValueError(f"Unknown client type: {client_type}")
