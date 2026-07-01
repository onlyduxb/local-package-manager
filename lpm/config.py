# ruff: noqa

import json
from pathlib import Path
import click
from platformdirs import user_config_dir
from dotenv import load_dotenv
from os import getenv

DEFAULT_CONFIG_DIR = Path(user_config_dir("lpm"))


class Config:
    def __init__(
        self,
        host: str,
        gitea_username: str,
        gitea_token: str,
        github_username: str | None = None,
        github_token: str | None = None,
        pypi_username: str | None = None,
        pypi_token: str | None = None,
    ) -> None:
        self._host: str = host
        self._gitea_username = gitea_username
        self._gitea_token = gitea_token
        self._github_username = github_username
        self._github_token = github_token
        self._pypi_username = pypi_username
        self._pypi_token = pypi_token

    @property
    def public(self) -> dict[str, str | None]:
        return {
            "host": self._host,
            "gitea_username": self._gitea_username,
            "github_username": self._github_username,
            "pypi_username": self._pypi_username,
        }

    @property
    def secrets(self) -> dict[str, str | None]:
        return {
            "gitea_token": self._gitea_token,
            "github_token": self._github_token,
            "pypi_token": self._pypi_token,
        }

    @property
    def all(self) -> dict[str, str | None]:
        return {
            "host": self._host,
            "gitea_username": self._gitea_username,
            "github_username": self._github_username,
            "pypi_username": self._pypi_username,
            "gitea_token": self._gitea_token,
            "github_token": self._github_token,
            "pypi_token": self._pypi_token,
        }


def save_config(config: Config, base_dir: Path = DEFAULT_CONFIG_DIR):
    if not base_dir.exists():
        base_dir.mkdir(parents=True, exist_ok=True)

    save_public(config.public, base_dir)

    env_file = base_dir / ".env"
    save_secrets(config.secrets, env_file)

    click.echo(f"Successfully wrote the configuration files to {base_dir}")


def save_public(public: dict[str, str | None], base_dir: Path = DEFAULT_CONFIG_DIR):
    config_file = base_dir / "config.json"
    with open(config_file, "w") as file:
        json.dump(public, file, indent=4)


def save_secrets(secrets: dict[str, str | None], env_path: Path):
    env_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [f"{key}={value}" for key, value in secrets.items() if value]
    env_path.write_text("\n".join(lines))

    env_path.chmod(0o600)


def load_public(base_dir: Path = DEFAULT_CONFIG_DIR) -> dict[str, str | None]:
    with open(base_dir / "config.json", "r") as file:
        return json.load(file)


def load_secrets(base_dir: Path = DEFAULT_CONFIG_DIR) -> dict[str, str | None]:
    load_dotenv(base_dir / ".env")
    return {
        "gitea_token": getenv("gitea_token"),
        "github_token": getenv("github_token"),
        "pypi_token": getenv("pypi_token"),
    }


def load_config(path: Path = DEFAULT_CONFIG_DIR):
    settings = load_public(path)
    tokens = load_secrets(path)
    return Config(
        host=settings["host"],  # type: ignore
        gitea_username=settings["gitea_username"],  # type: ignore
        gitea_token=tokens["gitea_token"],  # type: ignore
        github_username=settings["github_username"],
        github_token=tokens["github_token"],
        pypi_username=settings["pypi_username"],
        pypi_token=tokens["pypi_token"],
    )
