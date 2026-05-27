# Phase 2 review — 2026-05-21 ✅

> /rr phase 2 run. Step 0 fact-checker baseline + Step 1 blind + Step 2a traceability + Step 2b code-quality, all reports cross-checked.

## Scope
- Phase 2 = affect + recall + sub-page render + refusal sentinel + SessionStart backdrop (DESIGN L163, DECISIONS L20-38)
- Shipped to main: refusal sentinel (5c95008), sub-page render (1b98a55), schema freeze (c2dae8c)
- Pending merge in worktrees: A diary single-call (7cdb6b7), C recall (58433b3), D hooks/backdrop (59f6bea)
- Tests: 173 passed, 1 failed (fixture date drift, not code)

## Cross-checked findings

### Real bugs / safety-net gaps on main
1. **CJK tokenizer missing** — storage.py:163 `events_fts` uses unicode61, no CJK split. CN event_hint → NULL match. Phase 1 gap, approved in handover.md:27, never patched. (traceability MISSING; blind not visible)
2. **config.py: no merge at all** — config.py:20-40 copies default once on first run, then loads user toml standalone. Worse than handover's "shallow merge" framing. New keys added to `config.default.toml` (e.g. worktree-D `[recall]`) absent in existing installs. (traceability DRIFT; code-quality confirmed)
3. **Refusal fingerprints EN-only** — llm.py:253-255 `_REFUSAL_FINGERPRINTS` misses CN refusals ("很抱歉，我无法…"). `stop_reason=="refusal"` still primary, fingerprint layer is defense-in-depth but inert for CN. (blind + code-quality)
4. **subpages.py:123-124 hash file not atomic** — `_atomic_write(path,new)` then `hash_file.write_text(...)`. Crash between → next render false "hand-edit" conflict + alert noise. (code-quality)
5. **subpages.py:102 unclosed file handle** — `open(path, encoding="utf-8").read()` no `with`. (code-quality, low blast)
6. **hooks.py:240-241 session_end swallows PermissionError silently** — violates DESIGN L33 "every scheduled job writes alert row on failure". TCC-blocked install never alerts. (code-quality)
7. **storage.py:222-228 events_vec dim mismatch silent on non-empty old table** — comment says "never silently discard" (correct) but no alert row fires → operator unaware re-embed needed. (code-quality)
8. **Test fixture drift** — tests/test_diary.py::test_catchup_caps_and_alerts hardcoded 2026-05-16 outside 7d window from today 2026-05-21. (fact-check)

### Real bugs in worktrees (fix before merge)
9. **diary.py:550-563 (worktree-A) no clamp on LLM-supplied valence/arousal/importance** — hallucinated `valence=10.0` corrupts weighted std + label lookup. (code-quality)
10. **hooks.py:28-29 (worktree-D) mood labels still CN** — handover decision 1 requires EN; not applied. (code-quality)

### Documented as drift but actually NOT a bug
- **Heartbeat ">48h OR gap-day"** — handover.md:31 flags worktree-D as drifting. Reality: DECISIONS L37 was overwritten in-place to "gap-day only"; worktree-D matches DECISIONS; DESIGN L190 is the stale line. Fix = remove stale DESIGN line, not change code. (traceability)

### Smells / over-engineering (defer to simplify pass)
- diary.py 785 LOC (worktree-A) exceeds 300 soft cap; map-reduce path duplicates single-call iteration
- subpages.py + subpages_render.py duplicate `_MARKER_START/_m0/_m1` constants
- llm.py:290-313 `_log_usage` opens new DB conn per LLM call (smell under WAL, not bug)
- SCHEMA.md root file pre-Phase-2 stale (still lists retired emotions/people/preferences/dir placeholders; missing affect/entities DDL). Doc-only.

### Not Phase-2 defects
- 9 runtime alerts (ollama unreachable / claude_cli rotating) → fallback chain working as designed per DESIGN L154. Chain exhaustion DOES log alert (not silent), so blind's "silent drop" concern is not realised.

## Decision — fix-now (main, items 1-8)
- 1 CJK tokenizer — schema change + rebuild migration
- 2 config.py merge — prereq for worktree-D merge
- 3 CN refusal fingerprints — add CN list
- 4 hash file atomic — temp+replace pattern
- 5 unclosed file handle — `Path.read_text`
- 6 session_end alert on PermissionError — write alert row
- 7 events_vec dim mismatch alert — write alert row
- 8 test fixture — use relative date

## Decision — fix-before-merge (worktree, items 9-10)
- 9 diary affect clamp (worktree-A)
- 10 mood labels CN→EN (worktree-D)

## Decision — doc cleanup
- DESIGN.md L190 remove stale heartbeat ">48h OR gap-day" line
- SCHEMA.md update to actual Phase 2 DDL

## Decision — defer
- diary 785 LOC + duplication → post-merge simplify
- subpages duplicate constants → post-merge simplify
- _log_usage per-call conn → FUTURE
- refusal in tool_use block (llm.py:247-255) → not currently triggered with isolation on

## Source agent reports
- baseline: aeac2fb0482ea309f
- blind: a8975754e14bf6bff
- traceability: a0f6eacc5fb9be5ee
- code-quality: aec7e65d2076a743b
