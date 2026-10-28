"""Brew + uv + package-cache passes, python EOL watch.

Pinned brew pythons keep their Cellar path (TCC/FDA is keyed on it): pins go
first, and cleanup aborts if its plan still names a pinned Cellar dir. A
changed brew triggers an import health probe per repo venv; no kickstart.
Dry-run runs only `brew upgrade -n` and `brew cleanup -n`.
"""
from __future__ import annotations

from datetime import date

from . import Ctx, result


def _err(step: str, out: str, **extra) -> dict:
    tail = out.strip().splitlines()[-1] if out.strip() else "failed"
    return result(error=f"{step}: {tail}", **extra)


def _items(out: str) -> list[str]:
    return [ln.strip() for ln in out.splitlines()
            if ln.strip() and not ln.startswith(("==>", "Warning", "This operation"))]


def _pinned_hits(cleanup_plan: str, pinned: list[str]) -> list[str]:
    return [ln.strip() for ln in cleanup_plan.splitlines()
            if any(f"/Cellar/{p}/" in ln for p in pinned)]


def _versions(ctx: Ctx) -> str:
    return "\n".join(ctx.run(cmd)[1] for cmd in (
        ["brew", "list", "--formula", "--versions"],
        ["brew", "list", "--cask", "--versions"]))


def _health(ctx: Ctx) -> list[str]:
    bad = []
    for repo, mod in ctx.hk["health_imports"].items():
        py = ctx.repos_root / repo / ".venv" / "bin" / "python"
        rc, _ = ctx.run([str(py), "-c", f"import {mod}"],
                        cwd=str(ctx.repos_root / repo))
        if rc != 0:
            bad.append(repo)
    return bad


def brew(ctx: Ctx) -> dict:
    pinned = list(ctx.hk["brew_pinned"])
    prune = f"--prune={int(ctx.hk['brew_prune_days'])}"
    if ctx.dry_run:
        rc, up = ctx.run(["brew", "upgrade", "-n"])
        if rc != 0:
            return _err("brew upgrade -n", up)
        rc, plan = ctx.run(["brew", "cleanup", "-n", prune])
        if rc != 0:
            return _err("brew cleanup -n", plan)
        ups = [u for u in _items(up) if u.split()[0] not in pinned]
        clean = _items(plan)
        hits = _pinned_hits(plan, pinned)
        lines = [f"upgrade: {u}" for u in ups] + [f"cleanup: {c}" for c in clean]
        lines.append(f"pinned at apply: {', '.join(pinned)}")
        err = f"cleanup plan names pinned Cellar: {hits}" if hits else None
        return result(len(ups) + len(clean), error=err, lines=lines)
    for f in pinned:
        rc, out = ctx.run(["brew", "pin", f])
        if rc != 0:
            return _err(f"brew pin {f}", out)
    before = _versions(ctx)
    for cmd in (["brew", "update"], ["brew", "upgrade"]):
        rc, out = ctx.run(cmd)
        if rc != 0:
            return _err(" ".join(cmd), out)
    after = _versions(ctx)
    changed = before != after
    rc, plan = ctx.run(["brew", "cleanup", "-n", prune])
    if rc != 0:
        return _err("brew cleanup -n", plan)
    hits = _pinned_hits(plan, pinned)
    if hits:
        return result(error=f"cleanup skipped, plan names pinned Cellar: {hits}")
    rc, out = ctx.run(["brew", "cleanup", prune])
    if rc != 0:
        return _err("brew cleanup", out)
    n = len(_items(plan))
    if changed:
        bad = _health(ctx)
        if bad:
            return result(n, error=f"health: import failed in {', '.join(bad)}",
                          error_reported=True, todo=[("health", r, f"{r} venv import failed after "
                                 "brew upgrade") for r in bad])
    return result(n, lines=[f"brew changed: {changed}"])


def _steps(ctx: Ctx, cmds: list[list[str]]) -> dict:
    if ctx.dry_run:
        return result(lines=[f"would run: {' '.join(c)}" for c in cmds])
    for c in cmds:
        rc, out = ctx.run(c)
        if rc != 0:
            return _err(" ".join(c), out)
    return result(len(cmds))


def uv(ctx: Ctx) -> dict:
    return _steps(ctx, [["uv", "tool", "upgrade", "--all"],
                        ["uv", "cache", "prune"]])


def pip(ctx: Ctx) -> dict:
    return _steps(ctx, [["python3", "-m", "pip", "cache", "purge"]])


def npm(ctx: Ctx) -> dict:
    return _steps(ctx, [["npm", "cache", "clean", "--force"]])


def python_eol(ctx: Ctx) -> dict:
    warn = int(ctx.hk["eol_warn_days"])
    todo = []
    for name, eol in sorted(ctx.hk["python_eol"].items()):
        if (date.fromisoformat(str(eol)) - ctx.today).days <= warn:
            todo.append(("python-eol", name, f"{name} EOL {eol}"))
    return result(len(todo), todo=todo)


PASSES = [
    ("brew", brew),
    ("uv", uv),
    ("pip", pip),
    ("npm", npm),
    ("python_eol", python_eol),
]
