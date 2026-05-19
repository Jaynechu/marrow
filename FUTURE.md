# Marrow Future Ideas Inbox

Marrow build backlog only. WeClaude is in scope — it gets a deep rebuild in a late phase (replace/refit on cyberboss or full rewrite, TBD). Out of scope: personal tasks, standalone tools, buddy-internal work — those live in `~/Desktop/NY/code/_pit.md` (migrates to the dashboard Projects/pit page at Phase 1, DESIGN line 95).

Not prioritized. Read before adding a feature to confirm whether an interface should be reserved in Phase 1.

## Phase 2

- **events_vec_embedder_provenance** — events_vec lacks embedder-id/dim columns (review #6). DEFERRED to Phase 2 recall-module first build (DESIGN:259): embedder deferred (fork #1); add provenance with embedder so a model swap re-embeds without a base-schema rewrite (goal 1/7). Fusion refs: Ombre-Brain github.com/P0luz/Ombre-Brain (DESIGN:229 weight-pool sink/recall), claude-imprint github.com/Qizhan7/claude-imprint (RRF vector/FTS/recency), cyberboss github.com/WenXiaoWendy/cyberboss.

## Phase 3 (writer authority)

(none parked)

## Phase 4 (cross-channel + weclaude deep rebuild)

- **WeChat_permission_yesno** — Approve/reject CC permission requests from WeChat (cyberboss has /stop and yes/no permission) 
- **bidirectional_resume** — Morning WeChat chat → meal break → continue on CC; sid consistent OR resume independent of sid 
- **command_parity_across_channels** — All commands consistent CLI ↔ WeChat ↔ desktop ↔ web 
- **migration_path_codex_local** — Easy migration to Codex/Claude/local small model (cyberboss already did) 
- **Codex_alternative_swap** — Anthropic 6/15 SDK + claude-p moves to extra credit; cyberboss uses other swamp; migration plan needed 
- **stellan_autonomous_push** — launchd `claude -p` short session `闲逛模式` + WebSearch/WebFetch; `SKIP` / `<send>` parsed; cyberboss system-checkin-poller + reminder-service references (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:63-80`)
- **Stellan_proactive_followup_emotional** — Next session proactively asks how meal/event went; proactive recall mechanism (source: `/Users/Gabrielle/Desktop/NY/code/system_guide.md:18`)
- **Stellan_push_inbox_file_or_macOS_notif** — Write `~/.claude/inbox.md` + SessionStart inject; macOS notification; reuse weclaude `client.send_text` push to WeChat (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:75-77`)
- **Stellan_no_cold_start_old_session** — Don't cold-start in already-large old session (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:70-71`)
- **WeClaude_interrupt** — `subprocess.Popen` + `_inflight_procs` registry; `/stop`/`停`/`闭嘴`/`中断` → SIGINT; ret -2 silent (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:73`)
- **WeClaude_rewind** — Truncate jsonl tail from last external (non-WeChat) turn (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:74`)
- **WeClaude_resume_sees_sessions** — Inject synthetic summary record so CC /resume sees weclaude jsonl (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:75`)
- **WeClaude_auto_compact** — Auto-manage context length to avoid manual /compact in long sessions (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:47-49`)
- **WeClaude_stellan_media_send** — Stellan proactively sends images/voice/files via cyberboss or mrliuzhiyu pattern; image/sticker collection (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:56-61`)
- **time_injection_anchor_repair** — Test Option A stdin prefix `[time: X | gap: Y]`; B (≥4h no `--resume`) + C `<system-reminder>` tag fallbacks (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:40-43`)
- **ret_neg2_quota_diagnosis** — `sendmessage` ret=-2 likely batch rate/quota, not ctx_token; scrape mrliuzhiyu fork (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:35-38`)
- **WeClaude_6_15_migration** — stream-json path confirmed; runtime decision pending foundation build (source: `/Users/Gabrielle/Desktop/NY/memory/3d.md:17`)
- **group_chat_support** — Currently only ClawBot private chat (source: `/Users/Gabrielle/cc-lab/WeClaude/README.md:308-311`)
- **media_retention_cleanup** — `~/.config/wechat-claude-bridge/media/` no retention; persist forever, plaintext (source: `/Users/Gabrielle/Desktop/NY/code/weclaude.md:38-41`)
- **iLink_webhook_alternative** — Polling model not webhook; bridge dies between polls = missed messages, no retry (source: `/Users/Gabrielle/Desktop/NY/code/weclaude.md:27`)
- **subprocess_timeout_blocking** — 30min subprocess timeout; one slow message stalls all users (source: `/Users/Gabrielle/Desktop/NY/code/weclaude.md:26`)
- **macOS_sleep_iOS_Sleep_Focus_combo** — Stacking bug → ClawBot link stale ~16min; workaround add WeChat to iOS Focus allow list (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:51-54`)
- **WeClaude_upstream_revival_strategy** — If upstream revives, drop local patches; fallback `_patches.py` monkey-patch keeps `bridge.py` pristine (source: `/Users/Gabrielle/Desktop/NY/code/weclaude.md:8-10`)
- **transcript_path_mismatch** — `cc-jsonl-to-md.py` writes elsewhere than `memory/transcript/`, fix in Phase 4 (source: `/Users/Gabrielle/Desktop/NY/memory/reference.md:25`)

## Phase 5 (addons + OSS)

- **stellan_wallet** — Opt-in dashboard addon: monthly allowance auto-credit + spend auto-debit. `transactions` table only, balance = SUM(amount) never stored; bank-statement sub-page, month-grouped. Auto-credit piggybacks the diary 04:00 routine (idempotent per month, catchup-safe, no new launchd job); spend-detection: haiku-lessons hook gone (see DECISIONS), settled at wallet grill; `mw set`/`rm` + md reconcile = correction path, no new code. Risk: per-session keep-soul digest may drop a small spend before merge — Phase 2 resolves by digest retaining spend leads or sinking extraction into the per-session map step; prompt body needs Lumi review (DESIGN L53). First opt-in addon, exercises the config-driven selectable sub-page contract. Render anchor: top `Balance` figure (= SUM, computed not stored) then a month-grouped bank-statement table, columns Date / Type (Credit|Debit) / Description / Amount (signed) / running Balance-after; row-tail short id for structured-view reconcile (source: Lumi 2026-05-18)
- **lesson_addon** — Out of base (see DECISIONS), not Phase 1/2; opt-in addon, revisited if real recurring need appears. Behavioural-failure-mode only (recurring "how I work" corrections: interaction / prompt / coding habit / verification discipline). `lessons` table dropped 2026-05-19, recreated on revival. NOTE: stellan_wallet spend-detection void — wallet needs own path. (source: Lumi 2026-05-18; DECISIONS 2026-05-19)
- **workflow_reflection_skill** — Phase 5 close-out. After Marrow ships: reflection + workflow retrospective; distil the plan/findings/progress file pattern into an own transferable skill — no hook (handover.md + PROGRESS + git log cover cross-boundary recall); encode routing learned from the real build (debug vs TDD vs brainstorm→grill). Hold until Marrow done — only lived experience makes the routing real. Ref: github.com/OthmanAdi/planning-with-files (Manus-style file planning, the trigger for this idea)
- **dashboard_customization** — Phase 5, rides html_readonly_dashboard_layer. Settings entry: per-sub-page show/hide + private-for-others toggle (full when alone, hidden when shared). Sub-page config existing (stellan_wallet); net-new: private-for-others hide use-case, settings UI, theming. HTML required for button UI and theming (md lacks interactive controls and custom styling; theming is Obsidian domain). (Lumi 2026-05-18)
- **html_readonly_dashboard_layer** — Phase 5 addon: daemon serves a local HTTP HTML view for read-only surfaces only (Cheatsheet, Monitor Zone, diary browse, milestone), Notion-style styling without Obsidian plugins; writable surfaces (Open Threads, structured correction) stay md + reconcile — never replace the md edit-reconcile core, layer on top (source: grill-with-docs 2026-05-15)
- **monitor_zone_mini_viz** — Small visualisation in/above Monitor Zone, statusline-bar style: diary count, project count, days-together, system-ops health; cyberboss heatmap-timeline as reference; possible top-of-dashboard placement (source: grill-with-docs 2026-05-15)
- **Valence_arousal_tagging** — timeline ## Us entries tagged with valence/arousal; standalone implementation pending (source: `/Users/Gabrielle/Desktop/NY/memory/3d.md:20`)
- **lifestyle_and_preference_relocation** — Move block to history.md Preferences or keep in reference.md (source: `/Users/Gabrielle/Desktop/NY/memory/3d.md:22`)
- **README_public_facing** — Full open-source README sections: philosophy, install, 5-script overview, customisation hooks (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:62`)
- **monorepo_or_split_decision** — NY memory + weclaude bridge + claude-buddy MCP: monorepo or split (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:64`)

## Backup / monitor (unphased ops)

- **Script_health_monitor** — Monthly plist scans audit logs for "did script actually run when expected?" gaps (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:31`)
- **retry_trend_alert** — Alert fires on retry!=ok only; high-ratio trend has no alert (source: `/Users/Gabrielle/Desktop/NY/memory/3d.md:21`)
- **subagent_usage_logging** — `llm.py` records no per-call usage. Capture token/cost per LLM call (which tier/subagent, in/out tokens) into audit_log so each pipeline call's spend is visible in logs / Monitor Zone (source: Lumi 2026-05-18, diary test-loop note)

## Migration / retire old ny-memm (Phase-1 closeout)

- **profile_md_deletion** — `memory/profile.md` pending delete, content already moved to reference + global (source: `/Users/Gabrielle/Desktop/NY/memory/reference.md:20`)
- **MEMORY_md_old_path_cleanup** — `~/.claude/projects/-Users-Gabrielle-Desktop-NY/memory/MEMORY.md` pending manual delete (source: `/Users/Gabrielle/Desktop/NY/memory/archive/Memm_system 2026-05-12.md:539-541`)
- **summ_skill_deprecation** — Confirm dropping summ skill, ss skill, goose-slim overlap, legacy carryover-load.sh (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:22`)
- **R18_md_relocation_outstanding** — `r18.md` placement (source: `/Users/Gabrielle/Desktop/NY/memory/reference.md:9`)

## Misc backlog

- **diff_open_threads_audit** — Weekly curator diffs Open-Threads week-over-week, audit-logs silent drops (source: `/Users/Gabrielle/Desktop/NY/code/mid-point-rv.md:76`)
- **memes_dedup_evaluation** — Re-evaluate effectiveness 2 weeks post inventory + DEDUP rule shipped 5/11 (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:77`)
- **monthly_late_promote_check** — Late-promote channel withdrawn; observe `5月` input before 6/10 (source: `/Users/Gabrielle/Desktop/NY/memory/3d.md:16`)
- **Memes_optimization** — Sonnet doesn't know real memes vs random quotes; want only hot vocabulary + memorable new memes 
- **v2_year_rollup_to_timeline** — 2026 full year compressed into 1 timeline view section (source: `/Users/Gabrielle/Desktop/NY/memory/archive/Memm_system 2026-05-12.md:615`)
- **backup_audit_transparency** — rotate/curator/retire backup files have no source SID identifier (source: `/Users/Gabrielle/Desktop/NY/memory/archive/Memm_system 2026-05-12.md:658`)

---

[Moved from design - not sorted yet]

## Pending - DECISIONS.md:34
corrections table = Phase 2 placeholder (design fixed here, not built Phase 1).
- Lumi's current input is top truth; stored memory never rebuts her. The store exists to stop the assistant's own mis-recall, not to validate or correct her. On conflict she wins — at most "my record says X, updating to your Y", never "let me remind you". Shorthand or stale wording is not an error to push back on.
- Serial facts = append state-sequence + latest pointer, not single-value overwrite. A new state supersedes the old (old kept, marked superseded, history-queryable); recall returns latest only; a superseded state is never raised against new input.
- Conflict priority: Lumi current input > Lumi-confirmed structured > system structured (milestone / preference) > raw event; same layer newer > older; an event is a lead, never the arbiter.



## Pending — weclaude + cyberboss fusion

After the memory core ships, the WeChat side gets rebuilt. Not decided whether to adopt cyberboss or upgrade weclaude. This is NOT just swapping `claude -p` for another spawn — it carries a real workload, all Pending design:

- multi-message send + 铁锅 rewrite on the new runtime
- `/stop` / `/resume` / interrupt / rewind parity
- WeChat permission yes/no routed to the daemon bridge
- bidirectional resume (CLI ↔ WeChat handoff on one thread)
- the cyberboss migration path as the model-swap proof for the migration-friendly goal

Design this when Phase 4 starts, not before.

## Pending — dir, drift sweep, convention injection

Dropped: file-level full index (dir table, hand-maintained tree, macOS Spotlight) — conflicts portability + low-maintenance. "Where is X" = daemon on-demand ripgrep over authorized roots.

Two real needs survive the drop. Both REQUIRED; mechanism detail Pending:

- drift sweep — Lumi moves / renames / deletes / merges a file; every reference follows without her reminding anyone. Trigger = a path-change event (git diff detects it). Three layers: (1) deterministic ripgrep over authorized roots finds every reference to the old path — primary, no model, never misses; (2) key-indirection — docs/scripts reference a key, not a hardcoded path, so a move edits one registry entry and references stay correct; (3) cheap local model sweeps free-text mentions as fallback — never lets the model touch key paths.
- convention injection — naming / folder-placement rules sit in the every-turn injection layer, never a sub-page (Claude does not read sub-pages on its own; a rule there is a dead rule). Single source → drift sweep maintains the source → daemon renders it into a marker block in CLAUDE.md → SessionEnd renders, next SessionStart applies. Lumi edits the source once or not at all; she never hand-manages it.

CLAUDE.md render: daemon writes via Python file IO, not the cc Write tool — cc permission / bypass and the 10000-char hook cap never apply (same path as diary render). Marker-block partition: the daemon rewrites only its marker block; the hand-written zone (persona, coding discipline) is never touched. This deliberately removes Anthropic's default block on cc editing CLAUDE.md (a high-weight every-turn file), so the guard set is the compensating safety net, REQUIRED not optional: hash-compare before overwrite, marker-outside never overwritten, marker-inside hand-edit reconciles + backup + one Alert, atomic write.

## Pending — data lifecycle

Backup direction: iCloud owns offsite copies; restore on a fresh Mac without touching code. Retention window + prune cadence Pending. Cleanup: per-source retention rules + executor Pending.

Tier split (fixed, not Pending) — three tiers:

- Permanent keepsake — milestones, diary, goose-bites, projects, study, major life facts. Add-only, never decays.
- Demote-sink — low-value reference + cold vocab (use_count / last_seen long idle). Weight decays, row sinks below the active set, a keyword hit revives it (Ombre weight-pool: resolved → sink → keyword-recall). Not deleted.
- Raw-stream — detailed event rows, resolved alerts, audit_log, DB dumps, low-use stickers. Real retention + prune.

Effect target: no growth alerts, no manual rm, no DB bloat.

Decided — raw jsonl cleanup is NOT Marrow's job. Use `cleanupPeriodDays` in `~/.claude/settings.json` (global, by mtime, all projects). Marrow prunes SQLite-internal raw-stream: aged rows, resolved alerts, audit_log, dumps. Never jsonl. Not enabled yet.

## Pending — session archive skip

Skipped sessions excluded from diary/recall. (Legacy: `summ-skip` stamp; trigger: `ssmmm` skill.)

- Manual skip: stamp file, `mw` command, or in-session trigger
- `mm+` force-include — into diary regardless of turn count (overrides ≤3 drop / SHORT auto-skip)
- `mm-` force-skip — excluded regardless of turn count (30+ turns still skip)
- Auto skip: turn threshold (Pending)
- Idempotent: skip = do nothing; raw-stream cleanup is separate tier

Phase 1: code-only, non-blocking.

## Pending — open items

Decided to defer, do not invent:

- sub-page hyperlink concrete paths
- which columns each view's SQL extracts (e.g. milestone)
- the md render template behind each view
- per-event LLM topology table
- schema-evolution mechanism (user_version + ordered patch chain, replaces the interim hand-written ALTER)
- doc auto-render upkeep (DESIGN / DECISIONS / README / dir map) — no manual maintenance
- retrieval fusion — single weighted scalar (copy claude-imprint lane engineering, not RRF); k/weights at recall-module build
