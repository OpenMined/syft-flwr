import torch

import numpy as np

from typing import List
from collections import OrderedDict

from sklearn.metrics import accuracy_score, roc_auc_score


DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def get_parameters(net) -> List[np.ndarray]:
    return [val.cpu().numpy() for _, val in net.state_dict().items()]


def set_parameters(net, parameters: List[np.ndarray]):
    params_dict = zip(net.state_dict().keys(), parameters)
    state_dict = OrderedDict({k: torch.Tensor(v) for k, v in params_dict})
    net.load_state_dict(state_dict, strict=True)


def load_syftbox_dataset(id: int) -> tuple[torch.utils.data.TensorDataset, torch.utils.data.TensorDataset]:
    from syft_flwr.utils import get_syftbox_dataset_path
    import os
    
    os.environ["DATA_DIR"] = f"/Users/nutorbit/workspace/syftbox-flwr/notebooks/marketing/flwr/datasites/do_{id+1}@gmail.com/private/datasets"  # TODO: this is a hack to get the dataset path
    
    data_dir = get_syftbox_dataset_path()
    
    train_path = data_dir / f"marketing-data-{id}"
    test_path = data_dir / "marketing-data-test"

    X_train = np.load(train_path / f"X_train.npy")
    y_train = np.load(train_path / f"y_train.npy")
    
    X_test = np.load(test_path / f"X_test.npy")
    y_test = np.load(test_path / f"y_test.npy")
    
    # tensor_train_dataset = torch.utils.data.TensorDataset(torch.FloatTensor(X_train), torch.LongTensor(y_train))
    # tensor_test_dataset = torch.utils.data.TensorDataset(torch.FloatTensor(X_test), torch.LongTensor(y_test))

    return (
        torch.FloatTensor(X_train),
        torch.LongTensor(y_train),
        torch.FloatTensor(X_test),
        torch.LongTensor(y_test),
    )

    