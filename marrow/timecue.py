"""Time-cue parser: detect natural-language date references in prompt text.

Converts local-time cues (昨天, 上周X, N天前, etc.) to UTC ISO windows.
Day boundaries and tz conversion come from timeutil.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from . import timeutil

_CN_DIGIT = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_CN_WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


@dataclass
class TimeCue:
    since_utc: str   # UTC ISO, inclusive start
    until_utc: str   # UTC ISO, exclusive end
    stripped: str    # prompt text with the matched cue phrase removed


def _day(d: date) -> tuple[str, str]:
    return timeutil.local_day_range(d.isoformat())


def _span(first: date, last: date) -> tuple[str, str]:
    return _day(first)[0], _day(last)[1]


def _strip_and_collapse(text: str, match: re.Match) -> str:
    before = text[:match.start()].rstrip()
    after = text[match.end():].lstrip()
    if before and after:
        return before + " " + after
    return (before + after).strip()


def _cn_to_int(s: str) -> int | None:
    """Parse a short CN numeral string (e.g. (七), (十), (二十)) or arabic digit string."""
    s = s.strip()
    if s.isdigit():
        return int(s)
    if len(s) == 1 and s in _CN_DIGIT:
        return _CN_DIGIT[s]
    if s == "十":
        return 10
    if len(s) == 2 and s[0] == "十" and s[1] in _CN_DIGIT:
        return 10 + _CN_DIGIT[s[1]]
    if len(s) == 2 and s[0] in _CN_DIGIT and s[1] == "十":
        return _CN_DIGIT[s[0]] * 10
    if len(s) == 3 and s[0] in _CN_DIGIT and s[1] == "十" and s[2] in _CN_DIGIT:
        return _CN_DIGIT[s[0]] * 10 + _CN_DIGIT[s[2]]
    return None


# ── pattern list — ordered; first match wins ─────────────────────────────────
# Each entry: (compiled_regex, handler(match, now_local) -> (since, until) or None)
# Handler returns None to signal "future cue → skip".

def _h_yesterday(m: re.Match, now_local: datetime):
    d = (now_local - timedelta(days=1)).date()
    return _day(d)


def _h_today(m: re.Match, now_local: datetime):
    return _day(now_local.date())


def _h_qiantian(m: re.Match, now_local: datetime):
    d = (now_local - timedelta(days=2)).date()
    return _day(d)


def _h_daqiantian(m: re.Match, now_local: datetime):
    d = (now_local - timedelta(days=3)).date()
    return _day(d)


def _h_n_days_ago_cn(m: re.Match, now_local: datetime):
    n = _cn_to_int(m.group(1))
    if n is None or n < 1 or n > 30:
        return None
    d = (now_local - timedelta(days=n)).date()
    return _day(d)


def _h_n_days_ago_en(m: re.Match, now_local: datetime):
    n = int(m.group(1))
    if n < 1 or n > 30:
        return None
    d = (now_local - timedelta(days=n)).date()
    return _day(d)


def _h_last_week(m: re.Match, now_local: datetime):
    # Previous Mon-Sun full week
    today = now_local.date()
    this_mon = today - timedelta(days=today.weekday())
    prev_mon = this_mon - timedelta(days=7)
    prev_sun = prev_mon + timedelta(days=6)
    return _span(prev_mon, prev_sun)


def _h_last_week_day(m: re.Match, now_local: datetime):
    # (上周X / 上星期X): that specific weekday in the previous week
    wd = _CN_WEEKDAY.get(m.group(1))
    if wd is None:
        return None
    today = now_local.date()
    this_mon = today - timedelta(days=today.weekday())
    prev_mon = this_mon - timedelta(days=7)
    target = prev_mon + timedelta(days=wd)
    return _day(target)


def _h_this_week(m: re.Match, now_local: datetime):
    # This week Mon..today
    today = now_local.date()
    this_mon = today - timedelta(days=today.weekday())
    return _span(this_mon, today)


def _h_weekday_bare(m: re.Match, now_local: datetime):
    # (周X / 星期X) no prefix: most recent past occurrence within last 7 days
    wd = _CN_WEEKDAY.get(m.group(1))
    if wd is None:
        return None
    today = now_local.date()
    for delta in range(7):
        candidate = today - timedelta(days=delta)
        if candidate.weekday() == wd:
            return _day(candidate)
    return None


def _h_last_month(m: re.Match, now_local: datetime):
    today = now_local.date()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return _span(first_prev, last_prev)


def _h_month_day(m: re.Match, now_local: datetime):
    month = int(m.group(1))
    day = int(m.group(2))
    today = now_local.date()
    try:
        candidate = date(today.year, month, day)
        if candidate > today:
            candidate = date(today.year - 1, month, day)
        return _day(candidate)
    except ValueError:
        return None


def _h_day_of_month(m: re.Match, now_local: datetime):
    day = int(m.group(1))
    if day < 1 or day > 31:
        return None
    today = now_local.date()
    try:
        candidate = date(today.year, today.month, day)
        if candidate > today:
            # Go to previous month
            first_this = today.replace(day=1)
            prev_last = first_this - timedelta(days=1)
            candidate = date(prev_last.year, prev_last.month, day)
        return _day(candidate)
    except ValueError:
        return None


def _h_tomorrow(m: re.Match, now_local: datetime):
    return None  # future → skip


def _h_next_week(m: re.Match, now_local: datetime):
    return None  # future → skip


# Ordered list of (pattern, handler)
_PATTERNS: list[tuple[re.Pattern, object]] = [
    # Future cues — must come before bare (周X) to avoid partial match
    (re.compile(r"明天|明早|明晚|tomorrow", re.IGNORECASE), _h_tomorrow),
    (re.compile(r"下周|下星期|next\s+week", re.IGNORECASE), _h_next_week),

    # Specific past cues
    (re.compile(r"大前天"), _h_daqiantian),
    (re.compile(r"前天"), _h_qiantian),
    (re.compile(r"昨天|昨晚|昨夜|yesterday", re.IGNORECASE), _h_yesterday),
    (re.compile(r"今天|今早|今天早上|今晚|today", re.IGNORECASE), _h_today),

    # N days ago — CN numerals first (more specific)
    (re.compile(r"([一二两三四五六七八九十]{1,3})天前"), _h_n_days_ago_cn),
    (re.compile(r"(\d{1,2})\s*天前"), _h_n_days_ago_cn),
    (re.compile(r"(\d{1,2})\s*days?\s+ago", re.IGNORECASE), _h_n_days_ago_en),

    # Last week with specific day — must come before bare (上周)
    (re.compile(r"(?:上周|上星期)([一二三四五六日天])"), _h_last_week_day),

    # Whole last week
    (re.compile(r"上周|上星期|last\s+week", re.IGNORECASE), _h_last_week),

    # This week
    (re.compile(r"这周|本周|this\s+week", re.IGNORECASE), _h_this_week),

    # Bare weekday (no prefix) — within last 7 days
    (re.compile(r"(?:周|星期)([一二三四五六日天])"), _h_weekday_bare),

    # Last month
    (re.compile(r"上个月|last\s+month", re.IGNORECASE), _h_last_month),

    # X月X号 / X月X日
    (re.compile(r"(\d{1,2})月(\d{1,2})[号日]"), _h_month_day),

    # N号 alone (day of current month)
    (re.compile(r"(?<!\d)(\d{1,2})号(?!\d)"), _h_day_of_month),
]


def parse_time_cue(text: str, now: datetime | None = None) -> TimeCue | None:
    """Detect the first natural-language time cue in text (by position).

    Scans all patterns, picks the match at the earliest text position.
    Returns TimeCue(since_utc, until_utc, stripped) or None if no cue found
    or cue refers to the future.
    """
    now_local = timeutil.to_local(now) if now is not None else timeutil.local_now()
    best_pos: int = len(text) + 1
    best_match: re.Match | None = None
    best_handler = None

    for pat, handler in _PATTERNS:
        m = pat.search(text)
        if m is None:
            continue
        if m.start() < best_pos:
            best_pos = m.start()
            best_match = m
            best_handler = handler

    if best_match is None:
        return None

    result = best_handler(best_match, now_local)
    if result is None:
        return None  # future cue
    since, until = result
    stripped = _strip_and_collapse(text, best_match)
    return TimeCue(since_utc=since, until_utc=until, stripped=stripped)
