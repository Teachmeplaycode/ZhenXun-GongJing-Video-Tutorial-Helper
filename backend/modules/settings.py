"""Settings from the environment, falling back to `backend/.env` (real environment variables win)."""
from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
# Logins saved from the UI (modules/accounts). A separate file, because dev.sh restarts the backend
# whenever .env changes, which would cut off answers in progress.
ACCOUNTS_FILE = ENV_FILE.with_name(".env.accounts")


def parse_assignment(line: str) -> tuple[str, str]:
    """`[export ]NAME=value` with optional quotes → (NAME, value); a bare value gives ("", value)."""
    name, sep, value = line.removeprefix("export ").partition("=")
    if not sep:
        name, value = "", name
    return name.strip(), value.strip().strip("'\"")


def read_env_file(path: Path) -> dict[str, str]:
    """Minimal .env reader: NAME=value lines, `#` comments; no variable expansion."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return {}
    pairs = (parse_assignment(line.strip()) for line in lines if "=" in line and not line.strip().startswith("#"))
    return {name: value for name, value in pairs if name}


def settings() -> dict[str, str]:
    """Read on every call so an edited .env applies to the next request.

    Precedence: .env < .env.accounts (logins from the UI) < real environment variables.
    """
    return {**read_env_file(ENV_FILE), **read_env_file(ACCOUNTS_FILE), **os.environ}
