# Diabetes Prediction with `syft_flwr`

Diabetes prediction using [syft_flwr](https://github.com/OpenMined/syft-flwr)

Dataset: https://www.kaggle.com/datasets/uciml/pima-indians-diabetes-database/

## Workflow
1. For the data owner's workflow (uploading dataset, monitor and approve jobs), please take a look at `do.ipynb` notebook
2. For the data scientist's workflow (prepare code, observe mock datasets on the data owner's datasites, submit jobs), please look into the `ds.ipynb` notebook. Optionally, you can look at the `local_training.ipynb` to see the DS's process of processing data and training the neural network locally

## References
- https://github.com/elarsiad/diabetes-prediction-keras
- https://syftbox.openmined.org
- https://syftboxdev.openmined.org
- https://www.kaggle.com/datasets/uciml/pima-indians-diabetes-database/
- https://github.com/OpenMined/syftbox
- https://github.com/OpenMined/syft-flwr
- https://github.com/OpenMined/rds
- https://github.com/adap/flower/tree/main/examples/fl-tabular
