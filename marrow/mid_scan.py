"""Mid-session scan: evaluate trigger, pre-archive, spawn extraction.

CLI: python -m marrow.mid_scan --sid <sid> --jsonl-path <path> --channel <channel>

Called by bridge IdleFireLoop for active sessions.
"""
from __future__ import annotations

import datetime as _dt
import sys

from . import config, repo, storage
from .hooks import _spawn_sessionend_async
from .transcript import clean as transcript_clean


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    sid: str | None = None
    jsonl_path = ""
    channel = "wx"
    i = 0
    while i < len(args):
        if args[i] == "--sid" and i + 1 < len(args):
            sid = args[i + 1]
            i += 2
        elif args[i] == "--jsonl-path" and i + 1 < len(args):
            jsonl_path = args[i + 1]
            i += 2
        elif args[i] == "--channel" and i + 1 < len(args):
            channel = args[i + 1]
            i += 2
        else:
            i += 1

    if not sid or not jsonl_path:
        print(
            "usage: python -m marrow.mid_scan --sid <sid> --jsonl-path <path> --channel <ch>",
            file=sys.stderr,
        )
        return 2

    cfg = config.load()
    conn = storage.connect(config.db_path())

    try:
        try:
            rows = transcript_clean(jsonl_path, channel=channel)
            if rows:
                repo.archive_events(conn, rows)
        except Exception:  # noqa: BLE001
            pass

        mid_cfg = cfg.get("sessionend_mid", {})
        elapsed_hours = mid_cfg.get("elapsed_hours", 4)
        turn_threshold_time = mid_cfg.get("turn_threshold_time", 10)
        turn_threshold_abs = mid_cfg.get("turn_threshold_abs", 30)
        min_hours = mid_cfg.get("min_hours", 2)
        min_turns = mid_cfg.get("min_turns", 5)

        wm = storage.get_latest_watermark(conn, sid)
        after_event_id = wm["last_event_id"] if wm else 0

        if wm:
            user_turns = conn.execute(
                "SELECT COUNT(*) c FROM events"
                " WHERE session_id=? AND role='user' AND id > ?",
                (sid, after_event_id),
            ).fetchone()["c"]
        else:
            user_turns = conn.execute(
                "SELECT COUNT(*) c FROM events"
                " WHERE session_id=? AND role='user'",
                (sid,),
            ).fetchone()["c"]

        if wm:
            wm_ts = _dt.datetime.fromisoformat(
                wm["created_at"].replace("Z", "+00:00")
            )
        else:
            row = conn.execute(
                "SELECT MIN(timestamp) AS ts FROM events WHERE session_id=?",
                (sid,),
            ).fetchone()
            if row and row["ts"]:
                wm_ts = _dt.datetime.fromisoformat(
                    row["ts"].replace("Z", "+00:00")
                )
            else:
                return 0

        now = _dt.datetime.now(_dt.timezone.utc)
        elapsed_h = (now - wm_ts).total_seconds() / 3600

        if elapsed_h < min_hours or user_turns < min_turns:
            return 0

        triggered = (
            (elapsed_h >= elapsed_hours and user_turns >= turn_threshold_time)
            or (user_turns >= turn_threshold_abs and elapsed_h >= min_hours)
        )
        if not triggered:
            return 0

        next_seq = (wm["segment_seq"] + 1) if wm else 1
        _spawn_sessionend_async(
            sid,
            after_event_id=after_event_id if after_event_id else None,
            segment_seq=next_seq,
        )

        try:
            with conn:
                conn.execute(
                    "INSERT INTO audit_log (target_table, target_id, action, summary)"
                    " VALUES ('events', ?, 'mid_scan_trigger', ?)",
                    (sid, f"seq={next_seq},turns={user_turns},hours={elapsed_h:.1f}"),
                )
        except Exception:  # noqa: BLE001
            pass

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
