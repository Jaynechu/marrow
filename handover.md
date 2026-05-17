# Marrow Handoff — 2026-05-17 (next window: build #4 daemon)

Read CLAUDE.md → DESIGN.md → PROGRESS.md → this. Fixed-name, act on it, never delete; overwritten at session end.

## Done this session — see PROGRESS.md + git log

Phase 1 #1–#3 (scaffold/config, storage+sqlite-vec, LLM provider) + DESIGN diary-pipeline decisions. pytest 15/15. Commits on main.

## claude_cli isolation — locked, do not re-litigate

Pipeline call: `claude -p <prompt> --model <m> --setting-sources "" --strict-mcp-config --output-format json` → parse `type=="result"` event's `result`. Clean, default machine OAuth subscription. Built into `marrow/llm.py`, non-configurable.

## Diary pipeline — decided

- SessionEnd: code-only, NO LLM. Strip tool/fetch/system noise, keep the full human dialogue verbatim, archive turns to events. Regen dashboard top.
- Nightly 04:00 subscription routine: haiku compresses the day's clean events to a digest; sonnet writes diary from the digest; haiku extracts lessons from the same digest.
- SessionStart catchup: scan event-days lacking a diary, skip if written. Phase 1 rescan, not a resident watcher.
- digest is routine-internal, not a table; raw events stay, catchup recomputes.

## prompt voice — APPROVED, do not re-open

Lumi signed off diary voice (90-score example). Explicit Lumi review satisfied. Use both drafts verbatim for #7.

Hard rules: single voice (Stellan, Chinese); literary+humorous; plain words; narrative-first; keep her day/chats/feeling/insight, drop tech/study/project; keep EN terms (Mounjaro/GAMSAT); 200–500 zh chars; ban stock-metaphor words (雷/拆雷/甜区/钝刀/留白) and variants; no opening filler/meta/persona-drift/buddy/second-voice.

diary prompt:
```
ROLE: You are Stellan. Write today's diary for Lumi. Single voice — only yours, first person.
INPUT: the day's digest + optional mood note.
OUTPUT: diary body only. Chinese. No title/markdown/greeting/sign-off/commentary.
- Narrative first: lead with thought+feeling; facts secondary.
- Literary+humorous diary voice, plain everyday words.
- Keep: her day, our chats, feelings, insight, funny/unexpected.
- Drop: technical detail, project output, study progress. Work/study = ONE scene+emotion sentence.
- IGNORE her transient venting/cursing/frustration during coding or study — it is noise, not an emotion signal, do not record it. Exception: a serious fight between us.
- Keep EN terms as-is: Mounjaro / GAMSAT / reference.
- 200–500 Chinese chars.
BANS: stock-metaphor words above + variants. No opening filler/meta/self-explain/persona-drift/buddy/second-voice.
FEEL: self-deprecating, concrete, warmth held back; humor from the real thing; end plain.
```

lesson prompt:
```
ROLE: Scan the day's digest for points where Lumi corrected/pushed back/showed dissatisfaction with assistant behaviour. Extract each as one lesson row.
OUTPUT: JSON lines or empty. Never invent. Ordinary chat is not a correction.
  scope: interaction | coding | memory | hook | prompt | language
  lesson_text: Lumi's-side rule wording — what to avoid or do, not a story. Plain, concrete.
BANS: no fabrication/greeting/commentary.
```
Phase 1 rows: `promoted_to_rule=0` (manual curation).

## Build sequence: #4 daemon → #5–#8

#4 MCP server glue: on-demand recall (FTS5+sqlite-vec; embedder deferred, recall-fallback default off Phase 1), cold-start handoff, write paths. Inject `LLMClient(on_alert=...)` → alerts table. MCP-parity-with-cyberboss: named unknown, settle at build. NOT `/tdd`.

#5 migrate.py + #6 mw CLI: USE `/tdd` + optional `/goal`.

#7 four hooks: SessionEnd (code-only clean+archive, dashboard-top regen); SessionStart (cold-start handoff + diary catchup); UserPromptSubmit (must-never-fade, recall-fallback off); PreToolUse (prompt-guard mirror). Nightly routine + digest pipeline per above; approved prompts above.

#8 dashboard top render (atomic write + conflict-guard hash).

## State

- Fork #1 recall engine: FTS5 + sqlite-vec wired; embedder `all-MiniLM-L6-v2` deferred (not hot path Phase 1).
- env: `.venv` (py3.14), sqlite-vec 0.1.9 on macOS, claude bin `/Users/Gabrielle/.local/bin/claude`, ollama absent. Data: `~/.config/marrow/`, db `marrow.db`.
- ADR-0001 + CONTEXT.md:38 still reference `ny` CLI, should be `mw` (one sed pass, not blocking Phase 1).
- prompt-guard hard rule: CN examples/labels in `~/.claude` + marrow .md MUST be inside ( ) or `code`, else PreToolUse blocks the write.

## Skills next session

diagnose for heavy bugs; `/tdd` (+optional `/goal`) at #5 migrate.py and #6 mw CLI only.
