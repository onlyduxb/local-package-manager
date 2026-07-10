# ruff: noqa
from pathlib import Path
from pydantic import BaseModel, ValidationError
from .helpers import get_venv_python
from .config import load_config, DEFAULT_CONFIG_DIR
import subprocess
import requests
from platformdirs import user_config_dir, user_data_dir
from .helpers import resolve_venv
from typing import Dict, Any
import tomllib
import json
import click
import re

DEFAULT_REGISTRY_FILE = Path(user_config_dir("lpm")) / "registry.json"
DEFAULT_LOCK_FILE = Path.cwd() / "lpm.lock"
DEFAULT_PACKAGES_PATH = Path(user_data_dir("lpm")) / "packages"

type PackageDict = dict[str, dict[str, Any]]


# ── Models ────────────────────────────────────────────────────────────────────


class PackageInfo(BaseModel):
    version: str


class RegistryPackageInfo(PackageInfo):
    gitea_url: str
    path: str
    github_url: str | None = None


class PackageSchema[T: PackageInfo](BaseModel):
    package: Dict[str, T]


class RegistryPackageSchema(PackageSchema[RegistryPackageInfo]): ...


# ── JSON helpers ──────────────────────────────────────────────────────────────


def load_json(file: Path) -> PackageDict:
    try:
        if file.exists():
            with open(file, "r") as fp:
                return json.load(fp)
        else:
            file.parent.mkdir(parents=True, exist_ok=True)
            with open(file, "w") as fp:
                fp.write("{}")
    except Exception:
        click.secho(f"Could not load {file.name}.", fg="red")
    return {}


def save_json(data: PackageDict, file: Path):
    file.parent.mkdir(parents=True, exist_ok=True)
    with open(file, "w") as fp:
        json.dump(data, fp, indent=4)


def validate_package_structure[T: PackageSchema[Any]](
    package_info: PackageDict, model: type[T]
) -> None | T:
    try:
        return model.model_validate({"package": package_info})
    except ValidationError:
        click.secho(
            f"Package info ({list(package_info.keys())}) is incorrectly formatted.",
            fg="red",
        )
        return None


# ── Storage ───────────────────────────────────────────────────────────────────


class StorageHandler:
    def __init__(self, path: Path, structure_model: type[PackageSchema[Any]]) -> None:
        self.path = path
        self.structure_model = structure_model

    def register(self, package_info: PackageDict):
        validated_info = validate_package_structure(package_info, self.structure_model)
        if validated_info is None:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            registry = load_json(self.path)
            registry.update(package_info)
            save_json(registry, self.path)
        else:
            click.secho(f"{self.path.name} does not exist, creating.", fg="yellow")
            save_json(package_info, self.path)
            click.secho(f"Created {self.path.name} at {self.path}", fg="blue")
        click.secho(f"Wrote package to {self.path}", fg="green")

    def update(self, package_info: PackageDict):
        package_name = next(iter(package_info))
        if self.remove_package(package_name):
            self.register(package_info)

    def get_all(self) -> PackageDict:
        try:
            return load_json(self.path)
        except Exception:
            return {}

    def get_package(self, package_name: str) -> dict[str, Any] | None:
        data = load_json(self.path)
        return data.get(package_name)

    def remove_package(self, package_name: str) -> bool:
        try:
            data = load_json(self.path)
            if package_name not in data:
                click.secho(f"{package_name} not found in {self.path.name}", fg="red")
                return False
            data.pop(package_name)
            save_json(data, self.path)
            return True
        except Exception:
            click.secho(
                f"Failed to remove {package_name} from {self.path.name}", fg="red"
            )
            return False


class RegistryHandler(StorageHandler):
    def __init__(self, path: Path = DEFAULT_REGISTRY_FILE) -> None:
        super().__init__(path, RegistryPackageSchema)

    def set_github_url(self, package_name: str, github_url: str):
        package = self.get_package(package_name)
        if package is None:
            click.secho(f"{package_name} not found in registry.", fg="red")
            return
        package["github_url"] = github_url
        self.update({package_name: package})
        click.secho(f"Recorded GitHub URL for {package_name}", fg="green")


# ── URL helpers ───────────────────────────────────────────────────────────────


def get_gitea_auth_url(
    package_name: str, config_path: Path = DEFAULT_CONFIG_DIR
) -> str:
    config = load_config(config_path).all
    return f"http://{config['gitea_username']}:{config['gitea_token']}@{config['host']}/{config['gitea_username']}/{package_name}.git"


def get_gitea_public_url(
    package_name: str, config_path: Path = DEFAULT_CONFIG_DIR
) -> str:
    config = load_config(config_path).all
    return f"http://{config['host']}/{config['gitea_username']}/{package_name}.git"


def get_github_url(package_name: str, config_path: Path = DEFAULT_CONFIG_DIR) -> str:
    config = load_config(config_path).all
    return f"https://github.com/{config['github_username']}/{package_name}"


def get_github_clone_url(
    package_name: str, config_path: Path = DEFAULT_CONFIG_DIR
) -> str:
    config = load_config(config_path).all
    token = config["github_token"]
    username = config["github_username"]
    return f"https://{username}:{token}@github.com/{username}/{package_name}.git"


# ── Network checks ────────────────────────────────────────────────────────────


def get_status(url: str) -> int:
    try:
        return requests.get(url).status_code
    except requests.ConnectionError:
        return 503


def status_code_result(status_code: int) -> str:
    return {
        200: "OK.",
        401: "Unauthorized.",
        403: "Access not permitted.",
        404: "Could not locate the package.",
        500: "Internal server error.",
        503: "Could not connect.",
    }.get(status_code, f"Unexpected status code: {status_code}")


def check_gitea_exists(
    package_name: str, config_path: Path = DEFAULT_CONFIG_DIR
) -> bool:
    url = get_gitea_auth_url(package_name, config_path)
    return get_status(url) == 200


def check_github_exists(
    package_name: str, config_path: Path = DEFAULT_CONFIG_DIR
) -> bool:
    config = load_config(config_path).all
    url = f"https://api.github.com/repos/{config['github_username']}/{package_name}"
    headers = {"Authorization": f"Bearer {config['github_token']}"}
    try:
        return requests.get(url, headers=headers).status_code == 200
    except requests.ConnectionError:
        return False


# ── Git operations ────────────────────────────────────────────────────────────


def clone_repo(clone_url: str, dest: Path, public_url: str) -> Path | None:
    try:
        subprocess.run(
            ["git", "clone", clone_url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "remote", "set-url", "origin", public_url],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
        )
        return dest
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to clone: {e.stderr}", fg="red")
        return None


def pull_latest(package_path: Path) -> bool:
    try:
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=package_path,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=package_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to update package: {e.stderr}", fg="red")
        return False


# ── Package metadata ──────────────────────────────────────────────────────────


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


# ── Resolution ────────────────────────────────────────────────────────────────


def resolve_package_path(
    package_name: str,
    editable: bool,
    registry_handler: RegistryHandler,
    config_path: Path = DEFAULT_CONFIG_DIR,
) -> Path | None:
    package = registry_handler.get_package(package_name)
    if package is not None:
        click.secho(f"Found {package_name} in registry.", fg="green")
        return Path(package["path"])

    click.secho(f"Checking Gitea for {package_name}...", fg="blue")
    if check_gitea_exists(package_name, config_path):
        click.secho(f"Found {package_name} on Gitea, cloning...", fg="blue")
        auth_url = get_gitea_auth_url(package_name, config_path)
        public_url = get_gitea_public_url(package_name, config_path)
        dest = DEFAULT_PACKAGES_PATH / package_name
        path = clone_repo(auth_url, dest, public_url)
        if path is None:
            return None
        version = str(get_package_version(path))
        registry_handler.register(
            {
                package_name: {
                    "gitea_url": public_url,
                    "version": version,
                    "path": str(path),
                    "github_url": None,
                }
            }
        )
        return path

    click.secho(f"{package_name} not on Gitea, checking GitHub...", fg="yellow")
    if check_github_exists(package_name, config_path):
        click.secho(f"Found {package_name} on GitHub, cloning...", fg="blue")
        clone_url = get_github_clone_url(package_name, config_path)
        public_url = get_github_url(package_name, config_path)
        dest = DEFAULT_PACKAGES_PATH / package_name
        path = clone_repo(clone_url, dest, public_url)
        if path is None:
            return None
        version = str(get_package_version(path))
        registry_handler.register(
            {
                package_name: {
                    "gitea_url": "",
                    "version": version,
                    "path": str(path),
                    "github_url": public_url,
                }
            }
        )
        return path

    click.secho(f"{package_name} not found locally, on Gitea, or on GitHub.", fg="red")
    return None


# ── Venv operations ───────────────────────────────────────────────────────────


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


def install_into_venv(venv: Path, package_path: Path, editable: bool) -> bool:
    if editable:
        return pip_install_editable(venv, package_path)
    return pip_install(venv, package_path)


def uninstall_from_venv(package_name: str, venv: Path) -> bool:
    python = get_venv_python(venv)
    try:
        result = subprocess.run(
            [str(python), "-m", "pip", "uninstall", package_name, "-y"],
            check=True,
            capture_output=True,
            text=True,
        )
        if f"Skipping {package_name} as it is not installed" in result.stderr:
            click.secho(f"{package_name} was not installed in the venv.", fg="yellow")
            return False
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to uninstall {package_name}: {e.stderr}", fg="red")
        return False


def is_installed_in_venv(package_name: str, venv: Path) -> bool:
    python = get_venv_python(venv)
    result = subprocess.run(
        [str(python), "-m", "pip", "show", package_name],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


# ── Publish helpers (to be expanded) ─────────────────────────────────────────


def get_local_deps(config_path: Path = DEFAULT_CONFIG_DIR) -> list[str]:
    registry = load_json(DEFAULT_REGISTRY_FILE)
    return list(registry.keys())


def rewrite_pyproject_for_publish(
    project_path: Path,
    registry_handler: RegistryHandler,
    config_path: Path = DEFAULT_CONFIG_DIR,
) -> dict[str, str]:
    pyproject_path = project_path / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    try:
        deps: list[str] = data["project"]["dependencies"]
    except KeyError:
        try:
            deps = data["tool"]["poetry"]["dependencies"]
        except KeyError:
            return {}

    rewrites: dict[str, str] = {}
    new_deps = []

    for dep in deps:
        package_name = dep.split("==")[0].split(">=")[0].strip()
        package = registry_handler.get_package(package_name)

        if package is not None:
            github_url = package.get("github_url")
            version = package.get("version")

            if github_url:
                git_dep = f"{package_name} @ git+{github_url}.git@v{version}"
                new_deps.append(git_dep)  # type: ignore
                rewrites[package_name] = git_dep
            else:
                click.secho(
                    f"⚠ {package_name} has no GitHub URL — publish it first with `lpm publish github` from its directory.",
                    fg="yellow",
                )
                new_deps.append(dep)  # type: ignore
        else:
            new_deps.append(dep)  # type: ignore

    original_text = pyproject_path.read_text()
    return {"original": original_text, "rewrites": str(rewrites)}


def get_lock_path(project_path: Path) -> Path:
    return project_path / "lpm.lock"


def load_lock(project_path: Path) -> dict[str, str]:
    path = get_lock_path(project_path)
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        click.secho("Could not load lpm.lock.", fg="red")
        return {}


def save_lock(project_path: Path, data: dict[str, str]):
    path = get_lock_path(project_path)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def pin_package(project_path: Path, package_name: str, version: str):
    data = load_lock(project_path)
    data[package_name] = version
    save_lock(project_path, data)


def unpin_package(project_path: Path, package_name: str):
    data = load_lock(project_path)
    data.pop(package_name, None)
    save_lock(project_path, data)


def get_pinned_version(project_path: Path, package_name: str) -> str | None:
    return load_lock(project_path).get(package_name)


def get_all_pinned(project_path: Path) -> dict[str, str]:
    return load_lock(project_path)


def checkout_version(package_path: Path, version: str) -> bool:
    try:
        subprocess.run(
            ["git", "checkout", f"v{version}"],
            cwd=package_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Version v{version} not found: {e.stderr}", fg="red")
        return False


def calculate_new_version(current: str, bump_type: str) -> str:
    parts = current.split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return current


def prompt_version_bump(current_version: str) -> str:
    patch = calculate_new_version(current_version, "patch")
    minor = calculate_new_version(current_version, "minor")
    major = calculate_new_version(current_version, "major")

    click.echo(f"\nCurrent version: {current_version}")
    click.echo(f"  [1] Patch → {patch}")
    click.echo(f"  [2] Minor → {minor}")
    click.echo(f"  [3] Major → {major}")
    click.echo(f"  [4] Keep  → {current_version}")

    choice = click.prompt(
        "Choice", type=click.Choice(["1", "2", "3", "4"]), show_choices=False
    )

    return {
        "1": patch,
        "2": minor,
        "3": major,
        "4": current_version,
    }[choice]


def bump_version_in_toml(project_path: Path, new_version: str) -> bool:
    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.exists():
        click.secho("No pyproject.toml found.", fg="red")
        return False

    content = pyproject_path.read_text()
    pattern = r'(version\s*=\s*")[^"]*(")'
    if not re.search(pattern, content):
        click.secho("Could not find version field in pyproject.toml.", fg="red")
        return False

    new_content = re.sub(pattern, rf"\g<1>{new_version}\2", content, count=1)
    pyproject_path.write_text(new_content)
    click.secho(f"Version bumped to {new_version} in pyproject.toml", fg="green")
    return True


def is_clean_working_tree(project_path: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_path,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == ""


def tag_version(project_path: Path, version: str) -> bool:
    try:
        subprocess.run(
            ["git", "tag", f"v{version}"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to tag version: {e.stderr}", fg="red")
        return False


def push_to_remote(
    project_path: Path, remote: str = "origin", branch: str = "main"
) -> bool:
    try:
        subprocess.run(
            ["git", "push", remote, branch],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "push", remote, "--tags"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to push: {e.stderr}", fg="red")
        return False


def commit_version_bump(project_path: Path, version: str) -> bool:
    try:
        subprocess.run(
            ["git", "add", "pyproject.toml"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"bump version to {version}"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        click.secho(f"Failed to commit version bump: {e.stderr}", fg="red")
        return False


def push_package(project_path: Path) -> bool:
    if not is_clean_working_tree(project_path):
        click.secho(
            "Uncommitted changes detected. Commit or stash them first.", fg="red"
        )
        return False

    current_version = get_package_version(project_path)
    if current_version is None:
        return False

    new_version = prompt_version_bump(current_version)

    if new_version != current_version:
        if not bump_version_in_toml(project_path, new_version):
            return False
        if not commit_version_bump(project_path, new_version):
            return False

    if not tag_version(project_path, new_version):
        return False

    if not push_to_remote(project_path):
        return False

    registry = RegistryHandler()
    package = registry.get_package(project_path.name)
    if package:
        package["version"] = new_version
        registry.update({project_path.name: package})
        click.secho(f"Registry updated to {new_version}", fg="green")

    click.secho(f"\n{project_path.name}@{new_version} pushed successfully.", fg="green")
    return True

def update_package(package_name: str, install_here: bool, registry_handler: RegistryHandler, project_path: Path):
    package = registry_handler.get_package(package_name)
    if package is None:
        click.secho(f"{package_name} is not registered.", fg="red")
        return

    package_path = Path(package["path"])

    click.secho("Pulling latest changes...", fg="yellow")
    if not pull_latest(package_path):
        return

    version = get_package_version(package_path)
    if version is None:
        return

    registry_handler.register(
        {
            package_name: {
                "gitea_url": package["gitea_url"],
                "version": version,
                "path": str(package_path),
                "github_url": package.get("github_url"),
            }
        }
    )
    click.secho(f"{package_name} updated to {version}.", fg="green")
    if install_here:
        venv = resolve_venv(project_path)
        if venv is None:
            click.secho("No venv found in current directory.", fg="red")
            return

        if not install_into_venv(venv, package_path, False):
            return

        pin_package(project_path, package_name, str(version))
