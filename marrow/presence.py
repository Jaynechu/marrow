"""Presence heartbeat — where the user is and what they are doing, injected on
every user turn under a wall-clock throttle.

Independent of the cortex silence machinery: a continuous conversation still
gets a presence line every [presence].interval_min minutes. One line, pieces
joined by ` · `:  `📍 Home (3h20m) · 💻 Active: Telegram`.

Nothing knowable (no sensor state, non-macOS, probes failing) -> "" and no
injection. The throttle stamp advances whenever the window opens, so a machine
that can answer nothing is probed at most once per interval.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from . import config
from .paths import paths

_PROBE_TIMEOUT_S = 3
_DEFAULT_INTERVAL_MIN = 30
_DEFAULT_AWAY_IDLE_MIN = 30
_DEFAULT_CHANNELS = ("cli", "tg", "wx")


def _channel() -> str:
    return (os.environ.get("MARROW_CHANNEL") or "").strip() or "cli"


def _location_file() -> Path:
    return paths.state_dir / "sensors" / "location.json"


def _stamp_file(sid: str) -> Path:
    return config.DATA_DIR / "state" / "presence" / sid


def _duration(seconds: float) -> str:
    minutes = max(0, int(seconds) // 60)
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h{minutes % 60}m"


def _parse_local(ts: str, tz) -> datetime:
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=tz)


def _location_piece(now: datetime) -> str:
    try:
        loc = json.loads(_location_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(loc, dict):
        return ""
    zone = loc.get("zone")
    since = loc.get("since")
    prev = loc.get("prev") if isinstance(loc.get("prev"), dict) else None
    if not isinstance(zone, str) or not zone.strip():
        if not prev or not isinstance(prev.get("zone"), str):
            return ""
        zone = "out"
    zone = zone.strip()
    if not isinstance(since, str) or not since:
        return f"📍 {zone}" if zone != "out" else ""
    try:
        dur = _duration((now - _parse_local(since, now.tzinfo)).total_seconds())
    except (TypeError, ValueError):
        return f"📍 {zone}" if zone != "out" else ""
    return f"📍 {zone} ({dur})"


def _idle_seconds() -> int | None:
    """Seconds since the last keyboard/mouse event (IOHIDSystem)."""
    try:
        out = subprocess.run(
            ["/usr/sbin/ioreg", "-c", "IOHIDSystem"],
            capture_output=True, text=True, timeout=_PROBE_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out.stdout)
    return int(match.group(1)) // 1_000_000_000 if match else None


def _frontmost_app() -> str | None:
    """macOS frontmost application name; loginwindow/failure -> None."""
    try:
        out = subprocess.run(
            ["/usr/bin/osascript", "-e",
             'tell application "System Events" to get name of first application '
             'process whose frontmost is true'],
            capture_output=True, text=True, timeout=_PROBE_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    name = out.stdout.strip()
    if out.returncode != 0 or not name or name == "loginwindow":
        return None
    return name


def _activity_piece(away_idle_min: int) -> str:
    app = _frontmost_app()
    if not app:
        return ""
    idle = _idle_seconds()
    if idle is None:
        return ""
    if idle >= away_idle_min * 60:
        return f"💻 Inactive: {_duration(idle)} {app}"
    return f"💻 Active: {app}"


def _away_idle_min(cfg: dict) -> int:
    try:
        value = int((cfg.get("cortex", {}) or {}).get(
            "away_idle_min", _DEFAULT_AWAY_IDLE_MIN))
    except (TypeError, ValueError):
        return _DEFAULT_AWAY_IDLE_MIN
    return value if value >= 0 else _DEFAULT_AWAY_IDLE_MIN


def _throttle_open(sid: str, interval_min: int, now_epoch: int) -> bool:
    """True when the window has elapsed. A session with no stamp yet (fresh
    window, incl. a cortex rotation) is always open."""
    if interval_min <= 0:
        return True
    try:
        last = int(_stamp_file(sid).read_text().strip())
    except (OSError, ValueError):
        return True
    return now_epoch - last >= interval_min * 60


def _write_stamp(sid: str, now_epoch: int) -> None:
    path = _stamp_file(sid)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(now_epoch))
    except OSError:
        pass


def render(sid: str) -> str:
    """The presence line for this turn, or "" when disabled, throttled, off-channel
    or nothing is knowable."""
    if not sid:
        return ""
    cfg = config.load()
    pc = cfg.get("presence", {}) or {}
    if not pc.get("enabled", True):
        return ""
    channels = pc.get("channels")
    if not isinstance(channels, list):
        channels = list(_DEFAULT_CHANNELS)
    if _channel() not in [str(c).strip().lower() for c in channels]:
        return ""
    try:
        interval_min = int(pc.get("interval_min", _DEFAULT_INTERVAL_MIN))
    except (TypeError, ValueError):
        interval_min = _DEFAULT_INTERVAL_MIN
    now_epoch = int(time.time())
    if not _throttle_open(sid, interval_min, now_epoch):
        return ""
    now = datetime.now(config.get_tz())
    pieces = [p for p in (_location_piece(now),
                          _activity_piece(_away_idle_min(cfg))) if p]
    _write_stamp(sid, now_epoch)
    return " · ".join(pieces)
