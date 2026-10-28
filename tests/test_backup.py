"""Tests for marrow/backup.py — DESIGN net "DB never lost".

Contract: atomic local snapshot (never half-written), offsite copy,
offsite-unreachable still leaves local ok + raises a failure alert,
conservative retention keeps exactly N, dry-run writes nothing,
same-day re-run is idempotent.
"""
from __future__ import annotations

import sqlite3

from marrow import backup, storage


def _seed_db(path):
    conn = storage.init_db(str(path))
    with conn:
        conn.execute(
            "INSERT INTO events (session_id, timestamp, role, content) "
            "VALUES ('s', '2026-05-19T00:00:00Z', 'user', 'hello')"
        )
    conn.close()


def _table_names(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        return {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()


# ── atomic snapshot integrity ────────────────────────────────────────────────

def test_snapshot_is_integral_copy(tmp_path):
    src = tmp_path / "marrow.db"
    _seed_db(src)
    local = tmp_path / "backup"
    offsite = tmp_path / "icloud"
    rep = backup.run(
        apply=True, db=str(src), local_dir=str(local),
        offsite_dir=str(offsite), keep=14, today="2026-05-19",
        alert_db=str(src),
    )
    snap = local / "marrow-2026-05-19.db"
    assert snap.exists()
    # sqlite_master row set must match the source exactly.
    assert _table_names(snap) == _table_names(src)
    conn = sqlite3.connect(str(snap))
    try:
        n = conn.execute("SELECT count(*) FROM events").fetchone()[0]
    finally:
        conn.close()
    assert n == 1
    assert rep["local_ok"] is True
    assert rep["offsite_ok"] is True
    assert (offsite / "marrow-2026-05-19.db").exists()


def test_no_partial_file_left_on_disk(tmp_path):
    src = tmp_path / "marrow.db"
    _seed_db(src)
    local = tmp_path / "backup"
    backup.run(
        apply=True, db=str(src), local_dir=str(local),
        offsite_dir=str(tmp_path / "ic"), keep=14, today="2026-05-19",
        alert_db=str(src),
    )
    # Only the final named snapshot, no .tmp leftovers.
    assert [p.name for p in sorted(local.iterdir())] == ["marrow-2026-05-19.db"]


# ── offsite unreachable: local still ok + alert ──────────────────────────────

def test_offsite_unreachable_local_ok_and_alert_raised(tmp_path):
    src = tmp_path / "marrow.db"
    _seed_db(src)
    local = tmp_path / "backup"
    # A file (not a dir) at the offsite parent makes mkdir/copy fail.
    bad_parent = tmp_path / "blocked"
    bad_parent.write_text("not a directory")
    offsite = bad_parent / "sub"
    rep = backup.run(
        apply=True, db=str(src), local_dir=str(local),
        offsite_dir=str(offsite), keep=14, today="2026-05-19",
        alert_db=str(src),
    )
    assert rep["local_ok"] is True
    assert (local / "marrow-2026-05-19.db").exists()
    assert rep["offsite_ok"] is False
    conn = storage.connect(str(src))
    try:
        rows = conn.execute(
            "SELECT severity, type FROM alerts"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0]["type"] == "backup"


# ── retention prune keeps exactly N ──────────────────────────────────────────

def test_retention_keeps_exactly_n_newest(tmp_path):
    src = tmp_path / "marrow.db"
    _seed_db(src)
    local = tmp_path / "backup"
    local.mkdir()
    # 20 pre-existing daily dumps.
    for d in range(1, 21):
        (local / f"marrow-2026-04-{d:02d}.db").write_text("old")
    backup.run(
        apply=True, db=str(src), local_dir=str(local),
        offsite_dir=str(tmp_path / "ic"), keep=14, today="2026-05-19",
        alert_db=str(src),
    )
    names = sorted(p.name for p in local.iterdir())
    assert len(names) == 14
    # Newest kept: today's + the 13 most recent old ones (08..20).
    assert "marrow-2026-05-19.db" in names
    assert "marrow-2026-04-20.db" in names
    assert "marrow-2026-04-07.db" not in names


def test_offsite_retention_also_pruned(tmp_path):
    src = tmp_path / "marrow.db"
    _seed_db(src)
    offsite = tmp_path / "ic"
    offsite.mkdir()
    for d in range(1, 21):
        (offsite / f"marrow-2026-04-{d:02d}.db").write_text("old")
    backup.run(
        apply=True, db=str(src), local_dir=str(tmp_path / "b"),
        offsite_dir=str(offsite), keep=5, today="2026-05-19",
        alert_db=str(src),
    )
    assert len([p for p in offsite.iterdir()]) == 5


# ── dry-run writes nothing ───────────────────────────────────────────────────

def test_dry_run_writes_nothing(tmp_path):
    src = tmp_path / "marrow.db"
    _seed_db(src)
    local = tmp_path / "backup"
    offsite = tmp_path / "ic"
    rep = backup.run(
        apply=False, db=str(src), local_dir=str(local),
        offsite_dir=str(offsite), keep=14, today="2026-05-19",
        alert_db=str(src),
    )
    assert not (local / "marrow-2026-05-19.db").exists()
    assert not offsite.exists() or list(offsite.iterdir()) == []
    assert rep["applied"] is False
    assert rep["would_write"].endswith("marrow-2026-05-19.db")


def test_plan_lists_prune_targets_without_deleting(tmp_path):
    local = tmp_path / "backup"
    local.mkdir()
    for d in range(1, 21):
        (local / f"marrow-2026-04-{d:02d}.db").write_text("old")
    plan = backup.plan(local_dir=str(local), keep=14, today="2026-05-19")
    assert len(plan["prune"]) == 7  # 20 old + 1 new = 21, keep 14 -> 7
    # Nothing deleted by planning.
    assert len(list(local.iterdir())) == 20


# ── idempotent same-day re-run ───────────────────────────────────────────────

def test_same_day_rerun_is_idempotent(tmp_path):
    src = tmp_path / "marrow.db"
    _seed_db(src)
    local = tmp_path / "backup"
    offsite = tmp_path / "ic"
    kw = dict(
        apply=True, db=str(src), local_dir=str(local),
        offsite_dir=str(offsite), keep=14, today="2026-05-19",
        alert_db=str(src),
    )
    backup.run(**kw)
    first = sorted(p.name for p in local.iterdir())
    backup.run(**kw)
    second = sorted(p.name for p in local.iterdir())
    assert first == second == ["marrow-2026-05-19.db"]


# ── weekly copy (Sunday only, local only) ────────────────────────────────────

def _weekly_kw(tmp_path, src, today):
    return dict(
        apply=True, db=str(src), local_dir=str(tmp_path / "daily"),
        offsite_dir=str(tmp_path / "ic"), weekly_dir=str(tmp_path / "weekly"),
        keep=14, weekly_keep=13, today=today, alert_db=str(src),
    )


def test_sunday_copies_daily_into_weekly(tmp_path):
    src = tmp_path / "marrow.db"
    _seed_db(src)
    rep = backup.run(**_weekly_kw(tmp_path, src, "2026-11-01"))
    daily = tmp_path / "daily" / "marrow-2026-11-01.db"
    weekly = tmp_path / "weekly" / "marrow-2026-11-01.db"
    assert rep["weekly_ok"] is True
    assert weekly.read_bytes() == daily.read_bytes()
    assert not (tmp_path / "ic" / "weekly").exists()


def test_weekday_writes_no_weekly(tmp_path):
    src = tmp_path / "marrow.db"
    _seed_db(src)
    rep = backup.run(**_weekly_kw(tmp_path, src, "2026-11-02"))
    assert rep["weekly_ok"] is None
    assert rep["weekly_would_write"] is None
    assert not (tmp_path / "weekly").exists()


def test_weekly_prunes_beyond_keep(tmp_path):
    src = tmp_path / "marrow.db"
    _seed_db(src)
    weekly = tmp_path / "weekly"
    weekly.mkdir()
    for d in range(1, 21):
        (weekly / f"marrow-2026-04-{d:02d}.db").write_text("old")
    backup.run(**_weekly_kw(tmp_path, src, "2026-11-01"))
    names = sorted(p.name for p in weekly.iterdir())
    assert len(names) == 13
    assert names[-1] == "marrow-2026-11-01.db"
    assert "marrow-2026-04-08.db" not in names
    assert "marrow-2026-04-09.db" in names


def test_dry_run_sunday_plans_weekly_without_writing(tmp_path):
    src = tmp_path / "marrow.db"
    _seed_db(src)
    kw = _weekly_kw(tmp_path, src, "2026-11-01")
    kw["apply"] = False
    rep = backup.run(**kw)
    assert rep["weekly_would_write"] == str(tmp_path / "weekly" / "marrow-2026-11-01.db")
    assert not (tmp_path / "weekly").exists()
    assert not (tmp_path / "daily").exists()


def test_default_dirs_resolve_under_backup_root(tmp_path, monkeypatch):
    from marrow import config
    real = config.load

    def _load():
        cfg = real()
        cfg["paths"]["backup_dir"] = str(tmp_path / "bk")
        return cfg

    monkeypatch.setattr(config, "load", _load)
    rep = backup.run(apply=False, today="2026-11-01")
    assert rep["would_write"] == str(tmp_path / "bk" / "daily" / "marrow-2026-11-01.db")
    assert rep["weekly_would_write"] == str(tmp_path / "bk" / "weekly" / "marrow-2026-11-01.db")
    assert config.load()["backup"]["weekly_keep"] == 13
