from pathlib import Path
from uuid import uuid4

from flwr.client.client_app import LoadClientAppError
from flwr.common import Context
from flwr.common.object_ref import load_app
from flwr.server.server_app import LoadServerAppError
from loguru import logger
from syft_rds.orchestra import setup_rds_server
from typing_extensions import Union

from syft_flwr.config import load_flwr_pyproject
from syft_flwr.flower_client import syftbox_flwr_client
from syft_flwr.flower_server import syftbox_flwr_server
from syft_flwr.flwr_compatibility import RecordDict

__all__ = ["syftbox_run_flwr_client", "syftbox_run_flwr_server", "run"]


def syftbox_run_flwr_client(flower_project_dir):
    pyproject_conf = load_flwr_pyproject(flower_project_dir)
    client_ref = pyproject_conf["tool"]["flwr"]["app"]["components"]["clientapp"]

    context = Context(
        run_id=uuid4().int,
        node_id=uuid4().int,
        node_config=pyproject_conf["tool"]["flwr"]["app"]["config"],
        state=RecordDict(),
        run_config=pyproject_conf["tool"]["flwr"]["app"]["config"],
    )
    client_app = load_app(
        client_ref,
        LoadClientAppError,
        flower_project_dir,
    )

    syftbox_flwr_client(client_app, context)


def syftbox_run_flwr_server(flower_project_dir):
    pyproject_conf = load_flwr_pyproject(flower_project_dir)
    datasites = pyproject_conf["tool"]["syft_flwr"]["datasites"]
    server_ref = pyproject_conf["tool"]["flwr"]["app"]["components"]["serverapp"]

    context = Context(
        run_id=uuid4().int,
        node_id=uuid4().int,
        node_config=pyproject_conf["tool"]["flwr"]["app"]["config"],
        state=RecordDict(),
        run_config=pyproject_conf["tool"]["flwr"]["app"]["config"],
    )
    server_app = load_app(
        server_ref,
        LoadServerAppError,
        flower_project_dir,
    )

    syftbox_flwr_server(server_app, context, datasites)


def _simulated_do_client(email: str, key: str):
    do_stack_2 = setup_rds_server(email=email, key=key)
    return do_stack_2


def run(project_dir: Union[str, Path]) -> None:
    """Run a syft_flwr project in simulation mode over mock data"""
    project_dir = Path(project_dir).expanduser().resolve()
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory {project_dir} does not exist")

    if not project_dir.is_dir():
        raise NotADirectoryError(f"Project directory {project_dir} is not a directory")

    logger.info(
        f"Running syft_flwr project in simulation mode over mock data at {project_dir}"
    )
