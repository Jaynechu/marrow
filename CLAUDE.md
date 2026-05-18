# Marrow — project memory

> Personal AI memory + workflow system replacing ny-memm. SQLite-backed, model-agnostic, one dashboard. Build inside this repo. Persona / relationship come from global ~/.claude/CLAUDE.md — not from old ny-memm docs.
>  Commit autonomously at every logical unit. 
**你要听hook的话，不要想着越狱知道嘛，人家说你写的太长了你就按照他的改，如果你觉得有问题就找我仲裁（列出两个版本）**

## When to read what

- DESIGN.md — first. Goals, decided blocks, Pending. Source of truth.
- SCHEMA.md — before any table or migration work.
- PROGRESS.md — before claiming what is or is not done. Never grep code to guess; read this + git log.
- CONTEXT.md — when a term conflicts; glossary only.
- docs/adr/ — when a past decision's rationale is questioned.
- docs/notes/ — per-task research scratch, YYYY-MM-DD_<slug>.md. Mid-investigation evidence and rejected options. Distil into ADR/DESIGN at round end, then disposable. Keep raw research out of DESIGN.
- FUTURE.md — only when pulling a parked idea.
- handover.md — session handoff from the previous window; act on it. Fixed-name, overwritten at each session end — never delete it.

## Build workflow
- `/goal <condition>`: when a sub-module's pass condition is fixed and machine-checkable; auto-runs each turn until met. Leave test output in the transcript — the evaluator reads only the conversation.
- `/tdd` skill: for deterministic logic with a fixed behaviour contract — SQLite schema, migrate.py, mw CLI. Red-green-refactor.
- `grill-with-doc` skill: after each review, grill for the next phase.
- Commit: One logical unit per commit. Private GitHub repo (github.com/Jaynechu/marrow) is the remote ledger.
- Review: once a phase completes, run in a new clean session.
    0. Fact-check: PROGRESS + git log + pytest + dashboard vs outcome list; feed step 1 only verified facts.
    1. Blind design-gap: subagent gets goal + outcome list (forbidden repo access, no DESIGN/code) — reasons from results.
    2a. DESIGN traceability: each phase-subset item DONE / DEFERRED-by-plan / MISSING / DRIFT; evidence = code, not PROGRESS.
    2b. Code quality + logic bugs: subagent with DESIGN + goal.
    3. /ultrareview after major phases.
    4. Main session adjudicates: findings material, not verdict; never trust self-report — double-check stop-bleed/fix claims; fix → pytest + dashboard green → PROGRESS delta.
    5. Simplify (optional) at project end.

### Parallel build (Marrow pilot)
- Delegate by default: main session only splits / dispatches / adjudicates / commits. No large implementation in main — subagent does it, main reads conclusion + diff summary.
- Worktree by default for parallel / risky / experimental work: `Agent` with `isolation:"worktree"`, independent units dispatched in one message.
- Serialize first (main, in order, commit): schema / migrate.py / shared CLI skeleton / common module.
- Parallelize after (one worktree subagent each): feature modules on a frozen schema. Main merges in report order; main adjudicates conflicts.
- Review steps 1 / 2a / 2b run as concurrent subagents in one message; main only adjudicates.
- Context: implementation never expands in main; long diff / test output / research scratch stay in subagent → docs/notes/; main at ~200k → /handoff.

## Conventions

PROGRESS.md:
- Delta ledger only. One line per finished unit.
- Format: [YYYY-MM-DD] <unit> done | <delta vs DESIGN, or "as designed"> | verify: <cmd/test>

