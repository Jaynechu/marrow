"""DB passes: md_index tombstones, worktree slug shells, vec window eviction.

Memes are permanent — no aging/DELETE pass. Dry-run opens the DB read-only
and counts what a real run would delete.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import date
from pathlib import Path

import sqlite_vec

from .. import storage, timeutil
from . import Ctx, result as pass_result

_TOMBSTONE_WHERE = (
    "tombstone_at IS NOT NULL "
    "AND tombstone_at < strftime('%Y-%m-%dT%H:%M:%SZ','now', '-30 days')"
)


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


def prune_md_index_tombstones(conn: sqlite3.Connection,
                              dry_run: bool = False) -> int:
    """DELETE md_index rows tombstoned more than 30 days ago.

    Live rows and recent tombstones stay so the inserter's anti-resurrection
    guard still fires for blocks the user deleted recently.
    """
    return _delete(conn, "md_index", _TOMBSTONE_WHERE, dry_run)


def prune_projects_worktrees(projects_dir: Path, dry_run: bool = False) -> int:
    """Delete every ~/.claude/projects/<slug>/ whose name contains "worktrees".

    Worktree sessions are task-isolated; cc ages their jsonls out but leaves
    the slug shells, which are never revisited. Returns slug dirs removed.
    """
    if not projects_dir.is_dir():
        return 0
    purged = 0
    for child in sorted(projects_dir.iterdir()):
        if not child.is_dir() or "worktrees" not in child.name:
            continue
        if dry_run:
            purged += 1
            continue
        try:
            shutil.rmtree(child)
            purged += 1
        except OSError:
            continue
    return purged


_VEC_EVICT_CAP_PCT = 0.25
_VEC_EVICT_CAP_MIN = 100
_VEC_EVICT_CAP_ABS = 10000
_BACKUP_STALE_DAYS = 7
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
    dry_run: bool = False,
) -> dict:
    """Delete out-of-window events_vec rows; events_vec_meta stays as tombstone.

    Exempt: affect-linked (importance>=3) or recall_count>0. Skipped when the
    newest daily backup is missing or older than 7d; aborted above the 25% /
    10000-row caps. window_days=0 disables. Returns evicted, exempted,
    skipped, aborted, pending_alerts (problems the caller surfaces).
    """
    result: dict = {
        "evicted": 0, "exempted": 0,
        "skipped": False, "aborted": False,
        "pending_alerts": [],
    }

    if window_days == 0:
        return result

    newest = _newest_backup(backup_dir)
    today = timeutil.local_today()
    if newest is None or (today - newest).days > _BACKUP_STALE_DAYS:
        age_str = str((today - newest).days) + "d" if newest else "missing"
        result["pending_alerts"].append({
            "severity": "warn", "fingerprint": "vec_evict_backup_stale",
            "message": (
                f"vec_evict skipped: backup {age_str} (need ≤{_BACKUP_STALE_DAYS}d). "
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
    if (evict_count > _VEC_EVICT_CAP_MIN
            and total_vec > 0
            and evict_count > total_vec * _VEC_EVICT_CAP_PCT):
        result["pending_alerts"].append({
            "severity": "critical", "fingerprint": "vec_evict_cap_pct",
            "message": (
                f"vec_evict aborted: would evict {evict_count}/{total_vec} rows "
                f"({evict_count/total_vec:.0%} > {_VEC_EVICT_CAP_PCT:.0%} cap). "
                "Manual investigation required."
            ),
        })
        result["aborted"] = True
        return result
    if evict_count > _VEC_EVICT_CAP_ABS:
        result["pending_alerts"].append({
            "severity": "critical", "fingerprint": "vec_evict_cap_abs",
            "message": (
                f"vec_evict aborted: would evict {evict_count} rows "
                f"(> {_VEC_EVICT_CAP_ABS} abs cap). Manual investigation required."
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


def md_tombstones(ctx: Ctx) -> dict:
    return pass_result(_with_conn(
        ctx, lambda c: prune_md_index_tombstones(c, ctx.dry_run)))


def worktree_shells(ctx: Ctx) -> dict:
    return pass_result(prune_projects_worktrees(ctx.projects_dir, ctx.dry_run))


def vec_evict(ctx: Ctx) -> dict:
    r = _with_conn(ctx, lambda c: evict_vec_window(
        c, window_days=ctx.vec_window_days,
        backup_dir=str(ctx.backup_root / "daily"), dry_run=ctx.dry_run))
    err = "; ".join(a["message"] for a in r["pending_alerts"]) or None
    return pass_result(r["evicted"], error=err, lines=[f"exempted={r['exempted']}"])


PASSES = [
    ("md_tombstones", md_tombstones),
    ("worktree_shells", worktree_shells),
    ("vec_evict", vec_evict),
]
