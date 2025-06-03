"""pandas_example: A Flower / Pandas app."""

import random
import time
from collections.abc import Iterable
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from flwr.common import Context, Message, MessageType, RecordDict
from flwr.server import Grid, ServerApp
from loguru import logger
from rich import print as rprint

from fed_analytics_diabetes.client_app import (
    FEATURE_BINS,
    KEY_DIABETES_FEATURES,
)

MIN_NODES = 2

app = ServerApp()


@app.main()
def main(grid: Grid, context: Context) -> None:
    """This `ServerApp` construct a histogram from partial-histograms reported by the
    `ClientApp`s."""

    num_rounds = context.run_config["num-server-rounds"]

    fraction_sample = context.run_config["fraction-sample"]

    for server_round in range(num_rounds):
        logger.info("")  # Add newline for log readability
        logger.info(f"Starting round {server_round + 1}/{num_rounds}")

        # Loop and wait until enough nodes are available.
        all_node_ids: list[int] = []
        while len(all_node_ids) < MIN_NODES:
            all_node_ids = list(grid.get_node_ids())
            if len(all_node_ids) >= MIN_NODES:
                # Sample nodes
                num_to_sample = int(len(all_node_ids) * fraction_sample)
                node_ids = random.sample(all_node_ids, num_to_sample)
                break
            logger.info("Waiting for nodes to connect...")
            time.sleep(2)

        logger.info(f"Sampled {len(node_ids)} nodes (out of {len(all_node_ids)})")

        # Create messages
        recorddict = RecordDict()
        messages = []
        for node_id in node_ids:  # one message for each node
            message = Message(
                content=recorddict,
                message_type=MessageType.QUERY,  # target `query` method in ClientApp
                dst_node_id=node_id,
                group_id=str(server_round),
            )
            messages.append(message)

        # Send messages and wait for all results
        replies: list[Message] = grid.send_and_receive(messages)
        logger.info(f"Received {len(replies)}/{len(messages)} results")

        # Aggregate partial histograms
        aggregated_hist = aggregate_partial_histograms(replies)

        logger.info("Aggregated histogram: ")
        rprint(aggregated_hist)

        for feature_name in KEY_DIABETES_FEATURES:
            plot_feature_histogram_from_metrics_plt(
                feature_name, aggregated_hist, FEATURE_BINS
            )


def aggregate_partial_histograms(messages: Iterable[Message]):
    """Aggregate partial histograms."""
    logger.info(f"Aggregating partial histograms from {len(messages)} clients")

    aggregated_hist = {}

    for i, rep in enumerate(messages):
        if rep.has_error():
            continue

        query_results = rep.content["query_results"]
        logger.info(f"Query results from {i}th client: {query_results}")

        for k, v in query_results.items():
            if "hist_outcome" in k:
                if k in aggregated_hist:
                    aggregated_hist[k] += np.array(v)
                else:
                    aggregated_hist[k] = np.array(v)

            if "count_outcome" in k:
                if k in aggregated_hist:
                    aggregated_hist[k] += v
                else:
                    aggregated_hist[k] = v

    return aggregated_hist


def plot_feature_histogram_from_metrics_plt(
    feature_name: str, metrics_dict: dict, feature_bins_config: dict
):
    """Plots a combined histogram for a single feature using plt.bar."""
    print(f"\nPlotting histogram for: {feature_name} using plt.bar")
    sns.set_theme(style="whitegrid")  # Apply Seaborn style

    hist_outcome0 = metrics_dict.get(f"{feature_name}_hist_outcome0")
    count_outcome0 = metrics_dict.get(f"{feature_name}_count_outcome0", 0)
    hist_outcome1 = metrics_dict.get(f"{feature_name}_hist_outcome1")
    count_outcome1 = metrics_dict.get(f"{feature_name}_count_outcome1", 0)
    bin_edges = feature_bins_config.get(feature_name)

    if bin_edges is None:
        print(
            f"Error: Bin edges not defined for feature '{feature_name}'. Cannot plot."
        )
        return

    # Ensure bin_edges is a numpy array for np.diff
    if not isinstance(bin_edges, np.ndarray):
        bin_edges = np.array(bin_edges)

    bin_widths = np.diff(bin_edges)

    plt.figure(figsize=(10, 6))
    has_plotted_anything = False

    # Plot outcome 0
    if hist_outcome0 is not None and count_outcome0 > 0:
        frequencies0 = np.array(hist_outcome0)
        if len(frequencies0) == len(bin_edges) - 1:
            plt.bar(
                bin_edges[:-1],
                frequencies0,
                width=bin_widths,
                align="edge",
                alpha=0.6,
                label="No Diabetes (0)",
                color="skyblue",
            )
            has_plotted_anything = True
        else:
            print(
                f"Warning: Mismatch for {feature_name} Outcome 0. Frequencies length {len(frequencies0)}, Expected bins {len(bin_edges)-1}."
            )

    # Plot outcome 1
    if hist_outcome1 is not None and count_outcome1 > 0:
        frequencies1 = np.array(hist_outcome1)
        if len(frequencies1) == len(bin_edges) - 1:
            plt.bar(
                bin_edges[:-1],
                frequencies1,
                width=bin_widths,
                align="edge",
                alpha=0.6,
                label="Diabetes (1)",
                color="salmon",
            )
            has_plotted_anything = True
        else:
            print(
                f"Warning: Mismatch for {feature_name} Outcome 1. Frequencies length {len(frequencies1)}, Expected bins {len(bin_edges)-1}."
            )

    if not has_plotted_anything:
        print(f"Info: No valid histogram data to plot for feature '{feature_name}'.")
        plt.close()  # Close the empty figure
        return

    plt.title(f"Local Histogram: {feature_name}")
    plt.xlabel(feature_name)
    plt.ylabel("Local Frequency")
    plt.xticks(bin_edges, rotation=45, ha="right")
    plt.legend(title="Diabetes Status")
    plt.grid(axis="y", linestyle="--")
    plt.tight_layout()

    # Save plots
    save_dir = Path("./figures")
    if not save_dir.exists():
        save_dir.mkdir(parents=True, exist_ok=True)  # Using pathlib.Path.mkdir
        print(f"Created directory: {save_dir}")

    # Save the plot
    file_path = save_dir / f"{feature_name}_histogram.png"  # Using pathlib operator
    try:
        plt.savefig(file_path)
        print(f"Plot saved to {file_path}")
    except Exception as e:
        print(f"Error saving plot for {feature_name}: {e}")

    plt.show()
    plt.close()
