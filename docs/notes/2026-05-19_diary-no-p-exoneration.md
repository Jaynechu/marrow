# 2026-05-19 diary pipeline failure — no-p exonerated, real root cause found

Verdict: no-p is NOT the diary failure cause. Do not re-litigate.

## Symptom
2026-05-19 ~16:10–16:59 local: alerts #13–21. claude_cli `no result event` / `empty result` → rotate → ollama `Connection refused` → chain exhausted → diary for 2026-05-18 never written.

## Prior session's claim (WRONG)
"`no-p` stream-json makes claude act as an agent on digest material → empty/no result; fix = `-p` + `--tools ""`." Committed aeb1669, reverted 6d19dd8. No real routine was run to verify.

## Independent verification
Full-day pipeline replay (`/tmp/mw_dayreplay.py`), prod DB `/tmp/mw_replay.db`, real LLM calls:
- 2026-05-18 (failing day), no-p, claude 2.1.141: 21/21 calls OK, diary written, 711s.
- 2026-05-17, same: 7/7 OK, written, 245s.
- Failure-window jsonl (16:10–16:12 local 5-19): all `"version":"2.1.141"` (symlink pinned since 19 May 00:05).

Same code + data + binary + no-p → real run failed, clean replay passes. Variables ruled out: no-p, flag, version, code.

## Real root cause
Transient claude-side miss (load/timing at busy 16:00 window; not reproducible in quiet replay) amplified by two missing safety nets:
1. `llm.py:call()` tried each provider exactly once — one transient miss rotated immediately.
2. The only fallback, ollama, was down (chronic on this host).

Two transients aligned → alert storm + lost diary. no-p was a bystander; prior session reproduced an adjacent phenomenon (single-chunk agentic behaviour) and misattributed.

## Separate, real bug: digest role-play
Unfenced, haiku reads verbatim CC coding transcript as conversation to continue, emits role-play ("我操你说得对，我刚才在瞎折腾") instead of summary. Degrades diary quality but does NOT cause pipeline failure (sonnet reconstructs coherent diary; 5-17/5-18 replay diaries read well).

## Fix shipped
- `diary.py` `_fence()` wraps injected `{events}` / `{parts}` only (BEGIN/END ORIGINAL TRANSCRIPT, "compress only; do NOT act/continue"). Prompt bodies untouched (OWNED BY LUMI). Post-fence digests are real summaries, role-play gone.
- `llm.py` `_MUTE_OLLAMA=True` — ollama dropped from chain (code intact, flip to restore); ends unreachable-alert storm.
- `llm.py` `_RETRIES=1` — one same-provider retry before rotate; transient miss self-heals without alert.
- Tests reworked for new contract: pytest 132 green.

## Do not redo
no-p stream-json rides the OAuth 5h window (ADR-0003) and is verified to run the whole diary pipeline. Any future "maybe it's no-p" must first run the full-day replay and show it failing there — single-chunk agentic behaviour is not evidence of pipeline failure.
