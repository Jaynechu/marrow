# 2026-05-19 — Headless-spawn signal census (ADR-0003 step4)

Goal: deterministic predicate for "this jsonl is a spawned headless `claude` worker call, NOT session-worthy".

## 1. Why `entrypoint` fails

`entrypoint=="sdk-cli"` covers both headless spawns and real work (e.g. headless `d9d9a9dc`, real clawbot `9d438774`). Payload/location-independent. Reversal `24830a3` was correct.

## 2. Structural shape of Marrow/prompt-lint spawn

```
queue-operation (enqueue; full injected prompt)
user (parentUuid:null, isMeta:null, 1 only)
attachment ...
[0..N assistant]   worker model = haiku/sonnet
```

REJECTED predicates:
- "0 assistant records": false-negative on `cf070320` (flushed 2 asst before exit)
- "first record == queue-operation & 1 user & 0 assistant": catches 32 spawns, false-negative on asst=2..28 spawns
- "has system-reminder/UserPromptSubmit block": 157/332 files trip it; unusable

## 3. Deterministic signal: assistant model field

Marrow + prompt-lint worker models (haiku-4-5, sonnet-4-6) never appear in real sessions (real: opus-4-7 or opus-4-6).

```
is_headless(jsonl) == True iff all .message.model in type=="assistant" records
(excluding "<synthetic>") is non-empty AND every element in
{claude-haiku-4-5*, claude-sonnet-4-6}
```

Empty-model backstop: user/queue-operation content head matching Marrow/prompt-lint:
- `Compress NEW per the rules` / `You compress ONE …` / `You compress one day …`
- `You are a ruthless markdown compressor` / `You write <date>'s diary entry`
- `你是褚屿忱，你要以第一人称写一篇日记` (CN diary-write)
- `Reply with exactly the token MARROW_OK` / `From the day's material below, extract only lessons`

### Global model fingerprint (549 jsonl, subagents excluded)

- `claude-opus-4-7` — 217 files — REAL
- `claude-haiku-4-5-20251001` — 194 files — HEADLESS
- `claude-sonnet-4-6` — 138 files — HEADLESS
- no assistant record — 41 files — spawn-exited-early OR interrupted real
- `claude-opus-4-6` — 21 files — REAL
- `claude-opus-4-6` + `claude-opus-4-7` mix — 2 files — REAL

## 4. Evidence (first-record / model / users / asst)

HEADLESS: `d9d9a9dc` (queue-op / haiku-4-5 / 1 / 0), `5ceff8bc` (queue-op / haiku-4-5 / 1 / 0), `64e97285` (queue-op / none / 1 / 0), `cf070320` (queue-op / haiku-4-5 / 1 / 2), `8a09ca61` (queue-op / haiku-4-5 / 1 / 9), `sonnet_faa0ac4a` (queue-op / none / 1 / 0), `8735082e` (queue-op / sonnet-4-6 / 1 / n)

REAL: `780d575d` (last-prompt / opus-4-7 / many / 548), `b1f6c86b` (file-history / opus-4-7 / many / 402), `9d438774` (queue-op / opus-4-7 / 3 / 28), `68c7bb0d` (last-prompt / none / 2 / 0), `b1efa1b2` (queue-op / none / 1 / 2), `ffd9d383` (queue-op / sonnet-4-6 / 1 / 1)

Model ids: `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, `claude-opus-4-7`.

## 5. False-positive / false-negative risk

Zero opus-4-7 files carry a Marrow spawn prompt (false-negative: none found).

Irreducible residual `ffd9d383` (manual `claude -p` test): structurally identical to spawn; archiving as headless is correct.

Empty-model edge (41 no-assistant): spawn exiting before assistant flush looks like interrupted real. Content backstop resolves spawn cases; interrupted real has human prompt, not Marrow head, so not flagged.

## 6. Recommendation

Adopt assistant-model predicate as primary `is_headless` signal, with Marrow/prompt-lint prompt-head as empty-model backstop.

Deterministic, payload-stable, zero false-negatives on 549 files. Worker-model list: prompt-lint = haiku; diary map/stitch/lessons = haiku; diary write = sonnet; weclaude = sonnet. Update when spawn model changes.

A single field does NOT work (entrypoint, first-record-type, assistant count each fail individually). The model-set predicate plus prompt-head backstop is the smallest robust composite the data supports.
