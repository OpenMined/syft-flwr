from pathlib import Path
from typing import Annotated

import typer

from syft_flwr.run import syftbox_run_flwr_server

SERVER_PANEL = "Server Options"


FLOWER_PROJECT_DIR_OPTS = typer.Option(
    "-d",
    "--flower-project-dir",
    rich_help_panel=SERVER_PANEL,
    help="Path to the Flower project directory",
)


app = typer.Typer(
    name="syft-flwr server",
    pretty_exceptions_enable=False,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback(invoke_without_command=True)
def server(
    flower_project_dir: Annotated[Path, FLOWER_PROJECT_DIR_OPTS],
) -> None:
    """Run in server mode."""
    syftbox_run_flwr_server(Path(flower_project_dir) / "pyproject.toml")


if __name__ == "__main__":
    app()
