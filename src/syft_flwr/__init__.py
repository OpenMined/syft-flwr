__version__ = "0.4.3"

from syft_flwr.bootstrap import bootstrap
from syft_flwr.run import run

__all__ = ["bootstrap", "run"]


# Register the mount provider for syft_rds when syft_flwr is initializedAdd commentMore actions
from syft_rds.syft_runtime.mounts import register_mount_provider

from .mounts import SyftFlwrMountProvider

# Register the mount provider
register_mount_provider("syft_flwr", SyftFlwrMountProvider())
