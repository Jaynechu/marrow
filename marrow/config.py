"""Paths + config load. Data lives under ~/.config/marrow/, never in the repo."""
from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

DATA_DIR = Path.home() / ".config" / "marrow"
CONFIG_PATH = DATA_DIR / "config.toml"
_DEFAULT = Path(__file__).with_name("config.default.toml")


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        shutil.copyfile(_DEFAULT, CONFIG_PATH)
    return DATA_DIR


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursive merge: overlay keys win, dict-valued keys merge in-place.
    Lists/scalars are replaced, not concatenated. Needed so a new
    config.default.toml key (e.g. [recall]) lands on existing installs
    without forcing users to hand-edit ~/.config/marrow/config.toml.
    """
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    ensure_data_dir()
    with _DEFAULT.open("rb") as f:
        cfg = tomllib.load(f)
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("rb") as f:
            user = tomllib.load(f)
        cfg = _deep_merge(cfg, user)
    paths = cfg.setdefault("paths", {})
    db = paths.get("db") or str(DATA_DIR / "marrow.db")
    backup = paths.get("backup_dir") or str(DATA_DIR / "backup")
    offsite = paths.get("offsite_backup_dir") or str(
        Path.home() / "Library" / "Mobile Documents"
        / "com~apple~CloudDocs" / "marrow-backup"
    )
    dash = paths.get("dashboard") or str(
        Path.home() / "Desktop" / "NY" / "dashboard.md"
    )
    sub = paths.get("sub_pages") or str(
        Path.home() / "Desktop" / "NY" / "sub_pages"
    )
    sub_state = paths.get("sub_pages_state") or str(DATA_DIR / "state")
    paths["db"] = db
    paths["backup_dir"] = backup
    paths["offsite_backup_dir"] = offsite
    paths["dashboard"] = dash
    paths["sub_pages"] = str(Path(sub).expanduser())
    paths["sub_pages_state"] = str(Path(sub_state).expanduser())
    cfg.setdefault("backup", {}).setdefault("keep", 14)
    Path(backup).mkdir(parents=True, exist_ok=True)
    return cfg


def dashboard_path() -> str:
    return load()["paths"]["dashboard"]


def db_path() -> str:
    return load()["paths"]["db"]


def sub_pages_path() -> str:
    return load()["paths"]["sub_pages"]


def sub_pages_state_path() -> str:
    return load()["paths"]["sub_pages_state"]
