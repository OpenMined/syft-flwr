import os
from pathlib import Path
from typing import Optional, Union

from loguru import logger

from syft_flwr.client.protocol import SyftFlwrClient
from syft_flwr.client.syft_core_client import SyftCoreClient
from syft_flwr.client.syft_p2p_client import SyftP2PClient
from syft_flwr.config import load_flwr_pyproject


def _load_syft_flwr_config(project_dir: Path) -> Optional[dict]:
    """Load syft_flwr config from pyproject.toml.

    Returns dict with 'transport', 'aggregator', 'datasites' keys, or None if not found.
    """
    try:
        pyproject = load_flwr_pyproject(project_dir, check_module=False)
        return pyproject.get("tool", {}).get("syft_flwr", {})
    except Exception as e:
        logger.debug(f"Failed to load config from pyproject.toml: {e}")
        return None


def _syft_core_available() -> bool:
    """Check if syft_core config file exists at default location."""
    try:
        from syft_core.config import SyftClientConfig

        # Try to load default config - will raise if not found
        SyftClientConfig.load()
        return True
    except Exception:
        return False


def _create_p2p_client(email: Optional[str]) -> SyftP2PClient:
    """Create a SyftP2PClient for P2P transport mode.

    Uses Google Drive API directly (via GDriveFileIO), no filesystem paths needed.
    Email determined from: explicit param > env var
    """
    _email = email or os.getenv("SYFTBOX_EMAIL")

    if not _email:
        raise ValueError(
            "P2P transport requires email. Please either:\n"
            "1. Pass email parameter: create_client(email='you@example.com')\n"
            "2. Set SYFTBOX_EMAIL environment variable"
        )

    logger.info(f"Creating SyftP2PClient for {_email} (using Google Drive API)")
    return SyftP2PClient(email=_email)


def create_client(
    transport: Optional[str] = None,
    project_dir: Optional[Union[str, Path]] = None,
    email: Optional[str] = None,
    **kwargs,
) -> SyftFlwrClient:
    """Factory function to create the appropriate client.

    Detection order:
    1. If transport is explicitly specified, use that
    2. If project_dir is provided, read transport from pyproject.toml
    3. If syft_core config exists (local SyftBox), use syftbox transport
    4. Fallback: raise error with helpful message

    Args:
        transport: Communication transport type:
            - "syftbox": Local SyftBox with RPC/crypto
            - "p2p": P2P sync via Google Drive API (no encryption)
        project_dir: Path to the FL project (reads transport/email from pyproject.toml)
        email: Explicit email (for P2P mode)
        **kwargs: Additional arguments (e.g., filepath for syftbox config)

    Returns:
        SyftFlwrClient instance
    """
    # Convert project_dir to Path if provided
    if project_dir is not None:
        project_dir = Path(project_dir)

    # Load config from pyproject.toml if project_dir provided
    syft_flwr_config = None
    if project_dir:
        syft_flwr_config = _load_syft_flwr_config(project_dir)
        if syft_flwr_config:
            logger.debug(f"Loaded syft_flwr config: {syft_flwr_config}")

    # Determine transport: explicit param > pyproject.toml > auto-detect
    _transport = transport
    if not _transport and syft_flwr_config:
        _transport = syft_flwr_config.get("transport")
        if _transport:
            logger.info(f"Using transport from pyproject.toml: {_transport}")

    # 1. Explicit transport specified (or from config)
    if _transport == "syftbox":
        logger.info("Creating SyftCoreClient (syftbox transport)")
        return SyftCoreClient.load(kwargs.get("filepath"))
    elif _transport == "p2p":
        logger.info("Creating SyftP2PClient (p2p transport)")
        return _create_p2p_client(email)

    # 2. Auto-detect: check if syft_core config exists (local SyftBox installation)
    if _syft_core_available():
        logger.info("Creating SyftCoreClient (auto-detected from local config)")
        return SyftCoreClient.load(kwargs.get("filepath"))

    # 3. Fallback - cannot auto-detect
    raise RuntimeError(
        "Could not determine transport type. Please either:\n"
        "1. Run syft_flwr.bootstrap() with transport='syftbox' or transport='p2p'\n"
        "2. Pass project_dir pointing to a bootstrapped project\n"
        "3. Run with SyftBox installed locally (auto-detected)\n"
        "4. Explicitly pass transport='syftbox' or transport='p2p'"
    )
