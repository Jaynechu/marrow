# ADR-0007 — recall = SQLite + claude-imprint; breath is Ombre's engine; generic recall ≠ emotional entry

Status: accepted (2026-05-19, grill round 4, Lumi-adjudicated)

## Context

Recurring failures: fused generic recall + SessionStart; treated Ombre breath as Marrow concept; struck/reverted claude-imprint (0ae253d, 9d9725d). Root cause: DESIGN left recall/entry boundary and breath definition implicit.

## Decision

- **breath = Ombre's recall engine** (decay-score rank over .md buckets, dehydrate, token budget); Ombre lacks SQLite. Marrow recall is SQLite, so breath inapplicable—never a Marrow feature.
- **Marrow recall = claude-imprint** (RRF: full-text + vector + recency); chosen, not a fork.
- **Generic recall**: SQLite core—event rows + diary pulls. Claude self-pulls in-session, on-demand, unbounded, cheap (goal 3).
- **SessionStart emotional entry**: once per session, no re-pull. Top-N (recency + arousal + importance) over diary as lived-through backdrop (阶段性情绪); diary = ranking input, not text.
- **emotion = valence + arousal**, emitted by diary-writing sonnet (option C: zero agent/link, never SessionEnd); orthogonal to importance.
- **decay: score = importance × e^(-λ·days_idle)**. Reject Ombre's activation_count^0.3, short-long weight, urgency_boost, freshness bonus (complex). Implementation: demote-sink, lazy recall, keyword revives, λ + threshold at build.
- **diary.mood**: day's emotional key, both sides.

## Consequences

- No per-turn or per-N-turn emotional refresh. In-session, past resurfaces via Claude self-driven generic recall only, never re-pulled backdrop.
- claude-imprint = build target. Ombre decay shape, not engine.
- Ombre's dehydrate-on-surface = build-time reference, not pinned.
- ADR-0005 (emotion in diary, no feel layer) unchanged; this fixes the recall/entry boundary ADR-0005 left implicit.
