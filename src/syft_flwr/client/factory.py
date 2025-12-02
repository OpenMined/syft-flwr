import os
from pathlib import Path
from typing import Optional, Union

from loguru import logger

from syft_flwr.client.protocol import SyftFlwrClient
from syft_flwr.client.syft_core_client import SyftCoreClient
from syft_flwr.client.syft_p2p_client import SyftP2PClient


def _is_colab() -> bool:
    """Check if running in Google Colab environment."""
    try:
        import google.colab  # noqa: F401

        return True
    except ImportError:
        return False


def _get_colab_email() -> Optional[str]:
    """Get user email from Colab OAuth. Returns None if not in Colab or auth fails."""
    if not _is_colab():
        return None

    try:
        from google.colab import auth
        from googleapiclient.discovery import build

        auth.authenticate_user()
        oauth2 = build("oauth2", "v2")
        userinfo = oauth2.userinfo().get().execute()
        return userinfo.get("email")
    except Exception as e:
        logger.warning(f"Failed to get email from Colab OAuth: {e}")
        return None


def _get_colab_syftbox_folder(email: str) -> Path:
    """Get the default SyftBox folder path for Colab."""
    return Path("/content") / f"SyftBox_{email}"


def _syft_core_available() -> bool:
    """Check if syft_core config file exists at default location."""
    try:
        from syft_core.config import SyftClientConfig

        # Try to load default config - will raise if not found
        SyftClientConfig.load()
        return True
    except Exception:
        return False


def _load_syft_flwr_config(project_dir: Path) -> Optional[dict]:
    """Load syft_flwr config from pyproject.toml.

    Returns dict with 'aggregator' and 'datasites' keys, or None if not found.
    """
    try:
        import tomli

        pyproject_path = project_dir / "pyproject.toml"
        if not pyproject_path.exists():
            return None

        with open(pyproject_path, "rb") as f:
            config = tomli.load(f)

        return config.get("tool", {}).get("syft_flwr", {})
    except Exception as e:
        logger.debug(f"Failed to load config from pyproject.toml: {e}")
        return None


def _find_user_email_in_config(
    user_email: str, syft_flwr_config: dict
) -> Optional[str]:
    """Check if user_email is in the aggregator or datasites list.

    Returns the email if found (normalized), None otherwise.
    """
    aggregator = syft_flwr_config.get("aggregator", "")
    datasites = syft_flwr_config.get("datasites", [])

    # Check if user is the aggregator
    if user_email.lower() == aggregator.lower():
        return aggregator

    # Check if user is in datasites
    for ds in datasites:
        if user_email.lower() == ds.lower():
            return ds

    return None


def _get_fallback_email_from_config(syft_flwr_config: dict) -> Optional[str]:
    """Get a fallback email from config (aggregator preferred, then first datasite)."""
    aggregator = syft_flwr_config.get("aggregator")
    datasites = syft_flwr_config.get("datasites", [])

    if aggregator:
        return aggregator
    elif datasites:
        return datasites[0]
    return None


def create_client(
    client_type: Optional[str] = None,
    project_dir: Optional[Union[str, Path]] = None,
    email: Optional[str] = None,
    syftbox_folder: Optional[Union[str, Path]] = None,
    **kwargs,
) -> SyftFlwrClient:
    """Factory function to create the appropriate client.

    Detection order:
    1. If client_type is explicitly specified, use that
    2. If SYFTBOX_EMAIL and SYFTBOX_FOLDER env vars are set (job runner), use syft_client
    3. If syft_core config exists (local SyftBox), use syft_core
    4. If in Colab, use syft_client with auto-detected email/folder
    5. Fallback: raise error with helpful message

    Args:
        client_type: Explicit client type ("syft_core" or "syft_client")
        project_dir: Path to the FL project (used to read email from pyproject.toml)
        email: Explicit email (for syft_client mode)
        syftbox_folder: Explicit syftbox folder path (for syft_client mode)
        **kwargs: Additional arguments (e.g., filepath for syft_core config)

    Returns:
        SyftFlwrClient instance
    """
    # Convert project_dir to Path if provided
    if project_dir is not None:
        project_dir = Path(project_dir)

    # 1. Explicit client type
    if client_type == "syft_core":
        logger.info("Creating SyftCoreClient (explicit)")
        return SyftCoreClient.load(kwargs.get("filepath"))
    elif client_type == "syft_client":
        # Need email and folder for syft_client
        _email = email or os.getenv("SYFTBOX_EMAIL")
        _folder = syftbox_folder or os.getenv("SYFTBOX_FOLDER")

        if not _email or not _folder:
            raise ValueError(
                "syft_client requires email and syftbox_folder. "
                "Either pass them explicitly or set SYFTBOX_EMAIL and SYFTBOX_FOLDER env vars."
            )

        logger.info(f"Creating SyftP2PClient (explicit) for {_email}")
        return SyftP2PClient(email=_email, syftbox_folder=Path(_folder))

    # 2. Check env vars (set by syft_client job runner)
    env_email = os.getenv("SYFTBOX_EMAIL")
    env_folder = os.getenv("SYFTBOX_FOLDER")
    if env_email and env_folder:
        logger.info(f"Creating SyftP2PClient from env vars for {env_email}")
        return SyftP2PClient(email=env_email, syftbox_folder=Path(env_folder))

    # 3. Check if syft_core config exists (local SyftBox installation)
    if _syft_core_available():
        logger.info("Creating SyftCoreClient (auto-detected from config)")
        return SyftCoreClient.load(kwargs.get("filepath"))

    # 4. Check if in Colab environment
    if _is_colab():
        logger.info("Detected Colab environment, using syft_client (P2P) mode")

        # Load config from pyproject.toml if project_dir provided
        syft_flwr_config = None
        if project_dir:
            syft_flwr_config = _load_syft_flwr_config(project_dir)
            if syft_flwr_config:
                logger.debug(f"Loaded syft_flwr config: {syft_flwr_config}")

        # Try to determine the user's email
        _email = email  # 1. Explicit parameter takes priority

        if not _email:
            # 2. Try Colab OAuth to get the actual user's email
            logger.info("Attempting to get email from Colab OAuth...")
            oauth_email = _get_colab_email()

            if oauth_email and syft_flwr_config:
                # Verify this email is in the config (as aggregator or datasite)
                verified_email = _find_user_email_in_config(
                    oauth_email, syft_flwr_config
                )
                if verified_email:
                    _email = verified_email
                    logger.info(
                        f"OAuth email {oauth_email} found in config as: {_email}"
                    )
                else:
                    logger.warning(
                        f"OAuth email {oauth_email} not found in pyproject.toml config. "
                        f"Expected aggregator={syft_flwr_config.get('aggregator')} "
                        f"or datasites={syft_flwr_config.get('datasites')}"
                    )
                    # Still use it, user might know what they're doing
                    _email = oauth_email
            elif oauth_email:
                _email = oauth_email
                logger.info(f"Using OAuth email: {_email}")

        if not _email and syft_flwr_config:
            # 3. Fallback: use aggregator or first datasite from config
            _email = _get_fallback_email_from_config(syft_flwr_config)
            if _email:
                logger.warning(
                    f"Could not get OAuth email, falling back to config email: {_email}"
                )

        if not _email:
            raise ValueError(
                "Could not determine email in Colab. Please either:\n"
                "1. Pass email parameter: create_client(email='you@example.com')\n"
                "2. Pass project_dir with pyproject.toml containing aggregator/datasites\n"
                "3. Ensure Colab OAuth authentication works"
            )

        # Get syftbox folder
        _folder = syftbox_folder or _get_colab_syftbox_folder(_email)
        logger.info(f"Creating SyftP2PClient for {_email} at {_folder}")
        return SyftP2PClient(email=_email, syftbox_folder=Path(_folder))

    # 5. Fallback - cannot auto-detect
    raise RuntimeError(
        "Could not auto-detect client type. Please either:\n"
        "1. Run with SyftBox installed (syft_core config at default location)\n"
        "2. Set SYFTBOX_EMAIL and SYFTBOX_FOLDER environment variables\n"
        "3. Run in Google Colab\n"
        "4. Explicitly pass client_type='syft_core' or client_type='syft_client'"
    )
