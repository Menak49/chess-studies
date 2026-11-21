"""Secrets from a `.env` file at the repository root, never from the code.

A minimal reader rather than a dependency: `KEY=value` lines, `#` comments,
optional quotes. A variable already set in the environment wins over the file,
so a token can still be passed for one run without editing it.
"""

from __future__ import annotations

import os
from pathlib import Path

from chesslab.settings import REPO_ROOT

DOTENV_PATH = REPO_ROOT / ".env"


def read_dotenv(path: Path | None = None) -> dict[str, str]:
    path = DOTENV_PATH if path is None else path
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def get_secret(name: str, path: Path | None = None) -> str:
    """The environment's value of `name`, else the `.env` file's, else ''."""
    return os.environ.get(name, "").strip() or read_dotenv(path).get(name, "").strip()
