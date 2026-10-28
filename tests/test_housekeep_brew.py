"""housekeep brew/uv/cache passes — every subprocess goes through FakeRun."""
from __future__ import annotations

from datetime import date

from _housekeep_shared import FakeRun, make_ctx
from marrow.housekeep import brew

_UP_N = ("==> Would upgrade 2 outdated packages:\n"
         "python@3.13 3.13.13_1 -> 3.13.14\nripgrep 14.1 -> 14.2\n")
_CLEAN_N = ("Would remove: /opt/homebrew/Cellar/ripgrep/14.0 (10 files, 4MB)\n"
            "This operation would free approximately 4MB of disk space.\n")
_PINNED_HIT = "Would remove: /opt/homebrew/Cellar/python@3.13/3.13.12 (3k files)\n"
_WRITES = {"pin", "update", "upgrade", "cleanup"}


def _brew_writes(calls):
    return [c for c in calls if c[0] == "brew" and c[1] in _WRITES
            and "-n" not in c]


def test_dry_run_reads_plan_only(tmp_path):
    run = FakeRun({("brew", "upgrade", "-n"): (0, _UP_N),
                   ("brew", "cleanup", "-n"): (0, _CLEAN_N)})
    ctx = make_ctx(tmp_path, dry_run=True, run=run)
    r = brew.brew(ctx)
    assert r["error"] is None
    assert _brew_writes(run.calls) == []
    assert "upgrade: ripgrep 14.1 -> 14.2" in r["lines"]
    assert not any("python@3.13 3.13" in ln for ln in r["lines"])
    assert any("Cellar/ripgrep/14.0" in ln for ln in r["lines"])
    assert r["items"] == 2


def test_dry_run_flags_pinned_cellar_in_cleanup(tmp_path):
    run = FakeRun({("brew", "cleanup", "-n"): (0, _PINNED_HIT)})
    r = brew.brew(make_ctx(tmp_path, dry_run=True, run=run))
    assert r["error"] and "pinned Cellar" in r["error"]


def test_dry_run_other_steps_run_nothing(tmp_path):
    run = FakeRun()
    ctx = make_ctx(tmp_path, dry_run=True, run=run)
    for fn in (brew.uv, brew.pip, brew.npm):
        assert fn(ctx)["lines"][0].startswith("would run: ")
    assert run.calls == []


def test_apply_order_pins_first(tmp_path):
    run = FakeRun({("brew", "cleanup", "-n"): (0, _CLEAN_N)})
    r = brew.brew(make_ctx(tmp_path, run=run))
    assert r["error"] is None
    seq = [c[:2] for c in _brew_writes(run.calls)]
    assert seq == [("brew", "pin"), ("brew", "pin"), ("brew", "update"),
                   ("brew", "upgrade"), ("brew", "cleanup")]
    assert ("brew", "cleanup", "--prune=30") in run.calls


def test_pin_failure_aborts_before_upgrade(tmp_path):
    run = FakeRun({("brew", "pin", "python@3.13"): (1, "Error: No such keg")})
    r = brew.brew(make_ctx(tmp_path, run=run))
    assert r["error"] == "brew pin python@3.13: Error: No such keg"
    assert not any(c[:2] == ("brew", "upgrade") for c in run.calls)


def test_cleanup_skipped_when_plan_names_pinned(tmp_path):
    run = FakeRun({("brew", "cleanup", "-n"): (0, _PINNED_HIT)})
    r = brew.brew(make_ctx(tmp_path, run=run))
    assert "cleanup skipped" in r["error"]
    assert ("brew", "cleanup", "--prune=30") not in run.calls


def _changing_versions():
    state = {"n": 0}

    def ans(cmd):
        state["n"] += 1
        return 0, f"ripgrep 14.{state['n']}"
    return ans


def test_no_change_skips_health(tmp_path):
    run = FakeRun()
    r = brew.brew(make_ctx(tmp_path, run=run))
    assert r["error"] is None
    assert not any(c[1:2] == ("-c",) for c in run.calls)


def test_change_runs_health_and_reports_failure(tmp_path):
    ctx = make_ctx(tmp_path)
    syn_py = str(ctx.repos_root / "synapse" / ".venv" / "bin" / "python")
    run = FakeRun({("brew", "list"): _changing_versions(),
                   (syn_py,): (1, "ModuleNotFoundError")})
    ctx.run = run
    r = brew.brew(ctx)
    probes = [c for c in run.calls if c[1:2] == ("-c",)]
    assert {c[2] for c in probes} == {"import marrow", "import synapse_core",
                                      "import cortex"}
    assert r["error"] == "health: import failed in synapse"
    assert r["todo"] == [("health", "synapse",
                          "synapse venv import failed after brew upgrade")]
    assert not any(c[:2] == ("launchctl", "kickstart") for c in run.calls)


def test_step_failure_is_pass_error(tmp_path):
    run = FakeRun({("uv", "cache", "prune"): (2, "boom")})
    r = brew.uv(make_ctx(tmp_path, run=run))
    assert r["error"] == "uv cache prune: boom"


def test_python_eol_window(tmp_path):
    ctx = make_ctx(tmp_path, today=date(2029, 6, 1))
    r = brew.python_eol(ctx)
    assert r["todo"] == [("python-eol", "python@3.13", "python@3.13 EOL 2029-10-31")]
    assert brew.python_eol(make_ctx(tmp_path, today=date(2026, 10, 29)))["todo"] == []
