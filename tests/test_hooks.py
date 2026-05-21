"""Integration tests for marrow/hooks.py — thin CC hook entrypoints.

Hooks read paths from config; tests point config at a tmp db/dashboard via
monkeypatch and drive main() with stdin JSON like CC does.
"""
from __future__ import annotations

import io
import json

import pytest

from marrow import config, hooks, storage


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    dash = str(tmp_path / "dashboard.md")
    conn = storage.init_db(db)
    conn.execute("INSERT INTO threads(category,title,status) "
                 "VALUES('study','GAMSAT plan','active')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "db_path", lambda: db)
    monkeypatch.setattr(config, "dashboard_path", lambda: dash)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return db, dash, tmp_path


def _stdin(monkeypatch, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))


def test_session_start_emits_additional_context(env, monkeypatch, capsys):
    _stdin(monkeypatch, {"session_id": "s1"})
    rc = hooks.main(["session_start"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "GAMSAT plan" in ctx
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_session_end_archives_and_renders(env, monkeypatch, tmp_path):
    db, dash, _ = env
    jl = tmp_path / "s.jsonl"
    jl.write_text("\n".join(json.dumps(o) for o in [
        {"type": "user", "sessionId": "s1", "timestamp": "2026-05-17T01:00:00Z",
         "message": {"role": "user", "content": "build phase 1"}},
        {"type": "assistant", "sessionId": "s1",
         "timestamp": "2026-05-17T01:00:09Z",
         "message": {"role": "assistant",
                     "content": [{"type": "text", "text": "on it"}]}},
    ]))
    _stdin(monkeypatch, {"session_id": "s1", "transcript_path": str(jl)})
    rc = hooks.main(["session_end"])
    assert rc == 0
    conn = storage.connect(db)
    try:
        n = conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
    finally:
        conn.close()
    assert n == 2
    txt = open(dash).read()
    assert "GAMSAT plan" in txt and hooks.dashboard.M0 in txt


def test_session_end_dashboard_eperm_alerts_warn(env, monkeypatch, tmp_path):
    """TCC-protected Desktop write -> PermissionError must skip dashboard
    regen only; events still archived; a warn alert fires so the operator
    sees the TCC block instead of a silent stale dashboard (DESIGN L33)."""
    db, dash, _ = env
    jl = tmp_path / "s.jsonl"
    jl.write_text("\n".join(json.dumps(o) for o in [
        {"type": "user", "sessionId": "s1", "timestamp": "2026-05-17T01:00:00Z",
         "message": {"role": "user", "content": "build phase 1"}},
        {"type": "assistant", "sessionId": "s1",
         "timestamp": "2026-05-17T01:00:09Z",
         "message": {"role": "assistant",
                     "content": [{"type": "text", "text": "on it"}]}},
    ]))

    def boom(*a, **k):
        raise PermissionError(1, "Operation not permitted")
    monkeypatch.setattr(hooks.dashboard, "write_dashboard", boom)
    _stdin(monkeypatch, {"session_id": "s1", "transcript_path": str(jl)})
    rc = hooks.main(["session_end"])
    assert rc == 0
    conn = storage.connect(db)
    try:
        n = conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
        row = conn.execute(
            "SELECT severity, type, message FROM alerts").fetchone()
    finally:
        conn.close()
    assert n == 2  # events archive leg still succeeded
    assert row is not None
    assert row["severity"] == "warn"  # not critical, doesn't pollute handoff
    assert row["type"] == "dashboard"
    assert "session_end" in row["message"]


def test_session_end_real_error_still_alerts(env, monkeypatch, tmp_path):
    """A non-permission failure must still surface an alert (no broad catch)."""
    db, dash, _ = env
    jl = tmp_path / "s.jsonl"
    jl.write_text(json.dumps(
        {"type": "user", "sessionId": "s1", "timestamp": "2026-05-17T01:00:00Z",
         "message": {"role": "user", "content": "hi"}}))

    def boom(*a, **k):
        raise ValueError("genuine bug")
    monkeypatch.setattr(hooks.dashboard, "write_dashboard", boom)
    _stdin(monkeypatch, {"session_id": "s1", "transcript_path": str(jl)})
    assert hooks.main(["session_end"]) == 0
    conn = storage.connect(db)
    try:
        alerts = conn.execute("SELECT COUNT(*) c FROM alerts").fetchone()["c"]
    finally:
        conn.close()
    assert alerts == 1


def test_session_end_no_transcript_is_safe(env, monkeypatch):
    _stdin(monkeypatch, {"session_id": "s1"})
    assert hooks.main(["session_end"]) == 0


def test_unknown_event_usage_error(env, monkeypatch):
    _stdin(monkeypatch, {})
    assert hooks.main(["bogus"]) == 2
