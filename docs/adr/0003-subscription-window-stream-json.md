Status: accepted 2026-05-17

**Constraint**
No Anthropic API key. Pipeline LLM via local `claude` CLI subprocess. From 2026-06-15, `-p` (print) moves to credit-pool billing; OAuth 5-hour subscription window carries pipeline at ~0 cost.

**Decision**

Default provider: `_run_claude_stream` (llm.py)
```
claude --output-format stream-json --input-format stream-json --verbose --model <m> --setting-sources "" --strict-mcp-config
```

Stdin: one JSON line `{"type":"user","message":{"role":"user","content":"<prompt>"}}`, close, read stdout until `type":"result"`.

Flag meanings:
- `--output-format stream-json --input-format stream-json` — interactive session, bills to OAuth 5h window (not credit pool).
- `--verbose` — required for `result` event.
- `--setting-sources "" --strict-mcp-config` — isolation, no persona/user MCP/output-style inheritance.
- Watch stdout for `rate_limit_event` (rateLimitType, isUsingOverage).

Evidence: Haiku returned PONG in 2.7s, `rate_limit_event` with `rateLimitType:"five_hour"` confirmed.

**Fallback**

`_run_claude_p` (config `[llm.claude_cli] mode = "p"`) uses `-p --output-format json`, credit-pool billing. One-line switch, callers unchanged. Ollama available (local, no cost). Use `-p` only if stream breaks.

**Scheduling**

Catchup runs locally via macOS launchd (`~/Library/LaunchAgents/mw-diary-catchup.plist`, `StartCalendarInterval` 16:00 local, DST auto-followed). `marrow.diary --catchup` scans last 7 days (cap 3, overflow alert). Do NOT use Anthropic `/schedule` skill — cloud sandbox has no local SQLite, .venv, or OAuth `claude`.

**Consequences**

- Steady state: diary ≈ 3 stream calls/day on subscription window, ~0 pool burn.
- Re-verify `rate_limit_event` after `claude` CLI upgrade; `-p` fallback exists if behaviour regresses.
