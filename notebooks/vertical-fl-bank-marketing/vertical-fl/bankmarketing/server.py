import torch.nn as nn

from pathlib import Path

from flwr.common import Context, ndarrays_to_parameters
from flwr.server import ServerApp, ServerAppComponents, ServerConfig

from .model import SimpleMLP
from .utils import get_parameters


class ServerModel(nn.Module):
    def __init__(self, input_size):
        super(ServerModel, self).__init__()
        self.fc1 = nn.Linear(input_size, 1)

    def forward(self, x):
        x = self.fc1(x)
        return x


def weighted_average(metrics):
    accuracies = [num_examples * m["accuracy"] for num_examples, m in metrics]
    examples = [num_examples for num_examples, _ in metrics]

    return {"accuracy": sum(accuracies) / sum(examples)}


def server_fn(context: Context) -> ServerAppComponents:
    net = SimpleMLP((51, ), [1], 1, nn.ReLU)  # TODO: temporary fix
    params = ndarrays_to_parameters(get_parameters(net))

    from .strategy import AggregateCustomMetricStrategy
    from .utils import load_syftbox_dataset
    
    _, y_train, _, _ = load_syftbox_dataset(0)

    strategy = AggregateCustomMetricStrategy(
        labels=y_train,
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
