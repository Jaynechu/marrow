# 1M context probe + token census
2026-05-19 — empirical verification for single-call diary design
Probe scripts: /tmp/mw_probe_taska_1m_context.py, /tmp/mw_probe_taska_boundary.py, /tmp/mw_probe_taska_v3.py, /tmp/mw_probe_taskb_token_census.py
Raw JSON dumps: /tmp/mw_taska_v3_results.json, /tmp/mw_taskb_results.json

## Task A — 1M context window on the claude_cli stream-json sonnet path

### Verdict: YES, context window substantially exceeds 200K tokens

`modelUsage.contextWindow: 200000` is metadata, not enforced limit.
On OAuth stream-json path (`--output-format stream-json --input-format stream-json --verbose --model claude-sonnet-4-6 --setting-sources "" --strict-mcp-config`), successfully processed 269K, 372K, 456K token prompts without error.

### Probes

**v1: 950K prose + needles** — Content policy filter pre-rejection (zero tokens).

**Boundary: 160K–195K content** — Usage Policy hits, non-zero tokens confirms pre-rejection tokenization.

**v3: 50K–1M neutral filler**
All passed.
- 50K: 40,218 tokens, found N1
- 600K: 269,145 tokens, found N1
- 800K: 372,718 tokens, found N1 + N2
- 1000K: 456,288 tokens, found N1 + N2

800K: NEEDLE-ALPHA at ~197K depth (inside 200K) + NEEDLE-OMEGA at ~305K depth (beyond 200K) — both found. Hardest evidence for real >200K window.

### Raw results

800K two-needle:
```json
{
  "result": "NEEDLE-ALPHA-7F3A\nNEEDLE-OMEGA-9C21",
  "modelUsage": {
    "claude-sonnet-4-6": {
      "cacheCreationInputTokens": 344729,
      "contextWindow": 200000
    }
  }
}
```

1M two-needle:
```json
{
  "result": "NEEDLE-ALPHA-7F3A\nNEEDLE-OMEGA-9C21",
  "modelUsage": {
    "claude-sonnet-4-6": {
      "cacheCreationInputTokens": 428299,
      "contextWindow": 200000
    }
  }
}
```

### Content policy note

Natural-language prose rejected at large sizes; neutral filler passes.
Diary text (CN+EN dialogue, paths, code) requires functional test — neutral filler is approximation.
"Prompt is too long" = Usage Policy filter.

---

## Task B — per-day token census (haiku, stream-json)

### Method

- DB: `~/.config/marrow/marrow.db`
- Day grouping: `diary.day_events(conn, date)` + `diary._sessions(evs)`
- Session text: `[role] content` joined with `=== SESSION ... ===` headers
- Tokens: `input_tokens + cache_creation_input_tokens + cache_read_input_tokens` from result event
- Baseline: 30,513 tokens ("Reply OK" alone)
- Net tokens: raw − baseline

### Results

Largest session (780d575d, 2026-05-18, 67,167 chars, 47 turns):
- Net: 42,941 tokens — ratio: 0.6393 tok/char

DAY 2026-05-17 (52,408 chars, 6 sessions):
- Net: 34,984 tokens — ratio: 0.6675 tok/char

DAY 2026-05-18 (229,302 chars, 24 sessions):
- Net: 151,497 tokens — ratio: 0.6607 tok/char

DAY 2026-05-19 (159,029 chars, 11 sessions):
- Net: 93,783 tokens — ratio: 0.5897 tok/char

Observed ratio range: 0.59–0.67 tok/char. Representative: 0.66 tok/char.

### Raw usage dumps

BASELINE:
```json
{"input_tokens": 10, "cache_creation_input_tokens": 5877, "cache_read_input_tokens": 24626}
```

780d575d (67K chars):
```json
{"input_tokens": 10, "cache_creation_input_tokens": 48818, "cache_read_input_tokens": 24626}
```

2026-05-18 (229K chars):
```json
{"input_tokens": 10, "cache_creation_input_tokens": 157374, "cache_read_input_tokens": 24626}
```

2026-05-19 (159K chars):
```json
{"input_tokens": 10, "cache_creation_input_tokens": 99660, "cache_read_input_tokens": 24626}
```

### Over-volume guard

Heaviest day: 2026-05-18 = 151,497 net tokens.
Single-call merge: 229K chars × 0.66 = ~151K content + DIARY_PROMPT (~500) + labels ≈ 152K input.
**Guard: 200K net tokens** (≈303K chars) — 30% headroom above observed max, safe for months at current growth.

---

## Commands run

```bash
.venv/bin/python /tmp/mw_probe_taskb_token_census.py
.venv/bin/python /tmp/mw_probe_taska_1m_context.py
.venv/bin/python /tmp/mw_probe_taska_boundary.py
.venv/bin/python /tmp/mw_probe_taska_v3.py
```

## Real heavy-day single-call (2026-05-19)

Probe: `/tmp/mw_probe_real_heavyday.py` | Results: `/tmp/mw_real_heavyday_results.json`

**Task 1: 2026-05-18 CN+EN diary**
- Input: 230,355 chars (diary + sessions via _fence())
- Model: claude-sonnet-4-6 stream-json
- Total tokens: 171,637 (2 new + 158,312 cache-create + 13,323 cache-read)
- Output: 2,716 tokens
- Status: PASS

**Task 2: Content-type dependency (prose rejected, numeric passed)**

From `/tmp/mw_taska_boundary_results.json` and `/tmp/mw_taska_v3_results.json`:

- Prose EN template / 533,271 chars / 136,874 tokens / FAIL (policy refusal, stop_reason="refusal")
- Prose EN template / 650,388 chars / 162,721 tokens / FAIL (policy refusal)
- Numeric filler / 600,886 chars / 269,145 tokens / PASS
- Numeric filler / 800,567 chars / 372,718 tokens / PASS
- Numeric filler / 1,000,979 chars / 456,288 tokens / PASS

**Finding:** Content-type dependent, not token length. Prose refusals at 136-162K tokens; numeric passed at 269K-456K tokens. Real diary passed at 171K tokens.

**Prior agent correction:** Raw stop_reason is "refusal" and error = "API Error: Claude Code is unable to respond to this request, which appears to violate our Usage Policy". No "Prompt is too long" text appears in the raw events. That phrase was an uninferenced paraphrase.

**Single-call design premise: empirically safe at the heaviest real day.**
