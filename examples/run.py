from quickstart.quickstart.client_app import app as client_app
from quickstart.quickstart.server_app import app as server_app

from syft_flwr.server import run_simulation as custom_run_simulation


def run():
    NUM_CLIENTS = 3
    backend_config = {"client_resources": {"num_cpus": 1, "num_gpus": 0.0}}

    # run_simulation(
    #     server_app=server_app,
    #     client_app=client_app,
    #     num_supernodes=NUM_CLIENTS,
    #     backend_config=backend_config,
    # )
    custom_run_simulation(
        server_app=server_app,
        client_app=client_app,
        num_supernodes=NUM_CLIENTS,
        backend_config=backend_config,
    )


if __name__ == "__main__":
    run()
