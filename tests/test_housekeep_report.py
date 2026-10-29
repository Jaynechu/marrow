"""housekeep report file: append-only new findings, hand edits never rewritten."""
from __future__ import annotations

from datetime import date, timedelta

from _housekeep_shared import make_ctx
from marrow.housekeep import report, result


def _launchd(*labels):
    return {"launchd": result(todo=[("launchd", lb, f"{lb}: program missing /x")
                                     for lb in labels])}


def _ctx(tmp_path, day=0, **kw):
    return make_ctx(tmp_path, today=date(2026, 11, 1) + timedelta(days=day), **kw)


def test_nothing_found_writes_no_file(tmp_path):
    ctx = _ctx(tmp_path)
    assert report.update(ctx, {"sizes": result(1)}) == []
    assert not ctx.report_path.exists()


def test_first_findings_create_file(tmp_path):
    ctx = _ctx(tmp_path)
    added = report.update(ctx, _launchd("com.marrow.x"))
    assert added == ["launchd: com.marrow.x: program missing /x"]
    assert ctx.report_path.read_text() == (
        "# Housekeep report\n\n## 2026-11-01\n"
        "- launchd: com.marrow.x: program missing /x\n")


def test_persisting_finding_not_duplicated(tmp_path):
    ctx = _ctx(tmp_path)
    report.update(ctx, _launchd("com.marrow.x"))
    before = ctx.report_path.read_bytes()
    mtime = ctx.report_path.stat().st_mtime_ns
    assert report.update(_ctx(tmp_path, 7), _launchd("com.marrow.x")) == []
    assert ctx.report_path.read_bytes() == before
    assert ctx.report_path.stat().st_mtime_ns == mtime


def test_new_run_appends_only_new_findings(tmp_path):
    report.update(_ctx(tmp_path), _launchd("com.marrow.x"))
    report.update(_ctx(tmp_path, 7), _launchd("com.marrow.x", "com.marrow.y"))
    assert _ctx(tmp_path).report_path.read_text() == (
        "# Housekeep report\n\n## 2026-11-01\n"
        "- launchd: com.marrow.x: program missing /x\n"
        "\n## 2026-11-08\n"
        "- launchd: com.marrow.y: program missing /x\n")


def test_hand_edits_kept_and_deleted_finding_comes_back(tmp_path):
    ctx = _ctx(tmp_path)
    report.update(ctx, _launchd("com.marrow.x", "com.marrow.y"))
    edited = "# Mine\n- launchd: com.marrow.y: program missing /x (handling)"
    ctx.report_path.write_text(edited)
    added = report.update(_ctx(tmp_path, 7), _launchd("com.marrow.x",
                                                      "com.marrow.y"))
    assert added == ["launchd: com.marrow.x: program missing /x"]
    assert ctx.report_path.read_text() == (
        edited + "\n\n## 2026-11-08\n"
        "- launchd: com.marrow.x: program missing /x\n")


def test_failed_and_new_are_findings(tmp_path):
    added = report.update(_ctx(tmp_path), {
        "npm": result(error="npm cache clean --force: npm error code EACCES"),
        "known": result(1, new=["~/x (5 B)"])})
    assert added == ["failed: npm: npm cache clean --force: npm error code EACCES",
                     "new: ~/x (5 B)"]


def test_health_error_not_duplicated_as_failed(tmp_path):
    r = result(error="health: import failed in synapse", error_reported=True,
               todo=[("health", "synapse", "synapse venv import failed")])
    assert report.update(_ctx(tmp_path), {"brew": r}) == [
        "health: synapse venv import failed"]


def test_dry_run_writes_nothing(tmp_path):
    ctx = _ctx(tmp_path, dry_run=True)
    assert report.update(ctx, _launchd("com.marrow.x")) == [
        "launchd: com.marrow.x: program missing /x"]
    assert not ctx.report_path.exists()
