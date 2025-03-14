"""pytorch: A Flower / PyTorch app."""

from flwr.common import Context, ndarrays_to_parameters
from flwr.server import ServerApp, ServerAppComponents, ServerConfig
from flwr.server.run_serverapp import run as run_server
from flwr.server.strategy import FedAvg
from loguru import logger

from syft_flwr.driver import SyftDriver
from syft_flwr.utils import create_empty_context

from .task import Net, get_weights


def server_fn(context: Context):
    # Read from config
    num_rounds = context.run_config.get("num-server-rounds", 3)
    fraction_fit = context.run_config.get("fraction-fit", 0.5)

    # Initialize model parameters
    ndarrays = get_weights(Net())
    parameters = ndarrays_to_parameters(ndarrays)

    # Define strategy
    strategy = FedAvg(
        fraction_fit=fraction_fit,
        fraction_evaluate=1.0,
        min_available_clients=2,
        initial_parameters=parameters,
    )
    config = ServerConfig(num_rounds=num_rounds)

    return ServerAppComponents(strategy=strategy, config=config)


if __name__ == "__main__":
    # Create ServerApp
    server_app = ServerApp(server_fn=server_fn)

    run_id = 2
    syft_driver = SyftDriver()
    syft_driver.set_run(run_id)
    context = create_empty_context(run_id=run_id)

    updated_context = run_server(
        driver=syft_driver,
        context=context,
        loaded_server_app=server_app,
        server_app_dir="./examples/quickstart-pytorch-syft/pytorch",
    )
    logger.info(f"Updated context: {updated_context}")
