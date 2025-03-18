# stdlib
import argparse

from flwr.common import Context
from flwr.common.record import RecordSet
from flwr.common.typing import UserConfig
from flwr.server.run_serverapp import run as run_server
from loguru import logger
from syft_core import Client

from server_app import app as server_app
from syft_flwr.driver import SyftDriver

if __name__ == "__main__":
    # Get the config from the command line
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sb_conf_path",
        type=str,
        help="Path to the SyftBox configuration file",
        default="",
    )
    sb_conf_path = parser.parse_args().sb_conf_path
    sb_conf_path = "~/openmined/syft/.clients/a@openmined.org/config.json"

    sb_client = Client.load(sb_conf_path)
    logger.info(f"Started SyftBox Flower Server on: {sb_client.email}")

    run_id = 12345
    participants = ["b@openmined.org", "c@openmined.org"]

    syft_driver = SyftDriver(client=sb_client, datasites=participants)
    syft_driver.set_run(run_id)

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
        server_app_dir="./examples/basic",
    )
    logger.info(f"Updated context: {updated_context}")
