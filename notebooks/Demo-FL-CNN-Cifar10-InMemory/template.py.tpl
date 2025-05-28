# Step 1: task.py
# Client APP load data functions
# You can add these 2 functions anywhere in the task.py file
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
# Please put the replace the line 43-45 of  client_app.py
# with the following code
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

# Step 3: server_app.py (Optional)
# We use this to save the model weights of each round for the data scientist
# Please replace the server_app.py's FedAvg with the following code
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
