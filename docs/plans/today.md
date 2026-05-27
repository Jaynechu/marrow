# Today — 2026-05-27 Wed evening

## Dispatch Policy (read first)
You are the executor opening this plan. Orchestrator only — dispatch every implementation / scan / fetch / review to agent or wt. No inline coding when an agent fits. See `.claude/rules/agent-dispatch.md` + `build-workflow.md`.

## Session 1 (main) — Phase 3 bug cleanup
**Goal**: clear alerts + mm+ both modes work + study/pit two-way landed

Steps:
- TDD two red lines first
  - active sid + events=0 + `reset:mm_plus` marker → NOT skipped by short_session
  - reopened sid retry → covered by `_already_done` path (regression guard)
- Patch `sessionend_async.py:286` short_session early-exit to honor reset marker (mirror `:76`)
- study index gets an inserter spec (mirror `build_projects_index_spec`); unit detail stays render-only
- Lift pit out of `SUBPAGE_BUILDERS`: no more render, no more writes to `pit` table; projects index keeps `[[projects/pit|...]]` link; export current `pit` rows to `~/.config/marrow/db-pages/projects/pit.md` once, then retire the table
- watcher allowlist: subpage detail md (`study/<unit>.md`, `projects/<name>.md`, `projects/pit.md`) skips md_index
- Sweep git status backlog (M/D/??) into commits

Done:
- `pytest -q` exit 0
- `dashboard.md` Alerts no longer contains #114 #115
- mm+ on an active session reruns and writes events
- `pit.md` hand-edit survives a render cycle (echo a line, run refresh, verify)

Dispatch:
- Explore agent: `build_projects_index_spec` structure + current `pit` row count + watcher path filtering state
- worktree-implementer agent: TDD red lines + patches above; main session reviews diff and merges

## Session 2 (main) — dir_tree + drift_sweep .claude scope
**Goal**: drift_sweep watches only rule-class input + dir_tree shape decided

Steps:
- Decide: drop dir_tree or keep (if keep: max_depth=1 + one-line summary per folder, for LLM use)
- `drift_sweep.py` adds `~/.claude` subtree allowlist: `rules/ commands/ skills/ agents/ output-styles/ CLAUDE.md`
- Exclude: `projects/ image-cache/ statsig/ shell-snapshots/ settings.json *.jsonl`
- watchdog rename event triggers sweep (fixes dayplan→grillme not auto-propagating)

Done:
- `drift_sweep.py` subtree filter live + pytest green
- DECISIONS gains a dir_tree shape decision line

Dispatch:
- Explore agent: `.claude` subdirectory inventory + current `drift_sweep.authorized_roots`
- worktree-implementer agent: allowlist + watchdog rename wiring

## Session 3 (main + brainstorming) — NY memm retire sync
**Goal**: memm fully offline + code transfer paths decided

Steps:
- Decide with Lumi: which plists to unload (memm pipeline / curator / rotate / monitor)
- Which skills to delete (summ / ss / goose-slim / carryover-load)
- `~/Desktop/NY/code/` — archive / migrate to marrow / drop
- Lumi clears NY folder while main session unloads plists + deletes skills

Done:
- `docs/plans/ny-retire.md` checklist landed
- plist unload + skill delete + code archive executed

Dispatch:
- Explore agent: ny- prefixed plists under `~/Toolkit/scripts` + ny-relevant skills under `~/.claude/skills/`
- main session executes plist unload + skill delete after Lumi confirms each batch

## Session 4 (main + brainstorming) — Phase 4 WeChat full-chain direction
**Goal**: cyberboss evaluation + recommended path + FUTURE Phase 4-5 rewrite

Steps:
- Pull cyberboss source, map architecture
- Map against current weclaude pain points: multi-msg merge / `/stop` / `/rewind` / media / group chat / bridge long timeout / permission approval
- Decide: replace entirely with cyberboss vs modify cyberboss vs rewrite from scratch
- Mark every uncertain item TBD (Lumi 2026-05-24 rule — no wrong info in docs)

Done:
- `docs/plans/phase4-direction.md` (evaluation + path + effort)
- `FUTURE.md` Phase 4-5 section rewritten

Dispatch:
- fetcher agent: cyberboss repo README + key module list
- general-purpose agent with web: any feature Lumi names that needs current docs lookup

## Constraints
- Concurrent ≤ 3
- Hold: cheatsheet / housekeeping / placement_rules.toml (cheatsheet recall lane design parked in FUTURE.md, ships after P4)
- Pit recall lane (vec + force_include) deferred — Lumi pending decision; today's Session 1 still retires the `pit` table, so the future lane will use a fresh `pit_entries` table without conflict
- mm+ feedback already in (Lumi screenshot), no further wait
