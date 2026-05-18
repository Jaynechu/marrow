# Marrow handover

> Events headless-pollution root-fixed structurally + DB cleaned; data layer firewalled. Two windows merged here. What's left: cosmetic disk backlog, `-p`→stream migration, Lumi prompt-tuning. Read DESIGN/PROGRESS next.

## State (committed, not pushed — 5 commits on main)

- `acafd60` fix(transcript): drop headless `claude -p` via `entrypoint` marker (neighbour window)
- `f08e08e` fix(diary): strict-discard digest + banned-phrase guard in prompts (Lumi prompt-tuning)
- `6d96dc8` docs(claude): push DB-only output full body to Lumi after a run
- `2fb88bd` fix(diary): stitch span tag carries local date for cross-04:00 days
- `b6febbd` fix(hooks): session_end no-op on unflushed/missing transcript
- uncommitted: `FUTURE.md` (dashboard_customization addon) — committed with this handover

pytest 88/88. events 518→464 (fake Compress-NEW = 0). backup `~/.config/marrow/marrow.db.bak-20260518-220058`.

## Done & verified (both windows)

- Events headless pollution root-fixed structurally: `transcript.is_headless()` reads CC `entrypoint` (interactive="cli", spawned `claude -p`="sdk-cli", absent=legacy→keep); `clean()` → [] for headless; `hooks.session_end()` no-ops before DB/dashboard. DB cleaned 518→464. Verified: 3-state correct, fake-row=0, 88/88.
- Alert #11 fake-warn: `transcript.clean` FileNotFound → []; stale alert resolved; 15 lesson-type alerts deleted; dashboard regenerated clean.
- Stitch cross-04:00 ordering: `_local_md()` adds date to span tag; verified on real 5-17 data.
- 5-17 diary overwritten with reviewed dry-run narrative (4 kept sessions). Dry-run script kept at `/tmp/mw_dryrun_diary.py` (no DB write; arg=date).
- `CLAUDE.md` rule added: push full DB-only body to Lumi after a run.

## Open — Lumi prompt-tuning (diary.py prompts are hers)

1. `DIARY_PROMPT` "no study/coding detail" was too weak (sonnet dropped all work). `f08e08e` added strict-discard + banned-phrase — confirm with Lumi whether this is now resolved or needs the "one line: what done + outcome" rule.
2. `DIGEST_SHORT` mis-SKIP concern — **CLOSED**: this window empirically confirmed `8a9d1efd` (5-turn /schedule discussion, no outcome) is a *correct* SKIP, not a miss. Not a bug.
3. `DIGEST_LONG` haiku still wraps a meta shell ("per diary compress rules…"). Prompt wording fix, core craft unaffected.

Test loop: clear `diary` row for a date in `~/.config/marrow/marrow.db`, `diary.run(day=…)`, show diary text + KEEP/SKIP/DROP. (llm.py records no usage — FUTURE.)

## Open — next window (priority order)

1. **Disk cleanup (cosmetic, main task).** 142 sdk-cli `.jsonl` physically in `~/.claude/projects/` (/643) cluttering CC project list (Lumi does not want extra projects). Data already firewalled — disk/UX only. Build: standalone weekly launchd job, pure code, NOT inside diary routine (decouple per "separate routines" lesson); delete jsonl whose head carries `"entrypoint":"sdk-cli"` + one-time sweep of the 142. Template: `deploy/mw-diary-catchup.plist`. Use `tdd`.
2. **`-p` → stream-json migration.** Audit (Lumi recorded): `~/.claude/hooks/prompt-lint.py:126` (high-freq, burns 6/15 pool, NOT in marrow repo — keep dependency-free, add `--setting-sources ""` + no-`-p` stream-json) is the one worth doing; `~/Toolkit/scripts/ny_lib.py:61` (confirm caller/freq); `weclaude/bridge.py:165` (already FUTURE WeClaude_6_15_migration); `marrow/llm.py:138` (fallback, low priority).
3. **Push** the 5 commits (private ledger github.com/Jaynechu/marrow).
4. **CC version drift.** PATH `claude` is 2.1.143; docs pin 2.1.142 (parse-bug, `docs/notes/2026-05-18_cc-2143-toolcall-parse-bug.md`). Decide: re-pin or update note.

## Don't redo / decided

- entrypoint-marker is THE root fix. Earlier "pin cwd + path-exclude" plan is **superseded** (entrypoint is payload- and location-independent) — do not re-add cwd pinning for pollution.
- `CLAUDE_CONFIG_DIR` redirect rejected: fresh config dir loses OAuth/keychain auth (verified empirically + agent + neighbour, three-way). Don't reopen.
- Cleanup must be a standalone job, never inside diary routine/catchup.
- diary.py prompts (DIGEST_SHORT/LONG, STITCH, DIARY_PROMPT) Lumi-owned; restore from `f08e08e`/`bcde095` if reverted; don't rewrite.
- /clear does NOT change session_id (same jsonl). lessons removal intentional (Lumi).

## Suggested skills

- `tdd` — cleanup module (deterministic: delete jsonl iff entrypoint=sdk-cli).
- `/loop` — if Lumi re-enters diary prompt-tuning.
