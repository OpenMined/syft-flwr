import argparse

from examples.quickstart.quickstart.client_app import ClientApp, client_fn
from examples.quickstart.quickstart.server_app import ServerApp, server_fn
from syft_flwr.runner import syftbox_flwr_client, syftbox_flwr_server

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--client", action="store_true")
    args = parser.parse_args()

    if args.server:
        server_app = ServerApp(server_fn=server_fn)
        syftbox_flwr_server(
            server_app, datasites=["khoa@openmined.org", "rasswanth@openmined.org"]
        )

    if args.client:
        client_app = ClientApp(client_fn=client_fn)
        syftbox_flwr_client(client_app, "khoa@openmined.org")
