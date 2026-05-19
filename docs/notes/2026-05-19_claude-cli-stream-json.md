# 2026-05-19 claude_cli stream-json returns no usable result

## Symptom
Diary pipeline dead (2026-05-18: 736 events, ~231K chars, largest session 780d = 67K chars / 172 turns). Alerts:
- 06:10:11Z `stitch: provider claude_cli failed (claude_cli stream-json: no result event); rotating`
- 06:12:34Z `day-digest: provider claude_cli failed (claude_cli: empty result); rotating`
- Both fall to ollama (down) → chain exhausted → diary fails.

## Reproduction
3 chunks of session 780d through DIGEST_LONG (timeout_s=120, binary ~/.local/share/claude/versions/2.1.141):
- chunk0: `result=""` (alert 16 "empty result")
- chunk1: 5 agentic_turns, `result="...你授权我操作 /Users/... 我查 git diff..."`
- chunk2: 1 agentic_turn, `result="...我在 /private/tmp 不是 git 仓库..."`

Plain PONG succeeds. Failure is content-triggered, not protocol-broken.

## Root cause
`_run_claude_stream` (llm.py:104-153) invokes claude WITHOUT `-p` and WITHOUT disabling tools. Per claude 2.1.141 `--help`: `--input-format` and `--output-format` only work with `--print`.

Piped stdout makes claude auto-run as full interactive agent with entire toolset enabled. When digest/stitch material contains file paths and imperatives ("fix the test", "run pytest", "git diff"), the model acts on the content instead of compressing:
- Emits tool-only assistant turns then terminal `result` with `result:""` → `_parse_claude` line 208-209 → "claude_cli: empty result"
- Enters multi-turn agentic loop; outruns 120s `killer` SIGKILL before `type==result` → `_parse_claude` line 197 → "claude_cli stream-json: no result event"

One cause, two surface messages, both content/length dependent → intermittent.

## Divergence from ADR-0003
ADR-0003 verified with trivial "PONG" probe (can't trigger tools); generalized "works for PONG" to "works for pipeline". Real digest/stitch prompts carry actionable content; without `-p` + tools-off, headless agent goes agentic. ADR's flag set is missing `-p` and tool isolation. Help documents that `--input-format`/`--output-format` require `-p`.

## Fix (verified)
Add `-p` and disable tools in `_run_claude_stream` cmd (llm.py:106-108):
```
cmd = [_claude_bin(), "-p",
       "--output-format", "stream-json",
       "--input-format", "stream-json", "--verbose",
       "--model", model, "--tools", "", *_ISOLATION]
```

3 chunks re-run: chunk0 dt=12s, chunk1 dt=16s, chunk2 dt=12s. All non-empty, zero tool turns, well under 120s. `-p` + stdin stream-json still within OAuth five-hour window (`rate_limit_event rateLimitType:"five_hour", isUsingOverage:false` emitted; `-p` billing moves to pool from 2026-06-15, separate concern).

`--tools ""` forbids agentic loop; digest is always single text turn. `-p` makes stream/io contract the documented one (single-shot print-and-exit).

## Note for main session
- Minimal change = llm.py:106-108 cmd list only. `_parse_claude` and timeout/process-group machinery unchanged.
- `_run_claude_p` (mode="p") already uses `-p` but `--output-format json` (no `--input-format`, no `--tools ""`); would also benefit from `--tools ""` for same agentic-content reason, not failing path here.
- Revisit ADR-0003 before 2026-06-15 billing change.
