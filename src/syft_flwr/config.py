from __future__ import annotations

from typing import Optional
from pathlib import Path

from flwr.common.config import validate_config

import tomllib

def load(file_path: str):
    """Read a TOML file and return the data."""
    with open(file_path, "rb") as fp:
        data = tomllib.load(fp)
    return data


def load_and_validate(path: Path, check_module: bool = True):
    config = load(path)

    if config is None:
        errors = [
            "Project configuration could not be loaded. "
            "`pyproject.toml` does not exist."
        ]
        return (None, errors, [])

    is_valid, errors, warnings = validate_config(config, check_module, path.parent)

    if not is_valid:
        return (None, errors, warnings)

    return (config, errors, warnings)

