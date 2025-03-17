import numpy as np
from flwr.common import Context, ndarrays_to_parameters
from flwr.common.record import RecordSet
from flwr.common.typing import UserConfig
from flwr.server import ServerApp, ServerAppComponents, ServerConfig
from flwr.server.run_serverapp import run as run_server
from flwr.server.strategy import FedAvg
from loguru import logger

from syft_flwr.driver import SyftDriver


def get_dummy_model():
    return np.random.rand(10, 10)


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
    server_app = ServerApp(server_fn=server_fn)

    run_id = 12345
    participants = ["rasswanth@openmined.org", "khoa@openmined.org"]

    syft_driver = SyftDriver(datasites=participants)
    syft_driver.set_run(run_id)

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
        server_app_dir="./examples/basic",
    )
    logger.info(f"Updated context: {updated_context}")
