# ruff: noqa
from pathlib import Path
from pydantic import BaseModel, ValidationError
from .helpers import get_venv_python
from .config import load_config, DEFAULT_CONFIG_DIR
import subprocess
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
            click.secho(f"JSON file does not exist", fg="yellow")
            save_json(package_info, self.path)
            click.secho(f"Created JSON file at {self.path}", fg="blue")
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
            f"Could not load JSON file.",
            fg="red",
        )
    return {}


def pip_install_editable(venv_path: Path, local_path: Path) -> bool:
    python = get_venv_python(venv_path)

    try:
        subprocess.run(
            [str(python), "-m", "pip", "install", "-e", str(local_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        click.secho(f"Installed {local_path.name} (editable)", fg="green")
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to install {local_path.name}: {e.stderr}", fg="red")
        return False


def pip_install(venv_path: Path, local_path: Path) -> bool:
    python = get_venv_python(venv_path)

    try:
        subprocess.run(
            [str(python), "-m", "pip", "install", str(local_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        click.secho(f"Installed {local_path.name} (static)", fg="green")
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to install {local_path.name}: {e.stderr}", fg="red")
        return False


def get_gitea_auth_url(package_name: str, path: Path = DEFAULT_CONFIG_DIR):
    config = load_config(path).all
    return f"http://{config['gitea_username']}:{config['gitea_token']}@{config['host']}/{config['gitea_username']}/{package_name}.git"


def get_gitea_public_url(package_name: str, path: Path = DEFAULT_CONFIG_DIR):
    config = load_config(path).all
    return f"http://{config['host']}/{config['gitea_username']}/{package_name}.git"


def clone_from_gitea(
    gitea_url: str,
    package_path: Path,
) -> Path | None:
    try:
        subprocess.run(
            ["git", "clone", gitea_url, str(package_path)],
            check=True,
            capture_output=True,
            text=True,
        )

        subprocess.run(
            ["git", "remote", "set-url", "origin", gitea_url],
            cwd=package_path,
            check=True,
            capture_output=True,
            text=True,
        )

        return package_path
    except:
        click.secho(f"Failed to clone package.", fg="red")
    return None


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


# dependency_handler = DependencyHandler()
# registry_handler = RegistryHandler()

# dependency_handler.register(
#     {
#         "package_name": {
#             "gitea_url": "url",
#             "version": "0.0.0.0",
#             "editable": False,
#         }
#     }
# )

# registry_handler.update(
#     {"package_name2": {"gitea_url": "url", "version": "0.0.0.5", "path": "shush"}}
# )

# registry_handler.register(
#     {
#         "bad_package": {
#             "gitea_url": "url",
#             "version": "0.0.0.0",
#             "path": "shush",
#             "foul": "rotten",
#         }
#     }
# )

# {"package_name": {
#     "path": "foo/baz",
#     "gitea_url": "url",
#     "version": "0.0.0.0"
# }}
