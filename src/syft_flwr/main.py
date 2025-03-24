from pathlib import Path

import typer
from rich import print as rprint
from typing_extensions import Annotated

from syft_flwr import __version__
from syft_flwr.utils import _copy_main_py, _update_pyproject_toml

app = typer.Typer(
    name="syft_flwr",
    help=typer.style(
        "Welcome to the command line interface for syft_flwr",
        fg=typer.colors.BRIGHT_YELLOW,
        bold=True,
    ),
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command(rich_help_panel="General Options")
def version() -> None:
    """Print syft-flwr version"""
    print(f"Welcome to syft_flwr version {__version__}")


@app.command(rich_help_panel="Setup Commands")
def bootstrap(
    path: Annotated[str, typer.Argument(help="Path to the flwr project to bootstrap")],
    aggregator: Annotated[str, typer.Option(help="Aggregator")] = "a@openmined.org",
    datasites: Annotated[list[str], typer.Option(help="List of datasites")] = [
        "b@openmined.org",
        "c@openmined.org",
    ],
) -> None:
    """Bootstrap a new syft-flwr project from the flwr project at the given path"""
    flwr_project_dir = Path(path).expanduser().resolve()

    if not flwr_project_dir.exists():
        rprint(f"[red]The flower project '{flwr_project_dir}' does not exist[/red]")
        raise typer.Exit(code=1)

    if not (flwr_project_dir / "pyproject.toml").exists():
        rprint(
            f"[red]There is no `pyproject.toml` in the flower project '{flwr_project_dir}'[/red]"
        )
        raise typer.Exit(code=1)

    rprint(f"[green]Bootstrapping syft-flwr project from '{flwr_project_dir}'[/green]")

    try:
        _copy_main_py(flwr_project_dir)
        _update_pyproject_toml(flwr_project_dir, aggregator, datasites)
    except Exception as e:
        # remove the main.py file
        (flwr_project_dir / "main.py").unlink()
        rprint(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
