"""housekeep orchestration: audit row, run-failure streak alert, dry-run."""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

import pytest

from _housekeep_shared import make_ctx
from marrow import storage
from marrow.housekeep import __main__ as hk
from marrow.housekeep import result


def _ok_pass(ctx):
    return result(1)


def _bad_pass(ctx):
    return result(error="boom")


@pytest.fixture()
def groups(monkeypatch):
    g = {"a": [("good", _ok_pass)]}
    monkeypatch.setattr(hk, "GROUPS", g)
    return g


def _row(ctx, ok, days_ago, *, only=None, passes=None, sizes=None):
    ts = (date.today() - timedelta(days=days_ago)).isoformat() + "T02:00:00Z"
    payload = {"ok": ok, "passes": passes or {}, "sizes": sizes or {}}
    if only:
        payload["only"] = [only]
    conn = storage.connect(ctx.db)
    with conn:
        conn.execute(
            "INSERT INTO audit_log (target_table, target_id, action, summary, "
            "occurred_at) VALUES ('housekeep', NULL, 'housekeep', ?, ?)",
            (json.dumps(payload), ts))
    conn.close()


def _alerts(ctx):
    conn = storage.connect(ctx.db)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE type='housekeep_failed'").fetchone()[0]
    finally:
        conn.close()


def _audit_rows(ctx):
    conn = storage.connect(ctx.db)
    try:
        return [json.loads(r[0]) for r in conn.execute(
            "SELECT summary FROM audit_log WHERE action='housekeep' ORDER BY id")]
    finally:
        conn.close()


def _crash_report(monkeypatch):
    def _boom(ctx, results):
        raise OSError("report unwritable")
    monkeypatch.setattr(hk.report, "update", _boom)


def test_failed_pass_is_not_a_run_failure(tmp_path, groups):
    groups["b"] = [("bad", _bad_pass)]
    ctx = make_ctx(tmp_path)
    _row(ctx, False, 7)
    _row(ctx, False, 1)
    assert hk.execute(ctx, None) == 0
    rows = _audit_rows(ctx)
    assert rows[-1]["ok"] is True and "error" not in rows[-1]
    assert rows[-1]["passes"]["good"] == {"items": 1, "bytes_freed": 0,
                                          "error": None}
    assert rows[-1]["passes"]["bad"]["error"] == "boom"
    assert _alerts(ctx) == 0


def test_failed_pass_goes_to_report(tmp_path, groups):
    groups["b"] = [("bad", _bad_pass)]
    ctx = make_ctx(tmp_path)
    hk.execute(ctx, None)
    assert "- failed: bad: boom\n" in ctx.report_path.read_text()


def test_every_apply_is_a_full_run(tmp_path, groups):
    calls = []
    groups["a"].append(("probe", lambda c: calls.append(1) or result()))
    ctx = make_ctx(tmp_path)
    _row(ctx, True, 0)
    hk.execute(ctx, None)
    hk.execute(ctx, None)
    assert calls == [1, 1]
    assert len(_audit_rows(ctx)) == 3


def test_growth_baseline_is_last_full_run_sizes(tmp_path, groups):
    seen = {}
    groups["a"] = [("probe", lambda c: seen.update(c.prev_sizes) or result())]
    ctx = make_ctx(tmp_path)
    _row(ctx, True, 14, sizes={"x": 1})
    _row(ctx, True, 7, sizes={"x": 2})
    _row(ctx, True, 1, only="files", sizes={"x": 3})
    hk.execute(ctx, None)
    assert seen == {"x": 2}


def test_raising_pass_isolated(tmp_path, groups):
    def _raise(ctx):
        raise RuntimeError("kaput")
    groups["a"].insert(0, ("raiser", _raise))
    ctx = make_ctx(tmp_path)
    assert hk.execute(ctx, None) == 0
    row = _audit_rows(ctx)[0]
    assert row["ok"] is True
    assert row["passes"]["raiser"]["error"] == "RuntimeError: kaput"
    assert row["passes"]["good"]["error"] is None


def test_crashed_run_records_failed_row(tmp_path, groups, monkeypatch, capsys):
    _crash_report(monkeypatch)
    ctx = make_ctx(tmp_path)
    assert hk.execute(ctx, None) == 1
    row = _audit_rows(ctx)[0]
    assert row["ok"] is False
    assert row["error"] == "OSError: report unwritable"
    assert row["passes"]["good"]["error"] is None
    assert "run failed: OSError" in capsys.readouterr().err


def test_crash_outside_passes_records_failed_row(tmp_path, groups, monkeypatch):
    def _boom(ctx, groups):
        raise RuntimeError("no groups")
    monkeypatch.setattr(hk, "run_passes", _boom)
    ctx = make_ctx(tmp_path)
    assert hk.execute(ctx, None) == 1
    assert _audit_rows(ctx)[0] == {"ok": False, "passes": {}, "sizes": {},
                                   "error": "RuntimeError: no groups"}


def test_alert_on_second_failed_run_in_a_row_only(tmp_path, groups, monkeypatch):
    _crash_report(monkeypatch)
    ctx = make_ctx(tmp_path)
    _row(ctx, True, 14)
    hk.execute(ctx, None)
    assert _alerts(ctx) == 0
    hk.execute(ctx, None)
    assert _alerts(ctx) == 1
    hk.execute(ctx, None)
    assert _alerts(ctx) == 1


def test_ok_run_between_failures_resets_streak(tmp_path, groups, monkeypatch):
    ctx = make_ctx(tmp_path)
    _row(ctx, False, 14)
    _row(ctx, True, 7)
    _crash_report(monkeypatch)
    hk.execute(ctx, None)
    assert _alerts(ctx) == 0


def test_new_streak_after_ok_alerts_again(tmp_path, groups, monkeypatch):
    _crash_report(monkeypatch)
    ctx = make_ctx(tmp_path)
    conn = storage.connect(ctx.db)
    with conn:
        conn.execute(
            "INSERT INTO alerts (severity, type, fingerprint, message, resolved, "
            "created_at) VALUES ('warn', 'housekeep_failed', 'housekeep_failed', "
            "'old', 1, ?)",
            ((date.today() - timedelta(days=30)).isoformat() + "T02:00:00Z",))
    conn.close()
    _row(ctx, True, 14)
    _row(ctx, False, 7)
    hk.execute(ctx, None)
    assert _alerts(ctx) == 2


def test_only_run_never_alerts(tmp_path, groups, monkeypatch):
    _crash_report(monkeypatch)
    ctx = make_ctx(tmp_path)
    _row(ctx, False, 7)
    hk.execute(ctx, "a")
    assert _alerts(ctx) == 0
    assert _audit_rows(ctx)[-1]["only"] == ["a"]


def _tree_digest(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        h.update(str(p).encode())
        if p.is_file():
            h.update(p.read_bytes())
            h.update(str(p.stat().st_mtime_ns).encode())
    return h.hexdigest()


def test_dry_run_writes_nothing(tmp_path, capsys):
    from _housekeep_shared import FakeRun
    run = FakeRun()
    ctx = make_ctx(tmp_path, dry_run=True, run=run)
    (ctx.data_dir / "x.bak").write_text("b")
    (ctx.repos_root / "r" / "__pycache__").mkdir(parents=True)
    before = _tree_digest(tmp_path)
    assert hk.execute(ctx, None) == 0
    assert _tree_digest(tmp_path) == before
    assert not ctx.report_path.exists()
    assert set(run.calls) == {("brew", "upgrade", "-n"),
                              ("brew", "cleanup", "-n", "--prune=30"),
                              ("launchctl", "list")}
    out = capsys.readouterr().out
    assert "(dry-run)" in out and "would add" in out


def test_main_dry_run_uses_ctx(tmp_path, monkeypatch, groups, capsys):
    ctx = make_ctx(tmp_path, dry_run=True)
    seen = {}

    def _build(dry_run):
        seen["dry_run"] = dry_run
        return ctx
    monkeypatch.setattr(hk, "build_ctx", _build)
    assert hk.main(["--dry-run"]) == 0
    assert seen == {"dry_run": True}
    assert "good: items=1" in capsys.readouterr().out
    assert _audit_rows(ctx) == []


def test_install_boots_out_and_removes_aging(tmp_path, monkeypatch):
    from marrow import install
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "com.marrow.aging.plist").write_text("<plist/>")
    calls = []
    monkeypatch.setattr(install, "_LAUNCH_AGENTS", agents)
    monkeypatch.setattr(install, "_uid", lambda: "501")
    monkeypatch.setattr(install, "_launchctl",
                        lambda *a: calls.append(a) or (0, ""))
    monkeypatch.setattr(install, "_plist_gate_open", lambda label: True)
    assert install.install_plists() is True
    assert not (agents / "com.marrow.aging.plist").exists()
    assert ("bootout", "gui/501", str(agents / "com.marrow.aging.plist")) in calls
    rendered = (agents / "com.marrow.housekeep.plist").read_text()
    assert "marrow.housekeep" in rendered and "__" not in rendered
