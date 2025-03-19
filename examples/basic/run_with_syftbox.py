import argparse

from loguru import logger
from syft_core import Client

from examples.basic.client_app import ClientApp, client_fn
from examples.basic.server_app import ServerApp, server_fn
from syft_flwr.runner import syftbox_flwr_client, syftbox_flwr_server

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--client", action="store_true")
    parser.add_argument(
        "--sb_conf_path",
        type=str,
        help="Path to the SyftBox configuration file",
        default="",
    )
    args = parser.parse_args()

    is_aggregator = args.server
    is_client = args.client

    sb_conf_path = parser.parse_args().sb_conf_path
    if not sb_conf_path:
        logger.warning("No SyftBox config path provided, using default")
        sb_conf_path = "~/openmined/syft/.clients/a@openmined.org/config.json"
    sb_client = Client.load(sb_conf_path)

    if is_aggregator:
        server_app = ServerApp(server_fn=server_fn)
        syftbox_flwr_server(
            server_app,
            datasites=["b@openmined.org", "c@openmined.org"],
            sb_client=sb_client,
        )

    if is_client:
        client_app = ClientApp(client_fn=client_fn)
        syftbox_flwr_client(client_app, sb_client)
