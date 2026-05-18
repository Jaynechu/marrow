# ADR-0004: Headless-spawn detection by assistant model-set

Status: accepted 2026-05-19

**Context**
- SessionEnd archives cleaned transcripts to `events`. Spawned `claude` LLM calls (prompt-lint haiku, diary haiku/sonnet via `marrow/llm.py`) fire SessionEnd but aren't archivable sessions.
- `entrypoint` ("cli" / "sdk-cli") rejected: clawbot, worktree, Task sub-agent, vscode, desktop sessions also carry "sdk-cli". Reversed fixes: `24830a3`. Census 549 jsonl confirms (see `docs/notes/2026-05-19_entrypoint-headless-census.md`).

**Decision**
- `is_headless(jsonl)` is True iff the set of assistant `.message.model` (records `type=="assistant"`, excluding `"<synthetic>"`) is non-empty AND a subset of the worker-model set.
- Worker-model set lives in `config.toml [transcript].worker_models` — single source of truth. Current: `claude-haiku-4-5*`, `claude-sonnet-4-6` (prefix match).
- Empty-model backstop: no assistant model present → match first user / `queue-operation` content head against known spawn prompt heads (prompt-lint, diary digest/stitch/write/lessons). Conservative: no match → not headless.
- Real human / clawbot / worktree / Task use chat model (opus-4-7, legacy opus-4-6) — never in worker set.

**Consequences**
- Census 549 jsonl: opus 217 + 23 all real; haiku 194 + sonnet 138 all headless; zero false-negatives.
- Residual: manual human `claude -p` pinned to worker model archived as headless. No data loss (single inject/result).
- Hazard: worker set MUST stay synced with pinned models in `marrow/llm.py`, `marrow/diary.py`, `~/.claude/hooks/prompt-lint.py`. If diary runs on opus, signal breaks silently.
- Mitigation: config single-source + guard test asserting every pipeline-pinned model ∈ `worker_models`.

**Supersedes**
- Reversed `entrypoint`-based `is_headless` (`acafd60`, hard-False bleed-stop `24830a3`). `entrypoint` is not a headless marker — do not reopen.
