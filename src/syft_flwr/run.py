import asyncio
import os
import shutil
import tempfile
from asyncio import Task
from pathlib import Path
from uuid import uuid4

from flwr.client.client_app import LoadClientAppError
from flwr.common import Context
from flwr.common.object_ref import load_app
from flwr.server.server_app import LoadServerAppError
from loguru import logger
from syft_rds.client.rds_client import RDSClient
from syft_rds.orchestra import setup_rds_server
from typing_extensions import Union

from syft_flwr.bootstrap import bootstrap
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


def __reset_db(key):
    root_path = Path(tempfile.gettempdir(), key)

    if root_path.exists():
        try:
            shutil.rmtree(root_path)
            logger.debug(f"Successfully Reset Flwr DB ✅ at {root_path}")
        except Exception as e:
            logger.warning(f"Failed to reset directory {root_path}: {e}")
    else:
        logger.debug(f"Skipping Reset , as path does not exist at {root_path}")


def __setup_mock_clients(
    project_dir: Path, aggregator: str, datasites: list[str]
) -> tuple[list[RDSClient], RDSClient]:
    key = project_dir.name
    __reset_db(key)

    ds_stack = setup_rds_server(email=aggregator, key=key)
    ds_client = ds_stack.init_session(host=aggregator)

    do_clients = []
    for datasite in datasites:
        do_stack = setup_rds_server(email=datasite, key=key)
        do_client = do_stack.init_session(host=datasite)
        do_clients.append(do_client)

    return do_clients, ds_client


async def __run_main(
    project_dir: Path,
    config_path: Path,
    client_email: str = None,
    data_path: Union[str, Path] = None,
) -> None:
    """Run a main.py file as a subprocess using asyncio"""
    logger.info(f"Running main.py at {project_dir}")
    main_py_path = Path(project_dir) / "main.py"
    if not main_py_path.exists():
        logger.error(f"main.py not found at {main_py_path}")
        return

    # Create environment with the SYFTBOX_CLIENT_CONFIG_PATH set
    env = os.environ.copy()
    env["SYFTBOX_CLIENT_CONFIG_PATH"] = str(config_path)
    if data_path:
        env["DATA_DIR"] = str(data_path)

    try:
        # Create logs directory if it doesn't exist
        logs_dir = project_dir / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Determine log file name
        log_file = logs_dir / f"{client_email}.log"

        logger.info(
            f"Starting subprocess: python {main_py_path} -s (logs to {log_file})"
        )

        # Open log file for writing
        with open(log_file, "w") as log_output:
            process = await asyncio.create_subprocess_exec(
                "python",
                str(main_py_path),
                "-s",
                stdout=log_output,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )

            # Wait for the process to complete
            return_code = await process.wait()
            logger.info(
                f"Process {client_email or 'server'} completed with return code: {return_code}"
            )
            return return_code

    except Exception as e:
        logger.error(f"Failed to run main.py: {e}")
        return None


async def __run_async(
    project_dir: Path, do_clients: list[RDSClient], ds_client: RDSClient
) -> None:
    """Run all clients and server concurrently"""
    # Prepare tasks for all clients and server
    client_processes: list[Task] = []

    # Add client tasks
    for i, do_client in enumerate(do_clients):
        logger.info(
            f"Preparing DO client {do_client.email} with config path {do_client._syftbox_client.config_path}"
        )
        client_process: Task = asyncio.create_task(
            __run_main(
                project_dir=project_dir,
                config_path=do_client._syftbox_client.config_path,
                client_email=do_client.email,
                data_path=project_dir / "data" / "cifar10" / f"cifar10_part_{i}",
            )
        )
        client_processes.append(client_process)

    # Add server task
    logger.info(
        f"Preparing DS server {ds_client.email} with config path {ds_client._syftbox_client.config_path}"
    )
    server_process: Task = asyncio.create_task(
        __run_main(
            project_dir=project_dir,
            config_path=ds_client._syftbox_client.config_path,
            client_email=ds_client.email,
        )
    )

    # Wait for server to complete first
    server_return_code = await server_process
    logger.info(f"Server process completed with return code: {server_return_code}")

    # Cancel all client processes if server returns
    for process in client_processes:
        if not process.done():
            process.cancel()

    # Wait for all client processes to be cancelled or complete
    if client_processes:
        await asyncio.gather(*client_processes, return_exceptions=True)

    logger.info("All processes terminated after server completion")


def run(project_dir: Union[str, Path]) -> None:
    """Run a syft_flwr project in simulation mode over mock data"""
    project_dir = Path(project_dir).expanduser().resolve()
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory {project_dir} does not exist")

    if not project_dir.is_dir():
        raise NotADirectoryError(f"Project directory {project_dir} is not a directory")

    # TODO: get datasites and aggregator from pyproject.toml after the DS bootstraps
    datasites = ["do1@openmined.org", "do2@openmined.org"]
    aggregator = "ds@openmined.org"

    logger.info(
        f"Running `syft_flwr` project in simulation mode over mock data at {project_dir} with datasites {datasites} and aggregator '{aggregator}'"
    )
    try:
        bootstrap(project_dir, aggregator, datasites)
    except Exception as e:
        logger.error(f"Failed to bootstrap project: {e}")
    # END TODO

    do_clients, ds_client = __setup_mock_clients(project_dir, aggregator, datasites)

    import nest_asyncio

    nest_asyncio.apply()  # allow asyncio to run in Jupyter notebooks

    # Run all clients and server concurrently using asyncio
    asyncio.run(__run_async(project_dir, do_clients, ds_client))
