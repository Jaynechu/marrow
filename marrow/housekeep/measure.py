"""Measure passes: sizes + growth, known items, launchd health, free disk.

State under <state_dir>/housekeep/: known.json (entry -> first_seen date +
size; the first run seeds it silently) and watch.json (last run's non-zero
launchd labels, disk_low flag). Dry-run reads both, writes neither.
"""
from __future__ import annotations

import plistlib
from pathlib import Path

from . import (Ctx, fmt_size, read_json, result, tilde, tree_size,
               unsafe_dirs, write_json)

_GB = 1024 ** 3
_MB = 1024 ** 2
_PROBE = ("import importlib.util,sys;"
          "sys.exit(0 if importlib.util.find_spec(sys.argv[1]) else 1)")


def expand(raw: str, home: Path) -> Path:
    return home / raw[2:] if raw.startswith("~/") else Path(raw)


def _log_dirs(ctx: Ctx) -> list[Path]:
    if not ctx.log_root.is_dir():
        return []
    pre = tuple(ctx.hk["log_prefixes"])
    return sorted(d for d in ctx.log_root.iterdir()
                  if d.is_dir() and d.name.startswith(pre))


def sizes(ctx: Ctx) -> dict:
    out = {raw: tree_size(expand(raw, ctx.home)) for raw in ctx.hk["measure_paths"]}
    todo = []
    limit = float(ctx.hk["growth_report_gb"]) * _GB
    for k, now in out.items():
        prev = ctx.prev_sizes.get(k)
        if prev is not None and now - prev >= limit:
            todo.append(("growth", k, f"{k} +{fmt_size(now - prev)} since last "
                         f"run (now {fmt_size(now)})"))
    log_limit = float(ctx.hk["launchd_log_report_mb"]) * _MB
    for d in _log_dirs(ctx):
        f = d / "launchd.log"
        n = f.stat().st_size if f.is_file() else 0
        if n > log_limit:
            t = tilde(f, ctx.home)
            todo.append(("launchd-log", t, f"{t} {fmt_size(n)}"))
    return result(len(out), sizes=out, todo=todo,
                  lines=[f"{k} {fmt_size(v)}" for k, v in out.items()])


def _entries(ctx: Ctx) -> dict[str, Path]:
    skip = {ctx.state_dir, ctx.backup_root, ctx.hk_state}
    found: list[Path] = []
    for root in (ctx.data_dir, ctx.state_dir, ctx.backup_root):
        if root.is_dir():
            found += [p for p in root.iterdir() if p not in skip]
    found += _log_dirs(ctx)
    return {tilde(p, ctx.home): p for p in sorted(found)}


def _ruled(ctx: Ctx) -> set[Path]:
    b = ctx.backup_root
    ruled = {b / "manual", b / "daily", b / "weekly", b / "claude-json",
             ctx.drift_dir, Path(ctx.db).expanduser()}
    ruled |= {ctx.state_dir / d for d in ctx.hk["state_dirs"]}
    ruled |= {ctx.data_dir / d for d in ctx.hk["snapshot_dirs"]}
    return ruled


def known(ctx: Ctx) -> dict:
    bad = unsafe_dirs(ctx.hk)
    if bad:
        return result(error=bad)
    f = ctx.hk_state / "known.json"
    entries = _entries(ctx)
    cur = {k: tree_size(p) for k, p in entries.items()}
    old = read_json(f, None)
    stamp = ctx.today.isoformat()
    if old is None:
        if not ctx.dry_run:
            write_json(f, {k: {"first_seen": stamp, "size": n}
                           for k, n in cur.items()})
        return result(lines=[f"seeded {len(cur)} entries"])
    new = [k for k in cur if k not in old]
    nxt = {k: old.get(k) or {"first_seen": stamp, "size": cur[k]} for k in cur}
    ruled = _ruled(ctx)
    limit = float(ctx.hk["unruled_growth_mb"]) * _MB
    todo = []
    for k, n in cur.items():
        first = nxt[k]["size"]
        if entries[k] not in ruled and n - first >= limit:
            todo.append(("unruled-growth", k,
                         f"{k} {fmt_size(first)} -> {fmt_size(n)}"))
    if not ctx.dry_run and nxt != old:
        write_json(f, nxt)
    labels = [f"{k} ({fmt_size(cur[k])})" for k in new]
    return result(len(new), new=labels, todo=todo,
                  lines=[f"new: {x}" for x in labels])


def _watch(ctx: Ctx) -> dict:
    return read_json(ctx.hk_state / "watch.json", {})


def _save_watch(ctx: Ctx, key: str, value) -> None:
    if ctx.dry_run:
        return
    w = _watch(ctx)
    if w.get(key) != value:
        w[key] = value
        write_json(ctx.hk_state / "watch.json", w)


def _check_plist(ctx: Ctx, label: str, spec: dict) -> tuple | None:
    args = spec.get("ProgramArguments") or []
    prog = spec.get("Program") or (args[0] if args else "")
    if not prog or not Path(prog).exists():
        return ("launchd", label, f"{label}: program missing {prog}")
    if "-m" in args[:-1]:
        mod = args[args.index("-m") + 1]
        wd = spec.get("WorkingDirectory")
        cwd = wd if wd and Path(wd).is_dir() else None
        rc, _ = ctx.run([prog, "-B", "-c", _PROBE, mod], cwd=cwd)
        if rc != 0:
            return ("launchd", label, f"{label}: module {mod} not importable")
    return None


def launchd(ctx: Ctx) -> dict:
    pre = tuple(ctx.hk["launchd_prefixes"])
    labels: list[str] = []
    todo = []
    for f in sorted(ctx.launch_agents.glob("*.plist")):
        try:
            spec = plistlib.loads(f.read_bytes())
        except Exception:  # noqa: BLE001
            if f.stem.startswith(pre):
                todo.append(("launchd", f.stem, f"{f.name}: unreadable plist"))
            continue
        label = str(spec.get("Label", ""))
        if not label.startswith(pre):
            continue
        labels.append(label)
        hit = _check_plist(ctx, label, spec)
        if hit:
            todo.append(hit)
    rc, out = ctx.run(["launchctl", "list"])
    if rc != 0:
        return result(len(labels), error=f"launchctl list: {out[-200:]}",
                      todo=todo)
    nonzero: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in labels and parts[0] == "-" \
                and parts[1] != "0":
            nonzero[parts[2]] = parts[1]
    prev = set(_watch(ctx).get("launchd_nonzero", []))
    for label in sorted(set(nonzero) & prev):
        todo.append(("launchd", f"{label} exit",
                     f"{label}: last exit {nonzero[label]} on 2 runs"))
    _save_watch(ctx, "launchd_nonzero", sorted(nonzero))
    return result(len(labels), todo=todo,
                  lines=[f"{t[2]}" for t in todo] or [f"{len(labels)} jobs ok"])


def disk(ctx: Ctx) -> dict:
    free = ctx.disk_free()
    limit = float(ctx.hk["disk_free_alert_gb"])
    low = free / _GB < limit
    todo = []
    if low and not _watch(ctx).get("disk_low", False):
        todo.append(("disk", "free",
                     f"free disk {fmt_size(free)} < {limit:g} GB"))
    _save_watch(ctx, "disk_low", low)
    return result(sizes={"disk_free": free}, todo=todo,
                  lines=[f"free {fmt_size(free)}"])


PASSES = [
    ("sizes", sizes),
    ("known", known),
    ("launchd", launchd),
    ("disk", disk),
]
