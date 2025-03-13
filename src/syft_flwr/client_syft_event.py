from __future__ import annotations

from loguru import logger
from syft_event import SyftEvents
from syft_event.types import Request
from flwr.common.serde import message_from_proto
from flwr.proto.messages_pb2 import Message as ProtoMessage

box = SyftEvents("flwr")


@box.on_request("/messages")
def handle_messages(request: Request) -> None:
    logger.info(f"Received request size: {len(request.body)} bytes")
    message = message_from_proto(ProtoMessage.FromString(request.body))
    logger.info(f"Message: {message}")
    # reply_message = client_app(message=message, context=context)



if __name__ == "__main__":
    box.run_forever()
