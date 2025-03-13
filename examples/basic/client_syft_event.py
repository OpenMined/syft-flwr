from __future__ import annotations

from loguru import logger
from syft_event import SyftEvents
from syft_event.types import Request
from flwr.common.serde import message_from_proto, message_to_proto
from flwr.proto.message_pb2 import Message as ProtoMessage

from client import app as client_app

from flwr.common.record import RecordSet
from flwr.common.typing import UserConfig
from flwr.common import Context

box = SyftEvents("flwr")


@box.on_request("/messages")
def handle_messages(request: Request) -> None:
    logger.info(f"Received request id: {request.id}, size: {len(request.body)} bytes")
    message = message_from_proto(ProtoMessage.FromString(request.body))
    # logger.info(f"Message: {message}")
    run_id = 12345 # same as server
    context = Context(
        run_id=run_id,
        node_id=0,
        node_config=UserConfig(),
        state=RecordSet(),
        run_config=UserConfig(),
    )
    reply_message = client_app(message=message, context=context)
    logger.info(f"Reply message type: {type(reply_message)}")

    msg_proto = message_to_proto(reply_message)
    res_bytes =  msg_proto.SerializeToString()
    logger.info(f"Reply message size: {len(res_bytes)/2**20} MB")
    return res_bytes

if __name__ == "__main__":
    box.run_forever()
