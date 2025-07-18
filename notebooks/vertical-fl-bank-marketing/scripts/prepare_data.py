import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, List
from sklearn.model_selection import train_test_split


CONFIG = {
    'test_size': 0.2,
    'random_state': 42,
    'client_0_fraction': 0.5,
    'client_2_fraction': 0.3,
    'output_dir': './notebooks/vertical-fl-bank-marketing/data',
    'target_column': 'y'
}

# Define column sets
BANK_COLS = [
    'age', 'job', 'marital', 'education', 'default', 'housing', 'loan', 'duration'
]

MARKETING_COLS = [
    'contact', 'month', 'day_of_week', 'campaign', 'pdays', 'previous', 'poutcome',
]

CATEGORICAL_COLUMNS = [
    "job", "marital", "education", "default", "loan", "housing", 
    "contact", "month", "day_of_week", "poutcome"
]

DATA_PARTITION_SETS = [
    BANK_COLS + [CONFIG['target_column']],
    MARKETING_COLS + [CONFIG['target_column']],
]


def transform_data_oh(
    df: pd.DataFrame, 
    categorical_columns: List[str], 
    target_col: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    X = df.drop(target_col, axis=1)
    y = df[target_col].map({"no": 0, "yes": 1})
    X = pd.get_dummies(X, columns=categorical_columns).astype(np.float32)
    return X, y


def transform_data_le(
    df: pd.DataFrame, 
    categorical_columns: List[str], 
    target_col: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    X = df.drop(target_col, axis=1)
    y = df[target_col].map({"no": 0, "yes": 1})
    X[categorical_columns] = X[categorical_columns].apply(lambda x: x.astype("category").cat.codes)
    return X, y


def transform_data(
    df: pd.DataFrame, 
    categorical_columns: List[str], 
    target_col: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return transform_data_le(df, categorical_columns, target_col)


def load_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path, sep=";")


def create_federated_splits(X_train: pd.DataFrame, y_train: pd.Series) -> Tuple[List[pd.DataFrame], List[pd.Series]]:
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


def _apply_client_sampling_strategies(X_splits: List[pd.DataFrame], y_splits: List[pd.Series]) -> Tuple[List[pd.DataFrame], List[pd.Series]]:
    # Client 0: Sample 50% of data
    X_splits[0] = X_splits[0].sample(frac=CONFIG['client_0_fraction'], random_state=CONFIG['random_state'])
    y_splits[0] = y_splits[0].loc[X_splits[0].index]
    
    # Client 1: Remove overlap with client 0
    overlap_indices = X_splits[0].index.intersection(X_splits[1].index)
    X_splits[1] = X_splits[1].drop(overlap_indices)
    y_splits[1] = y_splits[1].drop(overlap_indices)
    
    return X_splits, y_splits


def save_processed_data(X_splits: List[pd.DataFrame], y_splits: List[pd.Series], 
                       X_test: pd.DataFrame, y_test: pd.Series) -> None:
    # Create output directory if it doesn't exist
    output_path = Path(CONFIG['output_dir'])
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save training splits
    for i, (X_split, y_split) in enumerate(zip(X_splits, y_splits)):
        client_path = output_path / str(i)
        client_path.mkdir(parents=True, exist_ok=True)
        np.save(client_path / f'X_train.npy', X_split.values)
        np.save(client_path / f'y_train.npy', y_split.values)
    
    # Save test data
    test_path = output_path / 'test'
    test_path.mkdir(parents=True, exist_ok=True)
    np.save(test_path / 'X_test.npy', X_test.values)
    np.save(test_path / 'y_test.npy', y_test.values)


def process_marketing_data(data_path: str) -> None:
    # Load data
    df = load_data(data_path)
    
    # Transform data
    X, y = transform_data(df, CATEGORICAL_COLUMNS, CONFIG['target_column'])
    
    # Split into train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=CONFIG['test_size'], 
        random_state=CONFIG['random_state']
    )
    
    # Create federated splits
    X_splits, y_splits = create_federated_splits(X_train, y_train)
    
    # Save processed data
    save_processed_data(X_splits, y_splits, X_test, y_test)
    
    print(f"Data processing complete. Saved to {CONFIG['output_dir']}")
    print(f"Number of clients: {len(X_splits)}")
    for i, (X_split, y_split) in enumerate(zip(X_splits, y_splits)):
        print(f"Client {i}: {len(X_split)} samples")


if __name__ == '__main__':
    # data link: https://www.kaggle.com/datasets/volodymyrgavrysh/bank-marketing-campaigns-dataset
    process_marketing_data("./data/bank-additional-full.csv")
