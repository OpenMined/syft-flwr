import sys
import traceback

from flwr.client import ClientApp
from flwr.common import Context
from flwr.common.constant import ErrorCode
from flwr.common.message import Error, Message
from loguru import logger
from syft_event import SyftEvents
from syft_event.types import Request

from syft_flwr.flwr_compatibility import RecordDict, create_flwr_message
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes


def syftbox_flwr_client(client_app: ClientApp, context: Context):
    """Run the Flower ClientApp with SyftBox."""

    box = SyftEvents("flwr")
    client_email = box.client.email
    logger.info(f"Started SyftBox Flower Client on: {client_email}")

    @box.on_request("/messages")
    def handle_messages(request: Request) -> None:
        logger.info(
            f"Received request id: {request.id}, size: {len(request.body) / 1024 / 1024} (MB)"
        )
        message: Message = bytes_to_flower_message(request.body)

        try:
            reply_message: Message = client_app(message=message, context=context)
            res_bytes: bytes = flower_message_to_bytes(reply_message)
            logger.info(f"Reply message size: {len(res_bytes)/2**20} MB")
            return res_bytes

        except Exception as e:
            error_traceback = traceback.format_exc()
            error_message = f"Client: '{client_email}'. Error: {str(e)}. Traceback: {error_traceback}"
            logger.error(error_message)

            error = Error(
                code=ErrorCode.CLIENT_APP_RAISED_EXCEPTION, reason=f"{error_message}"
            )

            error_reply: Message = create_flwr_message(
                content=RecordDict(),
                reply_to=message,
                message_type=message.metadata.message_type,
                src_node_id=message.metadata.dst_node_id,
                dst_node_id=message.metadata.src_node_id,
                group_id=message.metadata.group_id,
                run_id=message.metadata.run_id,
                error=error,
            )
            # Convert to bytes for transmission
            error_bytes: bytes = flower_message_to_bytes(error_reply)
            logger.info(f"Error reply message size: {len(error_bytes)/2**20} MB")
            return error_bytes

    try:
        box.run_forever()
    except Exception as e:
        # Log any exceptions from the event loop itself
        logger.error(
            f"Fatal error in syftbox_flwr_client: {str(e)}\n{traceback.format_exc()}"
        )
        sys.exit(1)
