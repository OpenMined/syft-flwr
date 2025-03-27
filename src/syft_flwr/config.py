from __future__ import annotations

from pathlib import Path

import tomli
import tomli_w
from flwr.common.config import validate_config
from loguru import logger


def load_toml(path: str):
    with open(path, "rb") as fp:
        return tomli.load(fp)


def write_toml(path: str, val: dict):
    with open(path, "wb") as fp:
        tomli_w.dump(val, fp)


def load_flwr_pyproject(path: Path, check_module: bool = True) -> dict:
    """Load the flower's pyproject.toml file and validate it."""

    if path.name != "pyproject.toml":
        path = path / "pyproject.toml"

    pyproject = load_toml(path)
    is_valid, errors, warnings = validate_config(pyproject, check_module, path.parent)

    if not is_valid:
        raise Exception(errors)

    if warnings:
        logger.warning(warnings)

    return pyproject
