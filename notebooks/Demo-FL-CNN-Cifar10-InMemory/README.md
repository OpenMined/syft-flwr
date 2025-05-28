### Running the Demo

This directory contains a set of notebooks demonstrating an in-memory simulation of a Federated Learning (FL) workflow using Flower and Syft stack. The demo simulates a scenario with one Data Scientist (DS) and two Data Owners (DO1, DO2). To run this demo, follow these steps in order:

0.  **Prerequisites**:
    *   Clone the `syft_flwr` project: `git clone https://github.com/OpenMined/syft-flwr/`
    *   Navigate into the project directory: `cd syft-flwr`
    *   Assuming `uv` is installed, create and activate a virtual environment: `uv venv && source .venv/bin/activate`
    *   Install dependencies: `uv sync`
    *   You are now ready to run the notebooks using Jupyter Lab or a similar tool. Follow the instructions within each notebook and switch notebooks when indicated.

1.  **Start Data Owner Nodes:**
    *   Run the **`do1.ipynb`** notebook. This starts the datasite for DO1, loads their data, and waits for the DS.
    *   Run the **`do2.ipynb`** notebook similarly for DO2.

2.  **Data Scientist: Connect and Submit Job:**
    *   Run the **`ds.ipynb`** notebook.
    *   Connect to the DOs' datasites, inspect mock data, prepare the Flower strategy, and **Submit** the training job code to both DOs.

3.  **Data Owners: Inspect and Approve Job:**
    *   Return to the **`do1.ipynb`** and **`do2.ipynb`** notebooks.
    *   Run the remaining cells to **Inspect** the submitted job and code. If approved, **Start** the Flower client node, which will wait to connect to the DS's Flower server.

4.  **Data Scientist: Start FL Server & Training:**
    *   Return to the **`ds.ipynb`** notebook.
    *   Run the cells to **Start** the Flower server. The server will coordinate training across the two connected Data Owners and perform federated averaging.

5.  **Evaluation:**
    *   Once training is complete, the final cells in **`ds.ipynb`** evaluate the aggregated model.

### Notes on Execution

*   The simulated datasites will be created in the `flwr` directory within your project.
*   Logs for the simulation run will be stored in `quickstart-pytorch/simulation_logs`.
