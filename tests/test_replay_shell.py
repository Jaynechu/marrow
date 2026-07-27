"""Per-shell cortex replay: self-channel exclude + per-shell cursor.

cli shell = regression baseline (exclude 'ct', cursor in wake_state.json);
tg shell drops its own 'tg' rows, keeps 'ct' rows, and keeps its cursor in the
shell ledger <shell_state_dir>/tg.json.
"""
from __future__ import annotations

import io
import json

import pytest

from marrow import config, cortex_bridge, hooks, storage

SID_OTHER = "othr9999-8888"
SID_CT = "ctsid0000"


def _fresh_db(tmp_path):
    p = str(tmp_path / "d.db")
    storage.init_db(p).close()
    return p


def _ev(db, sid, role, content, *, channel="cli", ts="2026-07-26T04:00:00Z"):
    conn = storage.connect(db)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO events(session_id, timestamp, role, content, channel)"
                " VALUES(?,?,?,?,?)", (sid, ts, role, content, channel))
        return cur.lastrowid
    finally:
        conn.close()


def _setup(monkeypatch, tmp_path, db, shell):
    """Patch config + both cursor files into tmp_path and pretend this window is
    a cortex window of `shell`. Returns (wake_state path, ledger path)."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "db_path", lambda: db)
    real = config.load

    def _patched():
        cfg = dict(real())
        rp = dict(cfg.get("replay", {}))
        rp.update({"max_turns": 10, "max_lines": 0, "per_msg_chars": 500})
        cfg["replay"] = rp
        return cfg

    monkeypatch.setattr(config, "load", _patched)
    monkeypatch.setenv("MARROW_CORTEX", "1" if shell == "cli" else shell)
    ws = tmp_path / "wake_state.json"
    ledger_dir = tmp_path / "shells"
    monkeypatch.setattr(cortex_bridge, "_cortex_wake_state_path", lambda: ws)
    monkeypatch.setattr(cortex_bridge, "_shell_state_path",
                        lambda s=None: ledger_dir / f"{s or shell}.json")
    return ws, ledger_dir / f"{shell}.json"


def _cursor(p):
    return json.loads(p.read_text()).get("last_note_row_id") if p.exists() else None


def _three_rows(db):
    """One ordinary cli row, one tg row, one ct row — newest last."""
    return (
        _ev(db, SID_OTHER, "user", "ordinary session talking",
            channel="cli", ts="2026-07-26T05:00:00Z"),
        _ev(db, "tgsid111", "user", "telegram window talking",
            channel="tg", ts="2026-07-26T05:01:00Z"),
        _ev(db, SID_CT, "assistant", "cli cortex window talking",
            channel="ct", ts="2026-07-26T05:02:00Z"),
    )


# ── T1: exclude resolution ──────────────────────────────────────────────────

def test_exclude_defaults_per_shell(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "db_path", lambda: str(tmp_path / "none.db"))
    assert hooks._replay_cortex_exclude_channels("cli") == ["ct"]
    assert hooks._replay_cortex_exclude_channels("tg") == ["tg"]
    # unknown shell -> the unqualified set
    assert hooks._replay_cortex_exclude_channels("wx") == ["ct"]


def test_exclude_toml_override_and_multi_channel(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "db_path", lambda: str(tmp_path / "d.db"))
    (tmp_path / "cortex.toml").write_text(
        '[note]\nshell_replay_exclude = { tg = ["tg", "wx"] }\n')
    assert hooks._replay_cortex_exclude_channels("tg") == ["tg", "wx"]
    # a shell absent from the override map still falls back to 'ct'
    assert hooks._replay_cortex_exclude_channels("cli") == ["ct"]


def test_tg_shell_excludes_both_configured_channels(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "tg")
    (tmp_path / "cortex.toml").write_text(
        '[note]\nshell_replay_exclude = { tg = ["tg", "wx"] }\n')
    _ev(db, "tgsid111", "user", "telegram window talking", channel="tg")
    _ev(db, "wxsid111", "user", "wechat window talking", channel="wx")
    _ev(db, SID_CT, "assistant", "cli cortex window talking", channel="ct")
    out = hooks._replay_context(SID_CT, "ct")
    assert "cli cortex window talking" in out
    assert "telegram window talking" not in out
    assert "wechat window talking" not in out


# ── T1 + T2: cli baseline ───────────────────────────────────────────────────

def test_cli_shell_drops_ct_keeps_tg_and_uses_wake_state(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "cli")
    _cli, _tg, ct_id = _three_rows(db)
    out = hooks._replay_context(SID_CT, "ct")
    assert "ordinary session talking" in out
    assert "telegram window talking" in out
    assert "cli cortex window talking" not in out
    # cursor lands in wake_state.json on the newest SCANNED row (the ct row is
    # filtered by SQL, so the cutoff is the tg row)
    assert _cursor(ws) == _tg < ct_id
    assert not ledger.exists()
    # delivered once
    assert hooks._replay_context(SID_CT, "ct") == ""


def test_cli_legacy_ts_migration_still_applies(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "cli")
    _ev(db, SID_OTHER, "user", "already delivered", ts="2026-07-26T06:00:00Z")
    ws.write_text(json.dumps({"last_note_ts": "2026-07-26T06:00:00Z"}))
    new_id = _ev(db, SID_OTHER, "user", "new after migration",
                 ts="2026-07-26T06:05:00Z")
    out = hooks._replay_context(SID_CT, "ct")
    assert "new after migration" in out and "already delivered" not in out
    assert _cursor(ws) == new_id
    assert not ledger.exists()


# ── T2: tg ledger cursor ────────────────────────────────────────────────────

def test_tg_shell_drops_tg_keeps_ct_and_uses_ledger(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "tg")
    _cli, _tg, ct_id = _three_rows(db)
    out = hooks._replay_context(SID_CT, "ct")
    assert "ordinary session talking" in out
    assert "cli cortex window talking" in out
    assert "telegram window talking" not in out
    assert _cursor(ledger) == ct_id
    assert not ws.exists()
    assert hooks._replay_context(SID_CT, "ct") == ""
    assert _cursor(ledger) == ct_id


def test_tg_ledger_read_as_cursor_and_other_keys_preserved(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "tg")
    old = _ev(db, SID_OTHER, "user", "before the cursor",
              ts="2026-07-26T07:00:00Z")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({"last_note_row_id": old,
                                  "session_id": "keepme",
                                  "last_note_ts": "2026-07-26T07:00:00Z"}))
    new_id = _ev(db, SID_OTHER, "user", "after the cursor",
                 ts="2026-07-26T07:05:00Z")
    out = hooks._replay_context(SID_CT, "ct")
    assert "after the cursor" in out and "before the cursor" not in out
    d = json.loads(ledger.read_text())
    assert d["last_note_row_id"] == new_id
    assert d["session_id"] == "keepme"
    assert d["last_note_ts"] == "2026-07-26T07:00:00Z"


def test_tg_ledger_last_note_ts_is_not_a_cursor_source(tmp_path, monkeypatch):
    # the ledger's last_note_ts serves other purposes: with no row-id cursor the
    # window is full, exactly like cli's first read.
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "tg")
    _ev(db, SID_OTHER, "user", "older than last_note_ts",
        ts="2026-07-26T07:00:00Z")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({"last_note_ts": "2026-07-26T09:00:00Z"}))
    assert "older than last_note_ts" in hooks._replay_context(SID_CT, "ct")


def test_tg_all_noise_batch_still_advances_ledger(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "tg")
    _ev(db, SID_OTHER, "user", "/info", ts="2026-07-26T08:00:00Z")
    last = _ev(db, SID_OTHER, "user", "/status", ts="2026-07-26T08:01:00Z")
    assert hooks._replay_context(SID_CT, "ct") == ""
    assert _cursor(ledger) == last
    assert not ws.exists()


def test_tg_advance_is_monotonic(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "tg")
    _ev(db, SID_OTHER, "user", "old real", ts="2026-07-26T10:00:00Z")
    last = _ev(db, SID_OTHER, "user", "/info", ts="2026-07-26T10:01:00Z")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({"last_note_row_id": last + 50}))
    assert hooks._replay_context(SID_CT, "ct") == ""
    assert _cursor(ledger) == last + 50


def test_cli_advance_is_monotonic(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "cli")
    _ev(db, SID_OTHER, "user", "old real", ts="2026-07-26T10:00:00Z")
    last = _ev(db, SID_OTHER, "user", "/info", ts="2026-07-26T10:01:00Z")
    ws.write_text(json.dumps({"last_note_row_id": last + 50}))
    assert hooks._replay_context(SID_CT, "ct") == ""
    assert _cursor(ws) == last + 50


def test_two_shells_each_see_the_same_activity(tmp_path, monkeypatch):
    # the point of the split cursor: whichever shell wakes first no longer
    # consumes the batch for the other.
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, "tg")
    _ev(db, SID_OTHER, "user", "ordinary session talking",
        ts="2026-07-26T11:00:00Z")
    assert "ordinary session talking" in hooks._replay_context(SID_CT, "ct")
    _setup(monkeypatch, tmp_path, db, "cli")
    assert "ordinary session talking" in hooks._replay_context(SID_CT, "ct")


# ── T4: an in-flight note's pending cutoff counts as read ───────────────────

def _pending(p):
    return json.loads(p.read_text()).get("pending_note_row_id") if p.exists() else None


def test_pending_cutoff_higher_than_last_is_the_effective_cursor(tmp_path, monkeypatch):
    # synapse writes pending_note_row_id before feeding a note; the fed turn's
    # own hook must not re-replay what that note is already showing.
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "tg")
    old = _ev(db, SID_OTHER, "user", "already in the note",
              ts="2026-07-26T12:00:00Z")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({"last_note_row_id": old - 1,
                                  "pending_note_row_id": old}))
    assert hooks._replay_context(SID_CT, "ct") == ""
    # advance writes only last_note_row_id; the pending key is synapse's to clear
    assert _pending(ledger) == old
    new_id = _ev(db, SID_OTHER, "user", "landed after the note",
                 ts="2026-07-26T12:05:00Z")
    assert "landed after the note" in hooks._replay_context(SID_CT, "ct")
    assert _cursor(ledger) == new_id
    assert _pending(ledger) == old


def test_pending_absent_leaves_the_cursor_read_unchanged(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "tg")
    old = _ev(db, SID_OTHER, "user", "before the cursor",
              ts="2026-07-26T13:00:00Z")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({"last_note_row_id": old}))
    new_id = _ev(db, SID_OTHER, "user", "after the cursor",
                 ts="2026-07-26T13:05:00Z")
    out = hooks._replay_context(SID_CT, "ct")
    assert "after the cursor" in out and "before the cursor" not in out
    assert _cursor(ledger) == new_id


def test_advance_is_monotonic_against_the_effective_cursor(tmp_path, monkeypatch):
    # a pending cutoff above every scanned row: nothing to advance to, and the
    # lower last_note_row_id is left where it is.
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "tg")
    last = _ev(db, SID_OTHER, "user", "real talk", ts="2026-07-26T14:00:00Z")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({"last_note_row_id": last - 1,
                                  "pending_note_row_id": last + 50}))
    assert hooks._replay_context(SID_CT, "ct") == ""
    assert _cursor(ledger) == last - 1
    assert _pending(ledger) == last + 50


def test_effective_cursor_helper_ignores_non_ints():
    f = hooks._shell_ledger_since_row_id
    assert f({}) is None
    assert f({"last_note_row_id": 5}) == 5
    assert f({"pending_note_row_id": 7}) == 7
    assert f({"last_note_row_id": 9, "pending_note_row_id": 7}) == 9
    assert f({"last_note_row_id": True, "pending_note_row_id": "x"}) is None


def test_shell_state_keys_carry_the_row_id_cursor():
    assert "last_note_row_id" in cortex_bridge._SHELL_STATE_KEYS
    assert "pending_note_row_id" in cortex_bridge._SHELL_STATE_KEYS


# ── T1: a wake-bell turn injects the replay exactly once ────────────────────

def _bell_templates(monkeypatch):
    monkeypatch.setattr(cortex_bridge, "wake_bell_template", lambda cfg=None: "⏰ {hm}")
    monkeypatch.setattr(cortex_bridge, "spawn_opener_template", lambda cfg=None: "☀️ {hm}")


def _quiet_turn_inject(monkeypatch):
    """Silence every other turn_inject fragment so the assertion is about replay."""
    monkeypatch.delenv("MARROW_CHANNEL", raising=False)
    monkeypatch.setattr(hooks, "_kickout_context", lambda *a, **k: "")
    monkeypatch.setattr(hooks, "_usage_threshold_context", lambda *a, **k: "")
    monkeypatch.setattr(hooks, "_outbound_notes", lambda *a, **k: "")
    monkeypatch.setattr(cortex_bridge, "_cortex_show_context", lambda *a, **k: "")


def _turn_inject(monkeypatch, capsys, prompt):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({
        "session_id": SID_CT, "transcript_path": "/t/ct123456.jsonl",
        "prompt": prompt})))
    hooks.turn_inject()
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def test_wake_bell_turn_is_recognised_read_only(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, "cli")
    _bell_templates(monkeypatch)
    assert hooks._is_wake_bell_turn("⏰ 09:30", "/t/x.jsonl") is True
    assert hooks._is_wake_bell_turn("☀️ 09:30", "/t/x.jsonl") is True
    assert hooks._is_wake_bell_turn("早安，今天几点上班", "/t/x.jsonl") is False
    assert hooks._is_wake_bell_turn("", "/t/x.jsonl") is False
    monkeypatch.delenv("MARROW_CORTEX", raising=False)
    assert hooks._is_wake_bell_turn("⏰ 09:30", "/t/x.jsonl") is False


def test_turn_inject_skips_replay_on_a_wake_turn(tmp_path, monkeypatch, capsys):
    # The wakeup note injected by user_prompt_submit already carries these rows.
    db = _fresh_db(tmp_path)
    ws, _ledger = _setup(monkeypatch, tmp_path, db, "cli")
    _bell_templates(monkeypatch)
    _quiet_turn_inject(monkeypatch)
    _ev(db, SID_OTHER, "user", "ordinary session talking",
        ts="2026-07-26T15:00:00Z")
    ctx = _turn_inject(monkeypatch, capsys, "⏰ 09:30")
    assert "ordinary session talking" not in ctx
    assert "Recent replay" not in ctx
    # cursor untouched: the note's own delivery decides when it advances
    assert _cursor(ws) is None


def test_turn_inject_still_replays_on_an_ordinary_turn(tmp_path, monkeypatch, capsys):
    db = _fresh_db(tmp_path)
    ws, _ledger = _setup(monkeypatch, tmp_path, db, "cli")
    _bell_templates(monkeypatch)
    _quiet_turn_inject(monkeypatch)
    row = _ev(db, SID_OTHER, "user", "ordinary session talking",
              ts="2026-07-26T15:05:00Z")
    ctx = _turn_inject(monkeypatch, capsys, "在干嘛")
    assert "ordinary session talking" in ctx
    assert _cursor(ws) == row


def test_wake_note_delivery_advances_the_shared_cursor(tmp_path, monkeypatch):
    # deliver-then-advance: once the note carrying `row` is injected, the next
    # turn's replay must not show it again.
    db = _fresh_db(tmp_path)
    ws, _ledger = _setup(monkeypatch, tmp_path, db, "cli")
    row = _ev(db, SID_OTHER, "user", "in the wakeup note",
              ts="2026-07-26T16:00:00Z")
    cortex_bridge.advance_cli_replay_cursor(row)
    assert _cursor(ws) == row
    assert hooks._replay_context(SID_CT, "ct") == ""
    fresh = _ev(db, SID_OTHER, "user", "after the note",
                ts="2026-07-26T16:05:00Z")
    out = hooks._replay_context(SID_CT, "ct")
    assert "after the note" in out and "in the wakeup note" not in out
    assert _cursor(ws) == fresh


def test_advance_cli_replay_cursor_is_monotonic_and_cli_only(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, ledger = _setup(monkeypatch, tmp_path, db, "cli")
    cortex_bridge.advance_cli_replay_cursor(20)
    cortex_bridge.advance_cli_replay_cursor(9)   # never rewinds
    cortex_bridge.advance_cli_replay_cursor(None)
    cortex_bridge.advance_cli_replay_cursor(True)  # bool is not a row id
    assert _cursor(ws) == 20
    # a non-cli shell owns its own ledger, written by its feeder — no-op here
    ws2, ledger2 = _setup(monkeypatch, tmp_path, db, "tg")
    cortex_bridge.advance_cli_replay_cursor(99)
    assert _cursor(ws2) == 20
    assert not ledger2.exists()


def test_render_note_fresh_reports_the_cutoff(monkeypatch):
    monkeypatch.setattr(config, "load",
                        lambda: {"cortex": {"render_module": "cortex.note_render"}})
    monkeypatch.setattr(cortex_bridge, "_cortex_paths", lambda: ("/venv/py", "/root"))
    seen = {}

    class _P:
        returncode = 0
        stdout = "NOTE BODY\n"
        stderr = "some warning\ncutoff_row_id=42\n"

    def _run(cmd, **kw):
        seen["cmd"] = list(cmd)
        return _P()

    monkeypatch.setattr(cortex_bridge.subprocess, "run", _run)
    text, cutoff = cortex_bridge._render_note_fresh("/t/abc12345.jsonl")
    assert text == "NOTE BODY" and cutoff == 42
    assert "--no-ct" in seen["cmd"]
    assert "--transcript" in seen["cmd"]


def test_wakeup_note_payload_falls_back_without_a_cutoff(tmp_path, monkeypatch):
    monkeypatch.setattr(cortex_bridge, "_render_note_fresh", lambda t: (None, None))
    monkeypatch.setattr(cortex_bridge, "_cortex_path",
                        lambda key, default: tmp_path / "wakeup_note.md")
    (tmp_path / "wakeup_note.md").write_text("frozen fallback\n")
    assert cortex_bridge.wakeup_note_payload("/t/x.jsonl") == ("frozen fallback", None)


# ── T4: a lock we cannot take skips the round, never writes unlocked ────────

class _FastClock:
    """monotonic jumps a minute per call — the 5s lock deadline expires at once."""

    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        self.t += 60.0
        return self.t

    def sleep(self, _s):
        pass


def _lock_always_busy(monkeypatch):
    def _busy(_fd, _flags):
        raise OSError(35, "would block")

    monkeypatch.setattr(cortex_bridge._fcntl, "flock", _busy)
    monkeypatch.setattr(cortex_bridge, "time", _FastClock())


def test_required_lock_timeout_raises(tmp_path, monkeypatch):
    _lock_always_busy(monkeypatch)
    p = tmp_path / "wake_state.json"
    with pytest.raises(cortex_bridge.WakeStateLockTimeout):
        with cortex_bridge._wake_state_lock(p, required=True):
            pass


def test_default_lock_still_proceeds_unlocked(tmp_path, monkeypatch):
    # unchanged best-effort behaviour for the non-replay wake_state writers
    _lock_always_busy(monkeypatch)
    p = tmp_path / "wake_state.json"
    entered = False
    with cortex_bridge._wake_state_lock(p):
        entered = True
    assert entered


def test_replay_skips_the_round_when_the_lock_is_busy(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, _ledger = _setup(monkeypatch, tmp_path, db, "cli")
    ws.write_text(json.dumps({"last_note_row_id": 0}))
    row = _ev(db, SID_OTHER, "user", "contended row", ts="2026-07-26T17:00:00Z")
    _lock_always_busy(monkeypatch)
    assert hooks._replay_context(SID_CT, "ct") == ""
    assert _cursor(ws) == 0  # untouched — no unlocked write
    monkeypatch.undo()
    # the row was not consumed: it replays on the next round
    ws, _ledger = _setup(monkeypatch, tmp_path, db, "cli")
    ws.write_text(json.dumps({"last_note_row_id": 0}))
    assert "contended row" in hooks._replay_context(SID_CT, "ct")
    assert _cursor(ws) == row


def test_wake_cursor_advance_skips_on_lock_timeout(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    ws, _ledger = _setup(monkeypatch, tmp_path, db, "cli")
    ws.write_text(json.dumps({"last_note_row_id": 3}))
    _lock_always_busy(monkeypatch)
    cortex_bridge.advance_cli_replay_cursor(9)
    assert _cursor(ws) == 3


# ── T5: the 2-round / 4-line cap on the cortex path too ─────────────────────

def test_cortex_replay_caps_at_two_rounds_four_lines(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "db_path", lambda: db)
    monkeypatch.setenv("MARROW_CORTEX", "1")
    ws = tmp_path / "wake_state.json"
    monkeypatch.setattr(cortex_bridge, "_cortex_wake_state_path", lambda: ws)
    for i in range(4):  # shipped [replay] defaults: max_turns=2, max_lines=4
        _ev(db, SID_OTHER, "user", f"q{i}", ts=f"2026-07-26T18:0{i}:00Z")
        _ev(db, SID_OTHER, "assistant", f"a{i}", ts=f"2026-07-26T18:0{i}:30Z")
    out = hooks._replay_context(SID_CT, "ct")
    lines = [ln for ln in out.splitlines() if ln.startswith("[")]
    assert len(lines) == 4
    assert "q3" in out and "q2" in out and "q1" not in out
    assert _cursor(ws) == 8  # cursor passes the overflow it dropped
