"""quickstart-pytorch: A Flower / PyTorch app."""

from flwr.client import ClientApp, NumPyClient
from flwr.common import Context
from loguru import logger

from quickstart_pytorch.task import (
    Net,
    get_device,
    get_weights,
    load_data,
    set_weights,
    test,
    train,
)


# Define Flower Client and client_fn
class FlowerClient(NumPyClient):
    def __init__(self, net, trainloader, valloader, local_epochs):
        self.net = net
        self.trainloader = trainloader
        self.valloader = valloader
        self.local_epochs = local_epochs
        self.device = get_device()
        logger.info(f"Using device: {self.device}")
        self.net.to(self.device)

    def fit(self, parameters, config):
        set_weights(self.net, parameters)
        train_loss = train(
            self.net,
            self.trainloader,
            self.local_epochs,
            self.device,
        )
        return (
            get_weights(self.net),
            len(self.trainloader.dataset),
            {"train_loss": train_loss},
        )

    def evaluate(self, parameters, config):
        set_weights(self.net, parameters)
        loss, accuracy = test(self.net, self.valloader, self.device)
        return loss, len(self.valloader.dataset), {"accuracy": accuracy}


def client_fn(context: Context):
    # Load model and data
    net = Net()
    local_epochs = context.run_config["local-epochs"]
    from quickstart_pytorch.task import load_syftbox_dataset
    from syft_flwr.utils import run_syft_flwr

    if not run_syft_flwr():
        partition_id = context.node_config["partition-id"]
        num_partitions = context.node_config["num-partitions"]
        trainloader, valloader = load_data(partition_id, num_partitions)
    else:
        trainloader, valloader = load_syftbox_dataset()
    # Return Client instance
    return FlowerClient(net, trainloader, valloader, local_epochs).to_client()


# Flower ClientApp
app = ClientApp(
    client_fn,
)
