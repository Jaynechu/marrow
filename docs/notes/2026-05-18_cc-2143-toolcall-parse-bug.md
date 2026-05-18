# Followup: CC 2.1.143 tool-call parse failure

Status: OPEN — pinned to 2.1.142, waiting on upstream fix.

## Symptom
`The model's tool call could not be parsed (retry also failed)` — 3–4x per session. Surfaces after Write/Edit when content is escape-dense (quotes, backslashes, braces) or contains literal `<`.

## Root cause
- Trigger: Claude Code `2.1.143` (installed 2026-05-16 14:45). Not the model, context size, or Marrow code.
- CC harness mangles model Write/Edit output into malformed tool-input JSON when content is escape-dense or contains literal `<`.
- Upstream: #60033 (2026-05-17), #59787 (2026-05-16).
- Same parser bugs at low frequency before 2.1.143: #56655 (2026-04-27), #49747 (2026-04-17) — both OPEN.

## Action taken
- Set `~/.claude/settings.json`: `autoUpdates: false`.
- Downgrade to `2.1.142` (available at `~/.local/share/claude/versions/`).

## Followup
- Watch #60033 / #59787 for fix and CC version shipping it.
- When fixed: `claude install <fixed-version>`, then re-enable autoUpdates if desired.
