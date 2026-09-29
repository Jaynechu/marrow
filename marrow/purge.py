"""Event deletes behind the event_clear and tl clear MCP tools.

before/after arrive as local time and go through timeutil.local_bound_to_utc.
A selector matching nothing is an error: nothing is deleted, backed up or
refreshed. dry_run reports the match without touching the DB.
"""
from __future__ import annotations

import shutil
import subprocess

from . import storage, timeutil

NO_MATCH = "0 rows matched"
_BACKUP_DIR = "/tmp"
_LINES_CAP = 20


def _resolve_bounds(before: str | None, after: str | None) -> tuple[str | None, str | None]:
    """Local before/after -> UTC strings. ValueError on bad input."""
    before_utc = timeutil.local_bound_to_utc(before) if before else None
    after_utc = timeutil.local_bound_to_utc(after) if after else None
    return before_utc, after_utc


def _bounds_info(before_utc: str | None, after_utc: str | None) -> dict:
    out: dict = {}
    for name, utc in (("after", after_utc), ("before", before_utc)):
        if utc:
            out[f"{name}_utc"] = utc
            out[f"{name}_local"] = timeutil.utc_iso_to_local_datetime(utc)
    return out


def _time_clauses(col: str, before_utc: str | None, after_utc: str | None
                  ) -> tuple[list[str], list]:
    clauses, params = [], []
    if before_utc:
        clauses.append(f"{col} < ?")
        params.append(timeutil.sql_bound(before_utc))
    if after_utc:
        clauses.append(f"{col} >= ?")
        params.append(timeutil.sql_bound(after_utc))
    return clauses, params


def _match_summary(conn, where: str, params: list) -> dict:
    n, lo, hi = conn.execute(
        f"SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM events{where}",
        params).fetchone()
    return {"matched": n,
            "earliest": timeutil.utc_iso_to_local_datetime(lo or ""),
            "latest": timeutil.utc_iso_to_local_datetime(hi or "")}


def _backup(db: str, tag: str) -> str:
    ts = timeutil.utc_now().strftime("%Y%m%d-%H%M%S")
    path = f"{_BACKUP_DIR}/marrow-backup-{tag}-{ts}.db"
    shutil.copy2(str(db), path)
    return path


def _refresh() -> None:
    subprocess.run(["mw", "refresh", "--all"], capture_output=True, text=True)


def _tombstone_deleted(conn, where: str, params: list, reason: str) -> None:
    """Record event_tombstones for rows about to be deleted, so a later
    catchup/SessionEnd re-archive can't resurrect them (mirrors
    clean_harness_events.py). Keyed by the existing events.source_hash;
    rows with NULL source_hash are skipped."""
    hashes = [r[0] for r in conn.execute(
        f"SELECT source_hash FROM events{where} AND source_hash IS NOT NULL",
        params).fetchall()]
    if hashes:
        conn.executemany(
            "INSERT OR IGNORE INTO event_tombstones (source_hash, reason)"
            " VALUES (?, ?)", [(h, reason) for h in hashes])


def _purge_all(conn, pause_path) -> int:
    pause_path.touch()
    triggers = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name='events'"
    ).fetchall()
    for t in triggers:
        conn.execute(f"DROP TRIGGER IF EXISTS {t['name']}")
    deleted = conn.execute("DELETE FROM events").rowcount
    conn.execute("DELETE FROM sqlite_sequence WHERE name='events'")
    conn.execute("DELETE FROM event_tombstones")
    conn.execute("INSERT INTO events_fts(events_fts) VALUES('rebuild')")
    conn.execute("DELETE FROM events_vec")
    # Triggers are dropped above so events_ad_vec does not cascade — clear
    # meta manually or freed ids inherit orphan meta rows that poison the vec
    # dedup on reuse.
    conn.execute("DELETE FROM events_vec_meta")
    conn.execute("DELETE FROM audit_log WHERE action='sessionend_extract'")
    for t in triggers:
        conn.execute(t["sql"])
    return deleted


def _purge_where(conn, where: str, params: list, reason: str) -> int:
    sids = [r[0] for r in conn.execute(
        f"SELECT DISTINCT session_id FROM events{where}", params).fetchall()]
    _tombstone_deleted(conn, where, params, reason)
    deleted = conn.execute(f"DELETE FROM events{where}", params).rowcount
    if sids:
        conn.executemany(
            "DELETE FROM audit_log WHERE action='sessionend_extract' AND target_id=?",
            [(s,) for s in sids])
    return deleted


def event_clear(db: str, pause_path, before: str | None, after: str | None,
                last: int | None, sid: str | None, dry_run: bool = False) -> dict:
    """Delete events by time range and/or session prefix, the last N, or all."""
    if (before or after or sid) and last:
        return {"ok": False, "error": "before/after/sid and last are mutually exclusive"}
    try:
        before_utc, after_utc = _resolve_bounds(before, after)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    info = _bounds_info(before_utc, after_utc)

    if last:
        where = " WHERE id IN (SELECT id FROM events ORDER BY timestamp DESC LIMIT ?)"
        params: list = [last]
        reason = "event_clear: last=N"
    else:
        clauses, params = _time_clauses("timestamp", before_utc, after_utc)
        if sid:
            clauses.append("session_id LIKE ?")
            params.append(sid + "%")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        reason = "event_clear: range"

    conn = storage.connect(db)
    try:
        summary = _match_summary(conn, where, params)
        if summary["matched"] == 0:
            return {"ok": False, "error": NO_MATCH, **info}
        if dry_run:
            return {"ok": True, "dry_run": True, **summary, **info}
        backup = _backup(db, "purge")
        if where:
            deleted = _purge_where(conn, where, params, reason)
        else:
            deleted = _purge_all(conn, pause_path)
        conn.commit()
    finally:
        conn.close()

    _refresh()
    result = {"ok": True, "purged": ["events"], "deleted": deleted,
              "backup": backup, **info}
    if last:
        result["last"] = last
    if sid:
        result["sid"] = sid
    return result


def tl_clear(db: str, event_id: int | None, sid: str | None,
             before: str | None, after: str | None, dry_run: bool = False) -> dict:
    """Delete role='tl' rows by event_id, session, or local time range."""
    selectors = [event_id is not None, bool(sid), bool(before or after)]
    if sum(selectors) == 0:
        return {"ok": False, "error": "one of event_id / sid / before-after required"}
    if sum(selectors) > 1:
        return {"ok": False, "error": "event_id / sid / before-after are mutually exclusive"}
    try:
        before_utc, after_utc = _resolve_bounds(before, after)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    info = _bounds_info(before_utc, after_utc)

    if event_id is not None:
        clauses, params = ["id=?"], [event_id]
    elif sid:
        clauses, params = ["session_id=?"], [sid]
    else:
        clauses, params = _time_clauses("timestamp", before_utc, after_utc)
    where = " WHERE " + " AND ".join(["role='tl'", *clauses])

    from . import tl_writer
    conn = storage.connect(db)
    try:
        summary = _match_summary(conn, where, params)
        if summary["matched"] == 0:
            return {"ok": False, "error": NO_MATCH, **info}
        if dry_run:
            return {"ok": True, "dry_run": True, **summary, **info}
        rows = conn.execute(
            f"SELECT id, ts_start, ts_end, timestamp, content FROM events{where}"
            " ORDER BY timestamp", params).fetchall()
        lines = [tl_writer.render_line(
            timeutil.utc_iso_to_local_hm(r["ts_start"] or r["timestamp"]),
            timeutil.utc_iso_to_local_hm(r["ts_end"]) if r["ts_end"] else None,
            r["content"]) for r in rows]
        ids = [r["id"] for r in rows]
        backup = _backup(db, "tlclear") if len(ids) > 1 else None
        placeholders = ",".join("?" * len(ids))
        with conn:
            deleted = conn.execute(
                f"DELETE FROM events WHERE id IN ({placeholders})", ids).rowcount
            conn.execute(
                "INSERT INTO audit_log (target_table, target_id, action, summary)"
                " VALUES ('events', ?, 'tl_clear', ?)",
                (",".join(str(i) for i in ids),
                 f"selector={'event_id' if event_id is not None else 'sid' if sid else 'range'}"),
            )
    finally:
        conn.close()
    # DB rows are gone; re-render surviving surfaces so the tl line clears from
    # daybrief (a DELETE bumps no surviving row's mtime, so the 5s loop can't
    # detect it on its own).
    _refresh()

    result = {"ok": True, "deleted": deleted, "ids": ids,
              "lines": lines[:_LINES_CAP], **info}
    if len(lines) > _LINES_CAP:
        result["truncated"] = True
    if backup is not None:
        result["backup"] = backup
    return result
