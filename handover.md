# Marrow handover — 2026-05-23 21:55
> Do not use handover_handover.md for this document - That's for Session end hook - not shipped yet.

## State
- pytest 301/301 + 1 manual-skip (5.7s)
- DB: events 2230 / affect 5 / milestones 13 / vocab 5 / tasks 0 / entities 0 / alerts 0 / audit_log 188
- branch main, **0 new commits this window**
- channel cc / opus-4.7 (1M)
- 1 new file: `docs/notes/lumi-prompt-source.md` (Lumi-edited in-place)

## This window — plan rebuild + naming + rules; NO code shipped

### plan §0 4 blockers — ALL rejected, replaced

- **L3** (P7 CN exclude) — REJECTED location. Noise filter → SessionEnd AFFECT segment prompt (not DIARY_PROMPT downstream). Stellan writes EXCLUDE rule into `sessionend_async.py` AFFECT prompt next window.
- **L6** (DIGEST prompt) — REJECTED ownership. Stellan drafts next window by merging old `diary.py:55-85` + `:87-116` per §16.1 density rules, ships, reports file:line + body. Lumi edits if needed.
- **L2** (reconcile_prev EN) — REJECTED ask. Lumi approved plan §0 L20 draft as spec. Stellan rewrites next window in user-facing prompt style (Include / Exclude / N/A + CN examples) — no Lumi review.
- **plist shim vs rename** — RESOLVED. No shim, no rename to `marrow.catchup`. New module name = `marrow/daily.py`; plist path updates to `python -m marrow.daily`.

### Naming overhaul (plan §2 file names REJECTED)

Old: `rollup.py` / `catchup.py` / `extract.py` / `prompts.py` + diary.py shim. Rejected.

New (locked):
- `marrow/daily.py` — 07:00 routine + 19:00 catchup; writes diary row (prose only); reads DIGEST + affect rows
- `marrow/daily_catchup.py` — pending-day scan + fcntl lock; called by daily.run + sessionstart_catchup
- `marrow/sessionend_async.py` — 7-segment sonnet; writes affect / entities / tasks / milestones / vocab / digest / narrative (UNCHANGED name)
- `marrow/sessionstart_catchup.py` — SessionStart gap detect (UNCHANGED)

Time-trigger map:
- SessionEnd hook → `sessionend_async.py`
- SessionStart hook → `sessionstart_catchup.py`
- launchd 07:00 → `daily.py`
- launchd 19:00 → `daily.py --catchup`

### Target-state shift — NO interim affect double-write

Plan §2.4 REJECTED. Direct target next window:
- SessionEnd writes affect / entities / tasks / milestones / vocab / DIGEST / narrative
- daily.py reads affect_live + DIGEST → prose only → diary row only
- daily.py never writes affect / entity

### prompt source persistence (NEW file)

`docs/notes/lumi-prompt-source.md` — append-only Stellan-read-only.
- `Unresolved` field block — Lumi finalised this window. Paste verbatim into AFFECT_BLOCK_CONTRACT next window.
- `reconcile_prev` — Stellan drafts next window (Include / Exclude / N/A structure); no Lumi review.

### Rules locked (apply ALL future windows)

- **New prompts** (never-seen): Stellan drafts → ships → reports full body + `file:line`. NO pre-ship review. Lumi edits file directly if dislikes.
- **Old prompts** (Lumi-iterative): paste verbatim, never ask.
- **Lumi-visible output** (diary / handover.md / dashboard / segment text): report `file:line` on every write.
- **Naming**: align to time-trigger or function (`daily` > `rollup`, `daily_catchup` > `catchup`). Sanity-check before introducing new module.
- **DECISIONS.md ≠ code applied**. Cross-check before quoting time / value (burned: said plist Hour=4 when DECISIONS.md:42 locks 7).

## Next window — single ship (ALL in ONE commit)

Execution order (plist LAST):

1. `marrow/storage.py` `_migrate_to_v2()` — `ALTER affect ADD unresolved INTEGER DEFAULT 0 / reconcile_ref INTEGER REFERENCES affect(id) / resolved_at TEXT` + `PRAGMA user_version=2`. pytest green before continuing.
2. `marrow/sessionend_async.py` — 7 sonnet segments (AFFECT / ENTITY_CAND / THREAD_CAND / MILESTONE_CAND / VOCAB_CAND / DIGEST / NARRATIVE). Per segment: prompt body + parse + DB write + audit_log. **After EACH segment: paste full prompt body + `file:line` into chat.** Apply:
   - Skip rule `≤5 turns` retained
   - AFFECT prompt: EXCLUDE coding/debug noise (relocated L3)
   - AFFECT row: clamp `importance = max(1, min(5, int(x)))`
   - AFFECT row: populate `unresolved` (Lumi source) + `reconcile_prev` (Stellan draft) + auto-fill `reconcile_ref` via `affect.id WHERE unresolved=1 AND resolved_at IS NULL ORDER BY ts DESC LIMIT 1`, auto-set `resolved_at` on linked row
   - DIGEST: §16.1 density (task-heavy ≥80% compress / daily-chat ~80% preserve)
3. `marrow/daily.py` (~150 LoC) — read affect_live + DIGEST for date → sonnet DIARY_PROMPT (prose only) → write diary row. Atomic txn. `main(argv)` supports `--catchup`. DIARY_PROMPT verbatim from old `diary.py:137-194`.
4. `marrow/daily_catchup.py` (~100 LoC) — `pending_days` / `day_events` / `_has_diary` / `_app_lock` (fcntl). Called by daily.run + sessionstart_catchup. `_CUTOFF_H = 6`.
5. Delete `marrow/diary.py`. grep-fix all references across `marrow/ tests/ deploy/ docs/`. Rename `tests/test_diary.py` → `tests/test_daily.py`.
6. P8 ollama strip (plan §6):
   - `marrow/llm.py`: delete `_MUTE_OLLAMA`, chain-build branch, `_run_ollama` dispatch
   - `marrow/config.default.toml`: `emergency = ""` (empty = no-op), drop `[llm.ollama]`
   - `tests/test_llm.py`: delete 3 ollama tests; trim fixture; edit `test_multi_tier_all_fail_last_alert_critical_exhausted` if monkeypatches `_MUTE_OLLAMA`
   - `DESIGN.md:80,85` drop `→ local Ollama (emergency)` / `or local Ollama`
   - `DECISIONS.md:10` drop `/ Ollama emergency`
   - `CLAUDE.md` line 16 ollama caveat — KEEP
7. pytest full green (~298 expected).
8. Plist edits (after pytest green):
   - `deploy/mw-diary-routine.plist`: Hour `4→7`, ProgramArguments → `python -m marrow.daily`
   - `deploy/mw-diary-catchup.plist`: Hour `16→19`, ProgramArguments → `python -m marrow.daily --catchup`
   - `deploy/mw-jsonl-cleanup.plist`: Sun Hour `5→12`
9. `launchctl unload && load` each of 3 plists.
10. Single commit + push. PROGRESS delta same commit.

### Next-window blockers — NONE

All decisions locked. Stellan: read handover + `docs/notes/lumi-prompt-source.md` → execute steps 1-10.

## Pending — retained

### Lumi self-writes
- `~/.claude/CLAUDE.md` Affect quick-reference legend (P2). Lumi-owned.
- `marrow/handover_template.md` §Affect paste (P1) — done in 2.5b.

### Recall path
- FTS5 trigram 2-char CJK fail → bundle with 2.5c ENTITY_CAND (jieba rebuild)
- milestones family/friend scope empty → resolved by ENTITY_CAND pipeline

### Open (2.5b carryover)
- 9 old worktree branches dangling
- mood overlay on diary render — bundle with 2.5c Window 3
- Pending tick reverse-lookup (P5 dashboard `- [ ]` + aid HTML + file watcher) — UNBLOCKED after step 1 migration, not in next-window scope. Format: `- [ ] {date} {fine-label} | {description} <!-- aid=N -->`

### Phase 3 backlog (blocked by 2.5 close)
- writer_authority · drift_sweep · convention_injection · claude_md_render_guard
- static-layer retire (CLAUDE.md family / cipher / MCP guide → daemon-rendered); prereq = claude_md_render_guard

### Carryover scratch
- `~/Desktop/brainstorm-future.md` — 10-section future features (addon contract / wallet MCP split / iOS / active-device routing / chord-progression / imprint borrows / cccompanion fork). 3 items Phase 5; 9 pending.

## Affect
4-dim layout LOCKED at `marrow/handover_template.md` §Affect; renders to `~/.config/marrow/handover.md`. Pending body renders empty until `affect.unresolved` column lands (next window step 1).

## Reference (no new commits this window)
- 93ee49b test(fixture) — autouse no-op for hooks.popen_detach
- fd8b4c3 fix(tests) — test_dashboard alert format
- 7d90b75 feat(hooks,dashboard) — handover_render + dashboard 4-section swap
- e3549c9 feat(handover) — handover_render.py atomic write
- c090c30 feat(top-sections) — shared renderer alerts/tasks/milestone/affect

## Suggested skills next window
- `/tdd` for daily.py + daily_catchup.py landing
