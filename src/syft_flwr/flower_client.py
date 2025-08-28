import base64
import os
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

from syft_flwr.consts import SYFT_FLWR_ENCRYPTION_ENABLED
from syft_flwr.flwr_compatibility import RecordDict, create_flwr_message
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes


def _handle_normal_message(
    message: Message,
    client_app: ClientApp,
    context: Context,
    encryption_enabled: bool = False,
):
    # Normal message handling
    logger.info(f"Processing message with metadata: {message.metadata}")
    reply_message: Message = client_app(message=message, context=context)
    res_bytes: bytes = flower_message_to_bytes(reply_message)

    # Log with encryption status
    if encryption_enabled:
        logger.info(
            f"🔒 Preparing ENCRYPTED reply, size: {len(res_bytes)/2**20:.2f} MB"
        )
        # When encryption is enabled, return base64-encoded string directly
        return base64.b64encode(res_bytes).decode("utf-8")
    else:
        logger.info(
            f"📤 Preparing PLAINTEXT reply, size: {len(res_bytes)/2**20:.2f} MB"
        )
        # Return raw bytes when not encrypting
        return res_bytes


def _create_error_reply(
    message: Message, error: Error, encryption_enabled: bool = False
):
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
    logger.info(f"Error reply message size: {len(error_bytes)/2**20:.2f} MB")

    if encryption_enabled:
        # Return base64-encoded string for encryption
        return base64.b64encode(error_bytes).decode("utf-8")
    else:
        return error_bytes


def syftbox_flwr_client(client_app: ClientApp, context: Context, app_name: str):
    """Run the Flower ClientApp with SyftBox."""
    syft_flwr_app_name = f"flwr/{app_name}"
    client = Client.load()

    # Check if encryption is enabled (default: True for production)
    encryption_enabled = (
        os.environ.get(SYFT_FLWR_ENCRYPTION_ENABLED, "true").lower() != "false"
    )

    # Bootstrap X3DH encryption keys for the client (if encryption is enabled)
    if encryption_enabled:
        client = ensure_bootstrap(client)
    else:
        logger.warning("⚠️ Encryption disabled - skipping client key bootstrap")

    box = SyftEvents(app_name=syft_flwr_app_name, client=client)
    client_email = box.client.email

    logger.info(f"Started SyftBox Flower Client on: {client_email}")
    logger.info(f"syft_flwr app name: {syft_flwr_app_name}")

    if encryption_enabled:
        logger.info("🔐 End-to-end encryption is ENABLED for FL messages")
        logger.debug("🔐 End-to-end encryption is ENABLED for FL messages")
    else:
        logger.warning(
            "⚠️ End-to-end encryption is DISABLED for FL messages (development mode)"
        )

    @box.on_request(
        "/messages", auto_decrypt=encryption_enabled, encrypt_reply=encryption_enabled
    )
    def handle_messages(request: Request) -> None:
        # Log message reception with encryption status
        encryption_status = "🔐 ENCRYPTED" if encryption_enabled else "📥 PLAINTEXT"
        original_sender = request.headers.get("X-Syft-Original-Sender", "unknown")

        logger.info(
            f"{encryption_status} Received request from {original_sender}, "
            f"id: {request.id}, size: {len(request.body) / 1024 / 1024:.2f} MB"
        )

        try:
            # Request body is automatically decrypted if auto_decrypt=True
            request_body = request.body

            # If encryption is enabled, the decrypted body should be a base64-encoded string
            if encryption_enabled:
                try:
                    # Try to decode as base64 string directly
                    if isinstance(request_body, bytes):
                        request_body_str = request_body.decode("utf-8")
                    else:
                        request_body_str = request_body
                    # Decode the base64-encoded Flower message
                    request_body = base64.b64decode(request_body_str)
                    logger.debug(f"🔓 Decoded base64 message from {original_sender}")
                except Exception:
                    # Not base64 or decoding failed, use as-is (might be plaintext fallback)
                    pass

            # Parse the (potentially decoded) message
            message: Message = bytes_to_flower_message(request_body)

            # Log successful decryption if encryption is enabled
            if encryption_enabled:
                logger.debug(
                    f"🔓 Successfully decrypted message from {original_sender}"
                )
        except ValueError as e:
            # Message deserialization error - could be decryption failure
            logger.error(
                f"❌ Failed to deserialize message from {original_sender}: {e}. "
                f"This may indicate a decryption failure or corrupted message."
            )
            error = Error(
                code=ErrorCode.CLIENT_APP_RAISED_EXCEPTION,
                reason=f"Message deserialization failed: {e}",
            )
            return _create_error_reply(None, error, encryption_enabled)
        except Exception as e:
            logger.error(
                f"❌ Unexpected error processing message from {original_sender}: {e}"
            )
            error = Error(
                code=ErrorCode.CLIENT_APP_RAISED_EXCEPTION,
                reason=f"Message processing failed: {e}",
            )
            return _create_error_reply(None, error, encryption_enabled)

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

            # Handle normal FL message and return reply
            # The reply will be automatically encrypted if encrypt_reply=True
            # by the box.on_request decorator
            return _handle_normal_message(
                message, client_app, context, encryption_enabled
            )

        except Exception as e:
            error_traceback = traceback.format_exc()
            error_message = f"Client: '{client_email}'. Error: {str(e)}. Traceback: {error_traceback}"
            logger.error(error_message)

            error = Error(
                code=ErrorCode.CLIENT_APP_RAISED_EXCEPTION, reason=error_message
            )
            box._stop_event.set()
            return _create_error_reply(message, error, encryption_enabled)

    try:
        box.run_forever()
    except Exception as e:
        logger.error(
            f"Fatal error in syftbox_flwr_client: {str(e)}\n{traceback.format_exc()}"
        )
        sys.exit(1)
