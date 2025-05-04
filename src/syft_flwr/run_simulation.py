import asyncio
import os
from pathlib import Path

from loguru import logger
from syft_rds.client.rds_client import RDSClient
from syft_rds.orchestra import remove_rds_stack_dir, setup_rds_server
from typing_extensions import Union

from syft_flwr.config import load_flwr_pyproject


def _setup_mock_rds_clients(
    project_dir: Path, aggregator: str, datasites: list[str]
) -> tuple[list[RDSClient], RDSClient]:
    """Setup mock RDS clients for the given project directory"""
    key = project_dir.name
    remove_rds_stack_dir(key)

    ds_stack = setup_rds_server(email=aggregator, key=key)
    ds_client = ds_stack.init_session(host=aggregator)

    do_clients = []
    for datasite in datasites:
        do_stack = setup_rds_server(email=datasite, key=key)
        do_client = do_stack.init_session(host=datasite)
        do_clients.append(do_client)

    return do_clients, ds_client


async def _run_main_py(
    main_py_path: Path,
    config_path: Path,
    client_email: str,
    log_dir: Path,
    dataset_path: Union[str, Path] | None = None,
) -> int:
    """Run the `main.py` file for a given client"""
    log_file_path = log_dir / f"{client_email}.log"

    # setting up env variables
    env = os.environ.copy()
    env["SYFTBOX_CLIENT_CONFIG_PATH"] = str(config_path)
    env["DATA_DIR"] = str(dataset_path)

    # running the main.py file asynchronously in a subprocess
    try:
        with open(log_file_path, "w") as f:
            process = await asyncio.create_subprocess_exec(
                "python",
                str(main_py_path),
                "-s",
                stdout=f,
                stderr=f,
                env=env,
            )
            return_code = await process.wait()
            logger.debug(
                f"`{client_email}` returns code {return_code} for running `{main_py_path}`"
            )
            return return_code
    except Exception as e:
        logger.error(f"Error running `{main_py_path}` for `{client_email}`: {e}")
        return 1


async def _run_simulated_flwr_project(
    project_dir: Path,
    do_clients: list[RDSClient],
    ds_client: RDSClient,
    mock_dataset_paths: list[Union[str, Path]],
) -> bool:
    """Run all clients and server concurrently"""
    run_success = True

    log_dir = project_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"📝 Log directory: {log_dir}")

    main_py_path = project_dir / "main.py"

    logger.info(
        f"Running DS client '{ds_client.email}' with config path {ds_client._syftbox_client.config_path}"
    )
    ds_task: asyncio.Task = asyncio.create_task(
        _run_main_py(
            main_py_path,
            ds_client._syftbox_client.config_path,
            ds_client.email,
            log_dir,
        )
    )

    client_tasks: list[asyncio.Task] = []
    for client,mock_dataset_path in zip(do_clients, mock_dataset_paths):
        # check if the client has a mock dataset path
        logger.info(
            f"Running DO client '{client.email}' with config path {client._syftbox_client.config_path} on mock dataset {mock_dataset_path}"
        )
        client_tasks.append(
            asyncio.create_task(
                _run_main_py(
                    main_py_path,
                    client._syftbox_client.config_path,
                    client.email,
                    log_dir,
                    mock_dataset_path,
                )
            )
        )

    ds_return_code = await ds_task
    if ds_return_code != 0:
        run_success = False

    # log out ds client logs
    with open(log_dir / f"{ds_client.email}.log", "r") as log_file:
        log_content = log_file.read().strip()
        logger.info(f"DS client '{ds_client.email}' logs:\n{log_content}")

    # cancel all client tasks if DS client returns
    logger.debug("Cancelling DO client tasks as DS client returned")
    for task in client_tasks:
        if not task.done():
            task.cancel()

    await asyncio.gather(*client_tasks, return_exceptions=True)

    return run_success



def _validate_bootstraped_project(project_dir: Path) -> None:
    """Validate a bootstraped `syft_flwr` project directory"""
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory {project_dir} does not exist")

    if not project_dir.is_dir():
        raise NotADirectoryError(f"Project directory {project_dir} is not a directory")

    if not (project_dir / "main.py").exists():
        raise FileNotFoundError(f"main.py not found at {project_dir}")

    if not (project_dir / "pyproject.toml").exists():
        raise FileNotFoundError(f"pyproject.toml not found at {project_dir}")


def _validate_mock_dataset_paths(mock_dataset_paths: list[str]) -> list[Path]:
    """Validate the mock dataset paths"""
    resolved_paths = []
    for path in mock_dataset_paths:
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Mock dataset path {path} does not exist")
        resolved_paths.append(path)
    return resolved_paths


def run(
    project_dir: Union[str, Path], mock_dataset_paths: list[Union[str, Path]]
) -> None:
    """Run a syft_flwr project in simulation mode over mock data"""

    project_dir = Path(project_dir).expanduser().resolve()
    _validate_bootstraped_project(project_dir)
    mock_dataset_paths = _validate_mock_dataset_paths(mock_dataset_paths)

    pyproject_conf = load_flwr_pyproject(project_dir)
    datasites = pyproject_conf["tool"]["syft_flwr"]["datasites"]
    aggregator = pyproject_conf["tool"]["syft_flwr"]["aggregator"]

    do_clients, ds_client = _setup_mock_rds_clients(project_dir, aggregator, datasites)
    

    async def main():
        run_success =await _run_simulated_flwr_project(
            project_dir, do_clients, ds_client, mock_dataset_paths
        )
        if run_success:
            logger.success("Simulation completed successfully ✅")
        else:
            logger.error("Simulation failed ❌")

    try:
        asyncio.get_running_loop()
        # We are in an environment with an existing event loop (like Jupyter)
        asyncio.create_task(main())
    except RuntimeError:
        # No existing event loop, create and run one (for scripts)
        asyncio.run(main())