# Marrow Handoff — 2026-05-16 (next window)

Read CLAUDE.md first (it lists when to read what). DESIGN.md is source of truth. PROGRESS.md has this session's 4 entries — do not re-derive. This file is fixed-name persistent: act on it, never delete it; it is overwritten at next session end.

## Pending Lumi decision (do not action without her)

- _pit.md block #3 "关 auto memory + 重写 memory/ 文件夹 [high]" (`~/Desktop/NY/code/_pit.md:3`) — kept, flagged. Marrow genesis note; live sliver preserved in FUTURE `/config_auto_memory_off` + DESIGN Cheatsheet. Delete-or-keep is Lumi's call. _pit.md is NOT git-backed; backup at `~/Desktop/NY/memory/backup/_pit.md.bak-2026-05-16`.
- WeClaude scope: FUTURE.md re-scope (commit 672b539) cut ~12 weclaude-internal-bridge items, treating WeClaude as a sibling project not Marrow. If Lumi rules WeClaude is part of Marrow, recover them from git pre-672b539.

## Parked (carry-over, do not action)

- archive/ history rewrite: DESIGN-original.md personal fragments still in commit ae23fc4 on GitHub; full removal = force-push history rewrite. Lumi said leave it.
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
