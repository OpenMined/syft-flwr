# Vertical Federated Learning Tutorial with `syft_flwr`

This tutorial demonstrates Vertical Federated Learning (VFL) using `syft-flwr` and SyftBox, where multiple organizations can train a shared AI model while keeping their sensitive data on their own servers.

## Scenario

A Portuguese bank wants to predict which customers will subscribe to term deposits. The data is naturally distributed across organizations:

* **Bank**: Customer demographics and financial data
* **Marketing Agency**: Campaign interaction data
* **Server**: Coordinates training and owns target outcomes

Using VFL, these parties collaborate to build a powerful prediction model without ever sharing their raw data.


## Dataset

Bank Marketing Campaign Dataset - 41,188 phone marketing interactions from Portuguese bank campaigns.

Download: [Kaggle Dataset](https://www.kaggle.com/datasets/volodymyrgavrysh/bank-marketing-campaigns-dataset/)


## Quick Start


### Prerequisites

```bash
# Python 3.8+
pip install -r requirements.txt

# Install SyftBox
curl -LsSf https://syftbox.openmined.org/install.sh | sh
```

### Setup

Clone the repository

```bash
git clone https://github.com/OpenMined/syft-flwr.git
cd syft-flwr/notebooks/vfl-bank-marketing
```

### Running the VFL Workflow

1. Download the dataset from Kaggle
2. Run the notebook for the Bank `do_1.ipynb`
3. Run the notebook for the Marketing Agency `do_2.ipynb`
4. Run the notebook for the Server `ds.ipynb`


## References

- https://syftbox.net
- https://www.kaggle.com/datasets/volodymyrgavrysh/bank-marketing-campaigns-dataset/
- https://github.com/OpenMined/syft-flwr
