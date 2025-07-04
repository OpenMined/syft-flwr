"""quickstart-pytorch: A Flower / PyTorch app."""

from flwr.common import Context, ndarrays_to_parameters
from flwr.server import ServerApp, ServerAppComponents, ServerConfig

from quickstart_pytorch.task import Net, get_weights


def server_fn(context: Context):
    # Read from config
    num_rounds = context.run_config["num-server-rounds"]
    fraction_fit = context.run_config["fraction-fit"]

    # Initialize model parameters
    ndarrays = get_weights(Net())
    parameters = ndarrays_to_parameters(ndarrays)

    # Define strategy
    from pathlib import Path

    from syft_flwr.strategy import FedAvgWithModelSaving

    # Define strategy
    strategy = FedAvgWithModelSaving(
        save_path=Path(__file__).parent.parent.parent / "weights",
        fraction_fit=fraction_fit,
        fraction_evaluate=fraction_fit,
        min_available_clients=2,
        initial_parameters=parameters,
    )
    config = ServerConfig(num_rounds=num_rounds)

    return ServerAppComponents(strategy=strategy, config=config)


# Create ServerApp
app = ServerApp(server_fn=server_fn)
