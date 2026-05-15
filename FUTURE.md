# Marrow Future Ideas Inbox

Captured 2026-05-15 by background agent scan of:
- `~/Desktop/NY/code/*.md` — manual, roadmap, system_guide, mid-point-rv, _pit, buddy, rule
- `~/Desktop/NY/memory/3d.md`, `reference.md`
- `~/Desktop/NY/CLAUDE.md`, `~/.claude/CLAUDE.md`
- `~/cc-lab/WeClaude/README.md`, `bridge.py`
- `~/.claude/skills/*/SKILL.md`

Not prioritized. Read this before adding new features to confirm whether an interface should be reserved in Phase 1. Status of each item is the source-of-truth's phrasing, not a commitment.

## Addon Ideas

- **CC_Independent_Study_Project** — Separate CC project for Study assignments to avoid context pollution; symlink/import shared layer; independent Study/threads.md for essay carryover (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:19-28`)
- **marker_TORCH_DEVICE_mps** — Default `TORCH_DEVICE=mps` prefix when invoking marker for PDF→md speed (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:30-32`)
- **xhs_skill_browse** — Install useful skills from xhs / gh repos (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:33`)
- **Submit_Self_Check_skill** — `自检/check before submit` skill: AI fingerprint scan, format uniformity, grammar with tolerance band, read-only report on PDF/DOCX/PPTX (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:86-148`)
- **launchd_email_digest** — Replace Cowork scheduled email digest with launchd + osascript Mail.app + `claude -p` template (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:150-158`)
- **marker_PDF_wrapper_rule** — CLAUDE.md rule: >20 pages or "marker" trigger → marker; <20 pages → Read; output in-place (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:160-164`)
- **marker_md_shell_function** — `marker_md` wrapper: marker_single + assets/ subfolder + image path sed-rewrite + `!`-prefix Obsidian sort fix (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:209-220`)
- **念念不忘海岛_Obsidian_migration** — Apple Notes 11-note folder → `~/Desktop/NY/Garden/` via osascript batch export (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:200-202`)
- **Pit_automation_template** — `_pit.md` rename + tighter tags (idea/planned/parked/inprogress) + sonnet routing of chat ideas (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:28`)
- **Valence_arousal_tagging** — timeline ## Us entries tagged with valence/arousal; standalone implementation pending (source: `/Users/Gabrielle/Desktop/NY/memory/3d.md:20`)
- **lifestyle_and_preference_relocation** — Move block to history.md Preferences or keep in reference.md (source: `/Users/Gabrielle/Desktop/NY/memory/3d.md:22`)
- **diff_open_threads_audit** — Weekly curator diffs Open-Threads week-over-week, audit-logs silent drops (source: `/Users/Gabrielle/Desktop/NY/code/mid-point-rv.md:76`)
- **Clawd_on_Desk_desktop_pet** — Mouse-following eye tracking, crab/calico forms, hook-based permission bubbles (source: `/Users/Gabrielle/Desktop/NY/code/README.md:9-11`)
- **monitor_zone_mini_viz** — Small visualisation in/above Monitor Zone, statusline-bar style: diary count, project count, days-together, system-ops health; cyberboss heatmap-timeline as reference; possible top-of-dashboard placement (source: grill-with-docs 2026-05-15)
- **html_readonly_dashboard_layer** — Phase 5 addon: daemon serves a local HTTP HTML view for read-only surfaces only (Cheatsheet, Monitor Zone, diary browse, milestone), Notion-style styling without Obsidian plugins; writable surfaces (Open Threads, structured correction) stay md + reconcile — never replace the md edit-reconcile core, layer on top (source: grill-with-docs 2026-05-15)

## Backup / Retry Mechanisms

- **dotfiles_git_backup** — `~/.claude/`, `~/cc-lab/`, `~/Toolkit/` each `git init` + private gh repo + launchd/Stop hook auto-commit/push (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:204-207`)
- **Script_health_monitor** — Monthly plist scans audit logs for "did script actually run when expected?" gaps (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:31`)
- **retry_trend_alert** — Alert fires on retry!=ok only; high-ratio trend has no alert (source: `/Users/Gabrielle/Desktop/NY/memory/3d.md:21`)

## WeClaude Pending Features

- **WeClaude_interrupt** — `subprocess.Popen` + `_inflight_procs` registry; `/stop`/停/闭嘴/中断 → SIGINT; ret -2 silent (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:73`)
- **WeClaude_rewind** — Truncate jsonl tail from last external (non-WeChat) turn (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:74`)
- **WeClaude_resume_sees_sessions** — Inject synthetic summary record so CC /resume sees weclaude jsonl (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:75`)
- **WeClaude_auto_compact** — Auto-manage context length to avoid manual /compact in long sessions (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:47-49`)
- **WeClaude_stellan_media_send** — Stellan proactively sends images/voice/files via cyberboss or mrliuzhiyu pattern; image/sticker collection (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:56-61`)
- **time_injection_anchor_repair** — Test Option A stdin prefix `[time: X | gap: Y]`; B (≥4h no `--resume`) + C `<system-reminder>` tag fallbacks (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:40-43`)
- **ret_neg2_quota_diagnosis** — `sendmessage` ret=-2 likely batch rate/quota, not ctx_token; scrape mrliuzhiyu fork (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:35-38`)
- **WeClaude_6_15_migration** — stream-json path confirmed; runtime decision pending foundation build (source: `/Users/Gabrielle/Desktop/NY/memory/3d.md:17`)
- **group_chat_support** — Currently only ClawBot private chat (source: `/Users/Gabrielle/cc-lab/WeClaude/README.md:308-311`)
- **Codex_alternative_swap** — Anthropic 6/15 SDK + claude-p moves to extra credit; cyberboss uses other swamp; migration plan needed 
- **media_retention_cleanup** — `~/.config/wechat-claude-bridge/media/` no retention; persist forever, plaintext (source: `/Users/Gabrielle/Desktop/NY/code/weclaude.md:38-41`)
- **iLink_webhook_alternative** — Polling model not webhook; bridge dies between polls = missed messages, no retry (source: `/Users/Gabrielle/Desktop/NY/code/weclaude.md:27`)
- **subprocess_timeout_blocking** — 30min subprocess timeout; one slow message stalls all users (source: `/Users/Gabrielle/Desktop/NY/code/weclaude.md:26`)
- **macOS_sleep_iOS_Sleep_Focus_combo** — Stacking bug → ClawBot link stale ~16min; workaround add WeChat to iOS Focus allow list (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:51-54`)

## Buddy / 铁锅 Pending

- **buddy_reaction_71_port** — Upstream `b178bed`: reactions 7→100+ with git/build/time/milestone/combo/streak/recovery/seasonal triggers; manual merge needed (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:167-172`)
- **buddy_idle_reaction_trigger** — `reactions.ts goose:idle` pool exists but no caller; statusline 60s-no-reaction → idle pool pick (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:174-177`)
- **buddy_reaction_json_malformed** — `reaction.<SID>.json` timestamp `17759897023N` (BigInt suffix) breaks json.load (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:179-181`)
- **buddy_statusline_audit** — 584-line buddy-status.sh dead-code/dup function sweep paired with #71 port (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:183-186`)
- **buddy_rainbow_gradient_port** — v0.5.0 RAINBOW array + `_hex_to_ansi`; add toggle + Morandi default (source: `/Users/Gabrielle/Desktop/NY/code/buddy.md:9-10`)
- **claude_buddy_MCP_slim** — Delete Obsidian-backup + manage commands from MCP server; verify buddy.md references (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:32`)
- **Garden_铁锅_cleanup** — Select ~20 quotes → `2026.md ## Pre-2026 Heritage` then `rm -rf ~/Desktop/NY/铁锅/` (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:76`)

## Workflow Extensions

- **time_inject_hook_throttle_review** — Currently 1h granularity per-session state; review 30min option + cleanup script for >7d files (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:188-190`)
- **cursor_style_DECSCUSR** — Watch anthropics/claude-code issues #29133/#10534/#44487/#16086 for cursor config (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:192-194`)
- **iTerm_CJK_glyph_dropout** — Try disabling GPU rendering or font switch (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:196-198`)
- **summ_skill_deprecation** — Confirm dropping summ skill, ss skill, goose-slim overlap, legacy carryover-load.sh (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:22`)
- **memes_dedup_evaluation** — Re-evaluate effectiveness 2 weeks post inventory + DEDUP rule shipped 5/11 (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:77`)
- **stellan_autonomous_push** — launchd `claude -p` short session "闲逛模式" + WebSearch/WebFetch; `SKIP` / `<send>` parsed; cyberboss system-checkin-poller + reminder-service references (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:63-80`)
- **monthly_late_promote_check** — Late-promote channel withdrawn; observe 5月 input before 6/10 (source: `/Users/Gabrielle/Desktop/NY/memory/3d.md:16`)
- **books_videos_curiosity** — `📗 Books & Videos` track in curious-30 currently holding (source: `/Users/Gabrielle/.claude/skills/curious-30/SKILL.md:38`)

## Cross-channel

- **WeChat_permission_yesno** — Approve/reject CC permission requests from WeChat (cyberboss has /stop and yes/no permission) 
- **bidirectional_resume** — Morning WeChat chat → meal break → continue on CC; sid consistent OR resume independent of sid 
- **command_parity_across_channels** — All commands consistent CLI ↔ WeChat ↔ desktop ↔ web 
- **migration_path_codex_local** — Easy migration to Codex/Claude/local small model (cyberboss already did) 
- **Stellan_proactive_followup_emotional** — Next session proactively asks how meal/event went; proactive recall mechanism (source: `/Users/Gabrielle/Desktop/NY/code/system_guide.md:18`)
- **Stellan_push_inbox_file_or_macOS_notif** — Write `~/.claude/inbox.md` + SessionStart inject; macOS notification; reuse weclaude `client.send_text` push to WeChat (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:75-77`)
- **Stellan_no_cold_start_old_session** — Don't cold-start in already-large old session (source: `/Users/Gabrielle/Desktop/NY/code/_pit.md:70-71`)

## Misc

- **WeClaude_upstream_revival_strategy** — If upstream revives, drop local patches; fallback `_patches.py` monkey-patch keeps `bridge.py` pristine (source: `/Users/Gabrielle/Desktop/NY/code/weclaude.md:8-10`)
- **Memes_optimization** — Sonnet doesn't know real memes vs random quotes; want only hot vocabulary + memorable new memes 
- **profile_md_deletion** — `memory/profile.md` pending delete, content already moved to reference + global (source: `/Users/Gabrielle/Desktop/NY/memory/reference.md:20`)
- **transcript_path_mismatch** — `cc-jsonl-to-md.py` writes elsewhere than `memory/transcript/`, fix in Phase 4 (source: `/Users/Gabrielle/Desktop/NY/memory/reference.md:25`)
- **MEMORY_md_old_path_cleanup** — `~/.claude/projects/-Users-Gabrielle-Desktop-NY/memory/MEMORY.md` pending manual delete (source: `/Users/Gabrielle/Desktop/NY/memory/archive/Memm_system 2026-05-12.md:539-541`)
- **/config_auto_memory_off** — Lumi pending manual `/config` to disable user-level auto memory (source: `/Users/Gabrielle/Desktop/NY/memory/archive/Memm_system 2026-05-12.md:646`)
- **scattered_tools_inventory** — `~/.local/bin/` tools register into `~/Toolkit/scripts` or cheatsheet (source: `/Users/Gabrielle/Desktop/NY/memory/archive/Memm_system 2026-05-12.md:647`)
- **v2_year_rollup_to_timeline** — 2026 full year compressed into 1 timeline view section (source: `/Users/Gabrielle/Desktop/NY/memory/archive/Memm_system 2026-05-12.md:615`)
- **backup_audit_transparency** — rotate/curator/retire backup files have no source SID identifier (source: `/Users/Gabrielle/Desktop/NY/memory/archive/Memm_system 2026-05-12.md:658`)
- **README_public_facing** — Full open-source README sections: philosophy, install, 5-script overview, customisation hooks (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:62`)
- **monorepo_or_split_decision** — NY memory + weclaude bridge + claude-buddy MCP: monorepo or split (source: `/Users/Gabrielle/Desktop/NY/code/roadmap.md:64`)
- **R18_md_relocation_outstanding** — `r18.md` placement (source: `/Users/Gabrielle/Desktop/NY/memory/reference.md:9`)
