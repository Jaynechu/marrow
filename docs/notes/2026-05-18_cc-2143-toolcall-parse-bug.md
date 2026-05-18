# Followup: tool-call parse failure (two distinct bugs)

Status: OPEN — re-pinned to 2.1.142 (2026-05-18 22:54). All upstream issues OPEN, no fixed version exists. Empirically NOT resolved by 2.1.143; Lumi sees it persist whenever a session passes ~100k context.

## Symptom
`The model's tool call could not be parsed (retry also failed)`. Surfaces after Write/Edit when content is escape-dense (quotes, backslashes, braces) or contains literal `<`. Frequency scales with total context — heavy past ~100k tokens. Retry resends an identical payload, so it fails again.

## Root causes
- **Harness layer — CC 2.1.143 regression.** #60033, #59787: 2.1.143's XML→JSON tool-input handling mangles escape-dense / literal-`<` Write payloads. Re-pinning 2.1.142 removes THIS source.
- **Model decoder layer — Opus 4.7, pre-dates 2.1.143.** #49747 (CC `2.1.112`, "regression from Opus 4.6"), #56655 (from 2026-04-27, worse under parallel-batch / large context): Opus 4.7 intermittently emits legacy XML tool syntax inside JSON on longer payloads. Version downgrade does NOT remove this — root cause is the model, amplified by large context.

## Mitigation
- Re-pin 2.1.142 (done) — kills the harness-layer source only.
- Keep total context < ~100k: /clear or handoff earlier; the decoder bug's probability rises sharply past that.
- Offload large reads/writes to a subagent (#56655 official workaround) — isolated small context, failure does not pollute the main window.
- Split Edits into small old_string/new_string; avoid one escape-dense 2500+ token payload (#60033 trigger size).
- Extreme fallback only: Opus 4.6 has no #49747 decoder bug (it is a 4.7 regression); cost = weaker model. Not default.

## Followup
- Watch #60033 / #59787 / #56655 / #49747 for a fixed CC version.
- 2.1.141 also installed locally if 2.1.142 still bleeds; next downgrade step.
- When a fix ships: `claude install <ver>`, re-enable autoUpdates if desired. autoUpdates already false.
