# Federated Learning for Diabetes Prediction

A federated learning application for diabetes prediction using the Pima Indians Diabetes Database. This project leverages [Flower](https://flower.ai/) for federated learning orchestration and [SyftBox](https://github.com/OpenMined/syftbox) for privacy-preserving distributed computation.

## Overview

This application trains a neural network to predict diabetes onset using federated learning, enabling multiple data owners to collaboratively train a model without sharing their raw data. The project supports both local simulation mode and distributed deployment across multiple SyftBox nodes.

## Features

- **Federated Learning**: Decentralized training across multiple clients using Flower framework
- **Privacy-Preserving**: Data remains with data owners; only model updates are shared
- **Imbalanced Data Handling**: Uses SMOTE (Synthetic Minority Over-sampling Technique) for class balancing
- **Advanced Neural Architecture**: Deep neural network with batch normalization and dropout
- **Dual Execution Modes**:
  - Local simulation for development and testing
  - Distributed mode via SyftBox for real-world deployment
- **Model Persistence**: Automatic model checkpointing after each round

## Architecture

### Model

The neural network architecture consists of:
- **Input Layer**: 6 features (after preprocessing)
- **Hidden Layers**:
  - Layer 1: 32 units with BatchNorm, LeakyReLU, and Dropout (0.2)
  - Layer 2: 24 units with BatchNorm, LeakyReLU, and Dropout (0.25)
  - Layer 3: 16 units with BatchNorm and LeakyReLU
- **Output Layer**: Single unit with Sigmoid activation (binary classification)

See `fl_diabetes_prediction/task.py:31` for implementation details.

### Dataset

**Source**: [Pima Indians Diabetes Database](https://huggingface.co/datasets/khoaguin/pima-indians-diabetes-database)

**Features**:
- Pregnancies
- Glucose
- Blood Pressure
- BMI (Body Mass Index)
- Diabetes Pedigree Function
- Age

**Preprocessing**:
- Removed `SkinThickness` and `Insulin` features
- Imputed zero values with mean/median
- Applied SMOTE for class balancing
- Standardized features using StandardScaler

**Partitioning**: IID (Independent and Identically Distributed) partitioning across clients

## Installation

### Requirements

- Python >= 3.12
- UV package manager (recommended) or pip

### Setup

1. Clone the repository:
```bash
cd fl-diabetes-prediction
```

2. Install dependencies using UV:
```bash
uv sync
```

Or using pip:
```bash
pip install -e .
```

## Usage

### Local Simulation

Run federated learning locally with simulated clients:

```bash
flwr run .
```

This will:
- Simulate 2 supernodes (clients) locally
- Run 2 federated learning rounds
- Save model weights to `./weights/` directory

**Configuration**: Edit `pyproject.toml` to adjust:
- `num-server-rounds`: Number of training rounds
- `num-supernodes`: Number of simulated clients

### Distributed Mode (SyftBox)

For distributed deployment across real SyftBox nodes:

1. **Setup SyftBox nodes**:
   - Configure data owner (DO) nodes
   - Configure data scientist (DS) aggregator node

2. **Configure endpoints** in `pyproject.toml`:
```toml
[tool.syft_flwr]
datasites = [
    "do1@openmined.org",
    "do2@openmined.org",
]
aggregator = "ds@openmined.org"
```

3. **Run the application**:
   - On each DO node: `python main.py` (runs as client)
   - On DS node: `python main.py` (runs as server)

The system automatically detects whether to run as client or server based on the email configuration.

### Jupyter Notebooks

Example notebooks are available in:
- `local/`: Local execution examples
  - `do1.ipynb`, `do2.ipynb`: Data owner notebooks
  - `ds.ipynb`: Data scientist aggregator notebook
- `distributed/`: Distributed execution examples

## Project Structure

```
fl-diabetes-prediction/
├── fl_diabetes_prediction/
│   ├── __init__.py
│   ├── task.py           # Model, data loading, training logic
│   ├── client_app.py     # Flower client implementation
│   ├── server_app.py     # Flower server implementation
│   └── main.py           # SyftBox entry point
├── pyproject.toml        # Project configuration
├── weights/              # Saved model checkpoints
└── README.md
```

## Configuration

### Flower App Configuration (`pyproject.toml`)

```toml
[tool.flwr.app.config]
num-server-rounds = 2        # Number of FL rounds
partition-id = 0             # Client partition ID
num-partitions = 1           # Total number of partitions

[tool.flwr.federations.local-simulation.options]
num-supernodes = 2          # Number of simulated clients
```

### Strategy

Uses `FedAvgWithModelSaving` strategy (see `server_app.py:55`):
- **Algorithm**: Federated Averaging (FedAvg)
- **Model Saving**: Automatic checkpointing after each round
- **Metrics Aggregation**: Weighted average by dataset size
- **Fault Tolerance**: Configurable via `pyproject.toml` (default: 50% failure tolerance)
  - Min Available Clients: 1 (can start with 1 out of 2 clients)
  - Min Fit Clients: 1 (needs 1 client minimum per training round)
  - Min Evaluate Clients: 1 (needs 1 client minimum per evaluation)

## Fault Tolerance

The system is designed to handle client failures during federated learning:

### Configuration

**Default Setup (50% failure tolerance)**:
- **Total Clients**: 2
- **Minimum Required**: 1
- **Failure Tolerance**: Can continue with 1 out of 2 clients (50% failure)

### How It Works

1. **min-available-clients**: Minimum clients needed to start a federation (default: 1)
2. **min-fit-clients**: Minimum clients needed per training round (default: 1)
3. **min-evaluate-clients**: Minimum clients needed per evaluation round (default: 1)
4. **fraction-fit**: Fraction of available clients to **sample** per round (default: 0.5)
   - With 2 clients: samples 1 client per round (50% × 2 = 1)
   - Prevents waiting for failed clients that were already sampled
5. **fraction-evaluate**: Fraction of available clients to sample for evaluation (default: 0.5)

### Customizing Fault Tolerance

Edit `pyproject.toml` to adjust fault tolerance:

```toml
[tool.flwr.app.config]
min-available-clients = 1   # Start with at least 1 client
min-fit-clients = 1          # Train with at least 1 client
min-evaluate-clients = 1     # Evaluate with at least 1 client
fraction-fit = 0.5           # Sample 50% of clients per round
fraction-evaluate = 0.5      # Sample 50% of clients for evaluation

[tool.flwr.federations.local-simulation.options]
num-supernodes = 2  # Total number of clients
```

**Examples for 50% failure tolerance**:
- **2 clients, fraction=0.5**: Samples 1 client/round (current default)
- **4 clients, fraction=0.5**: Samples 2 clients/round (more robust)
- **10 clients, fraction=0.5**: Samples 5 clients/round (production scale)

**Important**: Using `fraction-fit < 1.0` ensures the server doesn't get stuck waiting for failed clients that were already sampled in a round.

### Testing Fault Tolerance

To test client failure scenarios locally:

1. Start with `num-supernodes = 2` in `pyproject.toml`
2. Run `flwr run .`
3. The system will continue even if 1 client fails or disconnects

## Training Details

- **Optimizer**: Adam (lr=0.001, weight_decay=0.0005)
- **Loss Function**: Binary Cross-Entropy (BCELoss)
- **Batch Size**: 10 (training), full dataset (testing)
- **Local Epochs**: 1 per round (configurable)
- **Device Support**: CUDA, MPS (Apple Silicon), XPU, or CPU

## Development

### Running Tests

```bash
# Add test commands here
```

### Adding New Features

1. Model modifications: Edit `fl_diabetes_prediction/task.py`
2. Client behavior: Edit `fl_diabetes_prediction/client_app.py`
3. Server strategy: Edit `fl_diabetes_prediction/server_app.py`

## License

Apache-2.0

## Publisher

OpenMined

## Dependencies

Key dependencies:
- `flwr-datasets>=0.5.0` - Federated dataset utilities
- `torch>=2.8.0` - Deep learning framework
- `scikit-learn==1.6.1` - Machine learning utilities
- `imblearn` - Imbalanced data handling (SMOTE)
- `syft_flwr==0.4.0` - SyftBox integration
- `loguru` - Logging
- `pandas` - Data manipulation

## Troubleshooting

### Common Issues

1. **CUDA/GPU Issues**: The code automatically falls back to CPU if GPU is unavailable
2. **SMOTE k_neighbors Error**: Handled automatically by adjusting k_neighbors based on minority class count
3. **Model Loading**: Ensure `weights/` directory exists for model checkpointing

### Logs

The application uses `loguru` for logging. Check console output for detailed execution information.

## Contributing

Contributions are welcome! Please ensure:
- Code follows existing style conventions
- Tests pass (when available)
- Documentation is updated

## Resources

- [Flower Documentation](https://flower.ai/docs/)
- [SyftBox Repository](https://github.com/OpenMined/syftbox)
- [Pima Indians Diabetes Database](https://huggingface.co/datasets/khoaguin/pima-indians-diabetes-database)
- [OpenMined](https://www.openmined.org/)

## Contact

For questions or issues, please open an issue in the repository.
