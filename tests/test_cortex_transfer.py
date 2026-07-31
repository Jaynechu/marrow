"""T4: the transfer MCP tool — registration, shell routing and its nudge."""
from __future__ import annotations

import io
import json

import pytest
from mcp.server.fastmcp import FastMCP

from marrow import config, cortex_bridge, hooks


def _fresh_mcp():
    m = FastMCP("t")

    def marrow_tool():
        return m.tool(meta={"anthropic/alwaysLoad": True})

    return m, marrow_tool


def _force_cortex(monkeypatch, **extra):
    real = config.load

    def _patched():
        cfg = dict(real())
        cx = dict(cfg.get("cortex", {}))
        cx["enabled"] = True
        cx.update(extra)
        cfg["cortex"] = cx
        return cfg

    monkeypatch.setattr(config, "load", _patched)


def _register_as(monkeypatch, shell_env, shells=None):
    extra = {} if shells is None else {"shells": shells}
    _force_cortex(monkeypatch, **extra)
    if shell_env is None:
        monkeypatch.delenv("MARROW_CORTEX", raising=False)
    else:
        monkeypatch.setenv("MARROW_CORTEX", shell_env)
    monkeypatch.setattr(cortex_bridge, "_CORTEX", shell_env is not None)
    m, mt = _fresh_mcp()
    cortex_bridge.register(mt)
    return m._tool_manager._tools


# --- registration -------------------------------------------------------------

def test_transfer_registers_for_every_listed_shell(monkeypatch):
    for shell in ("cli", "tg"):
        tools = _register_as(monkeypatch, shell, shells=["cli", "tg"])
        assert "transfer" in tools


def test_transfer_absent_outside_a_cortex_session(monkeypatch):
    assert "transfer" not in _register_as(monkeypatch, None)


def test_transfer_absent_for_a_shell_off_the_list(monkeypatch):
    assert "transfer" not in _register_as(monkeypatch, "tg", shells=["cli"])


def test_transfer_absent_when_cortex_is_disabled(monkeypatch):
    real = config.load
    monkeypatch.setattr(config, "load", lambda: {
        **real(), "cortex": {"enabled": False, "shells": ["cli"]}})
    monkeypatch.setenv("MARROW_CORTEX", "cli")
    monkeypatch.setattr(cortex_bridge, "_CORTEX", True)
    m, mt = _fresh_mcp()
    cortex_bridge.register(mt)
    assert "transfer" not in m._tool_manager._tools


def test_registered_description_is_the_contract_copy(monkeypatch):
    tools = _register_as(monkeypatch, "cli", shells=["cli", "tg"])
    assert tools["transfer"].description == (
        "transfer(): transfer between cortex shells (cli<->tg) - hold current "
        "one and kick the other. Update handoff first.")


def test_transfer_takes_no_arguments(monkeypatch):
    tools = _register_as(monkeypatch, "cli", shells=["cli", "tg"])
    assert tools["transfer"].parameters.get("properties", {}) == {}


# --- routing ------------------------------------------------------------------

@pytest.fixture
def calls(monkeypatch):
    seen = []

    def _run(module, extra_args=None):
        seen.append((module, list(extra_args or [])))
        return {"ok": True, "stdout": json.dumps(
            {"ok": True, "shell": "cli", "target": "tg", "hold": "cli"})}

    monkeypatch.setattr(cortex_bridge, "_run_cortex_module", _run)
    return seen


def test_cli_caller_transfers_from_cli(monkeypatch, calls):
    monkeypatch.setenv("MARROW_CORTEX", "cli")
    out = cortex_bridge.transfer()
    assert calls == [("cortex.duty", ["--transfer", "cli"])]
    assert out["ok"] is True and out["target"] == "tg"


def test_legacy_marker_transfers_from_cli(monkeypatch, calls):
    monkeypatch.setenv("MARROW_CORTEX", "1")
    cortex_bridge.transfer()
    assert calls == [("cortex.duty", ["--transfer", "cli"])]


def test_tg_caller_transfers_from_tg(monkeypatch, calls):
    monkeypatch.setenv("MARROW_CORTEX", "tg")
    cortex_bridge.transfer()
    assert calls == [("cortex.duty", ["--transfer", "tg"])]


def test_bad_shell_id_never_reaches_cortex(monkeypatch, calls):
    monkeypatch.setenv("MARROW_CORTEX", "not a shell")
    monkeypatch.setattr(cortex_bridge, "_warn_bad_shell_id", lambda v: None)
    out = cortex_bridge.transfer()
    assert out["ok"] is False and calls == []


def test_refusal_payload_is_surfaced(monkeypatch):
    monkeypatch.setenv("MARROW_CORTEX", "cli")
    monkeypatch.setattr(cortex_bridge, "_run_cortex_module", lambda *a, **k: {
        "ok": True, "stdout": json.dumps({"ok": False, "error": "breaker held"})})
    assert cortex_bridge.transfer() == {"ok": False, "error": "breaker held"}


def test_unparseable_stdout_leaves_the_subprocess_result(monkeypatch):
    monkeypatch.setenv("MARROW_CORTEX", "cli")
    monkeypatch.setattr(cortex_bridge, "_run_cortex_module", lambda *a, **k: {
        "ok": True, "stdout": "not json"})
    assert cortex_bridge.transfer() == {"ok": True, "stdout": "not json"}


def test_launch_failure_is_surfaced(monkeypatch):
    monkeypatch.setenv("MARROW_CORTEX", "cli")
    monkeypatch.setattr(cortex_bridge, "_run_cortex_module", lambda *a, **k: {
        "ok": False, "error": "cortex not configured"})
    assert cortex_bridge.transfer()["ok"] is False


# --- nudge --------------------------------------------------------------------

def _stdin(monkeypatch, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))


def test_nudge_renders_the_handoff_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARROW_CORTEX", "cli")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    _force_cortex(monkeypatch, home=str(tmp_path / "cortex"))
    _stdin(monkeypatch, {"tool_name": "mcp__marrow__transfer", "tool_input": {}})
    assert hooks.main(["pretool_use"]) == 0
    hso = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    handoff = str(tmp_path / "cortex" / "handoff.md")
    assert hso["additionalContext"] == (
        f"Update {handoff} before transfer. Add todo if any.")
    assert "permissionDecision" not in hso


def test_nudge_default_matches_config(monkeypatch):
    monkeypatch.setenv("MARROW_CORTEX", "cli")
    assert (config.load()["cortex"]["transfer_nudge_text"]
            == cortex_bridge._DEFAULT_TRANSFER_NUDGE)


def test_blank_override_silences_the_nudge(monkeypatch):
    monkeypatch.setenv("MARROW_CORTEX", "cli")
    _force_cortex(monkeypatch, transfer_nudge_text="")
    inp = {"tool_name": "mcp__marrow__transfer", "tool_input": {}}
    assert cortex_bridge._cortex_transfer_nudge(inp) is None


def test_nudge_ignores_other_tools(monkeypatch):
    monkeypatch.setenv("MARROW_CORTEX", "cli")
    _force_cortex(monkeypatch)
    assert cortex_bridge._cortex_transfer_nudge(
        {"tool_name": "mcp__marrow__lie_down", "tool_input": {}}) is None


def test_nudge_silent_outside_a_cortex_shell(monkeypatch):
    monkeypatch.delenv("MARROW_CORTEX", raising=False)
    _force_cortex(monkeypatch)
    assert cortex_bridge._cortex_transfer_nudge(
        {"tool_name": "mcp__marrow__transfer", "tool_input": {}}) is None
