"""python -m marrow.housekeep — weekly maintenance, fired daily by launchd.

A full run is due when the last full run is at least
[housekeep].interval_days old. Until then, a day after a failed run reruns
only the passes that failed in it (a retry run, ok once they pass). Each pass
is isolated. --apply writes one audit_log row (action=housekeep, JSON {ok,
passes, sizes[, retry]}) and updates the report file; fail_alert_days failed
days in a row (full or retry) raise one housekeep_failed alert per streak.
--dry-run writes nothing.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import sys
from datetime import date

from .. import repo, storage, timeutil
from . import Ctx, brew, build_ctx, db, files, fmt_size, measure, report, result

GROUPS: dict[str, list] = {
    "db": db.PASSES,
    "files": files.PASSES,
    "brew": brew.PASSES,
    "measure": measure.PASSES,
}


def history(ctx: Ctx) -> list[dict]:
    """Full and retry audit rows, newest first, each with local `date`."""
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
        s["date"] = timeutil.utc_iso_to_local_date(r["occurred_at"])
        out.append(s)
    return out


def last_ok(hist: list[dict]) -> dict | None:
    return next((h for h in hist if h.get("ok")), None)


def last_full(hist: list[dict]) -> dict | None:
    return next((h for h in hist if "retry" not in h), None)


def is_due(ctx: Ctx, hist: list[dict]) -> bool:
    full = last_full(hist)
    if full is None:
        return True
    age = (ctx.today - date.fromisoformat(full["date"])).days
    return age >= int(ctx.hk["interval_days"])


def retry_passes(hist: list[dict]) -> list[str] | None:
    """Passes that failed in the newest run, or None when it was ok."""
    if not hist or hist[0].get("ok"):
        return None
    return [n for n, p in hist[0].get("passes", {}).items() if p.get("error")]


def fail_streak(hist: list[dict]) -> int:
    """Distinct local days with a failed run since the last ok one."""
    days: set[str] = set()
    for h in hist:
        if h.get("ok"):
            break
        days.add(h["date"])
    return len(days)


def run_passes(ctx: Ctx, groups: list[str],
               names: list[str] | None = None) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for g in groups:
        for name, fn in GROUPS[g]:
            if names is not None and name not in names:
                continue
            try:
                results[name] = fn(ctx)
            except Exception as e:  # noqa: BLE001
                results[name] = result(error=f"{type(e).__name__}: {e}")
    return results


def _audit_payload(results: dict[str, dict], ok: bool,
                   only: str | None, retry: list[str] | None) -> dict:
    payload: dict = {
        "ok": ok,
        "passes": {
            n: {k: r.get(k) for k in ("items", "bytes_freed", "error")}
            for n, r in results.items()
        },
        "sizes": {k: v for r in results.values()
                  for k, v in r.get("sizes", {}).items()},
    }
    if only:
        payload["only"] = [only]
    if retry is not None:
        payload["retry"] = retry
    return payload


def record(ctx: Ctx, results: dict[str, dict], ok: bool,
           only: str | None, retry: list[str] | None) -> None:
    conn = storage.connect(ctx.db)
    try:
        with conn:
            conn.execute(
                "INSERT INTO audit_log (target_table, target_id, action, summary) "
                "VALUES ('housekeep', NULL, 'housekeep', ?)",
                (json.dumps(_audit_payload(results, ok, only, retry),
                            sort_keys=True),),
            )
    finally:
        conn.close()


def maybe_alert_streak(ctx: Ctx, failed: list[str]) -> bool:
    hist = history(ctx)
    n = fail_streak(hist)
    if n < int(ctx.hk["fail_alert_days"]):
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
        message=(f"housekeep failed {n} days in a row: {', '.join(failed)}. "
                 f"See {ctx.report_path}"),
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


def execute(ctx: Ctx, only: str | None, force: bool) -> int:
    hist = history(ctx)
    retry = None
    if not force and not is_due(ctx, hist):
        retry = None if only else retry_passes(hist)
        if retry is None:
            print(f"[housekeep] not due (last full run "
                  f"{last_full(hist)['date']})")
            return 0
        print(f"[housekeep] retry: {', '.join(retry) or '(report only)'}")
    ctx.prev_sizes = next((h["sizes"] for h in hist
                           if "retry" not in h and h.get("sizes")), {})
    results = run_passes(ctx, [only] if only else list(GROUPS), retry)
    try:
        rep = report.update(ctx, results)
    except Exception as e:  # noqa: BLE001
        rep = None
        results["report"] = result(error=f"{type(e).__name__}: {e}")
    failed = [n for n, r in results.items() if r.get("error")]
    ok = not failed
    _print(ctx, results)
    if rep:
        verb = "would " if ctx.dry_run else ""
        print(f"[housekeep] report: {verb}open {len(rep['opened'])}, "
              f"{verb}close {len(rep['closed'])}"
              + (f"; {verb}write {ctx.report_path}" if rep["wrote"] else ""))
        if ctx.dry_run and rep["line"]:
            print(f"    {rep['line']}")
    if ctx.dry_run:
        return 0
    record(ctx, results, ok, only, retry)
    if not ok and not only:
        maybe_alert_streak(ctx, failed)
    for r in results.values():
        for a in r.get("alerts", []):
            repo.add_alert(a["severity"], a["type"], a["type"],
                           source="housekeep", message=a["message"], db=ctx.db)
    return 0 if ok else 1


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
    ap.add_argument("--force", action="store_true",
                    help="full run even when not due")
    a = ap.parse_args(argv)
    ctx = build_ctx(dry_run=not a.apply)
    if ctx.dry_run:
        return execute(ctx, a.only, a.force)
    ctx.hk_state.mkdir(parents=True, exist_ok=True)
    with open(ctx.hk_state / "run.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("[housekeep] another run holds the lock", file=sys.stderr)
            return 0
        return execute(ctx, a.only, a.force)


if __name__ == "__main__":
    raise SystemExit(main())
