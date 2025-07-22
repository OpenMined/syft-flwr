from collections import OrderedDict
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


def load_syftbox_dataset(
    id: int,
) -> tuple[torch.utils.data.TensorDataset, torch.utils.data.TensorDataset]:
    from syft_flwr.utils import get_syftbox_dataset_path

    data_dir = get_syftbox_dataset_path()
    logger.info(f"getting dataset from {data_dir}")

    train_path = data_dir / f"marketing-data-{id}"
    test_path = data_dir / "marketing-data-test"

    X_train = np.load(train_path / "X_train.npy")
    y_train = np.load(train_path / "y_train.npy")

    X_test = np.load(test_path / "X_test.npy")
    y_test = np.load(test_path / "y_test.npy")

    # tensor_train_dataset = torch.utils.data.TensorDataset(torch.FloatTensor(X_train), torch.LongTensor(y_train))
    # tensor_test_dataset = torch.utils.data.TensorDataset(torch.FloatTensor(X_test), torch.LongTensor(y_test))

    return (
        torch.FloatTensor(X_train),
        torch.LongTensor(y_train),
        torch.FloatTensor(X_test),
        torch.LongTensor(y_test),
    )
