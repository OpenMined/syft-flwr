from pathlib import Path
from typing import Annotated

import typer

from syft_flwr.run import syftbox_run_flwr_client

CLIENT_PANEL = "Client Options"


FLOWER_PROJECT_DIR_OPTS = typer.Option(
    "-d",
    "--flower-project-dir",
    rich_help_panel=CLIENT_PANEL,
    help="Path to the Flower project directory",
)


app = typer.Typer(
    name="syft-flwr client",
    pretty_exceptions_enable=False,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback(invoke_without_command=True)
def client(
    flower_project_dir: Annotated[Path, FLOWER_PROJECT_DIR_OPTS],
) -> None:
    """Run in client mode."""
    syftbox_run_flwr_client(Path(flower_project_dir) / "pyproject.toml")


if __name__ == "__main__":
    app()
