# Marrow handover

> Phase-1 close-out done bar #2. blocker root-fixed (ADR-0004 model-set signal). #3/#4/#5 shipped, #7 adjudicated not-a-bug, #6 deferred. ONLY open thread: #2 data-restore awaiting Lumi's y/n.

## Awaiting Lumi (only open thread)
- #2 purge recovery: 52 backup-only rows triaged — 48 = correctly-deleted haiku-spawn, 4 = wrongly-deleted REAL (ids 453-456, sessions `9851c4d9`+`f8b22b07`, two "hello"→persona-greeting turns; jsonl gone, content thin). Idempotent restore SQL ready in `docs/notes/2026-05-19_purge-recovery-triage.md`. NOT executed — destructive, Lumi's call.

## Done this window
- blocker#1: `is_headless` rewritten per ADR-0004 — assistant model-set ⊆ config `worker_models` → headless, else empty-set spawn-prompt-head backstop. `entrypoint` abandoned. `cleanup.py` auto-follows. Config single-source + sync-guard test. Live jsonl: real opus/clawbot → keep, haiku spawn → headless.
- #3: diary same-day correction (`run_day(force=)` deletes+rewrites; catchup stays idempotent) + `fcntl.flock` app-lock serializes routine/catchup/manual (DESIGN L188 REQUIRED net).
- #7: `_routine_target` adjudicated NOT-a-bug — 02:00 run correctly targets prev-closed day under `[04:00,04:00)`; regression-locked 03:59/04:01.
- #4: `marrow/backup.py` `VACUUM INTO`+`os.replace` atomic local + iCloud offsite, keep=14 prune, dry-run/`--apply`, per-leg `add_alert` on fail. `deploy/mw-db-backup.plist` daily 03:00.
- #5: `archive_events` mirrors one batch `audit_log` row/call (n==0 → none) in same txn.
- #6: events_vec provenance DEFERRED → FUTURE (embedder itself deferred; avoid Phase-1 base-schema thaw with no writer).
- #8: DESIGN L139/L170 catchup doc-drift (SessionStart → 16:00 launchd) corrected; dead `return False` removed by blocker#1.

## Remaining minor (non-blocking, NOT done)
- #8 timeout not process-group kill: `llm.py` `threading.Timer` kills main `claude`, orphan children possible — robustness, deserves its own focused TDD round.
- #8 lessons 2 stale rows — safe (no auto read-path); Lumi-intentional removal, leave.

## State
- main: blocker#1 + #3 + #4 + #5 + ADR-0004 + census/triage notes + doc-fixes + PROGRESS deltas. pytest 125 (real-run on main, not worktree self-report). Pushed → origin/main.
- All marrow launchd jobs (diary routine/catchup, jsonl-cleanup, new db-backup) NOT launchctl-loaded — Lumi gate, unchanged.
- 4 agent worktrees locked → harness auto-cleans; `phase1-review` worktree from prior window untouched. `.claude/worktrees/` now gitignored.

## Don't redo / decided
- `entrypoint` is NOT a headless marker — ADR-0004 supersedes; do not reopen.
- #7 `_routine_target` is correct under the 04:00 boundary; the "off-by-one" was a wrong mental model. Do not "fix" it.
- #2 restore is Lumi's call — never auto-execute.
- `isolation:"worktree"` subagents branch from the origin baseline, not current main → always cherry-pick to main and real-run pytest there; never trust the worktree's own pytest count.
