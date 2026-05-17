"""Tests for marrow/repo.py public API + daemon smoke test."""
from __future__ import annotations

import marrow.daemon as daemon
import pytest

from marrow import repo, storage

ROWS = [
    {"session_id": "s1", "timestamp": "2026-05-17T01:00:00Z", "role": "user",
     "content": "hello marrow world"},
    {"session_id": "s1", "timestamp": "2026-05-17T01:01:00Z", "role": "assistant",
     "content": "hi there, welcome back"},
]


@pytest.fixture()
def db(tmp_path):
    conn = storage.init_db(str(tmp_path / "t.db"))
    yield conn
    conn.close()


# ── recall ────────────────────────────────────────────────────────────────────

def test_recall_hit(db):
    repo.archive_events(db, ROWS)
    results = repo.recall(db, "marrow")
    assert len(results) == 1
    assert results[0]["content"] == "hello marrow world"


def test_recall_empty_query(db):
    repo.archive_events(db, ROWS)
    assert repo.recall(db, "") == []
    assert repo.recall(db, "   ") == []


def test_recall_budget_chars_truncates(db):
    rows = [
        {"session_id": "s1", "timestamp": "2026-05-17T02:00:00Z", "role": "user",
         "content": "x" * 3000},
        {"session_id": "s1", "timestamp": "2026-05-17T02:01:00Z", "role": "user",
         "content": "x" * 3000},
    ]
    repo.archive_events(db, rows)
    # budget_chars=4000; first row fills 3000, second gets truncated to 1000
    results = repo.recall(db, "x", limit=10, budget_chars=4000)
    total = sum(len(r["content"]) for r in results)
    assert total <= 4000


# ── open_threads ──────────────────────────────────────────────────────────────

def test_open_threads_active_only(db):
    db.execute("INSERT INTO threads(category,title,status) VALUES('work','A','active')")
    db.execute("INSERT INTO threads(category,title,status) VALUES('work','B','closed')")
    db.commit()
    titles = [t["title"] for t in repo.open_threads(db)]
    assert "A" in titles
    assert "B" not in titles


def test_open_threads_due_before_null(db):
    db.execute("INSERT INTO threads(category,title,status,due) VALUES('work','NullDue','active',NULL)")
    db.execute("INSERT INTO threads(category,title,status,due) VALUES('work','HasDue','active','2026-06-01')")
    db.commit()
    titles = [t["title"] for t in repo.open_threads(db)]
    assert titles.index("HasDue") < titles.index("NullDue")


# ── open_alerts ───────────────────────────────────────────────────────────────

def test_open_alerts_unresolved_only(db):
    db.execute("INSERT INTO alerts(severity,type,message,resolved) VALUES('warn','x','open',0)")
    db.execute("INSERT INTO alerts(severity,type,message,resolved) VALUES('warn','x','done',1)")
    db.commit()
    msgs = [a["message"] for a in repo.open_alerts(db)]
    assert "open" in msgs
    assert "done" not in msgs


def test_open_alerts_severity_order(db):
    db.execute("INSERT INTO alerts(severity,type,message) VALUES('warn','x','w')")
    db.execute("INSERT INTO alerts(severity,type,message) VALUES('info','x','o')")
    db.execute("INSERT INTO alerts(severity,type,message) VALUES('critical','x','c')")
    db.commit()
    severities = [a["severity"] for a in repo.open_alerts(db)]
    assert severities.index("critical") < severities.index("warn")
    assert severities.index("warn") < severities.index("info")


# ── handoff ───────────────────────────────────────────────────────────────────

def test_handoff_keys(db):
    h = repo.handoff(db)
    assert set(h.keys()) == {"threads", "alerts"}


def test_handoff_reflects_open(db):
    db.execute("INSERT INTO threads(category,title,status) VALUES('work','T','active')")
    db.execute("INSERT INTO alerts(severity,type,message) VALUES('warn','x','A')")
    db.commit()
    h = repo.handoff(db)
    assert len(h["threads"]) == 1
    assert len(h["alerts"]) == 1


# ── add_alert ─────────────────────────────────────────────────────────────────

def test_add_alert_returns_id(tmp_path):
    p = str(tmp_path / "a.db")
    storage.init_db(p).close()
    aid = repo.add_alert("warn", "test", "something happened", db=p)
    assert isinstance(aid, int) and aid > 0


def test_add_alert_writes_alerts_and_audit(tmp_path):
    p = str(tmp_path / "a.db")
    storage.init_db(p).close()
    aid = repo.add_alert("critical", "llm", "provider down", source="llm.py", db=p)
    conn = storage.connect(p)
    try:
        alert_row = conn.execute("SELECT * FROM alerts WHERE id=?", (aid,)).fetchone()
        assert alert_row is not None
        assert alert_row["severity"] == "critical"
        audit_row = conn.execute(
            "SELECT * FROM audit_log WHERE target_table='alerts' AND target_id=?",
            (str(aid),),
        ).fetchone()
        assert audit_row is not None
        assert audit_row["action"] == "insert"
    finally:
        conn.close()


# ── archive_events ────────────────────────────────────────────────────────────

def test_archive_events_inserts_n(db):
    n = repo.archive_events(db, ROWS)
    assert n == len(ROWS)


def test_archive_events_idempotent(db):
    repo.archive_events(db, ROWS)
    n2 = repo.archive_events(db, ROWS)
    assert n2 == 0


def test_archive_events_fts_indexed(db):
    repo.archive_events(db, ROWS)
    results = repo.recall(db, "welcome")
    assert len(results) == 1
    assert "welcome" in results[0]["content"]


# ── daemon smoke ──────────────────────────────────────────────────────────────

def test_daemon_mcp_exists():
    assert hasattr(daemon, "mcp"), "daemon.mcp not found"


def test_daemon_recall_callable():
    assert callable(daemon.recall), "daemon.recall is not callable"


def test_daemon_recall_returns_list(tmp_path, monkeypatch):
    # _DB is read by name from daemon module globals at each call, so patching
    # it after import is safe — no closure baking at def time.
    p = str(tmp_path / "d.db")
    storage.init_db(p).close()
    monkeypatch.setattr(daemon, "_DB", p)
    result = daemon.recall("anything")
    assert isinstance(result, list)
