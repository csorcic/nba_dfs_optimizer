"""Load config/settings.yaml and config/name_overrides.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


def load_settings(path: Path | None = None) -> dict:
    with open(path or CONFIG_DIR / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_name_overrides(path: Path | None = None) -> dict[str, str]:
    with open(path or CONFIG_DIR / "name_overrides.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return dict(data.get("overrides") or {})
