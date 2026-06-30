# ruff: noqa

from platformdirs import user_data_dir
from pathlib import Path
from pydantic import BaseModel, ValidationError
from typing import Dict, Any
import json
import os
import click

DEFAULT_REGISTRY_PATH = Path(user_data_dir("lpm")) / "registry.json"
DEFAULT_DEPENDENCY_PATH = Path(os.getcwd()) / "lpm.lock"

type PackageDict = dict[str, dict[str, Any]]


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

        if os.path.exists(self.path):
            registry = load_json(self.path)
            for package_name in package_info.keys():
                registry[package_name] = package_info[package_name]
            save_json(registry, self.path)
        else:
            click.secho(f"Registry does not exist", fg="yellow")
            save_json(package_info, self.path)
            click.secho(f"Created registry at {self.path}")
        click.secho(f"Wrote package to file at {self.path}", fg="green")

    def update(self, package_info: PackageDict):
        for package_name in package_info.keys():
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
    def __init__(self, path: Path = DEFAULT_REGISTRY_PATH) -> None:
        super().__init__(path, RegistryPackageSchema)


class DependencyHandler(StorageHandler):
    def __init__(self, path: Path = DEFAULT_DEPENDENCY_PATH) -> None:
        super().__init__(path, DependencyPackageSchema)


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
