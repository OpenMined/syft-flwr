"""pytorch: A Flower / PyTorch app."""

import torch
from flwr.client import ClientApp, NumPyClient
from flwr.common import Context
from flwr.common.message import Message as FlowerMessage
from loguru import logger
from syft_event import SyftEvents
from syft_event.types import Request

from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes
from syft_flwr.utils import create_empty_context

from .task import Net, get_weights, load_data, set_weights, test, train

box = SyftEvents("flwr-torch")


# Define Flower Client and client_fn
class FlowerClient(NumPyClient):
    def __init__(self, net, trainloader, valloader, local_epochs):
        self.net = net
        self.trainloader = trainloader
        self.valloader = valloader
        self.local_epochs = local_epochs
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.net.to(self.device)

    def fit(self, parameters, config):
        set_weights(self.net, parameters)
        train_loss = train(
            self.net,
            self.trainloader,
            self.local_epochs,
            self.device,
        )
        logger.info(f"Client's train loss: {train_loss}")
        return (
            get_weights(self.net),
            len(self.trainloader.dataset),
            {"train_loss": train_loss},
        )

    def evaluate(self, parameters, config):
        set_weights(self.net, parameters)
        loss, accuracy = test(self.net, self.valloader, self.device)
        logger.info(f"Client's evaluate loss: {loss}, accuracy: {accuracy}")
        return loss, len(self.valloader.dataset), {"accuracy": accuracy}


def client_fn(context: Context):
    # Load model and data
    net = Net()
    # partition_id = context.node_config["partition-id"]
    # num_partitions = context.node_config["num-partitions"]
    # local_epochs = context.run_config["local-epochs"]
    partition_id = (
        0  # Starting with first partition which might contain more balanced data
    )
    num_partitions = 1  # Using just 1 partition to get all available data
    local_epochs = 1  # Increasing training epochs for better convergence
    trainloader, valloader = load_data(partition_id, num_partitions)

    # Return Client instance
    return FlowerClient(net, trainloader, valloader, local_epochs).to_client()


@box.on_request("/messages")
def handle_messages(request: Request) -> bytes:
    context = create_empty_context(run_id=2)
    client_app = ClientApp(client_fn=client_fn)

    logger.info(f"Received request id: {request.id}, size: {len(request.body)} bytes")
    message: FlowerMessage = bytes_to_flower_message(request.body)

    reply_message: FlowerMessage = client_app(message=message, context=context)
    logger.info(f"Reply message type: {type(reply_message)}")
    reply_bytes: bytes = flower_message_to_bytes(reply_message)
    logger.info(f"Reply message size: {len(reply_bytes)/2**20} MB")

    return reply_bytes


if __name__ == "__main__":
    box.run_forever()
