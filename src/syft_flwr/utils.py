import os
import re
import zlib
from pathlib import Path

from flwr_datasets import FederatedDataset
from flwr_datasets.partitioner import IidPartitioner
from loguru import logger
from typing_extensions import Union

EMAIL_REGEX = r"^[^@]+@[^@]+\.[^@]+$"


def is_valid_datasite(datasite: str) -> bool:
    return re.match(EMAIL_REGEX, datasite)


def str_to_int(input_string: str) -> int:
    """Convert a string to an int32"""
    return zlib.crc32(input_string.encode())


def get_syftbox_dataset_path() -> Path:
    """Get the path to the syftbox dataset from the environment variable"""
    data_dir = Path(os.getenv("DATA_DIR", ".data/"))
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Path {data_dir} does not exist (must be a valid file or directory)"
        )
    return data_dir


def run_syft_flwr() -> bool:
    try:
        get_syftbox_dataset_path()
        return True
    except FileNotFoundError:
        return False


def save_dataset_to_disk(
    dataset_name: str, dataset_dir: Union[str, Path], num_partitions: int = 2
) -> None:
    """This function downloads the Fashion-MNIST / CIFAR10 dataset,
    generates N partitions and save them to disk under the `dataset_dir` directory.

    Ref: https://github.com/adap/flower/blob/main/examples/embedded-devices/generate_dataset.py
    """
    save_dataset_dir = Path(dataset_dir) / dataset_name
    if not save_dataset_dir.is_absolute():
        save_dataset_dir = save_dataset_dir.expanduser().absolute()
    if save_dataset_dir.exists():
        logger.info(f"Dataset {dataset_name} already exists in {save_dataset_dir}")
        return
    if not save_dataset_dir.exists():
        save_dataset_dir.mkdir(parents=True, exist_ok=True)

    dataset_full_name = None
    if dataset_name in ["fashion_mnist", "fmnist", "fashionmnist"]:
        dataset_full_name = "zalando-datasets/fashion_mnist"
    elif dataset_name in ["cifar10", "cifar"]:
        dataset_full_name = "uoft-cs/cifar10"
    else:
        raise ValueError(f"Dataset {dataset_name} not supported")

    partitioner = IidPartitioner(num_partitions=num_partitions)
    fds = FederatedDataset(
        dataset=dataset_full_name,
        partitioners={"train": partitioner},
    )

    for partition_id in range(num_partitions):
        partition = fds.load_partition(partition_id)
        partition_train_test = partition.train_test_split(test_size=0.2, seed=42)
        file_path = f"{save_dataset_dir}/{dataset_name}_part_{partition_id + 1}"
        partition_train_test.save_to_disk(file_path)

    logger.info(f"Dataset {dataset_name} saved to {save_dataset_dir}")
