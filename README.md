# Marrow

> please remember to update this md with your progress.

Personal AI memory + workflow system. Replaces ny-memm. SQLite-backed, model-agnostic, one dashboard.

## Read order

- DESIGN.md — goals, the outcome Lumi should experience, core mechanism, the decided blocks, and everything Pending. Start here.
- SCHEMA.md — table skeleton + migration mapping.
- FUTURE.md — parked ideas inbox. Not in scope until pulled.

## Conventions

- These docs are frame-level: intended effect + method direction, not code-level spec.
- Pending — decided-to-defer; do not invent a value, ask Lumi when that step is built.
- Idea — exploratory, not committed.

## Architecture

```
  CC CLI ─┐                          ┌─ Open Threads / Alerts   (writable: edits reconcile to DB)
          ├─ marrow daemon ─ SQLite ─┼─ sub-pages               (writable: edits reconcile to DB)
  WeChat ─┘   (MCP server)           └─ Monitor Zone / Cheatsheet (read-only: disk / audit mirror)
                                            │
                                     dashboard.md  (the one file Lumi opens)

  hooks:  SessionStart  inject dashboard top + active threads
          SessionEnd    archive turns · render diary · capture lessons · regen dashboard
          PreToolUse    write-guard (Phase 3: route prompt-class md to writer sub-Claude)
```

## Locations (all future — no code yet)

- Code: `~/cc-lab/marrow/`
- Data: `~/.config/` (exact db path finalized at build)
- User entry: `~/Desktop/NY/dashboard.md`

## Status

2026-05-15 — DESIGN / SCHEMA / README rewritten to frame level: blocks kept whole, product-level detail cut to method direction, blanks marked Pending. Pre-rewrite originals kept as `DESIGN-original.md` / `SCHEMA-original.md`. No code yet.
