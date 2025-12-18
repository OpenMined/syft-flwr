import os
import re
import zlib
from pathlib import Path

from flwr.common import Metadata
from flwr.common.message import Error, Message
from flwr.common.record import RecordDict
from loguru import logger
from syft_core import Client, SyftClientConfig
from syft_crypto.x3dh_bootstrap import ensure_bootstrap
from typing_extensions import Optional, Tuple, Union

from syft_flwr.client import SyftFlwrClient, create_client
from syft_flwr.client.syft_p2p_client import SyftP2PClient
from syft_flwr.consts import SYFT_FLWR_ENCRYPTION_ENABLED

EMAIL_REGEX = r"^[^@]+@[^@]+\.[^@]+$"


def is_valid_datasite(datasite: str) -> bool:
    return re.match(EMAIL_REGEX, datasite)


def str_to_int(input_string: str) -> int:
    """Convert a string to an int32"""
    return zlib.crc32(input_string.encode())


def get_syftbox_dataset_path() -> Path:
    """Get the path to the syftbox dataset from the environment variable"""
    data_dir = Path(os.getenv("DATA_DIR", ".data/"))
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Path {data_dir} does not exist (must be a valid file or directory)"
        )
    return data_dir


def run_syft_flwr() -> bool:
    """Util function to check if we are running with syft_flwr or plain flwr
    Currently only checks the `DATA_DIR` environment variable.
    """
    try:
        get_syftbox_dataset_path()
        return True
    except FileNotFoundError:
        return False


def create_temp_client(email: str, workspace_dir: Path) -> Client:
    """Create a temporary Client instance for testing"""
    workspace_hash = hash(str(workspace_dir)) % 10000
    server_port = 8080 + workspace_hash
    client_port = 8082 + workspace_hash
    config: SyftClientConfig = SyftClientConfig(
        email=email,
        data_dir=workspace_dir,
        server_url=f"http://localhost:{server_port}",
        client_url=f"http://localhost:{client_port}",
        path=workspace_dir / ".syftbox" / f"{email.split('@')[0]}_config.json",
    ).save()
    logger.debug(f"Created temp client {email} with config {config}")
    return Client(config)


def setup_client(
    app_name: str, project_dir: Optional[Path] = None
) -> Tuple[Union[Client, SyftFlwrClient], bool, str]:
    """Setup SyftBox client and encryption.

    Args:
        app_name: Name of the FL app
        project_dir: Path to the FL project directory (for reading transport config)

    Returns:
        Tuple of (client, encryption_enabled, app_path)
        - client: SyftFlwrClient (or native Client if encryption bootstrap needed)
        - encryption_enabled: Whether encryption is enabled
        - app_path: Path for the app (e.g., "flwr/{app_name}")
    """
    syftbox_client = create_client(project_dir=project_dir)
    syftbox_client = syftbox_client.get_client()

    # Check encryption setting
    encryption_enabled = (
        os.environ.get(SYFT_FLWR_ENCRYPTION_ENABLED, "true").lower() != "false"
    )

    # Bootstrap encryption if needed (only for syft_core - has RPC/crypto stack)
    if encryption_enabled and not isinstance(syftbox_client, SyftP2PClient):
        syftbox_client = ensure_bootstrap(syftbox_client)
        logger.info("🔐 End-to-end encryption is ENABLED for FL messages")
        # Return native client for RPC/crypto operations
        return syftbox_client, encryption_enabled, f"flwr/{app_name}"
    elif isinstance(syftbox_client, SyftP2PClient):
        # syft_client (Google Drive) - no encryption needed
        logger.info("📁 Running via syft_client (e.g. Google Drive sync)")
        return syftbox_client, False, f"flwr/{app_name}"
    else:
        logger.warning("⚠️ Encryption disabled - skipping client key bootstrap")
        logger.warning(
            "⚠️ End-to-end encryption is DISABLED for FL messages (development mode / insecure)"
        )
        return syftbox_client, encryption_enabled, f"flwr/{app_name}"


def check_reply_to_field(metadata: Metadata) -> bool:
    """Check if reply_to field is empty (Flower 1.17+ format)."""
    return metadata.reply_to_message_id == ""


def create_flwr_message(
    content: RecordDict,
    message_type: str,
    dst_node_id: int,
    group_id: str,
    ttl: Optional[float] = None,
    error: Optional[Error] = None,
    reply_to: Optional[Message] = None,
) -> Message:
    """Create a Flower message (requires Flower >= 1.17)."""
    if reply_to is not None:
        if error is not None:
            return Message(reply_to=reply_to, error=error)
        return Message(content=content, reply_to=reply_to)
    else:
        # Allow standalone error messages when we can't parse the original message
        if error is not None:
            logger.warning(
                "Creating error message without reply_to (failed to parse request)"
            )
            return Message(
                content=RecordDict(),
                dst_node_id=dst_node_id,
                message_type=message_type,
                ttl=ttl,
                group_id=group_id,
                error=error,
            )
        return Message(
            content=content,
            dst_node_id=dst_node_id,
            message_type=message_type,
            ttl=ttl,
            group_id=group_id,
        )
