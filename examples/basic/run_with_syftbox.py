import argparse
from pathlib import Path

from syft_core import Client

from examples.basic.client_app import ClientApp, client_fn
from examples.basic.server_app import ServerApp, server_fn
from syft_flwr.runner import syftbox_flwr_client, syftbox_flwr_server


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run a Flower client or server with SyftBox integration"
    )
    parser.add_argument(
        "--server", action="store_true", help="Run as a server (aggregator)"
    )
    parser.add_argument("--client", action="store_true", help="Run as a client")
    parser.add_argument(
        "--sb_conf_path",
        type=str,
        help="Path to the SyftBox configuration file",
        default="",
    )
    return parser.parse_args()


def get_syftbox_client(config_path):
    """Initialize and return a SyftBox client.

    Args:
        config_path: Path to the SyftBox configuration file

    Returns:
        A SyftBox client instance
    """
    if not config_path:
        raise ValueError("No SyftBox config path provided")
    config_path = Path(config_path).expanduser()
    return Client.load(str(config_path))


if __name__ == "__main__":
    args = parse_arguments()

    sb_client = get_syftbox_client(args.sb_conf_path)

    if args.server:
        server_app = ServerApp(server_fn=server_fn)
        syftbox_flwr_server(
            server_app,
            datasites=["b@openmined.org", "c@openmined.org"],
            sb_client=sb_client,
        )

    if args.client:
        client_app = ClientApp(client_fn=client_fn)
        syftbox_flwr_client(client_app, sb_client)
