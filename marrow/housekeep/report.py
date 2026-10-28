"""Housekeep report: one markdown file, To do on top, Log below.

State lives in <state_dir>/housekeep/report.json ({items, log}); the file is a
render of it, written only when the render differs from what is on disk.
Items are keyed `<kind>:<subject>` and owned by the pass that raised them; a
pass that ran and no longer raises an item closes it. A Log line is added only
when items opened/closed, a pass failed, or new entries were seen.
"""
from __future__ import annotations

from . import Ctx, read_json, write_json
from .._atomic import atomic_write


def open_subjects(ctx: Ctx, kind: str) -> list[str]:
    items = read_json(ctx.hk_state / "report.json", {"items": {}})["items"]
    return [k.partition(":")[2] for k in items if k.startswith(f"{kind}:")]


def collect(results: dict[str, dict]) -> dict[str, dict]:
    items: dict[str, dict] = {}
    for name, r in results.items():
        todo = list(r.get("todo", []))
        if r.get("error") and not r.get("error_reported"):
            todo.append(("failed", name, f"{name}: {r['error']}"))
        for kind, subject, detail in todo:
            items[f"{kind}:{subject}"] = {"kind": kind, "detail": detail,
                                          "owner": name}
    return items


def merge(old: dict, items: dict, ran: set[str],
          today: str) -> tuple[dict, list[str], list[str]]:
    nxt: dict[str, dict] = {}
    opened: list[str] = []
    closed: list[str] = []
    for k, it in old.items():
        if it["owner"] in ran and k not in items:
            closed.append(k)
        else:
            nxt[k] = it
    for k, it in items.items():
        if k in old:
            nxt[k] = {**old[k], "detail": it["detail"]}
        else:
            nxt[k] = {**it, "date": today}
            opened.append(k)
    return nxt, opened, closed


def _show(key: str) -> str:
    kind, _, subject = key.partition(":")
    return f"{kind} {subject}"


def log_line(today: str, opened: list[str], closed: list[str],
             failed: list[str], new: list[str]) -> str | None:
    segs = []
    for label, vals in (("opened", [_show(k) for k in opened]),
                        ("closed", [_show(k) for k in closed]),
                        ("failed", failed), ("new", new)):
        if vals:
            segs.append(f"{label}: {', '.join(vals)}")
    return f"- {today} " + "; ".join(segs) if segs else None


def render(state: dict) -> str:
    rows = sorted(state["items"].items(), key=lambda kv: (kv[1]["date"], kv[0]))
    out = ["# Housekeep report", "", "## To do"]
    out += [f"- [{it['date']}] {it['kind']}: {it['detail']}" for _, it in rows]
    out += ["", "## Log"]
    out += state["log"]
    return "\n".join(out) + "\n"


def update(ctx: Ctx, results: dict[str, dict]) -> dict:
    sf = ctx.hk_state / "report.json"
    old = read_json(sf, {"items": {}, "log": []})
    today = ctx.today.isoformat()
    items, opened, closed = merge(old["items"], collect(results),
                                  set(results), today)
    failed = [n for n, r in results.items() if r.get("error")]
    new = [x for r in results.values() for x in r.get("new", [])]
    log = list(old["log"])
    line = log_line(today, opened, closed, failed, new)
    if line:
        log = [line] + log[:int(ctx.hk["report_log_cap"]) - 1]
    state = {"items": items, "log": log}
    text = render(state)
    path = ctx.report_path
    try:
        current = path.read_text(encoding="utf-8")
    except OSError:
        current = None
    wrote = text != current
    if not ctx.dry_run:
        if state != old:
            write_json(sf, state)
        if wrote:
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(str(path), text)
    return {"opened": opened, "closed": closed, "line": line, "wrote": wrote}
