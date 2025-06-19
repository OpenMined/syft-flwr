import os
from time import sleep

import flwr
import syft_rds as sy
from loguru import logger
from syft_core import Client
from syft_rds.models import JobStatus

import syft_flwr

os.environ["SYFT_RDS_BLOCKING_EXECUTION"] = "False"

logger.info(f"syft_rds version: {sy.__version__}")
logger.info(f"syft_flwr version: {syft_flwr.__version__}")
logger.info(f"flwr version: {flwr.__version__}")
logger.debug(f"Blocking execution: {os.environ['SYFT_RDS_BLOCKING_EXECUTION']}")


email = Client.load().email
logger.info(f"SyftBox client email: {email}")
client = sy.init_session(email)


def main():
    logger.info("Waiting for jobs...")
    while True:
        jobs = client.jobs.get_all(status="pending_code_review")
        for job in jobs:
            if job.status == JobStatus.pending_code_review:
                logger.info(f"Got job {job.uid}")
                logger.info(job.user_code)
                logger.info(f"Job started {job.uid}")
                res_job = client.run_private(job)
                logger.info(res_job)
                logger.info(f"Job finished {job.uid}")

        sleep(10)


if __name__ == "__main__":
    main()
