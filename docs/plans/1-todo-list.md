# Marrow — todo (from MAP §14 drift, 2026-05-31)

> Real problems pulled from the MAP audit. Each one needs code, not docs. Ordered roughly by user-visible blast radius.

---

## 1. Subpage bidirectional reconcile — expand beyond milestone + atlas

**Why it matters**: today, 9 of 11 subpages are DB→md only. Anything Lumi hand-edits on those pages (meme pin toggle, entity fact rewrite, sticker description, goose-bite revote) gets silently overwritten on the next render.顺便看一下dormant的问题

- **Already bidirectional**: milestone (reconcile_milestones), atlas (reconcile_atlas)
- **Missing md→DB**: profile · diary · memes · stickers · wallet · goose-bites · study (index + children) · projects (index + children) · cheatsheet (by design, disk SoT)
- **First targets (highest user value)**:
  - memes — pin / unpin toggle via emoji or `<!-- pin:1 -->`
  - profile — entity fact / aliases edit (Lumi already hand-edits entities and they revert)
  - goose-bites — revote / pick a different quote of the day
- **Pattern to follow**: copy reconcile_milestones (marrow/reconcile.py:162). Parse the rendered block by id anchor, diff vs DB row, INSERT/UPDATE/DELETE with audit_log entry. Hook into write_subpage so reconcile runs before render.
- **Acceptance**: edit a meme pin in dashboard → save → next sync_loop tick → DB pin column changes, render re-emits the edit.

---

## 2. Alert system — rewrite §8 as a listing, mirror catchup style

**Why it matters**: Lumi flagged §8 as 一坨 prose with no actual fail-path coverage. catchup §9 lists each self-heal path explicitly (sessionstart_catchup, daily_catchup, affect-heartbeat, etc.) — §8 should do the same for alerts.

- **Inventory (from rg add_alert sweep, 2026-05-31)**:
  - backup.py: 127 critical local · 140 warn offsite
  - daily.py: 167/258 warn · 228/322 critical · 301/313 warn (subpages, goose-bites)
  - dashboard.py: 150/158/166 warn (candidate / task / affect reconcile)
  - drift_sweep.py: 452 dynamic (info/warn/critical via _emit_alert)
  - hooks.py: 211 warn catchup spawn · 333 warn sessionend spawn · 679 info atlas_hook · 704 warn hook main
  - reconcile.py: 794 warn unanchored task
  - sessionend_async.py: 233 critical/warn catchup retry · 486 warn dashboard write · 496 warn embed
  - sessionstart_catchup.py: 273 critical silent_death · 330 warn catchup spawn
  - subpages.py: 118/129/136/293/378/388 warn (db_pages + atlas sweep)
- **Real gaps the rewrite must fix**:
  - watcher crash — no alert anywhere; watchdog.Observer dying silently kills the whole sync layer
  - embed_pending UNIQUE conflict — alert #169 type, currently fail-soft only on the LLM-call try/except, DB-level UNIQUE collisions vanish
  - sync_loop reconcile exception — no alert; reconcile inside sync_loop tick raises and the next tick just tries again forever
  - atlas_sweep_fs standalone — alert only fires when called through subpages.py:293, the launchd path doesn't alert
- **Shape of the rewrite**: keep §8 as "what alerts are + storage + dashboard render". Add §8.1 = listing table, one row per alert site (file:line · severity · type · trigger). Add §8.2 = known gaps (the four above).

---

## 3. embed_pending lane — add catchup + tighter alert

**Why it matters**: alert #169 has been quietly warning for a while. The lane is fail-soft so the visible symptom is "embeddings just stop updating" — silent rot of recall quality.

- **Diagnosis first**: run `mw embed --apply` manually, look at the actual sqlite error message (UNIQUE constraint failed on events_vec primary key). Decide whether the cause is (a) rowid collision after a DELETE+INSERT, (b) a stale meta row pointing to a vanished events row, or (c) something else.
- **Fix candidate A**: in embed_pending, catch UNIQUE on insert, attempt UPDATE on the conflicting rowid, log if both fail.
- **Fix candidate B**: add a sweep before insert that purges vec_meta rows whose rowid no longer maps to a base table row (this already exists for diary at marrow/recall.py:340 — generalise to all 6 lanes).
- **Catchup leg**: add embed_pending to §9 — either a periodic sweep in aging.py or a check at sessionstart_catchup that backlog ≤ N rows, alert critical if exceeded.

---

## 4. Decay floor — `imp >= 8` is unreachable on the 1–5 scale

**Why it matters**: `_decay_floor` (marrow/recall.py:436) gates the "Permanent FLOOR 0.5" tier on `imp >= 8`, leftover from an old 1–10 scale. Importance was locked 1–5 from day one, so the permanent floor never triggers — high-importance rows decay the same as imp 4–7.

- **Fix**: re-tier on 1–5. e.g. `imp == 5 (or source=override) → 0.5`; `3 ≤ imp ≤ 4 → 0.18`; `imp ≤ 2 & age > 90d → dormant`. Keep `_is_dormant` aligned.
- **Acceptance**: imp-5 row >90d still scores ≥ 0.5 * raw at read time; recall test surfaces a milestone-tier memory after long gap.

---

## 5. Memes aging — `DELETE` should be `demote dormant`

**Why it matters**: `retire_memes` (marrow/aging.py:48) hard-deletes rows with `pinned=0 AND last_seen > 90d`. DECISIONS:46 says aging should demote to dormant (recall excludes, FTS-key match revives). Hand-delete from md still goes through reconcile and stays DELETE — only the 90d auto-pass changes.

- **Schema**: add `dormant INTEGER DEFAULT 0` to memes table (migration step). recall lane filters `dormant=0`.
- **Aging pass**: flip the DELETE to `UPDATE memes SET dormant=1`.
- **Revive**: FTS phrase hit on a dormant key → `UPDATE memes SET dormant=0, last_seen=now`. Also `mw memes promote <key>`.
- **Acceptance**: meme last_seen 100d ago, pinned=0 → after aging, row still exists with `dormant=1`. Recall excludes it. Trigger phrase in a fresh event → next sync brings it back.

