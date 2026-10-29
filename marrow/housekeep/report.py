"""Housekeep report: one markdown file the assistant reads and edits by hand.

Each run appends its new findings under a `## <date>` line. A finding whose
text is already in the file is skipped; nothing is appended when no finding is
new. Existing content is never rewritten or removed.
"""
from __future__ import annotations

from . import Ctx


def findings(results: dict[str, dict]) -> list[str]:
    out: list[str] = []
    for name, r in results.items():
        out += [f"{kind}: {detail}" for kind, _, detail in r.get("todo", [])]
        if r.get("error") and not r.get("error_reported"):
            out.append(f"failed: {name}: {r['error']}")
        out += [f"new: {x}" for x in r.get("new", [])]
    return out


def update(ctx: Ctx, results: dict[str, dict]) -> list[str]:
    path = ctx.report_path
    try:
        current = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        current = ""
    added = list(dict.fromkeys(f for f in findings(results) if f not in current))
    if added and not ctx.dry_run:
        head = "# Housekeep report\n" if not current else (
            "" if current.endswith("\n") else "\n")
        block = f"\n## {ctx.today.isoformat()}\n" + "".join(
            f"- {f}\n" for f in added)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(head + block)
    return added
