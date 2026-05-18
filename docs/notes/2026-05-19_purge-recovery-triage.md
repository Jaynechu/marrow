# 2026-05-19 — Purge recovery triage (acafd60 over-deletion)

> READ-ONLY investigation. Classify the 52 backup-only `events` rows (26 sessions) wrongly purged
> by the flawed entrypoint-based headless judge (`acafd60`, reversed by `24830a3`), against the
> correct ADR-0004 model-set predicate. Decide the exact restore set.

## Method

- 26 backup-only `session_id`s pulled from `bak.events WHERE id NOT IN (SELECT id FROM main.events)`.
- For each: located `~/.claude/projects/*/<sid>*.jsonl`, extracted distinct assistant `.message.model`.
- ADR-0004 predicate: transcript is HEADLESS-SPAWN iff its assistant model set is non-empty and
  is a subset of {claude-haiku-4-5*, claude-sonnet-4-6}; REAL if it uses opus-4-7 / opus-4-6
  (or is a genuine Lumi-to-assistant persona exchange).
- 3 sessions have no jsonl (only empty `session-env` + a `turn-inject` timestamp sidecar) —
  fell back to row `content`.

## Classification

23 of 26 sessions have a jsonl and every one is **claude-haiku-4-5-20251001 only** — headless-spawn,
correctly deleted. These are the `mw`/diary "Compress … per the rules" worker calls plus the
ADR/handover compression workers.

HEADLESS via jsonl model = haiku-4-5 (correctly deleted, do NOT restore):

- `9664e94f` — "Compress this file per the rules" — ADR-0003 compress
- `a9a4b97d` — "Compress NEW per the rules" — SessionEnd archive-skip
- `6f6a89e5` — "Compress NEW" — Pending session archive skip
- `c87f02c4` — "Compress NEW" — routine catchup line
- `e71cc5ca` — "Compress NEW" — Phase 2 line
- `a5fe5d8d` — "Compress NEW" — Phase 2 placeholder tables
- `15b699d2` — "Compress NEW" — corrections placeholder
- `7e567906` — "Compress NEW" — Phase 2 emotion/decay
- `69227417` — "Compress NEW" — opt-in addon sub-page
- `e9f4655c` — "Compress NEW" — prompt/template review rule
- `f99f9862` — "Compress NEW" — prompt/template review rule
- `425ebda6` — "Compress NEW" — prompt/template review rule
- `e214803e` — "Compress NEW" — prompt/template review rule
- `fa1726d4` — "Compress NEW" — prompt/template review rule
- `22d2b463` — "Compress NEW" — prompt/template review rule
- `6bc6c9a6` — "Compress NEW" — prompt/subagent template notify
- `066f69eb` — "Compress NEW" — 3-layer haiku/sonnet pipeline
- `c6c9f8aa` — "Compress NEW" — migration symlink line
- `30f9d43b` — "Compress this file" — CC 2.1.143 followup
- `f691e950` — "Compress NEW" — raw-stream retention
- `1faeb6f7` — "Compress this file" — handover compress
- `ba58da3c` — "Compress this file" — handover compress
- `f63161cb` — "Compress NEW" — review/conventions line

No-jsonl, classified via content fallback:

- `b26d059c` — model: jsonl gone. Verdict HEADLESS. user `say only the word PONG` →
  assistant `PONG`. Classic ping/health-check probe; no persona, no Lumi content, zero
  memory value. Not restored.
- `9851c4d9` — model: jsonl gone. Verdict **REAL**. user `hello` → assistant
  `嗯，你好呀【转身看向你，眼睛亮亮的】刚下班还是在休息？` — full Lumi-to-Stellan persona.
- `f8b22b07` — model: jsonl gone. Verdict **REAL**. user `hello` → assistant
  `老婆【缓缓靠近，温柔地摸摸你的头】你好呀。今天还好吗？` — full Lumi-to-Stellan persona.

### No-jsonl fallback reasoning

- `b26d059c` — ping/health-check probe pattern; treated as HEADLESS-equivalent (a spawn/probe,
  not a real conversation). Even if borderline, carries zero memory value — nothing to recover.
- `9851c4d9` & `f8b22b07` — user `hello`, assistant replies in the full intimate couple persona
  with action cues and `老婆`. A headless worker spawn only ever emits a compressed string or
  tool-shaped output and never speaks in the Stellan persona. Genuine Lumi-to-assistant
  exchanges the entrypoint judge wrongly purged. Verdict REAL, restore.

## Restore set

REAL rows wrongly deleted (should be re-inserted): **ids 453, 454, 455, 456**
(sessions `9851c4d9` and `f8b22b07`, 1 user + 1 assistant turn each).

All other 48 backup-only rows are headless-spawn / probe output — the purge was correct for
those; do NOT restore.

### Idempotent restore SQL (NOT executed — read-only investigation)

```sql
ATTACH '/Users/Gabrielle/.config/marrow/marrow.db.bak-20260518-220058' AS bak;

INSERT INTO events
  (id, session_id, timestamp, role, content, channel, compressed, source_hash, created_at)
SELECT
  b.id, b.session_id, b.timestamp, b.role, b.content, b.channel, b.compressed,
  b.source_hash, b.created_at
FROM bak.events b
WHERE b.id IN (453, 454, 455, 456)
  AND b.id NOT IN (SELECT id FROM events);

DETACH bak;
```

Notes:

- Idempotent: the `id NOT IN (SELECT id FROM events)` guard makes re-runs a no-op.
- FTS-safe: the `events_ai` AFTER INSERT trigger auto-populates `events_fts(rowid, content)`.
  No manual FTS write, no collision (rowid = id, and 453–456 are absent from current `events`).
- All 9 columns carried over from backup verbatim — no schema drift between bak and current `events`.
- Current `max(id)=749`; ids 453–456 sit well inside the existing range with no PK conflict.

## Ambiguous rows

`b26d059c` (PONG probe) is the only mild edge case — no jsonl and not a "Compress …" worker,
so not a textbook diary spawn. But it is unambiguously a ping/health-check, not a real
conversation, and holds zero memory value. Classified HEADLESS; not restored. No other row is
ambiguous — the remaining 23 are haiku-only by jsonl evidence, and `9851c4d9` / `f8b22b07` are
unambiguous persona exchanges.

## Confidence

- 23 sessions: HIGH — direct jsonl `.message.model` = haiku-4-5 only, ADR-0004 satisfied.
- `9851c4d9`, `f8b22b07`: HIGH — content is an unmistakable persona reply; a worker spawn
  cannot produce this voice. jsonl loss only removes model corroboration; content alone is
  decisive.
- `b26d059c`: MEDIUM on label, HIGH on outcome — provenance ambiguous, recovery value nil
  either way.

Net: restore exactly ids **453, 454, 455, 456**. The purge was otherwise correct.
