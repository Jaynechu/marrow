"""housekeep measure passes: growth, launchd.log size, known items, launchd, disk."""
from __future__ import annotations

import plistlib
from datetime import date

from _housekeep_shared import FakeRun, make_ctx
from marrow.housekeep import measure

_MB = 1024 ** 2
_GB = 1024 ** 3


def _sparse(p, n):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        f.truncate(n)


def test_sizes_recorded_and_growth_threshold(tmp_path):
    ctx = make_ctx(tmp_path, hk={"measure_paths": ["~/.npm", "~/.cache/uv"]})
    _sparse(ctx.home / ".npm" / "big", 3 * _GB)
    _sparse(ctx.home / ".cache" / "uv" / "x", 1 * _GB)
    ctx.prev_sizes = {"~/.npm": 0, "~/.cache/uv": 0}
    r = measure.sizes(ctx)
    assert r["sizes"] == {"~/.npm": 3 * _GB, "~/.cache/uv": 1 * _GB}
    assert [t[:2] for t in r["todo"]] == [("growth", "~/.npm")]


def test_sizes_silent_without_previous_run(tmp_path):
    ctx = make_ctx(tmp_path, hk={"measure_paths": ["~/.npm"]})
    _sparse(ctx.home / ".npm" / "big", 3 * _GB)
    assert measure.sizes(ctx)["todo"] == []


def test_launchd_log_over_limit(tmp_path):
    ctx = make_ctx(tmp_path, hk={"measure_paths": []})
    _sparse(ctx.log_root / "mw-watcher" / "launchd.log", 11 * _MB)
    _sparse(ctx.log_root / "synapse-tg" / "launchd.log", 1 * _MB)
    _sparse(ctx.log_root / "other-app" / "launchd.log", 50 * _MB)
    todo = measure.sizes(ctx)["todo"]
    assert [t[1] for t in todo] == ["~/Library/Logs/mw-watcher/launchd.log"]


def test_known_seed_is_silent_then_new_logged_once(tmp_path):
    ctx = make_ctx(tmp_path)
    (ctx.data_dir / "config.toml").write_text("x")
    seed = measure.known(ctx)
    assert seed["items"] == 0 and "new" not in seed
    assert (ctx.hk_state / "known.json").exists()
    (ctx.data_dir / "stray.txt").write_text("hello")
    (ctx.log_root / "mw-newsvc").mkdir()
    first = measure.known(ctx)
    assert first["new"] == ["~/.config/marrow/stray.txt (5 B)",
                            "~/Library/Logs/mw-newsvc (0 B)"]
    assert first["todo"] == []
    assert measure.known(ctx)["new"] == []


def test_known_dry_run_does_not_seed(tmp_path):
    ctx = make_ctx(tmp_path, dry_run=True)
    measure.known(ctx)
    assert not (ctx.hk_state / "known.json").exists()


def test_unruled_growth_opens_at_threshold(tmp_path):
    ctx = make_ctx(tmp_path)
    blob = ctx.data_dir / "cortex" / "blob"
    _sparse(blob, 1 * _MB)
    _sparse(ctx.backup_root / "manual" / "b.db", 1 * _MB)
    measure.known(ctx)
    _sparse(blob, 100 * _MB)
    assert measure.known(ctx)["todo"] == []
    _sparse(blob, 101 * _MB)
    _sparse(ctx.backup_root / "manual" / "b.db", 900 * _MB)
    todo = measure.known(ctx)["todo"]
    assert [t[:2] for t in todo] == [("unruled-growth", "~/.config/marrow/cortex")]
    assert todo[0][2] == "~/.config/marrow/cortex 1.0 MB -> 101.0 MB"


def test_live_db_exempt_from_unruled_growth(tmp_path):
    ctx = make_ctx(tmp_path)
    measure.known(ctx)
    _sparse(ctx.data_dir / "marrow.db", 500 * _MB)
    assert measure.known(ctx)["todo"] == []


def test_known_rejects_unsafe_dir_entries(tmp_path):
    ctx = make_ctx(tmp_path, hk={"state_dirs": ["ok", "../x"]})
    r = measure.known(ctx)
    assert "state_dirs" in r["error"]
    assert not (ctx.hk_state / "known.json").exists()


def _plist(ctx, label, args, wd=None):
    spec = {"Label": label, "ProgramArguments": args}
    if wd:
        spec["WorkingDirectory"] = wd
    (ctx.launch_agents / f"{label}.plist").write_bytes(plistlib.dumps(spec))


def _py(tmp_path):
    py = tmp_path / "venv" / "python"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("")
    return str(py)


def test_launchd_missing_program_opens_at_once(tmp_path):
    ctx = make_ctx(tmp_path)
    _plist(ctx, "com.cortex.gone", ["/nope/python", "-m", "cortex.gone"])
    _plist(ctx, "com.apple.other", ["/nope/x"])
    todo = measure.launchd(ctx)["todo"]
    assert todo == [("launchd", "com.cortex.gone",
                     "com.cortex.gone: program missing /nope/python")]


def test_launchd_missing_module_opens_at_once(tmp_path):
    py = _py(tmp_path)
    run = FakeRun({(py, "-B", "-c"): lambda cmd: (1, "") if cmd[-1] == "cortex.pacemaker"
                   else (0, "")})
    ctx = make_ctx(tmp_path, run=run)
    _plist(ctx, "com.cortex.pacemaker-tick", [py, "-m", "cortex.pacemaker"])
    _plist(ctx, "com.marrow.watcher", [py, "-m", "marrow.watcher"])
    todo = measure.launchd(ctx)["todo"]
    assert todo == [("launchd", "com.cortex.pacemaker-tick",
                     "com.cortex.pacemaker-tick: module cortex.pacemaker not importable")]


def test_launchd_nonzero_exit_opens_on_second_run_only(tmp_path):
    py = _py(tmp_path)
    listing = ("PID\tStatus\tLabel\n-\t1\tcom.marrow.refresh\n"
               "123\t-15\tcom.marrow.embedd\n-\t0\tcom.marrow.watcher\n")
    run = FakeRun({("launchctl", "list"): (0, listing)})
    ctx = make_ctx(tmp_path, run=run)
    for label in ("com.marrow.refresh", "com.marrow.embedd", "com.marrow.watcher"):
        _plist(ctx, label, [py, "-m", "marrow.x"])
    assert measure.launchd(ctx)["todo"] == []
    todo = measure.launchd(ctx)["todo"]
    assert todo == [("launchd", "com.marrow.refresh exit",
                     "com.marrow.refresh: last exit 1 on 2 runs")]
    run.table[("launchctl", "list")] = (0, listing.replace("-\t1\t", "-\t0\t"))
    assert measure.launchd(ctx)["todo"] == []


def test_launchd_dry_run_keeps_watch_state(tmp_path):
    py = _py(tmp_path)
    run = FakeRun({("launchctl", "list"): (0, "-\t1\tcom.marrow.refresh\n")})
    ctx = make_ctx(tmp_path, run=run, dry_run=True)
    _plist(ctx, "com.marrow.refresh", [py, "-m", "marrow.x"])
    measure.launchd(ctx)
    assert not (ctx.hk_state / "watch.json").exists()


def test_disk_low_reported_once_until_recovered(tmp_path):
    low = make_ctx(tmp_path, free=10 * _GB)
    assert measure.disk(low)["todo"] == [
        ("disk", "free", "free disk 10.0 GB < 50 GB")]
    assert measure.disk(low)["todo"] == []
    ok = make_ctx(tmp_path, free=80 * _GB)
    assert measure.disk(ok)["todo"] == []
    assert len(measure.disk(low)["todo"]) == 1


def test_disk_size_lands_in_sizes(tmp_path):
    ctx = make_ctx(tmp_path, free=80 * _GB, today=date(2026, 10, 29))
    assert measure.disk(ctx)["sizes"] == {"disk_free": 80 * _GB}
