# ruff: noqa

from platformdirs import user_data_dir
from pathlib import Path
from pydantic import BaseModel, ValidationError
from typing import Dict, Any
import json
import os
import click

DEFAULT_REGISTRY_PATH = Path(user_data_dir("lpm")) / "registry.json"
DEFAULT_LOCK_PATH = Path(os.getcwd()) / "lpm.lock"

type PackageDict = dict[str, dict[str, Any]]


class PackageInfo(BaseModel):
    gitea_url: str
    version: str


class RegistryPackageInfo(PackageInfo):
    path: str


class LockPackageInfo(PackageInfo):
    editable: bool


class PackageSchema[T: PackageInfo](BaseModel):
    package: Dict[str, T]


class RegistryPackageSchema(PackageSchema[RegistryPackageInfo]): ...


class LockPackageSchema(PackageSchema[LockPackageInfo]): ...


def load_json(path: Path) -> PackageDict:
    with open(path, "r") as fp:
        registry = json.load(fp)
    return registry


def save_json(
    data: PackageDict,
    path: Path,
):
    with open(path, "w") as fp:
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


def register_package(
    package_info: dict[str, dict[str, Any]], registry_path: Path = DEFAULT_REGISTRY_PATH
):
    validated_info = validate_package_structure(package_info, RegistryPackageSchema)
    if validated_info is None:
        return

    if os.path.exists(registry_path):
        registry = load_json(registry_path)
        for package_name in package_info.keys():
            registry[package_name] = package_info[package_name]
        save_json(registry, registry_path)
    else:
        click.secho(f"Registry does not exist", fg="yellow")
        save_json(package_info, registry_path)
        click.secho(f"Created registry at {registry_path}")
    click.secho(f"Wrote package to file at {registry_path}", fg="green")


def register_dependency(
    dependency_info: dict[str, dict[str, Any]], lock_path: Path = DEFAULT_LOCK_PATH
):
    validated_info = validate_package_structure(dependency_info, LockPackageSchema)
    if validated_info is None:
        return

    if os.path.exists(lock_path):
        dependencies = load_json(lock_path)
        for package_name in dependency_info.keys():
            dependencies[package_name] = dependency_info[package_name]
        save_json(dependencies, lock_path)
    else:
        click.secho(f"Lock file does not exist", fg="yellow")
        save_json(dependency_info, lock_path)
        click.secho(f"Created lock at {lock_path}")
    click.secho(f"Wrote package to file at {lock_path}", fg="green")


def get_registry(
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> PackageDict:
    try:
        return load_json(registry_path)
    except:
        return {}


def get_dependencies(lock_path: Path = DEFAULT_LOCK_PATH) -> PackageDict:
    try:
        return load_json(lock_path)
    except:
        return {}


def remove_package(package_name: str, registry_path: Path = DEFAULT_REGISTRY_PATH):
    try:
        data = load_json(registry_path)
        data.pop(package_name)
        save_json(data, registry_path)
    except:
        click.secho(f"Package not found in registry ({registry_path})", fg="red")


def remove_dependency(dependency_name: str, lock_path: Path = DEFAULT_LOCK_PATH):
    try:
        data = load_json(lock_path)
        data.pop(dependency_name)
        save_json(data, lock_path)
    except:
        click.secho(f"Package not found in registry ({lock_path})", fg="red")


# register_dependency(
#     {
#         "package_name2": {
#             "gitea_url": "url",
#             "version": "0.0.0.0",
#             "editable": False,
#         }
#     }
# )

# register_package(
#     {"package_name2": {"gitea_url": "url", "version": "0.0.0.0", "path": "shush"}}
# )

# register_package(
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
