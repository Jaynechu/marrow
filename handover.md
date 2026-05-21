# Marrow handover — 2026-05-21 23:45

## This session shipped
- Workflow infra: 5 agents + /rr command + 2 rule files + CLAUDE.md slim (62→30 lines). marrow `3bacaef`, pushed.
- Hook fix: per-key flag + 30-line threshold for prompt-lint. ~/.claude `21094cd`, local only per global rule.
- `/rr phase 2` piloted end-to-end. Findings in `docs/notes/review-phase-2.md`.

## Next session — act on docs/notes/review-phase-2.md
Priority order:
1. **A/C/D worktree merge** — real Phase 2 completion. `.claude/worktrees/` holds diary affect / recall / hooks. Decide order, resolve conflicts, pytest each, PROGRESS delta line per merge.
2. **config.py merge** — prior handover misdiagnosed as shallow vs deep; actually never merged. Investigate then merge.
3. **CJK tokenizer MISSING** — DESIGN + prior handover both flagged but no implementation. Use /tdd skill.
4. **handover-drift cleanup** — DECISIONS L37 already overrode DESIGN L190 (gap-day only). Delete obsolete "drift" flag wherever it lingers.
5. **fixture date drift** — 1 pytest failure, hard-coded date drifted. Trivial.

## Skills suggested
- /tdd — CJK tokenizer (red-green-refactor on fixed contract)
- grill-with-doc — after merges, before Phase 3 plan
- handoff — at session end

## Don'ts
- DO NOT re-run /rr phase 2 (already done, ~177k tokens — no new info to extract)
- DO NOT push ~/.claude (local commit only per global rule)
- DO NOT delete handover.md (fixed name, overwrite only)

## Reference
- `docs/notes/review-phase-2.md` — full /rr findings
- `.claude/rules/build-workflow.md` — /rr usage, review 5 steps
- `.claude/rules/agent-dispatch.md` — delegation policy
