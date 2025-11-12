import warnings
from pathlib import Path
from uuid import uuid4

from flwr.clientapp.client_app import LoadClientAppError
from flwr.common import Context
from flwr.common.object_ref import load_app
from flwr.common.record import RecordDict
from flwr.server.server_app import LoadServerAppError

from syft_flwr.config import load_flwr_pyproject
from syft_flwr.flower_client import syftbox_flwr_client
from syft_flwr.flower_server import syftbox_flwr_server
from syft_flwr.run_simulation import run

__all__ = ["syftbox_run_flwr_client", "syftbox_run_flwr_server", "run"]


# Suppress Pydantic deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic")


def syftbox_run_flwr_client(flower_project_dir: Path) -> None:
    pyproject_conf = load_flwr_pyproject(flower_project_dir)
    client_ref = pyproject_conf["tool"]["flwr"]["app"]["components"]["clientapp"]
    app_name = pyproject_conf["tool"]["syft_flwr"]["app_name"]

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

    syftbox_flwr_client(client_app, context, app_name)


def syftbox_run_flwr_server(flower_project_dir: Path) -> None:
    pyproject_conf = load_flwr_pyproject(flower_project_dir)
    datasites = pyproject_conf["tool"]["syft_flwr"]["datasites"]
    server_ref = pyproject_conf["tool"]["flwr"]["app"]["components"]["serverapp"]
    app_name = pyproject_conf["tool"]["syft_flwr"]["app_name"]

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

    syftbox_flwr_server(server_app, context, datasites, app_name)
