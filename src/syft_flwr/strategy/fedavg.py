from pathlib import Path

from loguru import logger
from safetensors.numpy import save_file

from flwr.common import parameters_to_ndarrays
from flwr.server.strategy import FedAvg


class FedAvgWithModelSaving(FedAvg):
    """This is a custom strategy that behaves exactly like
    FedAvg with the difference of storing of the state of
    the global model to disk after each round.
    Ref: https://discuss.flower.ai/t/how-do-i-save-the-global-model-after-training/71/2
    """

    def __init__(self, save_path: str, *args, **kwargs):
        self.save_path = Path(save_path)
        self.save_path.mkdir(exist_ok=True, parents=True)
        super().__init__(*args, **kwargs)

    def _save_global_model(self, server_round: int, parameters):
        """A new method to save the parameters to disk."""
        ndarrays = parameters_to_ndarrays(parameters)
        tensor_dict = {f"layer_{i}": array for i, array in enumerate(ndarrays)}
        filename = self.save_path / f"parameters_round_{server_round}.safetensors"
        if not self.save_path.exists():
            logger.error(
                f"Save directory {self.save_path} does NOT exist! Maybe it's deleted or moved."
            )
        else:
            save_file(tensor_dict, str(filename))
            logger.info(f"Checkpoint saved to: {filename}")

    def evaluate(self, server_round: int, parameters):
        """Evaluate model parameters using an evaluation function."""
        self._save_global_model(server_round, parameters)
        return super().evaluate(server_round, parameters)
