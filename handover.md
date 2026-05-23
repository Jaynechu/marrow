# Marrow handover — 2026-05-23 04:30

## State
- pytest 274/274
- DB rows: events 2230 / affect 5 / milestones 13 / vocab 5 / tasks-or-threads 0 / entities 0 (INSERT wired, no SessionEnd LLM run yet) / alerts 0 active / audit_log 186
- branch: main, 5 commits this window
- channel: cc / opus-4.7 (1M)

## This window — phase 2.5a design landing + 2 fixes + handover template lock

### Ship
- 8863cf5 docs(phase-2.5): land design draft + spine reset (DESIGN min-diff L34/L68/L100, DECISIONS +6 reasoned, CLAUDE.md MCP caveat, docs/notes 16 sections)
- 678f64f fix(recall): per-item budget_chars cap (recall.py:472-490)
- 5c23742 feat(diary): entities table INSERT (diary.py:653-689,765,823; 2.5c step 2 cherry-pick)
- 56ddaa0 docs(handover,progress): 2.5a closed, pre-flight gates
- (this commit) docs(template,handover): template lock + DECISIONS +4 reasoned (tag schema / affect aggregation / variance detect / template lock)

## Pre-flight gates for next window (BLOCKERS)

> 2026-05-23 update: gate #2 (9 labels) + gate #3 (importance anchor) DONE in commit b728b2a. Gates #1 / #4 / #5 retained. New plan items consolidated below (§Plan batch).

1. **===DIGEST=== prompt content — Lumi confirm BEFORE first SessionEnd async ships**
   - language register (CN dominant, EN technical inline)
   - second-person voice ((你 / 老婆)) preserved
   - verbatim conversational lines retained, NOT collapsed to work-style summary
   - inner-monologue ((心理活动)) must NOT proliferate; DIGEST is not diary, keep close to transcript shape
   - compression ratio judged BY sonnet per density (work-vs-chat turns); no hard cap, no fixed ratio
   - same gate as DIARY_PROMPT
2. DONE 2026-05-23 b728b2a — main-tone table ((低落/烦躁/痛苦 · 平淡/专注/紧张 · 温暖/愉悦/兴奋)) + LLM fine label 2-char two-layer locked
3. DONE 2026-05-23 b728b2a — importance 1-5 EN anchor in diary.py, decoupled from V/A (retention-based)
4. **handover template LOCKED** at `marrow/handover_template.md` — top §Affect block still needs Lumi paste from `marrow/_affect_template_paste.txt` (Edit hook blocked CN edit from main session; Lumi opens file in editor, replaces lines 32-39 with paste content)
5. Run `grill-with-doc` skill on `docs/notes/2026-05-23_sessionend-llm-pipeline.md` before writing 2.5b code (Lumi stance: design just slimmed, do not move it except for methodology change)

## Plan batch — Lumi-locked 2026-05-23, all land together with diary.py rewrite

> Batch first, no per-item confirm. Next window starts by drafting diary.py rewrite plan that folds every item below into a single edit batch.

### P1. handover_template.md §Affect — Lumi paste manually
Open `marrow/handover_template.md` in editor, replace lines 32-39 with the contents of `marrow/_affect_template_paste.txt`. Edit hook blocks CN from a Claude tool call; file save from editor is not gated.

### P2. CLAUDE.md (global) — Lumi self-writes affect legend
Lumi adds an Affect quick-reference block in `~/.claude/CLAUDE.md` so new sessions can read dashboard semantics. Stellan handling guidance for solo Pending states also lives here.

### P3. ===AFFECT=== prompt new fields — land with diary.py rewrite
Two new JSON fields added to AFFECT contract (region `diary.py:256-279`):

`unresolved` field, Lumi-locked wording (grammar polish only, semantics frozen):
- Only record unresolved emotional ep.
- If nothing fits, skip and output N/A.
- Include: emotion still intense at session end, no resolution or winding down; can be personal or relationship. (e.g. (吵架本session没合好) / (后天要演讲很紧张) / (分享喜讯没说完出门了))
- Exclude: unresolved tasks, emotion tied to study/project, already-resolved emotions. (e.g. (已合好) / (情绪稳定) / (已聊完) / (essay还有两段))

`reconcile_prev` field (sonnet semantic): bool, set true when current ep clearly resolves a prior unresolved emotional state; code links to the most recent affect.unresolved=1 row at write time and auto-fills affect.resolved_at.

### P4. affect schema — three new columns, single migration with 2.5c step 1
- `unresolved INTEGER DEFAULT 0`
- `reconcile_ref INTEGER NULL` (REFERENCES affect(id))
- `resolved_at TEXT NULL` (ISO ts)

Merge with importance 1-5 clamp + 6AM boundary into one migration.

### P5. Pending resolve = dashboard interactive tick
- Render Pending rows as `- [ ] {date} {fine-label} | {description}` in dashboard.md AND handover top
- file watcher (new module `marrow/dashboard_watch.py`) listens for `- [ ]` → `- [x]` transition in dashboard.md
- on tick: reverse-lookup ep_id (embed affect.id as `<!-- aid=N -->` HTML comment per rendered line), write `affect.resolved_at = now`
- next render auto-drops resolved rows
- CLI fallback: `mw set --resolved <aid>` and md direct delete also supported
- delivery batch: 2.5b SessionEnd framework (file watcher fits the daemon process model)

### P6. diary.py rewrite — reconsider responsibility + possibly rename
Trigger: diary.py is doing extract + rollup + catchup + AFFECT contract + prompt embed — too much for one module. Before next big edit, propose a plan that:
- audits diary.py current responsibilities
- considers split (already in 2.5c Window 3: extract.py + rollup.py + catchup.py)
- IF non-diary work dominates, rename the module away from "diary" (e.g. `pipeline.py` / `extractor.py`)
- prompt-and-contract pieces (AFFECT JSON schema, importance anchor, unresolved field, fine label rules) may move out of diary.py into a dedicated prompt module
- delivery: BEFORE any 2.5c step touches diary.py, present rewrite plan for Lumi approval

### P7. DIARY_PROMPT — filter coding-related arguments out of diary
Lumi note 2026-05-23: do not let coding/debug arguments quoted into diary.
- current DIARY_PROMPT (`diary.py:198-254`) already filters Lumi's small-temper lines at work, but coding-argue lines still leak
- next diary.py rewrite: add explicit EXCLUDE rule for any quote/paraphrase of coding/debug arguments, technical pushback, or work-flow scolding — these go to PROGRESS, not diary
- delivery: with P3 / P6 prompt-rewrite batch

### P8. ollama removal — bundled, not yet executed
- Cleanup plan exists (transcript 2026-05-23 ~16:00; ~60 LoC net delete + doc trim across llm.py / config / tests / DESIGN:80 / DECISIONS:10 / CLAUDE.md:16)
- DECISIONS already records the hook-isolation contract that supersedes ollama's role
- Lumi 2026-05-23 directive: do NOT execute standalone — fold into the diary.py / pipeline rewrite batch (one disruption, not two)
- BLOCKING tests to remove: 4 ollama-dependent tests in tests/test_llm.py (incl. test_whole_chain_fails_raises_and_critical_alert which monkeypatches _MUTE_OLLAMA)
- emergency slot in config kept (empty string) as OSS-fork extension point

### P9. daemon LLM hook-isolation contract — 2.5b first ping-pong test must verify in hook context
DECISIONS commit 11db233 locks the contract: schedule path verified (a week of CN diary), SessionEnd-from-hook path NOT yet verified.
- 2.5b first task BEFORE any other 2.5b work: ping-pong test that spawns LLMClient from inside a SessionEnd hook with a prompt containing CN + a known PreToolUse-trigger string; assert clean text return
- if isolation leaks in hook context, fix before proceeding

## Reset rollout — Phase 2.5

### 2.5a — design landing DONE THIS WINDOW (incl template lock)

### 2.5b — async LLM framework (next window priority, after pre-flight gates)
- SessionEnd async detach (Popen triple-redirect per DECISIONS Popen line; stderr -> log file, NEVER DEVNULL)
- Ping-pong stability test (no-op sonnet via Popen + assert detached + <=2s parent return + log file written)
- SessionEnd-catchup (SessionStart fire-and-forget Popen, same detach contract; detection via audit_log marker)
- `marrow/handover_render.py` — render code per `marrow/handover_template.md` (after Lumi confirms 9 labels)
- dashboard render code update: 4 top sections (Alerts / Tasks / Milestone candidate / Affect) sync handover template
- SessionEnd skip-<=5-turn gate code
- ===DIGEST=== prompt write — gated by Lumi pre-ship confirm (BLOCKER #1)

### 2.5c — segment migration (2-3 windows, 7 segments)

Window 1 (3 segments):
1. ===AFFECT=== per-ep + 6AM boundary + importance 1-5 clamp & Lumi anchor (see pre-flight #3) (`diary.py:256-275`, `_build_affect_rows ~L563-600`); rolling 24h/7d aggregation + 9 label words + variance detect land here
2. ===ENTITY_CAND=== + entities.pinned column + FTS5 CJK jieba rebuild (one migration; entities INSERT already done in 5c23742)
3. ===THREAD_CAND=== -> tasks table (DROP threads + CREATE tasks; threads 0 rows; tag nullable TEXT field added)

Window 2 (3 segments):
4. ===MILESTONE_CAND=== + dashboard alert + 7d auto-confirm + handover top render (Milestone candidate section)
5. ===VOCAB_CAND=== + use_count + vocab.pinned + 5 cipher backfill + vocab leg in recall_fusion
6. ===DIGEST=== (per Section 16 length flex; prompt MUST be Lumi-confirmed first)

Window 3 (1 segment + closure):
7. ===NARRATIVE=== handover async segment
- 07:00 nightly demote validation (3-5 day A/B prose quality)
- diary.py split: extract.py + rollup.py + catchup.py (each <=200 LOC)
- launchd plist realign (03/07/19/Sun12)
- pinned + aging code lands

## Open — retained

### Recall path fixes (partial done this window)
- DONE budget_chars per-item cap (678f64f)
- PENDING FTS5 trigram fails on 2-char CJK -> bundle with 2.5c step 2
- DONE MCP daemon restart caveat -> CLAUDE.md (in 8863cf5)
- PENDING milestones family/friend scope empty -> resolved naturally by 2.5c entity pipeline

### Prior-window retain (still untouched)
- affect day-boundary 5AM -> 6AM rewrite (`diary.py:256-275`) — bundle with 2.5c step 1
- importance 1-5 scale clamp (`diary.py:_build_affect_rows ~L563-600`) — bundle with 2.5c step 1
- mood overlay on diary render (`subpages_render.py:render_diary`) — bundle with 2.5c step 6 or Window 3 closure

### Phase 3 backlog (blocked by 2.5 close)
- writer_authority · drift_sweep · convention_injection · claude_md_render_guard
- static-layer retire (CLAUDE.md family / cipher / MCP guide -> daemon-rendered); prerequisite = claude_md_render_guard

### Hygiene (still untouched)
- 9 old worktree branches dangling; main guardrail blocks force-delete; Lumi runs manually

## Carryover scratch
- `~/Desktop/brainstorm-future.md` — 10-section future-features brainstorm (addon contract / wallet MCP split / iOS path / active-device routing / chord-progression from 和弦 / imprint borrows / cccompanion fork). 3 items in FUTURE Phase 5; 9 pending (待加).

## Affect

(4-dim layout LOCKED at `marrow/handover_template.md` §Affect; 9 label words + band thresholds 0.4/0.6 pending Lumi to unify tomorrow; aggregation = weighted mean v×a + variance detect stddev(v)>0.3)

## Reference (last commits)
- (this commit) docs(template,handover): template lock + DECISIONS +4 reasoned
- 56ddaa0 docs(handover,progress): 03:00 - 2.5a closed, pre-flight gates
- 5c23742 feat(diary): wire entities table INSERT alongside affect.entities JSON
- 678f64f fix(recall): per-item budget_chars cap
- 8863cf5 docs(phase-2.5): land design draft + spine reset

## Suggested skills for next window
- `grill-with-doc` on `docs/notes/2026-05-23_sessionend-llm-pipeline.md` before 2.5b code
- `tdd` for Popen triple-redirect ping-pong test + handover_render template contract
- `writing-plans` for 2.5b/c detail plan after pre-flight gates clear
