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


def load() -> dict:
    ensure_data_dir()
    with CONFIG_PATH.open("rb") as f:
        cfg = tomllib.load(f)
    paths = cfg.setdefault("paths", {})
    db = paths.get("db") or str(DATA_DIR / "marrow.db")
    backup = paths.get("backup_dir") or str(DATA_DIR / "backup")
    paths["db"] = db
    paths["backup_dir"] = backup
    Path(backup).mkdir(parents=True, exist_ok=True)
    return cfg


def db_path() -> str:
    return load()["paths"]["db"]
