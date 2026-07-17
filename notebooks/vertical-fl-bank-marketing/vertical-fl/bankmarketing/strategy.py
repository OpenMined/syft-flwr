import torch
import torch.nn as nn
from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays
from sklearn.metrics import roc_auc_score
from torch import optim

from syft_flwr.strategy import FedAvgWithModelSaving

from .server import ServerModel


class AggregateCustomMetricStrategy(FedAvgWithModelSaving):
    def __init__(
        self,
        labels,
        save_path,
        *,
        client_embedding_sizes=None,  # List of embedding sizes per client
        total_embedding_size=None,  # Total embedding size (alternative to client_embedding_sizes)
        fraction_fit=1.0,
        fraction_evaluate=1.0,
        min_fit_clients=2,
        min_evaluate_clients=2,
        min_available_clients=2,
        evaluate_fn=None,
        on_fit_config_fn=None,
        on_evaluate_config_fn=None,
        accept_failures=False,  # CRITICAL: For VFL, all clients must participate
        initial_parameters=None,
        fit_metrics_aggregation_fn=None,
        evaluate_metrics_aggregation_fn=None,
    ) -> None:
        super().__init__(
            save_path=save_path,
            fraction_fit=fraction_fit,
            fraction_evaluate=fraction_evaluate,
            min_fit_clients=min_fit_clients,
            min_evaluate_clients=min_evaluate_clients,
            min_available_clients=min_available_clients,
            evaluate_fn=evaluate_fn,
            on_fit_config_fn=on_fit_config_fn,
            on_evaluate_config_fn=on_evaluate_config_fn,
            accept_failures=accept_failures,
            initial_parameters=initial_parameters,
            fit_metrics_aggregation_fn=fit_metrics_aggregation_fn,
            evaluate_metrics_aggregation_fn=evaluate_metrics_aggregation_fn,
        )

        # Calculate total embedding size for the server model
        if client_embedding_sizes is not None:
            self.client_embedding_sizes = client_embedding_sizes
            self.total_embedding_size = sum(client_embedding_sizes)
        elif total_embedding_size is not None:
            self.total_embedding_size = total_embedding_size
            # Default to equal split among clients if individual sizes not specified
            self.client_embedding_sizes = [
                total_embedding_size // min_fit_clients
            ] * min_fit_clients
        else:
            # Default fallback for backward compatibility (2 clients with 2D embeddings each)
            self.client_embedding_sizes = [2, 2]
            self.total_embedding_size = 4

        self.model = ServerModel(self.total_embedding_size)
        self.initial_parameters = ndarrays_to_parameters(
            [val.cpu().numpy() for _, val in self.model.state_dict().items()]
        )
        self.optimizer = optim.SGD(self.model.parameters(), lr=0.001)
        self.criterion = nn.BCEWithLogitsLoss()
        self.label = torch.tensor(labels).float().unsqueeze(1)

    def aggregate_fit(
        self,
        rnd,
        results,
        failures,
    ):
        # Do not aggregate if there are failures and failures are not accepted
        if not self.accept_failures and failures:
            return None, {}

        # Convert results
        embedding_results = [
            torch.from_numpy(parameters_to_ndarrays(fit_res.parameters)[0])
            for _, fit_res in results
        ]

        embeddings_aggregated = torch.cat(embedding_results, dim=1)
        embedding_server = embeddings_aggregated.detach().requires_grad_()
        output = self.model(embedding_server)
        loss = self.criterion(output, self.label[: output.shape[0]])
        loss.backward()

        self.optimizer.step()
        self.optimizer.zero_grad()

        grads = embedding_server.grad.split(self.client_embedding_sizes, dim=1)
        np_grads = [grad.numpy() for grad in grads]
        parameters_aggregated = ndarrays_to_parameters(np_grads)

        # evaluation
        with torch.no_grad():
            output = self.model(embedding_server)
            prob = torch.sigmoid(output)

            # Check if both classes are present before calculating AUC
            batch_labels = self.label[: output.shape[0]].cpu().numpy()
            auc = roc_auc_score(batch_labels, prob)

        metrics_aggregated = {"accuracy": auc}

        return parameters_aggregated, metrics_aggregated

    def aggregate_evaluate(
        self,
        rnd,
        results,
        failures,
    ):
        """
        In VFL, evaluation is typically done on the server using test data.
        For now, we'll skip round-by-round evaluation and just rely on
        the training metrics from aggregate_fit.
        """
        return None, {}
