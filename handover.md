# Marrow handover — 2026-05-23 02:15

## State
- pytest 271/271 (no code shipped this window — brainstorm-only)
- DB rows: events 2230 / affect 5 / milestones 13 / vocab 5 / tasks-or-threads 0 / entities 0 / alerts 0 active / audit_log 186
- branch: main, 0 commits this window
- channel: cc / opus-4.7 (1M)

## This window — brainstorm reset (decisions only, no code)

> Goal: overturn the phase-2-end patchwork mindset, land the main spine + framework + sequencing.
> Source: `~/Desktop/2026-05-22_marrow-reset-brainstorm.md` (prior window note).
> Continued from upstream handover 52d6945.

### Locked this window

1. **diary demoted to byproduct; marrow main spine = recall + affect-now + handover + thread/task.**
2. **Overturn the false red-line "SessionEnd no-LLM"** — SessionEnd async LLM extraction is the reset core.
3. **Pipeline topology** (replaces brainstorm §6.3):
    - SessionStart sync: inject recall + affect 4-dim backdrop + tasks + alerts + handover.md; fire-and-forget SessionStart-catchup Popen subprocess
    - SessionEnd sync (<2s, code-only): transcript clean → events archive → dashboard regen → handover.md sync skeleton atomic write
    - SessionEnd async (Popen detach, sonnet single call): multi-segment output `===AFFECT===` / `===ENTITY_CAND===` / `===THREAD_CAND===` / `===MILESTONE_CAND===` / `===VOCAB_CAND===` / `===DIGEST===` (200-400 char compressed narrative) / `===NARRATIVE===` (handover async segment); table writes + audit_log telemetry; failure → alert + queued to SessionEnd-catchup
    - 07:00 nightly: sonnet 1×/day, reads only pre-extracted `===DIGEST===` + structured rows → diary prose; **raw transcript hits LLM once (SessionEnd); nightly does NOT re-read raw**
    - 19:00 catchup: same shape, scans missing daily roll-ups
    - SessionEnd-catchup: SessionStart-time Popen subprocess scans events for sessions lacking extraction, async detach

4. **LLM tier = all sonnet** (Agent B 2026-05-23 02:00 verdict, artifacts `~/Desktop/marrow_ab/`):
    - haiku 2/3 runs: prose-ep count != affect-entry count → affect dropped/misaligned (data-correctness bug, not taste)
    - sonnet 3/3: perfect alignment; latency 50s vs 95s, nightly path user-invisible; ~$0.1/day; **no turn-routing** (haiku failure mode is length-independent)

5. **Handover two-segment topology** (replaces brainstorm §3 LLM auto-emit, deleted):
    - sync skeleton (code, <500ms, mandatory, 0 LLM): State / Affect 4-dim / Todo / Today done / Alerts / audit_log last 5 / Reference last 3 commits
    - async narrative (LLM best-effort, may lag at next start, non-blocking): Context narrative section
    - Template landed at `~/Desktop/2026-05-23_handover-template.md` (8 sections), pending Lumi edit + lock

6. **Popen triple-redirect hard constraint** (Agent A 2026-05-23 02:00 traced ny-memm legacy: the 5/11 stuck-prompt bug was fixed 5/12; root cause = subshell fd leak. marrow current SessionStart does not block because it is pure SQL read + stdout JSON with no Popen and no LLM — any Popen added later must obey):
    - `stdin/stdout/stderr=DEVNULL`
    - `start_new_session=True` (setsid, detach controlling tty)
    - `close_fds=True`
    - missing any of the three = 100% reproduces the legacy stuck-prompt; goes into safety-nets checklist + code-review gate

7. **6AM day boundary** (replaces current 5AM rule at `diary.py:256-275`); all schedules realigned.

8. **Schedule** (4 launchd plists at `~/Library/LaunchAgents/mw-*.plist`):
    - 03:00 daily db-backup (unchanged)
    - **07:00** daily nightly roll-up (was 04:00; mw-diary-routine.plist)
    - **19:00** daily catchup (was 16:00; mw-diary-catchup.plist)
    - **Sun 12:00** jsonl-cleanup (was Sun 05:00; mw-jsonl-cleanup.plist, avoid day-end collision)

9. **Tasks** (renames threads table, migrate backfill):
    - schema minimal: `id / title / status (active|done|archived) / due / completed_at + ts`
    - extension fields (source / category / parent_id / recurring_rule / external_id / pinned) → FUTURE.md `tasks_table_extensions` (written 2026-05-23, Phase 2 closeout tail)
    - dashboard renders `## Today done` + `## Todo` only, no source/category labels visible
    - edit priority: dashboard hand-edit = priority; reconcile always overwrites marrow_auto writes

10. **Candidates 0-audit pipeline** (no approval UI, no `mw confirm` CLI):
     - entity/pref conf ≥0.8 → direct insert status=auto; <0.8 drop
     - vocab conf ≥0.7 → direct insert; use_count ≥3 auto-promote dormant→active
     - milestone conf ≥0.85 → direct insert + dashboard alert line `milestone added: <CJK title>`; 7d undeleted → auto-confirm
     - thread/task → SessionEnd LLM extracts → direct insert tasks table status=active; dashboard line delete = drop

11. **No-decay = `pinned=1`** (Lumi had prior-window edit DESIGN subpage rule: memes / people are no-decay):
     - vocab.pinned column added; entities.pinned column added
     - current 5 cipher rows backfill pinned=1
     - identity anchors (`鸭子=屿忱` / `念念=Lumi`) permanently pinned; ordinary memes/people pinned=0 follow aging

12. **Aging rules** (07:00 nightly, code-only, no LLM):
     - vocab `last_seen > 90d AND pinned=0` → demote dormant (recall excludes); revive paths = LLM extract vocab key match auto-reactivate / `mw vocab promote <key>` / never auto-delete (only `mw vocab delete <key>` manual)
     - task status=active with 0 mention 30d → auto-archive
     - milestone alert line 7d undeleted → auto-confirm

13. **Token path**: raw transcript hits LLM 1× only (SessionEnd sonnet single call); nightly sonnet reads digest (1-3k chars vs raw 20-40k); overturns the "raw passed twice" wastage.

### DECISIONS.md edits this window

- L11 SessionEnd code-only → `[revising]` (false red-line overturned, SessionEnd async sonnet is main path)
- L32 04:00 single_call main → `[revising]` (moved to SessionEnd; 07:00 nightly is read-only roll-up)
- 5 new entries appended after L40 (Popen triple-redirect / tier all-sonnet / 6AM + schedule / handover two-segment / tasks + candidates / pinned + aging)

## Open — not handled this window (retain to next)

### Reset rollout path (Phase 2.5 plan)

**2.5a — write design (next window priority)**
- DECISIONS: fill in remaining detail (handover two-segment / candidates 0-audit / pinned etc); use grill-with-doc skill to converge
- DESIGN: rewrite L131 SessionEnd section + Hooks section + Phase plan + subpage section (confirm prior-window memes/people no-decay edit landed)
- `docs/notes/2026-05-23_sessionend-llm-pipeline.md` start design draft

**2.5b — async LLM framework (1-2 windows)**
- SessionEnd async detach (Popen triple-redirect + setsid + close_fds, ping-pong stability test)
- SessionEnd-catchup (SessionStart Popen same shape)
- handover sync code render → `marrow/handover_render.py` (write after Lumi template lock)

**2.5c — segment migration (3-5 windows, one segment at a time)**
1. `===AFFECT===` per-ep + 6AM boundary + importance 1-5 clamp (`diary.py:256-275`, `_build_affect_rows ~L563-600`)
2. `===ENTITY_CAND===` + entities table writes (fix 0 rows; combine with entities.pinned column + FTS5 tokenizer rebuild in one migration)
3. `===THREAD_CAND===` → tasks table (threads migrate rename)
4. `===MILESTONE_CAND===` + dashboard alert line + 7d auto-confirm
5. `===VOCAB_CAND===` + use_count code segment + vocab.pinned column + 5 cipher backfill pinned=1 + vocab leg recall_fusion
6. `===DIGEST===` (200-400 char compressed narrative, fed to 07:00 roll-up)
7. `===NARRATIVE===` (handover async segment, atomic append after sync skeleton)

**2.5d — 04:00 demotion + file rename**
- `diary.py` split → `extract.py` (~150 LOC) + `rollup.py` (~120 LOC) + `catchup.py` (~80 LOC); each ≤200 LOC
- 04:00 → 07:00 rename + demote to read-only roll-up
- 3-5 day diary literary-quality A/B verification

**2.5e — schedule plist realign**
- mw-diary-routine.plist 04:00 → 07:00
- mw-diary-catchup.plist 16:00 → 19:00
- mw-jsonl-cleanup.plist Sun 05:00 → Sun 12:00
- mw-db-backup.plist unchanged

**2.5f — pinned + no-decay landing**
- vocab.pinned + entities.pinned column migrations; 5 cipher backfill pinned=1
- aging code rule `last_seen > 90d AND pinned=0` gate

### Recall path fixes (identified prior window, not done, retain)

- **`budget_chars` per-item cap** (`marrow/recall.py:460-471`, high impact): a single long event eats the budget, dropping the remaining 9 hits. Fix = `budget_chars // limit` per-item. Run tdd red test "10 hits with one 3000-char event still returns 10 short rows".
- **FTS5 trigram fails on 2-char CJK** (`marrow/storage.py` events_fts tokenize='trigram'): swap to `unicode61 remove_diacritics 2` + jieba/cppjieba segmenter + `INSERT INTO events_fts(events_fts) VALUES('rebuild')`. Schema-level, bundle with entity writes + entities.pinned migration in one migration.
- **MCP daemon restart caveat** (`marrow/daemon.py`): stdio long-runner, code changes don't apply until next cc launch. Add one-liner to CLAUDE.md (not written).
- **milestones family/friend scope empty** (data gap, not bug): `scope` only `me=1` / `us=12`. Wait for Phase 2.5c entity pipeline to auto-surface.

### Prior-window retain (untouched this window)

- affect day-boundary 5AM rule → 6AM rewrite (`diary.py:256-275`)
- importance 1-5 scale clamp (`diary.py:_build_affect_rows ~L563-600`)
- mood overlay on diary render (`subpages_render.py:render_diary`, add `[Mid/Calm | <CJK label>]` at section head)

### Phase 3 backlog (retain, brainstorm §1 gaps E/F/G)

- writer authority / drift_sweep / convention_injection / claude_md_render_guard (all REQUIRED, mechanism Pending)
- static-layer future retirement (`~/.claude/CLAUDE.md` family / cipher / MCP guide → daemon-rendered; **only `interaction` stays static**); prerequisite = Phase 3 claude_md_render_guard must land first

### Brainstorm note useful points not handled (retain)

- §2.2 affect 4-dim label unification: `valence ∈ {Low, Neu, High}` / `arousal ∈ {Calm, Active, Intense}` / `trend ∈ {Stable, Wavy, Stormy}` / time markers Nh-Nd-Nw ago — pending Lumi demo, then write into DECISIONS
- §2.2 emotional-pending lifecycle: insert from diary unresolved_event / resolve via reconcile_keywords or `mw set --resolved` or md direct delete / TTL 14d auto-stale (pending Lumi)
- §1 gap H entities table writes → folded into 2.5c step 2
- §1 gap K subagent_usage_logging (llm.py per-call token/cost) → FUTURE already has same-name entry
- §1 gap L vocab/stickers/threads dead inventory → handled via 2.5c segment migration
- §9 meta-issue review pipeline blind spot → `workflow_reflection_skill` (FUTURE Phase 5 already has same-name entry)
- prior window e37631b already fixed milestone gate; gap A "identity anchor recall misses milestones" remaining backstop = entity pipeline → 2.5c

### Hygiene (retain)

- 9 old worktree branches dangling; main guardrail blocks `git branch -D`; Lumi runs manually
- worktree-agent-a13a751e533445bc6 / worktree-agent-abc5afb10dd92cda6 dirs removed, branch refs dangling
- 5/17-5/20 affect blank: skip, do not backfill ✅

## Suggested skills for next window

- `grill-with-doc` for 2.5a design (DESIGN L131 rewrite + DECISIONS detail fill-in)
- `tdd` for `budget_chars` per-item cap + Popen triple-redirect tests + handover_render template contract
- `writing-plans` for 2.5b/c/d/e/f rollout detail (after DESIGN is written)

## Reference

- This window deliverables (0 commits, brainstorm-only):
  - `~/Desktop/2026-05-23_handover-template.md` (handover template 8 sections, pending Lumi lock)
  - `~/cc-lab/marrow/FUTURE.md` Phase 2 closeout tail added `tasks_table_extensions`
  - `~/cc-lab/marrow/DECISIONS.md` 5 reset-core entries shipped this window
  - `~/Desktop/marrow_ab/` (Agent B test artifacts: 6 runs + summary)
- Last 3 commits before this window:
  - 52d6945 docs(handover): 22:20 — Round 3 recall fixes + 3 unfixed findings
  - e37631b fix(recall): surface milestones on long queries + align MCP/hook
  - af87881 docs: handover close + retain-untouched rule
- Brainstorm source: `~/Desktop/2026-05-22_marrow-reset-brainstorm.md`
- Agent A artifact (ny-memm popen root cause): not persisted, summary in §6 above + DECISIONS Popen entry
- Agent B artifact (LLM A/B test): `~/Desktop/marrow_ab/` (script + 6 runs + summary.json)
