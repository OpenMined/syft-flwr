from pathlib import Path
from typing import Union

import tomli_w
import typer
from rich import print as rprint

from syft_flwr.config import load_config


def _copy_main_py(flwr_project_dir: Path) -> None:
    """Copy the content below to `main.py` file to the syft-flwr project"""
    main_py_path = flwr_project_dir / "main.py"
    if main_py_path.exists():
        rprint(
            f"[red]The `main.py` file already exists in the syft-flwr project '{flwr_project_dir}'[/red]"
        )
        raise typer.Exit(code=1)
    main_py_content = """
import os
from pathlib import Path

from syft_core import Client

from syft_flwr.config import load_config
from syft_flwr.run import syftbox_run_flwr_client, syftbox_run_flwr_server

DATA_DIR = os.environ["DATA_DIR"]
OUTPUT_DIR = os.environ["OUTPUT_DIR"]


flower_project_dir = Path(__file__).parent.absolute()
client = Client.load()
config = load_config(flower_project_dir)

is_client = client.email in config["tool"]["syft_flwr"]["datasites"]
is_server = client.email in config["tool"]["syft_flwr"]["aggregator"]

if is_client:
    # run by each DO
    syftbox_run_flwr_client(flower_project_dir)
elif is_server:
    # run by the DS
    syftbox_run_flwr_server(flower_project_dir)
else:
    raise ValueError(f"{client.email} is not in config.datasites or config.aggregator")
    """
    with open(main_py_path, "w") as f:
        f.write(main_py_content)


def _update_pyproject_toml(
    flwr_project_dir: Union[str, Path], aggregator: str, datasites: list[str]
) -> None:
    """Update the `pyproject.toml` file to the syft-flwr project"""
    flwr_project_dir = Path(flwr_project_dir)
    pyproject_conf = load_config(flwr_project_dir, check_module=False)

    # TODO: remove this after we find out how to pass the right context to the clients
    pyproject_conf["tool"]["flwr"]["app"]["config"]["partition-id"] = 0
    pyproject_conf["tool"]["flwr"]["app"]["config"]["num-partitions"] = 1

    # Remove any existing syft_flwr section if exists
    if "syft_flwr" in pyproject_conf.get("tool", {}):
        del pyproject_conf["tool"]["syft_flwr"]

    with open(flwr_project_dir / "pyproject.toml", "w") as f:
        toml_str = tomli_w.dumps(pyproject_conf)
        f.write(toml_str)

    # Append the syft_flwr section at the end of the file
    with open(flwr_project_dir / "pyproject.toml", "a") as f:
        f.write("\n[tool.syft_flwr]\n")
        f.write(f"datasites = {datasites}\n")
        f.write(f'aggregator = "{aggregator}"\n')

    rprint(
        "[green]Updated pyproject.toml with syft_flwr template configuration. Please check and change according to your needs.[/green]"
    )


def bootstrap(flwr_project_dir: Path, aggregator: str, datasites: list[str]) -> None:
    """Bootstrap a new syft-flwr project from the flwr project at the given path"""
    if not flwr_project_dir.exists():
        rprint(f"[red]The flower project '{flwr_project_dir}' does not exist[/red]")
        raise ValueError(f"The flower project '{flwr_project_dir}' does not exist")

    if not (flwr_project_dir / "pyproject.toml").exists():
        rprint(
            f"[red]There is no `pyproject.toml` in the flower project '{flwr_project_dir}'[/red]"
        )
        raise ValueError(
            f"There is no `pyproject.toml` in the flower project '{flwr_project_dir}'"
        )

    rprint(f"[green]Bootstrapping syft-flwr project from '{flwr_project_dir}'[/green]")

    try:
        _copy_main_py(flwr_project_dir)
        _update_pyproject_toml(flwr_project_dir, aggregator, datasites)
    except Exception as e:
        # remove the main.py file
        (flwr_project_dir / "main.py").unlink()
        rprint(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
