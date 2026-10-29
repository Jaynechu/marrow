"""housekeep brew/uv/cache passes — every subprocess goes through FakeRun."""
from __future__ import annotations

from datetime import date

from _housekeep_shared import FakeRun, make_ctx
from marrow.housekeep import brew

_UP_N = ("✔︎ Bottle Manifest python@3.13 (3.13.18)\n"
         "==> Would upgrade 2 outdated packages:\n"
         "python@3.13 3.13.13_1 -> 3.13.14\nripgrep 14.1 -> 14.2\n")
_CLEAN_N = ("Would remove: /opt/homebrew/Cellar/ripgrep/14.0 (10 files, 4MB)\n"
            "This operation would free approximately 4MB of disk space.\n")
_PINNED_HIT = "Would remove: /opt/homebrew/Cellar/python@3.13/3.13.12 (3k files)\n"
_WRITES = {"pin", "update", "upgrade", "cleanup"}
_PYS = (0, "python@3.13 3.13.13_1\npython@3.14 3.14.6")


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
    run = FakeRun({("brew", "cleanup", "-n"): (0, _CLEAN_N),
                   ("brew", "list", "--formula"): _PYS})
    r = brew.brew(make_ctx(tmp_path, run=run))
    assert r["error"] is None
    seq = [c[:2] for c in _brew_writes(run.calls)]
    assert seq == [("brew", "pin"), ("brew", "pin"), ("brew", "update"),
                   ("brew", "upgrade"), ("brew", "cleanup")]
    assert ("brew", "cleanup", "--prune=30") in run.calls


def test_pin_failure_aborts_before_upgrade(tmp_path):
    run = FakeRun({("brew", "pin", "python@3.13"): (1, "Error: No such keg"),
                   ("brew", "list", "--formula"): _PYS})
    r = brew.brew(make_ctx(tmp_path, run=run))
    assert r["error"] == "brew pin python@3.13: Error: No such keg"
    assert not any(c[:2] == ("brew", "upgrade") for c in run.calls)


def test_pin_skips_formula_not_installed(tmp_path):
    run = FakeRun({("brew", "list", "--formula"): (0, "python@3.14 3.14.6")})
    r = brew.brew(make_ctx(tmp_path, run=run))
    assert r["error"] is None
    pins = [c for c in run.calls if c[:2] == ("brew", "pin")]
    assert pins == [("brew", "pin", "python@3.14")]


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
    assert not any(c[1:3] == ("-B", "-c") for c in run.calls)


def test_change_runs_health_and_reports_failure(tmp_path):
    ctx = make_ctx(tmp_path)
    syn_py = str(ctx.repos_root / "synapse" / ".venv" / "bin" / "python")
    run = FakeRun({("brew", "list"): _changing_versions(),
                   (syn_py,): (1, "ModuleNotFoundError")})
    ctx.run = run
    r = brew.brew(ctx)
    probes = [c for c in run.calls if c[1:3] == ("-B", "-c")]
    assert {c[3] for c in probes} == {"import marrow", "import synapse_core",
                                      "import cortex"}
    assert r["error"] == "health: import failed in synapse"
    assert r["todo"] == [("health", "synapse",
                          "synapse venv import failed after brew upgrade")]
    assert not any(c[:2] == ("launchctl", "kickstart") for c in run.calls)


def test_step_failure_is_pass_error(tmp_path):
    run = FakeRun({("uv", "cache", "prune"): (2, "boom")})
    r = brew.uv(make_ctx(tmp_path, run=run))
    assert r["error"] == "uv cache prune: boom"


_NPM_FAIL = (
    "npm warn using --force Recommended protections disabled.\n"
    "npm error code ENOTEMPTY\n"
    "npm error syscall rmdir\n"
    "npm error path /Users/x/.npm/_cacache/index-v5/3f\n"
    "npm error errno -66\n"
    "npm error\n"
    "npm error A complete log of this run can be found in: "
    "/Users/x/.npm/_logs/2026-10-29T01_12_41_800Z-debug-0.log\n")


def test_npm_failure_keeps_first_real_error_line(tmp_path):
    run = FakeRun({("npm", "cache", "clean"): (1, _NPM_FAIL)})
    r = brew.npm(make_ctx(tmp_path, run=run))
    assert r["error"] == "npm cache clean --force: npm error code ENOTEMPTY"


def test_err_falls_back_to_last_non_noise_line():
    out = "step one\nstep two\nnpm error\n"
    assert brew._err("x", out)["error"] == "x: step two"
    assert brew._err("x", "npm error\n")["error"] == "x: failed"


def test_runner_disables_brew_auto_update_and_cleanup(monkeypatch):
    import subprocess

    from marrow import housekeep
    seen = {}

    def _fake(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, "ok", "")
    monkeypatch.setattr(housekeep.subprocess, "run", _fake)
    assert housekeep.make_runner(5)(["brew", "upgrade"]) == (0, "ok")
    assert seen["env"]["HOMEBREW_NO_AUTO_UPDATE"] == "1"
    assert seen["env"]["HOMEBREW_NO_INSTALL_CLEANUP"] == "1"
    assert seen["timeout"] == 5


def test_python_eol_window(tmp_path):
    ctx = make_ctx(tmp_path, today=date(2029, 6, 1))
    r = brew.python_eol(ctx)
    assert r["todo"] == [("python-eol", "python@3.13", "python@3.13 EOL 2029-10-31")]
    assert brew.python_eol(make_ctx(tmp_path, today=date(2026, 10, 29)))["todo"] == []


def _open_health(ctx, *repos):
    from marrow.housekeep import write_json
    write_json(ctx.hk_state / "report.json", {"log": [], "items": {
        f"health:{r}": {"kind": "health", "detail": "x", "owner": "brew",
                        "date": "2026-10-01"} for r in repos}})


def test_open_health_item_reprobes_without_brew_change(tmp_path):
    ctx = make_ctx(tmp_path)
    _open_health(ctx, "synapse")
    syn_py = str(ctx.repos_root / "synapse" / ".venv" / "bin" / "python")
    ctx.run = FakeRun({(syn_py,): (1, "ModuleNotFoundError")})
    r = brew.brew(ctx)
    assert r["error"] == "health: import failed in synapse"
    assert [t[:2] for t in r["todo"]] == [("health", "synapse")]


def test_open_health_item_passing_probe_clears(tmp_path):
    ctx = make_ctx(tmp_path)
    _open_health(ctx, "synapse")
    run = FakeRun()
    ctx.run = run
    r = brew.brew(ctx)
    assert r["error"] is None and not r.get("todo")
    assert any(c[1:3] == ("-B", "-c") for c in run.calls)


def test_step_failure_still_probes_open_health(tmp_path):
    ctx = make_ctx(tmp_path)
    _open_health(ctx, "synapse")
    syn_py = str(ctx.repos_root / "synapse" / ".venv" / "bin" / "python")
    ctx.run = FakeRun({("brew", "update"): (1, "network down"),
                       (syn_py,): (1, "ModuleNotFoundError")})
    r = brew.brew(ctx)
    assert r["error"].startswith("brew update: network down")
    assert "health: import failed in synapse" in r["error"]
    assert not r.get("error_reported")
    assert [t[:2] for t in r["todo"]] == [("health", "synapse")]
