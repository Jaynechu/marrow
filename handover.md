# Marrow handover — 2026-05-22 22:20

## State
- pytest 271/271 passing
- diary single call: 5/22 first success — 4 affect rows, all `source=diary_single_call` (no fallback)
- sub_pages live: `~/Desktop/NY/sub_pages/` → milestone / diary / study / cheatsheet / memes / goose / projects + projects/pit.md
- dashboard.md: Alerts (none), Open Threads (none), Sub Pages (7 wikilinks)
- recall path: hook + MCP daemon now share `recall.recall_with_config` (single config-driven entry)

## This session shipped
12 commits on main + 3 uncommitted edits (DECISIONS.md untouched-by-me).

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

### Round 3 — recall path fixes (1 commit, this session)
- `e37631b` **fix(recall): surface milestones on long queries + align MCP/hook path**
  - `marrow/recall.py:449-456` milestone `min_score` gate removed — long queries dilute `kw_score = hits/len(query_tokens)` below 0.1 (real trigger: a 9-token prompt with 2 CJK matches → kw=0.22 → raw=0.066). Milestones are evergreen anchors; any token hit must enter.
  - `marrow/recall.py:458-471` **reserved milestone slots** — `ms_cap = max(1, (limit+2)//3)`. Events outrank milestones on raw score (recency + affect additive); plain top-K cut starved milestones even when they matched.
  - `marrow/recall.py:476-503` **new `recall_with_config(conn, query, *, limit=None, budget_chars=None)`** — single config-driven entry. Reads `[recall]` section for weights + `min_score`. Used by hook and MCP daemon to guarantee identical shape.
  - `marrow/hooks.py:303-309` collapsed 12-line `recall_fusion(...)` call → `recall_mod.recall_with_config(conn, prompt_text)`.
  - `marrow/daemon.py:29` MCP `recall` tool was calling `repo.recall` (fusion defaults `min_score=0.35`) while hook used config `0.1`. Two paths, two shapes. Now both go through `recall_with_config`.
  - tests 271/271 (244 baseline + new `test_milestone_long_query_dilution_still_surfaces`, `test_milestone_any_token_hit_enters_regardless_of_min_score`, `test_recall_with_config_reads_rcfg`; rewrote `test_milestone_min_score_gate_respected` and `test_milestone_pinned_only_boost_when_pinned`).

## Open / not touched

### Recall path — found this session, NOT fixed
- **`budget_chars` swallow (high impact)** — `marrow/recall.py:460-471` truncation loop tracks cumulative chars; default `budget_chars=2000`. A single long event content (event 2210 = 3054 chars) fills the budget on the first row and the loop breaks, dropping the remaining 9. Reproduced: `recall_with_config(conn, "<3-char CJK name>", limit=10)` returns **1** row (the giant assistant turn) — user-side this looked like "recall nothing about today's outing", even though the user message and 4 assistant replies were all in DB and indexed. With `budget_chars=20000` all 10 come back.
  - Fix: add per-item cap = `budget_chars // limit` so long content gets truncated to its fair share before consuming the global budget. Skill: `tdd` (write red test for "10 hits with one 3000-char event still returns 10 short rows").
- **FTS5 trigram fails on 2-char CJK** — `events_fts` declared `tokenize='trigram'` (`marrow/storage.py` schema). Any 2-char CJK term (food / nickname / common verb) returns 0 FTS hits. vec leg can't compensate (cosine distance 1.1+ for short queries → `vec_score=0`). 3-char queries work fine. All 2-char CJK terms are effectively unsearchable in events.
  - Fix: swap tokenizer to `unicode61 remove_diacritics 2` plus integrate jieba/cppjieba for CJK segmentation, then `INSERT INTO events_fts(events_fts) VALUES('rebuild')`. **Schema-level change**, gate on phase 3.
- **milestones family/friend scope empty (data gap, not bug)** — `select scope, count(*) from milestones` → `me=1, us=12`. No `family` / `friend` / `people` / `contacts` rows at all. User asked "who is (CJK 3-char name)" — recall path is healthy, the row just doesn't exist. Two paths:
  - (a) manual `mw add milestone --scope friend --date YYYY-MM-DD --title "..." --description "..."` for 5-10 core people now (~10 min).
  - (b) wait for phase 3 entity pipeline (`DECISIONS.md:36`) to auto-surface from events.
  - Lumi to pick; user-side context already references named friends and family with no anchor in DB.
- **MCP server restart caveat** — `marrow/daemon.py` is a long-running stdio process spawned at cc startup. Code changes to daemon (e.g. this session's `recall` tool switch) do NOT take effect until a new cc window. Hook path picks up changes immediately (spawned per UserPromptSubmit). Worth a one-liner in CLAUDE.md.

### Critical for downstream (from prior session, retained)
- **affect day-boundary 5AM rule** — 5/22 ep1 (`晚安吻`) v=0.85 @04:xx should belong to 5/21, not 5/22. Add to `marrow/diary.py:256-275`: "before 05:00 belongs to previous day".
- **importance 1-5 scale** — 5/22 emitted 6/7/8 instead of max 5. Lumi ground truth: (`晚安吻`)=1, (`骑豹剧`)=2, (`删笔记`)=1, (`编记忆`)=4. Fix: prompt `1-5` explicit + parser clamp in `marrow/diary.py:_build_affect_rows` (~L563–600).
- **mood overlay on diary render** — `marrow/subpages_render.py:render_diary` add captions like `[Mid/Calm | 删笔记]` at section head. Lumi next window.
- **semantic alignment + param tuning** — Lumi next window.

### Phase 3 backlog (from prior session, retained)
- **entity / new-people / preference pipeline** — `DECISIONS.md:36`. `entities` table 0 rows; `entity_facts` table not in schema; prompt has no `===ENTITY_FACTS===`. Single call must produce affect + entity_facts + milestone candidate together. Static `<Family_and_Friend>` block retires only after entity precision ≥ 90%. **Couples naturally with the FTS5 tokenizer rebuild above — do them in one schema migration.**
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

## Suggested skills for next session
- **`tdd`** for the `budget_chars` per-item cap fix — deterministic logic, easy red-green.
- **`grill-with-doc`** or **`brainstorming`** for phase 3 entity pipeline + FTS5 tokenizer swap (schema migration deserves a real plan, not improv).
- **`diagnose`** if user reports more "recall returns nothing" cases — the trigram + budget bugs may be masking other issues.

## Reference
- `marrow/recall.py:449-503` milestone gate + reserved slots + `recall_with_config`
- `marrow/hooks.py:303-309` UserPromptSubmit hook (now thin)
- `marrow/daemon.py:22-31` MCP `recall` tool (now aligned)
- `marrow/diary.py:519-548` `_parse_single_call` telemetry
- `marrow/diary.py:256-275` SINGLE_CALL_PROMPT AFFECT contract (importance + day-boundary rules)
- `marrow/reconcile.py` 214 LOC
- `marrow/subpages.py:255` `build_all_configs` — add new view + matching key in `_SUB_PAGE_NAV`
- `marrow/dashboard.py:render_top` + `_SUB_PAGE_NAV`
- `marrow/hooks.py:251-264` session_end sub_pages wire
- `marrow/cli.py:_add_milestone` + `_ADD_TABLES`
- `DESIGN.md:67,118,163` / `DECISIONS.md:36` / `FUTURE.md:19,59,62`
- audit_log telemetry: `diary_single_call_affect_ok` / `_no_affect_marker` / `_affect_parse_fail`
