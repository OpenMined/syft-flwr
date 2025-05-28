"""fltabular: Flower Example on Adult Census Income Tabular Dataset."""

from flwr.common import Context, ndarrays_to_parameters
from flwr.server import ServerApp, ServerAppComponents, ServerConfig

from fl_diabetes_prediction.task import Net, get_weights


def weighted_average(metrics):
    accuracies = [num_examples * m["accuracy"] for num_examples, m in metrics]
    examples = [num_examples for num_examples, _ in metrics]

    return {"accuracy": sum(accuracies) / sum(examples)}


def server_fn(context: Context) -> ServerAppComponents:
    net = Net()
    params = ndarrays_to_parameters(get_weights(net))

    from pathlib import Path

    from syft_flwr.strategy import FedAvgWithModelSaving

    strategy = FedAvgWithModelSaving(
        save_path=Path(__file__).parent.parent.parent / "weights",
        fraction_fit=1.0,
        fraction_evaluate=1.0,
        min_available_clients=2,
        initial_parameters=params,
        evaluate_metrics_aggregation_fn=weighted_average,
    )
    num_rounds = context.run_config["num-server-rounds"]
    config = ServerConfig(num_rounds=num_rounds)

    return ServerAppComponents(config=config, strategy=strategy)


app = ServerApp(server_fn=server_fn)
