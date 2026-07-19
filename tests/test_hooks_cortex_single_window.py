"""Single-active-window registration + gate (P14 Fix 3): cortex_claude_sid is a
SEPARATE registration key from wake_state's session_id/transcript (iTerm
liveness — untouched by this suite). Covers the CAS registration primitives,
the PreToolUse gate + /ct-wake takeover claim, and the UserPromptSubmit
wake-branch early-return / deathbed-turn / handoff-landed notify.
"""
from __future__ import annotations

import io
import json

import pytest

from marrow import config, cortex_bridge, hooks


def _stdin(monkeypatch, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))


def _ctx(capsys):
    out = capsys.readouterr().out
    if not out.strip():
        return ""
    return json.loads(out)["hookSpecificOutput"].get("additionalContext", "")


def _hso(capsys):
    out = capsys.readouterr().out
    if not out.strip():
        return {}
    return json.loads(out)["hookSpecificOutput"]


@pytest.fixture()
def cortex_env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    py = tmp_path / "venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("")
    root = tmp_path / "repo"
    root.mkdir()
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(config, "db_path", lambda: db)
    monkeypatch.setattr(config, "load", lambda: {
        "cortex": {
            "enabled": True, "home": str(home),
            "venv_python": str(py), "repo_root": str(root),
            "wake_state_file": "wake_state.json",
            "watchdog_pidfile": "watchdog.pid",
            "tuck_in_marker": "[TUCK-IN]",
            "machine_markers": ["[NEW ROUND]", "[TUCK-IN]",
                                "[NIGHT]", "[FUSE]", "[CTL]", "[CMD"],
            "compact_markers": ["===== BEGIN ORIGINAL TRANSCRIPT",
                                "===== END ORIGINAL TRANSCRIPT"],
            "compact_marker_head_chars": 200,
            "wake_audit_log_file": "wake_audit.log",
            "handoff_file": "handoff.md",
            "wake_signal_log_file": "state/wake_signal.log",
            "takeover_text": "⚙️ [RETIRED] A new cortex window has taken over "
                             "(sid {new_sid}). Retire now.",
            "handoff_landed_text": "previous window handoff landed",
        },
        "outbox": {"inject_header": "📮 Message from {channel}·{sid4} {time}"},
        "recall": {"exclude_cwds": []},
        "replay": {"enabled": False},
    })
    monkeypatch.setenv("MARROW_CORTEX", "1")
    monkeypatch.setattr(cortex_bridge, "_spawn_watchdog_if_absent", lambda: None)
    return home, db


def _ws(home):
    p = home / "wake_state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _write_ws(home, **fields):
    (home / "wake_state.json").write_text(json.dumps(fields))


def _jsonl(tmp_path, name):
    p = tmp_path / f"{name}.jsonl"
    p.write_text("")
    return str(p)


# --- registration primitives (cortex_bridge helpers) --------------------------

def test_is_registered_window_no_registration_is_tolerant(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "abc")
    assert cortex_bridge.is_registered_window(tpath) is True


def test_is_registered_window_matches_registered_sid(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "abc")
    _write_ws(home, cortex_claude_sid="abc")
    assert cortex_bridge.is_registered_window(tpath) is True


def test_is_registered_window_mismatch_is_false(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "abc")
    _write_ws(home, cortex_claude_sid="other-sid")
    assert cortex_bridge.is_registered_window(tpath) is False


def test_claim_registration_if_pending_succeeds_with_current_token(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "newsid")
    _write_ws(home, gen=5, state_id="cafe", cortex_registration_pending=True)
    ok = cortex_bridge.claim_registration_if_pending(tpath, (5, "cafe"))
    assert ok is True
    d = _ws(home)
    assert d["cortex_claude_sid"] == "newsid"
    assert "cortex_registration_pending" not in d
    assert "cortex_registered_at" in d


def test_claim_registration_if_pending_fails_stale_token(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "newsid")
    _write_ws(home, gen=5, state_id="cafe", cortex_registration_pending=True)
    ok = cortex_bridge.claim_registration_if_pending(tpath, (4, "cafe"))
    assert ok is False
    assert "cortex_claude_sid" not in _ws(home)


def test_claim_registration_if_pending_fails_when_not_pending(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "newsid")
    _write_ws(home, gen=5, state_id="cafe")  # no pending flag
    ok = cortex_bridge.claim_registration_if_pending(tpath, (5, "cafe"))
    assert ok is False
    assert "cortex_claude_sid" not in _ws(home)


def test_claim_registration_takeover_unconditional_overwrite(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "newwindow")
    _write_ws(home, cortex_claude_sid="oldwindow")
    ok = cortex_bridge.claim_registration_takeover(tpath)
    assert ok is True
    d = _ws(home)
    assert d["cortex_claude_sid"] == "newwindow"
    assert "cortex_registered_at" in d


def test_claim_registration_takeover_noop_when_already_self(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "samewindow")
    _write_ws(home, cortex_claude_sid="samewindow", cortex_registered_at="2020-01-01T00:00:00+00:00")
    ok = cortex_bridge.claim_registration_takeover(tpath)
    assert ok is True
    d = _ws(home)
    # Already-self is a no-op — the registered_at stamp is untouched.
    assert d["cortex_registered_at"] == "2020-01-01T00:00:00+00:00"


def test_takeover_text_renders_new_sid(cortex_env):
    text = cortex_bridge.takeover_text("abcdef1234567890")
    assert text is not None
    assert "abcdef12" in text  # first 8 chars


def test_handoff_written_since_takeover_false_without_stamp(cortex_env):
    assert cortex_bridge.handoff_written_since_takeover() is False


def test_handoff_written_since_takeover_true_after_touch(cortex_env):
    home, _ = cortex_env
    from datetime import datetime, timedelta, timezone
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    _write_ws(home, cortex_registered_at=past)
    (home / "handoff.md").write_text("## window section\ncontent")
    assert cortex_bridge.handoff_written_since_takeover() is True


def test_handoff_written_since_takeover_false_when_stale(cortex_env):
    """A handoff written BEFORE the takeover stamp does not count (must be
    touched at/after the takeover, not merely exist)."""
    home, _ = cortex_env
    from datetime import datetime, timedelta, timezone
    (home / "handoff.md").write_text("stale content")
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    _write_ws(home, cortex_registered_at=future)
    assert cortex_bridge.handoff_written_since_takeover() is False


def test_notify_handoff_landed_once_is_one_shot(cortex_env, monkeypatch):
    home, db = cortex_env
    from datetime import datetime, timedelta, timezone
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    _write_ws(home, cortex_registered_at=past)
    sent = []
    from marrow import outbox as _outbox
    monkeypatch.setattr(_outbox, "send", lambda *a, **k: sent.append((a, k)) or {"ok": True})
    cortex_bridge.notify_handoff_landed_once()
    cortex_bridge.notify_handoff_landed_once()
    assert len(sent) == 1  # second call is a no-op (same registered_at stamp)


# --- PreToolUse gate: cortex_gate_pretool --------------------------------------

def test_gate_allows_registered_window(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "reg")
    _write_ws(home, cortex_claude_sid="reg")
    inp = {"transcript_path": tpath, "tool_name": "mcp__marrow__lie_down",
           "tool_input": {}}
    assert cortex_bridge.cortex_gate_pretool(inp) is None


def test_gate_denies_retired_window_liveness_tool(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "retired")
    _write_ws(home, cortex_claude_sid="registered-one")
    for tool in ("Monitor", "ScheduleWakeup", "mcp__marrow__lie_down",
                 "mcp__marrow__wait", "mcp__marrow__msg", "mcp__marrow__say"):
        inp = {"transcript_path": tpath, "tool_name": tool, "tool_input": {}}
        reason = cortex_bridge.cortex_gate_pretool(inp)
        assert reason, f"{tool} should be denied for a retired window"


def test_gate_allows_read_write_for_retired_window(cortex_env, tmp_path):
    """Read/Write stay allowed — the deathbed handoff write must go through."""
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "retired")
    _write_ws(home, cortex_claude_sid="registered-one")
    for tool in ("Read", "Write"):
        inp = {"transcript_path": tpath, "tool_name": tool, "tool_input": {}}
        assert cortex_bridge.cortex_gate_pretool(inp) is None


def test_gate_denies_bash_invoking_cortex_module(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "retired")
    _write_ws(home, cortex_claude_sid="registered-one")
    inp = {"transcript_path": tpath, "tool_name": "Bash",
           "tool_input": {"command": "/venv/bin/python -m cortex.lie_down --next-wake-min 30"}}
    assert cortex_bridge.cortex_gate_pretool(inp)


def test_gate_allows_ctl_wake_bash_exception(cortex_env, tmp_path):
    """The narrow /ct-wake exception: a retired window's ctl-wake Bash call is
    NOT denied here (it claims takeover upstream in PreToolUse first)."""
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "retired")
    _write_ws(home, cortex_claude_sid="registered-one")
    inp = {"transcript_path": tpath, "tool_name": "Bash",
           "tool_input": {"command": "/venv/bin/python -m cortex.ctl wake"}}
    assert cortex_bridge.cortex_gate_pretool(inp) is None


def test_gate_deny_reason_is_takeover_text(cortex_env, tmp_path):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "retired")
    _write_ws(home, cortex_claude_sid="newsid12345678")
    inp = {"transcript_path": tpath, "tool_name": "mcp__marrow__wait", "tool_input": {}}
    reason = cortex_bridge.cortex_gate_pretool(inp)
    assert "newsid12" in reason


def test_gate_off_cortex_env_is_noop(cortex_env, tmp_path, monkeypatch):
    home, _ = cortex_env
    monkeypatch.delenv("MARROW_CORTEX", raising=False)
    tpath = _jsonl(tmp_path, "retired")
    _write_ws(home, cortex_claude_sid="registered-one")
    inp = {"transcript_path": tpath, "tool_name": "mcp__marrow__lie_down", "tool_input": {}}
    assert cortex_bridge.cortex_gate_pretool(inp) is None


def test_gate_global_monitor_wake_signal_deny_covers_cli_window(cortex_env, tmp_path, monkeypatch):
    """A plain cli window (no MARROW_CORTEX) arming a Monitor on the cortex
    wake_signal path is also denied when it is not the registered window
    (covers cli /loop windows re-arming the ear on resume, F-D)."""
    home, _ = cortex_env
    monkeypatch.delenv("MARROW_CORTEX", raising=False)
    tpath = _jsonl(tmp_path, "cli-window")
    _write_ws(home, cortex_claude_sid="the-real-cortex-window")
    signal_log = str(home / "state" / "wake_signal.log")
    inp = {"transcript_path": tpath, "tool_name": "Monitor",
           "tool_input": {"command": f"tail -n 0 -f {signal_log}"}}
    reason = cortex_bridge.cortex_gate_pretool(inp)
    assert reason


def test_gate_monitor_other_command_untouched(cortex_env, tmp_path, monkeypatch):
    monkeypatch.delenv("MARROW_CORTEX", raising=False)
    tpath = _jsonl(tmp_path, "cli-window")
    home, _ = cortex_env
    _write_ws(home, cortex_claude_sid="the-real-cortex-window")
    inp = {"transcript_path": tpath, "tool_name": "Monitor",
           "tool_input": {"command": "tail -n 0 -f /var/log/other.log"}}
    assert cortex_bridge.cortex_gate_pretool(inp) is None


# --- PreToolUse hook integration: takeover claim + gate deny -------------------

def test_pretool_takeover_claim_registers_caller(cortex_env, tmp_path, monkeypatch):
    home, db = cortex_env
    tpath = _jsonl(tmp_path, "newcaller")
    _write_ws(home, cortex_claude_sid="oldresident")
    _stdin(monkeypatch, {
        "transcript_path": tpath, "session_id": "s1", "tool_name": "Bash",
        "tool_input": {"command": "/venv/bin/python -m cortex.ctl wake"},
    })
    assert hooks.main(["pretool_use"]) == 0
    assert _ws(home)["cortex_claude_sid"] == "newcaller"


def test_pretool_takeover_claim_then_allows_call(cortex_env, tmp_path, monkeypatch, capsys):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "newcaller")
    _write_ws(home, cortex_claude_sid="oldresident")
    _stdin(monkeypatch, {
        "transcript_path": tpath, "session_id": "s1", "tool_name": "Bash",
        "tool_input": {"command": "/venv/bin/python -m cortex.ctl wake"},
    })
    assert hooks.main(["pretool_use"]) == 0
    hso = _hso(capsys)
    assert hso.get("permissionDecision") != "deny"


def test_pretool_denies_retired_window_lie_down(cortex_env, tmp_path, monkeypatch, capsys):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "retired")
    _write_ws(home, cortex_claude_sid="registered-elsewhere")
    _stdin(monkeypatch, {
        "transcript_path": tpath, "session_id": "s1",
        "tool_name": "mcp__marrow__lie_down", "tool_input": {"next_wake_min": 30},
    })
    assert hooks.main(["pretool_use"]) == 0
    assert _hso(capsys)["permissionDecision"] == "deny"


def test_pretool_plain_cli_ctl_wake_never_claims(cortex_env, tmp_path, monkeypatch):
    """Plain cli window (no MARROW_CORTEX) running /ct-wake keeps original
    semantics — never registers itself."""
    home, _ = cortex_env
    monkeypatch.delenv("MARROW_CORTEX", raising=False)
    tpath = _jsonl(tmp_path, "cliwindow")
    _write_ws(home, cortex_claude_sid="the-resident")
    _stdin(monkeypatch, {
        "transcript_path": tpath, "session_id": "s1", "tool_name": "Bash",
        "tool_input": {"command": "/venv/bin/python -m cortex.ctl wake"},
    })
    assert hooks.main(["pretool_use"]) == 0
    assert _ws(home)["cortex_claude_sid"] == "the-resident"  # unchanged


# --- UserPromptSubmit wake-branch: early-return / deathbed / handoff-landed ---

def test_wake_turn_registered_window_gets_normal_payload(cortex_env, tmp_path, monkeypatch, capsys):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "resident")
    _write_ws(home, cortex_claude_sid="resident")
    (home / "wakeup_note.md").write_text("## Wakeup\nnote body here")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    _stdin(monkeypatch, {
        "session_id": "s1", "transcript_path": tpath,
        "prompt": "☀️ 09:00",  # human-text bell -> shape fallback (no receipt)
    })
    assert hooks.main(["user_prompt_submit"]) == 0
    assert "note body here" in _ctx(capsys)


def test_wake_turn_receipt_bell_injects_note_and_consumes_receipt(cortex_env, tmp_path, monkeypatch, capsys):
    """New human-text bell ('☀️ 09:00') matched via the wake_state receipt:
    the note is injected and the receipt is consumed (one-shot)."""
    home, _ = cortex_env
    from datetime import datetime, timezone
    tpath = _jsonl(tmp_path, "resident")
    _write_ws(home, cortex_claude_sid="resident", gen=5, state_id="cafe",
              wake_receipt={"text": "☀️ 09:00", "gen": 5, "state_id": "cafe",
                            "rearm": False,
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "template_prefix": "☀️ "})
    (home / "wakeup_note.md").write_text("## Wakeup\nnote body here")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    _stdin(monkeypatch, {
        "session_id": "s1", "transcript_path": tpath, "prompt": "☀️ 09:00",
    })
    assert hooks.main(["user_prompt_submit"]) == 0
    assert "note body here" in _ctx(capsys)
    assert "wake_receipt" not in _ws(home)  # consumed


def test_wake_turn_shape_fallback_injects_note_when_receipt_missing(cortex_env, tmp_path, monkeypatch, capsys):
    """Receipt gone but the on-screen line matches the template shape -> fail
    OPEN: the note is still injected (never drop a genuine wake)."""
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "resident")
    _write_ws(home, cortex_claude_sid="resident")  # no receipt
    (home / "wakeup_note.md").write_text("## Wakeup\nnote body here")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    _stdin(monkeypatch, {
        "session_id": "s1", "transcript_path": tpath, "prompt": "☀️ 09:00",
    })
    assert hooks.main(["user_prompt_submit"]) == 0
    assert "note body here" in _ctx(capsys)


def test_wake_turn_receipt_stale_epoch_suppressed(cortex_env, tmp_path, monkeypatch, capsys):
    """A receipt-matched bell whose epoch token is stale (a newer epoch
    superseded it) suppresses the note — no injection."""
    home, _ = cortex_env
    from datetime import datetime, timezone
    tpath = _jsonl(tmp_path, "resident")
    # Live epoch gen=9 but the receipt token is gen=5 -> stale.
    _write_ws(home, cortex_claude_sid="resident", gen=9, state_id="cafe",
              wake_receipt={"text": "☀️ 09:00", "gen": 5, "state_id": "cafe",
                            "rearm": False,
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "template_prefix": "☀️ "})
    (home / "wakeup_note.md").write_text("## Wakeup\nnote body here")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    _stdin(monkeypatch, {
        "session_id": "s1", "transcript_path": tpath, "prompt": "☀️ 09:00",
    })
    assert hooks.main(["user_prompt_submit"]) == 0
    assert _ctx(capsys) == ""  # suppressed


def test_wake_turn_retired_window_gets_takeover_text_not_note(cortex_env, tmp_path, monkeypatch, capsys):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "retired")
    _write_ws(home, cortex_claude_sid="new-resident")
    (home / "wakeup_note.md").write_text("## Wakeup\nnote body here")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    _stdin(monkeypatch, {
        "session_id": "s1", "transcript_path": tpath,
        "prompt": "☀️ 09:00",  # human-text bell -> shape fallback (no receipt)
    })
    assert hooks.main(["user_prompt_submit"]) == 0
    ctx = _ctx(capsys)
    assert "note body here" not in ctx
    assert "RETIRED" in ctx


def test_wake_turn_retired_window_after_handoff_goes_silent(cortex_env, tmp_path, monkeypatch, capsys):
    home, _ = cortex_env
    from datetime import datetime, timedelta, timezone
    tpath = _jsonl(tmp_path, "retired")
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    _write_ws(home, cortex_claude_sid="new-resident", cortex_registered_at=past)
    (home / "handoff.md").write_text("## retired window section\ndone")
    (home / "wakeup_note.md").write_text("## Wakeup\nnote body here")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    _stdin(monkeypatch, {
        "session_id": "s1", "transcript_path": tpath,
        "prompt": "☀️ 09:00",  # human-text bell -> shape fallback (no receipt)
    })
    assert hooks.main(["user_prompt_submit"]) == 0
    assert _ctx(capsys) == ""  # fully silent


def test_wake_turn_retired_window_no_cursor_or_outbox_claim(cortex_env, tmp_path, monkeypatch, capsys):
    """Scenario matrix: resume retired window -> no zombie side effects (no
    note claim / cursor advance). Verified via no crash + no payload; the
    early-return happens before outbox.deliver/wakeup_note_text run."""
    home, db = cortex_env
    tpath = _jsonl(tmp_path, "retired")
    _write_ws(home, cortex_claude_sid="new-resident")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    calls = []
    from marrow import outbox as _outbox
    monkeypatch.setattr(_outbox, "deliver", lambda *a, **k: calls.append(1))
    _stdin(monkeypatch, {
        "session_id": "s1", "transcript_path": tpath,
        "prompt": "☀️ 09:00",  # human-text bell -> shape fallback (no receipt)
    })
    assert hooks.main(["user_prompt_submit"]) == 0
    assert calls == []  # outbox never touched on the retired branch


def test_wake_turn_handoff_landing_sends_notify(cortex_env, tmp_path, monkeypatch, capsys):
    home, _ = cortex_env
    from datetime import datetime, timedelta, timezone
    tpath = _jsonl(tmp_path, "retired")
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    _write_ws(home, cortex_claude_sid="new-resident", cortex_registered_at=past)
    (home / "handoff.md").write_text("## retired window section\ndone")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    sent = []
    from marrow import outbox as _outbox
    monkeypatch.setattr(_outbox, "send", lambda *a, **k: sent.append(a) or {"ok": True})
    _stdin(monkeypatch, {
        "session_id": "s1", "transcript_path": tpath,
        "prompt": "☀️ 09:00",  # human-text bell -> shape fallback (no receipt)
    })
    assert hooks.main(["user_prompt_submit"]) == 0
    assert len(sent) == 1
    assert sent[0][0] == "ct"


def test_chat_turn_retired_window_no_user_wake_reset(cortex_env, tmp_path, monkeypatch, capsys):
    """Scenario matrix: chat in retired window -> read-only, liveness tools
    denied. A real (non-machine) chat message must not flip awake / bump gen
    on the shared wake_state."""
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "retired")
    _write_ws(home, cortex_claude_sid="new-resident", awake=False)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    _stdin(monkeypatch, {
        "session_id": "s1", "transcript_path": tpath,
        "prompt": "hey are you there?",
    })
    assert hooks.main(["user_prompt_submit"]) == 0
    d = _ws(home)
    assert d.get("awake") is False  # unchanged -> no zombie wake flip
    assert "user_replied_this_wake" not in d


def test_chat_turn_registered_window_still_resets(cortex_env, tmp_path, monkeypatch, capsys):
    home, _ = cortex_env
    tpath = _jsonl(tmp_path, "resident")
    _write_ws(home, cortex_claude_sid="resident", awake=False)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    _stdin(monkeypatch, {
        "session_id": "s1", "transcript_path": tpath,
        "prompt": "hey are you there?",
    })
    assert hooks.main(["user_prompt_submit"]) == 0
    d = _ws(home)
    assert d.get("awake") is True  # registered window -> normal reset fires
