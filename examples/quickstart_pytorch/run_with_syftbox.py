from examples.basic.run_with_syftbox import (
    get_syftbox_client,
    parse_arguments,
)
from examples.quickstart_pytorch.pytorch.client_app import app as client_app
from examples.quickstart_pytorch.pytorch.server_app import app as server_app
from syft_flwr.runner import syftbox_flwr_client, syftbox_flwr_server

if __name__ == "__main__":
    args = parse_arguments()
    sb_client = get_syftbox_client(args.sb_conf_path)
    if args.server:
        syftbox_flwr_server(
            server_app,
            datasites=["b@openmined.org", "c@openmined.org"],
            sb_client=sb_client,
        )
    if args.client:
        syftbox_flwr_client(client_app, sb_client=sb_client)
