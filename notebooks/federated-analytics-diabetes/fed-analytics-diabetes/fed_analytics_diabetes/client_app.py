"""pandas_example: A Flower / Pandas app."""

import warnings

import numpy as np
import pandas as pd
from flwr.client import ClientApp
from flwr.common import Context, Message, MetricRecord, RecordDict
from flwr_datasets import FederatedDataset
from flwr_datasets.partitioner import IidPartitioner
from loguru import logger

warnings.filterwarnings("ignore", category=UserWarning)


KEY_DIABETES_FEATURES = ["Glucose", "BMI", "Age"]
DIABETES_OUTCOME_COLUMN = "y"
FEATURE_BINS = {
    "Glucose": np.linspace(40, 250, 11),  # 10 bins from 40 to 250
    "BMI": np.linspace(15, 60, 10),  # 9 bins from 15 to 60
    "Age": np.linspace(20, 90, 15),  # 14 bins from 20 to 90
}


def load_syftbox_dataset() -> pd.DataFrame:
    from loguru import logger

    from syft_flwr.utils import get_syftbox_dataset_path

    data_dir = get_syftbox_dataset_path()
    df_train = pd.read_csv(data_dir / "train.csv")
    df_test = pd.read_csv(data_dir / "test.csv")
    df: pd.DataFrame = pd.concat([df_train, df_test], ignore_index=True)
    logger.info(f"Loaded syftbox dataset from {data_dir}")
    logger.info(f"Dataset head: {df.head(2)}")

    return df[KEY_DIABETES_FEATURES + [DIABETES_OUTCOME_COLUMN]]


def load_flwr_data(partition_id: int, num_partitions: int) -> pd.DataFrame:
    """
    Load the `fl-diabetes-prediction` dataset to memory
    """
    logger.info(
        f"Loading FLWR data for partition {partition_id} of {num_partitions} partitions"
    )
    partitioner = IidPartitioner(num_partitions=num_partitions)
    fds = FederatedDataset(
        dataset="khoaguin/pima-indians-diabetes-database",
        partitioners={"train": partitioner},
    )

    partition: pd.DataFrame = fds.load_partition(partition_id, "train").with_format(
        "pandas"
    )[:]

    return partition[KEY_DIABETES_FEATURES + [DIABETES_OUTCOME_COLUMN]]


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
        df = load_flwr_data(partition_id, num_partitions)
    else:
        df = load_syftbox_dataset()

    # Ensure Glucose, BMI, Age are numeric and handle potential issues if necessary
    df["Glucose"] = pd.to_numeric(df["Glucose"], errors="coerce")
    df["BMI"] = pd.to_numeric(df["BMI"], errors="coerce")
    df["Age"] = pd.to_numeric(df["Age"], errors="coerce")

    metrics = {}
    for feature_name in KEY_DIABETES_FEATURES:
        logger.info(f"Calculating metrics for feature: {feature_name}")

        if feature_name not in df.columns:
            logger.warning(
                f"Feature '{feature_name}' not found in DataFrame. Skipping."
            )
            continue

        current_bin_edges = FEATURE_BINS[feature_name]

        # Metrics for y=0
        subset_no_diabetes = df[df[DIABETES_OUTCOME_COLUMN] == 0]
        feature_data_outcome0 = subset_no_diabetes[feature_name].dropna()

        if not feature_data_outcome0.empty:
            freqs_0, _ = np.histogram(feature_data_outcome0, bins=current_bin_edges)
            metrics[f"{feature_name}_hist_outcome0"] = freqs_0.tolist()
            metrics[f"{feature_name}_mean_outcome0"] = float(
                feature_data_outcome0.mean()
            )
            metrics[f"{feature_name}_sum_outcome0"] = int(feature_data_outcome0.sum())
            metrics[f"{feature_name}_count_outcome0"] = len(feature_data_outcome0)
        else:  # Handle case where feature_data_outcome0 is empty
            metrics[f"{feature_name}_hist_outcome0"] = [0] * (
                len(current_bin_edges) - 1
            )
            metrics[f"{feature_name}_mean_outcome0"] = np.nan
            metrics[f"{feature_name}_sum_outcome0"] = np.nan
            metrics[f"{feature_name}_count_outcome0"] = 0

        # Metrics for y=1
        subset_diabetes = df[df[DIABETES_OUTCOME_COLUMN] == 1]
        feature_data_outcome1 = subset_diabetes[feature_name].dropna()

        if not feature_data_outcome1.empty:
            freqs_1, _ = np.histogram(feature_data_outcome1, bins=current_bin_edges)
            metrics[f"{feature_name}_hist_outcome1"] = freqs_1.tolist()
            metrics[f"{feature_name}_mean_outcome1"] = float(
                feature_data_outcome1.mean()
            )
            metrics[f"{feature_name}_sum_outcome1"] = int(feature_data_outcome1.sum())
            metrics[f"{feature_name}_count_outcome1"] = len(feature_data_outcome1)
        else:  # Handle case where feature_data_outcome1 is empty
            metrics[f"{feature_name}_hist_outcome1"] = [0] * (
                len(current_bin_edges) - 1
            )
            metrics[f"{feature_name}_mean_outcome1"] = np.nan
            metrics[f"{feature_name}_sum_outcome1"] = np.nan
            metrics[f"{feature_name}_count_outcome1"] = 0

    logger.info(f"Metrics: {metrics}")

    reply_content = RecordDict({"query_results": MetricRecord(metrics)})

    return Message(reply_content, reply_to=msg)
