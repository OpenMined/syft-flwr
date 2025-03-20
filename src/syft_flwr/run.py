from uuid import uuid4

from flwr.client.client_app import LoadClientAppError
from flwr.server.server_app import LoadServerAppError
from flwr.common import Context
from flwr.common.object_ref import load_app
from flwr.common.record import RecordSet


from syft_flwr.flower_server import syftbox_flwr_server
from syft_flwr.config import load_and_validate

__all__ = ["syftbox_run_flwr_client", "syftbox_run_flwr_server"]


def syftbox_run_flwr_client(flower_project_dir):
    from syft_flwr.flower_client import syftbox_flwr_client

    pyproject_conf = load_and_validate(flower_project_dir)
    client_ref = pyproject_conf["tool"]["flwr"]["app"]["components"]["clientapp"]

    context = Context(
        run_id=uuid4().int,
        node_id=uuid4().int,
        node_config={},
        state=RecordSet(),
        run_config={}, 
    )
    client_app = load_app(
        client_ref,
        LoadClientAppError,
        flower_project_dir,
    )

    syftbox_flwr_client(client_app, context)


def syftbox_run_flwr_server(flower_project_dir):
    
    pyproject_conf = load_and_validate(flower_project_dir)
    server_ref = pyproject_conf["tool"]["flwr"]["app"]["components"]["serverapp"]

    context = Context(
        run_id=uuid4().int,
        node_id=uuid4().int,
        node_config={},
        state=RecordSet(),
        run_config={}, 
    )
    server_app = load_app(
        server_ref,
        LoadServerAppError,
        flower_project_dir,
    )

    syftbox_flwr_server(server_app, context)