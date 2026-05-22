# Marrow handover — 2026-05-22 20:25

## State
- pytest 269/269 passing
- diary single call: 5/22 first success — 4 affect rows, all `source=diary_single_call` (no fallback)
- sub_pages live: `~/Desktop/NY/sub_pages/` → milestone / diary / study / cheatsheet / memes / goose / projects + projects/pit.md
- dashboard.md: Alerts (none), Open Threads (none), Sub Pages (7 wikilinks)

## This session shipped
11 commits on main + 3 uncommitted edits.

### Round 1 — stop-bleed + telemetry (4 commits)
- `e4be1c7` **llm tier severity**: length-1 chain failure = `warn`, not `critical`. `marrow/llm.py:120`, test at `tests/test_llm.py:86`.
- `2d22abd` **diary single-call telemetry**: `marrow/diary.py:519-548` `_parse_single_call` → `(prose, affect_raw, outcome, err)` where outcome ∈ {`ok`, `no_marker`, `parse_fail`}. Emits `audit_log` via `_log_single_call_outcome`.
- `edc6b28` **source-tag three-state**: `diary_single_call` (ok) / `diary_single_call_no_affect` (missing block) / `diary_fallback` (LLMError).
- `2ce699b` **prompt fix**: `marrow/diary.py:256-275` AFFECT block moved to EN imperative (was CJK parens → read as asides).

### Round 2 — milestone persistence (5 commits)
- `537ab9b` `milestones.updated_at` column + migration (backfill `updated_at = created_at`).
- `ca0830f` `config.sub_pages_path()` → `~/Desktop/NY/sub_pages`, `config.sub_pages_state_path()` → `~/.config/marrow/state`.
- `6717b44` `hooks.py:251-264` session_end: sub_pages write, then dashboard, then embed_pending; each step independent try/except.
- `8db0e11` `mw add milestone --scope us|me --date YYYY-MM-DD --title "..." [--description --theme --pinned]`. Dispatcher pattern `_ADD_TABLES`.
- `98ece57` **new `marrow/reconcile.py`** (214 LOC) — `reconcile_milestones(conn, md_path) → ReconcileReport`. Anchor `<!-- id:N -->`. Backup md to `state_dir/milestone.<ts>.bak.md` on delete>0 or conflict>0. Reordered: reconcile-first then re-render then hash-check; prevents spurious hand-edit alerts on Lumi md edits.

### Post-cherry-pick fixes (3 edits, uncommitted)
- `marrow/hooks.py:162-168` `_read_input`: `if sys.stdin.isatty(): return {}` — terminal-direct `python -m marrow.hooks session_end` no longer blocks on `sys.stdin.read()`. Real cc SessionEnd path unaffected.
- `marrow/dashboard.py:render_top`: `## Sub Pages` block after Open Threads. `_SUB_PAGE_NAV = ["milestone", "diary", "study", "projects", "cheatsheet", "memes", "goose"]` filtered to existing `<key>.md` files; emits `[[sub_pages/<key>]]` wikilinks. Hand-edit guard unchanged.
- **DB UPDATE alert #13**: `severity` kept `critical`, set `resolved=1, resolved_at=2026-05-22T19:48:00Z`. Dashboard filters resolved alerts.

## Open / not touched

### Critical for downstream
- **affect day-boundary 5AM rule** — 5/22 ep1 (`晚安吻`) v=0.85 @04:xx should belong to 5/21, not 5/22. Add to `marrow/diary.py:256-275`: "before 05:00 belongs to previous day".
- **importance 1-5 scale** — 5/22 emitted 6/7/8 instead of max 5. Lumi ground truth: (`晚安吻`)=1, (`骑豹剧`)=2, (`删笔记`)=1, (`编记忆`)=4. Fix: prompt `1-5` explicit + parser clamp in `marrow/diary.py:_build_affect_rows` (~L563–600).
- **mood overlay on diary render** — `marrow/subpages_render.py:render_diary` add captions like `[Mid/Calm | 删笔记]` at section head. Lumi next window.
- **semantic alignment + param tuning** — Lumi next window.

### Phase 3 backlog
- **entity / new-people / preference pipeline** — `DECISIONS.md:36`. `entities` table 0 rows; `entity_facts` table not in schema; prompt has no `===ENTITY_FACTS===`. Single call must produce affect + entity_facts + milestone candidate together. Static `<Family_and_Friend>` block retires only after entity precision ≥ 90%.
- **milestone automatic extraction** — old ny-memm auto-pulled candidates; Round 2 only shipped md-edit + CLI input (downgrade). Likely: single call outputs `===MILESTONE_CANDIDATE===` → pending-review queue → Lumi batch-approve. Owner: Lumi.
- **event extraction eval harness** — gate for entity + milestone-auto. Run pipeline on N old sessions → ground-truth vs 5/17–5/22 reality → precision/recall/F1. Decides if `<Family_and_Friend>` can be deleted. Must run before entity ships.
- **goose render dedup + per-day best** — `~/Desktop/NY/sub_pages/goose.md` 3340 lines. Lumi spec: pick **best** per day (funny + interesting, not shortest); dedupe. `marrow/subpages_render.py:render_goose`.
- **stellan_wallet** (`钱包`) — `FUTURE.md:59`. Month-grouped bank-statement style; auto-credit from diary 04:00 routine. Sub_pages root level.
- **projects table schema** — `projects.md` Active/Done empty (no table). Only `pit` table (23 rows → `projects/pit.md`).
- **CN/EN language consistency** — 5/22 18:20 carryover. Scan headers/labels/tags across handover, dashboard, SessionStart context, alerts. ★

### Hygiene
- 9 old worktree branches dangling; main guardrail blocks `git branch -D`. Lumi runs manually. Worktree dirs: `git worktree remove --force` first.
- worktree-agent-a13a751e533445bc6 / worktree-agent-abc5afb10dd92cda6: dirs removed, branch refs dangling (cherry-pick absorbed).
- 5/17–5/20 affect blank: skip, do not backfill. ✅
- `entities` JSON column on affect populated — extraction working.

## Reference
- `marrow/diary.py:519-548` `_parse_single_call` telemetry
- `marrow/diary.py:256-275` SINGLE_CALL_PROMPT AFFECT contract (importance + day-boundary rules)
- `marrow/reconcile.py` 214 LOC
- `marrow/subpages.py:255` `build_all_configs` — add new view + matching key in `_SUB_PAGE_NAV`
- `marrow/dashboard.py:render_top` + `_SUB_PAGE_NAV`
- `marrow/hooks.py:251-264` session_end sub_pages wire
- `marrow/cli.py:_add_milestone` + `_ADD_TABLES`
- `DESIGN.md:67,118,163` / `DECISIONS.md:36` / `FUTURE.md:19,59,62`
- audit_log telemetry: `diary_single_call_affect_ok` / `_no_affect_marker` / `_affect_parse_fail`
