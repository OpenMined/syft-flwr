import os
import re
import zlib
from pathlib import Path

from loguru import logger
from syft_core import Client, SyftClientConfig

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
