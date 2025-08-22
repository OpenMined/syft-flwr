import sys
import traceback

from flwr.client import ClientApp
from flwr.common import Context
from flwr.common.constant import ErrorCode, MessageType
from flwr.common.message import Error, Message
from loguru import logger
from syft_core import Client
from syft_crypto.x3dh_bootstrap import ensure_bootstrap
from syft_event import SyftEvents
from syft_event.types import Request

from syft_flwr.flwr_compatibility import RecordDict, create_flwr_message
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes


def _handle_normal_message(
    message: Message, client_app: ClientApp, context: Context
) -> bytes:
    # Normal message handling
    logger.info(f"Receive message with metadata: {message.metadata}")
    reply_message: Message = client_app(message=message, context=context)
    res_bytes: bytes = flower_message_to_bytes(reply_message)
    logger.info(f"Reply message size: {len(res_bytes)/2**20} MB")
    return res_bytes


def _create_error_reply(message: Message, error: Error) -> bytes:
    """Create and return error reply message in bytes."""
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
    error_bytes: bytes = flower_message_to_bytes(error_reply)
    logger.info(f"Error reply message size: {len(error_bytes)/2**20} MB")
    return error_bytes


def syftbox_flwr_client(client_app: ClientApp, context: Context, app_name: str):
    """Run the Flower ClientApp with SyftBox."""
    syft_flwr_app_name = f"flwr/{app_name}"
    client = Client.load()
    client = ensure_bootstrap(client)
    box = SyftEvents(app_name=syft_flwr_app_name, client=client)
    client_email = box.client.email
    logger.info(f"Started SyftBox Flower Client on: {client_email}")
    logger.info(f"syft_flwr app name: {syft_flwr_app_name}")

    @box.on_request("/messages")
    def handle_messages(request: Request) -> None:
        logger.info(
            f"Received request id: {request.id}, size: {len(request.body) / 1024 / 1024} (MB)"
        )
        message: Message = bytes_to_flower_message(request.body)
        try:
            # Handle stop signal
            if message.metadata.message_type == MessageType.SYSTEM:
                # Check for stop action in various possible formats
                is_stop_signal = False
                if (
                    "config" in message.content
                    and "action" in message.content["config"]
                ):
                    is_stop_signal = message.content["config"]["action"] == "stop"
                elif message.metadata.group_id == "final":
                    # Alternative stop signal format
                    is_stop_signal = True

                if is_stop_signal:
                    logger.info(f"Received stop message: {message}")
                    box._stop_event.set()
                    return None

            return _handle_normal_message(message, client_app, context)

        except Exception as e:
            error_traceback = traceback.format_exc()
            error_message = f"Client: '{client_email}'. Error: {str(e)}. Traceback: {error_traceback}"
            logger.error(error_message)

            error = Error(
                code=ErrorCode.CLIENT_APP_RAISED_EXCEPTION, reason=error_message
            )
            box._stop_event.set()
            return _create_error_reply(message, error)

    try:
        box.run_forever()
    except Exception as e:
        logger.error(
            f"Fatal error in syftbox_flwr_client: {str(e)}\n{traceback.format_exc()}"
        )
        sys.exit(1)
