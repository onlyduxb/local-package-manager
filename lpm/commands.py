# ruff: noqa

import click
from pathlib import Path
from typing import Any
import shutil
from .crud import (
    DEFAULT_PACKAGES_PATH,
    DependencyHandler,
    RegistryHandler,
    get_gitea_auth_url,
    get_gitea_public_url,
    get_package_version,
    clone_from_gitea,
    pip_install,
    pip_install_editable,
)
from .config import save_config, DEFAULT_CONFIG_DIR, Config
from .helpers import resolve_venv, collect_packages, check_dependencies


@click.command()
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


@click.command()
@click.option(
    "--project",
    "project_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.cwd(),
    help="Path to the project. Defaults to current directory.",
)
@click.option("--codes", help="Output the status codes from pypi.", is_flag=True)
def check(project_path: Path, codes: bool):
    venv_path = resolve_venv(project_path)
    if venv_path is None:
        click.echo(f"No venv found in {project_path}")
        return
    packages = collect_packages(venv_path)
    check_dependencies(packages, codes)


@click.command()
@click.argument("package_name")
@click.option("--editable", "editable", default=False, is_flag=True)
def install(package_name: str, editable: bool):
    registry_handler = RegistryHandler()
    dependency_handler = DependencyHandler()
    if dependency_handler.get_package(package_name) is None:
        package = registry_handler.get_package(package_name)
        if package is None:
            gitea_url = get_gitea_auth_url(package_name)
            package_path = clone_from_gitea(gitea_url, DEFAULT_PACKAGES_PATH / package_name)
            if package_path is None:
                click.secho("Unable to resolve package path.", fg="red")
                return
            package_version = get_package_version(package_path)
            register_info: dict[str, dict[str, str]] = {
                package_name: {
                    "gitea_url": get_gitea_public_url(package_name),
                    "version": str(package_version),
                    "path": str(package_path),
                }
            }
            dependency_info: dict[str, dict[str, Any]] = {
                package_name: {
                    "gitea_url": get_gitea_public_url(package_name),
                    "version": str(package_version),
                    "editable": editable
                }
            }
            registry_handler.register(register_info)
            dependency_handler.register(dependency_info)
        else:
            click.secho("Found package in register.", fg="green")
            package_path = Path(package["path"])
        venv = resolve_venv(Path.cwd())
        if venv is None:
            click.secho("Venv could not be resolved.", fg="red")
        else:
            if editable:
                pip_install_editable(venv, package_path)
            else:
                pip_install(venv, package_path)
    else:
        click.secho("Package already installed.", fg="red")

@click.command()
@click.argument("package_name")
def uninstall(package_name: str):
    registry_handler = RegistryHandler()
    dependency_handler = DependencyHandler()
    if dependency_handler.get_package(package_name) is not None:
        dependency_handler.remove_package(package_name)
        click.secho("Removed package from dependencies.", fg="green")
    else:
        click.secho("Could not find package in dependencies", fg="red")
    if registry_handler.get_package(package_name) is not None:
        registry_handler.remove_package(package_name)
        click.secho("Removed package from registry.", fg="green")
    else:
        click.secho("Could not find package in registry", fg="red")
    if Path.exists(DEFAULT_PACKAGES_PATH/package_name):
        shutil.rmtree(DEFAULT_PACKAGES_PATH/package_name)
        click.secho("Removed package from packages.", fg="green")
    else:
        click.secho("Could not find package from packages.", fg="red")