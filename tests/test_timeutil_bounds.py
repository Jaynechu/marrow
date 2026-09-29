"""timeutil input side: local_bound_to_utc + local_day_range.

conftest pins timeutil's tz to Australia/Melbourne (AEST +10 / AEDT +11).
"""
from __future__ import annotations

import pytest

from marrow import timeutil


@pytest.mark.parametrize("value, expected", [
    ("2026-09-30", "2026-09-29T14:00:00Z"),
    ("2026-09-30 14:30", "2026-09-30T04:30:00Z"),
    ("2026-09-30T14:30", "2026-09-30T04:30:00Z"),
    ("2026-09-30 14:30:15", "2026-09-30T04:30:15Z"),
    ("2026-09-30T14:30:15", "2026-09-30T04:30:15Z"),
    ("  2026-09-30 14:30  ", "2026-09-30T04:30:00Z"),
    ("2026-01-10", "2026-01-09T13:00:00Z"),
])
def test_local_date_and_naive_datetime(value, expected):
    assert timeutil.local_bound_to_utc(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("2026-09-30T14:30:00Z", "2026-09-30T14:30:00Z"),
    ("2026-09-30T14:30:00z", "2026-09-30T14:30:00Z"),
    ("2026-09-30T14:30:00.123Z", "2026-09-30T14:30:00Z"),
    ("2026-09-30 14:30Z", "2026-09-30T14:30:00Z"),
    ("2026-09-30T14:30:00+08:00", "2026-09-30T06:30:00Z"),
    ("2026-09-30T14:30:00+0800", "2026-09-30T06:30:00Z"),
    ("2026-09-30T14:30:00-05:00", "2026-09-30T19:30:00Z"),
    ("2026-09-30T14:30:00+00:00", "2026-09-30T14:30:00Z"),
])
def test_explicit_zone_respected(value, expected):
    assert timeutil.local_bound_to_utc(value) == expected


@pytest.mark.parametrize("value", [
    "", "   ", "yesterday", "2026-9-30", "2026-02-30", "2026-09-30 25:00",
    "30/09/2026", "2026-09-30Z", "2026-09-30T14", "1759240800", None,
])
def test_invalid_raises_value_error(value):
    with pytest.raises(ValueError):
        timeutil.local_bound_to_utc(value)


def test_dst_end_day_is_25h():
    start, end = timeutil.local_day_range("2026-04-05")
    assert (start, end) == ("2026-04-04T13:00:00Z", "2026-04-05T14:00:00Z")
    assert timeutil.local_bound_to_utc("2026-04-05") == start
    assert timeutil.local_bound_to_utc("2026-04-06") == end
    assert timeutil.local_bound_to_utc("2026-04-05 12:00") == "2026-04-05T02:00:00Z"


def test_dst_start_day_is_23h():
    start, end = timeutil.local_day_range("2026-10-04")
    assert (start, end) == ("2026-10-03T14:00:00Z", "2026-10-04T13:00:00Z")
    assert timeutil.local_bound_to_utc("2026-10-04") == start
    assert timeutil.local_bound_to_utc("2026-10-05") == end
    assert timeutil.local_bound_to_utc("2026-10-04 12:00") == "2026-10-04T01:00:00Z"


def test_local_day_range_bad_date():
    with pytest.raises(ValueError):
        timeutil.local_day_range("2026-13-01")


def test_render_roundtrip():
    utc = timeutil.local_bound_to_utc("2026-09-30 09:05")
    assert timeutil.utc_iso_to_local_datetime(utc) == "2026-09-30 09:05"
    assert timeutil.utc_iso_to_local_hm(utc) == "09:05"
    assert timeutil.utc_iso_to_local_hm("garbage") == "??:??"
    assert timeutil.utc_iso_to_local_hm("garbage", default=None) is None


def test_sql_bound_orders_z_and_millis_rows_by_instant():
    bound = timeutil.sql_bound("2026-09-29T14:00:00Z")
    assert bound == "2026-09-29T14:00:00"
    before = ["2026-09-29T13:59:59Z", "2026-09-29T13:59:59.999Z"]
    at_or_after = ["2026-09-29T14:00:00Z", "2026-09-29T14:00:00.000Z",
                   "2026-09-29T14:00:00.001Z", "2026-09-29T14:00:01Z"]
    assert all(ts < bound for ts in before)
    assert all(ts >= bound for ts in at_or_after)
    assert timeutil.sql_bound("2026-09-29T14:00:00") == "2026-09-29T14:00:00"
