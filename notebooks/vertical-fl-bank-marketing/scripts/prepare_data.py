from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


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


CONFIG = {
    "test_size": 0.2,
    "random_state": 42,
    "client_0_fraction": 0.5,
    "client_2_fraction": 0.3,
    "output_dir": "./data/marketing/processed",
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

    # Create splits based on column sets
    for cols in DATA_PARTITION_SETS:
        X_split = X_train[cols[:-1]]  # Exclude target column
        y_split = y_train
        X_splits.append(X_split)
        y_splits.append(y_split)

    # Apply different sampling strategies for each client
    X_splits, y_splits = _apply_client_sampling_strategies(X_splits, y_splits)

    return X_splits, y_splits


def _apply_client_sampling_strategies(
    X_splits: List[pd.DataFrame], y_splits: List[pd.Series]
) -> Tuple[List[pd.DataFrame], List[pd.Series]]:
    # Client 0: Sample 50% of data
    X_splits[0] = X_splits[0].sample(
        frac=CONFIG["client_0_fraction"], random_state=CONFIG["random_state"]
    )
    y_splits[0] = y_splits[0].loc[X_splits[0].index]

    # Client 1: Remove overlap with client 0
    overlap_indices = X_splits[0].index.intersection(X_splits[1].index)
    X_splits[1] = X_splits[1].drop(overlap_indices)
    y_splits[1] = y_splits[1].drop(overlap_indices)

    return X_splits, y_splits


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

    # README content for test partition
    readme_test_content = """# Bank Marketing Dataset - Test Set

This partition contains the test dataset used for model evaluation in the vertical federated learning setup.

## Purpose:
This test set is used to evaluate the performance of the federated learning model trained on the distributed bank marketing data.

## Features:
The test set contains all features from both partitions:

### Bank Features:
- age, job, marital, education, default, housing, loan, duration

### Marketing Features:
- contact, month, day_of_week, campaign, pdays, previous, poutcome

## Target Variable:
- **y**: Has the client subscribed to a term deposit? (binary: 0='no', 1='yes')

## Data Format:
- **X_test.npy**: Test features (numpy array)
- **y_test.npy**: Test labels (numpy array)

## Usage:
This dataset is used for final model evaluation after the vertical federated learning training process is complete.
"""

    # Write README files
    readme_contents = [readme_0_content, readme_1_content]
    for i, content in enumerate(readme_contents):
        readme_path = output_path / str(i) / "README.md"
        with open(readme_path, "w") as f:
            f.write(content)

    # Write test README
    test_readme_path = output_path / "test" / "README.md"
    with open(test_readme_path, "w") as f:
        f.write(readme_test_content)


def save_processed_data(
    X_splits: List[pd.DataFrame],
    y_splits: List[pd.Series],
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> None:
    # Create output directory if it doesn't exist
    output_path = Path(CONFIG["output_dir"])
    output_path.mkdir(parents=True, exist_ok=True)

    # Save training splits
    for i, (X_split, y_split) in enumerate(zip(X_splits, y_splits)):
        client_path = output_path / str(i)
        client_path.mkdir(parents=True, exist_ok=True)
        np.save(client_path / "X_train.npy", X_split.values)
        np.save(client_path / "y_train.npy", y_split.values)

    # Save test data
    test_path = output_path / "test"
    test_path.mkdir(parents=True, exist_ok=True)
    np.save(test_path / "X_test.npy", X_test.values)
    np.save(test_path / "y_test.npy", y_test.values)

    # Create README files
    create_readme_files(output_path)


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
    process_marketing_data("./data/bank-additional-full.csv")
