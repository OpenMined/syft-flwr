import hashlib
from pathlib import Path

import tomllib  # TODO: replace with tomli, as it is not supported older python versions.
from flwr.client.client_app import LoadClientAppError
from flwr.common.object_ref import load_app
from flwr.server.server_app import LoadServerAppError


def string_to_hash_int(input_string: str) -> int:
    """Convert a string to a hash integer."""
    hash_object = hashlib.sha256(input_string.encode("utf-8"))
    hash_hex = hash_object.hexdigest()
    hash_int = int(hash_hex, 16) % (2**32)
    return hash_int


def read_toml_file(file_path):
    """Read a TOML file and return the data."""
    file_path = to_path(file_path)
    with open(file_path, "rb") as file:
        data = tomllib.load(file)
    return data


def to_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def load_server_app(flower_conf, flower_project_dir):
    """Load the Flower server app."""

    return load_app(
        flower_conf["tool"]["flwr"]["app"]["components"]["serverapp"],
        LoadServerAppError,
        flower_project_dir,
    )


def load_client_app(flower_conf, flower_project_dir):
    """Load the Flower client app."""
    return load_app(
        flower_conf["tool"]["flwr"]["app"]["components"]["clientapp"],
        LoadClientAppError,
        flower_project_dir,
    )
