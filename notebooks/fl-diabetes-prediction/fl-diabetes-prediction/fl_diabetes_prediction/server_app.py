"""fltabular: Flower Example on Adult Census Income Tabular Dataset."""

from flwr.common import Context, ndarrays_to_parameters
from flwr.server import ServerApp, ServerAppComponents, ServerConfig

from fl_diabetes_prediction.task import Net, get_weights


def weighted_average(metrics):
    print("\n" + "⚖" * 80)
    print("📊 AGGREGATING METRICS")
    print(f"   Number of clients: {len(metrics)}")
    print("⚖" * 80)
    accuracies = [num_examples * m["accuracy"] for num_examples, m in metrics]
    examples = [num_examples for num_examples, _ in metrics]

    avg_accuracy = sum(accuracies) / sum(examples)
    print(f"✅ AGGREGATION COMPLETE - Average Accuracy: {avg_accuracy:.4f}\n")
    return {"accuracy": avg_accuracy}


def server_fn(context: Context) -> ServerAppComponents:
    print("\n" + "█" * 80)
    print("🚀 SERVER FUNCTION STARTED")
    print(f"📋 Run Config: {context.run_config}")
    print("█" * 80 + "\n")

    net = Net()
    params = ndarrays_to_parameters(get_weights(net))

    from pathlib import Path

    from syft_flwr.strategy import FedAvgWithModelSaving

    save_path = Path(__file__).parent.parent.parent / "weights"
    print("⚙️ CONFIGURING STRATEGY")
    print("   Strategy: FedAvgWithModelSaving")
    print(f"   Model save path: {save_path}")
    print("   Min available clients: 2")

    strategy = FedAvgWithModelSaving(
        save_path=save_path,
        fraction_fit=1.0,
        fraction_evaluate=1.0,
        min_available_clients=2,
        initial_parameters=params,
        evaluate_metrics_aggregation_fn=weighted_average,
    )
    num_rounds = context.run_config["num-server-rounds"]
    print(f"   Number of rounds: {num_rounds}\n")
    config = ServerConfig(num_rounds=num_rounds)

    print("✅ SERVER INITIALIZATION COMPLETE\n")
    return ServerAppComponents(config=config, strategy=strategy)


app = ServerApp(server_fn=server_fn)
