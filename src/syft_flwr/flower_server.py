import traceback
from random import randint

from flwr.common import Context
from flwr.server import ServerApp
from flwr.server.run_serverapp import run as run_server
from loguru import logger

from syft_flwr.grid import SyftGrid
from syft_flwr.utils import setup_client


def syftbox_flwr_server(
    server_app: ServerApp,
    context: Context,
    datasites: list[str],
    app_name: str,
) -> Context:
    """Run the Flower ServerApp with SyftBox."""
    client, _, syft_flwr_app_name = setup_client(app_name)

    # Construct the SyftGrid
    syft_grid = SyftGrid(
        app_name=syft_flwr_app_name, datasites=datasites, client=client
    )

    # Set the run id (random for now)
    run_id = randint(0, 1000)
    syft_grid.set_run(run_id)

    logger.info(f"Started SyftBox Flower Server on: {syft_grid._client.email}")
    logger.info(f"syft_flwr app name: {syft_flwr_app_name}")

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
        logger.error(f"Traceback: {traceback.format_exc()}")
        updated_context = context
    finally:
        syft_grid.send_stop_signal(group_id="final", reason="Server stopped")
        logger.info("Sending stop signals to the clients")

    return updated_context
