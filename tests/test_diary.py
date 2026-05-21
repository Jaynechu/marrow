"""Tests for marrow/diary.py. LLM faked — prompt quality not under test;
day-boundary, per-session map-reduce, idempotency, dual triggers are.

Melbourne is UTC+10 (AEST) on these dates; diary_day(utc) = (utc+10h-4h)
= (utc+6h).date(). So UTC 18:00 rolls into the next diary day; a local
02:00 (UTC 16:00) still counts as the previous day.
"""
from __future__ import annotations

import datetime as dt

import pytest

from marrow import diary, storage


class FakeLLM:
    def __init__(self, digest="digest: did X"):
        self.digest = digest
        self.calls: list[str] = []
        self.digest_bodies: list[str] = []
        self.stitch_bodies: list[str] = []

    def call(self, role, body, *, tier="cheap"):
        self.calls.append(role)
        if role == "day-digest":
            self.digest_bodies.append(body)
            return self.digest
        if role == "stitch":
            self.stitch_bodies.append(body)
            return "woven strand with X"
        if role == "diary":
            # echo the digest so a re-run with a different digest yields
            # different diary text (force-overwrite test depends on this)
            return f"今天我们一起把 X 做完了。[{self.digest}]"
        return ""

    def n(self, role):
        return self.calls.count(role)


def _ev(conn, sid, ts, role, content):
    conn.execute("INSERT INTO events(session_id,timestamp,role,content) "
                 "VALUES(?,?,?,?)", (sid, ts, role, content))


def _session(conn, sid, hh, n_user=4):
    # n_user user turns (+ a reply each) inside diary day 2026-05-16.
    # Default 4 clears _SKIP_DROP_MAX (3) and lands in the judge window.
    for i in range(n_user):
        _ev(conn, sid, f"2026-05-16T{hh:02d}:{i:02d}:00Z", "user", f"msg {i}")
        _ev(conn, sid, f"2026-05-16T{hh:02d}:{i:02d}:30Z", "assistant", "ok")


@pytest.fixture()
def db(tmp_path):
    p = str(tmp_path / "t.db")
    conn = storage.init_db(p)
    # all map to diary day 2026-05-16 (utc+6h within that date);
    # 4 user turns each -> survive the skip filter, kept
    _session(conn, "s1", 2)
    _session(conn, "s2", 9)
    conn.commit()
    return p, conn


# ── day boundary ──────────────────────────────────────────────────────────────

def test_diary_day_local_0400_cutoff():
    # UTC 18:00 -> local next-day 04:00 -> rolls to next diary day
    assert diary._diary_day("2026-05-16T17:00:00Z") == "2026-05-16"
    assert diary._diary_day("2026-05-16T18:00:00Z") == "2026-05-17"
    # local 02:00 (UTC 16:00) counts as previous day (late-night spillover)
    assert diary._diary_day("2026-05-16T16:00:00Z") == "2026-05-16"


def test_routine_target_is_just_closed_day(monkeypatch):
    fixed = dt.datetime(2026, 5, 18, 4, 30, tzinfo=diary._TZ)

    class _DT(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(diary._dt, "datetime", _DT)
    assert diary._routine_target() == "2026-05-17"


# ── grouping / pending ────────────────────────────────────────────────────────

def test_day_events_only_that_diary_day(db):
    _, conn = db
    _ev(conn, "s9", "2026-05-16T18:00:00Z", "user", "next day")  # -> 05-17
    conn.commit()
    evs = diary.day_events(conn, "2026-05-16")
    assert {e["session_id"] for e in evs} == {"s1", "s2"}


def test_pending_days_excludes_written(db):
    p, conn = db
    assert diary.pending_days(conn) == ["2026-05-16"]
    conn.execute("INSERT INTO diary(date,content) VALUES('2026-05-16','x')")
    conn.commit()
    assert diary.pending_days(conn) == []


# ── per-session map-reduce ────────────────────────────────────────────────────

def test_run_day_one_digest_per_session(db):
    p, conn = db
    f = FakeLLM()
    assert diary.run_day(conn, "2026-05-16", f, db=p) is True
    assert f.n("day-digest") == 2          # s1 + s2, not one whole-day blob
    assert f.n("stitch") == 1              # 2 sessions woven once
    assert f.n("diary") == 1
    row = conn.execute(
        "SELECT content,session_ids FROM diary WHERE date='2026-05-16'"
    ).fetchone()
    assert "X" in row["content"]
    assert row["session_ids"] == "s1,s2"


def test_single_session_skips_stitch(tmp_path):
    p = str(tmp_path / "one.db")
    conn = storage.init_db(p)
    _session(conn, "solo", 2)
    conn.commit()
    f = FakeLLM()
    assert diary.run_day(conn, "2026-05-16", f, db=p) is True
    assert f.n("day-digest") == 1
    assert f.n("stitch") == 0              # nothing to weave, digest is strand
    assert f.n("diary") == 1


def test_stitch_span_tag_carries_local_date(tmp_path):
    # Two sessions in ONE diary day (2026-05-16) but different local dates:
    # an afternoon one (local 05-16) and a post-midnight one (local 05-17,
    # still <04:00 so same diary day). Tag must carry the date so haiku
    # keeps real order instead of sorting 01:00 before 14:00.
    p = str(tmp_path / "cross.db")
    conn = storage.init_db(p)
    for i in range(4):  # afternoon: UTC 04:00 -> local 14:00
        _ev(conn, "pm", f"2026-05-16T04:0{i}:00Z", "user", f"a{i}")
        _ev(conn, "pm", f"2026-05-16T04:0{i}:30Z", "assistant", "ok")
    for i in range(4):  # next-midnight: UTC 15:00 -> local 01:00 (05-17)
        _ev(conn, "am", f"2026-05-16T15:0{i}:00Z", "user", f"b{i}")
        _ev(conn, "am", f"2026-05-16T15:0{i}:30Z", "assistant", "ok")
    conn.commit()
    f = FakeLLM()
    assert diary.run_day(conn, "2026-05-16", f, db=p) is True
    body = f.stitch_bodies[0]
    assert "05-16 14:00" in body and "05-17 01:00" in body
    assert body.index("05-16 14:00") < body.index("05-17 01:00")


def test_oversized_session_is_chunked(db):
    p, conn = db
    big = "x" * (diary._SESSION_CHAR_CAP + diary._CHUNK_CHARS)
    _ev(conn, "s3", "2026-05-16T10:00:00Z", "user", big)
    for i in range(1, 4):  # extra turns so s3 clears the skip filter
        _ev(conn, "s3", f"2026-05-16T10:0{i}:00Z", "user", "more")
    conn.commit()
    f = FakeLLM()
    diary.run_day(conn, "2026-05-16", f, db=p)
    # s1 (1) + s2 (1) + s3 chunked (>=2) -> more than 3 digest calls
    assert f.n("day-digest") >= 4


def test_idempotent_skip(db):
    p, conn = db
    diary.run_day(conn, "2026-05-16", FakeLLM(), db=p)
    f2 = FakeLLM()
    assert diary.run_day(conn, "2026-05-16", f2, db=p) is False
    assert f2.calls == []


# ── same-day correction (force overwrite) vs catchup idempotency ──────────────

def test_force_overwrites_existing_diary(db):
    # A late session closes after the 04:00 routine already wrote the day.
    # An explicit forced re-run MUST replace the row + lessons-free content,
    # keeping date PK stable; catchup default path stays skip-if-exists.
    p, conn = db
    diary.run_day(conn, "2026-05-16", FakeLLM(digest="first pass"), db=p)
    first = conn.execute(
        "SELECT content FROM diary WHERE date='2026-05-16'").fetchone()
    f2 = FakeLLM()
    assert diary.run_day(conn, "2026-05-16", f2, db=p, force=True) is True
    assert f2.n("diary") == 1                       # actually re-wrote
    rows = conn.execute(
        "SELECT COUNT(*) c FROM diary WHERE date='2026-05-16'").fetchone()
    assert rows["c"] == 1                           # PK stable, no dup
    row = conn.execute(
        "SELECT content,updated_at,created_at FROM diary "
        "WHERE date='2026-05-16'").fetchone()
    assert row["content"] != first["content"]       # overwritten
    aud = conn.execute(
        "SELECT action FROM audit_log WHERE target_table='diary' "
        "AND target_id='2026-05-16' ORDER BY id DESC LIMIT 1").fetchone()
    assert aud["action"] == "update"                # not a silent insert


def test_catchup_default_still_idempotent(db):
    # Without force, an existing row is never overwritten — unattended
    # catchup/routine stays idempotent (no LLM spent).
    p, conn = db
    diary.run_day(conn, "2026-05-16", FakeLLM(), db=p)
    f2 = FakeLLM()
    assert diary.run_day(conn, "2026-05-16", f2, db=p) is False
    assert f2.calls == []
    assert diary.run(conn, f2, db=p, catchup=True) == []
    assert f2.calls == []


def test_run_force_flag_threads_to_run_day(db):
    p, conn = db
    diary.run_day(conn, "2026-05-16", FakeLLM(), db=p)
    out = diary.run(conn, FakeLLM(), db=p, day="2026-05-16", force=True)
    assert out == ["2026-05-16"]


# ── multi-process app-lock ────────────────────────────────────────────────────

def test_lock_serializes_separate_holders(tmp_path):
    import os
    lf = str(tmp_path / "diary.lock")
    with diary._app_lock(lf):
        # a second non-blocking acquire from another fd must fail while held
        with pytest.raises(BlockingIOError):
            with diary._app_lock(lf, blocking=False):
                pass
    # released after the block — re-acquire succeeds
    with diary._app_lock(lf, blocking=False):
        pass
    assert os.path.exists(lf)


def test_lock_releases_on_exception(tmp_path):
    lf = str(tmp_path / "diary.lock")
    with pytest.raises(RuntimeError):
        with diary._app_lock(lf):
            raise RuntimeError("boom")
    # lock must be free again despite the exception
    with diary._app_lock(lf, blocking=False):
        pass


def test_main_holds_lock_around_run(db, monkeypatch, tmp_path):
    # main() must wrap run() in the app-lock so routine/catchup/manual
    # serialize instead of colliding on the diary date PK.
    p, conn = db
    seen = {}
    real = diary._app_lock

    def spy(path=None, blocking=True):
        from pathlib import Path
        seen["path"] = path or str(
            Path(diary.config.DATA_DIR) / "diary.lock")
        return real(path, blocking=blocking)

    monkeypatch.setattr(diary, "_app_lock", spy)
    monkeypatch.setattr(diary.config, "db_path", lambda: p)
    monkeypatch.setattr(diary.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(diary.storage, "connect", lambda _p: conn)
    monkeypatch.setattr(diary, "LLMClient", lambda **k: FakeLLM())
    # main() closes conn in finally; assertions only read `seen`
    assert diary.main(["--day", "2026-05-16"]) == 0
    assert "path" in seen and seen["path"].endswith(".lock")


# ── _routine_target boundary (00:00–03:59 belongs to previous diary day) ──────

def _freeze_now(monkeypatch, when):
    class _DT(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return when

    monkeypatch.setattr(diary._dt, "datetime", _DT)


def test_routine_target_at_0359_is_two_days_back(monkeypatch):
    # 03:59 May 18 local is still inside diary day May 17's window
    # ([May17 04:00, May18 04:00)); the last FULLY closed day is May 16.
    _freeze_now(monkeypatch, dt.datetime(2026, 5, 18, 3, 59, tzinfo=diary._TZ))
    assert diary._routine_target() == "2026-05-16"


def test_routine_target_at_0401_is_just_closed_day(monkeypatch):
    # 04:01 May 18: diary day May 17 just closed at 04:00 -> target May 17.
    _freeze_now(monkeypatch, dt.datetime(2026, 5, 18, 4, 1, tzinfo=diary._TZ))
    assert diary._routine_target() == "2026-05-17"




# ── dual triggers ─────────────────────────────────────────────────────────────

def test_catchup_caps_and_alerts(db, monkeypatch):
    # Pin "today" to 2026-05-17 so the 7d window deterministically covers
    # the fixture's 2026-05-16 base + 5 days before it, independent of when
    # the test runs.
    p, conn = db
    pinned = dt.date(2026, 5, 17)

    class _D(dt.date):
        @classmethod
        def today(cls):
            return pinned

    class _DT(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 5, 17, 4, 30, tzinfo=diary._TZ)

    monkeypatch.setattr(diary._dt, "date", _D)
    monkeypatch.setattr(diary._dt, "datetime", _DT)
    base = dt.date(2026, 5, 16)
    for i in range(1, 6):  # 5 extra missing diary days
        d = base - dt.timedelta(days=i)
        _ev(conn, "s", f"{d.isoformat()}T08:00:00Z", "user", "x")
    conn.commit()
    written = diary.run(conn, FakeLLM(), db=p, catchup=True)
    assert len(written) == diary.CATCHUP_MAX
    al = conn.execute(
        "SELECT message FROM alerts WHERE type='routine'").fetchone()
    assert al and "still pending" in al["message"]


def test_run_explicit_day(db):
    p, conn = db
    assert diary.run(conn, FakeLLM(), db=p, day="2026-05-16") == ["2026-05-16"]


# ── skip filter ───────────────────────────────────────────────────────────────

def test_low_turn_session_hard_dropped(tmp_path):
    # <= _SKIP_DROP_MAX user turns -> never reaches haiku
    p = str(tmp_path / "lo.db")
    conn = storage.init_db(p)
    _session(conn, "lo", 3, n_user=diary._SKIP_DROP_MAX)
    conn.commit()
    f = FakeLLM()
    assert diary.run_day(conn, "2026-05-16", f, db=p) is True
    assert f.n("day-digest") == 0          # hard-dropped in code
    row = conn.execute(
        "SELECT content,session_ids FROM diary WHERE date='2026-05-16'"
    ).fetchone()
    assert row["content"] == "—"           # placeholder, whole day trivial
    assert row["session_ids"] == ""


def test_short_session_skip_drops(db):
    # 4-turn sessions route to DIGEST_SHORT; SKIP is honoured -> dropped
    p, conn = db
    f = FakeLLM(digest="SKIP")
    assert diary.run_day(conn, "2026-05-16", f, db=p) is True
    assert f.n("day-digest") == 2
    assert f.n("stitch") == 0 and f.n("diary") == 0
    assert conn.execute(
        "SELECT content FROM diary WHERE date='2026-05-16'"
    ).fetchone()["content"] == "—"


def test_long_session_skip_not_honoured(tmp_path):
    # >_SKIP_JUDGE_MAX turns route to DIGEST_LONG: even if haiku returns
    # SKIP, the session is kept (stub digest), heavy work never vanishes
    p = str(tmp_path / "long.db")
    conn = storage.init_db(p)
    _session(conn, "lng", 2, n_user=diary._SKIP_JUDGE_MAX + 5)
    conn.commit()
    f = FakeLLM(digest="SKIP")
    assert diary.run_day(conn, "2026-05-16", f, db=p) is True
    row = conn.execute(
        "SELECT content,session_ids FROM diary WHERE date='2026-05-16'"
    ).fetchone()
    assert row["content"] != "—" and row["session_ids"] == "lng"


def test_short_session_routes_to_short_prompt(tmp_path):
    # routing is by code, not haiku self-classification
    p = str(tmp_path / "r.db")
    conn = storage.init_db(p)
    _session(conn, "sh", 2, n_user=6)            # 6 -> SHORT
    _session(conn, "lg", 9, n_user=diary._SKIP_JUDGE_MAX + 5)  # -> LONG
    conn.commit()
    f = FakeLLM()
    diary.run_day(conn, "2026-05-16", f, db=p)
    short_in = any("short session" in b for b in f.digest_bodies)
    long_in = any("long session" in b for b in f.digest_bodies)
    assert short_in and long_in
