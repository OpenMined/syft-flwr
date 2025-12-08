"""
Integration test for simple Python script submission using syft-client.

This test verifies the complete workflow for submitting and accepting a Python job:
1. DOs upload private datasets to Google Drive
2. DS discovers datasets and submits simple analysis jobs
3. DOs approve jobs and accept them by depositing results
4. Results are verified

This is a simpler test that focuses on the job submission/acceptance workflow
without actually executing the Python scripts.

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
# Phase 7: DOs Accept Jobs by Depositing Results
# ==============================================================================


def test_phase_07_dos_accept_jobs(syft_managers):
    """Phase 7: DOs accept jobs by depositing mock results.

    This uses accept_by_depositing_result() to mark jobs as done
    without actually executing the Python scripts.
    """
    logger.info("Phase 7: DOs accepting jobs by depositing results...")

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]

    # Create a mock result file to deposit
    result_content = """DIABETES DATASET ANALYSIS RESULTS
==================================
Shape: (384, 9)
Analysis completed successfully.
RESULT: SUCCESS
"""

    # DO1 accepts job by depositing result
    logger.info("DO1 accepting job...")
    do1_jobs = do1_manager.jobs
    assert len(do1_jobs) > 0, "No jobs found for DO1"
    do1_job = do1_jobs[0]
    assert (
        do1_job.status == "approved"
    ), f"DO1 job not approved, status: {do1_job.status}"

    # Create temp result file and deposit it
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(result_content)
        do1_result_path = f.name

    try:
        do1_job.accept_by_depositing_result(do1_result_path)
        logger.success("✅ DO1 job accepted with deposited result")
    finally:
        Path(do1_result_path).unlink(missing_ok=True)

    # DO2 accepts job by depositing result
    logger.info("DO2 accepting job...")
    do2_jobs = do2_manager.jobs
    assert len(do2_jobs) > 0, "No jobs found for DO2"
    do2_job = do2_jobs[0]
    assert (
        do2_job.status == "approved"
    ), f"DO2 job not approved, status: {do2_job.status}"

    # Create temp result file and deposit it
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(result_content)
        do2_result_path = f.name

    try:
        do2_job.accept_by_depositing_result(do2_result_path)
        logger.success("✅ DO2 job accepted with deposited result")
    finally:
        Path(do2_result_path).unlink(missing_ok=True)

    logger.success("✅ Phase 7 complete: Both DOs accepted jobs")


# ==============================================================================
# Phase 8: Verify Results
# ==============================================================================


def test_phase_08_verify_results(syft_managers):
    """Phase 8: Verify that jobs are marked as done and results are deposited."""
    logger.info("Phase 8: Verifying job results...")

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]
    ds_manager = syft_managers["ds"]

    # DS syncs to get latest state
    logger.info("DS syncing to get latest job status...")
    ds_manager.sync()
    sleep(1)

    # Verify DO1 job is done
    do1_jobs = do1_manager.jobs
    assert len(do1_jobs) > 0, "No jobs found for DO1"
    do1_job = do1_jobs[0]
    assert do1_job.status == "done", f"DO1 job not done, status: {do1_job.status}"

    # Check DO1 has output files
    do1_outputs = do1_job.output_paths
    assert len(do1_outputs) > 0, "DO1 job has no output files"
    logger.info(f"DO1 job outputs: {[p.name for p in do1_outputs]}")
    logger.success("✅ DO1 job verified: status=done, outputs deposited")

    # Verify DO2 job is done
    do2_jobs = do2_manager.jobs
    assert len(do2_jobs) > 0, "No jobs found for DO2"
    do2_job = do2_jobs[0]
    assert do2_job.status == "done", f"DO2 job not done, status: {do2_job.status}"

    # Check DO2 has output files
    do2_outputs = do2_job.output_paths
    assert len(do2_outputs) > 0, "DO2 job has no output files"
    logger.info(f"DO2 job outputs: {[p.name for p in do2_outputs]}")
    logger.success("✅ DO2 job verified: status=done, outputs deposited")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("JOB VERIFICATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  DO1 job status: {do1_job.status}")
    logger.info(f"  DO1 outputs: {len(do1_outputs)} file(s)")
    logger.info(f"  DO2 job status: {do2_job.status}")
    logger.info(f"  DO2 outputs: {len(do2_outputs)} file(s)")
    logger.info("=" * 60)

    logger.success("✅ Phase 8 complete: All jobs verified successfully!")
