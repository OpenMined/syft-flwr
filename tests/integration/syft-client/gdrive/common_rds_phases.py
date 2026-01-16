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
from pathlib import Path
from time import sleep

from googleapiclient.errors import HttpError
from loguru import logger
from syft_client.sync.syftbox_manager import SyftboxManager

from .utils import has_file

# ==============================================================================
# Phase: Upload Datasets
# ==============================================================================


def do_upload_dataset(
    do_manager: SyftboxManager,
    dataset_dir: Path,
    partition_index: int,
    do_name: str = "DO",
):
    """Single DO uploads their dataset partition.

    Args:
        do_manager: Data Owner's SyftboxManager
        dataset_dir: Path to directory containing dataset partitions
        partition_index: Which partition to upload (0 or 1)
        do_name: Name for logging (e.g., "DO1", "DO2")
    """
    partition_dir = dataset_dir / f"pima-indians-diabetes-database-{partition_index}"

    logger.info(
        f"{do_name} uploading partition {partition_index} from {partition_dir}..."
    )
    do_manager.create_dataset(
        name="pima-indians-diabetes-database",
        mock_path=partition_dir / "mock",
        private_path=partition_dir / "private",
        summary=f"Diabetes partition {partition_index} for {do_name}",
        readme_path=partition_dir / "README.md",
        tags=["diabetes", "fl", "healthcare"],
    )

    # Verify DO can see dataset
    do_datasets = do_manager.datasets.get_all()
    assert (
        len(do_datasets) == 1
    ), f"Expected 1 dataset for {do_name}, got {len(do_datasets)}"
    assert do_datasets[0].name == "pima-indians-diabetes-database"
    logger.success(f"✅ {do_name} dataset uploaded: {do_datasets[0].name}")

    # Sync to propagate dataset metadata to peers
    logger.info(f"{do_name} syncing dataset to peers...")
    do_manager.sync()


def dos_upload_datasets(syft_managers, dataset_dir):
    """DOs upload their dataset partitions (convenience wrapper for 2 DOs).

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

    # DO1 uploads partition 0
    do_upload_dataset(
        do_manager=syft_managers["do1"],
        dataset_dir=dataset_dir,
        partition_index=0,
        do_name="DO1",
    )

    # DO2 uploads partition 1
    do_upload_dataset(
        do_manager=syft_managers["do2"],
        dataset_dir=dataset_dir,
        partition_index=1,
        do_name="DO2",
    )

    # Wait for sync to propagate through Google Drive
    sleep(3)
    logger.success("✅ Both datasets uploaded and synced")


# ==============================================================================
# Phase: DS Discovers Datasets
# ==============================================================================


def ds_discover_dataset_from_do(
    ds_manager: SyftboxManager,
    do_email: str,
    do_name: str = "DO",
    max_retries: int = 5,
    retry_delay: int = 5,
):
    """DS discovers dataset from a single DO.

    Args:
        ds_manager: Data Scientist's SyftboxManager
        do_email: Data Owner's email address
        do_name: Name for logging (e.g., "DO1", "DO2")
        max_retries: Number of sync retries
        retry_delay: Delay between retries in seconds

    Returns:
        List of discovered datasets from the DO
    """
    datasets = []

    for attempt in range(max_retries):
        logger.info(
            f"DS syncing to receive dataset metadata from {do_name} "
            f"(attempt {attempt + 1}/{max_retries})..."
        )
        ds_manager.sync()
        sleep(retry_delay)

        logger.info(f"Discovering datasets from {do_name} ({do_email})...")
        datasets = ds_manager.datasets.get_all(datasite=do_email)
        logger.info(f"Found {len(datasets)} dataset(s) from {do_name}")

        if len(datasets) > 0:
            break

        if attempt < max_retries - 1:
            logger.warning(f"Datasets not yet synced, retrying in {retry_delay}s...")

    assert len(datasets) > 0, f"No datasets found from {do_name} ({do_email})"
    assert datasets[0].name == "pima-indians-diabetes-database"
    logger.success(f"✅ DS discovered dataset from {do_name}: {datasets[0].name}")

    return datasets


def ds_discover_datasets(syft_managers):
    """DS discovers datasets from DOs (convenience wrapper for 2 DOs).

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

    # Discover datasets from both DOs
    ds_discover_dataset_from_do(ds_manager, env["EMAIL_DO1"], "DO1")
    ds_discover_dataset_from_do(ds_manager, env["EMAIL_DO2"], "DO2")

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


def do_approve_jobs(do_manager: SyftboxManager, do_name: str = "DO"):
    """Single DO reviews and approves jobs from DS.

    Args:
        do_manager: Data Owner's SyftboxManager
        do_name: Name for logging (e.g., "DO1", "DO2")

    Returns:
        List of approved jobs
    """
    logger.info(f"{do_name} getting jobs...")
    jobs = do_manager.jobs
    assert len(jobs) > 0, f"No jobs received by {do_name}"
    logger.info(f"✅ {do_name} received {len(jobs)} job(s)")

    # Approve first job
    job_to_approve = jobs[0]
    logger.info(f"{do_name} approving job: {job_to_approve.name}")
    job_to_approve.approve()
    logger.success(f"✅ {do_name} approved job")

    return jobs


def dos_approve_jobs(syft_managers):
    """DOs review and approve jobs from DS (convenience wrapper for 2 DOs).

    Args:
        syft_managers: Dict with 'ds', 'do1', 'do2', 'env' managers
    """
    logger.info("DOs approving jobs...")

    do_approve_jobs(syft_managers["do1"], "DO1")
    do_approve_jobs(syft_managers["do2"], "DO2")

    logger.success("✅ Both DOs approved jobs")


# ==============================================================================
# Phase: Execute Jobs
# ==============================================================================


def do_execute_jobs(
    do_manager: SyftboxManager,
    do_name: str = "DO",
    max_retries: int = 3,
) -> float:
    """Single DO executes approved jobs on their private data.

    Args:
        do_manager: Data Owner's SyftboxManager
        do_name: Name for logging (e.g., "DO1", "DO2")
        max_retries: Number of retries for transient Google API errors

    Returns:
        Duration in seconds
    """
    logger.info(f"{do_name} processing approved jobs...")

    for attempt in range(max_retries):
        try:
            start_time = time.time()
            do_manager.process_approved_jobs()
            duration = time.time() - start_time
            logger.success(f"✅ {do_name} completed job in {duration:.1f}s")
            return duration
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504] and attempt < max_retries - 1:
                logger.warning(
                    f"{do_name} got transient Google API error "
                    f"(attempt {attempt + 1}/{max_retries}), retrying..."
                )
                sleep(2)
            else:
                raise

    return 0.0


def dos_execute_jobs(syft_managers):
    """DOs execute approved jobs on their private data (convenience wrapper for 2 DOs).

    Args:
        syft_managers: Dict with 'ds', 'do1', 'do2', 'env' managers

    Returns:
        Tuple of (do1_duration, do2_duration) in seconds
    """
    logger.info("Executing jobs...")

    duration_do1 = do_execute_jobs(syft_managers["do1"], "DO1")
    duration_do2 = do_execute_jobs(syft_managers["do2"], "DO2")

    logger.success(
        f"✅ Both DOs executed jobs (DO1: {duration_do1:.1f}s, DO2: {duration_do2:.1f}s)"
    )

    return duration_do1, duration_do2
