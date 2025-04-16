import shutil
import tempfile
from pathlib import Path

from loguru import logger


def reset_db(key):
    root_path = Path(tempfile.gettempdir(), key)

    if root_path.exists():
        try:
            shutil.rmtree(root_path)
            print("Successfully Reset Flwr DB ✅")
        except Exception as e:
            logger.warning(f"Failed to reset directory {root_path}: {e}")
    else:
        print("Skipping Reset , as path does not exist")
