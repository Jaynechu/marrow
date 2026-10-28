"""Tests for repo.safe_backup_db — pre-destructive-op snapshot into backup/manual/."""
from __future__ import annotations

import os
import re
import time

import pytest

from marrow import config, repo


@pytest.fixture()
def db_and_manual(tmp_path, monkeypatch):
    """Minimal real db file + redirect DATA_DIR so safe_backup_db writes to tmp."""
    src = tmp_path / "marrow.db"
    src.write_bytes(b"SQLITE-STUB")

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "db_path", lambda: str(src))

    manual = tmp_path / "backup" / "manual"
    return src, manual


# ── filename format ───────────────────────────────────────────────────────────

def test_dest_filename_format(db_and_manual):
    src, _ = db_and_manual
    dest = repo.safe_backup_db("test-reason", db_path=src)
    assert re.fullmatch(
        r"marrow-before-test-reason-\d{8}T\d{6}Z\.db",
        dest.name,
    ), f"Unexpected filename: {dest.name}"


# ── content integrity ─────────────────────────────────────────────────────────

def test_copy_content_matches_source(db_and_manual):
    src, _ = db_and_manual
    src.write_bytes(b"real-db-content-xyz")
    dest = repo.safe_backup_db("integrity", db_path=src)
    assert dest.read_bytes() == b"real-db-content-xyz"


# ── dest lands in backup/manual/ ─────────────────────────────────────────────

def test_dest_in_correct_subdir(db_and_manual):
    src, manual = db_and_manual
    dest = repo.safe_backup_db("subdir-check", db_path=src)
    assert dest.parent == manual
    assert dest.exists()


# ── no self-prune: expiry belongs to housekeep ───────────────────────────────

def test_old_manual_files_untouched(db_and_manual):
    src, manual = db_and_manual
    manual.mkdir(parents=True, exist_ok=True)
    old_file = manual / "marrow-before-old-op-20260101T000000Z.db"
    old_file.write_bytes(b"old")
    old_mtime = time.time() - (30 * 24 * 3600)
    os.utime(old_file, (old_mtime, old_mtime))

    repo.safe_backup_db("no-prune", db_path=src)

    assert old_file.exists()


def test_purge_backup_lands_in_manual(tmp_path, monkeypatch):
    from marrow import purge
    real = config.load

    def _load():
        cfg = real()
        cfg["paths"]["backup_dir"] = str(tmp_path / "bk")
        return cfg

    monkeypatch.setattr(config, "load", _load)
    src = tmp_path / "marrow.db"
    src.write_bytes(b"x")
    out = purge._backup(str(src), "purge")
    assert out.startswith(str(tmp_path / "bk" / "manual" / "marrow-backup-purge-"))


def test_drift_backup_default_under_backup_root():
    from marrow.paths import _read_paths_section, _DEFAULT_CONFIG
    assert _read_paths_section(_DEFAULT_CONFIG)["drift_backup_dir"] == "~/.config/marrow/backup/drift"
