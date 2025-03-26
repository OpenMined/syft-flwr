from __future__ import annotations

from pathlib import Path

import tomli
import tomli_w
from flwr.common.config import validate_config
from loguru import logger


def load_pyproject(path: str):
    with open(path, "rb") as fp:
        return tomli.load(fp)


def write_pyproject(path: str, pyproject_conf: dict):
    with open(path, "wb") as fp:
        tomli_w.dump(pyproject_conf, fp)


def load_flwr_pyproject(path: Path, check_module: bool = True) -> dict:
    """Load the flower's pyproject.toml file and validate it."""
    pyproject = load_pyproject(path)
    is_valid, errors, warnings = validate_config(pyproject, check_module, path.parent)

    if not is_valid:
        raise Exception(errors)

    if warnings:
        logger.warning(warnings)

    return pyproject
