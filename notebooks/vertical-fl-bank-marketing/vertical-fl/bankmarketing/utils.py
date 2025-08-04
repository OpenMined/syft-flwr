import os
from collections import OrderedDict
from pathlib import Path
from typing import List

import numpy as np
import torch
from loguru import logger

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def get_parameters(net) -> List[np.ndarray]:
    return [val.cpu().numpy() for _, val in net.state_dict().items()]


def set_parameters(net, parameters: List[np.ndarray]):
    params_dict = zip(net.state_dict().keys(), parameters)
    state_dict = OrderedDict({k: torch.Tensor(v) for k, v in params_dict})
    net.load_state_dict(state_dict, strict=True)


def load_syftbox_dataset() -> tuple[torch.Tensor, torch.Tensor]:
    """Load training dataset from SyftBox data directory.

    Loads the training features and labels from numpy arrays stored in the
    SyftBox data directory. This function is used in vertical federated learning
    scenarios where clients need access to training data features.

    Example:
        >>> X_train, y_train = load_syftbox_dataset()
        >>> print(f"Features shape: {X_train.shape}")
        >>> print(f"Labels shape: {y_train.shape}")
    """
    from syft_flwr.utils import get_syftbox_dataset_path

    data_dir = get_syftbox_dataset_path()
    logger.info(f"getting dataset from {data_dir}")

    X_train = np.load(data_dir / "X_train.npy")
    y_train = np.load(data_dir / "y_train.npy")

    return (
        torch.FloatTensor(X_train),
        torch.LongTensor(y_train),
    )


def load_server_training_labels() -> torch.Tensor:
    """Load the server's training labels for VFL training.

    These labels correspond to the same samples that clients are working on.

    Returns:
        torch.Tensor: y_train tensor matching client training data
    """
    project_root = Path(__file__).parent.parent.parent
    train_labels_path = (
        project_root / "dataset" / "marketing" / "processed" / "server_train"
    )

    logger.info(f"Loading server training labels from {train_labels_path}")

    if not train_labels_path.exists():
        raise FileNotFoundError(
            f"Server training labels directory not found: {train_labels_path}"
        )

    # Use environment variable to control which dataset to load
    use_mock = os.getenv("USE_MOCK_DATA", "true").lower() == "true"

    if use_mock:
        y_train = np.load(train_labels_path / "y_mock.npy")
        logger.info(f"Loaded mock training labels with {len(y_train)} samples")
    else:
        y_train = np.load(train_labels_path / "y_train.npy")
        logger.info(f"Loaded full training labels with {len(y_train)} samples")

    return torch.LongTensor(y_train)
