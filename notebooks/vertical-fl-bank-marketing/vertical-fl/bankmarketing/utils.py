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


def load_syftbox_dataset() -> (
    tuple[torch.utils.data.TensorDataset, torch.utils.data.TensorDataset]
):
    from syft_flwr.utils import get_syftbox_dataset_path

    data_dir = get_syftbox_dataset_path()
    logger.info(f"getting dataset from {data_dir}")

    X_train = np.load(data_dir / "X_train.npy")
    y_train = np.load(data_dir / "y_train.npy")

    return (
        torch.FloatTensor(X_train),
        torch.LongTensor(y_train),
    )


def load_server_test_dataset() -> tuple[torch.Tensor, torch.Tensor]:
    """Load the server's test dataset for evaluation purposes.

    Returns:
        tuple: X_test, y_test tensors for server evaluation
    """
    # Get the path to the test data directory
    project_root = Path(__file__).parent.parent.parent
    test_data_path = (
        project_root / "dataset" / "marketing" / "processed" / "server_test"
    )

    logger.info(f"Loading server test dataset from {test_data_path}")

    if not test_data_path.exists():
        raise FileNotFoundError(f"Test data directory not found: {test_data_path}")

    X_test = np.load(test_data_path / "X_test.npy")
    y_test = np.load(test_data_path / "y_test.npy")

    logger.info(f"Loaded test dataset with {len(X_test)} samples")

    return torch.FloatTensor(X_test), torch.LongTensor(y_test)
