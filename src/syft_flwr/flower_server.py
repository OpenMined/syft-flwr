from flwr.common import Context
from flwr.server import ServerApp
from flwr.server.run_serverapp import run as run_server
from loguru import logger
from syft_core import Client

from syft_flwr.constant import RUN_ID
from syft_flwr.driver import SyftDriver


def syftbox_flwr_server(
    server_app: ServerApp, datasites, sb_client: Client, context: Context
):
    """Run the Flower ServerApp with SyftBox."""
    syft_driver = SyftDriver(datasites=datasites, client=sb_client)
    syft_driver.set_run(RUN_ID)
    logger.info(f"Started SyftBox Flower Server on: {syft_driver._client.email}")

    updated_context = run_server(
        driver=syft_driver,
        context=context,
        loaded_server_app=server_app,
        server_app_dir="",
    )
    logger.info(f"Server completed with context: {updated_context}")
    return updated_context
