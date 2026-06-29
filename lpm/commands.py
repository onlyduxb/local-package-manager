# ruff: noqa

import click
from pathlib import Path
from .config import save_config, DEFAULT_CONFIG_DIR
from .dependency_check import resolve_venv, collect_packages, check_dependencies

@click.command()
@click.option("--clear", help="Clear the current configuration file.", is_flag=True)
def setup(clear: bool):
    """Get the user's information."""
    config: dict[str, None | str] = {}
    tokens: dict[str, None | str] = {}
    if not clear:
        config["host"] = click.prompt(
            "Enter your gitea host URL",
            default="http://localhost:3000",
            show_default=True,
        )
        config["gitea_username"] = click.prompt("Enter your gitea username", default="")
        tokens["gitea_token"] = click.prompt("Enter gitea token: ", hide_input=True)
        if click.confirm("Set up GitHub publishing?", default=False, show_default=True):
            config["github_username"] = click.prompt(
                "Enter your github username", default=""
            )
            tokens["github_token"] = click.prompt(
                "Enter github token: ", hide_input=True
            )
        else:
            config["github_username"] = tokens["github_token"] = None
        if click.confirm("Set up PyPI publishing?", default=False, show_default=True):
            config["pypi_username"] = click.prompt(
                "Enter your PyPI username", default=""
            )
            tokens["pypi_token"] = click.prompt("Enter PyPI token: ", hide_input=True)
        else:
            config["pypi_username"] = tokens["pypi_token"] = None
    save_config(config, tokens, Path(str(DEFAULT_CONFIG_DIR)))

@click.command()
@click.option(
    "--project", "project_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.cwd(),
    help="Path to the project. Defaults to current directory."
)
@click.option("--codes", help="Output the status codes from pypi.", is_flag=True)
def check(project_path: Path, codes: bool):
    venv_path = resolve_venv(project_path)
    if venv_path is None:
        click.echo(f"No venv found in {project_path}")
        return
    packages = collect_packages(venv_path)
    check_dependencies(packages, codes)