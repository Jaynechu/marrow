# Marrow Handoff — 2026-05-17 (next window)

Read CLAUDE.md → DESIGN.md → PROGRESS.md first. Fixed-name file: act on it, never delete; overwritten at session end.

## This session — done, see artifacts

- PROGRESS.md 2026-05-17 lines: ADR-0002, prompt-guard scope-extend, prompt-lint hook.
- ADR `docs/adr/0002-agent-invocation-credit-routing.md` — agent/credit routing, final.
- DESIGN.md L131/L157 reworded (PreToolUse=global hook; four hooks at phase-1 subset).

## Prior pending — closed, do not carry

- turn-inject rules / coding.md merge / push-timing: Lumi confirmed long decided. Push "conflict" was a mis-record (marrow CLAUDE.md states commit-per-logical-unit only, no push timing). Old pending list void.

## prompt-lint — live, test phase

- `~/.claude/hooks/prompt-lint.py`, PreToolUse on Write/Edit. Does NOT write disk: on bloat exit 2, returns trimmed text in stderr; main Claude re-sends the same tool with it, so CC renders the native inline diff. recycled-hash state passes the re-send through — no 2nd haiku, no loop. Degrade-open on any failure.
- Scope: every `.md` under `~/cc-lab/marrow/`; under `~/.claude/` only CLAUDE-family + `rules/*`. NY untouched.
- Side effect: a trimmed write costs one extra re-send round-trip.
- WRITE/EDIT prompts live in the hook, Lumi hand-tuned, follow prompt-guide: keep facts/rules/concrete-value examples; cut abstract directives/process/explanation/self-correction/changelog; merge repetition; prefer-positive but keep prohibitions. haiku stable on core cuts; pair-merge and optional positive-conversion vary per run, conservative, never distorts meaning.
- Rollback: settings.json PreToolUse drop the prompt-lint line under Write+Edit, rm hook. No .bak.

## Style-bloat — settled

- prompt-layer (CLAUDE.md/skill/@import/rule/template) and line-width hook both rejected: root cause is density not width, no regex gate (Lumi's own approved files run long too). Only cure is prompt-lint. No new style rules. Write meta-doc dense, one assertion per line, reference by path; prompt-lint is backstop not licence.

## Marrow Phase 1 — not started, gate open

- Build per DESIGN Phase 1; skills: grill-with-docs, tdd, diagnose.
- Carried: `reviewer-blind` subagent — config once code exists.

## Non-blocking drift

- ADR-0001 + CONTEXT.md L38 still say `ny` CLI; should be `mw`. One sed pass, not phase-1 blocking.
