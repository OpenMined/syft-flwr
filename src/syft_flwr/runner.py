import argparse

from loguru import logger
from syft_core import Client

from syft_flwr.flower_client import syftbox_flwr_client
from syft_flwr.flower_server import syftbox_flwr_server
from syft_flwr.utils import read_toml_file, to_path
from syft_flwr.utils import load_server_app, load_client_app


def parse_arguments():
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--flower-toml-path",
        type=str,
        help="Path to the Flower pyproject TOML file",
        required=True,
    )
    parser.add_argument(
        "--sb-conf-path",
        type=str,
        help="Path to the SyftBox configuration file",
        default="",
    )
    parser.add_argument(
        "--aggregator",
        action="store_true",
        help="Flag to enable aggregator mode",
    )
    parser.add_argument(
        "--client",
        action="store_true",
        help="Flag to enable client mode",
    )
    
    return parser.parse_args()
    


if __name__ == "__main__":
    args = parse_arguments()

    flower_conf_path = args.flower_toml_path
    sb_conf_path = args.sb_conf_path
    if args.aggregator == args.client:
        raise ValueError("Either --aggregator or --client flag must be set")

    # Load the Flower configuration
    flower_conf_path = to_path(flower_conf_path)
    flower_project_dir = flower_conf_path.parent
    flower_conf = read_toml_file(flower_conf_path)
    syft_flower_conf = flower_conf["tool"]["syft_flwr"]
    logger.info(f"Flower Project Path: {flower_project_dir}")

    # Extract the datasites and aggregator
    datasites = syft_flower_conf["datasites"]
    aggregator = syft_flower_conf["aggregator"]
    logger.info(f"Aggregator: {aggregator}")
    logger.info(f"Datasites: {datasites}")

    # Load the SyftBox configuration
    sb_client = Client.load(sb_conf_path)
    sb_email = sb_client.email
    logger.info(f"Loading SyftBox Config Path: {sb_client.config_path}")

    if args.aggregator:
        if sb_email != aggregator:
            raise ValueError(
                f"SyftBox email: {sb_email} not same as aggregator: {aggregator} email in Flower configuration"
            )
        # Load the Server App
        server_app = load_server_app(flower_conf, flower_project_dir)
        syftbox_flwr_server(server_app, datasites, sb_client)

    if args.client:
        if sb_email not in datasites:
            raise ValueError(
                f"SyftBox email: {sb_email} not found in datasites: {datasites} in Flower configuration"
            )
        # Load the Client App
        client_app = load_client_app(flower_conf, flower_project_dir)
        syftbox_flwr_client(client_app, sb_client)
