import typer

from syft_flwr import __version__

app = typer.Typer(
    name="syft-flwr",
    help=typer.style(
        "syft-flwr CLI",
        fg=typer.colors.BRIGHT_YELLOW,
        bold=True,
    ),
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command(rich_help_panel="General Options")
def version() -> None:
    """Print version"""
    print(f"Welcome to syft_flwr version {__version__}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
