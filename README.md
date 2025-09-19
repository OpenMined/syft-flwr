# syft_flwr

`syft_flwr` is an open source framework that facilitate federated learning (FL) projects using [Flower](https://github.com/adap/flower) over the [SyftBox](https://github.com/OpenMined/syftbox) protocol

![FL Training Process](https://github.com/OpenMined/syft-flwr/raw/main/notebooks/fl-diabetes-prediction/images/fltraining.gif)

## Example Usages
Please look at the `notebooks/` folder for example use cases:
-  [FL diabetes prediction](notebooks/fl-diabetes-prediction/README.md) shows how to train a federated model over distributed machines for multiple rounds
-  [Federated analytics](notebooks/federated-analytics-diabetes/README.md) shows how to query statistics from private datasets from distributed machines and then aggregate them
-  [FedRAG (Federated RAG)](notebooks/fedrag/README.md) demonstrates privacy-preserving question answering using Retrieval Augmented Generation across distributed document sources with remote data science workflow

## Development
### Releasing
See [RELEASE.md](RELEASE.md) for the complete release process.