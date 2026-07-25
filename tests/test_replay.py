"""P3 — cross-session replay inject (hooks._replay_context).

Covers: first-sight cursor seed (no backfill), cursor advance, turn grouping +
cap + fold line, own-sid exclusion, source-ct exclusion, destination-channel
exclusion, enabled=false, nothing-new → empty inject; F11 SessionStart seed.
"""
from __future__ import annotations

import io
import json

from marrow import config, cortex_bridge, hooks, storage

SID_SELF = "self1111-2222"
SID_OTHER = "othr9999-8888"


def _fresh_db(tmp_path):
    p = str(tmp_path / "d.db")
    storage.init_db(p).close()
    return p


def _ev(db, sid, role, content, *, channel="cli", ts="2026-07-17T04:00:00Z"):
    conn = storage.connect(db)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO events(session_id, timestamp, role, content, channel)"
                " VALUES(?,?,?,?,?)", (sid, ts, role, content, channel))
        return cur.lastrowid
    finally:
        conn.close()


def _cursor(sid):
    return hooks._load_replay_cursor(sid)


def _setup(monkeypatch, tmp_path, db, replay_extra=None):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "db_path", lambda: db)
    real = config.load

    def _patched():
        cfg = dict(real())
        rp = dict(cfg.get("replay", {}))
        if replay_extra:
            rp.update(replay_extra)
        cfg["replay"] = rp
        return cfg

    monkeypatch.setattr(config, "load", _patched)


# ── first-sight seed: no backfill ───────────────────────────────────────────

def test_first_sight_seeds_no_backfill(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db)
    _ev(db, SID_OTHER, "user", "old history one")
    _ev(db, SID_OTHER, "assistant", "old history two")
    # first sight → seed to MAX(id), inject nothing
    assert hooks._replay_context(SID_SELF, "cli") == ""
    assert _cursor(SID_SELF) == 2


def test_first_sight_empty_db_seeds_zero(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db)
    assert hooks._replay_context(SID_SELF, "cli") == ""
    assert _cursor(SID_SELF) == 0


# ── nothing new after seed ──────────────────────────────────────────────────

def test_nothing_new_empty_inject(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db)
    _ev(db, SID_OTHER, "user", "existing")
    hooks._replay_context(SID_SELF, "cli")  # seed
    assert hooks._replay_context(SID_SELF, "cli") == ""  # no new rows


# ── happy render + cursor advance ───────────────────────────────────────────

def test_render_and_cursor_advance(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db)
    hooks._replay_context(SID_SELF, "cli")  # seed at 0
    _ev(db, SID_OTHER, "user", "hey there", ts="2026-07-17T04:10:00Z")
    aid = _ev(db, SID_OTHER, "assistant", "hi back", ts="2026-07-17T04:11:00Z")
    out = hooks._replay_context(SID_SELF, "cli")
    assert out.startswith("## Recent replay from other sessions")
    assert "N: hey there" in out
    assert "Y: hi back" in out
    assert "othr" in out  # source sid[:4]
    assert "cli·" in out
    assert _cursor(SID_SELF) == aid
    # consumed → next call empty
    assert hooks._replay_context(SID_SELF, "cli") == ""


# ── turn grouping: consecutive user msgs = one turn ─────────────────────────

def test_consecutive_user_same_turn(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 1})
    hooks._replay_context(SID_SELF, "cli")
    _ev(db, SID_OTHER, "user", "part one", ts="2026-07-17T04:10:00Z")
    _ev(db, SID_OTHER, "user", "part two", ts="2026-07-17T04:10:30Z")
    _ev(db, SID_OTHER, "assistant", "reply", ts="2026-07-17T04:11:00Z")
    out = hooks._replay_context(SID_SELF, "cli")
    # both user msgs + assistant land in the single kept turn, no fold
    assert "part one" in out and "part two" in out and "reply" in out
    assert "more turns" not in out


# ── cap + fold ──────────────────────────────────────────────────────────────

def test_cap_and_fold(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 2})
    hooks._replay_context(SID_SELF, "cli")
    for i in range(4):  # 4 distinct turns
        _ev(db, SID_OTHER, "user", f"q{i}", ts=f"2026-07-17T05:0{i}:00Z")
        _ev(db, SID_OTHER, "assistant", f"a{i}", ts=f"2026-07-17T05:0{i}:30Z")
    out = hooks._replay_context(SID_SELF, "cli")
    # Keep the NEWEST turns; the older overflow folds (cursor advances to max_id
    # unconditionally, so the folded turns would be silenced forever otherwise).
    assert "q2" in out and "q3" in out          # newest kept
    assert "q0" not in out and "q1" not in out  # oldest folded
    assert "+2 earlier turns" in out
    # cursor advanced past ALL rows despite fold (ambient)
    conn = storage.connect(db)
    try:
        maxid = conn.execute("SELECT MAX(id) m FROM events").fetchone()["m"]
    finally:
        conn.close()
    assert _cursor(SID_SELF) == maxid


# ── per_msg_chars truncation ────────────────────────────────────────────────

def test_truncation(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"per_msg_chars": 10})
    hooks._replay_context(SID_SELF, "cli")
    _ev(db, SID_OTHER, "user", "abcdefghijklmnopqrstuvwxyz")
    out = hooks._replay_context(SID_SELF, "cli")
    assert "abcdefghi…" in out


# ── max_lines cap: newest lines win ─────────────────────────────────────────

def test_max_lines_caps_to_newest(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 1, "max_lines": 4})
    hooks._replay_context(SID_SELF, "cli")
    # a single turn (consecutive user msgs stay open) carrying 6 messages —
    # within max_turns=1 but over max_lines=4.
    for i in range(3):
        _ev(db, SID_OTHER, "user", f"u{i}", ts=f"2026-07-17T05:0{i}:00Z")
    _ev(db, SID_OTHER, "assistant", "a0", ts="2026-07-17T05:10:00Z")
    _ev(db, SID_OTHER, "assistant", "a1", ts="2026-07-17T05:11:00Z")
    _ev(db, SID_OTHER, "assistant", "a2", ts="2026-07-17T05:12:00Z")
    out = hooks._replay_context(SID_SELF, "cli")
    lines = [l for l in out.splitlines() if l.startswith("[")]
    assert len(lines) == 4
    assert "u0" not in out and "u1" not in out  # oldest dropped
    assert "u2" in out and "a2" in out          # newest kept


def test_max_lines_zero_disables_cap(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 1, "max_lines": 0})
    hooks._replay_context(SID_SELF, "cli")
    for i in range(3):
        _ev(db, SID_OTHER, "user", f"u{i}", ts=f"2026-07-17T05:0{i}:00Z")
    _ev(db, SID_OTHER, "assistant", "a0", ts="2026-07-17T05:10:00Z")
    _ev(db, SID_OTHER, "assistant", "a1", ts="2026-07-17T05:11:00Z")
    _ev(db, SID_OTHER, "assistant", "a2", ts="2026-07-17T05:12:00Z")
    out = hooks._replay_context(SID_SELF, "cli")
    lines = [l for l in out.splitlines() if l.startswith("[")]
    assert len(lines) == 6  # single turn, no line cap


# ── own-sid exclusion ───────────────────────────────────────────────────────

def test_own_sid_excluded(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db)
    hooks._replay_context(SID_SELF, "cli")
    _ev(db, SID_SELF, "user", "my own message")
    assert hooks._replay_context(SID_SELF, "cli") == ""


# ── source ct exclusion ─────────────────────────────────────────────────────

def test_source_ct_excluded(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db)
    hooks._replay_context(SID_SELF, "cli")
    _ev(db, SID_OTHER, "user", "cortex monologue", channel="ct")
    assert hooks._replay_context(SID_SELF, "cli") == ""


# ── destination channel exclusion ──────────────────────────────────────────

def test_destination_channel_excluded(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"exclude_target_channels": ["foo"]})
    _ev(db, SID_OTHER, "user", "should never reach an excluded channel")
    # a session ON an excluded channel receives nothing — no seed, no cursor write
    assert hooks._replay_context(SID_SELF, "foo") == ""
    assert _cursor(SID_SELF) is None


# ── enabled=false kills feature ─────────────────────────────────────────────

def test_enabled_false(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"enabled": False})
    _ev(db, SID_OTHER, "user", "hi")
    assert hooks._replay_context(SID_SELF, "cli") == ""
    assert _cursor(SID_SELF) is None


# ── F11: SessionStart seed, moves the first inject earlier ─────────────────

def _run_hook(monkeypatch, event, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr("sys.stdout", io.StringIO())
    import sys as _sys
    buf = io.StringIO()
    monkeypatch.setattr(_sys, "stdout", buf)
    rc = hooks.main([event])
    return rc, buf.getvalue()


def test_session_start_shows_last_turns_regardless_of_cursor(tmp_path, monkeypatch):
    # F11: SessionStart renders the last [replay].max_turns turns of other-
    # session activity even on first sight (fresh sid, no cursor yet) —
    # opening context is never empty just because the cursor never moved.
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db)
    aid = _ev(db, SID_OTHER, "user", "earlier chatter", ts="2026-07-17T04:00:00Z")
    _ev(db, SID_OTHER, "assistant", "earlier reply", ts="2026-07-17T04:00:30Z")

    rc, out = _run_hook(monkeypatch, "session_start", {"session_id": SID_SELF})
    assert rc == 0
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "## Recent replay from other sessions" in ctx
    assert "earlier chatter" in ctx and "earlier reply" in ctx
    # Cursor advanced forward to the seed's rendered cutoff (not left at None).
    assert _cursor(SID_SELF) == aid + 1


def test_session_start_seed_cursor_forward_only_no_repeat_on_turn1(tmp_path, monkeypatch):
    # The seed's cursor advance is forward-only to the rendered cutoff, so a
    # normal turn_inject call right after never re-shows the same lines.
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db)
    _ev(db, SID_OTHER, "user", "seeded content", ts="2026-07-17T04:00:00Z")
    _ev(db, SID_OTHER, "assistant", "seeded reply", ts="2026-07-17T04:00:30Z")

    rc, out = _run_hook(monkeypatch, "session_start", {"session_id": SID_SELF})
    assert rc == 0
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "seeded content" in ctx

    rc, out = _run_hook(
        monkeypatch, "turn_inject",
        {"session_id": SID_SELF, "prompt": "hi", "cwd": str(tmp_path)})
    assert rc == 0
    ctx2 = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""
    assert "seeded content" not in ctx2


def test_session_start_seed_then_new_activity_shows_on_turn1(tmp_path, monkeypatch):
    # Genuinely new activity landing AFTER the seed's cutoff, before her first
    # message, still surfaces on turn 1 as before.
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db)
    _ev(db, SID_OTHER, "user", "seeded content", ts="2026-07-17T04:00:00Z")
    _ev(db, SID_OTHER, "assistant", "seeded reply", ts="2026-07-17T04:00:30Z")

    rc, out = _run_hook(monkeypatch, "session_start", {"session_id": SID_SELF})
    assert rc == 0

    _ev(db, SID_OTHER, "user", "activity before her first message",
        ts="2026-07-17T04:10:00Z")
    _ev(db, SID_OTHER, "assistant", "reply before her first message",
        ts="2026-07-17T04:11:00Z")

    rc, out = _run_hook(
        monkeypatch, "turn_inject",
        {"session_id": SID_SELF, "prompt": "hi", "cwd": str(tmp_path)})
    assert rc == 0
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "activity before her first message" in ctx
    assert "seeded content" not in ctx  # already rendered by the seed


def test_session_start_seed_empty_db_seeds_zero(tmp_path, monkeypatch):
    # No other-session activity exists yet -> seed falls back to the old
    # empty-inject, cursor-at-zero behaviour (nothing to render).
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db)
    rc, out = _run_hook(monkeypatch, "session_start", {"session_id": SID_SELF})
    assert rc == 0
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "## Recent replay from other sessions" not in ctx
    assert _cursor(SID_SELF) == 0


# ── render-layer noise filter: slash commands + bot status output ───────────

SLASH_CMDS = ["/info", "/clear", "/resume", "/status", "/new", "/ct-wake"]
STATUS_LINE = ("Opus 5[high] | /Users/Gabrielle/.config/marrow/cortex | "
               "Health:ok | 1c1e9d7e | 3h28m | 13%(5h) 17%(7d) | 120.5k")
# Real messages that start with '/' or contain one — must survive.
KEEP_MSGS = [
    "/Users/Gabrielle/Desktop/tg-official-plugin-migration.md\n"
    "你先看看你爹这个plugin写得怎么样",
    "你是说/clear？我根本没有swap这个命令你在说哪个命令",
    "别急，那就/grill开始brainstorm，想清楚才写",
]


def test_slash_command_turns_dropped(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 10, "max_lines": 0})
    hooks._replay_context(SID_SELF, "cli")
    for i, cmd in enumerate(SLASH_CMDS):
        _ev(db, SID_OTHER, "user", cmd, ts=f"2026-07-17T06:0{i}:00Z")
    # every row dropped -> nothing renders at all
    assert hooks._replay_context(SID_SELF, "cli") == ""


def test_slash_command_with_short_args_dropped(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 10, "max_lines": 0})
    hooks._replay_context(SID_SELF, "cli")
    _ev(db, SID_OTHER, "user", "/ct-direction 去看看日程", ts="2026-07-17T06:00:00Z")
    assert hooks._replay_context(SID_SELF, "cli") == ""


def test_real_messages_with_slash_survive(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 10, "max_lines": 0})
    hooks._replay_context(SID_SELF, "cli")
    for i, msg in enumerate(KEEP_MSGS):
        _ev(db, SID_OTHER, "user", msg, ts=f"2026-07-17T06:1{i}:00Z")
        _ev(db, SID_OTHER, "assistant", f"ack{i}", ts=f"2026-07-17T06:1{i}:30Z")
    out = hooks._replay_context(SID_SELF, "cli")
    assert "tg-official-plugin-migration.md" in out
    assert "我根本没有swap这个命令" in out
    assert "那就/grill开始brainstorm" in out


def test_long_slash_prose_survives(tmp_path, monkeypatch):
    # Single line starting with '/' but far past the length cap = prose.
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 10, "max_lines": 0})
    hooks._replay_context(SID_SELF, "cli")
    msg = "/grill 这个方案我觉得还是有问题，你先把 replay 的过滤规则讲清楚再动手写代码"
    _ev(db, SID_OTHER, "user", msg, ts="2026-07-17T06:20:00Z")
    assert "replay 的过滤规则" in hooks._replay_context(SID_SELF, "cli")


def test_bot_status_line_dropped(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 10, "max_lines": 0,
                                       "per_msg_chars": 500})
    hooks._replay_context(SID_SELF, "cli")
    _ev(db, SID_OTHER, "assistant", STATUS_LINE, ts="2026-07-17T06:30:00Z")
    assert hooks._replay_context(SID_SELF, "cli") == ""


def test_empty_turn_leaves_no_shell(tmp_path, monkeypatch):
    # /info + its status reply = a whole turn of noise: no header, no bare
    # "N:"/"Y:" line, nothing.
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 10, "max_lines": 0,
                                       "per_msg_chars": 500})
    hooks._replay_context(SID_SELF, "cli")
    _ev(db, SID_OTHER, "user", "/info", ts="2026-07-17T06:40:00Z")
    _ev(db, SID_OTHER, "assistant", STATUS_LINE, ts="2026-07-17T06:40:30Z")
    out = hooks._replay_context(SID_SELF, "cli")
    assert out == ""


def test_dropped_turn_does_not_consume_turn_slot(tmp_path, monkeypatch):
    # 3 turns, the middle one pure noise. max_turns=2 must keep BOTH real
    # turns and print no fold line.
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 2, "max_lines": 0,
                                       "per_msg_chars": 500})
    hooks._replay_context(SID_SELF, "cli")
    _ev(db, SID_OTHER, "user", "q0", ts="2026-07-17T07:00:00Z")
    _ev(db, SID_OTHER, "assistant", "a0", ts="2026-07-17T07:00:30Z")
    _ev(db, SID_OTHER, "user", "/info", ts="2026-07-17T07:01:00Z")
    _ev(db, SID_OTHER, "assistant", STATUS_LINE, ts="2026-07-17T07:01:30Z")
    _ev(db, SID_OTHER, "user", "q1", ts="2026-07-17T07:02:00Z")
    _ev(db, SID_OTHER, "assistant", "a1", ts="2026-07-17T07:02:30Z")
    out = hooks._replay_context(SID_SELF, "cli")
    assert "q0" in out and "a0" in out and "q1" in out and "a1" in out
    assert "Health:ok" not in out
    assert "earlier turns" not in out
    assert len([ln for ln in out.splitlines() if ln.startswith("[")]) == 4


def test_drop_disabled_keeps_slash_commands(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 10, "max_lines": 0,
                                       "drop_slash_commands": False,
                                       "drop_patterns": []})
    hooks._replay_context(SID_SELF, "cli")
    _ev(db, SID_OTHER, "user", "/clear", ts="2026-07-17T07:10:00Z")
    assert "/clear" in hooks._replay_context(SID_SELF, "cli")


def test_bad_drop_pattern_is_ignored(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 10, "max_lines": 0,
                                       "drop_patterns": ["([unclosed"]})
    hooks._replay_context(SID_SELF, "cli")
    _ev(db, SID_OTHER, "user", "still talking", ts="2026-07-17T07:20:00Z")
    assert "still talking" in hooks._replay_context(SID_SELF, "cli")


# ── cortex path: dropped-noise rows must still advance last_note_ts ──────────

def _cortex_setup(monkeypatch, tmp_path, db, replay_extra=None):
    _setup(monkeypatch, tmp_path, db, replay_extra)
    monkeypatch.setenv("MARROW_CORTEX", "1")
    ws = tmp_path / "wake_state.json"
    monkeypatch.setattr(cortex_bridge, "_cortex_wake_state_path", lambda: ws)
    return ws


def _baseline(ws):
    return json.loads(ws.read_text()).get("last_note_ts")


def test_cortex_noise_newer_than_rendered_advances_cursor(tmp_path, monkeypatch):
    # real row @T1 then noise row @T2 (T2 > T1): the cursor must land on T2,
    # otherwise the noise row is re-selected and re-dropped on every turn.
    db = _fresh_db(tmp_path)
    ws = _cortex_setup(monkeypatch, tmp_path, db, {"max_turns": 10,
                                                   "max_lines": 0,
                                                   "per_msg_chars": 500})
    _ev(db, SID_OTHER, "user", "real talk", ts="2026-07-17T08:00:00Z")
    _ev(db, SID_OTHER, "user", "/info", ts="2026-07-17T08:01:00Z")
    out = hooks._replay_context("ctsid0000", "ct")
    assert "real talk" in out and "/info" not in out
    assert _baseline(ws) == "2026-07-17T08:01:00Z"
    # next turn sees nothing new — the noise row left the window
    assert hooks._replay_context("ctsid0000", "ct") == ""


def test_cortex_all_noise_batch_still_advances_cursor(tmp_path, monkeypatch):
    # whole batch is noise -> empty block, but the baseline must still move to
    # the newest scanned ts (the "stuck forever" regression).
    db = _fresh_db(tmp_path)
    ws = _cortex_setup(monkeypatch, tmp_path, db, {"max_turns": 10,
                                                   "max_lines": 0,
                                                   "per_msg_chars": 500})
    _ev(db, SID_OTHER, "user", "/info", ts="2026-07-17T09:00:00Z")
    _ev(db, SID_OTHER, "assistant", STATUS_LINE, ts="2026-07-17T09:00:30Z")
    assert hooks._replay_context("ctsid0000", "ct") == ""
    assert _baseline(ws) == "2026-07-17T09:00:30Z"
    assert hooks._replay_context("ctsid0000", "ct") == ""
    assert _baseline(ws) == "2026-07-17T09:00:30Z"


def test_cortex_empty_content_row_advances_cursor(tmp_path, monkeypatch):
    # pure-media bubble: strip_media_markers leaves nothing, so it can never
    # render for any caller — it must not pin the cursor either.
    db = _fresh_db(tmp_path)
    ws = _cortex_setup(monkeypatch, tmp_path, db, {"max_turns": 10,
                                                   "max_lines": 0})
    _ev(db, SID_OTHER, "user", '<image path="/x/y.png"/>',
        ts="2026-07-17T09:30:00Z")
    assert hooks._replay_context("ctsid0000", "ct") == ""
    assert _baseline(ws) == "2026-07-17T09:30:00Z"


def test_cortex_noise_advance_never_rewinds_baseline(tmp_path, monkeypatch):
    # a stale cutoff must never pull an already-advanced baseline backwards.
    db = _fresh_db(tmp_path)
    ws = _cortex_setup(monkeypatch, tmp_path, db, {"max_turns": 10,
                                                   "max_lines": 0,
                                                   "per_msg_chars": 500})
    _ev(db, SID_OTHER, "user", "old real", ts="2026-07-17T10:00:00Z")
    _ev(db, SID_OTHER, "user", "/info", ts="2026-07-17T10:01:00Z")
    ws.write_text(json.dumps({"last_note_ts": "2026-07-17T10:05:00Z"}))
    assert hooks._replay_context("ctsid0000", "ct") == ""
    assert _baseline(ws) == "2026-07-17T10:05:00Z"


# ── cortex path: row-id tie-break on a shared timestamp ─────────────────────

def test_cortex_same_second_real_after_noise_not_skipped(tmp_path, monkeypatch):
    # THE bug: a noise row @T advances the cursor to T; a REAL row landing
    # later but sharing the exact same timestamp string must still be
    # delivered, not skipped forever by a strict `timestamp > T` compare.
    db = _fresh_db(tmp_path)
    ws = _cortex_setup(monkeypatch, tmp_path, db, {"max_turns": 10,
                                                   "max_lines": 0,
                                                   "per_msg_chars": 500})
    _ev(db, SID_OTHER, "user", "/info", ts="2026-07-17T12:00:00Z")
    assert hooks._replay_context("ctsid0000", "ct") == ""
    assert _baseline(ws) == "2026-07-17T12:00:00Z"
    state = json.loads(ws.read_text())
    assert isinstance(state.get("last_note_row_id"), int)
    assert state.get("last_note_row_ts") == "2026-07-17T12:00:00Z"
    _ev(db, SID_OTHER, "user", "same-second real talk", ts="2026-07-17T12:00:00Z")
    out = hooks._replay_context("ctsid0000", "ct")
    assert "same-second real talk" in out
    # delivered once — a third read sees nothing new
    assert hooks._replay_context("ctsid0000", "ct") == ""


def test_cortex_same_second_noise_chain_advances_row_cursor(tmp_path, monkeypatch):
    # two same-second noise rows across separate batches: the id half of the
    # cursor must move past the second one too (ts is unchanged, so only the
    # id bound tracks it), or it sits in the window forever.
    db = _fresh_db(tmp_path)
    ws = _cortex_setup(monkeypatch, tmp_path, db, {"max_turns": 10,
                                                   "max_lines": 0,
                                                   "per_msg_chars": 500})
    _ev(db, SID_OTHER, "user", "/info", ts="2026-07-17T14:00:00Z")
    assert hooks._replay_context("ctsid0000", "ct") == ""
    row_id_1 = json.loads(ws.read_text())["last_note_row_id"]
    _ev(db, SID_OTHER, "user", "/info", ts="2026-07-17T14:00:00Z")
    assert hooks._replay_context("ctsid0000", "ct") == ""
    state = json.loads(ws.read_text())
    assert state["last_note_ts"] == "2026-07-17T14:00:00Z"
    assert state["last_note_row_id"] > row_id_1
    # a real event at the same second, arriving after both noise rows, still
    # shows — proves the id bound actually tracked the second noise row too
    _ev(db, SID_OTHER, "user", "finally real", ts="2026-07-17T14:00:00Z")
    assert "finally real" in hooks._replay_context("ctsid0000", "ct")


def test_cortex_migrates_timestamp_only_state(tmp_path, monkeypatch):
    # pre-fix state on disk carries only last_note_ts (no row-id cursor yet).
    # The first read after upgrade must resolve the row id from the DB,
    # exclude what predates it, deliver what's new, and persist the paired
    # row-id cursor for next time.
    db = _fresh_db(tmp_path)
    ws = _cortex_setup(monkeypatch, tmp_path, db, {"max_turns": 10,
                                                   "max_lines": 0,
                                                   "per_msg_chars": 500})
    _ev(db, SID_OTHER, "user", "already delivered", ts="2026-07-17T13:00:00Z")
    ws.write_text(json.dumps({"last_note_ts": "2026-07-17T13:00:00Z"}))
    _ev(db, SID_OTHER, "user", "new after migration", ts="2026-07-17T13:05:00Z")
    out = hooks._replay_context("ctsid0000", "ct")
    assert "new after migration" in out
    assert "already delivered" not in out
    state = json.loads(ws.read_text())
    assert state.get("last_note_ts") == "2026-07-17T13:05:00Z"
    assert isinstance(state.get("last_note_row_id"), int)
    assert state.get("last_note_row_ts") == "2026-07-17T13:05:00Z"


def test_replay_context_cursor_unaffected_by_noise(tmp_path, monkeypatch):
    # per-sid path uses rows[-1]["id"], not the render cutoff: an all-noise
    # batch still advances the cursor past it.
    db = _fresh_db(tmp_path)
    _setup(monkeypatch, tmp_path, db, {"max_turns": 10, "max_lines": 0,
                                       "per_msg_chars": 500})
    hooks._replay_context(SID_SELF, "cli")
    last = _ev(db, SID_OTHER, "user", "/info", ts="2026-07-17T11:00:00Z")
    assert hooks._replay_context(SID_SELF, "cli") == ""
    assert _cursor(SID_SELF) == last
