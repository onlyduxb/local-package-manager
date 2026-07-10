# ruff: noqa

import click
from pathlib import Path
from .crud import (
    RegistryHandler,
    checkout_version,
    pin_package,
    unpin_package,
    resolve_package_path,
    install_into_venv,
    uninstall_from_venv,
    get_package_version,
    is_installed_in_venv,
    push_package,
    update_package
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
    project_path = Path.cwd()

    venv = resolve_venv(project_path)
    if venv is None:
        click.secho("No venv found in current directory.", fg="red")
        return

    if is_installed_in_venv(package_name, venv):
        click.secho(f"{package_name} is already installed.", fg="yellow")
        return

    package_path = resolve_package_path(package_name, editable, registry_handler)
    if package_path is None:
        return

    if version is not None:
        if not checkout_version(package_path, version):
            return
    else:
        version = get_package_version(package_path)

    if not install_into_venv(venv, package_path, editable):
        return

    if version:
        pin_package(project_path, package_name, str(version))

    click.secho(f"{package_name}=={version} installed.", fg="green")


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("package_name")
@click.option("--remove-files", is_flag=True, default=False)
def uninstall(package_name: str, remove_files: bool):
    if not click.confirm(f"Uninstall {package_name}?"):
        return

    project_path = Path.cwd()
    venv = resolve_venv(project_path)
    if venv is None:
        click.secho("No venv found in current directory.", fg="red")
        return

    if not uninstall_from_venv(package_name, venv):
        return

    unpin_package(project_path, package_name)

    if remove_files:
        registry_handler = RegistryHandler()
        package = registry_handler.get_package(package_name)
        if package:
            import shutil

            shutil.rmtree(package["path"])
            registry_handler.remove_package(package_name)
            click.secho(f"Deleted {package['path']}", fg="green")

    click.secho(f"{package_name} uninstalled.", fg="green")


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("package_name", required=False)
@click.option("--all", "update_all", is_flag=True, default=False, help="Update all registered packages.")
@click.option("--install-here", is_flag=True, default=False)
def update(package_name: str, install_here: bool, update_all: bool):
    registry_handler = RegistryHandler()
    project_path = Path.cwd()
    if update_all:
        for package in registry_handler.get_all().keys():
            update_package(package, install_here, registry_handler, project_path)
        click.secho("Updated all packages!", fg="green")
        return
    if package_name:
        update_package(package_name, install_here, registry_handler, project_path)
        return
    click.secho("No package name provided and not updating all packages!", fg="red")

@click.group()
def publish():
    pass


@publish.command()
def gitea():
    # if not run_pre_publish_checks():
    #     return
    # crud.push_to_gitea(Path.cwd(), DEFAULT_CONFIG_DIR)
    raise NotImplementedError()


@publish.command()
def github():
    # if not run_pre_publish_checks():
    #     return
    # crud.push_to_github(Path.cwd(), DEFAULT_CONFIG_DIR)
    raise NotImplementedError()


@publish.command()
def pypi():
    # if not run_pre_publish_checks():
    #     return
    # crud.build_package(Path.cwd())
    # crud.upload_to_pypi(Path.cwd(), DEFAULT_CONFIG_DIR)
    raise NotImplementedError()


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--project",
    "project_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.cwd(),
)
def push(project_path: Path):
    push_package(project_path)
