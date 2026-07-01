# ruff: noqa

import requests
import subprocess
import click
from pathlib import Path

VENV_CANDIDATES = [".venv", "venv", "env", ".env_py"]

def collect_packages(venv_path: Path) -> dict[str, str]:
    python = get_venv_python(venv_path)
    result = subprocess.run(
        [str(python), "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=True,
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
