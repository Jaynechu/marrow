"""Memes dedup gate tests:
- string dup against milestone.title / entities_live.name / aliases
- cosine dup via bge-m3 (real round-trip, slow)
- memes_reject_log accumulation + fast-skip
- freq_gate rejects must NOT log
- embedder-missing fallback
- migration v11 idempotent + lossless
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from marrow import candidates, memes_dedup, recall, storage


# ── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path):
    return storage.init_db(str(tmp_path / "dedup.db"))


def _ev(conn, sid, ts, role, content):
    conn.execute(
        "INSERT INTO events(session_id,timestamp,role,content)"
        " VALUES(?,?,?,?)", (sid, ts, role, content),
    )


def _seed_events_with_key(conn, key: str, count: int, date: str):
    base = dt.date.fromisoformat(date)
    for i in range(count):
        ts = (base - dt.timedelta(days=i % 6)).isoformat() + "T10:00:00Z"
        _ev(conn, f"s{i}", ts, "user", f"chat {key} more chat {i}")
    conn.commit()


def _disable_cosine(monkeypatch):
    """Force cosine check to return None (embedder absent path)."""
    monkeypatch.setattr(
        memes_dedup, "cosine_dup_score", lambda conn, key: None,
    )


def _force_cosine(monkeypatch, score: float):
    monkeypatch.setattr(
        memes_dedup, "cosine_dup_score", lambda conn, key: score,
    )


# ── 1. baseline: new candidate inserts ──────────────────────────────────────

def test_new_candidate_inserts_as_before(db, monkeypatch):
    _disable_cosine(monkeypatch)
    _seed_events_with_key(db, "totally_new_key", 4, "2026-05-16")
    raw = (
        "===MEMES_CAND===\n"
        "[{\"key\":\"totally_new_key\",\"type\":\"meme\","
        " \"value\":\"x\",\"pinned\":0,\"conf\":0.9}]\n"
        "===END===\n"
    )
    n = candidates.write_memes_cand(db, raw, date="2026-05-16")
    assert n == 1
    row = db.execute(
        "SELECT key FROM memes WHERE key='totally_new_key'"
    ).fetchone()
    assert row is not None


# ── 2. dup_milestone ────────────────────────────────────────────────────────

def test_candidate_matching_milestone_title_rejected(db, monkeypatch):
    _disable_cosine(monkeypatch)
    db.execute(
        "INSERT INTO milestones (scope, date, title) VALUES (?, ?, ?)",
        ("me", "2026-02-19", "2/19合同"),
    )
    db.commit()
    _seed_events_with_key(db, "2/19合同", 4, "2026-05-16")
    raw = (
        "===MEMES_CAND===\n"
        "[{\"key\":\"2/19合同\",\"type\":\"event\","
        " \"value\":\"\",\"pinned\":0,\"conf\":0.9}]\n"
        "===END===\n"
    )
    n = candidates.write_memes_cand(db, raw, date="2026-05-16")
    assert n == 0
    assert db.execute(
        "SELECT 1 FROM memes WHERE key='2/19合同'"
    ).fetchone() is None
    log = db.execute(
        "SELECT count, reason FROM memes_reject_log"
        " WHERE key='2/19合同' AND type='event'"
    ).fetchone()
    assert log["reason"] == "dup_milestone" and log["count"] == 1


# ── 3. dup_entity (alias match) ─────────────────────────────────────────────

def test_candidate_matching_entity_alias_rejected(db, monkeypatch):
    _disable_cosine(monkeypatch)
    db.execute(
        "INSERT INTO entities (kind, name, aliases) VALUES (?, ?, ?)",
        ("person", "Stellan",
         json.dumps(["鸭子", "屿忱"], ensure_ascii=False)),
    )
    db.commit()
    _seed_events_with_key(db, "鸭子", 4, "2026-05-16")
    raw = (
        "===MEMES_CAND===\n"
        "[{\"key\":\"鸭子\",\"type\":\"paw\","
        " \"value\":\"x\",\"pinned\":0,\"conf\":0.9}]\n"
        "===END===\n"
    )
    n = candidates.write_memes_cand(db, raw, date="2026-05-16")
    assert n == 0
    assert db.execute("SELECT 1 FROM memes WHERE key='鸭子'").fetchone() is None
    log = db.execute(
        "SELECT reason FROM memes_reject_log WHERE key='鸭子' AND type='paw'"
    ).fetchone()
    assert log["reason"] == "dup_entity"


def test_candidate_matching_entity_name_rejected(db, monkeypatch):
    _disable_cosine(monkeypatch)
    db.execute(
        "INSERT INTO entities (kind, name) VALUES (?, ?)",
        ("person", "Summer"),
    )
    db.commit()
    _seed_events_with_key(db, "Summer", 4, "2026-05-16")
    raw = (
        "===MEMES_CAND===\n"
        "[{\"key\":\"Summer\",\"type\":\"meme\","
        " \"value\":\"x\",\"pinned\":0,\"conf\":0.9}]\n"
        "===END===\n"
    )
    n = candidates.write_memes_cand(db, raw, date="2026-05-16")
    assert n == 0
    log = db.execute(
        "SELECT reason FROM memes_reject_log WHERE key='Summer'"
    ).fetchone()
    assert log["reason"] == "dup_entity"


# ── 4. cosine_dup (forced score) ────────────────────────────────────────────

def test_cosine_dup_forced_score_rejected(db, monkeypatch):
    _force_cosine(monkeypatch, 0.91)
    _seed_events_with_key(db, "签约合同", 4, "2026-05-16")
    raw = (
        "===MEMES_CAND===\n"
        "[{\"key\":\"签约合同\",\"type\":\"event\","
        " \"value\":\"x\",\"pinned\":0,\"conf\":0.9}]\n"
        "===END===\n"
    )
    n = candidates.write_memes_cand(db, raw, date="2026-05-16")
    assert n == 0
    log = db.execute(
        "SELECT reason FROM memes_reject_log WHERE key='签约合同'"
    ).fetchone()
    assert log["reason"] == "cosine_dup"


def test_cosine_below_threshold_inserts(db, monkeypatch):
    _force_cosine(monkeypatch, 0.55)
    _seed_events_with_key(db, "新概念xx", 4, "2026-05-16")
    raw = (
        "===MEMES_CAND===\n"
        "[{\"key\":\"新概念xx\",\"type\":\"meme\","
        " \"value\":\"x\",\"pinned\":0,\"conf\":0.9}]\n"
        "===END===\n"
    )
    n = candidates.write_memes_cand(db, raw, date="2026-05-16")
    assert n == 1


# ── 5. real bge-m3 round trip (slow, skip if model absent) ──────────────────

def _embedder_available() -> bool:
    return recall._ensure_embedder() is not None


@pytest.mark.skipif(
    not _embedder_available(), reason="bge-m3 model files not present",
)
def test_cosine_dup_real_bge_m3_round_trip(tmp_path):
    """Real round-trip: insert milestone '签约协议', candidate '签约合同'.
    bge-m3 should score these CN paraphrases ≥0.85 → cosine_dup reject.
    """
    p = str(tmp_path / "real.db")
    conn = storage.init_db(p)
    conn.execute(
        "INSERT INTO milestones (scope, date, title) VALUES (?, ?, ?)",
        ("us", "2026-02-19", "签约协议"),
    )
    base = dt.date.fromisoformat("2026-05-16")
    for i in range(4):
        ts = (base - dt.timedelta(days=i % 6)).isoformat() + "T10:00:00Z"
        conn.execute(
            "INSERT INTO events(session_id,timestamp,role,content)"
            " VALUES(?,?,?,?)", (f"s{i}", ts, "user", f"提了 签约合同 {i}"),
        )
    conn.commit()
    raw = (
        "===MEMES_CAND===\n"
        "[{\"key\":\"签约合同\",\"type\":\"event\","
        " \"value\":\"x\",\"pinned\":0,\"conf\":0.9}]\n"
        "===END===\n"
    )
    n = candidates.write_memes_cand(conn, raw, date="2026-05-16")
    assert n == 0
    log = conn.execute(
        "SELECT reason FROM memes_reject_log WHERE key='签约合同'"
    ).fetchone()
    assert log is not None and log["reason"] == "cosine_dup"


# ── 6. reject_log accumulation ──────────────────────────────────────────────

def test_reject_log_count_accumulates(db, monkeypatch):
    _disable_cosine(monkeypatch)
    db.execute(
        "INSERT INTO milestones (scope, date, title) VALUES (?, ?, ?)",
        ("me", "2026-02-19", "dup_title"),
    )
    db.commit()
    _seed_events_with_key(db, "dup_title", 4, "2026-05-16")
    raw = (
        "===MEMES_CAND===\n"
        "[{\"key\":\"dup_title\",\"type\":\"event\","
        " \"value\":\"x\",\"pinned\":0,\"conf\":0.9}]\n"
        "===END===\n"
    )
    # First reject lands count=1.
    candidates.write_memes_cand(db, raw, date="2026-05-16")
    # Second reject bumps count=2 — still below fast_skip_count=3.
    candidates.write_memes_cand(db, raw, date="2026-05-16")
    log = db.execute(
        "SELECT count FROM memes_reject_log WHERE key='dup_title'"
    ).fetchone()
    assert log["count"] == 2


# ── 7. fast-skip after threshold ────────────────────────────────────────────

def test_fast_skip_after_threshold(db, monkeypatch):
    _disable_cosine(monkeypatch)
    db.execute(
        "INSERT INTO milestones (scope, date, title) VALUES (?, ?, ?)",
        ("me", "2026-02-19", "fast_skip_title"),
    )
    db.commit()
    _seed_events_with_key(db, "fast_skip_title", 4, "2026-05-16")
    raw = (
        "===MEMES_CAND===\n"
        "[{\"key\":\"fast_skip_title\",\"type\":\"event\","
        " \"value\":\"x\",\"pinned\":0,\"conf\":0.9}]\n"
        "===END===\n"
    )
    # Drive count to 3 via three rejects.
    for _ in range(3):
        candidates.write_memes_cand(db, raw, date="2026-05-16")
    log = db.execute(
        "SELECT count FROM memes_reject_log WHERE key='fast_skip_title'"
    ).fetchone()
    assert log["count"] == 3
    # Patch string_dup_reason to RAISE so we can prove the fast-skip path
    # exits before any gate work runs.
    def _explode(*_a, **_k):
        raise AssertionError("string_dup_reason should be skipped")
    monkeypatch.setattr(memes_dedup, "string_dup_reason", _explode)
    n = candidates.write_memes_cand(db, raw, date="2026-05-16")
    assert n == 0
    # Count must NOT bump again — fast-skip drops silently, no log write.
    log = db.execute(
        "SELECT count FROM memes_reject_log WHERE key='fast_skip_title'"
    ).fetchone()
    assert log["count"] == 3


# ── 8. freq_gate reject must NOT log ────────────────────────────────────────

def test_freq_gate_reject_does_not_log(db, monkeypatch):
    _disable_cosine(monkeypatch)
    # Zero events → freq_gate fails for type=meme.
    raw = (
        "===MEMES_CAND===\n"
        "[{\"key\":\"freq_only_key\",\"type\":\"meme\","
        " \"value\":\"x\",\"pinned\":0,\"conf\":0.9}]\n"
        "===END===\n"
    )
    n = candidates.write_memes_cand(db, raw, date="2026-05-16")
    assert n == 0
    log = db.execute(
        "SELECT 1 FROM memes_reject_log WHERE key='freq_only_key'"
    ).fetchone()
    assert log is None


# ── 9. embedder-missing path raises one alert ───────────────────────────────

def test_embedder_missing_alert_idempotent(db, monkeypatch):
    _disable_cosine(monkeypatch)
    _seed_events_with_key(db, "alert_key_xy", 4, "2026-05-16")
    raw = (
        "===MEMES_CAND===\n"
        "[{\"key\":\"alert_key_xy\",\"type\":\"meme\","
        " \"value\":\"x\",\"pinned\":0,\"conf\":0.9}]\n"
        "===END===\n"
    )
    candidates.write_memes_cand(db, raw, date="2026-05-16")
    candidates.write_memes_cand(db, raw, date="2026-05-16")
    n_alerts = db.execute(
        "SELECT COUNT(*) c FROM alerts WHERE type='memes_dedup_no_embedder'"
    ).fetchone()["c"]
    assert n_alerts == 1


# ── 10. migration v11 idempotency + losslessness ────────────────────────────

def test_v11_migration_idempotent(tmp_path):
    p = str(tmp_path / "mig.db")
    conn = storage.init_db(p)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == storage.SCHEMA_VERSION
    # Insert a row then re-init.
    conn.execute(
        "INSERT INTO memes_reject_log (key, type, reason, count,"
        " last_rejected_at) VALUES ('x', 'meme', 'cosine_dup', 2, 'now')"
    )
    conn.commit()
    conn.close()
    conn2 = storage.init_db(p)
    row = conn2.execute(
        "SELECT count FROM memes_reject_log WHERE key='x'"
    ).fetchone()
    assert row["count"] == 2


def test_v11_migration_preserves_existing_memes(tmp_path):
    """Stand up at v10 baseline, insert memes, then re-init at v11. Memes
    survive the migration unscathed.
    """
    p = str(tmp_path / "v10.db")
    conn = storage.init_db(p)
    conn.execute(
        "INSERT INTO memes (type, key, value) VALUES ('fact', 'k1', 'v1')"
    )
    conn.execute(
        "INSERT INTO memes (type, key, value) VALUES ('paw', 'k2', 'v2')"
    )
    conn.commit()
    conn.close()
    conn2 = storage.init_db(p)
    n = conn2.execute("SELECT COUNT(*) c FROM memes").fetchone()["c"]
    assert n == 2
    # memes_reject_log exists now
    conn2.execute("SELECT 1 FROM memes_reject_log LIMIT 1")
