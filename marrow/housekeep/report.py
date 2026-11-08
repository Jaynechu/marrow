"""Housekeep report: one markdown file the assistant reads and edits by hand.

Each full run appends its new findings under a `## <date>` line, or a single
"Cleanup completed, no new issues" line when a full run finds nothing new; a
finding whose text is already in the file is skipped; `--only` runs append
nothing when there is nothing new. Existing content is never rewritten or
removed.
"""
from __future__ import annotations

from . import Ctx, fmt_size


def findings(results: dict[str, dict]) -> list[str]:
    out: list[str] = []
    for name, r in results.items():
        out += [f"{kind}: {detail}" for kind, _, detail in r.get("todo", [])]
        if r.get("error") and not r.get("error_reported"):
            out.append(f"failed: {name}: {r['error']}")
        out += [f"new: {x}" for x in r.get("new", [])]
    return out


def update(ctx: Ctx, results: dict[str, dict], full: bool = True) -> list[str]:
    path = ctx.report_path
    try:
        current = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        current = ""
    added = list(dict.fromkeys(f for f in findings(results) if f not in current))
    if ctx.dry_run:
        return added
    if added:
        head = "# Housekeep report\n" if not current else (
            "" if current.endswith("\n") else "\n")
        block = f"\n## {ctx.today.isoformat()}\n" + "".join(
            f"- {f}\n" for f in added)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(head + block)
    elif full:
        freed = sum(r.get("bytes_freed", 0) for r in results.values())
        head = "# Housekeep report\n" if not current else (
            "" if current.endswith("\n") else "\n")
        line = (f"\n## {ctx.today.isoformat()} — Cleanup completed, "
                f"no new issues (freed {fmt_size(freed)})\n")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(head + line)
        print("[housekeep] report: clean line written")
    return added
