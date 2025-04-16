# Step 1: task.py
# Client APP load data functions
# You can add these 2 functions anywhere in the task.py file
"""
def load_syftbox_dataset() -> tuple[DataLoader, DataLoader]:
    from syft_flwr.utils import get_syftbox_dataset_path

    data_dir = get_syftbox_dataset_path()
    return load_data_from_disk(data_dir)


def load_data_from_disk(path: str, batch_size: int = 32):
    """Load a partition of the dataset from disk.

    Args:
        path: Path to the partition directory containing train.csv and test.csv
        batch_size: Batch size for DataLoader

    Returns:
        Tuple of (train_loader, test_loader)
    """
    import pandas as pd
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    from pathlib import Path

    # Load data from CSV files
    train_data = pd.read_csv(Path(path) / "train.csv")
    test_data = pd.read_csv(Path(path) / "test.csv")

    # Split features and labels
    X_train = train_data.drop("income", axis=1)
    y_train = train_data["income"]
    X_test = test_data.drop("income", axis=1)
    y_test = test_data["income"]

    numeric_features = X_train.select_dtypes(include=["float64", "int64"]).columns
    numeric_transformer = Pipeline(steps=[("scaler", StandardScaler())])

    preprocessor = ColumnTransformer(
        transformers=[("num", numeric_transformer, numeric_features)]
    )

    X_train = preprocessor.fit_transform(X_train)
    X_test = preprocessor.transform(X_test)

    # Convert to PyTorch tensors - X_train and X_test are already numpy arrays
    X_train_tensor = torch.tensor(X_train, dtype=torch.float32)
    X_test_tensor = torch.tensor(X_test, dtype=torch.float32)
    # y_train and y_test are still pandas Series, so we need .values
    y_train_tensor = torch.tensor(y_train.values, dtype=torch.float32).view(-1, 1)
    y_test_tensor = torch.tensor(y_test.values, dtype=torch.float32).view(-1, 1)

    # Create datasets and dataloaders
    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
    test_dataset = TensorDataset(X_test_tensor, y_test_tensor)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    return train_loader, test_loader
"""

# Step 2: client_app.py
# Client App Load Data
# Please put the replace the line 43-45 of  client_app.py
# with the following code
"""
    from fltabular.task import load_syftbox_dataset
    from syft_flwr.utils import run_syft_flwr

    if not run_syft_flwr():
        partition_id = context.node_config["partition-id"]
        train_loader, test_loader = load_data(
            partition_id=partition_id, num_partitions=context.node_config["num-partitions"]
        )
    else:
        train_loader, test_loader = load_syftbox_dataset()
"""

# Step 3: server_app.py (Optional)
# We use this to save the model weights of each round for the data scientist
# Please replace the server_app.py's FedAvg with the following code
"""
    from pathlib import Path
    from syft_flwr.strategy import FedAvgWithModelSaving

    strategy = FedAvgWithModelSaving(
        save_path=Path(__file__).parent.parent.parent / "weights",
        fraction_evaluate=1.0,
        min_available_clients=2,
        initial_parameters=params,
        evaluate_metrics_aggregation_fn=weighted_average,
    )
"""

# Step 4: pyproject.toml
# Reduce the num-server-rounds to 2 or 3 for faster runs
