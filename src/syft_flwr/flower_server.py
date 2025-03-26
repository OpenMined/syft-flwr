from flwr.common import Context
from flwr.server import ServerApp
from flwr.server.run_serverapp import run as run_server
from loguru import logger

from syft_flwr.constant import RUN_ID
from syft_flwr.grid import SyftGrid


def syftbox_flwr_server(server_app: ServerApp, context: Context, datasites: list[str]):
    """Run the Flower ServerApp with SyftBox."""
    syft_grid = SyftGrid(datasites=datasites)
    syft_grid.set_run(RUN_ID)
    logger.info(f"Started SyftBox Flower Server on: {syft_grid._client.email}")

    updated_context = run_server(
        grid=syft_grid,
        context=context,
        loaded_server_app=server_app,
        server_app_dir="",
    )
    logger.info(f"Server completed with context: {updated_context}")
    return updated_context
