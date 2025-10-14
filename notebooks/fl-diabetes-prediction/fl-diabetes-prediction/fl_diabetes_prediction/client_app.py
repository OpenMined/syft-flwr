from flwr.client import ClientApp, NumPyClient
from flwr.common import Context
from loguru import logger

from fl_diabetes_prediction.task import (
    Net,
    evaluate,
    get_weights,
    load_flwr_data,
    set_weights,
    train,
)


class FlowerClient(NumPyClient):
    def __init__(self, net, trainloader, testloader):
        print("\n" + "=" * 80)
        print("🔵 FLOWER CLIENT INITIALIZED")
        print(
            f"   Training batches: {len(trainloader)} | Test batches: {len(testloader)}"
        )
        print("=" * 80 + "\n")
        self.net = net
        self.trainloader = trainloader
        self.testloader = testloader

    def fit(self, parameters, config):
        print("\n" + "▶" * 80)
        print("🟢 TRAINING ROUND STARTED")
        print(f"   Batches: {len(self.trainloader)}")
        print("▶" * 80)
        set_weights(self.net, parameters)
        train(self.net, self.trainloader)
        print("✅ TRAINING COMPLETE\n")
        return get_weights(self.net), len(self.trainloader), {}

    def evaluate(self, parameters, config):
        print("\n" + "◆" * 80)
        print("🔵 EVALUATION ROUND STARTED")
        print(f"   Batches: {len(self.testloader)}")
        print("◆" * 80)
        set_weights(self.net, parameters)
        loss, accuracy = evaluate(self.net, self.testloader)
        print("📊 EVALUATION RESULTS:")
        print(f"   Loss: {loss:.4f} | Accuracy: {accuracy:.4f}")
        print("✅ EVALUATION COMPLETE\n")
        return loss, len(self.testloader), {"accuracy": accuracy}


def client_fn(context: Context):
    print("\n" + "█" * 80)
    print("🚀 CLIENT FUNCTION STARTED")
    print(f"📋 Node Config: {context.node_config}")
    print("█" * 80 + "\n")
    from fl_diabetes_prediction.task import load_syftbox_dataset
    from syft_flwr.utils import run_syft_flwr

    if not run_syft_flwr():
        print("📦 Loading Flower data locally...")
        logger.info("Running flwr locally")
        train_loader, test_loader = load_flwr_data(
            partition_id=context.node_config["partition-id"],
            num_partitions=context.node_config["num-partitions"],
        )
    else:
        print("📦 Loading SyftBox dataset...")
        logger.info("Running with syft_flwr")
        train_loader, test_loader = load_syftbox_dataset()
    net = Net()
    return FlowerClient(net, train_loader, test_loader).to_client()


app = ClientApp(client_fn=client_fn)
