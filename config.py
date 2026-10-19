"""Small local/environment configuration helpers; never log credential values."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_local_env(path=None):
    """Load literal KEY=value settings without executing shell expressions.

    Deployed environment variables take precedence. This intentionally supports
    only simple values, not expansion, shell commands, or multiline secrets.
    """
    target = Path(path) if path else ROOT / ".env"
    if not target.is_file():
        return
    allowed = ("GEMINI_", "VENDENCE_")
    for raw in target.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key.startswith(allowed) or not key.replace("_", "").isalnum():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            os.environ.setdefault(key, value)


def setting(name, secrets=None, default=""):
    value = os.environ.get(name)
    if value:
        return value
    if secrets is not None:
        try:
            return str(secrets.get(name, default))
        except (FileNotFoundError, KeyError):
            pass
    return default


def public_configuration_errors():
    """Public mode must fail closed before any vendor information is loaded."""
    if os.environ.get("VENDENCE_PUBLIC", "0") != "1":
        return []
    access = os.environ.get("VENDENCE_ACCESS_PASSWORD", "")
    reviewer = os.environ.get("VENDENCE_REVIEWER_PASSWORD", "")
    errors = []
    if len(access) < 12:
        errors.append("Set a workspace access password of at least 12 characters.")
    if len(reviewer) < 12 or reviewer == access:
        errors.append("Set a different reviewer password of at least 12 characters.")
    if not os.environ.get("VENDENCE_DATA_DIR"):
        errors.append("Set the persistent data directory before public startup.")
    return errors
