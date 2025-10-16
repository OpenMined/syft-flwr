import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TypeAlias

from loguru import logger
from syft_core import Client
from syft_crypto import did_path, ensure_bootstrap, get_did_document, private_key_path
from syft_rds import init_session
from syft_rds.client.rds_client import RDSClient
from typing_extensions import Optional, Union

from syft_flwr.config import load_flwr_pyproject
from syft_flwr.consts import SYFT_FLWR_ENCRYPTION_ENABLED
from syft_flwr.utils import create_temp_client

PathLike: TypeAlias = Union[str, os.PathLike, Path]


def remove_rds_stack_dir(
    key: str = "shared_client_dir", root_dir: Optional[PathLike] = None
) -> None:
    root_path = (
        Path(root_dir).resolve() / key if root_dir else Path(tempfile.gettempdir(), key)
    )

    if not root_path.exists():
        logger.warning(f"⚠️ Skipping removal, as path {root_path} does not exist")
        return None

    try:
        shutil.rmtree(root_path)
        logger.info(f"✅ Successfully removed directory {root_path}")
    except Exception as e:
        logger.error(f"❌ Failed to remove directory {root_path}: {e}")


def _setup_mock_rds_clients(
    project_dir: Path, aggregator: str, datasites: list[str]
) -> tuple[Path, list[RDSClient], RDSClient]:
    """Setup mock RDS clients for the given project directory"""
    simulated_syftbox_network_dir = Path(tempfile.gettempdir(), project_dir.name)
    remove_rds_stack_dir(root_dir=simulated_syftbox_network_dir)

    ds_syftbox_client = create_temp_client(
        email=aggregator, workspace_dir=simulated_syftbox_network_dir
    )
    ds_rds_client = init_session(
        host=aggregator, email=aggregator, syftbox_client=ds_syftbox_client
    )

    do_rds_clients = []
    for datasite in datasites:
        do_syftbox_client = create_temp_client(
            email=datasite, workspace_dir=simulated_syftbox_network_dir
        )
        do_rds_client = init_session(
            host=datasite, email=datasite, syftbox_client=do_syftbox_client
        )
        do_rds_clients.append(do_rds_client)

    return simulated_syftbox_network_dir, do_rds_clients, ds_rds_client


def _bootstrap_encryption_keys(
    do_clients: list[RDSClient], ds_client: RDSClient
) -> None:
    """Bootstrap the encryption keys for all clients if encryption is enabled."""
    # Check if encryption is enabled
    encryption_enabled = (
        os.environ.get(SYFT_FLWR_ENCRYPTION_ENABLED, "true").lower() != "false"
    )

    if not encryption_enabled:
        logger.warning("⚠️ Encryption disabled - skipping key bootstrap")
        return

    logger.info("🔐 Bootstrapping encryption keys for all participants...")

    all_syftbox_clients: list[Client] = []

    # Bootstrap server
    try:
        server_client: Client = ds_client._syftbox_client
        ensure_bootstrap(server_client)
        server_client_did_path = did_path(server_client, server_client.email)
        server_client_private_key_path = private_key_path(server_client)
        logger.debug(
            f"✅ Server {ds_client.email} bootstrapped with private encryption keys at {server_client_private_key_path} and did path at {server_client_did_path}"
        )
        all_syftbox_clients.append(server_client)
    except Exception as e:
        logger.error(f"❌ Failed to bootstrap server {ds_client.email}: {e}")
        raise

    # Bootstrap each client
    for do_client in do_clients:
        try:
            client: Client = do_client._syftbox_client
            ensure_bootstrap(client)
            client_did_path = did_path(client, client.email)
            client_did_doc = get_did_document(client, client.email)
            client_private_key_path = private_key_path(client)
            logger.debug(
                f"✅ Client {do_client.email} bootstrapped with private encryption keys at {client_private_key_path} and did path at {client_did_path} with content: {client_did_doc}"
            )
            all_syftbox_clients.append(client)
        except Exception as e:
            logger.error(f"❌ Failed to bootstrap client {do_client.email}: {e}")
            raise

    # Verify all DID documents are accessible
    for checking_client in all_syftbox_clients:
        for target_client in all_syftbox_clients:
            if checking_client.email != target_client.email:
                # Verify that checking_client can see target_client's DID document
                did_file_path = did_path(checking_client, target_client.email)
                if did_file_path.exists():
                    logger.debug(
                        f"✅ {checking_client.email} can see {target_client.email}'s DID at {did_file_path}"
                    )
                else:
                    logger.warning(
                        f"⚠️ {checking_client.email} cannot find {target_client.email}'s DID at {did_file_path}"
                    )

    logger.info("🔐 All participants bootstrapped for E2E encryption ✅✅✅")


async def _run_main_py(
    main_py_path: Path,
    config_path: Path,
    client_email: str,
    log_dir: Path,
    dataset_path: Optional[Union[str, Path]] = None,
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
                sys.executable,  # Use the current Python executable
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

    log_dir = project_dir / "simulation_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📝 Log directory: {log_dir}")

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
    for client, mock_dataset_path in zip(do_clients, mock_dataset_paths):
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


def validate_bootstraped_project(project_dir: Path) -> None:
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
) -> Union[bool, asyncio.Task]:
    """Run a syft_flwr project in simulation mode over mock data.

    Returns:
        bool: True if simulation succeeded, False otherwise (synchronous execution)
        asyncio.Task: Task handle if running in async environment (e.g., Jupyter)
    """

    project_dir = Path(project_dir).expanduser().resolve()
    validate_bootstraped_project(project_dir)
    mock_dataset_paths = _validate_mock_dataset_paths(mock_dataset_paths)

    # Skip module validation during testing to avoid parallel test issues
    skip_module_check = (
        os.environ.get("SYFT_FLWR_SKIP_MODULE_CHECK", "false").lower() == "true"
    )
    pyproject_conf = load_flwr_pyproject(
        project_dir, check_module=not skip_module_check
    )
    datasites = pyproject_conf["tool"]["syft_flwr"]["datasites"]
    aggregator = pyproject_conf["tool"]["syft_flwr"]["aggregator"]

    simulated_syftbox_network_dir, do_clients, ds_client = _setup_mock_rds_clients(
        project_dir, aggregator, datasites
    )

    _bootstrap_encryption_keys(do_clients, ds_client)

    simulation_success = False  # Track success status

    async def main():
        nonlocal simulation_success
        try:
            run_success = await _run_simulated_flwr_project(
                project_dir, do_clients, ds_client, mock_dataset_paths
            )
            simulation_success = run_success
            if run_success:
                logger.success("Simulation completed successfully ✅")
            else:
                logger.error("Simulation failed ❌")
        except Exception as e:
            logger.error(f"Simulation failed ❌: {e}")
            simulation_success = False
        finally:
            # Clean up the RDS stack
            remove_rds_stack_dir(simulated_syftbox_network_dir)
            logger.debug(f"Removed RDS stack: {simulated_syftbox_network_dir}")
            # Also remove the .syftbox folder that saves the config files and private keys
            remove_rds_stack_dir(simulated_syftbox_network_dir.parent / ".syftbox")

        return simulation_success

    try:
        loop = asyncio.get_running_loop()
        logger.debug(f"Running in an environment with an existing event loop {loop}")
        # We are in an environment with an existing event loop (like Jupyter)
        task = asyncio.create_task(main())
        return task  # Return the task so callers can await it
    except RuntimeError:
        logger.debug("No existing event loop, creating and running one")
        # No existing event loop, create and run one (for scripts)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
        loop.close()
        return simulation_success  # Return success status for synchronous execution
