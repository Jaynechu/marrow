# Marrow handover

> CRITICAL: entrypoint-marker false — `entrypoint=="sdk-cli"` ≠ headless. Bleed-stopped; blocker. Phase-1 review step 0–2 + stop-bleed verified; next = step 3 /ultrareview, step 4 close-out.

## Phase-1 review status (review window)

- step 0 fact-check ✓ · step 1 blind design-gap ✓ (2 opus, zero repo access) · step 2a traceability ✓ · step 2b code+logic ✓ · blocker double-checked ✓ (neighbour bleed-stop verified real, not self-report-trusted)
- Produced: CLAUDE.md review flow → 0–5 steps (`ea9e24c`); DESIGN mm+/mm- archive override (`eccc1df`). Branch `worktree-phase1-review` — see Worktree merge, MUST land on main before next window.

## Blocker: entrypoint signal wrong

Census (653 jsonl): sdk-cli 389 / cli 259 / vscode 4 / desktop 1. Assumption in `acafd60`+`8f2747f`+`b46deb1` wrong. ~51 min live damage: real `.jsonl` at risk.

Bleed-stop (`24830a3`): launchctl bootout, `is_headless()` hard-False, cleanup verified no-op (del 0 / kept 653). Previous purge (518→464) used same flawed judge — 54 rows may be recoverable from `marrow.db.bak-20260518-220058`.

## State (PUSHED — marrow main @ 39fbbff; worktree doc commits NOT yet on main)

- `39fbbff` docs(handover): purge reversed-premise sections
- `c4a12b4` docs(notes): parse-bug two layers + re-pin 2.1.142
- `33d6393` docs: bleed-stop handover + PROGRESS delta
- `24830a3` fix!: BLEED-STOP — is_headless hard-False, entrypoint signal wrong
- `8f2747f`+`b46deb1` cleanup.py reaper + launchd (premise reversed)
- `acafd60` fix(transcript): entrypoint headless marker (REVERSED by 24830a3)
- `~/.claude`: prompt-lint.py `-p`→stream-json — unpushed
- worktree-phase1-review: `eccc1df` DESIGN mm+/mm-, `ea9e24c` CLAUDE.md review flow, this handover — unmerged

pytest 91/91. events 479 (backup `marrow.db.bak-20260518-220058`, was 518).

## step 3 — /ultrareview (Lumi runs; billed; Claude cannot launch)

- `git checkout main` FIRST — Phase-1 code is on main; `worktree-phase1-review` is doc-only, ultrareview there reviews nothing.
- `/ultrareview` no-arg = bundles current local branch, no GitHub remote needed. `/ultrareview <PR#>` = a GitHub PR.
- Multi-agent cloud, user-triggered + billed. Run after major phases, before add-ons.

## step 4 — close-out fix list (adjudicated this review)

Blocker root (entrypoint):
1. Real headless signal — entrypoint can't split headless `claude -p` vs real sdk-cli. Candidates: process/tty, cwd, promptId shape — re-census + ADR-0003. Then rewrite cleanup.py + test_cleanup.py against it. NO sdk-cli→delete before that.
2. Recover wrongly-purged events — prior 518→479 purge used the flawed judge, ~39 rows may be REAL. Restore from `marrow.db.bak-20260518-220058`. Backfill the ~51-min `clean()=[]` window (acafd60 22:02 → bleed-stop 22:53).

Major:
3. diary idempotency-by-date blocks late-session correction + no multi-process app-lock (04:00/16:00/SessionEnd overlap → diary PK collision crashes the job).
4. DB backup not implemented — DESIGN L186 = Phase-1 agreed; only empty backup_dir ships. Land before ny-memm retires.
5. audit_log doesn't mirror archive_events (biggest writer invisible to Monitor Zone).
6. events_vec no embedder-id/dim provenance — model swap can't coexist re-embed (goal 1/7, base-schema, costly post-rewrite).
7. _routine_target off-by-one on late/manual run 00:00–03:59 (catchup masks it).

Minor:
8. is_headless dead second `return False`; timeout not process-group kill; lessons 2 stale rows (no auto read-path, safe); SessionStart catchup DESIGN L139 doc drift vs L141/L170.

Done: mm+/mm- recorded (DESIGN `eccc1df`).
Close rule: subagent findings are material not verdict; fix → pytest+dashboard green → PROGRESS delta.

## Worktree merge (review window does before close)

- `worktree-phase1-review` rebased onto `39fbbff`: `eccc1df` + `ea9e24c` + this handover. Linear, doc-only, no code.
- Land: fast-forward main to branch HEAD (or cherry-pick the doc commits). No conflict with neighbour bleed-stop expected.
- After merge main carries them so next window's /ultrareview + handover see them.

## Ops note — next session restart

- 2.1.142 takes effect on next restart (this window ran 2.1.143). Watch parse-failure past ~100k context; still bleeding → decoder layer confirmed version-independent.

## Done & verified (both windows)

- Alert #11 fake-warn: `transcript.clean` FileNotFound → []; stale alert resolved; 15 lesson-type alerts deleted; dashboard regenerated clean.
- Stitch cross-04:00 ordering: `_local_md()` adds date to span tag; verified on real 5-17 data.
- 5-17 diary overwritten with reviewed dry-run narrative (4 kept sessions). Dry-run script at `/tmp/mw_dryrun_diary.py` (no DB write; arg=date).
- `CLAUDE.md` rule added: push full DB-only body to Lumi after a run.

## Open — Lumi prompt-tuning (diary.py prompts are hers)

1. `DIARY_PROMPT` "no study/coding detail" was too weak (sonnet dropped all work). `f08e08e` added strict-discard + banned-phrase — confirm with Lumi whether resolved or needs the "one line: what done + outcome" rule.
2. `DIGEST_SHORT` mis-SKIP — **CLOSED**: `8a9d1efd` (5-turn /schedule, no outcome) is a *correct* SKIP, not a miss.
3. `DIGEST_LONG` haiku still wraps a meta shell ("per diary compress rules…"). Prompt wording fix, core craft unaffected.

Test loop: clear `diary` row for a date in `~/.config/marrow/marrow.db`, `diary.run(day=…)`, show diary text + KEEP/SKIP/DROP. (llm.py records no usage — FUTURE.)

## Shipped (done, keep)

- `~/.claude/hooks/prompt-lint.py`: `-p`→stream-json + isolation, system in user content, off 6/15 pool, dependency-free. Live-verified 4.5s. (local commit, unpushed per rule)
- ADR-0003 scheduling: 3 jobs + bootstrap-from-repo wording.
- `cleanup.py` + `deploy/mw-jsonl-cleanup.plist` (com.marrow.jsonl-cleanup) — harmless no-op under is_headless hard-False; left in place.

## Don't redo / decided

- sdk-cli `entrypoint` is NOT a headless marker — covers real clawbot/Task-agent/worktree human sessions. Pollution-drop REVERSED (`24830a3`). Wait for step4 real signal.
- `CLAUDE_CONFIG_DIR` redirect rejected: fresh config dir loses OAuth/keychain auth (three-way verified). Don't reopen.
- Cleanup must be a standalone job, never inside diary routine/catchup.
- diary.py prompts (DIGEST_SHORT/LONG, STITCH, DIARY_PROMPT) Lumi-owned; restore from `f08e08e`/`bcde095` if reverted; don't rewrite.
- prompt-lint stream-json migration verified correct; don't revert to `-p`.
- /clear does NOT change session_id (same jsonl). lessons removal intentional (Lumi).
- Review flow lives in CLAUDE.md (0–5); blind step forbids repo access; never trust a self-report — double-check.

## Suggested skills

- `/loop` — if Lumi re-enters diary prompt-tuning.
