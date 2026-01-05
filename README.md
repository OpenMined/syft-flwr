# syft-flwr

**Easy, file-based, offline capable federated learning**

`syft-flwr` is an open-source framework that combines [Flower's](https://github.com/adap/flower) federated learning capabilities with file-based communication. Train machine learning models collaboratively across distributed datasets without centralizing data—with easy setup, offline capability, and no servers required.

![FL Training Process](https://github.com/OpenMined/syft-flwr/raw/main/notebooks/fl-diabetes-prediction/images/fltraining.gif)

## Key Features

- **File-Based Communication**: Train models without direct network connections—communication happens via file sync (Google Drive or [SyftBox](https://syftbox.net/))
- **Zero Infrastructure**: No servers to maintain, no complex networking setup—just notebooks and file sync
- **Offline Capable**: Asynchronous message passing enables training even with intermittent connectivity
- **Privacy by Design**: Data never leaves its source—only model updates are shared
- **Flower Integration**: Built on Flower's robust FL framework—supports FedAvg, custom strategies, and all standard Flower features

## Quick Start

The easiest way to get started is with our **Google Colab tutorial**—no local setup required:

📓 [Zero-Setup FL with Google Colab](notebooks/fl-diabetes-prediction/distributed-gdrive/README.md)

## Example Notebooks

| Example | Description | Communication |
|---------|-------------|---------------|
| [FL Diabetes (Google Drive)](notebooks/fl-diabetes-prediction/distributed-gdrive/README.md) | Train a diabetes prediction model across distributed Colab notebooks | Google Drive |
| [FL Diabetes (SyftBox)](notebooks/fl-diabetes-prediction/distributed/README.md) | Train a diabetes prediction model across distributed machines | SyftBox |
| [FL Diabetes (Local)](notebooks/fl-diabetes-prediction/local/README.md) | Local simulation for development and testing | Local |
| [Federated Analytics](notebooks/federated-analytics-diabetes/README.md) | Query statistics from private datasets and aggregate them | SyftBox |
| [FedRAG](notebooks/fedrag/README.md) | Privacy-preserving question answering with RAG | SyftBox |

## Installation

```bash
pip install syft-flwr
```

Or install from source:

```bash
pip install "git+https://github.com/OpenMined/syft-flwr.git@main"
```

## Documentation

📚 [Full Documentation](https://syft-flwr-documentation.openmined.org/)

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and guidelines.

### Releasing

See [RELEASE.md](RELEASE.md) for the complete release process.

## Community

- 💬 [Slack](https://slack.openmined.org/) - Join #support-syftbox for questions
- 🐛 [Issues](https://github.com/OpenMined/syft-flwr/issues) - Report bugs or request features
- 🌟 Star this repo to support the project!

## License

[Apache 2.0](LICENSE)
