# Marrow handover — Phase 2 parallel build: worktrees done, MERGE pending (2026-05-20)

Plan: `~/.claude/plans/nifty-seeking-llama.md` (5-step recovery + worktree scope). DECISIONS.md Phase 2 = truth. Next window: MERGE in fresh context.

## State of main

- main = c2dae8c (Step 0 freeze) + 5c95008 (B) + 1b98a55 (E); pytest 174 green
- Step 0 verified: ~/.config/marrow/marrow.db live-migrated float[384]→[1024], 1301 events intact, idempotent; backup marrow.db.bak-step0-20260520-011021

## Isolation incident

B + E committed straight to main, not isolated. C branched off 5c95008 (carries B). A clean off c2dae8c. D off 8828904 but self-synced storage.py = byte-identical to frozen; safe.

## Branches to merge (order A→C→D)

- A `worktree-agent-aae03ecdff44bfdfb` 7cdb6b7←c2dae8c: diary.py single-call, 785 lines, isolated/clean
- C `worktree-agent-a920e84c084052b88` 58433b3←5c95008: recall.py + repo.py/daemon.py wiring; carries B
- D `worktree-agent-aa58a15244899604c` 59f6bea←8828904: ONLY hooks.py + test_hooks.py; storage.py no-op vs frozen; edited config.default.toml [recall]
- B (5c95008) + E (1b98a55) in main, never line-reviewed

## Lumi decisions (apply during merge)

1. Mood labels → English: `hooks.py:29` `_INTENSITY_LABEL`→`[(0.4,"calm"),(inf,"intense")]`; `hooks.py:28` `_VALENCE_LABEL`→`[(-0.3,"low"),(0.3,"neutral"),(inf,"high")]`. A's `SINGLE_CALL_PROMPT` label instruction → English (no CN/EN mix).
2. `config.py load()` = NO default-merge. Fix: shallow-merge default under user (C added [recall] keys old config lacks). User config.toml [embedding] already hand-synced.
3. SINGLE_CALL_PROMPT Lumi-reviewed OK. Review: reuse shared DIARY_PROMPT (DRY), don't delete Lumi content (bloat from verbatim copy).
4. CJK-FTS gap: `events_fts` unicode61 does not tokenize CJK. Fix: add CJK tokenizer + rebuild 1301-row index. Fills Phase-1 gap, approved.

## Review red flags

- B + E not line-reviewed (green tests ≠ correct logic)
- D heartbeat fires gap-day only; DECISIONS L37/DESIGN L190 want ">48h OLD or gap day"—missing >48h arm
- diary.py 785 / subpages_render.py 324 exceed 300 soft cap (DRY-violation)
- C: verify bge-m3 ran (HF cache ~/.cache/huggingface/hub/models--BAAI--bge-m3/, 2.1GB); 183 green may be FTS5-only degrade
- C/D both edited config.default.toml [recall], collide: C=vector true+weights (enable), D=vector=UserPromptSubmit fallback. Split at merge.
- A event_hint FTS5 CN→NULL—re-verify after CJK patch

## Merge plan (5 steps)

1. Merge A→C→D; D=hooks.py/test_hooks.py only
2. config.default.toml 3-way + split [recall] key
3. CJK tokenizer patch on events_fts + rebuild 1301 index
4. Fix config.py default-merge
5. Wire D's UserPromptSubmit stub → C's `recall.recall_fusion(conn, text, limit=K)`. Then 3 concurrent review subagents (blind/DESIGN trace/code), main adjudicates; /ultrareview Lumi-triggered

## Skills for next session

- `tdd`: CJK patch + config-merge are deterministic, fixed contract
- `review` workflow (CLAUDE.md): 3 concurrent subagents, main adjudicates
- `simplify`: end diary.py DRY collapse

## Constraints

- Step 0 schema frozen+verified—CJK patch only, nothing else
- Worktrees DONE; merge existing branches, don't re-dispatch
- Recall API: `recall.recall_fusion(conn, query, limit, budget_chars, *, w_vec,w_bm25,w_recency,w_affect,min_score)`; write path `recall.embed_event`/`recall.embed_pending`
- Tasks #1-6 done; #7 (merge+review) only open task
