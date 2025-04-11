# Step 1: task.py
# Client APP load data functions
"""
def load_syftbox_dataset() -> tuple[DataLoader, DataLoader]:
    from syft_flwr.utils import get_syftbox_dataset_path

    data_dir = get_syftbox_dataset_path()
    return load_data_from_disk(data_dir)


def load_data_from_disk(path: str, batch_size: int = 32):
    from datasets import load_from_disk

    partition_train_test = load_from_disk(path)
    pytorch_transforms = Compose(
        [ToTensor(), Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))]
    )

    def apply_transforms(batch):
        batch["img"] = [pytorch_transforms(img) for img in batch["img"]]
        return batch

    partition_train_test = partition_train_test.with_transform(apply_transforms)
    trainloader = DataLoader(
        partition_train_test["train"], batch_size=batch_size, shuffle=True
    )
    testloader = DataLoader(partition_train_test["test"], batch_size=batch_size)
    return trainloader, testloader
"""

# Step 2: client_app.py
# Client App Load Data
"""
from quickstart_pytorch.task import load_syftbox_dataset
from syft_flwr.utils import run_syft_flwr

if not run_syft_flwr():
    partition_id = context.node_config["partition-id"]
    num_partitions = context.node_config["num-partitions"]
    trainloader, valloader = load_data(partition_id, num_partitions)
else:
    trainloader, valloader = load_syftbox_dataset()
"""

# Step 3: server_app.py
"""
from pathlib import Path
from syft_flwr.strategy import FedAvgWithModelSaving

# Define strategy
strategy = FedAvgWithModelSaving(
    save_path=Path(__file__).parent.parent.parent / "weights",
    fraction_fit=fraction_fit,
    fraction_evaluate=1.0,
    min_available_clients=2,
    initial_parameters=parameters,
)
"""
