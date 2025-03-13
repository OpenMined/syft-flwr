from syft_flwr.driver import SyftDriver
from flwr.common.typing import Run, UserConfig
from flwr.server.run_serverapp import run as run_server
from flwr.common.context import Context
from flwr.common.record import RecordSet
from flwr.common import Context, ndarrays_to_parameters
from flwr.server import ServerApp, ServerAppComponents, ServerConfig
from flwr.server.strategy import FedAvg

import numpy as np


def get_dummy_model():
    return np.ones((1, 1))


def server_fn(context: Context):
    # Read from config
    num_rounds = context.run_config.get("num-server-rounds", 2)

    # Initial model
    model = get_dummy_model()
    dummy_parameters = ndarrays_to_parameters([model])

    # Define strategy
    strategy = FedAvg(initial_parameters=dummy_parameters)
    config = ServerConfig(num_rounds=num_rounds)

    return ServerAppComponents(strategy=strategy, config=config)


if __name__ == "__main__":
    # Create ServerApp
    app = ServerApp(server_fn=server_fn)

    run = Run.create_empty(run_id=1234)
    syft_driver = SyftDriver()
    syft_driver.set_run(run)

    context = Context(
        run_id=run.run_id,
        node_id=0,
        node_config=UserConfig(),
        state=RecordSet(),
        run_config=UserConfig(),
    )

    updated_context = run_server(
        driver = syft_driver,
        context = context,
        loaded_server_app =app ,
        server_app_dir="./examples/quickstart"
    )