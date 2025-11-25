"""
Simple analysis script for diabetes dataset.

This script is used in integration tests to verify that:
1. syft:// URLs can be resolved to private data paths
2. Private data can be read and processed
3. Results can be returned via stdout

Usage: Submitted as a job via syft-client to data owners.
"""

import pandas as pd
import syft_client as sc

# Use syft:// URL to access private data
# The resolve_path function uses SYFTBOX_FOLDER env var set by job runner
# Structure: syft://private/syft_datasets/<dataset_name>/<filename>
data_path = "syft://private/syft_datasets/pima-indians-diabetes-database/train.csv"

try:
    resolved_path = sc.resolve_path(data_path)
    print(f"Resolved path: {resolved_path}")
except Exception as e:
    print(f"ERROR: Failed to resolve path: {e}")
    exit(1)

if not resolved_path.exists():
    print(f"ERROR: train.csv not found at {resolved_path}")
    exit(1)

# Load and print data summary
df = pd.read_csv(resolved_path)

# Print data summary
print("=" * 50)
print("DIABETES DATASET SUMMARY")
print("=" * 50)
print(f"Dataset path: {resolved_path}")
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print("Data types:")
print(df.dtypes)
print("=" * 50)
print("RESULT: SUCCESS")
