import hashlib
from pathlib import Path

import tomllib  # TODO: replace with tomli, as it is not supported older python versions.
from flwr.common import Context
from flwr.common.record import RecordSet
from flwr.common.typing import UserConfig


def string_to_hash_int(input_string: str) -> int:
    """Convert a string to a hash integer."""
    hash_object = hashlib.sha256(input_string.encode("utf-8"))
    hash_hex = hash_object.hexdigest()
    hash_int = int(hash_hex, 16) % (2**32)
    return hash_int


def create_context(run_id: int, node_id: int) -> Context:
    return Context(
        run_id=run_id,
        node_id=node_id,
        node_config=UserConfig(),
        state=RecordSet(),
        run_config=UserConfig(),
    )


def read_toml_file(file_path):
    """Read a TOML file and return the data."""
    file_path = to_path(file_path)
    with open(file_path, "rb") as file:
        data = tomllib.load(file)
    return data


def to_path(path: str) -> Path:
    return Path(path).expanduser().resolve()
