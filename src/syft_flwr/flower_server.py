from typing import Optional

from flwr.server.run_serverapp import run as run_server
from loguru import logger
from syft_core import Client

from syft_flwr.constant import RUN_ID
from syft_flwr.driver import SyftDriver
from syft_flwr.utils import create_context


def syftbox_flwr_server(server_app, datasites, sb_client: Optional[Client] = None):
    """Run the Flower ServerApp with SyftBox."""
    syft_driver = SyftDriver(datasites=datasites, client=sb_client)
    syft_driver.set_run(RUN_ID)
    logger.info(f"Started SyftBox Flower Server on: {syft_driver._client.email}")

    context = create_context(RUN_ID, 0)

    updated_context = run_server(
        driver=syft_driver,
        context=context,
        loaded_server_app=server_app,
        server_app_dir="",
    )
    logger.info(f"Server completed with context: {updated_context}")
    return updated_context
