"""Tests for repo.safe_backup_db — pre-destructive-op snapshot into backup/manual/."""
from __future__ import annotations

import os
import re
import sqlite3
import time

import pytest

from marrow import config, repo


def _mkdb(path, *vals):
    conn = sqlite3.connect(str(path))
    with conn:
        conn.execute("CREATE TABLE IF NOT EXISTS t (v TEXT)")
        conn.executemany("INSERT INTO t VALUES (?)", [(v,) for v in vals])
    conn.close()


def _vals(path):
    conn = sqlite3.connect(str(path))
    try:
        return [r[0] for r in conn.execute("SELECT v FROM t ORDER BY rowid")]
    finally:
        conn.close()


def _live_wal_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    with conn:
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.execute("INSERT INTO t VALUES ('in-wal')")
    return conn


@pytest.fixture()
def db_and_manual(tmp_path, monkeypatch):
    """Minimal real db file + redirect DATA_DIR so safe_backup_db writes to tmp."""
    src = tmp_path / "marrow.db"
    _mkdb(src, "stub")

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
    _mkdb(src, "real-db-content-xyz")
    dest = repo.safe_backup_db("integrity", db_path=src)
    assert _vals(dest) == ["stub", "real-db-content-xyz"]


def test_live_wal_rows_land_in_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    src = tmp_path / "live.db"
    live = _live_wal_db(src)
    try:
        dest = repo.safe_backup_db("wal", db_path=src)
    finally:
        live.close()
    assert _vals(dest) == ["in-wal"]
    assert not dest.with_name(dest.name + "-wal").exists()


def test_missing_source_raises_and_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    with pytest.raises(sqlite3.Error):
        repo.safe_backup_db("gone", db_path=tmp_path / "nope.db")
    assert not (tmp_path / "nope.db").exists()


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
    live = _live_wal_db(src)
    try:
        out = purge._backup(str(src), "purge")
    finally:
        live.close()
    assert out.startswith(str(tmp_path / "bk" / "manual" / "marrow-backup-purge-"))
    assert _vals(out) == ["in-wal"]


def test_drift_backup_default_under_backup_root():
    from marrow.paths import _read_paths_section, _DEFAULT_CONFIG
    assert _read_paths_section(_DEFAULT_CONFIG)["drift_backup_dir"] == "~/.config/marrow/backup/drift"
