from flwr.client import ClientApp, NumPyClient
from flwr.common import Context

from server import get_dummy_model


class FlowerClient(NumPyClient):
    def fit(self, parameters, config):
        model = get_dummy_model()
        return [model], 1, {}

    def evaluate(self, parameters, config):
        return float(1.2345), 1, {"accuracy": float(1.0)}


def client_fn(context: Context):
    return FlowerClient().to_client()


# Flower ClientApp
app = ClientApp(client_fn=client_fn)
