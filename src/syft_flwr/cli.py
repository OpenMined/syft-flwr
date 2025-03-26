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


@app.command()
def bootstrap(
    project_dir: Annotated[Path, PROJECT_DIR_OPTS],
    aggregator: Annotated[str, AGGREGATOR_OPTS] = None,
    datasites: Annotated[List[str], DATASITES_OPTS] = None,
) -> None:
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
