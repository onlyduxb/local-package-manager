# ruff: noqa
from pathlib import Path
from pydantic import BaseModel, ValidationError
from .helpers import get_venv_python
from .config import load_config, DEFAULT_CONFIG_DIR
import subprocess
import requests
from platformdirs import user_config_dir, user_data_dir
from typing import Dict, Any
import tomllib
import json
import os
import click

DEFAULT_REGISTRY_FILE = Path(user_config_dir("lpm")) / "registry.json"
DEFAULT_PACKAGES_PATH = Path(user_data_dir("lpm")) / "packages"
DEFAULT_DEPENDENCY_FILE = Path(os.getcwd()) / "lpm.lock"
type PackageDict = dict[str, dict[str, Any]]


def save_json(
    data: PackageDict,
    file: Path,
):
    with open(file, "w") as fp:
        json.dump(data, fp, indent=4)


def validate_package_structure[T: PackageSchema[Any]](
    package_info: PackageDict, model: type[T]
) -> None | T:
    try:
        return model.model_validate({"package": package_info}, extra="forbid")
    except ValidationError:
        click.secho(
            f"Package info ({[package_name for package_name in package_info.keys()]}) is incorrectly formatted.",
            fg="red",
        )
        return None


class PackageInfo(BaseModel):
    gitea_url: str
    version: str


class RegistryPackageInfo(PackageInfo):
    path: str


class DependencyPackageInfo(PackageInfo):
    editable: bool


class PackageSchema[T: PackageInfo](BaseModel):
    package: Dict[str, T]


class RegistryPackageSchema(PackageSchema[RegistryPackageInfo]): ...


class DependencyPackageSchema(PackageSchema[DependencyPackageInfo]): ...


class StorageHandler:
    def __init__(self, path: Path, structure_model: type[PackageSchema[Any]]) -> None:
        self.path = path
        self.structure_model = structure_model

    def register(self, package_info: PackageDict):
        validated_info = validate_package_structure(package_info, self.structure_model)
        if validated_info is None:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.path.exists(self.path):
            registry = load_json(self.path)
            for package_name in package_info.keys():
                registry[package_name] = package_info[package_name]
            save_json(registry, self.path)
        else:
            click.secho(f"{self.path.name} does not exist", fg="yellow")
            save_json(package_info, self.path)
            click.secho(f"Created {self.path.name} at {self.path}", fg="blue")
        click.secho(f"Wrote package to file at {self.path}", fg="green")

    def update(self, package_info: PackageDict):
        package_name = next(iter(package_info))
        if self.remove_package(package_name):
            self.register(package_info)

    def get_all(self) -> PackageDict:
        try:
            return load_json(self.path)
        except:
            return {}

    def get_package(self, package_name: str):
        return load_json(self.path).get(package_name)

    def remove_package(self, package_name: str):
        try:
            data = load_json(self.path)
            data.pop(package_name)
            save_json(data, self.path)
            return True
        except:
            click.secho(f"Package not found in registry ({self.path})", fg="red")
        return False


class RegistryHandler(StorageHandler):
    def __init__(self, path: Path = DEFAULT_REGISTRY_FILE) -> None:
        super().__init__(path, RegistryPackageSchema)


class DependencyHandler(StorageHandler):
    def __init__(self, path: Path = DEFAULT_DEPENDENCY_FILE) -> None:
        super().__init__(path, DependencyPackageSchema)


def load_json(file: Path) -> PackageDict:
    try:
        with open(file, "r") as fp:
            registry = json.load(fp)
        return registry
    except:
        click.secho(
            f"Could not load {file.name}.",
            fg="red",
        )
    return {}


def pip_install(venv_path: Path, wheel_path: Path) -> bool:
    python = get_venv_python(venv_path)
    try:
        subprocess.run(
            [str(python), "-m", "pip", "install", str(wheel_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        click.secho(f"Installed {wheel_path.name} (static)", fg="green")
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to install {wheel_path.name}: {e.stderr}", fg="red")
        return False


def pip_install_editable(venv_path: Path, source_path: Path) -> bool:
    python = get_venv_python(venv_path)
    try:
        subprocess.run(
            [str(python), "-m", "pip", "install", "-e", str(source_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        click.secho(f"Installed {source_path.name} (editable)", fg="green")
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to install {source_path.name}: {e.stderr}", fg="red")
        return False


def get_gitea_auth_url(package_name: str, path: Path = DEFAULT_CONFIG_DIR):
    config = load_config(path).all
    return f"http://{config['gitea_username']}:{config['gitea_token']}@{config['host']}/{config['gitea_username']}/{package_name}.git"


def get_gitea_public_url(package_name: str, path: Path = DEFAULT_CONFIG_DIR):
    config = load_config(path).all
    return f"http://{config['host']}/{config['gitea_username']}/{package_name}.git"


def check_package_exists(package_name: str):
    return requests.get(get_gitea_auth_url(package_name)).status_code


def get_status(url: str):
    return requests.get(url).status_code


def status_code_result(status_code: int):
    status_messages = {
        401: "Unauthorized.",
        403: "Access not permitted.",
        404: "Could not locate the package.",
        500: "Internal server error.",
    }
    return status_messages[status_code]


def clone_from_gitea(gitea_url: str, package_path: Path) -> Path | None:
    try:
        subprocess.run(
            ["git", "clone", gitea_url, str(package_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return package_path
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to clone package: {e.stderr}", fg="red")
    return None


def pull_latest(package_path: Path) -> bool:
    try:
        subprocess.run(
            ["git", "pull"],
            cwd=package_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to update package: {e.stderr}", fg="red")
        return False


def get_package_version(package_path: Path) -> str | None:
    pyproject = package_path / "pyproject.toml"
    if not pyproject.exists():
        click.secho(f"No pyproject.toml found in {package_path}", fg="red")
        return None
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    try:
        return data["project"]["version"]
    except KeyError:
        try:
            return data["tool"]["poetry"]["version"]
        except KeyError:
            click.secho(f"No version found in {pyproject}", fg="red")
            return None


def build_package_records(
    package_name: str, gitea_url: str, version: str, path: Path, editable: bool
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    register_info = {
        package_name: {
            "gitea_url": gitea_url,
            "version": version,
            "path": str(path),
        }
    }
    dependency_info: dict[str, dict[str, Any]] = {
        package_name: {
            "gitea_url": gitea_url,
            "version": version,
            "editable": editable,
        }
    }
    return register_info, dependency_info


def resolve_package_path(
    package_name: str,
    version: str | None,
    editable: bool,
    registry_handler: RegistryHandler,
    dependency_handler: DependencyHandler,
) -> Path | None:
    package = registry_handler.get_package(package_name)

    if package is not None:
        package_path = Path(package["path"])

        if editable:
            click.secho("Found package in register.", fg="green")
            return package_path

        if find_wheel(package_path, version) is not None:
            click.secho("Found package in register.", fg="green")
            return package_path

        click.secho("Wheel not found locally, pulling latest...", fg="yellow")
        if pull_latest(package_path) and find_wheel(package_path, version) is not None:
            return package_path

        label = f"{package_name}=={version}" if version else package_name
        click.secho(f"Could not find {label} in repository.", fg="red")
        return None

    return fetch_and_register_package(
        package_name, editable, registry_handler, dependency_handler
    )


def find_wheel(package_path: Path, version: str | None) -> Path | None:
    dist_dir = package_path / "dist"
    if not dist_dir.exists():
        return None

    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        return None

    if version is None:
        return wheels[-1]

    for wheel in wheels:
        parts = wheel.stem.split("-")
        if len(parts) >= 2 and parts[1] == version:
            return wheel

    return None


def fetch_and_register_package(
    package_name: str,
    editable: bool,
    registry_handler: RegistryHandler,
    dependency_handler: DependencyHandler,
) -> Path | None:
    gitea_url = get_gitea_auth_url(package_name)
    status_code = get_status(gitea_url)
    if status_code != 200:
        click.secho(status_code_result(status_code), fg="red")
        return None

    package_path = clone_from_gitea(gitea_url, DEFAULT_PACKAGES_PATH / package_name)
    if package_path is None:
        click.secho("Unable to resolve package path.", fg="red")
        return None

    package_version = str(get_package_version(package_path))
    public_url = get_gitea_public_url(package_name)

    register_info, dependency_info = build_package_records(
        package_name, public_url, package_version, package_path, editable
    )
    registry_handler.register(register_info)
    dependency_handler.register(dependency_info)
    return package_path


def install_into_venv(
    venv: Path, package_path: Path, editable: bool, version: str | None
) -> bool:
    if editable:
        return pip_install_editable(venv, package_path)

    wheel_path = find_wheel(package_path, version)
    if wheel_path is None:
        label = f"{package_path.name}=={version}" if version else package_path.name
        click.secho(f"No matching wheel found for {label}", fg="red")
        return False

    return pip_install(venv, wheel_path)


def uninstall_from_venv(package_name: str, venv: Path):
    try:
        python = get_venv_python(venv)
        result = subprocess.run(
            [str(python), "-m", "pip", "uninstall", package_name, "-y"],
            check=True,
            capture_output=True,
            text=True,
        )
        
        if f"Skipping {package_name} as it is not installed" in result.stderr:
            click.secho(f"Package {package_name} was not found in the venv.", fg="yellow")
            return False
            
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to uninstall {package_name}: {e.stderr}", fg="red")
        return False