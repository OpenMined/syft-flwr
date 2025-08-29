import json
import os
from pathlib import Path

import tomli
from loguru import logger
from syft_core import Client
from syft_rds.models import DockerMount, JobConfig
from syft_rds.syft_runtime.mounts import MountProvider
from typing_extensions import List


class SyftFlwrMountProvider(MountProvider):
    def _simplify_config(self, config_path: Path, simplified_config_path: Path) -> None:
        """
        Simplify the config by removing the refresh_token and setting the data_dir to /app/SyftBox
        in order to mount the config to the container.
        """
        with open(config_path, "r") as fp:
            config = json.load(fp)
            modified_config = config.copy()
            modified_config["data_dir"] = "/app/SyftBox"
            modified_config.pop("refresh_token", None)
            with open(simplified_config_path, "w") as fp:
                json.dump(modified_config, fp)

    def get_mounts(self, job_config: JobConfig) -> List[DockerMount]:
        client = Client.load()
        client_email = client.email
        flwr_app_data = client.app_data("flwr")

        config_path = client.config_path
        simplified_dir = client.config_path.parent / ".simplified_configs"
        simplified_dir.mkdir(parents=True, exist_ok=True)
        simplified_config_path = simplified_dir / f"{client_email}.config.json"
        self._simplify_config(config_path, simplified_config_path)

        # Read app name from pyproject.toml
        with open(job_config.function_folder / "pyproject.toml", "rb") as fp:
            toml_dict = tomli.load(fp)
            syft_flwr_app_name = toml_dict["tool"]["syft_flwr"]["app_name"]

        rpc_messages_source = Path(f"{flwr_app_data}/{syft_flwr_app_name}/rpc/messages")
        rpc_messages_source.mkdir(parents=True, exist_ok=True)
        os.chmod(rpc_messages_source, 0o777)

        mounts = [
            DockerMount(
                source=simplified_config_path,
                target="/app/config.json",
                mode="ro",
            ),
            DockerMount(
                source=rpc_messages_source,
                target=f"/app/SyftBox/datasites/{client_email}/app_data/flwr/{syft_flwr_app_name}/rpc/messages",
                mode="rw",
            ),
        ]

        logger.debug(f"Mounts: {mounts}")

        return mounts
