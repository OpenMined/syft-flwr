"""
Integration test for FL Diabetes Prediction with a SINGLE Data Owner.

This simplified test verifies the FL workflow with just one DO:
1. Single data owner uploads private dataset to Google Drive
2. Data scientist discovers dataset and submits FL training job
3. Data owner approves and executes job on their private data
4. Training results are verified

This test avoids the parallel execution requirement that would be needed
when multiple DOs need to coordinate in federated learning.

Prerequisites:
- Google OAuth credentials (client_id, client_secret) in syft-flwr/credentials/
- Environment variables (automatically loaded from credentials/.env if it exists)
- Both syft-client and syft-flwr installed in editable mode

Setup:
    1. Create credentials/.env with your configuration:
        DIABETES_EMAIL_DO1="do1@example.com"
        DIABETES_EMAIL_DS="ds@example.com"
        DIABETES_CRED_FNAME_DO1="do1.json"
        DIABETES_CRED_FNAME_DS="ds.json"
        DIABETES_TOKEN_FNAME_DO1="token_do1.json"
        DIABETES_TOKEN_FNAME_DS="token_ds.json"

    2. Place OAuth credentials (from Google Cloud Console) in credentials/:
        - do1.json, ds.json

    3. Run: pytest tests/integration/syft-client/fl_diabetes_one_do_test.py -v -s
       (OAuth tokens will be generated automatically on first run)
"""

import shutil
import tempfile
from pathlib import Path
from time import sleep

import tomli
from common_rds_phases import (
    dos_upload_datasets,
)
from conftest import FL_PROJECT_DIR
from loguru import logger

import syft_flwr

# ==============================================================================
# Phase 3: Upload Dataset to DO1 Datasite
# ==============================================================================


def test_phase_03_upload_dataset(syft_managers, prepare_datasets):
    """Phase 3: DO1 uploads their dataset partition."""
    logger.info("Phase 3: Uploading dataset to DO1 datasite...")

    do1_manager = syft_managers["do1"]
    do1_dataset = prepare_datasets

    # Upload dataset to DO1's datasite
    logger.info(f"DO1 uploading dataset: {do1_dataset.name}")
    dos_upload_datasets(syft_managers, prepare_datasets)
    logger.info("DO1 dataset uploaded, syncing...")
    do1_manager.sync()

    logger.success("✅ Phase 3 complete: DO1 dataset uploaded and synced")


# ==============================================================================
# Phase 4: DS Discovers Dataset
# ==============================================================================


def test_phase_04_ds_discovers_dataset(syft_managers):
    """Phase 4: DS discovers dataset from DO1."""
    logger.info("Phase 4: DS discovering dataset...")

    ds_manager = syft_managers["ds"]
    env = syft_managers["env"]

    # Sync DS to pull down DO1's dataset catalog
    ds_manager.sync()
    sleep(2)

    # Get datasets from DO1
    do1_email = env["EMAIL_DO1"]
    datasets = ds_manager.datasets(peer=do1_email)

    assert len(datasets) > 0, f"No datasets found from {do1_email}"
    logger.info(f"Found {len(datasets)} dataset(s) from {do1_email}")

    for ds in datasets:
        logger.info(f"  - {ds.name}: {ds.description}")

    logger.success("✅ Phase 4 complete: DS discovered DO1's dataset")


# ==============================================================================
# Phase 5: Bootstrap FL Project (Single DO)
# ==============================================================================


def test_phase_05_bootstrap_fl_project(syft_managers):
    """Phase 5: Bootstrap FL project for single DO execution."""
    logger.info("Phase 5: Bootstrapping FL project for single DO...")

    env = syft_managers["env"]
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
    syft_managers["fl_project"] = fl_temp_project

    logger.success("✅ Phase 5 complete: FL project bootstrapped for single DO")


# ==============================================================================
# Phase 6: Submit FL Job to DO1
# ==============================================================================


def test_phase_06_submit_fl_job(syft_managers):
    """Phase 6: DS submits FL training job to DO1."""
    logger.info("Phase 6: Submitting FL job to DO1...")

    ds_manager = syft_managers["ds"]
    env = syft_managers["env"]
    fl_project = syft_managers.get("fl_project")

    assert fl_project is not None, "FL project not bootstrapped - run phase 5 first"
    assert fl_project.exists(), f"FL project not found: {fl_project}"

    # Submit entire FL project folder to DO1 only
    logger.info(f"FL project folder: {fl_project}")
    logger.info(f"Submitting FL job to {env['EMAIL_DO1']}...")

    ds_manager.submit_python_job(
        user=env["EMAIL_DO1"],
        code_path=str(fl_project),
        job_name="fl-diabetes-training",
    )
    logger.success("✅ FL job submitted to DO1")

    # Wait for job to propagate
    sleep(2)

    logger.success("✅ Phase 6 complete: FL job submitted to DO1")


# ==============================================================================
# Phase 7: DO1 Reviews and Approves Job
# ==============================================================================


def test_phase_07_do1_approves_job(syft_managers):
    """Phase 7: DO1 reviews and approves FL job from DS."""
    logger.info("Phase 7: DO1 approving FL job...")

    do1_manager = syft_managers["do1"]

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
# Phase 8: Execute FL Job on DO1
# ==============================================================================


def test_phase_08_execute_fl_job(syft_managers):
    """Phase 8: DO1 executes approved FL job on their private data."""
    logger.info("Phase 8: DO1 executing FL job...")

    do1_manager = syft_managers["do1"]

    # Process approved jobs (this will run the FL training)
    import time

    start_time = time.time()
    do1_manager.process_approved_jobs()
    duration = time.time() - start_time

    logger.success(f"✅ Phase 8 complete: DO1 executed FL job in {duration:.1f}s")


# ==============================================================================
# Phase 9: Verify Training Results
# ==============================================================================


def test_phase_09_verify_training_results(syft_managers):
    """Phase 9: Verify training results from DO1."""
    logger.info("Phase 9: Verifying FL training results...")

    do1_manager = syft_managers["do1"]
    ds_manager = syft_managers["ds"]

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

    # Cleanup FL project temp directory
    fl_project = syft_managers.get("fl_project")
    if fl_project and fl_project.parent.exists():
        shutil.rmtree(fl_project.parent, ignore_errors=True)
        logger.info("✅ FL code temp directory cleaned up")

    logger.success("✅ Phase 9 complete: FL training results verified!")
