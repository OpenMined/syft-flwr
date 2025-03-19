from typing import Optional

from flwr.common import Context
from flwr.common.record import RecordSet
from flwr.common.typing import UserConfig
from flwr.server.run_serverapp import run as run_server
from loguru import logger
from syft_core import Client

from syft_flwr.driver import SyftDriver


def syftbox_flwr_server(server_app, datasites, sb_client: Optional[Client] = None):
    """Run the Flower ServerApp with SyftBox."""
    run_id = 12345
    syft_driver = SyftDriver(datasites=datasites, client=sb_client)
    syft_driver.set_run(run_id)
    logger.info(f"Started SyftBox Flower Server on: {syft_driver._client.email}")

    context = Context(
        run_id=run_id,
        node_id=0,
        node_config=UserConfig(),
        state=RecordSet(),
        run_config=UserConfig(),
    )

    updated_context = run_server(
        driver=syft_driver,
        context=context,
        loaded_server_app=server_app,
        server_app_dir="",
    )
    logger.info(f"Server completed with context: {updated_context}")
    return updated_context
