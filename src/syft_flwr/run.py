from uuid import uuid4

from flwr.client.client_app import LoadClientAppError
from flwr.common import Context
from flwr.common.object_ref import load_app
from flwr.common.record import RecordSet
from flwr.server.server_app import LoadServerAppError

from syft_flwr.config import load_config
from syft_flwr.flower_client import syftbox_flwr_client
from syft_flwr.flower_server import syftbox_flwr_server

__all__ = ["syftbox_run_flwr_client", "syftbox_run_flwr_server"]


def syftbox_run_flwr_client(flower_project_dir):
    pyproject_conf = load_config(flower_project_dir)
    client_ref = pyproject_conf["tool"]["flwr"]["app"]["components"]["clientapp"]

    context = Context(
        run_id=uuid4().int,
        node_id=uuid4().int,
        node_config=pyproject_conf["tool"]["flwr"]["app"]["config"],
        state=RecordSet(),
        run_config=pyproject_conf["tool"]["flwr"]["app"]["config"],
    )
    client_app = load_app(
        client_ref,
        LoadClientAppError,
        flower_project_dir,
    )

    syftbox_flwr_client(client_app, context)


def syftbox_run_flwr_server(flower_project_dir):
    pyproject_conf = load_config(flower_project_dir)
    datasites = pyproject_conf["tool"]["syft_flwr"]["datasites"]
    server_ref = pyproject_conf["tool"]["flwr"]["app"]["components"]["serverapp"]

    context = Context(
        run_id=uuid4().int,
        node_id=uuid4().int,
        node_config=pyproject_conf["tool"]["flwr"]["app"]["config"],
        state=RecordSet(),
        run_config=pyproject_conf["tool"]["flwr"]["app"]["config"],
    )
    server_app = load_app(
        server_ref,
        LoadServerAppError,
        flower_project_dir,
    )

    syftbox_flwr_server(server_app, context, datasites)
