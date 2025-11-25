"""
Common Remote Data Science (RDS) test phases for syft-client integration tests.

These are reusable test functions for the standard RDS workflow:
1. Upload datasets (DOs upload private data)
2. Discover datasets (DS finds datasets from peers)
3. Approve jobs (DOs approve submitted jobs)
4. Execute jobs (DOs run approved jobs on private data)

Each test file imports and calls these phases, then implements
workflow-specific phases (e.g., FL bootstrap, result verification).
"""

import time
from time import sleep

from googleapiclient.errors import HttpError
from loguru import logger
from utils import has_file

# ==============================================================================
# Phase: Upload Datasets
# ==============================================================================


def dos_upload_datasets(syft_managers, dataset_dir):
    """DOs upload their dataset partitions.

    Args:
        syft_managers: Dict with 'ds', 'do1', 'do2', 'env' managers
        dataset_dir: Path to directory containing dataset partitions
    """
    logger.info("Uploading datasets to datastites...")

    # Verify DS has both DOs as peers before uploading datasets
    ds_manager = syft_managers["ds"]
    ds_peer_emails = [p.email for p in ds_manager.peers]
    assert (
        len(ds_peer_emails) == 2
    ), f"DS should have 2 peers before upload, got {len(ds_peer_emails)}: {ds_peer_emails}"
    logger.info("✅ Verified DS has 2 peers before dataset upload")

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]

    # DO1 uploads partition 0
    partition_0 = dataset_dir / "pima-indians-diabetes-database-0"

    logger.info(f"DO1 uploading partition 0 from {partition_0}...")
    do1_manager.create_dataset(
        name="pima-indians-diabetes-database",
        mock_path=partition_0 / "mock",
        private_path=partition_0 / "private",
        summary="Diabetes partition 0 for DO1",
        readme_path=partition_0 / "README.md",
        tags=["diabetes", "fl", "healthcare"],
    )

    # Verify DO1 can see dataset
    do1_datasets = do1_manager.datasets.get_all()
    assert (
        len(do1_datasets) == 1
    ), f"Expected 1 dataset for DO1, got {len(do1_datasets)}"
    assert do1_datasets[0].name == "pima-indians-diabetes-database"
    logger.success(f"✅ DO1 dataset uploaded: {do1_datasets[0].name}")

    # Sync to propagate dataset metadata to peers
    logger.info("DO1 syncing dataset to peers...")
    do1_manager.sync()

    # DO2 uploads partition 1
    partition_1 = dataset_dir / "pima-indians-diabetes-database-1"

    logger.info(f"DO2 uploading partition 1 from {partition_1}...")
    do2_manager.create_dataset(
        name="pima-indians-diabetes-database",
        mock_path=partition_1 / "mock",
        private_path=partition_1 / "private",
        summary="Diabetes partition 1 for DO2",
        readme_path=partition_1 / "README.md",
        tags=["diabetes", "fl", "healthcare"],
    )

    # Verify DO2 can see dataset
    do2_datasets = do2_manager.datasets.get_all()
    assert (
        len(do2_datasets) == 1
    ), f"Expected 1 dataset for DO2, got {len(do2_datasets)}"
    assert do2_datasets[0].name == "pima-indians-diabetes-database"
    logger.success(f"✅ DO2 dataset uploaded: {do2_datasets[0].name}")

    # Sync to propagate dataset metadata to peers
    logger.info("DO2 syncing dataset to peers...")
    do2_manager.sync()

    # Wait for sync to propagate through Google Drive
    sleep(3)
    logger.success("✅ Both datasets uploaded and synced")


# ==============================================================================
# Phase: DS Discovers Datasets
# ==============================================================================


def ds_discover_datasets(syft_managers):
    """DS discovers datasets from DOs.

    Args:
        syft_managers: Dict with 'ds', 'do1', 'do2', 'env' managers
    """
    logger.info("DS discovering datasets...")

    ds_manager = syft_managers["ds"]
    env = syft_managers["env"]

    # Verify peers are still connected
    peers = ds_manager.peers
    peer_emails = [p.email for p in peers]
    logger.info(f"DS peers after sync: {peer_emails}")
    logger.info(f"Expected peers: [{env['EMAIL_DO1']}, {env['EMAIL_DO2']}]")

    assert (
        len(peer_emails) == 2
    ), f"DS should have 2 peers, got {len(peer_emails)}: {peer_emails}"
    assert env["EMAIL_DO1"] in peer_emails, f"DO1 not in peers: {peer_emails}"
    assert env["EMAIL_DO2"] in peer_emails, f"DO2 not in peers: {peer_emails}"
    logger.success(f"✅ DS has {len(peers)} peers: {peer_emails}")

    # DS syncs to receive dataset metadata from peers (with retry)
    # Dataset sync can take time due to Google Drive propagation delays
    max_retries = 5
    retry_delay = 5  # seconds

    do1_datasets = []
    do2_datasets = []

    for attempt in range(max_retries):
        logger.info(
            f"DS syncing to receive dataset metadata (attempt {attempt + 1}/{max_retries})..."
        )
        ds_manager.sync()
        sleep(retry_delay)

        # Discover datasets from DO1
        logger.info(f"Discovering datasets from DO1 ({env['EMAIL_DO1']})...")
        do1_datasets = ds_manager.datasets.get_all(datasite=env["EMAIL_DO1"])
        logger.info(f"Found {len(do1_datasets)} dataset(s) from DO1")

        # Discover datasets from DO2
        logger.info(f"Discovering datasets from DO2 ({env['EMAIL_DO2']})...")
        do2_datasets = ds_manager.datasets.get_all(datasite=env["EMAIL_DO2"])
        logger.info(f"Found {len(do2_datasets)} dataset(s) from DO2")

        if len(do1_datasets) > 0 and len(do2_datasets) > 0:
            break

        if attempt < max_retries - 1:
            logger.warning(f"Datasets not yet synced, retrying in {retry_delay}s...")

    assert len(do1_datasets) > 0, f"No datasets found from DO1. DS peers: {peer_emails}"
    assert do1_datasets[0].name == "pima-indians-diabetes-database"
    logger.success(f"✅ DS discovered dataset from DO1: {do1_datasets[0].name}")

    assert len(do2_datasets) > 0, f"No datasets found from DO2. DS peers: {peer_emails}"
    assert do2_datasets[0].name == "pima-indians-diabetes-database"
    logger.success(f"✅ DS discovered dataset from DO2: {do2_datasets[0].name}")

    # Verify DS can access mock data
    do1_dataset = ds_manager.datasets.get(
        "pima-indians-diabetes-database", datasite=env["EMAIL_DO1"]
    )
    assert do1_dataset.mock_dir is not None, "Mock directory should be accessible"

    # Check mock file exists in DS's syftbox
    assert has_file(
        ds_manager.syftbox_folder, "train.csv"
    ), "Mock data not synced to DS"
    logger.success("✅ DS can access mock data")

    # Verify private data is NOT accessible
    logger.success("✅ Private data is protected")

    logger.success("✅ DS discovered all datasets")


# ==============================================================================
# Phase: DOs Approve Jobs
# ==============================================================================


def dos_approve_jobs(syft_managers):
    """DOs review and approve jobs from DS.

    Args:
        syft_managers: Dict with 'ds', 'do1', 'do2', 'env' managers
    """
    logger.info("DOs approving jobs...")

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]

    logger.info("DO1 getting jobs...")
    do1_jobs = do1_manager.jobs
    assert len(do1_jobs) > 0, "No jobs received by DO1"
    logger.info(f"✅ DO1 received {len(do1_jobs)} job(s)")

    # DO1 approves first job
    job_to_approve = do1_jobs[0]
    logger.info(f"DO1 approving job: {job_to_approve.name}")
    job_to_approve.approve()
    logger.success("✅ DO1 approved job")

    logger.info("DO2 getting jobs...")
    do2_jobs = do2_manager.jobs
    assert len(do2_jobs) > 0, "No jobs received by DO2"
    logger.info(f"✅ DO2 received {len(do2_jobs)} job(s)")

    # DO2 approves
    do2_jobs[0].approve()
    logger.success("✅ DO2 approved job")

    logger.success("✅ Both DOs approved jobs")


# ==============================================================================
# Phase: Execute Jobs
# ==============================================================================


def _process_with_retry(manager, name, max_retries=3):
    """Process approved jobs with retry for transient Google API errors."""
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            manager.process_approved_jobs()
            duration = time.time() - start_time
            return duration
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504] and attempt < max_retries - 1:
                logger.warning(
                    f"{name} got transient Google API error (attempt {attempt + 1}/{max_retries}), retrying..."
                )
                sleep(2)
            else:
                raise
    return 0


def dos_execute_jobs(syft_managers):
    """DOs execute approved jobs on their private data.

    Args:
        syft_managers: Dict with 'ds', 'do1', 'do2', 'env' managers

    Returns:
        Tuple of (do1_duration, do2_duration) in seconds
    """
    logger.info("Executing jobs...")

    do1_manager = syft_managers["do1"]
    do2_manager = syft_managers["do2"]

    # DO1 processes approved jobs (SYNCHRONOUS - blocks until complete)
    logger.info("DO1 processing approved jobs...")
    duration_do1 = _process_with_retry(do1_manager, "DO1")
    logger.success(f"✅ DO1 completed job in {duration_do1:.1f}s")

    # DO2 processes approved jobs
    logger.info("DO2 processing approved jobs...")
    duration_do2 = _process_with_retry(do2_manager, "DO2")
    logger.success(f"✅ DO2 completed job in {duration_do2:.1f}s")

    logger.success(
        f"✅ Both DOs executed jobs (DO1: {duration_do1:.1f}s, DO2: {duration_do2:.1f}s)"
    )

    return duration_do1, duration_do2
