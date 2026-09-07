"""marrow.cortex_cfg — cortex settings are read FROM cortex, never copied.

The cortex CLI is mocked everywhere: no real subprocess is ever spawned.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from marrow import config, cortex_cfg

pytestmark = pytest.mark.live_cortex_cfg

RESOLVED = """
[paths]
cortex_home = ""
wake_state_file = ""
watchdog_pidfile = ""

[wake]
spawn_opener_template = "[FAIRY]"
wake_bell_template = "[BELL]"
tuck_in_text = "[ROUND]"
next_wake_max = 360
next_wake_low_max = 55
next_wake_high_min = 120

[daemon]
shell = "cli"
socket_path = ""
kick_timeout_sec = 1.0
"""


class _Completed:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


@pytest.fixture
def cortex(monkeypatch, tmp_path):
    """cortex enabled + configured, with `cortex.ctl config --resolved` mocked."""
    calls: list[dict] = []

    def _run(cmd, **kw):
        calls.append({"cmd": list(cmd), "cwd": kw.get("cwd")})
        return _Completed(stdout=RESOLVED)

    monkeypatch.setattr(config, "load", lambda: {"cortex": {
        "enabled": True,
        "venv_python": str(tmp_path / "venv" / "bin" / "python"),
        "repo_root": str(tmp_path / "repo"),
        "home": str(tmp_path / "home"),
    }})
    monkeypatch.setattr(subprocess, "run", _run)
    cortex_cfg.reset()
    yield calls
    cortex_cfg.reset()


def test_reads_the_resolved_cortex_config(cortex):
    assert cortex_cfg.get("wake", "wake_bell_template") == "[BELL]"
    assert cortex_cfg.get("wake", "tuck_in_text") == "[ROUND]"
    assert cortex_cfg.get("wake", "next_wake_high_min") == 120


def test_invokes_the_cortex_cli_from_repo_root(cortex, tmp_path):
    cortex_cfg.load()
    assert cortex[0]["cmd"][1:] == ["-m", "cortex.ctl", "config", "--resolved"]
    assert cortex[0]["cmd"][0] == str(tmp_path / "venv" / "bin" / "python")
    assert cortex[0]["cwd"] == str(tmp_path / "repo")


def test_result_is_cached_for_the_process(cortex):
    cortex_cfg.load()
    cortex_cfg.load()
    cortex_cfg.get("wake", "wake_bell_template")
    assert len(cortex) == 1


def test_empty_path_resolves_under_cortex_home(cortex, tmp_path):
    assert cortex_cfg.path("wake_state_file") == tmp_path / "home" / "state" / "wake_state.json"
    assert cortex_cfg.path("watchdog_pidfile") == tmp_path / "home" / "state" / "watchdog.pid"


def test_explicit_path_wins(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "load", lambda: {"cortex": {
        "enabled": True, "venv_python": "py", "repo_root": ".", "home": "/nope"}})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed(
        stdout='[paths]\nwake_state_file = "/tmp/ws.json"\ncortex_home = ""\n'))
    cortex_cfg.reset()
    try:
        assert cortex_cfg.path("wake_state_file") == Path("/tmp/ws.json")
    finally:
        cortex_cfg.reset()


def test_cortex_home_from_cortex_config_wins_over_marrow(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "load", lambda: {"cortex": {
        "enabled": True, "venv_python": "py", "repo_root": ".",
        "home": str(tmp_path / "marrow-side")}})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed(
        stdout=f'[paths]\ncortex_home = "{tmp_path / "cortex-side"}"\n'))
    cortex_cfg.reset()
    try:
        assert cortex_cfg.home() == tmp_path / "cortex-side"
    finally:
        cortex_cfg.reset()


def test_disabled_cortex_raises(monkeypatch):
    monkeypatch.setattr(config, "load", lambda: {"cortex": {
        "enabled": False, "venv_python": "py", "repo_root": "."}})
    cortex_cfg.reset()
    with pytest.raises(cortex_cfg.CortexConfigError, match="disabled"):
        cortex_cfg.load()


def test_unconfigured_cortex_raises(monkeypatch):
    monkeypatch.setattr(config, "load", lambda: {"cortex": {
        "enabled": True, "venv_python": "", "repo_root": ""}})
    cortex_cfg.reset()
    with pytest.raises(cortex_cfg.CortexConfigError, match="not configured"):
        cortex_cfg.load()


def test_failed_command_raises_with_stderr(monkeypatch):
    monkeypatch.setattr(config, "load", lambda: {"cortex": {
        "enabled": True, "venv_python": "py", "repo_root": "."}})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed(
        stderr="boom", returncode=2))
    cortex_cfg.reset()
    with pytest.raises(cortex_cfg.CortexConfigError, match="boom"):
        cortex_cfg.load()


def test_launch_failure_raises(monkeypatch):
    monkeypatch.setattr(config, "load", lambda: {"cortex": {
        "enabled": True, "venv_python": "py", "repo_root": "."}})

    def _boom(*a, **k):
        raise OSError("no such file")

    monkeypatch.setattr(subprocess, "run", _boom)
    cortex_cfg.reset()
    with pytest.raises(cortex_cfg.CortexConfigError, match="no such file"):
        cortex_cfg.load()


def test_missing_key_raises_instead_of_inventing_a_value(cortex):
    with pytest.raises(cortex_cfg.CortexConfigError, match=r"\[wake\].nope"):
        cortex_cfg.get("wake", "nope")


def test_missing_key_with_explicit_default_returns_it(cortex):
    assert cortex_cfg.get("note", "shell_replay_exclude", None) is None
