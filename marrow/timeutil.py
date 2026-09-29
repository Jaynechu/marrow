"""The single timezone boundary for marrow.

DB stores UTC ISO strings ("...Z"). Anything entering from a user or model is
read as configured local time (config.get_tz()) and converted to UTC here;
anything shown to a user or model is converted UTC -> local here. No other
module does its own tz conversion (tests/test_tz_boundary.py enforces it).
"""
from __future__ import annotations

import datetime
import re

from . import config as _config

_TZ = _config.get_tz()
_UTC = datetime.timezone.utc
_UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"
_BOUND_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)


# ── now ──────────────────────────────────────────────────────────────────────

def utc_now() -> datetime.datetime:
    return datetime.datetime.now(_UTC)


def local_now() -> datetime.datetime:
    return utc_now().astimezone(_TZ)


def local_today() -> datetime.date:
    return local_now().date()


# ── parse / convert ──────────────────────────────────────────────────────────

def _parse(s, naive_tz: datetime.tzinfo) -> datetime.datetime | None:
    raw = (s or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=naive_tz)


def parse_utc(s) -> datetime.datetime | None:
    """ISO string -> aware UTC datetime; naive input is UTC. None if empty/invalid."""
    dt = _parse(s, _UTC)
    return dt.astimezone(_UTC) if dt is not None else None


def parse_local(s) -> datetime.datetime | None:
    """ISO string -> aware datetime; naive input is configured local time.
    Offsets in the input are kept. None if empty/invalid."""
    return _parse(s, _TZ)


def to_local(value) -> datetime.datetime | None:
    """UTC ISO string (naive = UTC) or aware datetime -> aware local datetime."""
    dt = parse_utc(value) if isinstance(value, str) else value
    return dt.astimezone(_TZ) if dt is not None else None


def epoch_to_local(epoch: float) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(epoch, _UTC).astimezone(_TZ)


def local_at(d: datetime.date, hour: int = 0, minute: int = 0,
             second: int = 0) -> datetime.datetime:
    """Aware datetime for a local wall-clock time on local calendar day d."""
    return datetime.datetime(d.year, d.month, d.day, hour, minute, second, tzinfo=_TZ)


def fmt_utc(dt: datetime.datetime) -> str:
    """Datetime -> UTC 'YYYY-MM-DDTHH:MM:SSZ'. Naive input is configured local time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_TZ)
    return dt.astimezone(_UTC).strftime(_UTC_FMT)


# ── local days and input bounds ──────────────────────────────────────────────

def local_day_bounds(d: datetime.date) -> tuple[datetime.datetime, datetime.datetime]:
    """(start, end) aware UTC datetimes of local calendar day d, end exclusive.
    DST days come out 23h / 25h long."""
    start = local_at(d)
    end = local_at(d + datetime.timedelta(days=1))
    return start.astimezone(_UTC), end.astimezone(_UTC)


def local_day_range(date_str: str) -> tuple[str, str]:
    """YYYY-MM-DD local day -> (since_utc, until_utc) ISO strings.
    ValueError on a malformed date."""
    s, e = local_day_bounds(datetime.date.fromisoformat(date_str))
    return s.strftime(_UTC_FMT), e.strftime(_UTC_FMT)


def local_bound_to_utc(value: str) -> str:
    """User/model time bound -> UTC 'YYYY-MM-DDTHH:MM:SSZ'.

    'YYYY-MM-DD' = start of that local day; 'YYYY-MM-DD HH:MM[:SS]' (or with
    'T') = local time; a trailing 'Z' or '+HH:MM' offset is respected as-is.
    ValueError on anything else."""
    raw = (value or "").strip().upper()
    if not _BOUND_RE.match(raw):
        raise ValueError(
            f"bad time {value!r}: expected YYYY-MM-DD, YYYY-MM-DD HH:MM[:SS]"
            " (local time) or ISO with Z/offset")
    if len(raw) == 10:
        return fmt_utc(local_at(datetime.date.fromisoformat(raw)))
    dt = parse_local(raw)
    if dt is None:
        raise ValueError(f"bad time {value!r}")
    return fmt_utc(dt)


# ── render ───────────────────────────────────────────────────────────────────

def utc_iso_to_local_date(s: str) -> str:
    """UTC ISO string -> YYYY-MM-DD in configured local time.
    Falls back to the first 10 chars on parse error."""
    if not s:
        return ""
    local = to_local(s)
    return local.strftime("%Y-%m-%d") if local else s[:10]


def utc_iso_to_local_datetime(s: str) -> str:
    """UTC ISO string -> 'YYYY-MM-DD HH:MM' in configured local time.
    Falls back to the first 16 chars (T -> space) on parse error."""
    if not s:
        return ""
    local = to_local(s)
    return local.strftime("%Y-%m-%d %H:%M") if local else s[:16].replace("T", " ")


def utc_iso_to_local_hm(s: str, default: str | None = "??:??") -> str | None:
    """UTC ISO string -> local 'HH:MM'; `default` on empty/invalid input."""
    local = to_local(s or "")
    return local.strftime("%H:%M") if local else default


def local_mmdd_or_year(s: str, *, now: datetime.datetime | None = None) -> str:
    """UTC ISO string -> local 'MM-DD', or local 'YYYY' when >=365d old.
    Empty on missing/unparseable input."""
    dt = parse_utc(s or "")
    if dt is None:
        return ""
    ref = now if now is not None else utc_now()
    local = dt.astimezone(_TZ)
    if (ref - dt).total_seconds() >= 365 * 86400:
        return local.strftime("%Y")
    return local.strftime("%m-%d")


def format_recall_ts(s: str, *, now: datetime.datetime | None = None) -> str:
    """Return '[MM-DD Day · Xd ago]' label for a UTC ISO timestamp string.

    Absolute part: MM-DD Day in configured local timezone (e.g. 06-08 Mon).
    Relative part: <1h -> 'Xm ago' or 'just now'; <24h -> 'Xh ago';
                   <14d -> 'Xd ago'; <8w -> 'Xw ago'; else 'Xmo ago'.
    `now` defaults to utc_now() — injectable for tests.
    Falls back to raw slice on parse error.
    """
    if not s:
        return ""
    dt = parse_utc(s)
    if dt is None:
        return f"[{s[:10]}]"
    abs_part = dt.astimezone(_TZ).strftime("%m-%d %a")
    ref = now if now is not None else utc_now()
    secs = (ref - dt).total_seconds()
    if secs < 60:
        rel = "just now"
    elif secs < 3600:
        rel = f"{int(secs // 60)}m ago"
    elif secs < 86400:
        rel = f"{int(secs // 3600)}h ago"
    elif secs < 14 * 86400:
        rel = f"{int(secs // 86400)}d ago"
    elif secs < 8 * 7 * 86400:
        rel = f"{int(secs // (7 * 86400))}w ago"
    else:
        rel = f"{int(secs // (30 * 86400))}mo ago"
    return f"[{abs_part} · {rel}]"


def reltime_short(s: str, *, now: datetime.datetime | None = None) -> str:
    """Return a short time label for a UTC ISO timestamp — no 'ago' suffix.

    <24h -> 'Xh'; <7d -> 'Xd'; 7d-365d -> 'MM-DD' (configured local timezone);
    >=365d -> 'YYYY' (configured local timezone year). Distinct from format_recall_ts's
    longer '[MM-DD Day · Xd ago]' label — used where a compact single token
    is needed (event-row recall header short format).
    `now` defaults to utc_now() — injectable for tests.
    Falls back to '' on empty input / parse error.
    """
    dt = parse_utc(s or "")
    if dt is None:
        return ""
    ref = now if now is not None else utc_now()
    secs = max(0.0, (ref - dt).total_seconds())
    if secs < 86400:
        return f"{int(secs // 3600)}h"
    if secs < 7 * 86400:
        return f"{int(secs // 86400)}d"
    local = dt.astimezone(_TZ)
    if secs < 365 * 86400:
        return local.strftime("%m-%d")
    return local.strftime("%Y")
