"""fltabular: Flower Example on Adult Census Income Tabular Dataset."""

import os

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

    # Always use RDS job output directory
    output_dir = os.getenv("OUTPUT_DIR")
    if output_dir is None:
        output_dir = Path.home() / ".syftbox/rds/"
        output_dir.mkdir(parents=True, exist_ok=True)
    save_path = Path(output_dir) / "weights"

    # Fault tolerance configuration
    # With 4 total clients, system can tolerate 50% failure (2 clients)
    # and still have 2 clients for training
    min_available_clients = context.run_config.get("min-available-clients", 1)
    min_fit_clients = context.run_config.get("min-fit-clients", 1)
    min_evaluate_clients = context.run_config.get("min-evaluate-clients", 1)
    fraction_fit = context.run_config.get("fraction-fit", 1)
    fraction_evaluate = context.run_config.get("fraction-evaluate", 1)

    print("⚙️ CONFIGURING STRATEGY")
    print("   Strategy: FedAvgWithModelSaving")
    print(f"   Model save path: {save_path}")
    print(f"   Min available clients: {min_available_clients}")
    print(f"   Min fit clients: {min_fit_clients}")
    print(f"   Min evaluate clients: {min_evaluate_clients}")
    print(f"   Fraction fit: {fraction_fit}")
    print(f"   Fraction evaluate: {fraction_evaluate}")

    strategy = FedAvgWithModelSaving(
        save_path=save_path,
        fraction_fit=fraction_fit,
        fraction_evaluate=fraction_evaluate,
        min_available_clients=min_available_clients,
        min_fit_clients=min_fit_clients,
        min_evaluate_clients=min_evaluate_clients,
        initial_parameters=params,
        evaluate_metrics_aggregation_fn=weighted_average,
    )
    num_rounds = context.run_config["num-server-rounds"]
    print(f"   Number of rounds: {num_rounds}\n")
    config = ServerConfig(num_rounds=num_rounds)

    print("✅ SERVER INITIALIZATION COMPLETE\n")
    return ServerAppComponents(config=config, strategy=strategy)


app = ServerApp(server_fn=server_fn)
