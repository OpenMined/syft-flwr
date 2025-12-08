"""FL Orchestrator module for syft_flwr.

This module contains the server-side FL orchestration components:
- SyftGrid: Message orchestrator for FL communication
- syftbox_flwr_server: Server-side FL runner
- syftbox_flwr_client: Client-side FL runner
"""

from syft_flwr.fl_orchestrator.flower_client import (
    MessageHandler,
    RequestProcessor,
    syftbox_flwr_client,
)
from syft_flwr.fl_orchestrator.flower_server import syftbox_flwr_server
from syft_flwr.fl_orchestrator.syft_grid import SyftGrid

__all__ = [
    # Grid
    "SyftGrid",
    # Server
    "syftbox_flwr_server",
    # Client
    "syftbox_flwr_client",
    "MessageHandler",
    "RequestProcessor",
]
