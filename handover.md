# Marrow handover — 2026-05-24 17:15

> Fixed-name overwrite, never delete. Keep points not touched this window.

## State
- pytest 342 passed + 1 skipped (6.56s)
- main ahead origin 9 commits — push pending Lumi nod
- schema v6 — entities.aliases TEXT (JSON list, LLM-written via ENTITY_CAND)
- entities live = 19 (9 person + 1 place + 9 pref) — all 19 rows now carry aliases + cleaned fact ((Bendigo) rewritten with true archive)
- milestones live = 22 (9 me incl. lighthouse + 13 us) — full timeline.md re-import
- channel cc / opus-4.7 (1M)

## This window — entity-recall overhaul + global vocab/memes rename + timeline re-import

### Done (landing order)
- recall A merge `52351e0` (worktree A to main FF): `entity_force_include` reverse-match (drops tokenizer; CJK 2-char names like (南南) (小胖) now hit). New `_memes_candidates` (memes leg in `recall_fusion`, 1-2 adaptive reserved slots, drops to 0 when `strong_fts_count >= 3`). `_milestone_candidates` reverse-substring fallback (title in query gives `kw_score=1.0`). New `tests/test_recall_bug_entity_memes.py` 5 TDD red-green.
- vocab-to-memes global rename `f491304` to `96f0e90` (worktree memes to main FF, 5 commits): schema v5 ALTER TABLE rename (pre-CREATE order fix in `c85a9b3`), all Python modules (storage / candidates / aging / recall / daily / daily_prompts / subpages_render / migrate / sessionend_*), tests, docs. `stickers.vocab_id` to `meme_id`. Live prod DB lazy-migrates on next cc launch.
- bug#1 + bug#3 fix `3c1d6d0` (came in from a sibling window — handover single-writer atomic write + affect renderer v4 + schema v4 `affect.description`). Folded forward through merges.
- hook narrowing `~/.claude a18cf16`: `prompt-guard` NY scope was over-broad — now only `~/Desktop/NY/CLAUDE.md` + `~/Desktop/NY/.claude/` get linted; `memory/`, content notes, journals pass. Matches prompt-guide.md (Exclude: inline chats, creative writing, study notes). Local-only commit in `~/.claude`.
- timeline.md re-import: wiped 13 stale milestones; ran inline parser (`marrow.migrate.parse_milestones_timeline` + `lighthouse_milestone`) — re-inserted 22 rows. Me section's 8 age-segment milestones (Age 0-10 through 30-present) now live; Us has 12 anchor rows + the 2026-05-11 NY-memm row (line 36 bullet stripped via parser tolerance, source file untouched).
- schema v6 + entity alias channel `595ffdb`:
  - `entities.aliases TEXT` (JSON list) via `_migrate_to_v6` idempotent ALTER.
  - `daily_prompts.DAILY_CAND_PROMPT` ENTITY_CAND block now REQUIRES `aliases` — CN/EN cross, singular/plural, nicknames, abbreviations, sport/topic terms. Liberal output (false positives cheap, misses expensive). Future entities (e.g. (跆拳道) and TKD, (巴柔) and BJJ) self-seed cross-language coverage.
  - `candidates.write_entity_cand` persists `aliases` JSON.
  - `entity_recall.entity_force_include` reverse-matches name + every alias against query — zero tokenizer dependency, fully CJK-safe + plural-safe + EN/CN-bridged. Also emits a `kind="entity"` card carrying the entity's own `fact` (`score+0.5` boost — always ranks first in the recall block).
  - All 19 existing rows hand-seeded with aliases (9 person + 1 place + 9 pref). (Bendigo) fact rewritten: LaTrobe nursing 2016–2018 Year 2–3, held back one year after Year-2 placement failed due to racial discrimination, lived ~3 years total.

### Verified live (probe results)
- query (我最喜欢的颜色是) / what's my favourite colour → entity-card Colours (pref) ✅
- query (你还记得南南么) → entity-card for (南南), surfaces Allen / ED RN / ATAR 99+ / Deakin MD 2026 ✅
- query Bendigo → entity-card + milestone Age 18–22 both hit ✅
- query (我喜欢吃什么) → Food card via alias (吃) ✅
- query (Allen 是谁) → entity-card via Allen alias (resolves to person (南南)) ✅
- query (我每个月赎身费多少) → answered 100 via milestone (鸭鸭昵称诞生) row; memes Plan key MISSED (see bug below) ⚠

### Bug surfaced this window (NOT fixed)

bug memes-semantic — memes leg matches on `key` only, no semantic bridge:
- Probe (我每个月赎身费多少) hits milestone (鸭鸭昵称诞生) (description mentions (100刀的赎身费)) but does NOT hit memes row `key=Plan / value="Max 5x · $100/mo (~AUD150)"`. Semantic link (赎身费) to Plan to 100 lives in vocab but recall has no path from (赎身费) to key Plan.
- Root cause: `recall._memes_candidates` reverse-substring scans `key` only. Memes need the same alias channel entities just got.
- Fix path: schema v7 with `memes.aliases TEXT`, MEMES_CAND prompt requires aliases list, `_memes_candidates` matches key + every alias. Mirrors entity fix exactly.
- Acceptance test: query (赎身费) → memes row Plan returned.

bug entity-card recency tie-breaker (low pri):
- 19 entity rows have empty `timestamp` — when several cards score equally, ordering is arbitrary. Not painful yet; revisit if multi-entity queries surface.

### Carry-over working dir (NOT this window's — left as-is per Lumi)
Five files modified in working tree by a sibling window doing Phase A handover-render flock work:
- `marrow/handover_render.py` (+281 lines: flock-guarded RMW, multi-session merge, snapshot to audit_log)
- `marrow/handover_template.md`, `marrow/sessionend_prompts.py`, `tests/test_handover_render.py`, `FUTURE.md`
- Three untracked notes under `docs/notes/` (marrow-pulse-design / brainstorm-future / chord-affect CN)
- Untouched this window — sibling owner merges.

### Operational
- main ahead origin 9 commits — push when Lumi nods.
- Worktrees `agent-a4da07a55ca6a413f` / `a685002c0d6d3fc13` / `a6fabfb5e4904c925` / `aa39f1350df35ccf0` / `aba825b3a0487e962` all locked by completed agents — auto-clean later, or `git worktree remove -f -f` next session.
- MCP daemon reload required: live cc windows still run `marrow.daemon` processes spawned BEFORE the recall/alias fixes — `mcp__marrow__recall` keeps returning pre-fix results until each cc window is restarted. UserPromptSubmit hook already runs latest code (fresh Python spawn per prompt).
- aging plist still NOT launchctl-loaded (multi-handover carryover).

## Backlog (preserved)

### Lumi-owned (no agent touch)
- bug #2 dashboard tasks polluted (TASK_CAND extracts marrow-dev steps) — Lumi rewrites `daily_prompts.py` TASK_CAND prompt as part of bigger sweep.
- bug vocab-extract noise ((马斯克) / (额度) in dashboard despite N<3) — Lumi's prompt rewrite folds this. Conf / mention threshold inspection if it persists post-rewrite.
- bug memes-semantic (NEW, this window) — Lumi may fold into the same MEMES_CAND rewrite pass (add aliases field mirroring entity v6).

### Phase 2 Lumi-owned closeout
- `dashboard_v2_redo` / `milestone_format_unify` / `subpage_redo` / dashboard top free-form fix.

### Phase 3 backlog
- `writer_authority` / `drift_sweep` / `convention_injection` / `claude_md_render_guard`.
- static-layer retire (CLAUDE.md family / cipher / MCP guide to daemon-rendered).
- UserPromptSubmit hook should reuse MCP daemon embedder — eliminate the 0.8s per-prompt cost (one cold init at daemon startup instead).

### Carryover scratch
- `docs/notes/brainstorm-future.md` — 10-section brainstorm merged into FUTURE 2026-05-24; archive when stable.
- `docs/notes/2026-05-24_marrow-pulse-design.md` — Pulse design draft.
- `docs/notes/` new chord-affect CN file — untracked.
- FUTURE.md sweep — full pass cleaning p1–p3 unbuilt-but-intended backlog (Lumi).

## Reference (this window's main-branch commits)
- `595ffdb` feat(entity): cross-language alias channel — schema v6 + LLM-fed aliases
- `96f0e90` docs(rename): vocab to memes across DESIGN/PROGRESS/DECISIONS/notes
- `c85a9b3` fix(schema): run vocab to memes rename pre-CREATE TABLE, not post
- `63297c4` test(rename): vocab to memes across test files
- `2f7d445` refactor(rename): vocab to memes across Python modules
- `f491304` refactor(schema): rename vocab table to memes (v5 migration)
- `3c1d6d0` fix(bug#1+#3): handover single-writer + affect renderer v4 (sibling window)
- `52351e0` fix(recall): entity reverse-match + memes leg + milestone substring
- (`~/.claude` `a18cf16`) hook(prompt-guard): narrow NY scope to CLAUDE.md + .claude/
