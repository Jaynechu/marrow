"""Smoke test: SyncLoop + AtlasSweepLoop accept conn_factory and start/stop cleanly."""
from __future__ import annotations

import sqlite3
import time

from marrow.sync_loop import AtlasSweepLoop, SyncLoop, SyncTarget


def _factory(tmp_path):
    db = str(tmp_path / "smoke.db")
    def _mk() -> sqlite3.Connection:
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        return c
    return _mk


def test_sync_loop_conn_factory_start_stop(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("x")
    t = SyncTarget(
        name="smoke",
        md_path=str(md),
        db_mtime_fn=lambda c: None,
        reconcile_fn=None,
        render_fn=lambda c: None,
    )
    loop = SyncLoop(_factory(tmp_path), [t], tick_s=10.0)
    loop.start()
    time.sleep(0.05)
    loop.stop(timeout=2.0)
    assert loop._thread is not None
    assert not loop._thread.is_alive()


def test_atlas_sweep_loop_conn_factory_start_stop(tmp_path, monkeypatch):
    # Monkeypatch drift_sweep.AUTHORIZED_ROOTS to an empty list so sweep_once
    # has nothing to walk — just verifies no crash.
    from marrow import drift_sweep
    monkeypatch.setattr(drift_sweep, "AUTHORIZED_ROOTS", [])

    sweep = AtlasSweepLoop(_factory(tmp_path), tick_s=10.0)
    sweep.start()
    time.sleep(0.05)
    sweep.stop(timeout=2.0)
    assert sweep._thread is not None
    assert not sweep._thread.is_alive()
