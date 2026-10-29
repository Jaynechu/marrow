"""sync_loop settle gate: a target renders once per real change, then stays
quiet until md mtime, db mtime or its stamp_fn value moves. Ticks are driven
directly (no thread); render callables are fakes."""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from marrow.sync_loop import SyncLoop, SyncTarget


def _backdate(p: Path, seconds: float = 10.0) -> float:
    past = time.time() - seconds
    os.utime(str(p), (past, past))
    return p.stat().st_mtime


def _loop(target: SyncTarget) -> SyncLoop:
    return SyncLoop(lambda: sqlite3.connect(":memory:"), [target], tick_s=100.0)


def _ticks(loop: SyncLoop, n: int) -> None:
    for _ in range(n):
        loop._tick()


def test_identical_render_settles_after_one_call(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("x")
    _backdate(md)
    calls: list[int] = []
    t = SyncTarget("t", str(md), lambda c: md.stat().st_mtime - 30.0,
                   lambda c: calls.append(1))
    loop = _loop(t)
    _ticks(loop, 5)
    assert calls == [1]


def test_db_newer_identical_render_settles(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("x")
    _backdate(md)
    calls: list[int] = []
    t = SyncTarget("t", str(md), lambda c: time.time() + 3600.0,
                   lambda c: calls.append(1))
    loop = _loop(t)
    _ticks(loop, 3)
    assert len(calls) == 3

    fixed = time.time() + 3600.0
    t.db_mtime_fn = lambda c: fixed
    calls.clear()
    _ticks(loop, 4)
    assert calls == [1]


def test_render_that_writes_md_is_rechecked_then_settles(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("old")
    _backdate(md, 20.0)
    db = md.stat().st_mtime + 5.0
    calls: list[int] = []

    def render(c):
        calls.append(1)
        if md.read_text() != "new":
            md.write_text("new")
            _backdate(md, 10.0)

    t = SyncTarget("t", str(md), lambda c: db, render)
    loop = _loop(t)
    _ticks(loop, 5)
    assert len(calls) == 2


def test_user_md_edit_after_settle_is_processed(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("x")
    _backdate(md, 20.0)
    calls: list[int] = []
    t = SyncTarget("t", str(md), lambda c: 1000.0, lambda c: calls.append(1))
    loop = _loop(t)
    _ticks(loop, 3)
    assert calls == [1]

    md.write_text("user edit")
    _backdate(md, 5.0)
    _ticks(loop, 1)
    assert calls == [1, 1]


def test_user_active_edit_is_not_settled(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("typing")
    calls: list[int] = []
    t = SyncTarget("t", str(md), lambda c: 1000.0, lambda c: calls.append(1))
    loop = _loop(t)
    _ticks(loop, 2)
    assert calls == []

    _backdate(md, 5.0)
    _ticks(loop, 2)
    assert calls == [1]


def test_db_change_after_settle_is_rendered(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("x")
    md_mtime = _backdate(md)
    db = {"t": md_mtime + 2.0}
    calls: list[int] = []
    t = SyncTarget("t", str(md), lambda c: db["t"], lambda c: calls.append(1))
    loop = _loop(t)
    _ticks(loop, 3)
    assert calls == [1]

    db["t"] += 1.0
    _ticks(loop, 3)
    assert calls == [1, 1]


def test_stamp_change_forces_render_inside_epsilon(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("x")
    md_mtime = _backdate(md)
    stamp = {"v": 1}
    calls: list[int] = []
    t = SyncTarget("t", str(md), lambda c: md_mtime - 0.1,
                   lambda c: calls.append(1), stamp_fn=lambda: stamp["v"])
    loop = _loop(t)
    _ticks(loop, 3)
    assert calls == [1]

    stamp["v"] = 2
    _ticks(loop, 3)
    assert calls == [1, 1]


def test_no_stamp_inside_epsilon_stays_idle(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("x")
    md_mtime = _backdate(md)
    calls: list[int] = []
    t = SyncTarget("t", str(md), lambda c: md_mtime - 0.1,
                   lambda c: calls.append(1))
    loop = _loop(t)
    _ticks(loop, 3)
    assert calls == []


def test_render_error_is_not_settled(tmp_path):
    md = tmp_path / "t.md"
    md.write_text("x")
    _backdate(md)
    calls: list[int] = []

    def render(c):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    t = SyncTarget("t", str(md), lambda c: 1000.0, render)
    loop = _loop(t)
    _ticks(loop, 3)
    assert calls == [1, 1]


def test_daybrief_target_settles_and_gates_cadence(monkeypatch, tmp_path):
    from marrow import config, daybrief, schedule, storage, subpages, sync_loop

    db = str(tmp_path / "t.db")
    c = storage.init_db(db)
    c.execute(
        "INSERT INTO session_digests (sid, date, ts, text, kind, life_lines)"
        " VALUES ('s1', '2026-07-10', '2026-07-10T01:00:00Z', 'body',"
        " 'casual', '11:00 walked')")
    c.commit()
    c.close()
    md = tmp_path / "daybrief.md"
    md.write_text("seed")
    _backdate(md, 60.0)
    binary = tmp_path / "cadence"
    binary.write_text("")
    data = {"mtime": 100.0}
    spawns: list[list[str]] = []

    def fake_run(args, _binary):
        spawns.append(args)
        return "[]"

    monkeypatch.setattr(config, "daybrief_path", lambda: str(md))
    monkeypatch.setattr(config, "monitor_path", lambda: "")
    monkeypatch.setattr(subpages, "build_all_configs", lambda *a, **k: [])
    monkeypatch.setattr(sync_loop, "_daybrief_refresh_s", lambda: 1e9)
    monkeypatch.setattr(sync_loop, "USER_ACTIVE_WINDOW_S", -1.0)
    monkeypatch.setattr(daybrief, "_out_path", lambda: str(md))
    monkeypatch.setattr(daybrief, "_sleep_status_line", lambda: "")
    monkeypatch.setattr(daybrief.usage, "sessionstart_lines",
                        lambda: ["Plan Used: 5h 1%"])
    monkeypatch.setattr(schedule, "_fetch_cache", {})
    monkeypatch.setattr(schedule, "_cadence_bin", lambda: str(binary))
    monkeypatch.setattr(schedule, "_run_cadence", fake_run)
    monkeypatch.setattr(schedule, "get_data_mtime", lambda: data["mtime"])

    targets = sync_loop.build_targets(str(tmp_path), str(tmp_path))
    assert [t.name for t in targets] == ["daybrief"]
    loop = SyncLoop(lambda: storage.connect(db), targets, tick_s=100.0)
    loop._conn = storage.connect(db)
    try:
        _ticks(loop, 10)
        assert len(spawns) == 3
        assert "### Rem & Cal" in md.read_text()
        settled_mtime = md.stat().st_mtime
        _ticks(loop, 5)
        assert md.stat().st_mtime == settled_mtime

        data["mtime"] = 101.0
        _ticks(loop, 5)
        assert len(spawns) == 6
    finally:
        loop._conn.close()
