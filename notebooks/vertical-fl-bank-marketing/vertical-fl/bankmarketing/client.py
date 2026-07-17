import torch
import torch.nn as nn
from flwr.client import ClientApp, NumPyClient
from flwr.common import Context
from loguru import logger
from torch import optim

from .model import SimpleMLP, init_weights
from .utils import get_parameters

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class FlowerClient(NumPyClient):
    def __init__(self, cid, net, data):
        self.cid = cid
        self.net = net
        self.train = torch.tensor(data).float()
        self.optimizer = optim.Adam(self.net.parameters(), lr=0.001)
        self.embedding = self.net(self.train)

    def get_parameters(self, config):
        logger.info(f"[Client {self.cid}] get_parameters")
        return get_parameters(self.net)

    def fit(self, parameters, config):
        self.embedding = self.net(self.train)
        return [self.embedding.detach().numpy()], 1, {}

    def evaluate(self, parameters, config):
        """
        In VFL, clients receive gradients from server and update their models.
        The parameters contain gradients for this client's embedding.
        """
        try:
            # Get gradients from server for this client
            client_gradients = torch.from_numpy(parameters[int(self.cid)])

            # Ensure gradients match embedding shape
            if client_gradients.shape != self.embedding.shape:
                logger.error(
                    f"[Client {self.cid}] Gradient shape mismatch: {client_gradients.shape} vs {self.embedding.shape}"
                )
                return 0.0, 1, {"error": "gradient_shape_mismatch"}

            # Apply gradients to embedding and backpropagate
            self.net.zero_grad()
            self.embedding.backward(client_gradients)
            self.optimizer.step()

            # Recompute embedding after update
            self.embedding = self.net(self.train)

            logger.info(
                f"[Client {self.cid}] Successfully updated model with gradients"
            )
            return 0.0, 1, {"status": "success"}

        except Exception as e:
            logger.error(f"[Client {self.cid}] Error in evaluate: {e}")
            return 0.0, 1, {"error": str(e)}


def client_fn(context: Context):
    from .utils import load_syftbox_dataset

    X_train, _ = load_syftbox_dataset()
    input_features = X_train.shape[1]
    logger.info(f"X_train's shape: {X_train.shape}, input_features: {input_features}")

    net = SimpleMLP((input_features,), [1], 2, nn.ReLU)
    net.apply(init_weights)

    return FlowerClient(
        int(context.node_config["partition-id"]), net, X_train
    ).to_client()


app = ClientApp(client_fn=client_fn)
