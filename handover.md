# Marrow handover — 2026-05-23 03:00

## State
- pytest 274/274 (271 baseline + recall per-item-cap + entities INSERT x2)
- DB rows: events 2230 / affect 5 / milestones 13 / vocab 5 / tasks-or-threads 0 / entities 0 (INSERT wired but no SessionEnd LLM run yet) / alerts 0 active / audit_log 186
- branch: main, 3 commits this window (8863cf5, 678f64f, 5c23742)
- channel: cc / opus-4.7 (1M)

## This window — phase 2.5a design landing + 2 independent fixes

### Ship
- **8863cf5** docs(phase-2.5): land design draft + spine reset (+709/-272 across 7 files)
  - DESIGN min-diff: L34 threads->tasks · L68 SessionEnd code-only -> sync+async · L100 Phase 2.5 entry
  - DECISIONS +6 reasoned (narrative race sid stamp · catchup audit_log marker · Popen stderr -> log file · DIGEST length flex · DIGEST prompt confirm gate · SessionEnd skip <=5 turns)
  - CLAUDE.md: MCP daemon restart caveat
  - docs/notes/2026-05-23_sessionend-llm-pipeline.md: 16-section design landing draft
  - docs/archive/2026-05-23_DESIGN.md: Lumi slim-down archived
- **678f64f** fix(recall): per-item budget_chars cap so a long event cannot eat the whole window (recall.py:472-490 + test_recall.py)
- **5c23742** feat(diary): wire entities table INSERT alongside affect.entities JSON (diary.py:653-689,765,823 + test_diary.py x 2; 2.5c step 2 cherry-pick, no schema change)

## Pre-flight gates for next window (BLOCKERS)

1. **===DIGEST=== prompt content — Lumi confirm BEFORE first SessionEnd async ships**
   - language register (CN dominant, EN technical inline)
   - second-person voice (你 / 老婆) preserved
   - verbatim conversational lines retained, NOT collapsed to work-style summary
   - same gate as DIARY_PROMPT
2. **===AFFECT=== 4-dim layout + handover-template** — Lumi mid-writing; do NOT touch until she signals locked
3. Run `grill-with-doc` skill on `docs/notes/2026-05-23_sessionend-llm-pipeline.md` before writing 2.5b code (Lumi stance: design just slimmed, don't move it except for methodology change)

## Reset rollout — Phase 2.5

### 2.5a — design landing DONE THIS WINDOW

### 2.5b — async LLM framework (next window priority, after pre-flight gates)
- SessionEnd async detach (Popen triple-redirect per DECISIONS Popen line; stderr -> log file, NEVER DEVNULL)
- Ping-pong stability test (no-op sonnet via Popen + assert detached + <=2s parent return + log file written)
- SessionEnd-catchup (SessionStart fire-and-forget Popen, same detach contract; detection via audit_log marker)
- handover sync code render -> `marrow/handover_render.py` (after Lumi template lock)
- SessionEnd skip-<=5-turn gate code
- ===DIGEST=== prompt write — gated by Lumi pre-ship confirm (BLOCKER above)

### 2.5c — segment migration (2-3 windows, 7 segments)

Window 1 (3 segments):
1. ===AFFECT=== per-ep + 6AM boundary + importance 1-5 clamp (`diary.py:256-275`, `_build_affect_rows ~L563-600`)
2. ===ENTITY_CAND=== + entities.pinned column + FTS5 CJK jieba rebuild (one migration; entities INSERT already done in 5c23742)
3. ===THREAD_CAND=== -> tasks table (DROP threads + CREATE tasks; threads 0 rows)

Window 2 (3 segments):
4. ===MILESTONE_CAND=== + dashboard alert + 7d auto-confirm
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
- PENDING FTS5 trigram fails on 2-char CJK -> bundle with 2.5c step 2 (one migration with entities.pinned + jieba rebuild)
- DONE MCP daemon restart caveat -> CLAUDE.md (in 8863cf5)
- PENDING milestones family/friend scope empty -> resolved naturally by 2.5c entity pipeline

### Prior-window retain (still untouched)
- affect day-boundary 5AM -> 6AM rewrite (`diary.py:256-275`) — bundle with 2.5c step 1
- importance 1-5 scale clamp (`diary.py:_build_affect_rows ~L563-600`) — bundle with 2.5c step 1
- mood overlay on diary render (`subpages_render.py:render_diary`, `[Mid/Calm | <CJK label>]` at section head) — bundle with 2.5c step 6 or Window 3 closure

### Phase 3 backlog (blocked by 2.5 close)
- writer_authority · drift_sweep · convention_injection · claude_md_render_guard
- static-layer retire (CLAUDE.md family / cipher / MCP guide -> daemon-rendered); prerequisite = claude_md_render_guard

### Hygiene (still untouched)
- 9 old worktree branches dangling; main guardrail blocks force-delete; Lumi runs manually

## Affect

(Lumi mid-writing 4-dim layout; do NOT touch this section until she signals locked)

## Reference (last 3 commits)
- 5c23742 feat(diary): wire entities table INSERT alongside affect.entities JSON
- 678f64f fix(recall): per-item budget_chars cap so a long event cannot eat the whole window
- 8863cf5 docs(phase-2.5): land design draft + spine reset

## Suggested skills for next window
- `grill-with-doc` on `docs/notes/2026-05-23_sessionend-llm-pipeline.md` before 2.5b code
- `tdd` for Popen triple-redirect ping-pong test + handover_render template contract
- `writing-plans` for 2.5b/c detail plan after pre-flight gates clear
