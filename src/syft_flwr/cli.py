from pathlib import Path

import typer
from rich import print as rprint
from typing_extensions import Annotated, List, Tuple

app = typer.Typer(
    name="syft_flwr",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command()
def version() -> None:
    """Print syft_flwr version"""
    from syft_flwr import __version__

    print(__version__)


PROJECT_DIR_OPTS = typer.Argument(help="Path to a Flower project")
AGGREGATOR_OPTS = typer.Option(
    "-a",
    "--aggregator",
    "-s",
    "--server",
    help="Datasite email of the Flower Server",
)
DATASITES_OPTS = typer.Option(
    "-d",
    "--datasites",
    help="Datasites addresses",
)
MOCK_DATASET_PATHS_OPTS = typer.Option(
    "-m",
    "--mock-dataset-paths",
    help="Mock dataset paths",
)


def prompt_for_missing_args(
    aggregator: str, datasites: List[str]
) -> Tuple[Path, str, List[str]]:
    if not aggregator:
        aggregator = typer.prompt(
            "Enter the datasite email of the Aggregator (Flower Server)"
        )
    if not datasites:
        datasites = typer.prompt(
            "Enter a comma-separated email of datasites of the Flower Clients"
        )
        datasites = datasites.split(",")

    return aggregator, datasites


def prompt_for_missing_mock_paths(mock_dataset_paths: List[str]) -> List[str]:
    if not mock_dataset_paths:
        mock_paths = typer.prompt("Enter comma-separated paths to mock datasets")
        mock_dataset_paths = mock_paths.split(",")

    return mock_dataset_paths


@app.command()
def bootstrap(
    project_dir: Annotated[Path, PROJECT_DIR_OPTS],
    aggregator: Annotated[str, AGGREGATOR_OPTS] = None,
    datasites: Annotated[List[str], DATASITES_OPTS] = None,
) -> None:
    """Bootstrap a new syft_flwr project from a flwr project"""
    from syft_flwr.bootstrap import bootstrap

    aggregator, datasites = prompt_for_missing_args(aggregator, datasites)

    try:
        project_dir = project_dir.absolute()
        rprint(f"[cyan]Bootstrapping project at '{project_dir}'[/cyan]")
        rprint(f"[cyan]Aggregator: {aggregator}[/cyan]")
        rprint(f"[cyan]Datasites: {datasites}[/cyan]")
        bootstrap(project_dir, aggregator, datasites)
        rprint(f"[green]Bootstrapped project at '{project_dir}'[/green]")
    except Exception as e:
        rprint(f"[red]Error[/red]: {e}")
        raise typer.Exit(1)


@app.command()
def run(
    project_dir: Annotated[Path, PROJECT_DIR_OPTS],
    mock_dataset_paths: Annotated[List[str], MOCK_DATASET_PATHS_OPTS] = None,
) -> None:
    """Run a syft_flwr project in simulation mode over mock data"""
    from syft_flwr.run_simulation import run

    try:
        mock_dataset_paths: list[str] = prompt_for_missing_mock_paths(
            mock_dataset_paths
        )
        project_dir = Path(project_dir).expanduser().resolve()
        rprint(f"[cyan]Running syft_flwr project at '{project_dir}'[/cyan]")
        rprint(f"[cyan]Mock dataset paths: {mock_dataset_paths}[/cyan]")
        run(project_dir, mock_dataset_paths)
    except Exception as e:
        rprint(f"[red]Error[/red]: {e}")
        raise typer.Exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
