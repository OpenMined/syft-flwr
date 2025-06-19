from time import sleep

import syft_rds as sy
from syft_core import Client
from syft_rds.models import JobStatus

email = Client.load().email
print(f"SyftBox client email: {email}")
client = sy.init_session(email)


def main():
    print("Waiting for jobs...")
    while True:
        jobs = client.jobs.get_all(status="pending_code_review")
        for job in jobs:
            if job.status == JobStatus.pending_code_review:
                print("Got job", job.uid)
                print(job.user_code)
                print("Job started", job.uid)
                res_job = client.run_private(job)
                print(res_job)
                print("Job finished", job.uid)

        sleep(10)


if __name__ == "__main__":
    main()
