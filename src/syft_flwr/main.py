import typer

from syft_flwr import __version__
from syft_flwr.bootstrap import bootstrap

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
    """Print syft_flwr version"""
    print(f"Welcome to syft_flwr version {__version__}")


app.command()(bootstrap)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
