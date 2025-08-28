import os
import traceback
from random import randint

from flwr.common import Context
from flwr.server import ServerApp
from flwr.server.run_serverapp import run as run_server
from loguru import logger
from syft_core import Client
from syft_crypto.x3dh_bootstrap import ensure_bootstrap

from syft_flwr.consts import SYFT_FLWR_ENCRYPTION_ENABLED
from syft_flwr.grid import SyftGrid


def syftbox_flwr_server(
    server_app: ServerApp,
    context: Context,
    datasites: list[str],
    app_name: str,
) -> Context:
    """Run the Flower ServerApp with SyftBox."""
    syft_flwr_app_name = f"flwr/{app_name}"

    # Bootstrap X3DH encryption keys for the server (if encryption is enabled)
    client = Client.load()
    encryption_enabled = (
        os.environ.get(SYFT_FLWR_ENCRYPTION_ENABLED, "true").lower() != "false"
    )
    if encryption_enabled:
        client = ensure_bootstrap(client)
    else:
        logger.warning("⚠️ Encryption disabled - skipping server key bootstrap")

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
