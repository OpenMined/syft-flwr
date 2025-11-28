"""
Integration test for simple Python script execution using syft-client.

This test verifies the complete workflow for executing a simple Python script:
1. DOs upload private datasets to Google Drive
2. DS discovers datasets and submits simple analysis jobs
3. DOs approve and execute jobs on their private data
4. Results are verified

This is a simpler test than FL diabetes training - just runs a Python script
that reads the dataset and prints summary statistics.

Prerequisites:
- Google OAuth credentials in syft-flwr/credentials/
- Environment variables (from credentials/.env)

Run: pytest tests/integration/syft-client/single_python_script_test.py -v -s
"""

import shutil
import tempfile
from pathlib import Path
from time import sleep

from common_rds_phases import (
    dos_approve_jobs,
    dos_execute_jobs,
    dos_upload_datasets,
    ds_discover_datasets,
)
from loguru import logger

# ==============================================================================
# Constants
# ==============================================================================

# Path to the analyze_diabetes.py script in assets
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
ANALYZE_SCRIPT = ASSETS_DIR / "code" / "single_python_script" / "analyze_diabetes.py"


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
# Phase 5: Submit Jobs to Data Owners
# ==============================================================================


def test_phase_05_submit_jobs(syft_managers):
    """Phase 5: DS submits simple analysis jobs to both DOs."""
    logger.info("Phase 5: Submitting jobs to data owners...")

    ds_manager = syft_managers["ds"]
    env = syft_managers["env"]

    # Copy script to temp file (syft-client needs a fresh copy for each submission)
    assert ANALYZE_SCRIPT.exists(), f"Script not found: {ANALYZE_SCRIPT}"
    temp_dir = Path(tempfile.mkdtemp())
    temp_script = temp_dir / "analyze_diabetes.py"
    shutil.copy(ANALYZE_SCRIPT, temp_script)
    logger.info(f"Copied script to temp: {temp_script}")

    try:
        # Submit job to DO1
        logger.info(f"Submitting job to {env['EMAIL_DO1']}...")
        ds_manager.submit_python_job(
            user=env["EMAIL_DO1"],
            code_path=str(temp_script),
            job_name="diabetes-analysis",
            dependencies=["pandas", "syft-client"],
        )
        logger.success("✅ Job submitted to DO1")

        # Submit job to DO2
        logger.info(f"Submitting job to {env['EMAIL_DO2']}...")
        ds_manager.submit_python_job(
            user=env["EMAIL_DO2"],
            code_path=str(temp_script),
            job_name="diabetes-analysis",
            dependencies=["pandas", "syft-client"],
        )
        logger.success("✅ Job submitted to DO2")

        # Wait for jobs to propagate
        sleep(2)

    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info("✅ Temp script cleaned up")

    logger.success("✅ Phase 5 complete: Jobs submitted to both DOs")


# ==============================================================================
# Phase 6: DOs Review and Approve Jobs
# ==============================================================================


def test_phase_06_dos_approve_jobs(syft_managers):
    """Phase 6: DOs review and approve jobs from DS."""
    logger.info("Phase 6: DOs approving jobs...")
    dos_approve_jobs(syft_managers)
    logger.success("✅ Phase 6 complete: Both DOs approved jobs")


# ==============================================================================
# Phase 7: Execute Jobs
# ==============================================================================


def test_phase_07_execute_jobs(syft_managers):
    """Phase 7: DOs execute approved jobs on their private data."""
    logger.info("Phase 7: Executing jobs...")
    duration_do1, duration_do2 = dos_execute_jobs(syft_managers)
    logger.success(
        f"✅ Phase 7 complete: Both DOs executed jobs (DO1: {duration_do1:.1f}s, DO2: {duration_do2:.1f}s)"
    )


# ==============================================================================
# Phase 8: Verify Job Results
# ==============================================================================


def test_phase_08_verify_results(syft_managers):
    """Phase 8: Verify job results - check that the simple analysis job ran successfully."""
    logger.info("Phase 8: Verifying job results...")

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]

    # Get DO1 job results
    do1_jobs = do1_manager.jobs
    assert len(do1_jobs) > 0, "No jobs found for DO1"
    do1_job = do1_jobs[0]

    # Read DO1 stdout
    logger.info("Reading DO1 job stdout...")
    do1_stdout = str(do1_job.stdout)
    logger.info(f"\nDO1 Output:\n{do1_stdout}\n")

    # Verify DO1 job succeeded
    assert (
        "RESULT: SUCCESS" in do1_stdout
    ), f"DO1 job did not succeed. Output: {do1_stdout}"
    assert (
        "Shape:" in do1_stdout
    ), f"DO1 job did not print dataset shape. Output: {do1_stdout}"
    assert "DIABETES DATASET SUMMARY" in do1_stdout, "DO1 job missing summary header"
    logger.success("✅ DO1 job completed successfully")

    # Get DO2 job results
    do2_jobs = do2_manager.jobs
    assert len(do2_jobs) > 0, "No jobs found for DO2"
    do2_job = do2_jobs[0]

    # Read DO2 stdout
    logger.info("Reading DO2 job stdout...")
    do2_stdout = str(do2_job.stdout)
    logger.info(f"\nDO2 Output:\n{do2_stdout}\n")

    # Verify DO2 job succeeded
    assert (
        "RESULT: SUCCESS" in do2_stdout
    ), f"DO2 job did not succeed. Output: {do2_stdout}"
    assert (
        "Shape:" in do2_stdout
    ), f"DO2 job did not print dataset shape. Output: {do2_stdout}"
    assert "DIABETES DATASET SUMMARY" in do2_stdout, "DO2 job missing summary header"
    logger.success("✅ DO2 job completed successfully")

    # Log final summary
    logger.info("\n" + "=" * 60)
    logger.info("JOB RESULTS SUMMARY")
    logger.info("=" * 60)
    logger.info("DO1: Job executed successfully - dataset summary printed")
    logger.info("DO2: Job executed successfully - dataset summary printed")
    logger.info("=" * 60)

    logger.success("✅ Phase 8 complete: Job results verified!")
