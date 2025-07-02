# Diabetes Prediction with `syft_flwr`

## Introduction

In this tutorial, we'll walk through a practical federated learning implementation for diabetes prediction using [syft_flwr](https://github.com/OpenMined/syft-flwr) — a framework that combines the flexibility of [Flower](https://github.com/adap/flower/) (a popular federated learning framework) with the privacy-preserving networking capabilities of [syftbox](https://www.syftbox.net/).

![overview](./images/overview.png)

Dataset: https://www.kaggle.com/datasets/uciml/pima-indians-diabetes-database/

## Set up

### Clone the project
```bash
git clone https://github.com/OpenMined/syft-flwr.git _tmp \
		&& mv _tmp/notebooks/fl-diabetes-prediction . \
		&& rm -rf _tmp && cd fl-diabetes-prediction
```

### Setup python virtual environment
Assume that you have python and the [uv](https://docs.astral.sh/uv/) package manager installed. Now let's create a virtual python environment with all dependencies installed:
```bash
uv sync
```

### Install and run `syftbox` client
Make sure you have syftbox client running in a terminal:
1. Install `syftbox`: `curl -fsSL https://syftbox.net/install.sh | sh`
2. Follow the instructions to start your `syftbox` client

When you have `syftbox` installed and run in the background, you can proceeed and run the notebooks with the installed Python environment in your favorite IDE.

### Local Setup
At the start of the notebooks, you can set the flag `LOCAL_TEST` to `True` if you want to run all the clients (2 data owners and 1 data scientist) locally to test the whole workflow, where all clients' local datasites will be saved locally under the `flwr` folder. For this, you need to follow the running the notebooks `do1.ipynb`, `do2.ipynb`, then `ds.ipynb` in order.

If running locally, you don't need your `syftbox client` running.


### Distributed setup
Set `LOCAL_TEST` to `False` and make sure you have your `syftbox` client running if you want to run the clients over the `syftbox` network.

1. For the data scientist's workflow (prepare code, observe mock datasets on the data owner's datasites, submit jobs), please look into the `ds.ipynb` notebook. Following this notebook will help you submit jobs to two datasites named `flower-test-group-1@openmined.org` and `flower-test-group-2@openmined.org` that host 2 partitions of the `pima-indians-diabetes-database`, and they will approve your job automatically.

Optionally, you can look at the `local_training.ipynb` to see the DS's process of processing data and training the neural network locally.

2. For the data owner's workflow (uploading dataset, monitor and approve jobs), please take a look at `do.ipynb` notebook. Following this notebook, you will learn how to upload your partition of the `pima-indians-diabetes-database` so others can submit jobs to you.

## References
- https://syftbox.net
- https://www.kaggle.com/datasets/uciml/pima-indians-diabetes-database/
- https://github.com/OpenMined/syftbox
- https://github.com/OpenMined/syft-flwr
- https://github.com/adap/flower/
- https://github.com/OpenMined/rds
- https://github.com/elarsiad/diabetes-prediction-keras
