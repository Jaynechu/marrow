"""Wake-pipeline v2 injections in hooks (cortex window only):
- SessionStart arm line (fresh window)
- UserPromptSubmit wake-turn full-note inject
- UserPromptSubmit monitor-death rearm inject
"""
from __future__ import annotations

import io
import json

import pytest

from marrow import config, cortex_bridge, hooks, storage


def _stdin(monkeypatch, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))


def _ctx(capsys):
    out = capsys.readouterr().out
    if not out.strip():
        return ""
    return json.loads(out)["hookSpecificOutput"].get("additionalContext", "")


def _enable(monkeypatch, tmp_path, extra=None):
    real = config.load

    def _patched():
        cfg = dict(real())
        cx = dict(cfg.get("cortex", {}))
        cx["enabled"] = True
        cx["home"] = str(tmp_path)
        if extra:
            cx.update(extra)
        cfg["cortex"] = cx
        return cfg

    monkeypatch.setattr(config, "load", _patched)


# ── Item 2: wake-turn full-note inject ────────────────────────────────────────

def test_wake_turn_injects_full_note(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARROW_CORTEX", "1")
    (tmp_path / "wakeup_note.md").write_text("read me and act", encoding="utf-8")
    _enable(monkeypatch, tmp_path, {"wake_marker": "[CORTEX-WAKE]"})
    _stdin(monkeypatch, {"session_id": "s1",
                         "prompt": "[CORTEX-WAKE] 2026-07-11 14:00 wake"})
    assert hooks.main(["user_prompt_submit"]) == 0
    assert _ctx(capsys) == "read me and act"


def test_wake_turn_missing_note_silent(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARROW_CORTEX", "1")
    _enable(monkeypatch, tmp_path, {"wake_marker": "[CORTEX-WAKE]"})
    _stdin(monkeypatch, {"session_id": "s1", "prompt": "[CORTEX-WAKE] wake"})
    assert hooks.main(["user_prompt_submit"]) == 0
    assert _ctx(capsys) == ""


def test_ordinary_chat_no_note_inject(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARROW_CORTEX", "1")
    (tmp_path / "wakeup_note.md").write_text("secret note", encoding="utf-8")
    _enable(monkeypatch, tmp_path, {"wake_marker": "[CORTEX-WAKE]"})
    _stdin(monkeypatch, {"session_id": "s1", "prompt": "今天过得怎么样"})
    assert hooks.main(["user_prompt_submit"]) == 0
    assert "secret note" not in _ctx(capsys)


def test_wakeup_note_fresh_render_wins(tmp_path, monkeypatch):
    """render_module configured + subprocess succeeds => fresh stdout is used,
    not the frozen file."""
    (tmp_path / "wakeup_note.md").write_text("frozen", encoding="utf-8")
    _enable(monkeypatch, tmp_path, {"render_module": "cortex.note_render",
                                    "venv_python": "/x/py", "repo_root": "/x"})

    class _P:
        returncode = 0
        stdout = "FRESH note SID feed1234"
        stderr = ""
    monkeypatch.setattr(cortex_bridge.subprocess, "run", lambda *a, **k: _P())
    assert cortex_bridge.wakeup_note_text("/t/feed1234ab.jsonl") == "FRESH note SID feed1234"


def test_wakeup_note_falls_back_on_render_failure(tmp_path, monkeypatch):
    """Subprocess failure / non-zero / empty => frozen file is returned."""
    (tmp_path / "wakeup_note.md").write_text("frozen fallback", encoding="utf-8")
    _enable(monkeypatch, tmp_path, {"render_module": "cortex.note_render",
                                    "venv_python": "/x/py", "repo_root": "/x"})

    def _boom(*a, **k):
        raise OSError("no such venv")
    monkeypatch.setattr(cortex_bridge.subprocess, "run", _boom)
    assert cortex_bridge.wakeup_note_text("/t/x.jsonl") == "frozen fallback"


def test_wakeup_note_no_render_module_uses_file(tmp_path, monkeypatch):
    """render_module unset => never spawns, static file only (feature disabled)."""
    (tmp_path / "wakeup_note.md").write_text("static only", encoding="utf-8")
    _enable(monkeypatch, tmp_path, {"venv_python": "/x/py", "repo_root": "/x"})

    def _fail(*a, **k):
        raise AssertionError("subprocess must not run when render_module unset")
    monkeypatch.setattr(cortex_bridge.subprocess, "run", _fail)
    assert cortex_bridge.wakeup_note_text("/t/x.jsonl") == "static only"


def test_non_cortex_session_no_wake_inject(tmp_path, monkeypatch, capsys):
    """No MARROW_CORTEX => the whole cortex branch is skipped."""
    monkeypatch.delenv("MARROW_CORTEX", raising=False)
    (tmp_path / "wakeup_note.md").write_text("note", encoding="utf-8")
    _enable(monkeypatch, tmp_path, {"wake_marker": "[CORTEX-WAKE]"})
    _stdin(monkeypatch, {"session_id": "s1", "prompt": "[CORTEX-WAKE] wake"})
    assert hooks.main(["user_prompt_submit"]) == 0
    assert "note" not in _ctx(capsys)


# ── Item 3: monitor-death rearm inject ────────────────────────────────────────

_DEATH = ('<task-notification>\n<summary>Monitor event: "ear"</summary>\n'
          '<event>[Monitor stopped — too much output.]</event>\n'
          '</task-notification>')


def test_monitor_death_injects_rearm(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARROW_CORTEX", "1")
    _enable(monkeypatch, tmp_path,
            {"rearm_text": "rearm: tail {signal_log}"})
    _stdin(monkeypatch, {"session_id": "s1", "prompt": _DEATH})
    assert hooks.main(["user_prompt_submit"]) == 0
    assert _ctx(capsys) == f"rearm: tail {tmp_path/'wake_signal.log'}"


def test_monitor_death_silent_on_normal_chat(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARROW_CORTEX", "1")
    _enable(monkeypatch, tmp_path, {"rearm_text": "rearm {signal_log}"})
    _stdin(monkeypatch, {"session_id": "s1", "prompt": "Monitor 工具怎么用啊"})
    assert hooks.main(["user_prompt_submit"]) == 0
    assert "rearm" not in _ctx(capsys)


def test_monitor_death_blank_text_silent(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARROW_CORTEX", "1")
    _enable(monkeypatch, tmp_path, {"rearm_text": ""})
    _stdin(monkeypatch, {"session_id": "s1", "prompt": _DEATH})
    assert hooks.main(["user_prompt_submit"]) == 0
    assert _ctx(capsys) == ""


# ── Item 1: SessionStart arm line (fresh cortex window) ───────────────────────

def _ss_db(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    storage.init_db(db).close()
    monkeypatch.setattr(config, "db_path", lambda: db)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return db


def test_arm_line_injected_fresh_cortex_window(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARROW_CORTEX", "1")
    _ss_db(tmp_path, monkeypatch)
    _enable(monkeypatch, tmp_path, {"arm_ear_text": "arm: tail {signal_log}"})
    jl = tmp_path / "s.jsonl"
    jl.write_text("", encoding="utf-8")
    _stdin(monkeypatch, {"session_id": "fresh1", "cwd": str(tmp_path),
                         "transcript_path": str(jl)})
    assert hooks.main(["session_start"]) == 0
    assert f"arm: tail {tmp_path/'wake_signal.log'}" in _ctx(capsys)


def test_arm_line_blank_silent(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARROW_CORTEX", "1")
    _ss_db(tmp_path, monkeypatch)
    _enable(monkeypatch, tmp_path, {"arm_ear_text": ""})
    jl = tmp_path / "s.jsonl"
    jl.write_text("", encoding="utf-8")
    _stdin(monkeypatch, {"session_id": "fresh2", "cwd": str(tmp_path),
                         "transcript_path": str(jl)})
    assert hooks.main(["session_start"]) == 0
    assert "arm:" not in _ctx(capsys)


def test_arm_line_skipped_non_cortex(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MARROW_CORTEX", raising=False)
    _ss_db(tmp_path, monkeypatch)
    _enable(monkeypatch, tmp_path, {"arm_ear_text": "arm: tail {signal_log}"})
    jl = tmp_path / "s.jsonl"
    jl.write_text("", encoding="utf-8")
    _stdin(monkeypatch, {"session_id": "fresh3", "cwd": str(tmp_path),
                         "transcript_path": str(jl)})
    assert hooks.main(["session_start"]) == 0
    assert "arm:" not in _ctx(capsys)


# ── Resume: resume_ear_text inject + no arm regression ────────────────────────

def _mark_resume(db, sid):
    """Seed a prior lifecycle:start row so SessionStart classifies sid a resume."""
    conn = storage.connect(db)
    with conn:
        conn.execute(
            "INSERT INTO audit_log (target_table, target_id, action, summary)"
            " VALUES ('events', ?, 'session_lifecycle:start', 'ppid=1,source=cc')",
            (sid,),
        )
    conn.close()


def _write_wake_state(tmp_path, transcript):
    (tmp_path / "wake_state.json").write_text(
        json.dumps({"awake": True, "transcript": str(transcript)}),
        encoding="utf-8")


def test_resume_resident_injects_resume_ear_text(tmp_path, monkeypatch, capsys):
    """Resident resume (wake_state transcript == this session) → re-arm guidance
    + orphan cleanup, never the fresh-window arm line."""
    monkeypatch.setenv("MARROW_CORTEX", "1")
    db = _ss_db(tmp_path, monkeypatch)
    _enable(monkeypatch, tmp_path,
            {"arm_ear_text": "arm: tail {signal_log}",
             "resume_ear_text": "resume: retail {signal_log}",
             "retired_ear_text": "retired: read only"})
    called = {"n": 0}
    monkeypatch.setattr(cortex_bridge, "kill_orphan_ear_tails",
                        lambda: called.__setitem__("n", called["n"] + 1) or 0)
    _mark_resume(db, "res1")
    jl = tmp_path / "s.jsonl"
    jl.write_text("", encoding="utf-8")
    _write_wake_state(tmp_path, jl)
    _stdin(monkeypatch, {"session_id": "res1", "cwd": str(tmp_path),
                         "transcript_path": str(jl)})
    assert hooks.main(["session_start"]) == 0
    ctx = _ctx(capsys)
    assert f"resume: retail {tmp_path/'wake_signal.log'}" in ctx
    assert "arm: tail" not in ctx
    assert "retired:" not in ctx
    assert called["n"] == 1  # orphan cleanup ran in the resident case


def test_resume_retired_injects_retired_text_no_cleanup(tmp_path, monkeypatch, capsys):
    """Retired resume (wake_state transcript points at a DIFFERENT session) →
    read-only guidance, NO orphan cleanup (must not kill resident's tail)."""
    monkeypatch.setenv("MARROW_CORTEX", "1")
    db = _ss_db(tmp_path, monkeypatch)
    _enable(monkeypatch, tmp_path,
            {"resume_ear_text": "resume: retail {signal_log}",
             "retired_ear_text": "retired: read only"})
    called = {"n": 0}
    monkeypatch.setattr(cortex_bridge, "kill_orphan_ear_tails",
                        lambda: called.__setitem__("n", called["n"] + 1) or 0)
    _mark_resume(db, "res3")
    jl = tmp_path / "old.jsonl"
    jl.write_text("", encoding="utf-8")
    # Resident pointer is a NEWER transcript, not this one.
    _write_wake_state(tmp_path, tmp_path / "newer.jsonl")
    _stdin(monkeypatch, {"session_id": "res3", "cwd": str(tmp_path),
                         "transcript_path": str(jl)})
    assert hooks.main(["session_start"]) == 0
    ctx = _ctx(capsys)
    assert "retired: read only" in ctx
    assert "resume: retail" not in ctx
    assert called["n"] == 0  # orphan cleanup must NOT run for a retired window


def test_is_resident_session_branch_decision(tmp_path, monkeypatch):
    """Deterministic match/no-match decision off wake_state.transcript."""
    _enable(monkeypatch, tmp_path, {})
    # Match.
    _write_wake_state(tmp_path, tmp_path / "a.jsonl")
    assert cortex_bridge.is_resident_session(str(tmp_path / "a.jsonl")) is True
    # No match → retired.
    assert cortex_bridge.is_resident_session(str(tmp_path / "b.jsonl")) is False
    # Empty/missing pointer defaults to resident.
    (tmp_path / "wake_state.json").write_text(json.dumps({"awake": True}),
                                              encoding="utf-8")
    assert cortex_bridge.is_resident_session(str(tmp_path / "a.jsonl")) is True


def test_fresh_window_still_arms_not_resume(tmp_path, monkeypatch, capsys):
    """Regression: a fresh window keeps injecting arm_ear_text, never resume."""
    monkeypatch.setenv("MARROW_CORTEX", "1")
    _ss_db(tmp_path, monkeypatch)
    _enable(monkeypatch, tmp_path,
            {"arm_ear_text": "arm: tail {signal_log}",
             "resume_ear_text": "resume: retail {signal_log}"})
    jl = tmp_path / "s.jsonl"
    jl.write_text("", encoding="utf-8")
    _stdin(monkeypatch, {"session_id": "freshR", "cwd": str(tmp_path),
                         "transcript_path": str(jl)})
    assert hooks.main(["session_start"]) == 0
    ctx = _ctx(capsys)
    assert f"arm: tail {tmp_path/'wake_signal.log'}" in ctx
    assert "resume: retail" not in ctx


def test_resume_blank_text_silent(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARROW_CORTEX", "1")
    db = _ss_db(tmp_path, monkeypatch)
    _enable(monkeypatch, tmp_path, {"resume_ear_text": ""})
    monkeypatch.setattr(cortex_bridge, "kill_orphan_ear_tails", lambda: 0)
    _mark_resume(db, "res2")
    jl = tmp_path / "s.jsonl"
    jl.write_text("", encoding="utf-8")
    _stdin(monkeypatch, {"session_id": "res2", "cwd": str(tmp_path),
                         "transcript_path": str(jl)})
    assert hooks.main(["session_start"]) == 0
    assert "resume:" not in _ctx(capsys)


# ── Resume no-completion-record notice is NOT monitor death ───────────────────

_NO_COMPLETION = (
    '<task-notification>\n<task-id>bxybfk5js</task-id>\n'
    '<tool-use-id>toolu_x</tool-use-id>\n<status>stopped</status>\n'
    '<summary>No completion record was found for this background shell command '
    'from the previous session. It may have been stopped (via the UI, Monitor '
    'timeout, or agent teardown — these leave no transcript marker), or it may '
    'have been running when the previous Claude Code process exited.</summary>\n'
    '</task-notification>'
)


def test_no_completion_record_not_monitor_death():
    assert cortex_bridge.is_monitor_death(_NO_COMPLETION) is False


def test_no_completion_record_no_rearm_inject(tmp_path, monkeypatch, capsys):
    """The resume notice must not trigger the mid-window rearm flow."""
    monkeypatch.setenv("MARROW_CORTEX", "1")
    _enable(monkeypatch, tmp_path, {"rearm_text": "rearm: tail {signal_log}"})
    _stdin(monkeypatch, {"session_id": "s1", "prompt": _NO_COMPLETION})
    assert hooks.main(["user_prompt_submit"]) == 0
    assert "rearm" not in _ctx(capsys)
