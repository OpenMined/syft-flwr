import os
from pathlib import Path

from syft_core import Client

from syft_flwr.config import load_flwr_pyproject
from syft_flwr.run import syftbox_run_flwr_client, syftbox_run_flwr_server

DATA_DIR = os.getenv("DATA_DIR")
OUTPUT_DIR = os.getenv("OUTPUT_DIR")


flower_project_dir = Path(__file__).parent.absolute()
client = Client.load()
config = load_flwr_pyproject(flower_project_dir)

is_client = client.email in config["tool"]["syft_flwr"]["datasites"]
is_server = client.email in config["tool"]["syft_flwr"]["aggregator"]

if is_client:
    # run by each DO
    syftbox_run_flwr_client(flower_project_dir)
elif is_server:
    # run by the DS
    syftbox_run_flwr_server(flower_project_dir)
else:
    raise ValueError(f"{client.email} is not in config.datasites or config.aggregator")
