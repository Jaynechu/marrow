"""Per-turn vector backfill in the Stop hook, plus the pending probe.

The embedd service boundary (ping / client_embed / socket_path) is faked in
every test and the in-process loader is booby-trapped: the Stop hook must
never load the ONNX model.
"""
from __future__ import annotations

import argparse
import fcntl
import io
import json
import sqlite3

import numpy as np
import pytest

from marrow import cli, config, embedd, hooks, recall, storage
from marrow.hooks import lifecycle


def _u(uuid, parent, content, role="user"):
    t = "user" if role == "user" else "assistant"
    msg = ({"role": "user", "content": content} if role == "user"
           else {"role": "assistant", "model": "claude-opus-4-7",
                 "content": [{"type": "text", "text": content}]})
    return {"type": t, "sessionId": "s1", "timestamp": "2026-07-03T01:00:00Z",
            "uuid": uuid, "parentUuid": parent, "isSidechain": False,
            "message": msg}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    storage.init_db(db).close()
    monkeypatch.setattr(config, "db_path", lambda: db)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(lifecycle, "_PAUSE_INGEST_PATH", tmp_path / "pause_ingest")
    monkeypatch.setattr(embedd, "socket_path", lambda: tmp_path / "embedd.sock")

    def _no_local():
        raise AssertionError("Stop hook must not load the model in-process")

    monkeypatch.setattr(recall, "_ensure_embedder", _no_local)
    alerts: list[str] = []
    monkeypatch.setattr(embedd, "alert_unreachable", lambda d: alerts.append(d))
    return db, tmp_path, alerts


@pytest.fixture()
def service(monkeypatch):
    """Live embedd stand-in: answers ping and returns 1024-d vectors."""
    calls: list[list[str]] = []
    monkeypatch.setattr(embedd, "enabled", lambda: True)
    monkeypatch.setattr(embedd, "ping", lambda: {"ok": True, "loaded": True})

    def _embed(texts):
        calls.append(list(texts))
        return np.ones((len(texts), 1024), dtype=np.float32)

    monkeypatch.setattr(embedd, "client_embed", _embed)
    return calls


def _cfg_with(monkeypatch, **embed):
    real = config.load

    def fake():
        cfg = dict(real())
        cfg["embed"] = dict(cfg["embed"], **embed)
        return cfg

    monkeypatch.setattr(config, "load", fake)


def _run_stop(monkeypatch, tmp_path, sid="s1"):
    jl = tmp_path / f"{sid}.jsonl"
    jl.write_text("\n".join(json.dumps(o) for o in [
        _u("u1", None, "hello"), _u("a1", "u1", "hi there", role="assistant"),
    ]), encoding="utf-8")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"session_id": sid, "transcript_path": str(jl), "cwd": str(tmp_path)})))
    assert hooks.main(["stop"]) == 0


def _add_event(conn, content="hi"):
    conn.execute(
        "INSERT INTO events (session_id, timestamp, role, content) "
        "VALUES ('s', '2026-07-28T00:00:00Z', 'user', ?)", (content,))
    conn.commit()


def _embedded(db, lane="events"):
    conn = storage.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {lane}_vec_meta").fetchone()[0]
    finally:
        conn.close()


def _pending(db):
    conn = storage.connect(db)
    try:
        return sum(recall.pending_counts(conn).values())
    finally:
        conn.close()


# ── stop(): per-turn embed ───────────────────────────────────────────────────

def test_stop_embeds_pending_via_service(env, service, monkeypatch):
    db, tmp, alerts = env
    _run_stop(monkeypatch, tmp)
    assert _embedded(db) == 2
    assert _pending(db) == 0
    assert sorted(t for c in service for t in c) == ["hello", "hi there"]
    assert alerts == []


def test_stop_embeds_other_lanes_too(env, service, monkeypatch):
    db, tmp, _ = env
    conn = storage.connect(db)
    conn.execute("INSERT INTO memes (type, key, value, status) "
                 "VALUES ('word', 'k', 'v', 'active')")
    conn.commit()
    conn.close()
    _run_stop(monkeypatch, tmp)
    assert _embedded(db, "memes") == 1
    assert _pending(db) == 0


def test_stop_empty_queue_makes_no_embed_call(env, monkeypatch):
    db, tmp, _ = env
    (tmp / "pause_ingest").touch()

    def _boom(*_a, **_k):
        raise AssertionError("no embed work expected on an empty queue")

    monkeypatch.setattr(embedd, "enabled", lambda: True)
    monkeypatch.setattr(embedd, "ping", _boom)
    monkeypatch.setattr(embedd, "client_embed", _boom)
    monkeypatch.setattr(recall, "embed_pending", _boom)
    _run_stop(monkeypatch, tmp)
    assert _pending(db) == 0


def test_stop_skips_when_service_disabled(env, monkeypatch):
    db, tmp, alerts = env
    monkeypatch.setattr(embedd, "enabled", lambda: False)
    _run_stop(monkeypatch, tmp)
    assert _embedded(db) == 0
    assert _pending(db) == 2
    assert alerts == []


def test_stop_socket_absent_alerts_and_keeps_pending(env, monkeypatch):
    db, tmp, alerts = env
    monkeypatch.setattr(embedd, "enabled", lambda: True)
    assert not embedd.socket_path().exists()
    _run_stop(monkeypatch, tmp)
    assert _embedded(db) == 0
    assert _pending(db) == 2
    assert alerts == ["socket absent"]


def test_stop_socket_present_but_dead_alerts_and_keeps_pending(env, monkeypatch):
    db, tmp, alerts = env
    monkeypatch.setattr(embedd, "enabled", lambda: True)
    (tmp / "embedd.sock").write_text("not a socket")
    _run_stop(monkeypatch, tmp)
    assert _embedded(db) == 0
    assert _pending(db) == 2
    assert len(alerts) >= 1


def test_stop_client_unreachable_alerts_and_keeps_pending(env, monkeypatch):
    db, tmp, alerts = env
    monkeypatch.setattr(embedd, "enabled", lambda: True)
    monkeypatch.setattr(embedd, "ping", lambda: {"ok": True, "loaded": True})

    def _dead(_texts):
        raise embedd.ServiceUnreachable("boom")

    monkeypatch.setattr(embedd, "client_embed", _dead)
    _run_stop(monkeypatch, tmp)
    assert _embedded(db) == 0
    assert _pending(db) == 2
    assert "boom" in alerts


def test_stop_respects_turn_cap(env, service, monkeypatch):
    db, tmp, _ = env
    (tmp / "pause_ingest").touch()
    conn = storage.connect(db)
    for i in range(5):
        _add_event(conn, f"e{i}")
    conn.close()
    _cfg_with(monkeypatch, turn_cap=2)
    _run_stop(monkeypatch, tmp)
    assert _embedded(db) == 2
    _run_stop(monkeypatch, tmp)
    assert _embedded(db) == 4


def test_stop_skips_while_embed_lock_held(env, service, monkeypatch):
    db, tmp, _ = env
    with open(tmp / "embed.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _run_stop(monkeypatch, tmp)
    assert _embedded(db) == 0
    assert service == []


def test_stop_embed_error_never_breaks_hook(env, monkeypatch):
    db, tmp, _ = env

    def _boom(*_a, **_k):
        raise RuntimeError("embed exploded")

    monkeypatch.setattr(recall, "embed_pending", _boom)
    _run_stop(monkeypatch, tmp)
    assert _pending(db) == 2
    cur = json.loads((tmp / "state" / "ct_cursor" / "s1.json").read_text())
    assert cur["last_uuid"] == "a1" and cur["offset"] > 0


# ── mw embed reads [embed] ───────────────────────────────────────────────────

def test_cmd_embed_uses_embed_section(env, monkeypatch, capsys):
    db, _, _ = env
    _cfg_with(monkeypatch, batch=7, max_batches=3)
    seen: list[int] = []

    def fake(conn, batch=50, **_k):
        seen.append(batch)
        return 1

    monkeypatch.setattr(recall, "embed_pending", fake)
    args = argparse.Namespace(batch=None, max_batches=None, db=db)
    assert cli.cmd_embed(args) == 0
    assert seen == [7, 7, 7]
    assert "embed: 3 rows" in capsys.readouterr().out


# ── recall.pending_counts — real schema, real SQL ────────────────────────────

@pytest.fixture
def db(tmp_path):
    conn = storage.init_db(str(tmp_path / "p.db"))
    yield conn
    conn.close()


def test_pending_counts_empty_db(db):
    counts = recall.pending_counts(db)
    assert set(counts) == set(recall._LANES)
    assert sum(counts.values()) == 0


def test_pending_counts_sees_unembedded_event(db):
    _add_event(db, "one")
    _add_event(db, "two")
    counts = recall.pending_counts(db)
    assert counts["events"] == 2
    assert sum(counts.values()) == 2


def test_pending_counts_ignores_embedded_rows(db):
    _add_event(db, "one")
    row_id = db.execute("SELECT id FROM events").fetchone()[0]
    db.execute("INSERT INTO events_vec_meta (rowid, embedder_id, dim) "
               "VALUES (?, 'bge-m3', 1024)", (row_id,))
    db.commit()
    assert recall.pending_counts(db)["events"] == 0


def test_pending_counts_respects_cap(db):
    for i in range(5):
        _add_event(db, f"e{i}")
    assert recall.pending_counts(db, cap=2)["events"] == 2


def test_pending_counts_survives_missing_table():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    assert recall.pending_counts(conn) == {}
    conn.close()
