"""
Integration test for FL Diabetes Prediction using syft-client's Google Drive transport.

This test verifies the complete federated learning workflow:
1. DS logs in and adds DO1/DO2 as peers
2. DO1 and DO2 log in and upload their datasets
3. DS discovers datasets and submits FL training jobs to both DOs
4. DOs approve jobs
5. DS runs Flower server (uv run main.py) + DO1/DO2 run Flower clients (process_approved_jobs)
   **simultaneously** for FL training to work
6. Training results are verified

Prerequisites:
- Google OAuth credentials (client_id, client_secret) in syft-flwr/credentials/
- Environment variables (automatically loaded from credentials/.env if it exists)
- Both syft-client and syft-flwr installed in editable mode

Setup:
    1. Create credentials/.env with your configuration:
        SYFT_EMAIL_DO1="do1@example.com"
        SYFT_EMAIL_DO2="do2@example.com"
        SYFT_EMAIL_DS="ds@example.com"
        SYFT_CRED_FNAME_DO1="do1.json"
        SYFT_CRED_FNAME_DO2="do2.json"
        SYFT_CRED_FNAME_DS="ds.json"
        SYFT_TOKEN_FNAME_DO1="token_do1.json"
        SYFT_TOKEN_FNAME_DO2="token_do2.json"
        SYFT_TOKEN_FNAME_DS="token_ds.json"

    2. Place OAuth credentials (from Google Cloud Console) in credentials/:
        - do1.json, do2.json, ds.json

    3. Run: pytest tests/integration/syft-client/fl_diabetes_two_dos_test.py -v -s
       (OAuth tokens will be generated automatically on first run)
"""

import multiprocessing
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from time import sleep

import pytest
import tomli
from common_rds_phases import (
    dos_approve_jobs,
    dos_upload_datasets,
    ds_discover_datasets,
)
from conftest import FL_PROJECT_DIR, TEST_LOGS_DIR
from loguru import logger

import syft_flwr

# Mark all tests in this module as slow (integration tests)
pytestmark = pytest.mark.slow

# ==============================================================================
# Multiprocessing Helper for DO Clients
# ==============================================================================


def _run_do_client_process(
    do_email: str,
    token_path: str,
    syftbox_folder: str,
    job_location_str: str,
    stdout_path: str,
    stderr_path: str,
    result_dict: dict,
):
    """Run DO Flower client in isolated subprocess.

    This function runs in a separate process with isolated os.environ.
    It creates a new SyftboxManager (which can access existing shared folders)
    and calls process_approved_jobs().

    Args:
        do_email: DO email address
        token_path: Path to Google OAuth token
        syftbox_folder: Path to SyftBox folder
        job_location_str: Path to job folder (for log copying)
        stdout_path: Where to copy stdout log
        stderr_path: Where to copy stderr log
        result_dict: Shared dict for returning results (multiprocessing.Manager().dict())
    """
    import time
    from pathlib import Path

    from loguru import logger
    from syft_client.sync.syftbox_manager import SyftboxManager, SyftboxManagerConfig

    try:
        # Set environment in this isolated process
        os.environ["GDRIVE_TOKEN_PATH"] = token_path

        # Small delay to let DS server start first
        sleep(5)

        logger.info(f"[Subprocess] Starting DO Flower client for {do_email}")
        logger.info(f"[Subprocess]   GDRIVE_TOKEN_PATH={token_path}")
        logger.info(f"[Subprocess]   SYFTBOX_FOLDER={syftbox_folder}")

        # Create a new manager for DO in this subprocess to run jobs
        config = SyftboxManagerConfig.for_google_drive_testing_connection(
            email=do_email,
            token_path=Path(token_path),
            syftbox_folder=syftbox_folder,  # Use existing folder, not random new one!
            use_in_memory_cache=False,
            only_ds=False,
            only_datasite_owner=True,
        )

        do_manager = SyftboxManager.from_config(config)

        # Setup callback for job handling (same as conftest.py)
        do_manager.proposed_file_change_handler.event_cache.add_callback(
            "on_event_local_write",
            do_manager.job_file_change_handler._handle_file_change,
        )

        logger.info(f"[Subprocess] Manager created for {do_email}, processing jobs...")

        start_time = time.time()
        do_manager.process_approved_jobs(stream_output=True)
        duration = time.time() - start_time

        result_dict["success"] = True
        result_dict["duration"] = duration
        logger.success(f"[Subprocess] {do_email} completed in {duration:.1f}s")

    except Exception as e:
        result_dict["error"] = str(e)
        logger.error(f"[Subprocess] {do_email} error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Copy DO job logs to central log directory
        if job_location_str:
            try:
                job_location = Path(job_location_str)
                src_stdout = job_location / "stdout.txt"
                src_stderr = job_location / "stderr.txt"
                if src_stdout.exists():
                    shutil.copy(src_stdout, stdout_path)
                if src_stderr.exists():
                    shutil.copy(src_stderr, stderr_path)
                logger.info(
                    f"[Subprocess] Logs copied to: {stdout_path}, {stderr_path}"
                )
            except Exception as log_err:
                logger.warning(f"[Subprocess] Could not copy logs: {log_err}")


# ==============================================================================
# Phase 3: Upload Datasets to DO Datastites
# ==============================================================================


def test_phase_03_upload_datasets(syft_managers, prepare_datasets):
    """Phase 3: DOs upload their dataset partitions."""
    logger.info("Phase 3: Uploading datasets to datastites...")
    dos_upload_datasets(syft_managers, prepare_datasets)
    logger.success("✅ Phase 3 complete: Both datasets uploaded and synced")


# ==============================================================================
# Phase 4: DS Discovers Datasets
# ==============================================================================


def test_phase_04_ds_discovers_datasets(syft_managers):
    """Phase 4: DS discovers datasets from DOs (peers already established in Phase 2.5)."""
    logger.info("Phase 4: DS discovering datasets...")
    ds_discover_datasets(syft_managers)
    logger.success("✅ Phase 4 complete: DS discovered all datasets")


# ==============================================================================
# Phase 5: Bootstrap FL Project
# ==============================================================================


def test_phase_05_bootstrap_fl_project(syft_managers):
    """Phase 5: Bootstrap FL project using syft_flwr for P2P federated learning."""
    logger.info("Phase 5: Bootstrapping FL project for distributed execution...")

    env = syft_managers["env"]
    ds_email = env["EMAIL_DS"]
    do_emails = [env["EMAIL_DO1"], env["EMAIL_DO2"]]

    # Create temp directory for FL code
    fl_temp_project = Path(tempfile.mkdtemp()) / "fl-diabetes-prediction"

    # Check FL project exists
    assert FL_PROJECT_DIR.exists(), f"FL project not found: {FL_PROJECT_DIR}"

    # Copy FL project
    shutil.copytree(FL_PROJECT_DIR, fl_temp_project)
    logger.info(f"Copied FL project to {fl_temp_project}")

    # Remove existing main.py if it exists (bootstrap() will create a new one)
    existing_main_py = fl_temp_project / "main.py"
    if existing_main_py.exists():
        existing_main_py.unlink()
        logger.info("Removed existing main.py (bootstrap will create new one)")

    # Bootstrap the project with syft_flwr
    # This will:
    # 1. Create main.py entry point that routes to client/server based on email
    # 2. Update pyproject.toml with syft_flwr config
    # Use P2P transport since tests use Google Drive API directly (like Colab notebooks)
    syft_flwr.bootstrap(
        fl_temp_project,
        aggregator=ds_email,
        datasites=do_emails,
        transport="p2p",
    )
    logger.info("Bootstrapped project with:")
    logger.info(f"  - Aggregator (DS): {ds_email}")
    logger.info(f"  - Datasites (DOs): {do_emails}")

    # Verify bootstrapped structure
    assert (
        fl_temp_project / "main.py"
    ).exists(), "main.py should be created by bootstrap()"
    assert (fl_temp_project / "fl_diabetes_prediction" / "task.py").exists()
    assert (fl_temp_project / "pyproject.toml").exists()

    # Verify bootstrap updated pyproject.toml
    with open(fl_temp_project / "pyproject.toml", "rb") as f:
        pyproject = tomli.load(f)
    assert (
        "syft_flwr" in pyproject["tool"]
    ), "Bootstrap should add [tool.syft_flwr] section"
    assert pyproject["tool"]["syft_flwr"]["aggregator"] == ds_email
    assert set(pyproject["tool"]["syft_flwr"]["datasites"]) == set(do_emails)

    logger.success("✅ FL project bootstrapped and validated")
    logger.info(f"Project path: {fl_temp_project}")

    # Store for later phases
    syft_managers["fl_project"] = fl_temp_project

    logger.success("✅ Phase 5 complete: FL project bootstrapped")


# ==============================================================================
# Phase 6: Submit FL Jobs to Data Owners
# ==============================================================================


def test_phase_06_submit_fl_jobs(syft_managers):
    """Phase 6: DS submits FL training jobs to both DOs."""
    logger.info("Phase 6: Submitting FL jobs to data owners...")

    ds_manager = syft_managers["ds"]
    env = syft_managers["env"]
    fl_project = syft_managers.get("fl_project")

    assert fl_project is not None, "FL project not bootstrapped - run phase 5 first"
    assert fl_project.exists(), f"FL project not found: {fl_project}"

    # Submit entire FL project folder (dependencies auto-parsed from pyproject.toml)
    # The folder contains: main.py (entry point), pyproject.toml, and fl_diabetes_prediction/
    logger.info(f"FL project folder: {fl_project}")

    # Submit job to DO1
    logger.info(f"Submitting FL job to {env['EMAIL_DO1']}...")
    ds_manager.submit_python_job(
        user=env["EMAIL_DO1"],
        code_path=str(fl_project),
        job_name="fl-diabetes-training",
        entrypoint="main.py",
    )
    logger.success("✅ FL job submitted to DO1")

    # Submit job to DO2
    logger.info(f"Submitting FL job to {env['EMAIL_DO2']}...")
    ds_manager.submit_python_job(
        user=env["EMAIL_DO2"],
        code_path=str(fl_project),
        job_name="fl-diabetes-training",
        entrypoint="main.py",
    )
    logger.success("✅ FL job submitted to DO2")

    # Wait for jobs to propagate
    sleep(2)

    logger.success("✅ Phase 6 complete: FL jobs submitted to both DOs")


# ==============================================================================
# Phase 7: DOs Review and Approve Jobs
# ==============================================================================


def test_phase_07_dos_approve_jobs(syft_managers):
    """Phase 7: DOs review and approve FL jobs from DS."""
    logger.info("Phase 7: DOs approving FL jobs...")
    dos_approve_jobs(syft_managers)
    logger.success("✅ Phase 7 complete: Both DOs approved FL jobs")


# ==============================================================================
# Phase 8: Execute FL Jobs (DS Server + DO1/DO2 Clients simultaneously)
# ==============================================================================


def test_phase_08_execute_fl_jobs(syft_managers):
    """Phase 8: Run DS Flower server and DO1/DO2 Flower clients simultaneously.

    The FL training requires:
    - DS to run main.py (Flower server) via `uv run main.py`
    - DO1 and DO2 to run process_approved_jobs() (Flower clients)

    All three must run at the same time for FL training to work.
    This mirrors the notebook flow where DS, DO1, and DO2 run in separate Colab instances.
    """
    logger.info("Phase 8: Executing FL jobs (DS server + DO1/DO2 clients)...")

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]
    ds_manager = syft_managers["ds"]
    env = syft_managers["env"]
    fl_project = syft_managers.get("fl_project")

    assert fl_project is not None, "FL project not bootstrapped - run phase 5 first"

    # Prepare environment for DS server
    ds_email = env["EMAIL_DS"]
    ds_syftbox_folder = ds_manager.syftbox_folder
    ds_token_path = env["token_path_ds"]

    # Set OUTPUT_DIR for trained weights to be saved in DS's syftbox folder
    output_dir = ds_syftbox_folder / ds_email / "fl_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    ds_env = os.environ.copy()
    ds_env["SYFTBOX_EMAIL"] = ds_email
    ds_env["SYFTBOX_FOLDER"] = str(ds_syftbox_folder)
    ds_env["GDRIVE_TOKEN_PATH"] = str(ds_token_path)  # For GDriveFileIO authentication
    ds_env["OUTPUT_DIR"] = str(output_dir)  # Where trained weights will be saved

    # Store output_dir for Phase 9 verification
    syft_managers["fl_output_dir"] = output_dir

    # DS result container (local, not shared across processes)
    ds_result = {"success": False, "error": None, "process": None}

    # Log files for debugging (stream output in real-time)
    # Clear old logs before each test run
    if TEST_LOGS_DIR.exists():
        shutil.rmtree(TEST_LOGS_DIR)
    TEST_LOGS_DIR.mkdir(exist_ok=True)
    ds_stdout_path = TEST_LOGS_DIR / "ds_stdout.log"
    ds_stderr_path = TEST_LOGS_DIR / "ds_stderr.log"
    do1_stdout_path = TEST_LOGS_DIR / "do1_stdout.log"
    do1_stderr_path = TEST_LOGS_DIR / "do1_stderr.log"
    do2_stdout_path = TEST_LOGS_DIR / "do2_stdout.log"
    do2_stderr_path = TEST_LOGS_DIR / "do2_stderr.log"
    logger.info(f"All logs will be written to: {TEST_LOGS_DIR}")

    # Get DO job locations for log access
    do1_jobs = do1_manager.jobs
    do1_approved = [j for j in do1_jobs if j.status == "approved"]
    do1_job_location = do1_approved[0].location if do1_approved else None
    if do1_job_location:
        logger.info(f"DO1 job location: {do1_job_location}")

    do2_jobs = do2_manager.jobs
    do2_approved = [j for j in do2_jobs if j.status == "approved"]
    do2_job_location = do2_approved[0].location if do2_approved else None
    if do2_job_location:
        logger.info(f"DO2 job location: {do2_job_location}")

    # Pre-install dependencies (mirrors ds.ipynb cell JyInjbVp_ye6)
    # This ensures packages are ready before parallel execution starts
    logger.info("Pre-installing FL project dependencies...")
    install_result = subprocess.run(
        ["uv", "sync"],
        cwd=str(fl_project),
        env=ds_env,
        capture_output=True,
        timeout=300,  # 5 min timeout for installation
    )
    if install_result.returncode != 0:
        logger.warning(f"uv sync warning: {install_result.stderr.decode()}")
    else:
        logger.success("Dependencies installed successfully")

    def run_ds_server():
        """Run DS Flower server via uv run main.py (mirrors ds.ipynb cell KxOOWlwm_3MB)"""
        ds_stdout_file = None
        ds_stderr_file = None
        try:
            logger.info(f"Starting DS Flower server: uv run {fl_project / 'main.py'}")
            logger.info(f"  SYFTBOX_EMAIL={ds_email}")
            logger.info(f"  SYFTBOX_FOLDER={ds_syftbox_folder}")
            logger.info(f"  Logs: {ds_stdout_path}, {ds_stderr_path}")

            # Open log files for streaming output
            ds_stdout_file = open(ds_stdout_path, "w")
            ds_stderr_file = open(ds_stderr_path, "w")

            process = subprocess.Popen(
                ["uv", "run", str(fl_project / "main.py")],
                cwd=str(fl_project),
                env=ds_env,
                stdout=ds_stdout_file,
                stderr=ds_stderr_file,
            )
            ds_result["process"] = process

            # Wait for process to complete
            process.wait(timeout=600)  # 10 min timeout

            if process.returncode == 0:
                ds_result["success"] = True
                logger.success("DS Flower server completed successfully")
            else:
                ds_result["error"] = f"DS server exited with code {process.returncode}"
                logger.error(ds_result["error"])

        except subprocess.TimeoutExpired:
            if ds_result["process"]:
                ds_result["process"].kill()
            ds_result["error"] = "DS server timed out after 10 minutes"
            logger.error(ds_result["error"])
        except Exception as e:
            ds_result["error"] = str(e)
            logger.error(f"DS server error: {e}")
        finally:
            if ds_stdout_file:
                ds_stdout_file.close()
            if ds_stderr_file:
                ds_stderr_file.close()
            logger.info(f"DS logs saved to: {ds_stdout_path}, {ds_stderr_path}")

    # Start all three in parallel (mirrors running DS, DO1, DO2 notebooks simultaneously)
    start_time = time.time()

    # Use multiprocessing.Manager for shared result dicts
    mp_manager = multiprocessing.Manager()
    do1_result = mp_manager.dict({"success": False, "error": None, "duration": 0.0})
    do2_result = mp_manager.dict({"success": False, "error": None, "duration": 0.0})

    # DS runs as thread (uses subprocess.Popen internally)
    ds_thread = threading.Thread(target=run_ds_server, name="DS-Server")

    # DO1 and DO2 run as separate PROCESSES with isolated os.environ
    # This allows them to run in PARALLEL without GDRIVE_TOKEN_PATH race conditions
    do1_process = multiprocessing.Process(
        target=_run_do_client_process,
        args=(
            env["EMAIL_DO1"],
            str(env["token_path_do1"]),
            str(do1_manager.syftbox_folder),
            str(do1_job_location) if do1_job_location else "",
            str(do1_stdout_path),
            str(do1_stderr_path),
            do1_result,
        ),
        name="DO1-Client",
    )
    do2_process = multiprocessing.Process(
        target=_run_do_client_process,
        args=(
            env["EMAIL_DO2"],
            str(env["token_path_do2"]),
            str(do2_manager.syftbox_folder),
            str(do2_job_location) if do2_job_location else "",
            str(do2_stdout_path),
            str(do2_stderr_path),
            do2_result,
        ),
        name="DO2-Client",
    )

    logger.info("Starting DS server and DO1/DO2 clients in parallel...")
    logger.info("  DS: thread with subprocess.Popen")
    logger.info(
        "  DO1/DO2: separate PROCESSES with isolated os.environ (truly parallel)"
    )
    ds_thread.start()
    do1_process.start()
    do2_process.start()

    # Wait for all to complete
    do1_process.join(timeout=660)  # 11 min timeout
    do2_process.join(timeout=660)
    ds_thread.join(timeout=660)

    total_duration = time.time() - start_time

    # Check results
    if do1_result["error"]:
        logger.error(f"DO1 failed: {do1_result['error']}")
    if do2_result["error"]:
        logger.error(f"DO2 failed: {do2_result['error']}")
    if ds_result["error"]:
        logger.error(f"DS failed: {ds_result['error']}")

    # All should succeed for FL training to work
    assert do1_result["success"] and do2_result["success"] and ds_result["success"], (
        f"FL training failed - DO1: {do1_result['error']}, "
        f"DO2: {do2_result['error']}, DS: {ds_result['error']}"
    )

    logger.success(
        f"✅ Phase 8 complete: FL training finished in {total_duration:.1f}s "
        f"(DO1: {do1_result['duration']:.1f}s, DO2: {do2_result['duration']:.1f}s)"
    )


# ==============================================================================
# Phase 9: Verify Training Results
# ==============================================================================


def test_phase_09_verify_training_results(syft_managers):
    """Phase 9: Verify training results and check trained weights exist for DS."""
    logger.info("Phase 9: Verifying FL training results...")

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]
    ds_manager = syft_managers["ds"]

    # Sync results back to DS
    do1_manager.sync()
    do2_manager.sync()
    sleep(2)
    ds_manager.sync()

    # Get DO1 job results
    do1_jobs = do1_manager.jobs
    assert len(do1_jobs) > 0, "No jobs found for DO1"
    do1_job = do1_jobs[0]

    # Read DO1 stdout
    logger.info("Reading DO1 job stdout...")
    do1_stdout = str(do1_job.stdout)
    logger.info(f"\nDO1 Output:\n{do1_stdout}\n")
    do1_stderr = str(do1_job.stderr)
    logger.info(f"\nDO1 Error Output:\n{do1_stderr}\n")

    # Get DO2 job results
    do2_jobs = do2_manager.jobs
    assert len(do2_jobs) > 0, "No jobs found for DO2"
    do2_job = do2_jobs[0]

    logger.info("Reading DO2 job stdout and stderr...")
    do2_stdout = str(do2_job.stdout)
    logger.info(f"\nDO2 Output:\n{do2_stdout}\n")
    do2_stderr = str(do2_job.stderr)
    logger.info(f"\nDO2 Error Output:\n{do2_stderr}\n")

    # =========================================================================
    # Verify trained weights are available for DS
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("VERIFYING TRAINED WEIGHTS FOR DS")
    logger.info("=" * 60)

    # Weights are saved to OUTPUT_DIR/weights/ (set in Phase 8)
    fl_output_dir = syft_managers.get("fl_output_dir")
    if fl_output_dir:
        weights_dir = fl_output_dir / "weights"
    else:
        # Fallback to default path
        weights_dir = Path.home() / ".syftbox" / "rds" / "weights"

    logger.info(f"Checking weights directory: {weights_dir}")

    assert weights_dir.exists(), f"Weights directory not found: {weights_dir}"

    # Find all .safetensors weight files
    weight_files = list(weights_dir.glob("parameters_round_*.safetensors"))
    logger.info(f"Found {len(weight_files)} weight file(s):")
    for wf in sorted(weight_files):
        file_size = wf.stat().st_size
        logger.info(f"  - {wf.name} ({file_size} bytes)")

    # Verify at least one weight file exists (from at least one FL round)
    assert len(weight_files) > 0, "No trained weight files found!"

    # Verify the latest weights file is readable
    latest_weights = max(weight_files, key=lambda p: p.stat().st_mtime)
    assert latest_weights.stat().st_size > 0, "Latest weights file is empty!"
    logger.success(f"✅ DS can access trained weights: {latest_weights.name}")

    # Load and verify the weights structure
    from safetensors.numpy import load_file

    weights_dict = load_file(str(latest_weights))
    logger.info(f"  Weight layers: {list(weights_dict.keys())}")
    logger.success("✅ Trained weights verified and loadable!")

    logger.info("=" * 60)

    # Cleanup FL project temp directory
    fl_project = syft_managers.get("fl_project")
    if fl_project and fl_project.parent.exists():
        shutil.rmtree(fl_project.parent, ignore_errors=True)
        logger.info("✅ FL code temp directory cleaned up")

    logger.success("✅ Phase 9 complete: FL training results verified!")
