"""event_clear / tl clear: local-time bounds, 0-match refusal, dry_run.

Temp DB only; `mw refresh` (subprocess.run) and the /tmp backup copy are
replaced by recorders. conftest pins local tz to Australia/Melbourne; all
dates below are AEST (+10).
"""
from __future__ import annotations

import pytest

from marrow import config, cortex_bridge, daemon, purge, storage

DAY_BEFORE_LAST = "2026-09-29T13:59:00Z"   # 09-29 23:59 local
DAY_FIRST = "2026-09-29T14:00:00Z"         # 09-30 00:00 local
DAY_LAST = "2026-09-30T13:59:00Z"          # 09-30 23:59 local
NEXT_FIRST = "2026-09-30T14:00:00Z"        # 10-01 00:00 local
ALL_TS = (DAY_BEFORE_LAST, DAY_FIRST, DAY_LAST, NEXT_FIRST)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    storage.init_db(db).close()
    monkeypatch.setattr(daemon, "_DB", db)
    monkeypatch.setattr(cortex_bridge, "_DB", db)
    monkeypatch.setattr(config, "db_path", lambda: db)
    monkeypatch.setattr(daemon, "_PAUSE_INGEST_PATH", tmp_path / "pause_ingest")
    calls = {"refresh": 0, "backup": 0}

    def _run(*a, **k):
        calls["refresh"] += 1

    def _backup(db_path, tag):
        calls["backup"] += 1
        return f"/tmp/fake-{tag}.db"

    monkeypatch.setattr(purge.subprocess, "run", _run)
    monkeypatch.setattr(purge, "_backup", _backup)
    return db, calls


def _insert(db, ts, role="user", sid="s1"):
    conn = storage.connect(db)
    try:
        with conn:
            conn.execute(
                "INSERT INTO events (session_id, timestamp, role, content,"
                " channel, ts_start) VALUES (?, ?, ?, 'x', 'cli', ?)",
                (sid, ts, role, ts if role == "tl" else None))
    finally:
        conn.close()


def _remaining(db, role=None):
    conn = storage.connect(db)
    try:
        sql = "SELECT timestamp FROM events"
        params: tuple = ()
        if role:
            sql += " WHERE role=?"
            params = (role,)
        return sorted(r[0] for r in conn.execute(sql + " ORDER BY timestamp", params))
    finally:
        conn.close()


def _seed(db, role="user"):
    for ts in ALL_TS:
        _insert(db, ts, role=role)


# ── event_clear ──────────────────────────────────────────────────────────────

def test_event_clear_local_day_hits_only_that_day(env):
    db, calls = env
    _seed(db)
    out = daemon.event_clear(after="2026-09-30", before="2026-10-01")
    assert out["ok"] is True
    assert out["deleted"] == 2
    assert out["after_utc"] == "2026-09-29T14:00:00Z"
    assert out["before_utc"] == "2026-09-30T14:00:00Z"
    assert out["after_local"] == "2026-09-30 00:00"
    assert out["before_local"] == "2026-10-01 00:00"
    assert _remaining(db) == [DAY_BEFORE_LAST, NEXT_FIRST]
    assert calls == {"refresh": 1, "backup": 1}


def test_event_clear_local_datetime_bounds(env):
    db, _ = env
    _seed(db)
    out = daemon.event_clear(after="2026-09-30 00:00", before="2026-09-30 23:59")
    assert out["deleted"] == 1
    assert _remaining(db) == [DAY_BEFORE_LAST, DAY_LAST, NEXT_FIRST]


def test_event_clear_explicit_utc_bound_respected(env):
    db, _ = env
    _seed(db)
    out = daemon.event_clear(before="2026-09-29T14:00:00Z")
    assert out["deleted"] == 1
    assert _remaining(db) == [DAY_FIRST, DAY_LAST, NEXT_FIRST]


def test_event_clear_zero_match_refuses(env):
    db, calls = env
    _seed(db)
    out = daemon.event_clear(after="2026-08-01", before="2026-08-02")
    assert out["ok"] is False
    assert out["error"] == "0 rows matched"
    assert out["after_local"] == "2026-08-01 00:00"
    assert len(_remaining(db)) == 4
    assert calls == {"refresh": 0, "backup": 0}


def test_event_clear_empty_db_full_clear_refuses(env):
    db, calls = env
    out = daemon.event_clear()
    assert out == {"ok": False, "error": "0 rows matched"}
    assert not daemon._PAUSE_INGEST_PATH.exists()
    assert calls == {"refresh": 0, "backup": 0}


def test_event_clear_dry_run_deletes_nothing(env):
    db, calls = env
    _seed(db)
    out = daemon.event_clear(after="2026-09-30", before="2026-10-01", dry_run=True)
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["matched"] == 2
    assert out["earliest"] == "2026-09-30 00:00"
    assert out["latest"] == "2026-09-30 23:59"
    assert len(_remaining(db)) == 4
    assert calls == {"refresh": 0, "backup": 0}


def test_event_clear_dry_run_last_and_full(env):
    db, _ = env
    _seed(db)
    assert daemon.event_clear(last=3, dry_run=True)["matched"] == 3
    assert daemon.event_clear(dry_run=True)["matched"] == 4
    assert not daemon._PAUSE_INGEST_PATH.exists()
    assert len(_remaining(db)) == 4


def test_event_clear_bad_bound_errors(env):
    db, calls = env
    _seed(db)
    out = daemon.event_clear(before="yesterday")
    assert out["ok"] is False
    assert "bad time" in out["error"]
    assert len(_remaining(db)) == 4
    assert calls == {"refresh": 0, "backup": 0}


def test_event_clear_sid_with_local_day(env):
    db, _ = env
    _insert(db, DAY_FIRST, sid="keep-me")
    _insert(db, DAY_LAST, sid="drop-me")
    out = daemon.event_clear(after="2026-09-30", before="2026-10-01", sid="drop")
    assert out["deleted"] == 1
    assert _remaining(db) == [DAY_FIRST]


def test_event_clear_last_reports_actual_count(env):
    db, _ = env
    _insert(db, DAY_FIRST)
    out = daemon.event_clear(last=5)
    assert out["deleted"] == 1


# ── tl clear ─────────────────────────────────────────────────────────────────

def test_tl_clear_local_day_hits_only_that_day(env):
    db, calls = env
    _seed(db, role="tl")
    _insert(db, DAY_FIRST, role="user")
    out = daemon.tl("clear", after="2026-09-30", before="2026-10-01")
    assert out["ok"] is True
    assert out["deleted"] == 2
    assert out["after_local"] == "2026-09-30 00:00"
    assert out["before_utc"] == "2026-09-30T14:00:00Z"
    assert [ln[:5] for ln in out["lines"]] == ["00:00", "23:59"]
    assert _remaining(db, "tl") == [DAY_BEFORE_LAST, NEXT_FIRST]
    assert _remaining(db, "user") == [DAY_FIRST]
    assert calls == {"refresh": 1, "backup": 1}


def test_tl_clear_zero_match_refuses(env):
    db, calls = env
    _seed(db, role="tl")
    out = daemon.tl("clear", after="2026-08-01", before="2026-08-02")
    assert out["ok"] is False
    assert out["error"] == "0 rows matched"
    assert len(_remaining(db, "tl")) == 4
    assert calls == {"refresh": 0, "backup": 0}


def test_tl_clear_zero_match_event_id_refuses(env):
    _, calls = env
    out = daemon.tl("clear", event_id=999)
    assert out == {"ok": False, "error": "0 rows matched"}
    assert calls == {"refresh": 0, "backup": 0}


def test_tl_clear_dry_run_deletes_nothing(env):
    db, calls = env
    _seed(db, role="tl")
    out = daemon.tl("clear", after="2026-09-30", before="2026-10-01", dry_run=True)
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["matched"] == 2
    assert out["earliest"] == "2026-09-30 00:00"
    assert out["latest"] == "2026-09-30 23:59"
    assert len(_remaining(db, "tl")) == 4
    assert calls == {"refresh": 0, "backup": 0}


def test_tl_clear_bad_bound_errors(env):
    db, _ = env
    _seed(db, role="tl")
    out = daemon.tl("clear", after="30/09/2026")
    assert out["ok"] is False
    assert "bad time" in out["error"]
    assert len(_remaining(db, "tl")) == 4
