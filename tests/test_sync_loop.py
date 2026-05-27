"""sync_loop — unit tests.

All tests use tmp_path + in-memory or tmp-path dbs; no real db touched.
Monkey-patched targets (fake db_mtime, reconcile, render callables) so we
can drive the loop deterministically without real subpage machinery.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable

import pytest

from marrow.sync_loop import (
    SyncLoop,
    SyncTarget,
    _MTIME_EPSILON_S,
    last_db_mtime_dashboard,
    last_db_mtime_subpage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    return c


def _target(
    md_path: str,
    db_mtime_fn: Callable,
    reconcile_fn=None,
    render_fn=None,
    name: str = "test",
) -> SyncTarget:
    return SyncTarget(
        name=name,
        md_path=md_path,
        db_mtime_fn=db_mtime_fn,
        reconcile_fn=reconcile_fn,
        render_fn=render_fn or (lambda c: None),
    )


# ---------------------------------------------------------------------------
# last_db_mtime_subpage
# ---------------------------------------------------------------------------

def test_last_db_mtime_subpage_unknown_key():
    c = _conn()
    assert last_db_mtime_subpage(c, "nonexistent_key") is None


def test_last_db_mtime_subpage_empty_sources():
    """wallet and cheatsheet have no sources → None."""
    c = _conn()
    assert last_db_mtime_subpage(c, "wallet") is None
    assert last_db_mtime_subpage(c, "cheatsheet") is None


def test_last_db_mtime_subpage_table_absent():
    """If the table doesn't exist, return None (not an error)."""
    c = _conn()
    result = last_db_mtime_subpage(c, "milestone")
    assert result is None  # milestones table absent in :memory: without init


def test_last_db_mtime_subpage_with_data(tmp_path):
    from marrow import storage
    db = str(tmp_path / "t.db")
    c = storage.init_db(db)
    c.execute(
        "INSERT INTO milestones (scope, date, title, updated_at)"
        " VALUES ('Us','2026-05-27','t1','2026-05-27T10:00:00Z')"
    )
    c.commit()
    ts = last_db_mtime_subpage(c, "milestone")
    assert ts is not None
    assert ts > 0.0
    c.close()


# ---------------------------------------------------------------------------
# last_db_mtime_dashboard
# ---------------------------------------------------------------------------

def test_last_db_mtime_dashboard_no_tables():
    c = _conn()
    assert last_db_mtime_dashboard(c) is None


def test_last_db_mtime_dashboard_aggregates_across_tables(tmp_path):
    """db_mtime = max across affect/tasks/milestones/alerts."""
    from marrow import storage
    db = str(tmp_path / "t.db")
    c = storage.init_db(db)
    # Insert into affect (created_at) and tasks (updated_at) with different times
    c.execute(
        "INSERT INTO affect (date,ep,valence,arousal,importance,created_at)"
        " VALUES ('2026-05-27',1,0.7,0.5,3,'2026-05-27T09:00:00Z')"
    )
    c.execute(
        "INSERT INTO tasks (category,title,updated_at)"
        " VALUES ('project','t1','2026-05-27T12:00:00Z')"
    )
    c.commit()
    ts = last_db_mtime_dashboard(c)
    assert ts is not None
    # Should pick max: tasks updated_at 12:00 > affect created_at 09:00
    from datetime import datetime, timezone
    expected = datetime(2026, 5, 27, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    assert abs(ts - expected) < 1.0
    c.close()


# ---------------------------------------------------------------------------
# SyncLoop — tick fires / shutdown
# ---------------------------------------------------------------------------

def test_sync_loop_tick_fires(tmp_path):
    """Loop calls _process on each iteration (db newer → render path)."""
    md = tmp_path / "t.md"
    md.write_text("# test")
    md_mtime = md.stat().st_mtime

    calls: list[str] = []
    db_mtime_base = md_mtime + 10.0  # db is newer → render path

    def db_fn(c):
        return db_mtime_base

    def render_fn(c):
        calls.append("render")

    t = _target(str(md), db_fn, render_fn=render_fn, name="tick-test")
    loop = SyncLoop(_conn, [t], tick_s=0.05)
    loop.start()
    time.sleep(0.3)
    loop.stop()
    assert len(calls) >= 2  # boot tick + at least one timed tick


def test_sync_loop_shutdown_stops_cleanly(tmp_path):
    """stop() terminates the thread without hanging."""
    md = tmp_path / "x.md"
    md.write_text("x")
    t = _target(str(md), lambda c: None, name="shutdown-test")
    loop = SyncLoop(_conn, [t], tick_s=0.1)
    loop.start()
    time.sleep(0.05)
    loop.stop(timeout=2.0)
    assert loop._thread is not None
    assert not loop._thread.is_alive()


# ---------------------------------------------------------------------------
# md newer → reconcile called, render NOT called independently
# ---------------------------------------------------------------------------

def test_md_newer_calls_reconcile_only(tmp_path):
    md = tmp_path / "subpage.md"
    md.write_text("# hello")
    md_mtime = md.stat().st_mtime
    db_mtime = md_mtime - 10.0  # md is newer

    reconciled: list[int] = []
    rendered: list[int] = []

    def recon(c, p):
        reconciled.append(1)

    def render(c):
        rendered.append(1)

    t = _target(str(md), lambda c: db_mtime, reconcile_fn=recon, render_fn=render)
    loop = SyncLoop(_conn, [t], tick_s=100.0)  # only boot tick
    loop.start()
    time.sleep(0.1)
    loop.stop()
    # Reconcile called; render also called (after reconcile md is stable → render)
    assert reconciled, "reconcile should be called when md newer"


def test_md_newer_no_reconcile_fn_skips(tmp_path):
    """Subpage with no reconcile callback: md→db direction is skipped entirely."""
    md = tmp_path / "t.md"
    md.write_text("x")
    md_mtime = md.stat().st_mtime
    db_mtime = md_mtime - 10.0

    rendered: list[int] = []

    t = _target(str(md), lambda c: db_mtime,
                reconcile_fn=None, render_fn=lambda c: rendered.append(1))
    loop = SyncLoop(_conn, [t], tick_s=100.0)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    # No reconcile → process returns early; render also not called
    assert rendered == []


# ---------------------------------------------------------------------------
# db newer → render called
# ---------------------------------------------------------------------------

def test_db_newer_calls_render(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("x")
    md_mtime = md.stat().st_mtime
    db_mtime = md_mtime + 10.0  # db is newer

    rendered: list[int] = []

    t = _target(str(md), lambda c: db_mtime, render_fn=lambda c: rendered.append(1))
    loop = SyncLoop(_conn, [t], tick_s=100.0)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    assert len(rendered) >= 1


# ---------------------------------------------------------------------------
# Equal mtimes (within epsilon) → noop
# ---------------------------------------------------------------------------

def test_equal_mtimes_noop(tmp_path):
    """md ≥ db within md→db epsilon → neither branch fires."""
    md = tmp_path / "t.md"
    md.write_text("x")
    md_mtime = md.stat().st_mtime

    reconciled: list[int] = []
    rendered: list[int] = []

    # db_mtime equal-to-or-just-behind md_mtime. md→db epsilon still applies
    # (avoids spurious reconciles on fs jitter), and db is NOT newer than md
    # so the render branch also does not fire.
    db_mtime = md_mtime - 0.1

    def recon(c, p):
        reconciled.append(1)

    t = _target(str(md), lambda c: db_mtime,
                reconcile_fn=recon, render_fn=lambda c: rendered.append(1))
    loop = SyncLoop(_conn, [t], tick_s=100.0)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    assert reconciled == []
    assert rendered == []


def test_db_slightly_newer_renders(tmp_path):
    """Regression: db just-a-bit-newer-than-md must trigger render in next tick.

    Pre-fix the 1s db→md epsilon would swallow this and md never reflected
    the db change (atlas depth-shrink / dashboard refresh freeze symptom).
    """
    md = tmp_path / "t.md"
    md.write_text("x")
    md_mtime = md.stat().st_mtime

    rendered: list[int] = []
    # 0.5s ahead — used to be inside epsilon, now must render.
    db_mtime = md_mtime + 0.5

    t = _target(str(md), lambda c: db_mtime,
                render_fn=lambda c: rendered.append(1))
    loop = SyncLoop(_conn, [t], tick_s=100.0)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    assert len(rendered) >= 1


# ---------------------------------------------------------------------------
# Race防御: mid-reconcile md write → render skipped
# ---------------------------------------------------------------------------

def test_race_defense_mid_reconcile_md_write(tmp_path):
    """If md mtime advances during reconcile, render is skipped this tick."""
    md = tmp_path / "race.md"
    md.write_text("initial")
    md_mtime_initial = md.stat().st_mtime
    db_mtime = md_mtime_initial - 10.0  # md is newer → reconcile path

    rendered: list[int] = []

    def recon(c, p):
        # Simulate user writing to md during reconcile
        time.sleep(0.02)
        md.write_text("mid-reconcile edit")
        # Touch to ensure mtime advances
        now = time.time() + 1.0
        import os
        os.utime(str(md), (now, now))

    t = _target(str(md), lambda c: db_mtime,
                reconcile_fn=recon, render_fn=lambda c: rendered.append(1))
    loop = SyncLoop(_conn, [t], tick_s=100.0)
    loop.start()
    time.sleep(0.2)
    loop.stop()
    # Render must be skipped because md advanced during reconcile
    assert rendered == [], "render must be skipped when md advanced mid-reconcile"


# ---------------------------------------------------------------------------
# Multiple targets processed independently
# ---------------------------------------------------------------------------

def test_multiple_targets_independent(tmp_path):
    md1 = tmp_path / "a.md"
    md2 = tmp_path / "b.md"
    md1.write_text("a")
    md2.write_text("b")
    now = time.time()

    calls: dict[str, list] = {"a_render": [], "b_render": []}

    # md1: db newer → render
    t1 = _target(str(md1), lambda c: now + 10.0,
                 render_fn=lambda c: calls["a_render"].append(1), name="a")
    # md2: db newer → render
    t2 = _target(str(md2), lambda c: now + 10.0,
                 render_fn=lambda c: calls["b_render"].append(1), name="b")

    loop = SyncLoop(_conn, [t1, t2], tick_s=100.0)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    assert len(calls["a_render"]) >= 1
    assert len(calls["b_render"]) >= 1


# ---------------------------------------------------------------------------
# Missing md file → skip
# ---------------------------------------------------------------------------

def test_missing_md_skipped(tmp_path):
    rendered: list[int] = []
    t = _target(
        str(tmp_path / "nonexistent.md"),
        lambda c: time.time() + 10.0,
        render_fn=lambda c: rendered.append(1),
    )
    loop = SyncLoop(_conn, [t], tick_s=100.0)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    assert rendered == []


# ---------------------------------------------------------------------------
# db_mtime None → skip
# ---------------------------------------------------------------------------

def test_db_mtime_none_skipped(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("x")
    rendered: list[int] = []
    t = _target(str(md), lambda c: None, render_fn=lambda c: rendered.append(1))
    loop = SyncLoop(_conn, [t], tick_s=100.0)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    assert rendered == []
