"""
Integration test for FL Diabetes Prediction with a SINGLE Data Owner.

This test verifies the FL workflow with one DO:
1. DS logs in and adds DO as peer
2. DO logs in and uploads dataset
3. DS discovers dataset and submits FL training job
4. DO approves job
5. DS runs Flower server + DO runs Flower client concurrently
6. Training results are verified

Prerequisites:
- Google OAuth credentials (client_id, client_secret) in syft-flwr/credentials/
- Environment variables (automatically loaded from credentials/.env if it exists)
- Both syft-client and syft-flwr installed in editable mode

Setup:
    1. Create credentials/.env with your configuration:
        SYFT_EMAIL_DO1="do1@example.com"
        SYFT_EMAIL_DS="ds@example.com"
        SYFT_CRED_FNAME_DO1="do1.json"
        SYFT_CRED_FNAME_DS="ds.json"
        SYFT_TOKEN_FNAME_DO1="token_do1.json"
        SYFT_TOKEN_FNAME_DS="token_ds.json"

    2. Place OAuth credentials (from Google Cloud Console) in credentials/:
        - do1.json, ds.json

    3. Run: pytest tests/integration/syft-client/fl_diabetes_one_do_test.py -v -s
        (OAuth tokens will be generated automatically on first run)
"""

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
    do_upload_dataset,
    ds_discover_dataset_from_do,
)
from conftest import FL_PROJECT_DIR
from loguru import logger

import syft_flwr

# Mark all tests in this module as slow (integration tests)
pytestmark = pytest.mark.slow

# ==============================================================================
# Phase 3: Upload Dataset to DO1 Datasite
# ==============================================================================


def test_phase_03_upload_dataset(syft_managers_single_do, prepare_datasets):
    """Phase 3: DO1 uploads their dataset partition."""
    logger.info("Phase 3: Uploading dataset to DO1 datasite...")

    do_upload_dataset(
        do_manager=syft_managers_single_do["do1"],
        dataset_dir=prepare_datasets,
        partition_index=0,
        do_name="DO1",
    )

    logger.success("✅ Phase 3 complete: DO1 dataset uploaded and synced")


# ==============================================================================
# Phase 4: DS Discovers Dataset
# ==============================================================================


def test_phase_04_ds_discovers_dataset(syft_managers_single_do):
    """Phase 4: DS discovers dataset from DO1."""
    logger.info("Phase 4: DS discovering dataset...")

    ds_manager = syft_managers_single_do["ds"]
    env = syft_managers_single_do["env"]

    ds_discover_dataset_from_do(
        ds_manager=ds_manager,
        do_email=env["EMAIL_DO1"],
        do_name="DO1",
    )

    logger.success("✅ Phase 4 complete: DS discovered DO1's dataset")


# ==============================================================================
# Phase 5: Bootstrap FL Project (Single DO)
# ==============================================================================


def test_phase_05_bootstrap_fl_project(syft_managers_single_do):
    """Phase 5: Bootstrap FL project for single DO execution."""
    logger.info("Phase 5: Bootstrapping FL project for single DO...")

    env = syft_managers_single_do["env"]
    ds_email = env["EMAIL_DS"]
    do1_email = env["EMAIL_DO1"]

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

    # Bootstrap the project with syft_flwr - SINGLE DO only
    syft_flwr.bootstrap(
        fl_temp_project,
        aggregator=ds_email,
        datasites=[do1_email],  # Only DO1
        transport="p2p",
    )
    logger.info("Bootstrapped project with:")
    logger.info(f"  - Aggregator (DS): {ds_email}")
    logger.info(f"  - Datasites (DOs): [{do1_email}]")

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
    assert pyproject["tool"]["syft_flwr"]["datasites"] == [do1_email]

    logger.success("✅ FL project bootstrapped and validated")
    logger.info(f"Project path: {fl_temp_project}")

    # Store for later phases
    syft_managers_single_do["fl_project"] = fl_temp_project

    logger.success("✅ Phase 5 complete: FL project bootstrapped for single DO")


# ==============================================================================
# Phase 6: Submit FL Job to DO1
# ==============================================================================


def test_phase_06_submit_fl_job(syft_managers_single_do):
    """Phase 6: DS submits FL training job to DO1."""
    logger.info("Phase 6: Submitting FL job to DO1...")

    ds_manager = syft_managers_single_do["ds"]
    env = syft_managers_single_do["env"]
    fl_project = syft_managers_single_do.get("fl_project")

    assert fl_project is not None, "FL project not bootstrapped - run phase 5 first"
    assert fl_project.exists(), f"FL project not found: {fl_project}"

    # Submit entire FL project folder to DO1 only
    logger.info(f"FL project folder: {fl_project}")
    logger.info(f"Submitting FL job to {env['EMAIL_DO1']}...")

    try:
        ds_manager.submit_python_job(
            user=env["EMAIL_DO1"],
            code_path=str(fl_project),
            job_name="fl-diabetes-training",
        )
        logger.success("✅ FL job submitted to DO1")
    except Exception as e:
        logger.error(f"❌ Failed to submit FL job: {e}")
        import traceback

        logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise

    # Wait for job to propagate
    sleep(2)

    logger.success("✅ Phase 6 complete: FL job submitted to DO1")


# ==============================================================================
# Phase 7: DO1 Reviews and Approves Job
# ==============================================================================


def test_phase_07_do1_approves_job(syft_managers_single_do):
    """Phase 7: DO1 reviews and approves FL job from DS."""
    logger.info("Phase 7: DO1 approving FL job...")

    do1_manager = syft_managers_single_do["do1"]

    # Sync to get the job
    do1_manager.sync()
    sleep(1)

    # Get jobs and approve
    jobs = do1_manager.jobs
    assert len(jobs) > 0, "No jobs found for DO1"

    inbox_jobs = [j for j in jobs if j.status == "inbox"]
    assert len(inbox_jobs) > 0, "No inbox jobs to approve for DO1"

    for job in inbox_jobs:
        logger.info(f"DO1 approving job: {job.name}")
        job.approve()

    logger.success("✅ Phase 7 complete: DO1 approved FL job")


# ==============================================================================
# Phase 8: Execute FL Job (DS Server + DO1 Client simultaneously)
# ==============================================================================


def test_phase_08_execute_fl_job(syft_managers_single_do):
    """Phase 8: Run DS Flower server and DO1 Flower client simultaneously.

    The FL training requires:
    - DS to run main.py (Flower server) via `uv run main.py`
    - DO1 to run process_approved_jobs() (Flower client)

    Both must run at the same time for FL training to work.
    This mirrors the notebook flow where DS and DO run in separate Colab instances.
    """
    logger.info("Phase 8: Executing FL job (DS server + DO1 client)...")

    do1_manager = syft_managers_single_do["do1"]
    ds_manager = syft_managers_single_do["ds"]
    env = syft_managers_single_do["env"]
    fl_project = syft_managers_single_do.get("fl_project")

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
    syft_managers_single_do["fl_output_dir"] = output_dir

    # Results containers
    do1_result = {"success": False, "error": None, "duration": 0.0}
    ds_result = {"success": False, "error": None, "process": None}

    # Log files for debugging (stream output in real-time)
    log_dir = Path("/tmp/syft_flwr_test_logs")
    # Clear old logs before each test run
    if log_dir.exists():
        shutil.rmtree(log_dir)
    log_dir.mkdir(exist_ok=True)
    ds_stdout_path = log_dir / "ds_stdout.log"
    ds_stderr_path = log_dir / "ds_stderr.log"
    do1_stdout_path = log_dir / "do1_stdout.log"
    do1_stderr_path = log_dir / "do1_stderr.log"
    logger.info(f"All logs will be written to: {log_dir}")

    # Get DO1 job location for log access
    do1_jobs = do1_manager.jobs
    approved_jobs = [j for j in do1_jobs if j.status == "approved"]
    do1_job_location = approved_jobs[0].location if approved_jobs else None
    if do1_job_location:
        logger.info(f"DO1 job location: {do1_job_location}")

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

    def run_do1_client():
        """Run DO1 Flower client via process_approved_jobs() (mirrors do.ipynb cell 17)"""
        try:
            # Small delay to let DS server start first
            sleep(5)

            # Set GDRIVE_TOKEN_PATH for the job subprocess to authenticate with Google Drive
            # The job_runner does os.environ.copy(), so this will be inherited
            do1_token_path = env["token_path_do1"]
            os.environ["GDRIVE_TOKEN_PATH"] = str(do1_token_path)
            logger.info(f"Set GDRIVE_TOKEN_PATH={do1_token_path} for DO1 job")

            logger.info("Starting DO1 Flower client (process_approved_jobs)...")
            start_time = time.time()
            do1_manager.process_approved_jobs()
            do1_result["duration"] = time.time() - start_time
            do1_result["success"] = True
            logger.success(f"DO1 client completed in {do1_result['duration']:.1f}s")
        except Exception as e:
            do1_result["error"] = str(e)
            logger.error(f"DO1 client error: {e}")
        finally:
            # Copy DO1 job logs to central log directory
            if do1_job_location:
                try:
                    src_stdout = do1_job_location / "stdout.txt"
                    src_stderr = do1_job_location / "stderr.txt"
                    if src_stdout.exists():
                        shutil.copy(src_stdout, do1_stdout_path)
                    if src_stderr.exists():
                        shutil.copy(src_stderr, do1_stderr_path)
                    logger.info(
                        f"DO1 logs copied to: {do1_stdout_path}, {do1_stderr_path}"
                    )
                except Exception as log_err:
                    logger.warning(f"Could not copy DO1 logs: {log_err}")

    # Start both in parallel (mirrors running DS and DO notebooks simultaneously)
    start_time = time.time()

    ds_thread = threading.Thread(target=run_ds_server, name="DS-Server")
    do1_thread = threading.Thread(target=run_do1_client, name="DO1-Client")

    logger.info("Starting DS server and DO1 client in parallel...")
    ds_thread.start()
    do1_thread.start()

    # Wait for both to complete
    do1_thread.join(timeout=660)  # 11 min timeout
    ds_thread.join(timeout=660)

    total_duration = time.time() - start_time

    # Check results
    if do1_result["error"]:
        logger.error(f"DO1 failed: {do1_result['error']}")
    if ds_result["error"]:
        logger.error(f"DS failed: {ds_result['error']}")

    # Both should succeed for FL training to work
    assert (
        do1_result["success"] and ds_result["success"]
    ), f"FL training failed - DO1: {do1_result['error']}, DS: {ds_result['error']}"

    logger.success(
        f"✅ Phase 8 complete: FL training finished in {total_duration:.1f}s"
    )


# ==============================================================================
# Phase 9: Verify Training Results
# ==============================================================================


def test_phase_09_verify_training_results(syft_managers_single_do):
    """Phase 9: Verify training results from DO1 and check trained weights exist for DS."""
    logger.info("Phase 9: Verifying FL training results...")

    do1_manager = syft_managers_single_do["do1"]
    ds_manager = syft_managers_single_do["ds"]

    # Sync results back to DS
    do1_manager.sync()
    sleep(2)
    ds_manager.sync()

    # Get DO1 job results
    do1_jobs = do1_manager.jobs
    assert len(do1_jobs) > 0, "No jobs found for DO1"
    do1_job = do1_jobs[0]

    # Check job completed
    assert do1_job.status == "done", f"Job not completed, status: {do1_job.status}"

    # Read DO1 stdout
    logger.info("Reading DO1 job stdout...")
    do1_stdout = str(do1_job.stdout)
    logger.info(f"\nDO1 Output:\n{do1_stdout}\n")

    do1_stderr = str(do1_job.stderr)
    if do1_stderr and "No stderr" not in do1_stderr:
        logger.warning(f"\nDO1 Error Output:\n{do1_stderr}\n")

    # =========================================================================
    # Verify trained weights are available for DS
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("VERIFYING TRAINED WEIGHTS FOR DS")
    logger.info("=" * 60)

    # Weights are saved to OUTPUT_DIR/weights/ (set in Phase 8)
    fl_output_dir = syft_managers_single_do.get("fl_output_dir")
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
    fl_project = syft_managers_single_do.get("fl_project")
    if fl_project and fl_project.parent.exists():
        shutil.rmtree(fl_project.parent, ignore_errors=True)
        logger.info("✅ FL code temp directory cleaned up")

    logger.success("✅ Phase 9 complete: FL training results verified!")
