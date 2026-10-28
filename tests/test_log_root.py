"""Every marrow log writer resolves under [log].dir."""
from __future__ import annotations

import logging
import plistlib

import pytest

from marrow import config


@pytest.fixture
def log_root(tmp_path, monkeypatch):
    root = tmp_path / "Logs"
    real = config.load

    def _load():
        cfg = real()
        cfg["log"] = {"dir": str(root), "keep_days": 9}
        return cfg

    monkeypatch.setattr(config, "load", _load)
    return root


def test_default_log_section():
    import tomllib
    with config._DEFAULT.open("rb") as f:
        log = tomllib.load(f)["log"]
    assert log == {"dir": "~/Library/Logs", "keep_days": 14}


def test_log_dir_mkdirs_service(log_root):
    d = config.log_dir("mw-x")
    assert d == log_root / "mw-x" and d.is_dir()
    assert config.log_keep_days() == 9


@pytest.mark.parametrize("mod,name,sub,fname", [
    ("watcher", "marrow.watcher", "mw-watcher", "watcher.log"),
    ("sensors", "marrow.sensors", "mw-sensors", "sensors.log"),
    ("embedd", "marrow.embedd", "mw-embedd", "embedd.log"),
])
def test_long_runner_file_only(log_root, mod, name, sub, fname):
    import importlib
    m = importlib.import_module(f"marrow.{mod}")
    lg = logging.getLogger(name)
    saved = lg.handlers[:]
    lg.handlers.clear()
    try:
        out = m._setup_logger() if mod == "watcher" else m._logger()
        assert len(out.handlers) == 1
        h = out.handlers[0]
        assert isinstance(h, logging.handlers.TimedRotatingFileHandler)
        assert h.baseFilename == str(log_root / sub / fname)
        assert h.backupCount == 9
        assert out.propagate is False
        rec = logging.LogRecord(name, logging.INFO, "", 0, "m", None, None)
        rec.created = 0
        assert h.format(rec) == "1970-01-01T00:00:00Z INFO m"
        h.close()
    finally:
        lg.handlers[:] = saved


def test_recall_log_dir(log_root):
    from marrow.hooks import state
    assert state._recall_log_dir() == log_root / "mw-recall"


def test_cadence_fail_log(log_root, monkeypatch):
    from marrow import schedule
    monkeypatch.setattr(schedule, "_fail_streak", 0)
    schedule._log_fail("rem", ["rem", "read"], 1, "boom")
    text = (log_root / "mw-jobs" / "cadence-fail.log").read_text()
    assert "kind=rem rc=1" in text


def test_rendered_plists_use_log_root(log_root, tmp_path, monkeypatch):
    from marrow import install
    monkeypatch.setattr(install, "_LAUNCH_AGENTS", tmp_path / "agents")
    monkeypatch.setattr(install, "_uid", lambda: "501")
    monkeypatch.setattr(install, "_launchctl", lambda *a: (0, ""))
    monkeypatch.setattr(install, "_plist_gate_open", lambda label: True)
    assert install.install_plists() is True
    expected = {
        "com.marrow.watcher": "mw-watcher/launchd.log",
        "com.marrow.embedd": "mw-embedd/launchd.log",
        "com.marrow.sensors": "mw-sensors/launchd.log",
        "com.marrow.db-backup": "mw-jobs/db-backup.log",
        "com.marrow.refresh": "mw-jobs/refresh.log",
        "com.marrow.housekeep": "mw-jobs/housekeep.log",
    }
    for label, rel in expected.items():
        spec = plistlib.loads((tmp_path / "agents" / f"{label}.plist").read_bytes())
        assert spec["StandardOutPath"] == str(log_root / rel)
        assert spec["StandardErrorPath"] == str(log_root / rel)
        assert (log_root / rel).parent.is_dir()


def test_cortex_watchdog_spawn_appends_to_cortex_log(tmp_path, monkeypatch):
    from marrow import cortex_bridge, cortex_cfg
    log = tmp_path / "cx" / "ct-wake-daemon" / "watchdog.log"
    monkeypatch.setattr(cortex_cfg, "watchdog_log", lambda: log)
    monkeypatch.setattr(cortex_bridge, "_cortex_watchdog_pidfile",
                        lambda: tmp_path / "state" / "watchdog.pid")
    monkeypatch.setattr(cortex_bridge, "_cortex_paths",
                        lambda: (str(tmp_path / "py"), str(tmp_path)))
    seen = {}

    class _Proc:
        pid = 4242

    def _popen(cmd, **kw):
        seen["stdout"] = kw["stdout"].name
        seen["stderr"] = kw["stderr"].name
        return _Proc()

    monkeypatch.setattr(cortex_bridge.subprocess, "Popen", _popen)
    cortex_bridge._spawn_watchdog_if_absent()
    assert seen == {"stdout": str(log), "stderr": str(log)}
    assert log.parent.is_dir()
    assert (tmp_path / "state" / "watchdog.pid").read_text() == "4242"
