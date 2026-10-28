"""housekeep file passes + ct table prune: old removed, fresh kept, excluded untouched."""
from __future__ import annotations

import os
import time

from _housekeep_shared import make_ctx
from marrow import storage
from marrow.housekeep import db as hdb
from marrow.housekeep import files


def _age(p, days):
    t = time.time() - days * 86400
    os.utime(p, (t, t))


def _file(p, days, data="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data)
    _age(p, days)
    return p


def test_manual_backups_expire_by_age(tmp_path):
    ctx = make_ctx(tmp_path)
    m = ctx.backup_root / "manual"
    old = _file(m / "marrow-backup-purge-old.db", 31, "abc")
    fresh = _file(m / "marrow-before-x.db", 5)
    r = files.manual_backups(ctx)
    assert (r["items"], r["bytes_freed"]) == (1, 3)
    assert not old.exists() and fresh.exists()


def test_drift_dirs_use_newest_inner_mtime(tmp_path):
    ctx = make_ctx(tmp_path)
    stale = ctx.drift_dir / "aaa"
    _file(stale / "f.md", 40)
    _age(stale, 40)
    live = ctx.drift_dir / "bbb"
    _file(live / "old.md", 40)
    _file(live / "new.md", 1)
    _age(live, 40)
    r = files.drift_backups(ctx)
    assert r["items"] == 1
    assert not stale.exists() and live.exists()


def test_state_expiry_only_listed_dirs(tmp_path):
    ctx = make_ctx(tmp_path, hk={"state_dirs": ["tl_seen"],
                                 "snapshot_dirs": ["schedule-snapshots"]})
    old = _file(ctx.state_dir / "tl_seen" / "sid-old", 31)
    fresh = _file(ctx.state_dir / "tl_seen" / "sid-new", 2)
    unlisted = _file(ctx.state_dir / "shells" / "cli.json", 300)
    snap = _file(ctx.data_dir / "schedule-snapshots" / "x.content", 31)
    r = files.state_expiry(ctx)
    assert r["items"] == 2
    assert not old.exists() and not snap.exists()
    assert fresh.exists() and unlisted.exists()


def test_stray_bak_moves_to_manual(tmp_path):
    ctx = make_ctx(tmp_path)
    bak = _file(ctx.data_dir / "config.toml.bak-20260101", 90)
    keep = _file(ctx.data_dir / "config.toml", 90)
    r = files.stray_bak(ctx)
    assert r["items"] == 1
    assert not bak.exists() and keep.exists()
    assert (ctx.backup_root / "manual" / "config.toml.bak-20260101").exists()


def test_stray_bak_never_overwrites(tmp_path):
    ctx = make_ctx(tmp_path)
    m = ctx.backup_root / "manual"
    _file(ctx.data_dir / "a.bak", 1, "new")
    _file(m / "a.bak", 1, "old")
    _file(m / "a.bak.1", 1, "older")
    r = files.stray_bak(ctx)
    assert r["items"] == 1 and r["error"] is None
    assert not (ctx.data_dir / "a.bak").exists()
    assert (m / "a.bak").read_text() == "old"
    assert (m / "a.bak.1").read_text() == "older"
    assert (m / "a.bak.2").read_text() == "new"


def test_expiry_keeps_lock_files_and_sockets(tmp_path, monkeypatch):
    import socket
    ctx = make_ctx(tmp_path, hk={"state_dirs": ["replay"], "snapshot_dirs": []})
    d = ctx.state_dir / "replay"
    old = _file(d / "k1", 60)
    lock = _file(d / "k1.lock", 60, "")
    monkeypatch.chdir(d)
    s = socket.socket(socket.AF_UNIX)
    s.bind("x.sock")
    try:
        _age(d / "x.sock", 60)
        r = files.state_expiry(ctx)
    finally:
        s.close()
    assert r["items"] == 1 and not old.exists()
    assert lock.exists() and (d / "x.sock").exists()


def test_expiry_drops_orphan_lock_with_no_sibling(tmp_path):
    ctx = make_ctx(tmp_path, hk={"state_dirs": ["replay"], "snapshot_dirs": []})
    d = ctx.state_dir / "replay"
    orphan = _file(d / "orphan.lock", 60, "")
    r = files.state_expiry(ctx)
    assert r["items"] == 1 and not orphan.exists()


def test_expiry_keeps_fresh_orphan_lock(tmp_path):
    ctx = make_ctx(tmp_path, hk={"state_dirs": ["replay"], "snapshot_dirs": []})
    d = ctx.state_dir / "replay"
    orphan = _file(d / "orphan.lock", 1, "")
    r = files.state_expiry(ctx)
    assert r["items"] == 0 and orphan.exists()


def test_expiry_keeps_old_lock_with_dotted_sibling(tmp_path):
    ctx = make_ctx(tmp_path, hk={"state_dirs": ["replay"], "snapshot_dirs": []})
    d = ctx.state_dir / "replay"
    marker = _file(d / "k2.json", 60)
    lock = _file(d / "k2.lock", 60, "")
    r = files.state_expiry(ctx)
    assert not marker.exists()
    assert lock.exists()


def test_state_expiry_rejects_unsafe_dir_entries(tmp_path):
    for bad in ("", ".", "..", "a/b", "x..y"):
        ctx = make_ctx(tmp_path, hk={"state_dirs": ["tl_seen", bad],
                                     "snapshot_dirs": []})
        old = _file(ctx.state_dir / "tl_seen" / "sid-old", 31)
        r = files.state_expiry(ctx)
        assert r["items"] == 0 and "state_dirs" in r["error"], bad
        assert old.exists()
    ctx = make_ctx(tmp_path, hk={"state_dirs": [], "snapshot_dirs": ["../x"]})
    assert "snapshot_dirs" in files.state_expiry(ctx)["error"]


def test_repo_caches_respect_excludes(tmp_path):
    ctx = make_ctx(tmp_path)
    root = ctx.repos_root
    hit = [root / "marrow" / "marrow" / "__pycache__",
           root / "synapse" / ".pytest_cache"]
    miss = [root / "marrow" / ".venv" / "lib" / "__pycache__",
            root / "cadence" / ".build" / "__pycache__",
            root / "web" / "node_modules" / "x" / "__pycache__",
            root / "marrow" / ".claude" / "worktrees" / "agent-1" / "__pycache__"]
    for d in hit + miss:
        _file(d / "m.pyc", 0)
    r = files.repo_caches(ctx)
    assert r["items"] == 2
    assert not any(d.exists() for d in hit)
    assert all(d.exists() for d in miss)


def test_dry_run_counts_without_touching(tmp_path):
    ctx = make_ctx(tmp_path, dry_run=True)
    old = _file(ctx.backup_root / "manual" / "old.db", 31, "abcd")
    bak = _file(ctx.data_dir / "x.bak", 1)
    pyc = ctx.repos_root / "r" / "__pycache__"
    _file(pyc / "m.pyc", 0)
    assert files.manual_backups(ctx)["bytes_freed"] == 4
    assert files.stray_bak(ctx)["items"] == 1
    assert files.repo_caches(ctx)["items"] == 1
    assert old.exists() and bak.exists() and pyc.exists()
    assert not (ctx.backup_root / "manual" / "x.bak").exists()


def _ct_tables(conn):
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS ct_collector_log (id INTEGER PRIMARY KEY, "
        "source TEXT, ts TEXT, ok INTEGER, error TEXT);")
    from marrow.hooks import state
    state._ensure_ct_activity(conn)


def test_ct_prune_windows(tmp_path):
    conn = storage.init_db(str(tmp_path / "t.db"))
    _ct_tables(conn)
    for days in (5, 31, 200):
        conn.execute("INSERT INTO ct_collector_log (source, ts, ok) VALUES "
                     "('x', strftime('%Y-%m-%dT%H:%M:%f+00:00','now',?), 1)",
                     (f"-{days} days",))
    for days in (5, 89, 91):
        conn.execute("INSERT INTO ct_activity (ts, sid, channel) VALUES "
                     "(strftime('%Y-%m-%dT%H:%M:%SZ','now',?), 's', 'cli')",
                     (f"-{days} days",))
    conn.commit()
    dry = hdb.prune_ct_tables(conn, collector_days=30, activity_days=90,
                              dry_run=True)
    assert dry == {"ct_collector_log": 2, "ct_activity": 1}
    assert conn.execute("SELECT COUNT(*) FROM ct_collector_log").fetchone()[0] == 3
    with conn:
        got = hdb.prune_ct_tables(conn, collector_days=30, activity_days=90)
    assert got == dry
    assert conn.execute("SELECT COUNT(*) FROM ct_collector_log").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM ct_activity").fetchone()[0] == 2
    conn.close()


def test_ct_prune_missing_tables(tmp_path):
    conn = storage.init_db(str(tmp_path / "t.db"))
    assert hdb.prune_ct_tables(conn, collector_days=30, activity_days=90) == {
        "ct_collector_log": 0, "ct_activity": 0}
    conn.close()
