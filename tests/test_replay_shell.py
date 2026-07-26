"""Per-shell cortex replay: self-channel exclude + per-shell cursor.

cli shell = regression baseline (exclude 'ct', cursor in wake_state.json);
tg shell drops its own 'tg' rows, keeps 'ct' rows, and keeps its cursor in the
shell ledger <shell_state_dir>/tg.json.
"""
from __future__ import annotations

import json

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


def test_shell_state_keys_carry_the_row_id_cursor():
    assert "last_note_row_id" in cortex_bridge._SHELL_STATE_KEYS
    assert "pending_note_row_id" in cortex_bridge._SHELL_STATE_KEYS
