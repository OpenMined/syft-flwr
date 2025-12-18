import base64
import sys
import traceback
from pathlib import Path

from flwr.client import ClientApp
from flwr.common import Context
from flwr.common.constant import ErrorCode, MessageType
from flwr.common.message import Error, Message
from flwr.common.record import RecordDict
from loguru import logger
from typing_extensions import Optional, Union

from syft_flwr.events import SyftFlwrEvents, create_events_watcher
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes
from syft_flwr.utils import create_flwr_message, setup_client


class MessageHandler:
    """Handles message processing for Flower client."""

    def __init__(
        self, client_app: ClientApp, context: Context, encryption_enabled: bool
    ):
        self.client_app = client_app
        self.context = context
        self.encryption_enabled = encryption_enabled

    def prepare_reply(self, data: bytes) -> Union[str, bytes]:
        """Prepare reply data based on encryption setting."""
        if self.encryption_enabled:
            logger.info(f"🔒 Preparing ENCRYPTED reply, size: {len(data)/2**20:.2f} MB")
            return base64.b64encode(data).decode("utf-8")
        else:
            logger.info(f"📤 Preparing PLAINTEXT reply, size: {len(data)/2**20:.2f} MB")
            return data

    def process_message(self, message: Message) -> Union[str, bytes]:
        """Process normal Flower message and return reply."""
        logger.info(f"Processing message with metadata: {message.metadata}")
        reply_message = self.client_app(message=message, context=self.context)
        reply_bytes = flower_message_to_bytes(reply_message)
        return self.prepare_reply(reply_bytes)

    def create_error_reply(
        self, message: Optional[Message], error: Error
    ) -> Union[str, bytes]:
        """Create error reply message."""
        error_reply = create_flwr_message(
            content=RecordDict(),
            reply_to=message,
            message_type=message.metadata.message_type
            if message
            else MessageType.SYSTEM,
            dst_node_id=message.metadata.src_node_id if message else 0,
            group_id=message.metadata.group_id if message else "",
            error=error,
        )
        error_bytes = flower_message_to_bytes(error_reply)
        logger.info(f"Error reply size: {len(error_bytes)/2**20:.2f} MB")
        return self.prepare_reply(error_bytes)


class RequestProcessor:
    """Processes incoming requests and handles encryption/decryption."""

    def __init__(
        self, message_handler: MessageHandler, events: SyftFlwrEvents, client_email: str
    ):
        self.message_handler = message_handler
        self.events = events
        self.client_email = client_email

    def decode_request_body(self, request_body: Union[bytes, str]) -> bytes:
        """Decode request body, handling base64 if encrypted."""
        if not self.message_handler.encryption_enabled:
            return request_body

        try:
            # Convert to string if bytes
            if isinstance(request_body, bytes):
                request_body_str = request_body.decode("utf-8")
            else:
                request_body_str = request_body
            # Decode base64
            decoded = base64.b64decode(request_body_str)
            logger.debug("🔓 Decoded base64 message")
            return decoded
        except Exception:
            # Not base64 or decoding failed, use as-is
            return request_body

    def is_stop_signal(self, message: Message) -> bool:
        """Check if message is a stop signal."""
        if message.metadata.message_type != MessageType.SYSTEM:
            return False

        # Check for stop action in config
        if "config" in message.content and "action" in message.content["config"]:
            return message.content["config"]["action"] == "stop"

        # Alternative stop signal format
        return message.metadata.group_id == "final"

    def process(self, request_body: bytes) -> Optional[Union[str, bytes]]:
        """Process incoming request body and return response.

        Args:
            request_body: Raw message bytes from the events adapter
        """
        encryption_status = (
            "🔐 ENCRYPTED"
            if self.message_handler.encryption_enabled
            else "📥 PLAINTEXT"
        )

        logger.info(
            f"{encryption_status} Received request, "
            f"size: {len(request_body) / 1024 / 1024:.2f} MB"
        )

        # Parse message
        try:
            decoded_body = self.decode_request_body(request_body)
            message = bytes_to_flower_message(decoded_body)

            if self.message_handler.encryption_enabled:
                logger.debug("🔓 Successfully decrypted message")
        except Exception as e:
            logger.error(f"❌ Failed to deserialize message: {e}")
            logger.debug(
                f"Request body preview (first 200 bytes): {str(request_body[:200])}"
            )

            # Can't create error reply without valid message - skip response
            logger.warning(
                "Skipping error reply (cannot create without valid parsed message)"
            )
            return None

        # Handle message
        try:
            # Check for stop signal
            if self.is_stop_signal(message):
                logger.info("Received stop signal")
                self.events.stop()
                return None

            # Process normal message
            return self.message_handler.process_message(message)

        except Exception as e:
            error_message = f"Client: '{self.client_email}'. Error: {str(e)}. Traceback: {traceback.format_exc()}"
            logger.error(error_message)

            error = Error(
                code=ErrorCode.CLIENT_APP_RAISED_EXCEPTION, reason=error_message
            )
            return self.message_handler.create_error_reply(message, error)


def syftbox_flwr_client(
    client_app: ClientApp,
    context: Context,
    app_name: str,
    project_dir: Optional[Path] = None,
):
    """Run the Flower ClientApp with SyftBox.

    Supports both syft_core (traditional SyftBox) and syft_client (P2P file sync).
    The appropriate events adapter is auto-detected based on environment.
    """
    # Setup - now works for both syft_core and syft_client
    client, encryption_enabled, syft_flwr_app_name = setup_client(
        app_name, project_dir=project_dir
    )

    # Create events adapter (auto-detects syft_core vs syft_client)
    events_watcher = create_events_watcher(
        app_name=syft_flwr_app_name,
        client=client,
        cleanup_expiry="1d",
        cleanup_interval="1d",
    )

    logger.info(f"Started SyftBox Flower Client on: {events_watcher.client_email}")
    logger.info(f"syft_flwr app name: {syft_flwr_app_name}")

    # Create handlers
    message_handler = MessageHandler(client_app, context, encryption_enabled)
    processor = RequestProcessor(
        message_handler, events_watcher, events_watcher.client_email
    )

    # Register message handler - works for both adapters
    events_watcher.on_request(
        "/messages",
        handler=lambda body: processor.process(body),
        auto_decrypt=encryption_enabled,
        encrypt_reply=encryption_enabled,
    )

    # Run
    try:
        events_watcher.run_forever()
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
        events_watcher.stop()
    except Exception as e:
        logger.error(
            f"Fatal error in syftbox_flwr_client: {str(e)}\n{traceback.format_exc()}"
        )
        sys.exit(1)
