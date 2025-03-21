import os

from syft_flwr.run import syftbox_run_flwr_client

DATA_DIR = os.environ["DATA_DIR"]
OUTPUT_DIR = os.environ["OUTPUT_DIR"]

# TODO - how does DATA_DIR pass information down
# TODD - how does OUTPUT_DIR work here. As data is constantly passed around over RPC
# This means we need to mount rpc directory into the vm for active communication
syftbox_run_flwr_client(os.path.dirname(__file__))
