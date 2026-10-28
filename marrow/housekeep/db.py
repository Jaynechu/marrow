"""DB passes: md_index tombstones, worktree slug shells, vec window, ct tables.

Memes are permanent — no aging/DELETE pass. Dry-run opens the DB read-only
and counts what a real run would delete.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import time
from datetime import date
from pathlib import Path

import sqlite_vec

from .. import storage, timeutil
from . import Ctx, latest_mtime, result as pass_result

def connect(ctx: Ctx) -> sqlite3.Connection:
    if not ctx.dry_run:
        return storage.connect(ctx.db)
    conn = sqlite3.connect(Path(ctx.db).as_uri() + "?mode=ro", uri=True,
                           timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def _with_conn(ctx: Ctx, fn):
    conn = connect(ctx)
    try:
        with conn:
            return fn(conn)
    finally:
        conn.close()


def _delete(conn: sqlite3.Connection, table: str, where: str,
            dry_run: bool) -> int:
    if dry_run:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
    return conn.execute(f"DELETE FROM {table} WHERE {where}").rowcount or 0


def prune_md_index_tombstones(conn: sqlite3.Connection, days: int,
                              dry_run: bool = False) -> int:
    """DELETE md_index rows tombstoned more than `days` days ago.

    Live rows and recent tombstones stay so the inserter's anti-resurrection
    guard still fires for blocks the user deleted recently.
    """
    where = ("tombstone_at IS NOT NULL AND tombstone_at < "
             f"strftime('%Y-%m-%dT%H:%M:%SZ','now', '-{int(days)} days')")
    return _delete(conn, "md_index", where, dry_run)


def prune_projects_worktrees(projects_dir: Path, idle_days: int,
                             dry_run: bool = False) -> int:
    """Delete ~/.claude/projects/<slug>/ dirs containing "worktrees" in the name.

    Worktree sessions are task-isolated; cc ages their jsonls out but leaves
    the slug shells, which are never revisited. A slug whose newest mtime is
    younger than idle_days may be a live session and stays. Returns slug dirs
    removed.
    """
    if not projects_dir.is_dir():
        return 0
    cutoff = time.time() - int(idle_days) * 86400
    purged = 0
    for child in sorted(projects_dir.iterdir()):
        if not child.is_dir() or "worktrees" not in child.name:
            continue
        try:
            if latest_mtime(child) >= cutoff:
                continue
            if not dry_run:
                shutil.rmtree(child)
        except OSError:
            continue
        purged += 1
    return purged


_BACKUP_NAME_RE = re.compile(r"^marrow-\d{4}-\d{2}-\d{2}\.db$")


def _newest_backup(backup_dir: str) -> date | None:
    """Date of the newest marrow-YYYY-MM-DD.db in backup_dir, or None."""
    d = Path(backup_dir)
    if not d.is_dir():
        return None
    candidates = sorted(
        p.name for p in d.iterdir() if _BACKUP_NAME_RE.match(p.name)
    )
    if not candidates:
        return None
    try:
        return date.fromisoformat(candidates[-1][len("marrow-"):-len(".db")])
    except ValueError:
        return None


def evict_vec_window(
    conn: sqlite3.Connection,
    *,
    window_days: int,
    backup_dir: str,
    hk: dict,
    dry_run: bool = False,
) -> dict:
    """Delete out-of-window events_vec rows; events_vec_meta stays as tombstone.

    Exempt: affect-linked (importance>=3) or recall_count>0. Skipped when the
    newest daily backup is missing or older than hk vec_backup_stale_days;
    aborted above the hk vec_evict_cap_pct / vec_evict_cap_abs caps.
    window_days=0 disables. Returns evicted, exempted, skipped, aborted,
    pending_alerts (problems the caller surfaces).
    """
    stale_days = int(hk["vec_backup_stale_days"])
    cap_pct = float(hk["vec_evict_cap_pct"])
    cap_min = int(hk["vec_evict_cap_min"])
    cap_abs = int(hk["vec_evict_cap_abs"])
    result: dict = {
        "evicted": 0, "exempted": 0,
        "skipped": False, "aborted": False,
        "pending_alerts": [],
    }

    if window_days == 0:
        return result

    newest = _newest_backup(backup_dir)
    today = timeutil.local_today()
    if newest is None or (today - newest).days > stale_days:
        age_str = str((today - newest).days) + "d" if newest else "missing"
        result["pending_alerts"].append({
            "severity": "warn", "fingerprint": "vec_evict_backup_stale",
            "message": (
                f"vec_evict skipped: backup {age_str} (need ≤{stale_days}d). "
                f"Run `python -m marrow.backup --apply` then retry."
            ),
        })
        result["skipped"] = True
        return result

    cutoff_sql = f"strftime('%Y-%m-%dT%H:%M:%SZ','now', '-{window_days} days')"

    candidate_rows = conn.execute(
        f"""
        SELECT ev.rowid
        FROM events_vec ev
        JOIN events e ON e.id = ev.rowid
        WHERE e.timestamp < {cutoff_sql}
          AND e.recall_count = 0
          AND NOT EXISTS (
            SELECT 1 FROM affect a
            WHERE a.event_id = e.id AND a.importance >= 3
          )
        """
    ).fetchall()
    candidate_ids = [r[0] for r in candidate_rows]

    exempt_rows = conn.execute(
        f"""
        SELECT ev.rowid
        FROM events_vec ev
        JOIN events e ON e.id = ev.rowid
        WHERE e.timestamp < {cutoff_sql}
          AND (
            e.recall_count > 0
            OR EXISTS (
              SELECT 1 FROM affect a
              WHERE a.event_id = e.id AND a.importance >= 3
            )
          )
        """
    ).fetchall()
    result["exempted"] = len(exempt_rows)

    evict_count = len(candidate_ids)
    if evict_count == 0:
        return result

    total_vec = conn.execute("SELECT COUNT(*) FROM events_vec").fetchone()[0]
    if (evict_count > cap_min
            and total_vec > 0
            and evict_count > total_vec * cap_pct):
        result["pending_alerts"].append({
            "severity": "critical", "fingerprint": "vec_evict_cap_pct",
            "message": (
                f"vec_evict aborted: would evict {evict_count}/{total_vec} rows "
                f"({evict_count/total_vec:.0%} > {cap_pct:.0%} cap). "
                "Manual investigation required."
            ),
        })
        result["aborted"] = True
        return result
    if evict_count > cap_abs:
        result["pending_alerts"].append({
            "severity": "critical", "fingerprint": "vec_evict_cap_abs",
            "message": (
                f"vec_evict aborted: would evict {evict_count} rows "
                f"(> {cap_abs} abs cap). Manual investigation required."
            ),
        })
        result["aborted"] = True
        return result

    if dry_run:
        result["evicted"] = evict_count
        return result

    placeholders = ",".join("?" * len(candidate_ids))
    conn.execute(
        f"DELETE FROM events_vec WHERE rowid IN ({placeholders})",
        candidate_ids,
    )
    result["evicted"] = evict_count
    return result


def prune_ct_tables(conn: sqlite3.Connection, *, collector_days: int,
                    activity_days: int, dry_run: bool = False) -> dict[str, int]:
    """DELETE cortex ct_collector_log / ct_activity rows past their window.

    Absent tables (cortex never ran) count 0.
    """
    out: dict[str, int] = {}
    for table, days in (("ct_collector_log", collector_days),
                        ("ct_activity", activity_days)):
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                            "AND name=?", (table,)).fetchone():
            out[table] = 0
            continue
        where = f"ts < strftime('%Y-%m-%dT%H:%M:%SZ','now', '-{int(days)} days')"
        out[table] = _delete(conn, table, where, dry_run)
    return out


def ct_prune(ctx: Ctx) -> dict:
    counts = _with_conn(ctx, lambda c: prune_ct_tables(
        c, collector_days=ctx.hk["ct_collector_log_days"],
        activity_days=ctx.hk["ct_activity_days"], dry_run=ctx.dry_run))
    return pass_result(sum(counts.values()),
                       lines=[f"{t}={n}" for t, n in counts.items()])


def md_tombstones(ctx: Ctx) -> dict:
    return pass_result(_with_conn(
        ctx, lambda c: prune_md_index_tombstones(
            c, ctx.hk["md_tombstone_days"], ctx.dry_run)))


def worktree_shells(ctx: Ctx) -> dict:
    return pass_result(prune_projects_worktrees(
        ctx.projects_dir, ctx.hk["worktree_shell_days"], ctx.dry_run))


def vec_evict(ctx: Ctx) -> dict:
    r = _with_conn(ctx, lambda c: evict_vec_window(
        c, window_days=ctx.vec_window_days,
        backup_dir=str(ctx.backup_root / "daily"), hk=ctx.hk,
        dry_run=ctx.dry_run))
    err = "; ".join(a["message"] for a in r["pending_alerts"]) or None
    return pass_result(r["evicted"], error=err, lines=[f"exempted={r['exempted']}"])


PASSES = [
    ("md_tombstones", md_tombstones),
    ("worktree_shells", worktree_shells),
    ("vec_evict", vec_evict),
    ("ct_prune", ct_prune),
]
