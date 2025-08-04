from pathlib import Path

import torch.nn as nn
from flwr.common import Context, ndarrays_to_parameters
from flwr.server import ServerApp, ServerAppComponents, ServerConfig

from .model import SimpleMLP
from .utils import get_parameters


class ServerModel(nn.Module):
    def __init__(self, input_size):
        super(ServerModel, self).__init__()
        self.fc1 = nn.Linear(input_size, 1)

    def forward(self, x):
        print(f"[ServerModel] Input shape: {x.shape}")
        x = self.fc1(x)
        print(f"[ServerModel] Output shape: {x.shape}")
        return x


def weighted_average(metrics):
    accuracies = [num_examples * m["accuracy"] for num_examples, m in metrics]
    examples = [num_examples for num_examples, _ in metrics]

    return {"accuracy": sum(accuracies) / sum(examples)}


def server_fn(context: Context) -> ServerAppComponents:
    net = SimpleMLP((51,), [1], 1, nn.ReLU)  # TODO: temporary fix
    params = ndarrays_to_parameters(get_parameters(net))

    from .strategy import AggregateCustomMetricStrategy
    from .utils import load_server_training_labels

    # Load server's training labels (same samples as clients)
    y_train = load_server_training_labels()

    strategy = AggregateCustomMetricStrategy(
        labels=y_train,
        save_path=Path(__file__).parent.parent.parent / "weights",
        client_embedding_sizes=[2, 2],  # Each client contributes 2D embeddings
        fraction_fit=1.0,  # Use 100% of available clients
        fraction_evaluate=1.0,  # Use 100% for evaluation
        min_fit_clients=2,  # Must have exactly 2 clients
        min_available_clients=2,  # Wait until 2 clients are available
        accept_failures=False,  # Critical: do not proceed with failures for VFL
        initial_parameters=params,
        evaluate_metrics_aggregation_fn=weighted_average,
    )

    num_rounds = context.run_config["num-server-rounds"]
    config = ServerConfig(
        num_rounds=num_rounds,
        round_timeout=120.0,  # 2 minute timeout per round
    )

    return ServerAppComponents(config=config, strategy=strategy)


app = ServerApp(server_fn=server_fn)
