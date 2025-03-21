import argparse
from pathlib import Path

from syft_flwr.run import syftbox_run_flwr_client, syftbox_run_flwr_server


def parse_arguments():
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--flower-project-dir",
        type=str,
        help="Path to the Flower project directory",
        required=True,
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Flag to enable server mode",
    )
    parser.add_argument(
        "--client",
        action="store_true",
        help="Flag to enable client mode",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    if args.server:
        syftbox_run_flwr_server(Path(args.flower_project_dir))
    if args.client:
        syftbox_run_flwr_client(Path(args.flower_project_dir))
