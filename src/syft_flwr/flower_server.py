from random import randint

from flwr.common import Context
from flwr.server import ServerApp
from flwr.server.run_serverapp import run as run_server
from loguru import logger

from syft_flwr.grid import SyftGrid


def syftbox_flwr_server(server_app: ServerApp, context: Context, datasites: list[str]):
    """Run the Flower ServerApp with SyftBox."""
    syft_grid = SyftGrid(datasites=datasites)
    run_id = randint(0, 1000)
    syft_grid.set_run(run_id)
    logger.info(f"Started SyftBox Flower Server on: {syft_grid._client.email}")

    try:
        updated_context = run_server(
            syft_grid,
            context=context,
            loaded_server_app=server_app,
            server_app_dir="",
        )
        logger.info(f"Server completed with context: {updated_context}")
    except Exception as e:
        logger.error(f"Server encountered an error: {str(e)}")
        updated_context = context
    finally:
        syft_grid.send_stop_signal(group_id="final", reason="Server stopped")
        logger.info("Sending stop signals to the clients")

    return updated_context
