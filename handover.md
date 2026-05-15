# Marrow Handoff — 2026-05-16 (next window)

Read CLAUDE.md first (it lists when to read what). DESIGN.md is source of truth. PROGRESS.md has this session's 4 entries — do not re-derive. This file is fixed-name persistent: act on it, never delete it; it is overwritten at next session end.

## Pending Lumi decision (do not action without her)

- GitHub history purge: `archive/DESIGN-original.md` (personal health/identity fragments) + `archive/SCHEMA-original.md` are in pushed commit `ae23fc4`. Local archive/ deleted, but GitHub history still has them. Full removal = git-filter-repo strip + force-push to main (destructive, rewrites 6 commits). Awaiting Lumi's explicit go for the force-push.

## Resolved this session

- _pit #3 auto-memory genesis: Lumi deleted it herself. _pit no longer managed by Marrow sessions for now.
- WeClaude scope: Lumi ruled WeClaude IS in Marrow (deep rebuild late phase, cyberboss-refit-or-rewrite TBD). 14 weclaude items restored to FUTURE.md.
- /config_auto_memory_off dropped — auto memory off for a week, moot.

## Parked (carry-over, do not action)

- reference.md dir tree stale (`ny/`, lists deleted README). Lumi said don't bother — Marrow's Cheatsheet / convention-injection absorbs it later.

## State

- grill round 2 already DONE (commit 5972174). Phase 1 build gate is open.
- 3d.md Open-Threads [Next] still lists "grill round 2 pending" + "grill-with-docs skill redesign pending" — both stale; drop on next memm run.
- Commit + push are autonomous (CLAUDE.md Commit/git, Lumi-edited). Remote up to date through 672b539.

## Done this session

- See PROGRESS.md [2026-05-16] x4: docs consolidation (CONVENTIONS folded into CLAUDE.md + rule.md discipline), ny→mw rename, handover overwrite model, global naming law, FUTURE 106→66→30, _pit memm prune.
- Out-of-repo (not in marrow git): `~/.claude/CLAUDE.md` File hygiene → naming law; `~/.claude/skills/handoff/SKILL.md` overwrite model; `~/.claude/settings.json` +`~/Desktop/NY` additionalDirectory; `~/cc-lab/marrow.code-workspace` (Raycast ⌥V via `~/Toolkit/scripts/raycast/vs-ny.sh`).

## Next task

- Start Phase 1 (DESIGN: Memory core — SQLite + full-text, daemon + minimal MCP tool set, three hooks, dashboard top render, migrate.py, `mw` CLI). Resolve the two Lumi decisions above first if she engages them.
- Suggested skills: grill-with-docs (more design stress before code), tdd (Phase 1 build), diagnose (bugs).
