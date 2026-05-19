# Marrow handover — Phase 2 pre-build grill (2026-05-19)

Read DECISIONS.md + CLAUDE.md first. This file = next-window only, act on it.

## Locked this round (Lumi decided — do NOT re-ask)

- **A1 embedding**: bge-m3 runs in-process inside the marrow daemon (NOT via ollama; ollama is not installed and is no longer the recall lifeline — installable later, optional). bge-m3 kept, not downgraded.
- **A2 affect granularity**: per-episode (one row per lived episode), NOT per-event, NOT per-day. Effect anchor below.
- **Pipeline**: three layers → ONE. The 04:00 routine = a single sonnet call reading the day's clean events, emitting { diary (segmented by episode) + per-episode affect tag + entity }. per-session map/stitch deleted; kept only as an over-volume-line fallback (history: 0 hits). Rationale: fewest stages = least brittle; diary's natural paragraphs ARE the episodes; affect/entity are per-segment annotations, not a second pass.
- **B3 recall fusion**: keep single weighted scalar (claude-imprint's real code is scalar, its README "RRF" is mislabel — agent gh-api verified, not locally re-checked). Add normalization: vec = 1 - cos_dist; bm25 = per-query in-group abs(rank)/max; recency = exp(-days/30); affect = capped 0.10; init weights 0.55/0.30/0.15/0.10; MIN_SCORE start 0.35. Build-time tune from logs, not pre-guessed.
- **B5**: affect heartbeat fires ONLY when a day had events but no affect (align with catchup predicate) — kills false alarm on no-login days.
- **B6**: params start conservative, tune from audit_log/Monitor real behaviour, no pre-guessing.
- **B7**: recall trigger = (a) deterministic prompt line at backdrop tail as floor + (b) UserPromptSubmit deterministic vector fallback as primary; b waits until embedding installed; BOTH ship, b is not optional.
- **C entity**: build it, emitted in the single call, no separate chain.
- Old "unresolved = 04:00 sonnet reads whole day to judge" (old DECISIONS:24) **dropped** — emotional-pending folds into "recent/current emotion"; work/study unresolved goes to open threads, not into emotion.

### A2 effect anchor (Lumi stated explicitly — do NOT re-ask "what do you want")
SessionStart injection lets Claude know: ① each of the recent few episodes' emotion ② current emotion ③ recent overall calm-vs-swing ④ emotional pending (ONLY "things unresolved between us two emotionally"; everything else → open threads). "frequency / what she keeps bringing up" does NOT go into emotion (that's sqlite / open-thread domain).

## CLAUDE.md added (line 13)
Decision-ask discipline: when a tech decision needs Lumi, lead with effect/impact/recommendation in plain words; name options by effect not by unfamiliar tech terms; term explanations last for optional learning.

## Next = grill these 5 hard points (ordered; ① gates the rest)

1. **Single-call output contract**: how diary-segment ↔ episode ↔ affect tag ↔ entity coexist in ONE prompt without the creative task and the analytic task fighting. Working hypothesis: keep them isomorphic — diary's by-episode segmentation is its natural writing form, affect/entity are per-segment notes, not a separate analytic job. Stress-test this hypothesis adversarially.
2. **"One episode" segmentation**: boundary rule, cross-session continuation, the line between too-fine and too-blurred.
3. **Over-volume fallback line**: measure historical per-day clean-events token count with a REAL tokenizer; set the threshold + the slice-and-fallback rule for days above it.
4. **affect / episode schema**: supersedes the per-event schema in DECISIONS:21; episode↔event linkage; keep superseded_by / source / importance; the live VIEW.
5. **Update DECISIONS** to match all the above (per-event→per-episode, single-layer, in-process embedding, fusion normalization). DESIGN is Lumi-owned — do NOT edit unprompted; if it must change, report to Lumi first.

## Hard verify (no assumption as conclusion)
- 1M confirmed available (Lumi, NOT beta); architecture PINNED to 1M; 200K rejected.
- Evidence: heaviest day (5-18) = 238K tokens (~24% of 1M); single-session max = 65520 chars. (190K Lumi is working context, not input.)
- Verify: (a) 04:00 sonnet via claude_cli stream-json ACTUALLY receives 1M — write probe; (b) replace char ceiling with exact count_tokens.

## Process directive (Lumi explicitly required)
- Do NOT grill Lumi on these technical deep-dives — she cannot and should not answer them. Use **agent-vs-agent adversarial grill/debate** (like this round's 3 debate agents, iterable cross-questioning) to push to implementable.
- Bundle ONLY the points that genuinely need Lumi's call AND are answerable by effect into ONE final round (follow CLAUDE.md line13: plain-effect first).
- Do not re-ask anything in "Locked this round".

## Off-limits
- DESIGN.md Lumi-owned, no unprompted edits.
- DECISIONS overwrite-in-place, never stack; docs/adr deleted, never recreate.
- ollama not rejected (LLM-chain _MUTE_OLLAMA was "not installed + then-unstable", not a verdict) — do not re-blame it.

## Data snapshot (threshold starting point)
events 1195 rows; per-UTC-day chars: 5-18 = 238347 (25 sessions, test+migration pile, non-typical) · 5-19 = 119191 (7 sess) · 5-17 = 49829 (6 sess); single-row max 18333.
