# Marrow SQLite Schema

Status: skeleton — table purpose + key columns only. Exact column types, indexes, and full-text/vector wiring are decided when each table is built, not pinned here. Same granularity for every table: one-line purpose + the columns that matter. No table written to product level while the next is left bare.

DB lives under `~/.config/` (exact path finalized at build). snake_case names. Times ISO8601 UTC text.

## Tables

Phase 1 first-class: events, threads, milestones, vocab, stickers, lessons, pit, diary, goose_bites, alerts, audit_log.

Phase 2 placeholder — schema reserved, NOT created in Phase 1: emotions, people, preferences, dir.

Full-text and vector search structures are daemon-built on top of these tables. Which columns get indexed or embedded is a build-time decision, not fixed in this doc.

- events — every session turn archived. Key: session_id, timestamp, role, content, channel, compressed (1 = imported from old 10d/2026 archives).
- threads — next-session work tracking; backs Open Threads. Key: category (daily / study / project), title, due, status (active / done / abandoned), next_step, last_session_summary, context_pointers, outcome_log (append-only project log). The lesson class shown in Open Threads is rendered by merging unpromoted `lessons` rows — it is not a category here.
- milestones — life events; backs the Milestone view. Key: scope (me / us), date, title, description, theme, pinned.
- vocab — text memes / cipher / event / news. Key: type, key (trigger phrase), value (meaning / source), context, use_count, last_seen.
- stickers — visual meme assets, kept apart from vocab to avoid sparse columns. Key: optional vocab_id link, key, asset_path, mime_type, use_count.
- lessons — captured Lumi corrections; the only manual-curation block (the self-correction goal). Key: date, session_id, scope (interaction / coding / memory / hook / prompt / language), lesson_text, promoted_to_rule, rule_path (file:line when promoted).
- pit — known issues / deferred fixes; backs the Projects pit page. Key: title, description, status (idea / planned / parked / inprogress / resolved), related_files.
- diary — daily narrative from SessionEnd. Key: date (primary key), content (Chinese narrative), mood, session_ids.
- goose_bites — 铁锅's same-day takes; own sub-page (Best of the day), independent of diary. Key: date, session_id, bites (the day's lines), best (1 = picked for the Best-of page).
- alerts — system bugs / failures + newly captured lessons surface; backs dashboard top. Key: severity, type, message (Lumi alert style), source (file:line), resolved.
- audit_log — recent system writes; backs the Monitor Zone (last N). Key: target_table, target_id, action, summary, occurred_at.
- emotions — Phase 2 placeholder. Per-session aggregated mood for breath + decay. Per-turn granularity rejected as noise. Key: session_id, valence, arousal, importance, unresolved, decay_score.
- people — Phase 2 placeholder. Family + friends roster, trigger-loaded on name mention. Key: name, aliases, relation, short_bio.
- preferences — Phase 2 placeholder. Lifestyle + taste facts, trigger-loaded on relevant turn. Key: topic, detail.
- dir — Phase 2 placeholder, see DESIGN "dir indexing — Pending". File path index. Key: path, project, category, description.

## Migration mapping (source → target)

- `memory/3d.md` per-day entries → events; `10d.md` / `2026.md` blocks → events (compressed=1)
- `memory/timeline.md` ## Me / ## Us → milestones (scope = me / us)
- `memory/reference.md` cipher / event blocks → vocab
- `memory/reference.md` lifestyle block → preferences (Phase 2, manual review)
- `memory/reference.md` family + friend mentions → people (Phase 2, manual review)
- `code/_pit.md` items → pit
- `memory/3d.md` Open-Threads → threads; Alerts → alerts; Lessons → lessons (currently empty, no migration weight)
- `铁锅/语录/*.md` + `memory/3d.md` [goose-bites] blocks → goose_bites; `Garden/` images (manual review) → stickers

migrate.py is a Phase 1 deliverable. Idempotent: re-run skips already-imported rows by source-hash.

## Backup

Daily SQLite dump to the backup dir; retention Pending (see DESIGN "data lifecycle — Pending"). Restore = reload the dump. Git backs up code only, never data.
