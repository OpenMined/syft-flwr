from pathlib import Path

from flwr_datasets import FederatedDataset
from flwr_datasets.partitioner import IidPartitioner
from loguru import logger
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder
from typing_extensions import Union


def save_readme(
    dataset_name: str, save_dataset_dir: Union[str, Path], num_partitions: int = 2
) -> None:
    with open(save_dataset_dir / "README.md", "w") as f:
        f.write(
            f"# {dataset_name}\n"
            f"## Number of Partitions: {num_partitions}\n"
            f"## Description:\n"
            f"This is {dataset_name} partitioned into {num_partitions} partitions.\n"
        )
    logger.info(f"README file created at {save_dataset_dir}/README.md")


def save_image_dataset(
    dataset_name: str,
    dataset_full_name: str,
    save_dataset_dir: Union[str, Path],
    num_partitions: int = 2,
) -> None:
    partitioner = IidPartitioner(num_partitions=num_partitions)
    fds = FederatedDataset(
        dataset=dataset_full_name,
        partitioners={"train": partitioner},
    )

    for partition_id in range(num_partitions):
        partition = fds.load_partition(partition_id)
        partition_train_test = partition.train_test_split(
            test_size=0.01, train_size=0.01, seed=42
        )
        file_path = f"{save_dataset_dir}/{dataset_name}_part_{partition_id + 1}"
        partition_train_test.save_to_disk(file_path)

    logger.info(f"Dataset {dataset_name} saved to {save_dataset_dir}")

    save_readme(dataset_name, save_dataset_dir, num_partitions)


def save_census_dataset(
    dataset_name: str,
    dataset_full_name: str,
    save_dataset_dir: Union[str, Path],
    num_partitions: int = 2,
) -> None:
    partitioner = IidPartitioner(num_partitions=num_partitions)
    fds = FederatedDataset(
        dataset=dataset_full_name,
        partitioners={"train": partitioner},
    )

    for partition_id in range(num_partitions):
        partition_dir = save_dataset_dir / f"part_{partition_id}"
        partition_dir.mkdir(exist_ok=True)

        dataset = fds.load_partition(partition_id, "train").with_format("pandas")[:]
        dataset.dropna(inplace=True)
        categorical_cols = dataset.select_dtypes(include=["object"]).columns
        ordinal_encoder = OrdinalEncoder()
        dataset[categorical_cols] = ordinal_encoder.fit_transform(
            dataset[categorical_cols]
        )

        X = dataset.drop("income", axis=1)
        y = dataset["income"]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        # Save to disk
        import pandas as pd

        train_data = pd.concat([X_train, y_train], axis=1)
        test_data = pd.concat([X_test, y_test], axis=1)

        train_data.to_csv(partition_dir / "train.csv", index=False)
        test_data.to_csv(partition_dir / "test.csv", index=False)

    logger.info(f"Dataset {dataset_name} saved to {save_dataset_dir}")

    save_readme(dataset_name, save_dataset_dir, num_partitions)


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
        save_image_dataset(
            dataset_name, dataset_full_name, save_dataset_dir, num_partitions
        )
    elif dataset_name in ["cifar10", "cifar"]:
        dataset_full_name = "uoft-cs/cifar10"
        save_image_dataset(
            dataset_name, dataset_full_name, save_dataset_dir, num_partitions
        )
    elif dataset_name in ["adult_census_income", "adult_income"]:
        dataset_full_name = "scikit-learn/adult-census-income"
        save_census_dataset(
            dataset_name, dataset_full_name, save_dataset_dir, num_partitions
        )
    else:
        raise ValueError(f"Dataset {dataset_name} not supported")


if __name__ == "__main__":
    # get dataset name from command line
    import sys

    dataset_name = sys.argv[1]
    save_dataset_to_disk(dataset_name, "data/")
