# ruff: noqa

import click
import requests
import subprocess
from pathlib import Path
from .config import save_config, DEFAULT_CONFIG_DIR

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
    save_config(config, tokens, Path( str(DEFAULT_CONFIG_DIR)))

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

def collect_packages(venv_path: Path) -> dict[str, str]:
    python = get_venv_python(venv_path)
    result = subprocess.run(
        [str(python), "-m", "pip", "freeze"],
        capture_output=True, text=True, check=True,
    )
    packages: dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            packages[name] = version
        elif "@" in line:
            name = line.split("@")[0].strip().lstrip("-e ").strip()
            packages[name] = "local"
    return packages

def get_venv_python(venv_path: Path) -> Path:
    if (venv_path / "Scripts" / "python.exe").exists():
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"

def resolve_venv(project_dir: Path = Path.cwd()) -> Path | None:
    venv = find_venv(project_dir)
    if venv:
        return venv

    if (project_dir / "pyproject.toml").exists():
        venv = find_poetry_venv(project_dir)
        if venv:
            return venv

    return None


VENV_CANDIDATES = [".venv", "venv", "env", ".env_py"]

def is_venv(path: Path) -> bool:
    return (path / "pyvenv.cfg").exists()

def find_venv(project_dir: Path) -> Path | None:
    for name in VENV_CANDIDATES:
        candidate = project_dir / name
        if is_venv(candidate):
            return candidate
    return None

def find_poetry_venv(project_dir: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["poetry", "env", "info", "--path"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        path = Path(result.stdout.strip())
        return path if path.exists() else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def check_dependencies(dependency_list: dict[str, str], codes: bool) -> bool:
    private_dependencies: list[tuple[str, str]] = []
    for name, version in dependency_list.items():
        click.secho(f"Checking {name} ({version}).", fg="yellow")
        package = requests.get(f"https://pypi.org/project/{name}/{version}")
        if package.status_code != 200:
            if codes:
                click.secho(f"Pypi responded {package.status_code}", fg="red")
            private_dependencies.append((name, version))
    if len(private_dependencies) == 0:
        click.secho(f"There are no private dependencies.", fg="green")
        return True
    click.secho(f"Private dependencies found.", fg="red")
    return False



# - The gitea host (default is localhost:3000).
# - Your gitea username.
# - Gitea token.
# - Github username (optional as lpm can be used to publish to github).
# - Github token (skipped if the username is left blank).
# - Pypi username (optional as lpm can be used to publish to pypi).
# - Pypi token (skipped if the username is left blank).
# - Storage location
# - Default python interpreter.
