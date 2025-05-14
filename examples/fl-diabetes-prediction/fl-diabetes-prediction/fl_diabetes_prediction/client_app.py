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
        self.net = net
        self.trainloader = trainloader
        self.testloader = testloader

    def fit(self, parameters, config):
        set_weights(self.net, parameters)
        train(self.net, self.trainloader)
        return get_weights(self.net), len(self.trainloader), {}

    def evaluate(self, parameters, config):
        set_weights(self.net, parameters)
        loss, accuracy = evaluate(self.net, self.testloader)
        return loss, len(self.testloader), {"accuracy": accuracy}


def client_fn(context: Context):
    from fl_diabetes_prediction.task import load_syftbox_dataset
    from syft_flwr.utils import run_syft_flwr

    if not run_syft_flwr():
        logger.info("Running flwr locally")
        train_loader, test_loader = load_flwr_data(
            partition_id=context.node_config["partition-id"],
            num_partitions=context.node_config["num-partitions"],
        )
    else:
        logger.info("Running with syft_flwr")
        train_loader, test_loader = load_syftbox_dataset()
    net = Net()
    return FlowerClient(net, train_loader, test_loader).to_client()


app = ClientApp(client_fn=client_fn)
