import torch
import torch.nn as nn
from flwr.client import ClientApp, NumPyClient
from flwr.common import Context
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
        print(f"[Client {self.cid}] get_parameters")
        return get_parameters(self.net)

    def fit(self, parameters, config):
        self.embedding = self.net(self.train)
        torch.save(self.net, f"model_{self.cid}.pt")
        return [self.embedding.detach().numpy()], 1, {}

    def evaluate(self, parameters, config):
        self.net.zero_grad()
        self.embedding.backward(torch.from_numpy(parameters[int(self.cid)]))
        self.optimizer.step()
        return 0.0, 1, {}


def client_fn(context: Context):
    from .utils import load_syftbox_dataset

    net = SimpleMLP((8,), [1], 2, nn.ReLU)  # TODO: temporary fix
    net.apply(init_weights)
    X_train, _, _, _ = load_syftbox_dataset(int(context.node_config["partition-id"]))

    return FlowerClient(
        int(context.node_config["partition-id"]), net, X_train
    ).to_client()


app = ClientApp(client_fn=client_fn)
