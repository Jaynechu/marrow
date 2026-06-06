"""Tests for repo.safe_backup_db — in-session snapshot helper."""
from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

from marrow import config, repo


@pytest.fixture()
def db_and_in_session(tmp_path, monkeypatch):
    """Minimal real db file + redirect DATA_DIR so safe_backup_db writes to tmp."""
    src = tmp_path / "marrow.db"
    src.write_bytes(b"SQLITE-STUB")

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "db_path", lambda: str(src))

    in_session = tmp_path / "backup" / "in-session"
    return src, in_session


# ── filename format ───────────────────────────────────────────────────────────

def test_dest_filename_format(db_and_in_session):
    src, in_session = db_and_in_session
    dest = repo.safe_backup_db("test-reason", db_path=src)
    assert re.fullmatch(
        r"marrow-before-test-reason-\d{8}T\d{6}Z\.db",
        dest.name,
    ), f"Unexpected filename: {dest.name}"


# ── content integrity ─────────────────────────────────────────────────────────

def test_copy_content_matches_source(db_and_in_session):
    src, in_session = db_and_in_session
    src.write_bytes(b"real-db-content-xyz")
    dest = repo.safe_backup_db("integrity", db_path=src)
    assert dest.read_bytes() == b"real-db-content-xyz"


# ── dest lands in backup/in-session/ ─────────────────────────────────────────

def test_dest_in_correct_subdir(db_and_in_session):
    src, in_session = db_and_in_session
    dest = repo.safe_backup_db("subdir-check", db_path=src)
    assert dest.parent == in_session
    assert dest.exists()


# ── prune removes files older than 7 days ────────────────────────────────────

def test_prune_removes_old_in_session_files(db_and_in_session, monkeypatch):
    src, in_session = db_and_in_session
    in_session.mkdir(parents=True, exist_ok=True)

    old_file = in_session / "marrow-before-old-op-20260101T000000Z.db"
    old_file.write_bytes(b"old")
    # backdate mtime to 8 days ago
    old_mtime = time.time() - (8 * 24 * 3600)
    import os
    os.utime(old_file, (old_mtime, old_mtime))

    repo.safe_backup_db("trigger-prune", db_path=src)

    assert not old_file.exists(), "File older than 7 days should have been pruned"


# ── prune does NOT touch recent in-session files ──────────────────────────────

def test_prune_keeps_recent_in_session_files(db_and_in_session):
    src, in_session = db_and_in_session
    in_session.mkdir(parents=True, exist_ok=True)

    recent = in_session / "marrow-before-recent-20260606T000000Z.db"
    recent.write_bytes(b"recent")
    # mtime is now (default) — well within 7 days

    repo.safe_backup_db("trigger-prune", db_path=src)

    assert recent.exists(), "Recent in-session file should NOT be pruned"


# ── prune does NOT touch daily backup files ───────────────────────────────────

def test_prune_ignores_daily_backup_files(db_and_in_session):
    """marrow-YYYY-MM-DD.db files must never be removed by safe_backup_db."""
    src, in_session = db_and_in_session
    in_session.mkdir(parents=True, exist_ok=True)

    # Place a daily-format file in in-session/ (adversarial edge case).
    daily = in_session / "marrow-2026-05-30.db"
    daily.write_bytes(b"daily")
    import os, time
    old_mtime = time.time() - (30 * 24 * 3600)
    os.utime(daily, (old_mtime, old_mtime))

    repo.safe_backup_db("prune-guard", db_path=src)

    assert daily.exists(), "Daily backup file must not be pruned by safe_backup_db"
