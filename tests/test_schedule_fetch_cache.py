"""render_daily cadence fetch cache: spawn cadence only when Reminders/Calendar
data mtime moved or the local date rolled; a failed fetch keeps the last good
data and retries next call. cadence is never spawned — _run_cadence is faked."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from marrow import schedule, timeutil


@pytest.fixture
def env(monkeypatch, tmp_path):
    binary = tmp_path / "cadence"
    binary.write_text("")
    state = {"mtime": 100.0, "fail": set(), "calls": [],
             "now": datetime(2026, 7, 10, 2, 0, tzinfo=timezone.utc)}

    def fake_run(args, _binary):
        state["calls"].append(args)
        kind = " ".join(args[:2]) + (" " + args[2] if args[0] == "rem" else "")
        if kind in state["fail"]:
            return ""
        today = state["now"].astimezone(timeutil._TZ).strftime("%Y-%m-%d")
        if args[0] == "cal":
            return json.dumps([{"calendar": "Work", "title": "Standup",
                                "start": f"{today}T09:00:00",
                                "end": f"{today}T09:15:00"}])
        if args[2] == "--all":
            return json.dumps([{"id": 7, "list": "Inbox", "title": "Pay rent",
                                "due_date": f"{today}T00:00:00"}])
        return "[]"

    monkeypatch.setattr(schedule, "_fetch_cache", {})
    monkeypatch.setattr(schedule, "_run_cadence", fake_run)
    monkeypatch.setattr(schedule, "get_data_mtime", lambda: state["mtime"])
    monkeypatch.setattr(timeutil, "utc_now", lambda: state["now"])
    monkeypatch.setattr(schedule, "_flag_note", lambda: "")
    monkeypatch.setattr(schedule, "_cal_exclude", lambda: set())
    monkeypatch.setattr(schedule, "_cal_keep_re", lambda: None)
    state["bin"] = str(binary)
    return state


def test_unchanged_mtime_reuses_last_fetch(env):
    first = schedule.render_daily(env["bin"])
    second = schedule.render_daily(env["bin"])
    assert len(env["calls"]) == 3
    assert "Pay rent" in second and "Standup" in second
    assert first.splitlines()[1:] == second.splitlines()[1:]


def test_mtime_change_refetches(env):
    schedule.render_daily(env["bin"])
    env["mtime"] = 101.0
    schedule.render_daily(env["bin"])
    assert len(env["calls"]) == 6


def test_date_rollover_refetches(env):
    schedule.render_daily(env["bin"])
    env["now"] = datetime(2026, 7, 11, 2, 0, tzinfo=timezone.utc)
    schedule.render_daily(env["bin"])
    assert len(env["calls"]) == 6
    assert ["cal", "read", "2026-07-11", "--json"] in env["calls"]


def test_failure_keeps_last_good_and_retries(env):
    schedule.render_daily(env["bin"])
    env["mtime"] = 101.0
    env["fail"] = {"rem read --all"}
    out = schedule.render_daily(env["bin"])
    assert "Pay rent" in out and "Standup" in out
    assert len(env["calls"]) == 6

    schedule.render_daily(env["bin"])
    assert len(env["calls"]) == 9

    env["fail"] = set()
    schedule.render_daily(env["bin"])
    schedule.render_daily(env["bin"])
    assert len(env["calls"]) == 12


def test_failure_after_rollover_drops_yesterday_cache(env):
    schedule.render_daily(env["bin"])
    env["now"] = datetime(2026, 7, 11, 2, 0, tzinfo=timezone.utc)
    env["fail"] = {"cal read", "rem read --all", "rem read --done"}
    out = schedule.render_daily(env["bin"])
    assert "Pay rent" not in out and "Standup" not in out
    assert schedule._fetch_cache["key"][1] == "2026-07-10"


def test_failure_without_cache_renders_nothing(env):
    env["fail"] = {"cal read", "rem read --all", "rem read --done"}
    assert schedule.render_daily(env["bin"]) == ""
    assert schedule._fetch_cache == {}
