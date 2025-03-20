import argparse

from loguru import logger
from syft_core import Client

from syft_flwr.constant import RUN_ID
from syft_flwr.flower_client import syftbox_flwr_client
from syft_flwr.flower_server import syftbox_flwr_server
from syft_flwr.utils import (
    create_context,
    load_client_app,
    load_server_app,
    read_toml_file,
    to_path,
)


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


def flower_configs(flower_conf_path):
    # Load the Flower configuration
    flower_conf_path = to_path(flower_conf_path)
    flower_project_dir = flower_conf_path.parent
    flower_conf = read_toml_file(flower_conf_path)

    syft_flower_conf = flower_conf["tool"]["syft_flwr"]
    logger.info(f"Flower Project Path: {flower_project_dir}")

    # TODO: Install dependencies here?
    dependencies = flower_conf["project"]["dependencies"]
    logger.info(f"Extra dependencies needed: {dependencies}")

    # Extract the datasites and aggregator
    datasites = syft_flower_conf["datasites"]
    aggregator = syft_flower_conf["aggregator"]
    logger.info(f"Aggregator: {aggregator}")
    logger.info(f"Datasites: {datasites}")

    # Load the Flower app configuration
    flower_app_config = flower_conf["tool"]["flwr"]["app"]["config"]

    return {
        "flower_project_dir": flower_project_dir,
        "flower_conf": flower_conf,
        "syft_flower_conf": syft_flower_conf,
        "flower_app_config": flower_app_config,
    }


if __name__ == "__main__":
    args = parse_arguments()

    flower_conf_path = args.flower_toml_path
    sb_conf_path = args.sb_conf_path
    if args.aggregator == args.client:
        raise ValueError("Either --aggregator or --client flag must be set")

    # Load the SyftBox client
    sb_client = Client.load(sb_conf_path)
    sb_email = sb_client.email
    logger.info(f"Loading SyftBox Config Path: {sb_client.config_path}")

    # Load the Flower and Syft-FLWR configurations
    configs = flower_configs(flower_conf_path)
    syft_flower_conf = configs["syft_flower_conf"]
    datasites = syft_flower_conf["datasites"]
    flower_context = create_context(
        run_id=RUN_ID,
        node_id=0,
        node_config=configs["flower_app_config"],
        run_config=configs["flower_app_config"],
    )

    if args.aggregator:
        aggregator_email = syft_flower_conf["aggregator"]
        if sb_email != aggregator_email:
            raise ValueError(
                f"SyftBox email: {sb_email} not same as aggregator: {aggregator_email} email in Flower configuration"
            )
        server_app = load_server_app(
            configs["flower_conf"], configs["flower_project_dir"]
        )
        syftbox_flwr_server(server_app, datasites, sb_client, flower_context)

    if args.client:
        if sb_email not in datasites:
            raise ValueError(
                f"SyftBox email: {sb_email} not found in datasites: {datasites} in Flower configuration"
            )
        client_app = load_client_app(
            configs["flower_conf"], configs["flower_project_dir"]
        )
        syftbox_flwr_client(client_app, sb_client, flower_context)
