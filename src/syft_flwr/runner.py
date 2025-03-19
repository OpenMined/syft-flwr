import argparse
from pathlib import Path
from typing import Optional

import tomllib
from flwr.client.client_app import LoadClientAppError
from flwr.common import Context
from flwr.common.message import Message
from flwr.common.object_ref import load_app
from flwr.common.record import RecordSet
from flwr.common.typing import UserConfig
from flwr.server.run_serverapp import run as run_server
from flwr.server.server_app import LoadServerAppError
from loguru import logger
from syft_core import Client
from syft_event import SyftEvents
from syft_event.types import Request

from syft_flwr.driver import SyftDriver
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes


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


def syftbox_flwr_client(client_app, sb_client: Optional[Client] = None):
    """Run the Flower ClientApp with SyftBox."""

    box = SyftEvents("flwr", client=sb_client)
    logger.info(f"Started SyftBox Flower Client on: {box.client.email}")

    @box.on_request("/messages")
    def handle_messages(request: Request) -> None:
        logger.info(
            f"Received request id: {request.id}, size: {len(request.body)} bytes"
        )
        message: Message = bytes_to_flower_message(request.body)
        run_id = 12345  # same as server
        context = Context(
            run_id=run_id,
            node_id=0,
            node_config=UserConfig(),
            state=RecordSet(),
            run_config=UserConfig(),
        )

        reply_message: Message = client_app(message=message, context=context)
        res_bytes: bytes = flower_message_to_bytes(reply_message)
        logger.info(f"Reply message size: {len(res_bytes)/2**20} MB")
        return res_bytes

    box.run_forever()


def read_toml_file(filename):
    with open(filename, "rb") as file:
        data = tomllib.load(file)
    return data


def load_app_from_path(path: str):
    module_path, variable_name = path.split(":")
    module_path = str(Path(module_path).expanduser())
    module = __import__(module_path, fromlist=[variable_name])
    return getattr(module, variable_name)


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--syft-flower-conf-path",
        type=str,
        help="Path to the Syft Flower Configuration TOML file",
    )
    parser.add_argument(
        "--sb-conf-path",
        type=str,
        help="Path to the SyftBox configuration file",
        default="",
    )

    args = parser.parse_args()
    # flower_conf_path = args.flower_conf_path
    syft_flower_conf_path = (
        "/Users/rasswanths/openmined/flwr/src/syft_flwr/syft_conf.toml"
    )
    # sb_conf_path = args.sb_conf_path
    sb_conf_path = (
        "/Users/rasswanths/openmined/syft/.clients/b@openmined.org/config.json"
    )

    # Load the Flower configuration
    syft_flower_conf = read_toml_file(syft_flower_conf_path)
    datasites = syft_flower_conf["config"]["datasites"]
    aggregator = syft_flower_conf["config"]["aggregator"]

    logger.info(f"Aggregator: {aggregator}")
    logger.info(f"Datasites: {datasites}")

    # Load the SyftBox configuration
    sb_client = Client.load(sb_conf_path)
    sb_email = sb_client.email
    logger.info(f"Loading SyftBox Config Path: {sb_client.config_path}")

    if sb_email not in datasites + [aggregator]:
        raise ValueError(
            f"SyftBox client: {sb_email} not in Flower Config Datasites: {datasites}"
        )

    flower_project_dir = Path(syft_flower_conf["flower"]["project_dir"])
    logger.info(f"Flower Project Path: {flower_project_dir}")
    flower_conf = read_toml_file(flower_project_dir / "pyproject.toml")

    if sb_email == aggregator:
        # Load the Server App

        server_app_path = flower_conf["tool"]["flwr"]["app"]["components"]["serverapp"]
        server_app = load_app(server_app_path, LoadServerAppError, flower_project_dir)
        print(server_app)
    else:
        # Load the Client App
        client_app_path = flower_conf["tool"]["flwr"]["app"]["components"]["clientapp"]
        client_app = load_app(client_app_path, LoadClientAppError, flower_project_dir)
        print(client_app)
