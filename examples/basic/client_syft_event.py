from __future__ import annotations

from flwr.client import ClientApp, NumPyClient
from flwr.common import Context
from flwr.common.record import RecordSet
from flwr.common.serde import message_from_proto, message_to_proto
from flwr.common.typing import UserConfig
from flwr.proto.message_pb2 import Message as ProtoMessage
from loguru import logger
from server import get_dummy_model
from syft_event import SyftEvents
from syft_event.types import Request

box = SyftEvents("flwr")


class FlowerClient(NumPyClient):
    def fit(self, parameters, config):
        model = get_dummy_model()
        return [model], 1, {}

    def evaluate(self, parameters, config):
        return float(1.2345), 1, {"accuracy": float(1.0)}


def client_fn(context: Context):
    return FlowerClient().to_client()


@box.on_request("/messages")
def handle_messages(request: Request) -> None:
    logger.info(f"Received request id: {request.id}, size: {len(request.body)} bytes")
    message_pb = ProtoMessage()
    message_pb.ParseFromString(request.body)
    message = message_from_proto(message_pb)
    run_id = 12345  # same as server
    context = Context(
        run_id=run_id,
        node_id=0,
        node_config=UserConfig(),
        state=RecordSet(),
        run_config=UserConfig(),
    )
    client_app = ClientApp(client_fn=client_fn)
    reply_message = client_app(message=message, context=context)
    logger.info(f"Reply message type: {type(reply_message)}")
    msg_proto = message_to_proto(reply_message)
    res_bytes = msg_proto.SerializeToString()
    logger.info(f"Reply message size: {len(res_bytes)/2**20} MB")
    return res_bytes


if __name__ == "__main__":
    box.run_forever()
