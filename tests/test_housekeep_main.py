"""housekeep orchestration: due check, audit row, retry streak alert, dry-run."""
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


def _row(ctx, ok, days_ago, *, only=None):
    ts = (date.today() - timedelta(days=days_ago)).isoformat() + "T02:00:00Z"
    payload = {"ok": ok, "passes": {}, "sizes": {}}
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


def test_due_without_history(tmp_path):
    ctx = make_ctx(tmp_path)
    assert hk.is_due(ctx, hk.history(ctx))


def test_not_due_inside_interval_due_at_interval(tmp_path):
    ctx = make_ctx(tmp_path)
    _row(ctx, True, 6)
    assert not hk.is_due(ctx, hk.history(ctx))
    _row(ctx, True, 7)
    ctx2 = make_ctx(tmp_path, today=date.today() + timedelta(days=1))
    assert hk.is_due(ctx2, hk.history(ctx2))


def test_failed_run_keeps_job_due(tmp_path):
    ctx = make_ctx(tmp_path)
    _row(ctx, True, 10)
    _row(ctx, False, 1)
    assert hk.is_due(ctx, hk.history(ctx))


def test_partial_only_runs_ignored_by_due_check(tmp_path):
    ctx = make_ctx(tmp_path)
    _row(ctx, True, 1, only="files")
    assert hk.is_due(ctx, hk.history(ctx))


def test_not_due_run_does_nothing(tmp_path, groups, capsys):
    ctx = make_ctx(tmp_path)
    _row(ctx, True, 2)
    assert hk.execute(ctx, None, force=False) == 0
    assert "not due" in capsys.readouterr().out
    assert len(_audit_rows(ctx)) == 1


def test_apply_writes_one_audit_row(tmp_path, groups):
    ctx = make_ctx(tmp_path)
    groups["b"] = [("bad", _bad_pass)]
    assert hk.execute(ctx, None, force=False) == 1
    rows = _audit_rows(ctx)
    assert len(rows) == 1
    assert rows[0]["ok"] is False
    assert rows[0]["passes"]["good"] == {"items": 1, "bytes_freed": 0, "error": None}
    assert rows[0]["passes"]["bad"]["error"] == "boom"


def test_apply_writes_report_with_failed_item(tmp_path, groups):
    groups["b"] = [("bad", _bad_pass)]
    ctx = make_ctx(tmp_path)
    hk.execute(ctx, None, force=True)
    text = ctx.report_path.read_text()
    assert f"- [{date.today().isoformat()}] failed: bad: boom" in text


def test_raising_pass_isolated(tmp_path, groups):
    def _raise(ctx):
        raise RuntimeError("kaput")
    groups["a"].insert(0, ("raiser", _raise))
    ctx = make_ctx(tmp_path)
    hk.execute(ctx, None, force=True)
    row = _audit_rows(ctx)[0]
    assert row["passes"]["raiser"]["error"] == "RuntimeError: kaput"
    assert row["passes"]["good"]["error"] is None


def test_streak_alerts_once_on_third_failed_day(tmp_path, groups):
    groups["a"] = [("bad", _bad_pass)]
    ctx = make_ctx(tmp_path)
    _row(ctx, True, 20)
    _row(ctx, False, 2)
    assert _alerts(ctx) == 0
    hk.execute(ctx, None, force=True)
    assert _alerts(ctx) == 0
    _row(ctx, False, 1)
    hk.execute(ctx, None, force=True)
    assert _alerts(ctx) == 1
    hk.execute(ctx, None, force=True)
    assert _alerts(ctx) == 1


def test_streak_needs_distinct_days(tmp_path, groups):
    groups["a"] = [("bad", _bad_pass)]
    ctx = make_ctx(tmp_path)
    for _ in range(4):
        hk.execute(ctx, None, force=True)
    assert _alerts(ctx) == 0


def test_new_streak_after_ok_alerts_again(tmp_path, groups):
    groups["a"] = [("bad", _bad_pass)]
    ctx = make_ctx(tmp_path)
    conn = storage.connect(ctx.db)
    with conn:
        conn.execute(
            "INSERT INTO alerts (severity, type, fingerprint, message, resolved, "
            "created_at) VALUES ('warn', 'housekeep_failed', 'housekeep_failed', "
            "'old', 1, ?)",
            ((date.today() - timedelta(days=9)).isoformat() + "T02:00:00Z",))
    conn.close()
    _row(ctx, True, 8)
    _row(ctx, False, 2)
    _row(ctx, False, 1)
    hk.execute(ctx, None, force=True)
    assert _alerts(ctx) == 2


def test_only_run_never_alerts(tmp_path, groups):
    groups["a"] = [("bad", _bad_pass)]
    ctx = make_ctx(tmp_path)
    _row(ctx, False, 2)
    _row(ctx, False, 1)
    hk.execute(ctx, "a", force=True)
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
    assert hk.execute(ctx, None, force=True) == 0
    assert _tree_digest(tmp_path) == before
    assert not ctx.report_path.exists()
    assert set(run.calls) == {("brew", "upgrade", "-n"),
                              ("brew", "cleanup", "-n", "--prune=30"),
                              ("launchctl", "list")}
    out = capsys.readouterr().out
    assert "(dry-run)" in out and "would open" in out


def test_main_dry_run_uses_ctx(tmp_path, monkeypatch, groups, capsys):
    ctx = make_ctx(tmp_path, dry_run=True)
    seen = {}

    def _build(dry_run):
        seen["dry_run"] = dry_run
        return ctx
    monkeypatch.setattr(hk, "build_ctx", _build)
    assert hk.main(["--dry-run", "--force"]) == 0
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
