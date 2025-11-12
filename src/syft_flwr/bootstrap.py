import time
from pathlib import Path

from loguru import logger
from typing_extensions import List, Union

from syft_flwr import __version__
from syft_flwr.config import load_flwr_pyproject, write_toml
from syft_flwr.utils import is_valid_datasite

__all__ = ["bootstrap"]


MAIN_TEMPLATE_PATH = Path(__file__).parent / "templates" / "main.py.tpl"
MAIN_TEMPLATE_CONTENT = MAIN_TEMPLATE_PATH.read_text()
assert MAIN_TEMPLATE_CONTENT


def __copy_main_py(flwr_project_dir: Path) -> None:
    """Copy the content below to `main.py` file to the syft-flwr project"""

    main_py_path = flwr_project_dir / "main.py"

    if main_py_path.exists():
        raise Exception(f"The file '{main_py_path}' already exists")

    main_py_path.write_text(MAIN_TEMPLATE_CONTENT)


def __update_pyproject_toml(
    flwr_project_dir: Union[str, Path],
    aggregator: str,
    datasites: List[str],
) -> None:
    """Update the `pyproject.toml` file to the syft-flwr project"""
    flwr_project_dir = Path(flwr_project_dir)
    flwr_pyproject = Path(flwr_project_dir, "pyproject.toml")
    pyproject_conf = load_flwr_pyproject(flwr_pyproject, check_module=False)

    # TODO: remove this after we find out how to pass the right context to the clients
    pyproject_conf["tool"]["flwr"]["app"]["config"]["partition-id"] = 0
    pyproject_conf["tool"]["flwr"]["app"]["config"]["num-partitions"] = 1
    # TODO end

    # add syft_flwr as a dependency
    if "dependencies" not in pyproject_conf["project"]:
        pyproject_conf["project"]["dependencies"] = []

    deps: list = pyproject_conf["project"]["dependencies"]
    deps = [dep for dep in deps if not dep.startswith("syft_flwr")]
    deps.append(f"syft_flwr=={__version__}")
    pyproject_conf["project"]["dependencies"] = deps

    pyproject_conf["tool"]["syft_flwr"] = {}

    # configure unique app name for each syft_flwr run
    base_app_name = pyproject_conf["project"]["name"]
    pyproject_conf["tool"]["syft_flwr"]["app_name"] = (
        f"{aggregator}_{base_app_name}_{int(time.time())}"
    )

    # always override the datasites and aggregator
    pyproject_conf["tool"]["syft_flwr"]["datasites"] = datasites
    pyproject_conf["tool"]["syft_flwr"]["aggregator"] = aggregator

    write_toml(flwr_pyproject, pyproject_conf)


def __validate_flwr_project_dir(flwr_project_dir: Union[str, Path]) -> Path:
    flwr_pyproject = flwr_project_dir / "pyproject.toml"
    flwr_main_py = flwr_project_dir / "main.py"

    if flwr_main_py.exists():
        raise FileExistsError(f"File '{flwr_main_py}' already exists")

    if not flwr_project_dir.exists():
        raise FileNotFoundError(f"Directory '{flwr_project_dir}' not found")

    if not flwr_pyproject.exists():
        raise FileNotFoundError(f"File '{flwr_pyproject}' not found")


def bootstrap(
    flwr_project_dir: Union[str, Path], aggregator: str, datasites: List[str]
) -> None:
    """Bootstrap a new syft-flwr project from the flwr project at the given path"""
    flwr_project_dir = Path(flwr_project_dir)

    if not is_valid_datasite(aggregator):
        raise ValueError(f"'{aggregator}' is not a valid datasite")

    for ds in datasites:
        if not is_valid_datasite(ds):
            raise ValueError(f"{ds} is not a valid datasite")

    __validate_flwr_project_dir(flwr_project_dir)
    __update_pyproject_toml(flwr_project_dir, aggregator, datasites)
    __copy_main_py(flwr_project_dir)

    logger.info(
        f"Successfully bootstrapped syft-flwr project at {flwr_project_dir} with datasites {datasites} and aggregator '{aggregator}' ✅"
    )
