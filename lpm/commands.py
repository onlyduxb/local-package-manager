# ruff: noqa

import click
from pathlib import Path
import shutil
from .crud import (
    DEFAULT_PACKAGES_PATH,
    RegistryHandler,
    resolve_package_path,
    install_into_venv,
    uninstall_from_venv,
    pull_latest,
    get_package_version,
    get_gitea_auth_url,
    build_package_records,
    is_installed_in_venv,
)
from .config import save_config, DEFAULT_CONFIG_DIR, Config
from .helpers import resolve_venv, collect_packages, check_dependencies

CONTEXT_SETTINGS = dict(allow_interspersed_args=True)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option("--clear", help="Clear the current configuration file.", is_flag=True)
def setup(clear: bool):
    """Get the user's information."""
    settings: dict[str, str | None] = {}
    tokens: dict[str, str | None] = {}

    if not clear:
        settings["host"] = click.prompt(
            "Enter your gitea host URL",
            default="localhost:3000",
            show_default=True,
            type=str,
        )
        settings["gitea_username"] = click.prompt(
            "Enter your gitea username", default=""
        )
        tokens["gitea_token"] = click.prompt("Enter gitea token: ", hide_input=True)

        if click.confirm("Set up GitHub publishing?", default=False, show_default=True):
            settings["github_username"] = click.prompt(
                "Enter your github username", default=""
            )
            tokens["github_token"] = click.prompt(
                "Enter github token: ", hide_input=True
            )
        else:
            settings["github_username"] = tokens["github_token"] = None

        if click.confirm("Set up PyPI publishing?", default=False, show_default=True):
            settings["pypi_username"] = click.prompt(
                "Enter your PyPI username", default=""
            )
            tokens["pypi_token"] = click.prompt("Enter PyPI token: ", hide_input=True)
        else:
            settings["pypi_username"] = tokens["pypi_token"] = None
    else:
        settings = {
            "host": "",
            "gitea_username": "",
            "github_username": None,
            "pypi_username": None,
        }
        tokens = {"gitea_token": "", "github_token": None, "pypi_token": None}

    config = Config(
        host=settings["host"],  # type: ignore
        gitea_username=settings["gitea_username"],  # type: ignore
        gitea_token=tokens["gitea_token"],  # type: ignore
        github_username=settings["github_username"],
        github_token=tokens["github_token"],
        pypi_username=settings["pypi_username"],
        pypi_token=tokens["pypi_token"],
    )

    save_config(config, Path(str(DEFAULT_CONFIG_DIR)))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--project",
    "project_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.cwd(),
    help="Path to the project. Defaults to current directory.",
)
@click.option(
    "--codes", "codes", help="Output the status codes from pypi.", is_flag=True
)
def check(codes: bool, project_path: Path):
    venv_path = resolve_venv(project_path)
    if venv_path is None:
        click.echo(f"No venv found in {project_path}")
        return
    packages = collect_packages(venv_path)
    check_dependencies(packages, codes)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("package_name")
@click.option("--editable", "editable", default=False, is_flag=True)
@click.option("--version", "version", default=None)
def install(package_name: str, editable: bool, version: str | None):
    registry_handler = RegistryHandler()

    venv = resolve_venv(Path.cwd())
    if venv is None:
        click.secho("Venv could not be resolved.", fg="red")
        return

    package_installed = is_installed_in_venv(package_name, venv)

    if package_installed:
        click.secho("Package already installed.", fg="red")
        return

    package_path = resolve_package_path(
        package_name, version, editable, registry_handler
    )
    if package_path is None:
        return

    if not install_into_venv(venv, package_path, editable, version):
        return


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("package_name")
def uninstall(package_name: str):
    registry_handler = RegistryHandler()
    if registry_handler.get_package(package_name) is not None:
        registry_handler.remove_package(package_name)
        click.secho("Removed package from registry.", fg="green")
    else:
        click.secho("Could not find package in registry", fg="yellow")
    if Path.exists(DEFAULT_PACKAGES_PATH / package_name):
        shutil.rmtree(DEFAULT_PACKAGES_PATH / package_name)
        click.secho("Removed package from packages.", fg="green")
    else:
        click.secho("Could not find package from packages.", fg="yellow")
    venv = resolve_venv(Path.cwd())
    if venv is None:
        click.secho("Venv could not be resolved.", fg="red")
        return
    if uninstall_from_venv(package_name, venv):
        click.secho("Removed package from venv.", fg="green")
    else:
        click.secho("Failed to remove package from venv.", fg="red")


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("package_name")
def update(package_name: str):
    registry_handler = RegistryHandler()

    package = registry_handler.get_package(package_name)

    if package is None:
        click.secho(f"{package_name} is not installed yet.", fg="red")
        return

    package_path = Path(package["path"])

    click.secho("Pulling latest changes...", fg="yellow")
    if not pull_latest(package_path):
        return

    version = get_package_version(package_path)
    if version is None:
        return

    gitea_url = get_gitea_auth_url(package_name)
    register_info = build_package_records(
        package_name, gitea_url, version, package_path, False
    )
    registry_handler.register(register_info)

    venv = resolve_venv(Path.cwd())
    if venv is None:
        click.secho("Venv could not be resolved.", fg="red")
        return

    if not install_into_venv(venv, package_path, False, None):
        return

    click.secho(f"{package_name} updated to {version}.", fg="green")
