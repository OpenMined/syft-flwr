from flwr.client import ClientApp
from flwr.common import Context
from flwr.common.message import Message
from loguru import logger
from syft_event import SyftEvents
from syft_event.types import Request

from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes


def syftbox_flwr_client(client_app: ClientApp, context: Context):
    """Run the Flower ClientApp with SyftBox."""

    box = SyftEvents("flwr")
    logger.info(f"Started SyftBox Flower Client on: {box.client.email}")

    @box.on_request("/messages")
    def handle_messages(request: Request) -> None:
        logger.info(
            f"Received request id: {request.id}, size: {len(request.body)} bytes"
        )
        message: Message = bytes_to_flower_message(request.body)
        reply_message: Message = client_app(message=message, context=context)
        res_bytes: bytes = flower_message_to_bytes(reply_message)
        logger.info(f"Reply message size: {len(res_bytes)/2**20} MB")
        return res_bytes

    box.run_forever()
