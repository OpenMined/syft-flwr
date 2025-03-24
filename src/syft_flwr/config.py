from __future__ import annotations

from pathlib import Path
from typing import Union

import tomllib
from flwr.common.config import validate_config
from loguru import logger


def load(file_path: str) -> dict:
    """Read a TOML file and return the data."""
    with open(file_path, "rb") as fp:
        data = tomllib.load(fp)
    return data


def load_config(path: Union[str, Path], check_module: bool = True) -> dict:
    path = Path(path)
    config_path = path / "pyproject.toml"
    if not config_path.exists():
        raise ValueError(
            "Project configuration could not be loaded. "
            "`pyproject.toml` does not exist."
        )

    config = load(config_path)

    is_valid, errors, warnings = validate_config(config, check_module, path.parent)

    if not is_valid:
        raise ValueError(errors)
    if warnings:
        logger.warning(warnings)

    return config
