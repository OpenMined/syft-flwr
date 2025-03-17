from __future__ import annotations

from flwr.client import ClientApp, NumPyClient
from flwr.common import Context
from flwr.common.message import Message as FlowerMessage
from flwr.common.record import RecordSet
from flwr.common.typing import UserConfig
from loguru import logger
from syft_event import SyftEvents
from syft_event.types import Request

from examples.basic.server import get_dummy_model
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes

box = SyftEvents("flwr")


class FlowerClient(NumPyClient):
    def fit(self, parameters, config):
        model = get_dummy_model()
        return [model], 1, {}

    def evaluate(self, parameters, config):
        return float(0.0), 1, {"accuracy": float(1.0)}


def client_fn(context: Context):
    return FlowerClient().to_client()


@box.on_request("/messages")
def handle_messages(request: Request) -> None:
    logger.info(f"Received request id: {request.id}, size: {len(request.body)} bytes")
    message: FlowerMessage = bytes_to_flower_message(request.body)
    run_id = 12345  # same as server
    context = Context(
        run_id=run_id,
        node_id=0,
        node_config=UserConfig(),
        state=RecordSet(),
        run_config=UserConfig(),
    )
    client_app = ClientApp(client_fn=client_fn)
    reply_message: FlowerMessage = client_app(message=message, context=context)
    logger.info(f"Reply message type: {type(reply_message)}")
    res_bytes: bytes = flower_message_to_bytes(reply_message)
    logger.info(f"Reply message size: {len(res_bytes)/2**20} MB")
    return res_bytes


if __name__ == "__main__":
    box.run_forever()
