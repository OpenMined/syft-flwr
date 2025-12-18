import os
import sys
from pathlib import Path

print("=" * 60)
print("SYFT-FLWR main.py starting...")
print("=" * 60)

# Debug: Print environment variables
print(f"SYFTBOX_EMAIL: {os.getenv('SYFTBOX_EMAIL')}")
print(f"SYFTBOX_FOLDER: {os.getenv('SYFTBOX_FOLDER')}")
print(f"DATA_DIR: {os.getenv('DATA_DIR')}")
print(f"OUTPUT_DIR: {os.getenv('OUTPUT_DIR')}")

from syft_flwr.client import create_client
from syft_flwr.config import load_flwr_pyproject
from syft_flwr.run import syftbox_run_flwr_client, syftbox_run_flwr_server

DATA_DIR = os.getenv("DATA_DIR")
OUTPUT_DIR = os.getenv("OUTPUT_DIR")


flower_project_dir = Path(__file__).parent.absolute()
print(f"flower_project_dir: {flower_project_dir}")

print("Creating client...")
client = create_client(project_dir=flower_project_dir)
print(f"Client created: email={client.email}")
print(f"Client my_datasite: {client.my_datasite}")
print(f"Client datasites: {client.datasites}")

print("Loading FL config from pyproject.toml...")
config = load_flwr_pyproject(flower_project_dir)
print(f"Config datasites: {config['tool']['syft_flwr']['datasites']}")
print(f"Config aggregator: {config['tool']['syft_flwr']['aggregator']}")

is_client = client.email in config["tool"]["syft_flwr"]["datasites"]
is_server = client.email in config["tool"]["syft_flwr"]["aggregator"]

print(f"is_client: {is_client}")
print(f"is_server: {is_server}")

if is_client:
    # run by each DO
    print("Running as FL CLIENT (DO)...")
    syftbox_run_flwr_client(flower_project_dir)
    print("FL CLIENT completed!")
    sys.exit(0)  # Exit cleanly after client work completes
elif is_server:
    # run by the DS
    print("Running as FL SERVER (DS/Aggregator)...")
    syftbox_run_flwr_server(flower_project_dir)
    print("FL SERVER completed!")
    sys.exit(0)  # Exit cleanly after server work completes
else:
    print(f"ERROR: {client.email} is not in config.datasites or config.aggregator")
    raise ValueError(f"{client.email} is not in config.datasites or config.aggregator")
    sys.exit(1)  # Exit with error code
