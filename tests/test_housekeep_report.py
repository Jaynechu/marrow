"""housekeep report file: keyed To do, auto-close, Log only on change, untouched otherwise."""
from __future__ import annotations

from datetime import date, timedelta

from _housekeep_shared import make_ctx
from marrow.housekeep import report, result


def _launchd(*labels):
    return {"launchd": result(todo=[("launchd", lb, f"{lb}: program missing /x")
                                     for lb in labels])}


def _ctx(tmp_path, day=0, **kw):
    return make_ctx(tmp_path, today=date(2026, 11, 1) + timedelta(days=day), **kw)


def test_first_run_creates_file_without_log_line(tmp_path):
    ctx = _ctx(tmp_path)
    rep = report.update(ctx, {"sizes": result(1)})
    assert rep["wrote"] and rep["line"] is None
    assert ctx.report_path.read_text() == "# Housekeep report\n\n## To do\n\n## Log\n"


def test_no_change_run_leaves_file_byte_identical(tmp_path):
    ctx = _ctx(tmp_path)
    report.update(ctx, _launchd("com.marrow.x"))
    before = ctx.report_path.read_bytes()
    mtime = ctx.report_path.stat().st_mtime_ns
    rep = report.update(_ctx(tmp_path, 7), _launchd("com.marrow.x"))
    assert rep == {"opened": [], "closed": [], "line": None, "wrote": False}
    assert ctx.report_path.read_bytes() == before
    assert ctx.report_path.stat().st_mtime_ns == mtime


def test_open_then_close_logs_once_each(tmp_path):
    report.update(_ctx(tmp_path), _launchd("com.marrow.x"))
    report.update(_ctx(tmp_path, 7), _launchd("com.marrow.x"))
    report.update(_ctx(tmp_path, 14), _launchd())
    report.update(_ctx(tmp_path, 21), _launchd())
    text = _ctx(tmp_path).report_path.read_text()
    assert text == (
        "# Housekeep report\n\n## To do\n\n## Log\n"
        "- 2026-11-15 closed: launchd com.marrow.x\n"
        "- 2026-11-01 opened: launchd com.marrow.x\n")


def test_open_item_line_format(tmp_path):
    ctx = _ctx(tmp_path)
    report.update(ctx, _launchd("com.cortex.gone"))
    lines = ctx.report_path.read_text().splitlines()
    assert "- [2026-11-01] launchd: com.cortex.gone: program missing /x" in lines


def test_failed_pass_opens_failed_item_and_logs_each_failed_run(tmp_path):
    bad = {"stray_bak": result(error="disk full")}
    report.update(_ctx(tmp_path), bad)
    rep = report.update(_ctx(tmp_path, 1), bad)
    assert rep["opened"] == [] and rep["line"] == "- 2026-11-02 failed: stray_bak"
    rep = report.update(_ctx(tmp_path, 2), {"stray_bak": result()})
    assert rep["closed"] == ["failed:stray_bak"]
    text = _ctx(tmp_path).report_path.read_text()
    assert "- 2026-11-01 opened: failed stray_bak; failed: stray_bak" in text


def test_items_of_passes_not_run_stay_open(tmp_path):
    report.update(_ctx(tmp_path), _launchd("com.marrow.x"))
    rep = report.update(_ctx(tmp_path, 1), {"repo_caches": result(3)})
    assert rep["closed"] == []
    assert "launchd: com.marrow.x" in _ctx(tmp_path).report_path.read_text()


def test_new_items_logged_but_never_todo(tmp_path):
    rep = report.update(_ctx(tmp_path), {"known": result(1, new=["~/x (5 B)"])})
    assert rep["line"] == "- 2026-11-01 new: ~/x (5 B)"
    assert "## To do\n\n## Log" in _ctx(tmp_path).report_path.read_text()


def test_health_error_not_duplicated_as_failed(tmp_path):
    r = result(error="health: import failed in synapse", error_reported=True,
               todo=[("health", "synapse", "synapse venv import failed")])
    rep = report.update(_ctx(tmp_path), {"brew": r})
    assert rep["opened"] == ["health:synapse"]


def test_log_capped(tmp_path):
    for d in range(5):
        report.update(_ctx(tmp_path, d, hk={"report_log_cap": 3}),
                      {"known": result(1, new=[f"~/n{d} (1 B)"])})
    log = _ctx(tmp_path).report_path.read_text().split("## Log\n")[1]
    assert log.splitlines() == ["- 2026-11-05 new: ~/n4 (1 B)",
                                "- 2026-11-04 new: ~/n3 (1 B)",
                                "- 2026-11-03 new: ~/n2 (1 B)"]


def test_dry_run_writes_neither_file_nor_state(tmp_path):
    ctx = _ctx(tmp_path, dry_run=True)
    rep = report.update(ctx, _launchd("com.marrow.x"))
    assert rep["opened"] == ["launchd:com.marrow.x"] and rep["wrote"]
    assert not ctx.report_path.exists()
    assert not (ctx.hk_state / "report.json").exists()
