from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

PROJECT_PATH = Path(__file__).parent.parent
DATSET_PATH = PROJECT_PATH / "dataset"


CONFIG = {
    "test_size": 0.2,
    "random_state": 42,
    "client_0_fraction": 0.5,
    "client_2_fraction": 0.3,
    "output_dir": str(DATSET_PATH / "marketing" / "processed"),
    "target_column": "y",
}


# Define column sets
BANK_COLS = [
    "age",
    "job",
    "marital",
    "education",
    "default",
    "housing",
    "loan",
    "duration",
]

MARKETING_COLS = [
    "contact",
    "month",
    "day_of_week",
    "campaign",
    "pdays",
    "previous",
    "poutcome",
]

CATEGORICAL_COLUMNS = [
    "job",
    "marital",
    "education",
    "default",
    "loan",
    "housing",
    "contact",
    "month",
    "day_of_week",
    "poutcome",
]

DATA_PARTITION_SETS = [
    BANK_COLS + [CONFIG["target_column"]],
    MARKETING_COLS + [CONFIG["target_column"]],
]

# Define descriptive folder names for data partitions
CLIENT_FOLDER_NAMES = ["bank_features", "marketing_features"]


def download_dataset_if_needed(data_path: str) -> None:
    """Download the bank marketing dataset from Kaggle if it doesn't exist."""
    target_file = Path(data_path)

    if target_file.exists():
        print(f"Dataset already exists at: {target_file}")
        return

    print("Dataset not found. Downloading from Kaggle...")

    try:
        import kagglehub
    except ImportError:
        print("Installing kagglehub...")
        import subprocess
        import sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "kagglehub"])
        import kagglehub

    # Create data directory
    target_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Download the dataset from Kaggle
        print("Downloading bank marketing dataset from Kaggle...")
        download_path = kagglehub.dataset_download(
            "volodymyrgavrysh/bank-marketing-campaigns-dataset"
        )

        # Find the CSV file in the downloaded directory
        downloaded_files = list(Path(download_path).glob("*.csv"))

        if downloaded_files:
            # Look for the specific file or use the first one
            source_file = None
            for file in downloaded_files:
                if "bank-additional-full" in file.name:
                    source_file = file
                    break

            if source_file is None:
                source_file = downloaded_files[0]

            print(f"Found file: {source_file}")

            # Copy to the expected location
            import shutil

            shutil.copy2(source_file, target_file)
            print(f"Dataset saved to: {target_file}")

            # Verify the file
            df = pd.read_csv(target_file, sep=";")
            print(f"Dataset verified - Shape: {df.shape}")

        else:
            print("No CSV files found in the downloaded dataset")
            # List all files to help debug
            all_files = list(Path(download_path).rglob("*"))
            print("Available files:")
            for file in all_files:
                print(f"  {file}")
            raise FileNotFoundError("Could not find the required CSV file")

    except Exception as e:
        print(f"Error downloading dataset: {e}")
        print("\nPlease manually download the dataset from:")
        print(
            "https://www.kaggle.com/datasets/volodymyrgavrysh/bank-marketing-campaigns-dataset"
        )
        print(f"And save it as: {target_file}")
        raise


def transform_data_oh(
    df: pd.DataFrame, categorical_columns: List[str], target_col: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    X = df.drop(target_col, axis=1)
    y = df[target_col].map({"no": 0, "yes": 1})
    X = pd.get_dummies(X, columns=categorical_columns).astype(np.float32)
    return X, y


def transform_data_le(
    df: pd.DataFrame, categorical_columns: List[str], target_col: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    X = df.drop(target_col, axis=1)
    y = df[target_col].map({"no": 0, "yes": 1})
    X[categorical_columns] = X[categorical_columns].apply(
        lambda x: x.astype("category").cat.codes
    )
    return X, y


def transform_data(
    df: pd.DataFrame,
    categorical_columns: List[str],
    target_col: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return transform_data_le(df, categorical_columns, target_col)


def load_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path, sep=";")


def create_federated_splits(
    X_train: pd.DataFrame, y_train: pd.Series
) -> Tuple[List[pd.DataFrame], List[pd.Series]]:
    X_splits = []
    y_splits = []

    # Create splits based on column sets - ALL CLIENTS GET SAME SAMPLES
    for cols in DATA_PARTITION_SETS:
        X_split = X_train[cols[:-1]]  # Exclude target column
        y_split = y_train  # ALL clients get same labels (same samples)
        X_splits.append(X_split)
        y_splits.append(y_split)

    return X_splits, y_splits


def create_balanced_mock_data(
    X_split: pd.DataFrame, y_split: pd.Series, mock_size: int = 10
) -> Tuple[pd.DataFrame, pd.Series]:
    """Create balanced mock data ensuring both classes are represented."""
    # Get unique classes
    unique_classes = y_split.unique()

    if len(unique_classes) == 1:
        # If only one class exists, just take the first mock_size samples
        return X_split.head(mock_size), y_split.head(mock_size)

    # Try to get equal representation of both classes
    samples_per_class = mock_size // len(unique_classes)
    remaining_samples = mock_size % len(unique_classes)

    mock_indices = []

    for i, class_label in enumerate(unique_classes):
        class_indices = y_split[y_split == class_label].index

        # Number of samples for this class
        n_samples = samples_per_class + (1 if i < remaining_samples else 0)
        n_samples = min(n_samples, len(class_indices))  # Don't exceed available samples

        # Sample indices for this class
        selected_indices = class_indices[:n_samples]
        mock_indices.extend(selected_indices)

    # If we don't have enough samples from balanced approach, fill with remaining
    if len(mock_indices) < mock_size:
        remaining_needed = mock_size - len(mock_indices)
        all_indices = set(y_split.index)
        used_indices = set(mock_indices)
        available_indices = list(all_indices - used_indices)

        additional_indices = available_indices[:remaining_needed]
        mock_indices.extend(additional_indices)

    # Sort indices to maintain order
    mock_indices = sorted(mock_indices[:mock_size])

    return X_split.loc[mock_indices], y_split.loc[mock_indices]


def create_readme_files(output_path: Path) -> None:
    """Create README.md files for each data partition."""

    # README content for partition 0 (Bank features)
    readme_0_content = """# Bank Marketing Dataset - Partition 0 (Bank Features)

This partition contains bank-related customer features from the Bank Marketing dataset.

## Features Included:
- **age**: Customer age (numeric)
- **job**: Type of job (categorical: 'admin.', 'blue-collar', 'entrepreneur', 'housemaid', 'management', 'retired', 'self-employed', 'services', 'student', 'technician', 'unemployed', 'unknown')
- **marital**: Marital status (categorical: 'divorced', 'married', 'single', 'unknown')
- **education**: Education level (categorical: 'basic.4y', 'basic.6y', 'basic.9y', 'high.school', 'illiterate', 'professional.course', 'university.degree', 'unknown')
- **default**: Has credit in default? (categorical: 'no', 'yes', 'unknown')
- **housing**: Has housing loan? (categorical: 'no', 'yes', 'unknown')
- **loan**: Has personal loan? (categorical: 'no', 'yes', 'unknown')
- **duration**: Last contact duration, in seconds (numeric)

## Target Variable:
- **y**: Has the client subscribed to a term deposit? (binary: 0='no', 1='yes')

## Data Format:
- **X_train.npy**: Training features (numpy array)
- **y_train.npy**: Training labels (numpy array)

This data is part of a vertical federated learning setup where different participants hold different feature sets of the same dataset.
"""

    # README content for partition 1 (Marketing features)
    readme_1_content = """# Bank Marketing Dataset - Partition 1 (Marketing Features)

This partition contains marketing campaign-related features from the Bank Marketing dataset.

## Features Included:
- **contact**: Contact communication type (categorical: 'cellular', 'telephone')
- **month**: Last contact month of year (categorical: 'jan', 'feb', 'mar', ..., 'nov', 'dec')
- **day_of_week**: Last contact day of the week (categorical: 'mon', 'tue', 'wed', 'thu', 'fri')
- **campaign**: Number of contacts performed during this campaign and for this client (numeric)
- **pdays**: Number of days that passed by after the client was last contacted from a previous campaign (numeric; 999 means client was not previously contacted)
- **previous**: Number of contacts performed before this campaign and for this client (numeric)
- **poutcome**: Outcome of the previous marketing campaign (categorical: 'failure', 'nonexistent', 'success')

## Target Variable:
- **y**: Has the client subscribed to a term deposit? (binary: 0='no', 1='yes')

## Data Format:
- **X_train.npy**: Training features (numpy array)
- **y_train.npy**: Training labels (numpy array)

This data is part of a vertical federated learning setup where different participants hold different feature sets of the same dataset.
"""

    # README content for mock data
    readme_mock_content = """# Mock Dataset (Sample Data)

This directory contains a small sample of the training data (10 rows) for development and testing purposes.

## Purpose:
- Quick testing and development
- Verification of data processing pipeline
- Demo purposes

## Data Format:
- **X_train.npy**: Sample training features (numpy array, 10 rows)
- **y_train.npy**: Sample training labels (numpy array, 10 rows)

## Note:
This is a subset of the full training data available in the `private/` directory.
"""

    # README content for private data
    readme_private_content = """# Private Dataset (Full Training Data)

This directory contains the complete training dataset for this client.

## Purpose:
- Full federated learning training
- Complete feature set for this participant

## Data Format:
- **X_train.npy**: Complete training features (numpy array)
- **y_train.npy**: Complete training labels (numpy array)

## Security:
This data represents the private dataset that would be held by this participant in a real federated learning scenario.
"""

    # Write README files for each client's mock and private directories
    readme_contents = [readme_0_content, readme_1_content]
    for i, content in enumerate(readme_contents):
        folder_name = CLIENT_FOLDER_NAMES[i]

        # Mock directory README
        mock_readme_path = output_path / folder_name / "mock" / "README.md"
        mock_readme_path.parent.mkdir(parents=True, exist_ok=True)
        with open(mock_readme_path, "w") as f:
            f.write(f"{content}\n\n{readme_mock_content}")

        # Private directory README
        private_readme_path = output_path / folder_name / "private" / "README.md"
        private_readme_path.parent.mkdir(parents=True, exist_ok=True)
        with open(private_readme_path, "w") as f:
            f.write(f"{content}\n\n{readme_private_content}")


def save_processed_data(
    X_splits: List[pd.DataFrame],
    y_splits: List[pd.Series],
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> None:
    # Create output directory if it doesn't exist
    output_path = Path(CONFIG["output_dir"])
    output_path.mkdir(parents=True, exist_ok=True)

    # Save training splits for each client
    for i, (X_split, y_split) in enumerate(zip(X_splits, y_splits)):
        folder_name = CLIENT_FOLDER_NAMES[i]

        # Create mock directory with 10 rows only
        mock_path = output_path / folder_name / "mock"
        mock_path.mkdir(parents=True, exist_ok=True)

        # Get balanced mock data ensuring both classes are represented
        X_mock, y_mock = create_balanced_mock_data(X_split, y_split, 10)

        np.save(mock_path / "X_train.npy", X_mock.values)
        np.save(mock_path / "y_train.npy", y_mock.values)

        # Create private directory with full data
        private_path = output_path / folder_name / "private"
        private_path.mkdir(parents=True, exist_ok=True)

        np.save(private_path / "X_train.npy", X_split.values)
        np.save(private_path / "y_train.npy", y_split.values)

    # Save TRAINING labels for server (same samples as clients)
    # In proper VFL, server needs training labels for the same samples clients are using
    server_train_path = output_path / "server_train"
    server_train_path.mkdir(parents=True, exist_ok=True)

    # Use the same labels that clients have (from any client since they're identical)
    server_train_labels = y_splits[0]  # All clients have same labels, so use first one
    np.save(server_train_path / "y_train.npy", server_train_labels.values)

    # Also save mock version for testing
    server_mock_labels = create_balanced_mock_data(
        pd.DataFrame(index=server_train_labels.index), server_train_labels, 10
    )[1]
    np.save(server_train_path / "y_mock.npy", server_mock_labels.values)

    # Create README files
    create_readme_files(output_path)

    # Create README for server training labels
    server_train_readme = """# Server Training Labels

This directory contains training labels for the server in the vertical federated learning setup.

## Purpose:
In VFL, the server acts as the label holder and coordinates training using the same samples
that clients are working on, but with access to the ground truth labels.

## Files:
- **y_train.npy**: Training labels for the same samples clients are using
- **y_mock.npy**: Mock training labels (10 samples) for testing

## Note:
These labels correspond to the exact same samples (row indices) that clients have in their
training data, ensuring proper vertical federated learning alignment.
"""

    with open(server_train_path / "README.md", "w") as f:
        f.write(server_train_readme)


def process_marketing_data(data_path: str) -> None:
    # Download dataset if needed
    download_dataset_if_needed(data_path)

    # Load data
    df = load_data(data_path)

    # Transform data
    X, y = transform_data(df, CATEGORICAL_COLUMNS, CONFIG["target_column"])

    # Split into train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=CONFIG["test_size"], random_state=CONFIG["random_state"]
    )

    # Create federated splits
    X_splits, y_splits = create_federated_splits(X_train, y_train)

    # Save processed data
    save_processed_data(X_splits, y_splits, X_test, y_test)

    print(f"Data processing complete. Saved to {CONFIG['output_dir']}")
    print(f"Number of clients: {len(X_splits)}")
    for i, (X_split, y_split) in enumerate(zip(X_splits, y_splits)):
        print(f"Client {i}: {len(X_split)} samples")


if __name__ == "__main__":
    # data link: https://www.kaggle.com/datasets/volodymyrgavrysh/bank-marketing-campaigns-dataset
    process_marketing_data(DATSET_PATH / "bank-additional-full.csv")
