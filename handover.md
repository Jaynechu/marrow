# Marrow handover

> Diary pipeline rebuilt + committed. Lumi prompt-tuning + events-pollution root fix pending. Read DESIGN/PROGRESS next.

## State (committed, not pushed)

- `bcde095` feat(diary): turn-routed digest SHORT/LONG, 3-tier skip, lessons dropped
- `9d179ea` docs: jsonl cleanup decided, transactions placeholder, lesson rework parked
- pytest 83/83 ✓

Route by turn count: ≤3 code-drop, 4–10 `DIGEST_SHORT` (may SKIP a no-outcome chore), >10 `DIGEST_LONG` (never SKIP, stub if haiku disobeys). `run_day` kept-filter + trivial placeholder. lessons extraction removed (parked: FUTURE `lesson_extraction_rework`).

Verified: `b1f6c86b` 22-turn Phase-1 session no longer SKIP-vanishes — heavy-work craft now kept in digest.

## Open — Lumi prompt calls (diary.py prompts are hers)

1. `DIARY_PROMPT` rule "no study/coding task detail" too weak — sonnet drops ALL work. Strengthen to "must write one line: what done + outcome".
2. `DIGEST_SHORT` (4–10 turns) may mis-SKIP sessions with real outcome. Review vs. `8a9d1efd` (5-turn schedule session with outcome).
3. `DIGEST_LONG` haiku wraps unwanted meta shell ("per diary compress rules…", "which day this belongs…"). Fix prompt wording; core craft unaffected.

Test: clear `diary`/`lessons` row for 2026-05-17 in `~/.config/marrow/marrow.db`, run `diary.run(day="2026-05-17")`, show diary text + KEEP/SKIP/DROP table. Token est only — llm.py records no usage (FUTURE).

## Open — root fix (code, next round)

Events table polluted by spawn-`claude` hooks: prompt-lint.py bare `claude -p` creates jsonl; transcript.clean ingests as 9 fake sessions (2026-05-17).

Fix (two layers): exclude transcript by jsonl **metadata structure** (headless `-p` marker, not payload) + rule that hook's claude call must not land in project jsonl. Verify leaked jsonl in `~/.claude/projects/-Users-Gabrielle-cc-lab-marrow/` carries headless `-p` structural marker.

## Suggested skills

- `tdd` — transcript hook-pollution filter (deterministic, fixed contract).
- `diagnose` — if structural-ID of leaked jsonl needs repro.
- `/loop` — if Lumi re-enters diary prompt-tuning cycle.

## Don't redo

- /clear does NOT change session_id (same jsonl). New sid = new cc process / window / resume.
- lessons removal is intentional (Lumi). Don't re-add without FUTURE redesign.
- diary.py prompts (DIGEST_SHORT/LONG, STITCH, DIARY_PROMPT) are Lumi-owned — restore from `bcde095` if reverted; don't rewrite.
- CC pinned to 2.1.142 (parse-bug); see `docs/notes/2026-05-18_cc-2143-toolcall-parse-bug.md`.
