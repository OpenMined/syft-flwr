# Diabetes Prediction with `syft_flwr`

Diabetes prediction using [syft_flwr](https://github.com/OpenMined/syft-flwr)

Dataset: https://www.kaggle.com/datasets/uciml/pima-indians-diabetes-database/

## Prerequisite
1. Make sure you have syftbox client running: `curl -fsSL https://syftboxdev.openmined.org/install.sh | sh`
2. `syftbox init` and follow the instructions to authenticate
3. `syftbox`

## Data Owner
```bash
git clone https://github.com/khoaguin/fl-diabetes-prediction
cd fl-diabetes-prediction
uv venv
source .venv/bin/activate
uv pip install jupyter
```
Run the `do.ipynb`

## Data Scientist

```bash
git clone https://github.com/khoaguin/fl-diabetes-prediction
cd fl-diabetes-prediction
uv venv
source .venv/bin/activate
cd fl-diabetes-prediction
uv sync --active
```

Run the `ds.ipynb`

## References
- https://github.com/elarsiad/diabetes-prediction-keras
- https://syftbox.openmined.org
- https://syftboxdev.openmined.org
- https://www.kaggle.com/datasets/uciml/pima-indians-diabetes-database/
- https://github.com/OpenMined/syftbox
- https://github.com/OpenMined/syft-flwr
- https://github.com/OpenMined/rds
- https://github.com/adap/flower/tree/main/examples/fl-tabular
