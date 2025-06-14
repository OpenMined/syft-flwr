"""pandas_example: A Flower / Pandas app."""

import warnings

import numpy as np
import pandas as pd
from flwr.client import ClientApp
from flwr.common import Context, Message, MetricRecord, RecordDict
from flwr_datasets import FederatedDataset
from flwr_datasets.partitioner import IidPartitioner

fds = None  # Cache FederatedDataset

warnings.filterwarnings("ignore", category=UserWarning)


def load_syftbox_dataset() -> pd.DataFrame:
    from datasets import load_from_disk
    from datasets.arrow_dataset import Dataset
    from loguru import logger

    from syft_flwr.utils import get_syftbox_dataset_path

    data_dir = get_syftbox_dataset_path()
    dataset: Dataset = load_from_disk(str(data_dir))
    df: pd.DataFrame = dataset.with_format("pandas")[:]
    logger.info(f"Loaded syftbox dataset from {data_dir}")
    logger.info(f"Dataset head: {df.head(2)}")
    return df[["SepalLengthCm", "SepalWidthCm"]]


def get_clientapp_dataset(partition_id: int, num_partitions: int):
    # Only initialize `FederatedDataset` once
    global fds
    if fds is None:
        partitioner = IidPartitioner(num_partitions=num_partitions)
        fds = FederatedDataset(
            dataset="scikit-learn/iris",
            partitioners={"train": partitioner},
        )

    dataset = fds.load_partition(partition_id, "train").with_format("pandas")[:]
    # Use just the specified columns
    return dataset[["SepalLengthCm", "SepalWidthCm"]]


# Flower ClientApp
app = ClientApp()


@app.query()
def query(msg: Message, context: Context):
    """Construct histogram of local dataset and report to `ServerApp`."""

    # Read the node_config to fetch data partition associated to this node
    partition_id = context.node_config["partition-id"]
    num_partitions = context.node_config["num-partitions"]

    from syft_flwr.utils import run_syft_flwr

    if not run_syft_flwr():
        dataset = get_clientapp_dataset(partition_id, num_partitions)
    else:
        dataset = load_syftbox_dataset()

    metrics = {}
    # Compute some statistics for each column in the dataframe
    for feature_name in dataset.columns:
        # Compute histogram
        freqs, _ = np.histogram(dataset[feature_name], bins=np.linspace(2.0, 10.0, 10))
        metrics[feature_name] = freqs.tolist()

        # Compute weighted average
        metrics[f"{feature_name}_avg"] = dataset[feature_name].mean() * len(dataset)
        metrics[f"{feature_name}_count"] = len(dataset)

    reply_content = RecordDict({"query_results": MetricRecord(metrics)})

    return Message(reply_content, reply_to=msg)
