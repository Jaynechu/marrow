"""python -m marrow.housekeep — weekly maintenance, fired weekly by launchd.

Each pass is isolated: a failing pass is a report finding, not a run failure.
A run fails only when it crashes outside the passes or the report cannot be
written. --apply writes one audit_log row (action=housekeep, JSON {ok, passes,
sizes[, error]}) and appends new findings to the report file; fail_alert_runs
failed runs in a row raise one housekeep_failed alert per streak.
--dry-run writes nothing.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import sys

from .. import repo, storage
from . import Ctx, brew, build_ctx, db, files, fmt_size, measure, report, result

GROUPS: dict[str, list] = {
    "db": db.PASSES,
    "files": files.PASSES,
    "brew": brew.PASSES,
    "measure": measure.PASSES,
}


def history(ctx: Ctx) -> list[dict]:
    """Audit rows of full runs, newest first."""
    conn = db.connect(ctx)
    try:
        rows = conn.execute(
            "SELECT occurred_at, summary FROM audit_log "
            "WHERE target_table='housekeep' AND action='housekeep' "
            "ORDER BY id DESC"
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        try:
            s = json.loads(r["summary"])
        except (TypeError, ValueError):
            continue
        if s.get("only"):
            continue
        s["occurred_at"] = r["occurred_at"]
        out.append(s)
    return out


def last_ok(hist: list[dict]) -> dict | None:
    return next((h for h in hist if h.get("ok")), None)


def fail_streak(hist: list[dict]) -> int:
    """Failed runs in a row since the last ok one."""
    n = 0
    for h in hist:
        if h.get("ok"):
            break
        n += 1
    return n


def run_passes(ctx: Ctx, groups: list[str]) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for g in groups:
        for name, fn in GROUPS[g]:
            try:
                results[name] = fn(ctx)
            except Exception as e:  # noqa: BLE001
                results[name] = result(error=f"{type(e).__name__}: {e}")
    return results


def _audit_payload(results: dict[str, dict], error: str | None,
                   only: str | None) -> dict:
    payload: dict = {
        "ok": error is None,
        "passes": {
            n: {k: r.get(k) for k in ("items", "bytes_freed", "error")}
            for n, r in results.items()
        },
        "sizes": {k: v for r in results.values()
                  for k, v in r.get("sizes", {}).items()},
    }
    if error:
        payload["error"] = error
    if only:
        payload["only"] = [only]
    return payload


def record(ctx: Ctx, results: dict[str, dict], error: str | None,
           only: str | None) -> None:
    conn = storage.connect(ctx.db)
    try:
        with conn:
            conn.execute(
                "INSERT INTO audit_log (target_table, target_id, action, summary) "
                "VALUES ('housekeep', NULL, 'housekeep', ?)",
                (json.dumps(_audit_payload(results, error, only),
                            sort_keys=True),),
            )
    finally:
        conn.close()


def maybe_alert_streak(ctx: Ctx, error: str) -> bool:
    hist = history(ctx)
    n = fail_streak(hist)
    if n < int(ctx.hk["fail_alert_runs"]):
        return False
    ok = last_ok(hist)
    since = ok["occurred_at"] if ok else ""
    conn = storage.connect(ctx.db)
    try:
        seen = conn.execute(
            "SELECT 1 FROM alerts WHERE type='housekeep_failed' "
            "AND created_at >= ? LIMIT 1", (since,)).fetchone()
    finally:
        conn.close()
    if seen:
        return False
    repo.add_alert(
        "warn", "housekeep_failed", "housekeep_failed", source="housekeep",
        message=f"housekeep run failed {n} times in a row: {error}",
        db=ctx.db)
    return True


def _print(ctx: Ctx, results: dict[str, dict]) -> None:
    tag = " (dry-run)" if ctx.dry_run else ""
    for name, r in results.items():
        line = f"[housekeep] {name}: items={r['items']}"
        if r.get("bytes_freed"):
            line += f" freed={fmt_size(r['bytes_freed'])}"
        if r.get("error"):
            line += f" ERROR {r['error']}"
        print(line + tag)
        if ctx.dry_run:
            for d in r.get("lines", []):
                print(f"    {d}")


def execute(ctx: Ctx, only: str | None) -> int:
    results: dict[str, dict] = {}
    error = None
    try:
        ctx.prev_sizes = next((h["sizes"] for h in history(ctx)
                               if h.get("sizes")), {})
        results.update(run_passes(ctx, [only] if only else list(GROUPS)))
        _print(ctx, results)
        added = report.update(ctx, results)
        verb = "would add" if ctx.dry_run else "added"
        print(f"[housekeep] report: {verb} {len(added)}"
              + (f" to {ctx.report_path}" if added else ""))
        if ctx.dry_run:
            for f in added:
                print(f"    {f}")
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {e}"
        print(f"[housekeep] run failed: {error}", file=sys.stderr)
    if ctx.dry_run:
        return 0 if error is None else 1
    record(ctx, results, error, only)
    if error and not only:
        maybe_alert_streak(ctx, error)
    return 0 if error is None else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="marrow.housekeep",
        description="Weekly maintenance: expiry, updates, sizes, report.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true", help="execute passes")
    g.add_argument("--dry-run", action="store_true",
                   help="list what a run would do, write nothing (default)")
    ap.add_argument("--only", choices=sorted(GROUPS),
                    help="run one pass group")
    a = ap.parse_args(argv)
    ctx = build_ctx(dry_run=not a.apply)
    if ctx.dry_run:
        return execute(ctx, a.only)
    ctx.hk_state.mkdir(parents=True, exist_ok=True)
    with open(ctx.hk_state / "run.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("[housekeep] another run holds the lock", file=sys.stderr)
            return 0
        return execute(ctx, a.only)


if __name__ == "__main__":
    raise SystemExit(main())
