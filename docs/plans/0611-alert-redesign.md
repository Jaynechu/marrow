# 2026-06-11
# Alert redesign — first-failure-visible, dedup-stable, no silent layer

> Root findings: docs/notes/0611-system-review.md (P0/P1). This plan is the build spec; each item = one logical commit. No schema change needed — alerts table + (type, fingerprint, resolved=0) dedup stays.

## Principles

- First real failure alerts immediately. Dedup (stable fingerprint + hit_count) handles repetition, not a prior-fails gate.
- Fingerprint = stable low-cardinality token. Exception text, sid, paths go in message=.
- The alert pipeline itself must not be able to fail silently (fallback sink).
- Catchup must never permanently park a sid (no terminal-less skip states).
- Skips are terminal states, alerts only for failures; misclassification fixed at classifier, not by alerting on healthy skips.

## Batch A — unbreak the chain (P0)

1. catchup P5 fix · sessionstart_catchup.py `_classify`
   - in-flight iff: start newer than end_row AND no sessionend_extract terminal row (ok/skip/fail/partial/reset) with id > that start id AND start age < 15 min.
   - terminal row after start → fall through to states 2-5 (so fail/partial sids re-spawn, capped by MAX_FIRE).
   - stale start (>15 min, no terminal) → treat as died mid-run → spawn.
   - Tests: partial:digest sid re-spawns; in-flight within grace skips; stale start spawns; ok sid still skips.
2. first-failure alert · sessionend_async.py `_write_final_audit`
   - Drop prior_fails>=1 gate. fail:* → critical, partial:* → warn, immediately.
   - Keep type-level fingerprint sessionend_async_failed (collapse, hit_count++, message=latest sid+summary). Delete now-dead silent-death counting block.
   - Retry still comes from fixed catchup; alert no longer depends on it.
3. add_alert fallback sink · repo.py `add_alert`
   - Wrap body; on any exception append JSON line to DATA_DIR/alerts-fallback.jsonl (mkdir ok) + stderr. Never raise.
   - sessionstart_catchup.main: on boot, drain alerts-fallback.jsonl back into alerts table (best-effort, then truncate).
4. aging flush in finally · aging.py `main`
   - Move pending_alerts flush into finally before conn.close(); audit INSERT failure no longer eats alerts.

## Batch B — correctness + coverage (P1)

5. reconcile_ref scoping · sessionend_writers.py `seg_affect`
   - Candidate SELECT adds `AND date = ?`; if no same-day unresolved row, skip resolve + audit_log note (no cross-day guessing).
6. stable fingerprints · hooks.py 3 sites
   - sessionend_spawn_failed / atlas_hook_error / hook_dispatch_failed:{event}; exception → message=.
7. wx death escalation · synapse_wx/loop.py
   - Consecutive provider-death counter on MainLoop (reset on successful recv). >=3 with session_id set → AlertSink critical + one user bubble (provider.dead). _ensure_provider spawn failure routes the same counter.
8. stub diary unblock · daily_catchup.py `pending_days`
   - done-set excludes rows where content is the stub; daily re-runs day when digests exist.
9. missing-alert coverage adds
   - sync_loop._process exception → add_alert warn (fingerprint sync_loop_tick_failed:{target}) — closes MAP known-gap.
   - watcher SyncLoop/AtlasSweepLoop start failure → critical (watcher_thread_start_failed).
   - wx media: decrypt/upload failure + pdf extract repeated failure → AlertSink warn (fingerprint media_{in|out}_failed).
   - seg_task_cand embedder-absent path → reuse semantic_dedup.warn_embedder_missing alert (currently audit-only).

## Batch C — false-positive diet (P2)

10. digest_zero_write: only alert when session has >= 5 user events (sparse sessions legitimately empty).
11. daily_catchup_overflow: auto-resolve when pending_days() <= CATCHUP_MAX on a later run (aging pass or daily tail).
12. offsite backup: 1 retry after 30s before warn (iCloud mount latency).
13. drift dangling-delete: only warn after pairing TTL expiry AND path still absent.
14. backup.py docstring: drop stale "WAL" wording (DELETE mode is deliberate — DECISIONS.md).

## Lifecycle semantics (unchanged, documented)

- resolve = acknowledge, not fix: same (type,fingerprint) re-inserts on recurrence by design (anti-mute). Dashboard row shows hit_count so repeat offenders are visible.
- aging auto-resolve only for milestone_added (7d). No generic TTL — alerts represent unfixed state.

## Acceptance

- Kill sessionend_async mid-LLM-call → next SessionStart re-spawns it; second kill → critical alert on dashboard.
- Force digest LLMError once → warn partial:digest alert same run.
- Lock DB, fire add_alert → line lands in alerts-fallback.jsonl, drained next session.
- Legit short session → skip, zero alerts, catchup stays quiet.
- pytest green; live dry-run: `python -m marrow.sessionstart_catchup` against real DB shows expected spawn list only.
