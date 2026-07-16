"""db_win split — render residue vs clobbered human edit.

When the freshness gate keeps DB text over a stale md line, we now branch on
the md FILE's real mtime vs the render trail t= (+ slack):
  - residue  (file mtime <= t= + slack): silent self-heal → audit_log only.
  - clobber  (file mtime  > t= + slack): a human edit was overwritten → warn.
"""
from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

import pytest

from marrow import storage
from marrow.reconcile import reconcile_timeline


@pytest.fixture()
def dbpath(tmp_path):
    return str(tmp_path / "dw.db")


@pytest.fixture()
def conn(dbpath):
    c = storage.init_db(dbpath)
    yield c
    c.close()


def _utc(delta_s: float = 0.0) -> str:
    dt = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=delta_s)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(iso: str) -> float:
    return (_dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=_dt.timezone.utc).timestamp())


def _insert_self(conn, content: str, created_at: str, updated_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO events (session_id, timestamp, role, content, channel,"
        " created_at, updated_at)"
        " VALUES ('s1', ?, 'tl', ?, 'cli', ?, ?)",
        (created_at, content, created_at, updated_at),
    )
    conn.commit()
    return cur.lastrowid


def _write_stale(path: Path, eid: int, t0: str) -> None:
    path.write_text(
        "## Timeline\n"
        f"14:00 【a】旧值 <!-- tl:e:{eid} -->\n"
        f"<!-- tl-rendered:e={eid};t={t0} -->\n"
    )


def _audit_rows(conn):
    return conn.execute(
        "SELECT * FROM audit_log WHERE action='md_stale_db_win'"
    ).fetchall()


def _alert_rows(dbpath):
    c = storage.connect(dbpath)
    try:
        return c.execute(
            "SELECT * FROM alerts WHERE fingerprint='timeline_reconcile:db_win'"
        ).fetchall()
    finally:
        c.close()


def test_residue_audit_only_no_alert(conn, dbpath, tmp_path):
    """File untouched since the render (mtime <= t= + slack) → self-heal:
    audit_log row, no alert, DB text kept."""
    t0 = _utc(-120)          # render moment
    row_ts = _utc(-60)       # DB row edited after render → gate keeps DB
    eid = _insert_self(conn, "【a】新值", created_at=t0, updated_at=row_ts)

    path = tmp_path / "daybrief.md"
    _write_stale(path, eid, t0)
    # File not touched by a human since render → mtime == render moment.
    os.utime(path, (_epoch(t0), _epoch(t0)))

    rpt = reconcile_timeline(conn, path, db=dbpath)

    assert rpt.updated == 0
    assert conn.execute(
        "SELECT content FROM events WHERE id=?", (eid,)
    ).fetchone()["content"] == "【a】新值"
    assert len(_audit_rows(conn)) == 1
    assert len(_alert_rows(dbpath)) == 0


def test_human_edit_clobbered_warns(conn, dbpath, tmp_path):
    """File modified after the render (mtime > t= + slack) → a real hand edit
    was overwritten → warn alert still fires, no residue audit row."""
    t0 = _utc(-120)
    row_ts = _utc(-60)
    eid = _insert_self(conn, "【a】新值", created_at=t0, updated_at=row_ts)

    path = tmp_path / "daybrief.md"
    _write_stale(path, eid, t0)
    # Human touched the file well after the render (now >> t0 + 5s slack).
    os.utime(path, (_epoch(_utc(0)), _epoch(_utc(0))))

    rpt = reconcile_timeline(conn, path, db=dbpath)

    assert rpt.updated == 0
    assert conn.execute(
        "SELECT content FROM events WHERE id=?", (eid,)
    ).fetchone()["content"] == "【a】新值"
    alerts = _alert_rows(dbpath)
    assert len(alerts) == 1
    assert f"e:{eid}" in alerts[0]["message"]
    assert len(_audit_rows(conn)) == 0
