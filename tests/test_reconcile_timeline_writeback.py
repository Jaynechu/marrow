from __future__ import annotations

import datetime as _dt
import time
from pathlib import Path

import pytest

from marrow import storage
from marrow.reconcile import reconcile_timeline


@pytest.fixture()
def conn(tmp_path):
    c = storage.init_db(str(tmp_path / "tl-writeback.db"))
    yield c
    c.close()


@pytest.fixture()
def dash_path(tmp_path) -> Path:
    return tmp_path / "dashboard.md"


def _now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _future_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3600))


def _insert_digest(
    conn,
    sid: str,
    life_lines: str,
    *,
    segment_seq: int = 0,
    ts: str | None = None,
) -> None:
    ts = ts or _now_utc()
    conn.execute(
        "INSERT INTO session_digests"
        " (sid, segment_seq, date, ts, text, kind, life_lines)"
        " VALUES (?, ?, ?, ?, 'body', 'casual', ?)",
        (sid, segment_seq, ts[:10], ts, life_lines),
    )
    conn.commit()


def test_life_line_edit_updates_indexed_line(conn, dash_path):
    _insert_digest(conn, "sid-life", "10:00 first\n11:00 second")
    dash_path.write_text(
        "## Timeline\n"
        "11:00 changed second <!-- tl:sid-life:0:1 -->\n",
        encoding="utf-8",
    )

    rpt = reconcile_timeline(conn, dash_path)

    row = conn.execute(
        "SELECT life_lines FROM session_digests WHERE sid='sid-life'"
    ).fetchone()
    assert row["life_lines"] == "10:00 first\n11:00 changed second"
    assert rpt.updated == 1


def test_life_line_mtime_gate_skips_future_digest(conn, dash_path):
    _insert_digest(conn, "sid-future", "10:00 original", ts=_future_ts())
    dash_path.write_text(
        "## Timeline\n"
        "10:00 stale edit <!-- tl:sid-future:0:0 -->\n",
        encoding="utf-8",
    )

    rpt = reconcile_timeline(conn, dash_path)

    row = conn.execute(
        "SELECT life_lines FROM session_digests WHERE sid='sid-future'"
    ).fetchone()
    assert row["life_lines"] == "10:00 original"
    assert rpt.updated == 0
    assert rpt.unchanged == 1


def test_life_line_index_out_of_range_conflicts_without_crash(conn, dash_path):
    _insert_digest(conn, "sid-short", "10:00 only line")
    dash_path.write_text(
        "## Timeline\n"
        "12:00 impossible edit <!-- tl:sid-short:0:3 -->\n",
        encoding="utf-8",
    )

    rpt = reconcile_timeline(conn, dash_path)

    row = conn.execute(
        "SELECT life_lines FROM session_digests WHERE sid='sid-short'"
    ).fetchone()
    assert row["life_lines"] == "10:00 only line"
    assert rpt.updated == 0
    assert any("out of range" in conflict for conflict in rpt.conflicts)


def test_old_format_anchor_without_line_index_is_unchanged(conn, dash_path):
    _insert_digest(conn, "sid-old", "10:00 original")
    dash_path.write_text(
        "## Timeline\n"
        "10:00 edited old format <!-- tl:sid-old:0 -->\n",
        encoding="utf-8",
    )

    rpt = reconcile_timeline(conn, dash_path)

    row = conn.execute(
        "SELECT life_lines FROM session_digests WHERE sid='sid-old'"
    ).fetchone()
    assert row["life_lines"] == "10:00 original"
    assert rpt.updated == 0
    assert rpt.unchanged == 1
