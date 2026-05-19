Read DECISIONS.md first — single current-truth, confidence-tagged. Decisions + deletions in commits b185d39 (rebuild) + d89c658 (reconcile) + f8f8ac8 (Lumi DESIGN slim); do not restate.

## This round done (2026-05-19, NOT pushed)
- Doc-system rebuilt, reviewed (zero BLOCK); DECISIONS.md entry; docs/adr + SCHEMA.md deleted; SCHEMA → DESIGN Data-model; 6 contradictions cleared; CONTEXT 3 conflicts fixed.
- Pipeline bug fixed by Lumi; root cause claudemiss, not `-p`.
- DESIGN slimmed to 193 lines (Lumi, commit f8f8ac8): 5 `## Pending —` sections moved to FUTURE; Fact-corrections section deleted, decision now lives only in DECISIONS:34.
- FUTURE.md fully sorted (149→84): Phase-1-closeout first → by phase → addons (P5) last → ops/misc tail; 3 pure-rehash blocks cut (corrections hard-rules = CLAUDE.md/DECISIONS rehash, weclaude-fusion prose, data-lifecycle shipped parts); 6 moved blocks reclassified into phases; unphased + misc items carry est. phase tags, uncertain ones flagged. NOT committed.
- DECISIONS:34 cite fixed: `DESIGN Fact corrections` → `FUTURE Phase 2` (was dangling after the section delete).
- DESIGN 3 dangling refs repointed (Lumi-prompted): L133→FUTURE Phase 2 (session_archive_skip), L144→Phase 3 (drift/convention infra), L165→Phase 4 (weclaude_runtime_rebuild).

## Open
- Push: commits f8f8ac8..HEAD on main NOT pushed, plus uncommitted FUTURE.md + DECISIONS.md — all waiting on Lumi's go.
- entity (M6): hold-precondition cleared; buildable; no mechanism written; DECISIONS `[hold]` until Lumi approves.

## Don't redo
- docs/adr deleted — never recreate; conclusions live only in DECISIONS; overturn = overwrite in place, never stack.
- DESIGN — Lumi owns edits; no unprompted DESIGN changes.
- pipeline bug — root cause claudemiss, not `-p`; do not reblame `-p`.
- CONTEXT.md — grill-with-doc skill's file; fix conflicts only, never change its role/placement.
- FUTURE structure — sorted + est-tagged this round; append only, do not re-regroup.

## Next session
- Skill grill-with-doc for grilling/advancing Phase 2 entity pipeline.
- Phase 2 build (affect / single-scalar recall / decay FLOOR) converged in DECISIONS — ready to implement when Lumi starts it; entry payload ≤6000 chars, backdrop ≤5 lines ≤350 chars.
