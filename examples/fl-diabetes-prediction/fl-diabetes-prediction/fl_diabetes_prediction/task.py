from collections import OrderedDict

import torch
import torch.nn as nn
import torch.optim as optim
from flwr_datasets import FederatedDataset
from flwr_datasets.partitioner import IidPartitioner
from imblearn.over_sampling import SMOTE
from loguru import logger
from pandas import DataFrame
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset


def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif torch.backends.mps.is_available():
        return torch.device("mps")
    elif torch.xpu.is_available():
        return torch.device("xpu")
    else:
        return torch.device("cpu")


DEVICE = get_device()
logger.info(f"Using device: {DEVICE}")


class Net(nn.Module):
    def __init__(self, input_dim=6):
        super(Net, self).__init__()
        # First layer with more units and batch normalization
        self.layer1 = nn.Sequential(
            nn.Linear(input_dim, 32),  # Increased from 20 to 32
            nn.BatchNorm1d(32),  # Added batch normalization
            nn.LeakyReLU(0.1),  # LeakyReLU instead of ReLU
            nn.Dropout(0.2),  # Increased dropout
        )

        # Second layer with more units
        self.layer2 = nn.Sequential(
            nn.Linear(32, 24),  # Increased from 14 to 24
            nn.BatchNorm1d(24),  # Added batch normalization
            nn.LeakyReLU(0.1),
            nn.Dropout(0.25),
        )

        # Third layer
        self.layer3 = nn.Sequential(
            nn.Linear(24, 16), nn.BatchNorm1d(16), nn.LeakyReLU(0.1)
        )

        # Output layer
        self.output_layer = nn.Sequential(nn.Linear(16, 1), nn.Sigmoid())

    def forward(self, x):
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.output_layer(x)
        return x


def dataset_processing(
    train_df: DataFrame, test_df: DataFrame
) -> tuple[DataLoader, DataLoader]:
    def preprocess_df(df: DataFrame) -> DataFrame:
        columns_to_drop = ["SkinThickness", "Insulin"]
        df_new: DataFrame = df.drop(columns_to_drop, axis=1)

        # Calculate mean and median (excluding zeros)
        mean_glucose = df_new[df_new["Glucose"] != 0]["Glucose"].mean()
        median_bmi = df_new[df_new["BMI"] != 0]["BMI"].median()
        median_bp = df_new[df_new["BloodPressure"] != 0]["BloodPressure"].median()

        # Replace zeros values with mean/median
        df_new.replace(
            {
                "Glucose": {0: mean_glucose},
                "BMI": {0: median_bmi},
                "BloodPressure": {0: median_bp},
            },
            inplace=True,
        )

        return df_new

    # Preprocess both datasets
    train_processed = preprocess_df(train_df)
    test_processed = preprocess_df(test_df)

    # Split features and labels for both sets
    X_train = train_processed.values[:, :6]
    y_train = train_processed.values[:, 6:]
    X_test = test_processed.values[:, :6]
    y_test = test_processed.values[:, 6:]

    from collections import Counter

    def get_minority_class_count(y):
        return min(Counter(y.flatten()).values())

    minority_count = get_minority_class_count(y_train)
    k_neighbors = min(5, minority_count - 1) if minority_count > 1 else 1

    # Resample the training data to fix the class imbalance
    smote = SMOTE(random_state=42, k_neighbors=k_neighbors)
    X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)

    # Scale the data to have zero mean and unit variance
    scaler = StandardScaler()
    X_train_resampled = scaler.fit_transform(X_train_resampled)
    X_test = scaler.transform(X_test)

    # Convert numpy arrays to PyTorch tensors
    X_train_tensor = torch.FloatTensor(X_train_resampled)
    y_train_tensor = torch.FloatTensor(y_train_resampled).reshape(
        -1, 1
    )  # Add this reshape
    X_test_tensor = torch.FloatTensor(X_test)
    y_test_tensor = torch.FloatTensor(y_test).reshape(-1, 1)

    # Create datasets and dataloaders
    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
    test_dataset = TensorDataset(X_test_tensor, y_test_tensor)

    train_loader = DataLoader(dataset=train_dataset, batch_size=10, shuffle=True)
    test_loader = DataLoader(
        dataset=test_dataset, batch_size=len(test_dataset), shuffle=False
    )

    return train_loader, test_loader


def load_syftbox_dataset() -> tuple[DataLoader, DataLoader]:
    import pandas as pd

    from syft_flwr.utils import get_syftbox_dataset_path

    data_dir = get_syftbox_dataset_path()
    logger.info(f"Loading dataset from {data_dir}")

    train_df = pd.read_csv(data_dir / "train.csv")
    test_df = pd.read_csv(data_dir / "test.csv")

    return dataset_processing(train_df, test_df)


fds = None  # Cache FederatedDataset


def load_flwr_data(
    partition_id: int, num_partitions: int
) -> tuple[DataLoader, DataLoader]:
    """
    Load the `fl-diabetes-prediction` dataset to memory
    """
    global fds
    if fds is None:
        partitioner = IidPartitioner(num_partitions=num_partitions)
        fds = FederatedDataset(
            dataset="khoaguin/pima-indians-diabetes-database",
            partitioners={"train": partitioner},
        )

    partition: DataFrame = fds.load_partition(partition_id, "train").with_format(
        "pandas"
    )[:]
    train_df, test_df = train_test_split(partition, test_size=0.2, random_state=95)

    return dataset_processing(train_df, test_df)


def train(model, train_loader, local_epochs=1):
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=0.0005)
    history = {"train_loss": [], "train_acc": []}
    model.to(DEVICE)

    for epoch in range(local_epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for inputs, labels in train_loader:
            inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)

            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * inputs.size(0)
            predicted = (outputs > 0.5).float()
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

        epoch_loss = running_loss / len(train_loader.dataset)
        epoch_acc = correct / total
        history["train_loss"].append(epoch_loss)
        history["train_acc"].append(epoch_acc)

    return history


def evaluate(model, data_loader):
    model.to(DEVICE)
    model.eval()
    criterion = nn.BCELoss()

    running_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for inputs, labels in data_loader:
            inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            running_loss += loss.item() * inputs.size(0)
            predicted = (outputs > 0.5).float()
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    epoch_loss = running_loss / len(data_loader.dataset)
    epoch_acc = correct / total

    return epoch_loss, epoch_acc


def set_weights(model, parameters):
    params_dict = zip(model.state_dict().keys(), parameters)
    state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
    model.load_state_dict(state_dict, strict=True)


def get_weights(model):
    ndarrays = [val.cpu().numpy() for _, val in model.state_dict().items()]
    return ndarrays
