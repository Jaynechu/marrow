"""File passes: manual/drift backup + state expiry, stray .bak moves, repo caches.

Expiry is by newest mtime inside an entry and unlinks (no trash); sockets are
never expired. A `*.lock` is only a candidate once it has no sibling entry
sharing its stem (`<name>` or `<name>.*`) left in the same directory — an
active owner's marker protects its lock. Stray `*.bak*` files in the data dir
move to backup/manual/ (a taken name gets a `.<n>` suffix) after that dir's
expiry ran, so a moved file survives at least until the next run.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from . import Ctx, latest_mtime, remove, result, tilde, tree_size, unsafe_dirs


def _merge(*parts: dict) -> dict:
    errors = [p["error"] for p in parts if p.get("error")]
    return result(sum(p["items"] for p in parts),
                  sum(p["bytes_freed"] for p in parts),
                  "; ".join(errors) or None,
                  lines=[ln for p in parts for ln in p.get("lines", [])])


def _drop(ctx: Ctx, p: Path) -> int:
    return tree_size(p) if ctx.dry_run else remove(p)


def _lock_has_sibling(names: set[str], lock_name: str) -> bool:
    stem = lock_name[: -len(".lock")]
    if stem in names:
        return True
    prefix = stem + "."
    return any(n != lock_name and n.startswith(prefix) for n in names)


def expire(ctx: Ctx, root: Path, days: int) -> dict:
    if not root.is_dir():
        return result()
    cutoff = time.time() - int(days) * 86400
    items = freed = 0
    lines: list[str] = []
    errors: list[str] = []
    entries = sorted(root.iterdir())
    names = {e.name for e in entries}
    for e in entries:
        if e.is_socket():
            continue
        if e.name.endswith(".lock") and _lock_has_sibling(names, e.name):
            continue
        try:
            if latest_mtime(e) >= cutoff:
                continue
            freed += _drop(ctx, e)
        except OSError as ex:
            errors.append(f"{tilde(e, ctx.home)}: {ex.strerror or ex}")
            continue
        items += 1
        lines.append(tilde(e, ctx.home))
    return result(items, freed, "; ".join(errors) or None, lines=lines)


def manual_backups(ctx: Ctx) -> dict:
    return expire(ctx, ctx.backup_root / "manual", ctx.hk["manual_backup_days"])


def drift_backups(ctx: Ctx) -> dict:
    return expire(ctx, ctx.drift_dir, ctx.hk["drift_backup_days"])


def state_expiry(ctx: Ctx) -> dict:
    bad = unsafe_dirs(ctx.hk)
    if bad:
        return result(error=bad)
    days = ctx.hk["state_days"]
    roots = [ctx.state_dir / d for d in ctx.hk["state_dirs"]]
    roots += [ctx.data_dir / d for d in ctx.hk["snapshot_dirs"]]
    return _merge(*(expire(ctx, r, days) for r in roots))


def stray_bak(ctx: Ctx) -> dict:
    dest_dir = ctx.backup_root / "manual"
    items = 0
    lines: list[str] = []
    for p in sorted(ctx.data_dir.glob("*.bak*")):
        dest = dest_dir / p.name
        n = 0
        while dest.exists():
            n += 1
            dest = dest_dir / f"{p.name}.{n}"
        if not ctx.dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest))
        items += 1
        lines.append(f"{tilde(p, ctx.home)} -> {tilde(dest, ctx.home)}")
    return result(items, 0, lines=lines)


def repo_caches(ctx: Ctx) -> dict:
    names = set(ctx.hk["repo_sweep_names"])
    exclude = ctx.hk["repo_sweep_exclude"]
    plain = {x for x in exclude if "/" not in x}
    nested = ["/" + x.strip("/") for x in exclude if "/" in x]
    items = freed = 0
    lines: list[str] = []
    for root, dirs, _files in os.walk(ctx.repos_root):
        keep = []
        for d in dirs:
            p = os.path.join(root, d)
            if d in plain or any(p.endswith(n) for n in nested):
                continue
            if d in names:
                try:
                    freed += _drop(ctx, Path(p))
                except OSError:
                    continue
                items += 1
                lines.append(tilde(p, ctx.home))
                continue
            keep.append(d)
        dirs[:] = keep
    return result(items, freed, lines=lines)


PASSES = [
    ("manual_backups", manual_backups),
    ("drift_backups", drift_backups),
    ("state_expiry", state_expiry),
    ("stray_bak", stray_bak),
    ("repo_caches", repo_caches),
]
