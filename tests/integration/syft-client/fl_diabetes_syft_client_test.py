"""
Integration test for FL Diabetes Prediction using syft-client's Google Drive transport.

This test verifies the complete federated learning workflow:
1. Multiple data owners upload private datasets to Google Drive
2. Data scientist discovers datasets and submits FL training jobs
3. Data owners approve and execute jobs on their private data
4. Training results are verified

Prerequisites:
- Google OAuth credentials (client_id, client_secret) in syft-flwr/credentials/
- Environment variables (automatically loaded from credentials/.env if it exists)
- Both syft-client and syft-flwr installed in editable mode

Setup:
    1. Create credentials/.env with your configuration:
        DIABETES_EMAIL_DO1="do1@example.com"
        DIABETES_EMAIL_DO2="do2@example.com"
        DIABETES_EMAIL_DS="ds@example.com"
        DIABETES_CRED_FNAME_DO1="do1.json"
        DIABETES_CRED_FNAME_DO2="do2.json"
        DIABETES_CRED_FNAME_DS="ds.json"
        DIABETES_TOKEN_FNAME_DO1="token_do1.json"
        DIABETES_TOKEN_FNAME_DO2="token_do2.json"
        DIABETES_TOKEN_FNAME_DS="token_ds.json"

    2. Place OAuth credentials (from Google Cloud Console) in credentials/:
        - do1.json, do2.json, ds.json

    3. Run: pytest tests/integration/syft-client/fl_diabetes_syft_client_test.py -v -s
       (OAuth tokens will be generated automatically on first run)
"""

import re
import shutil
import tempfile
from pathlib import Path
from time import sleep

import tomli
from common_rds_phases import (
    dos_approve_jobs,
    dos_execute_jobs,
    dos_upload_datasets,
    ds_discover_datasets,
)
from conftest import FL_PROJECT_DIR
from loguru import logger

import syft_flwr

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
    syft_flwr.bootstrap(fl_temp_project, aggregator=ds_email, datasites=do_emails)
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

    # NOTE: submit_python_job currently only accepts single files (folders are temporarily disabled)
    # For now, we submit the main.py entry point
    main_py = fl_project / "main.py"
    assert main_py.exists(), f"main.py not found: {main_py}"

    # Submit job to DO1
    logger.info(f"Submitting FL job to {env['EMAIL_DO1']}...")
    ds_manager.submit_python_job(
        user=env["EMAIL_DO1"],
        code_path=str(main_py),
        job_name="fl-diabetes-training",
        dependencies=["flwr", "torch", "pandas", "scikit-learn", "syft-flwr"],
    )
    logger.success("✅ FL job submitted to DO1")

    # Submit job to DO2
    logger.info(f"Submitting FL job to {env['EMAIL_DO2']}...")
    ds_manager.submit_python_job(
        user=env["EMAIL_DO2"],
        code_path=str(main_py),
        job_name="fl-diabetes-training",
        dependencies=["flwr", "torch", "pandas", "scikit-learn", "syft-flwr"],
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
# Phase 8: Execute FL Jobs
# ==============================================================================


def test_phase_08_execute_fl_jobs(syft_managers):
    """Phase 8: DOs execute approved FL jobs on their private data."""
    logger.info("Phase 8: Executing FL jobs...")
    duration_do1, duration_do2 = dos_execute_jobs(syft_managers)
    logger.success(
        f"✅ Phase 8 complete: Both DOs executed FL jobs (DO1: {duration_do1:.1f}s, DO2: {duration_do2:.1f}s)"
    )


# ==============================================================================
# Phase 9: Verify Training Results
# ==============================================================================


def test_phase_09_verify_training_results(syft_managers):
    """Phase 9: Verify training results meet quality criteria."""
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

    # Parse DO1 results from stdout
    # Looking for: "RESULT: test_accuracy=0.xxxx, test_loss=0.xxxx"
    do1_acc_match = re.search(r"test_accuracy=([\d.]+)", do1_stdout)
    do1_loss_match = re.search(r"test_loss=([\d.]+)", do1_stdout)

    assert do1_acc_match, "Could not find test_accuracy in DO1 output"
    assert do1_loss_match, "Could not find test_loss in DO1 output"

    do1_accuracy = float(do1_acc_match.group(1))
    do1_loss = float(do1_loss_match.group(1))

    logger.success(f"DO1 Results: accuracy={do1_accuracy:.4f}, loss={do1_loss:.4f}")

    # Get DO2 job results
    do2_jobs = do2_manager.jobs
    assert len(do2_jobs) > 0, "No jobs found for DO2"
    do2_job = do2_jobs[0]

    logger.info("Reading DO2 job stdout...")
    do2_stdout = str(do2_job.stdout)
    logger.info(f"\nDO2 Output:\n{do2_stdout}\n")

    # Parse DO2 results
    do2_acc_match = re.search(r"test_accuracy=([\d.]+)", do2_stdout)
    do2_loss_match = re.search(r"test_loss=([\d.]+)", do2_stdout)

    assert do2_acc_match, "Could not find test_accuracy in DO2 output"
    assert do2_loss_match, "Could not find test_loss in DO2 output"

    do2_accuracy = float(do2_acc_match.group(1))
    do2_loss = float(do2_loss_match.group(1))

    logger.success(f"DO2 Results: accuracy={do2_accuracy:.4f}, loss={do2_loss:.4f}")

    # Verify accuracy is reasonable for binary classification
    # Diabetes dataset is imbalanced, so accuracy > 0.5 is reasonable
    assert do1_accuracy > 0.5, f"DO1 accuracy too low: {do1_accuracy}"
    assert do2_accuracy > 0.5, f"DO2 accuracy too low: {do2_accuracy}"

    # Verify loss is finite and reasonable
    assert 0 < do1_loss < 10, f"DO1 loss out of range: {do1_loss}"
    assert 0 < do2_loss < 10, f"DO2 loss out of range: {do2_loss}"

    # Log final summary
    logger.info("\n" + "=" * 60)
    logger.info("FL TRAINING RESULTS SUMMARY")
    logger.info("=" * 60)
    logger.info(f"DO1: accuracy={do1_accuracy:.4f}, loss={do1_loss:.4f}")
    logger.info(f"DO2: accuracy={do2_accuracy:.4f}, loss={do2_loss:.4f}")
    logger.info("=" * 60)

    # Cleanup FL project temp directory
    fl_project = syft_managers.get("fl_project")
    if fl_project and fl_project.parent.exists():
        shutil.rmtree(fl_project.parent, ignore_errors=True)
        logger.info("✅ FL code temp directory cleaned up")

    logger.success("✅ Phase 9 complete: FL training results verified!")
