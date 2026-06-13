2026-06-13

# Timeline ADD date-context + sort scramble fix

Three coupled bugs in the timeline subpage write-back + render. Fix all three. TDD: write a failing test per bug first, then fix, commit per logical unit.

Files in scope:
- `marrow/marrow/reconcile.py` — `reconcile_timeline()` ADD path (~L1646-1679), `_TL_PLUS_RE` (L1459)
- `marrow/marrow/timeline.py` — `_render_24h()` (L449-533), `_render_2472h()` (L536-580)
- `marrow/tests/test_reconcile_timeline.py` and timeline render tests — add cases

Do NOT touch config/hooks/settings. Run `pytest marrow/tests/` — keep the full suite green (1184 baseline).

---

## Bug 1 — `+` ADD ignores the day block it sits under + rejects AM/PM/ND

Symptom: typing `+AM 吃饭` (or `+ 吃饭`) under the `--- 06-12 ---` divider writes a manual event at `now()` (today 22:50), not 06-12.

Two root causes:
1. `_TL_PLUS_RE` only captures `HH:MM`. `+AM 吃饭` → hhmm group None → falls to `ts_utc = _now()`.
2. The ADD loop (reconcile.py:1646-1679) never reads which day-block the `+` line sits under. It must.

### Required behaviour

When parsing the ## Timeline block, walk lines top→bottom and maintain a **current day-context date** as you go. The day context updates whenever you pass:
- a `--- MM-DD ---` divider (24h zone; year-less)
- a `**MM-DD Day 【...】**` header (24-72h zone; year-less)
- a `<!-- tl:d:YYYY-MM-DD -->` day anchor (day 4-7 zone; full date)
- a `--- MM-DD ---` style line in any form already emitted by the renderer

Resolve a year-less `MM-DD` to a full date by picking the **most recent past (or today) date** matching that MM-DD within a ~14-day lookback from today (timeline only spans ~8 days). Lines above the first divider (top of block) = **today**.

For each `+` line, compute its timestamp from:
- **date** = the current day-context date at that line's position (today if none)
- **time**:
  - explicit `HH:MM` → use it
  - period label `AM` / `PM` / `ND` (case-insensitive, as the token right after `+`) → representative local hour: **AM→09:00, PM→15:00, ND→21:00**
  - neither → if date == today use `now()`; else use **12:00** local (noon) of that date
- Build the local Melbourne datetime from (date, time), convert to UTC `%Y-%m-%dT%H:%M:%SZ`, insert as the manual event timestamp.

Keep the existing backdating-by-24h heuristic ONLY for the bare-`HH:MM`-under-today case (a `+ 23:00` typed at 09:00 today = last night). When an explicit day-context date is present, that date wins — do NOT also roll back 24h.

`_TL_PLUS_RE` must accept an optional leading period token: extend to capture either `HH:MM` or `AM|PM|ND` (case-insensitive) before the text. The plus-line parse currently happens at L1531 (collect into `plus_lines`) and L1647 (insert). You'll need to thread the per-line day-context into `plus_lines` — store `(day_context_date, raw_line)` tuples instead of bare strings so the ADD loop knows the date. Compute day-context during the single `for raw in block.splitlines()` scan (L1525).

### Test
- `+AM 吃饭` under a `--- 06-12 ---` divider → manual event timestamp resolves to 2026-06-12 09:00 Melbourne (UTC equivalent).
- `+ 14:30 咖啡` under `--- 06-12 ---` → 06-12 14:30 Melbourne.
- `+ 随手记` at top of block (no divider above) → today, now().
- `+ND 宵夜` under a `<!-- tl:d:2026-06-09 -->` anchor → 06-09 21:00 Melbourne.
- Year-less `--- 01-15 ---` while today is 06-13 → resolves to 2026-01-15 (most recent past match), not a future date.

---

## Bug 2 — 24h film-strip first-line sort key diverges from its displayed time

Symptom: a 06-13 08:07 line appears sandwiched between 06-12 lines, with a duplicate `--- 06-12 ---` divider.

Root cause: in `_render_24h` (timeline.py:503-508), the first life-line of each casual session (idx==0) forces `sort_key = ts` (session start UTC) while its **displayed HH:MM and `line_date`** come from the line's own parsed time (`_life_line_utc_and_date`). When the session start and the first line's own time differ, the line sorts at one position but is day-attributed to another → out-of-order render + duplicate dividers.

### Fix
Sort every line (including idx==0) by its **own** per-line computed UTC (`sort_key` from `_life_line_utc_and_date`), so sort order, displayed time, and day attribution agree. Drop the `sort_key = ts` override at L503-504. Keep the tone-tag-on-first-line behaviour (that's display, not sort).

Verify the "session-level ordering stays stable" intent the old override was protecting is still satisfied — within a session, lines are emitted in life_items order and now sort by their own ascending times, which is the desired chronological order. Confirm no test regresses on session grouping; if one does, it was asserting the buggy behaviour — fix the assertion to the correct chronological expectation and note it.

### Test
Construct a casual session whose start `ts` is e.g. 06-13 04:00 local but whose first life line is `08:07 …` and a later 06-12 evening item exists. Assert the rendered order is strictly newest→oldest by displayed time and that exactly one `--- 06-12 ---` / `--- 06-13 ---` divider each appears, no duplicates, no sandwich.

---

## Bug 3 — manual events vanish when backdated beyond 24h

Symptom (consequence of fixing Bug 1): a manual event backdated to 06-12 (>24h ago) is written to DB but never rendered — `_render_2472h` only renders `session_digests`, not `channel='manual'` events.

### Fix
Render manual events in the 24-72h zone too. In `render_timeline`, also query manual events for the zone_b window (`zone_b_from_utc` .. `t_24h`) and pass them into `_render_2472h`. Bucket each manual event by `_period_diary_date(ev['timestamp'])` into the same `(date, period)` buckets, and append its `content` (with `<!-- tl:e:N -->` anchor so it stays editable/deletable) into that period's line, time-ordered alongside session tl_lines. Respect the existing `_2472H_CAP` and 80-char period truncation, but do not let truncation drop the anchor (anchors are invisible to budget — keep them attached to their event's text segment, or append anchors after truncation).

Keep the existing `_query_manual_events_24h` for the 24h zone unchanged; add a sibling query (or generalise it to a range) for the 24-72h window.

### Test
Insert a `channel='manual'` event at 06-12 09:00 local (≈37h before a fixed 06-13 22:50 render-now). Assert it renders under the **06-12 AM** period line in the 24-72h zone with its `<!-- tl:e:N -->` anchor present, and that deleting it via the trail mechanism still works (anchor round-trips through reconcile).

---

## Verify
- New tests red first, then green.
- Full `pytest marrow/tests/` green (1184 baseline; if a pre-existing unrelated fail appears, report it, don't fix-pad).
- Commit per bug. Do not push.
