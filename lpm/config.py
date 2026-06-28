# ruff: noqa

import json
from pathlib import Path
from typing import Any
import click
from platformdirs import user_config_dir

DEFAULT_CONFIG_DIR = Path(user_config_dir("lpm"))


def save_config(
    config: dict[str, Any], tokens: dict[str, Any], base_dir: Path = DEFAULT_CONFIG_DIR
):
    if not base_dir.exists():
        base_dir.mkdir(parents=True, exist_ok=True)

    config_file = base_dir / "config.json"
    with open(config_file, "w") as file:
        json.dump(config, file, indent=4)

    env_file = base_dir / ".env"
    save_env(tokens, env_file)

    click.echo(f"Successfully wrote the configuration files to {base_dir}")


def save_env(tokens: dict[str, str], env_path: Path):
    env_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [f"{key}={value}" for key, value in tokens.items() if value]
    env_path.write_text("\n".join(lines))

    env_path.chmod(0o600)


def load_env(base_dir: Path = DEFAULT_CONFIG_DIR) -> dict[str, str]:
    env_file = base_dir / ".env"
    if not env_file.exists():
        return {}
    lines = env_file.read_text().splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line)
