# Marrow Future Inbox

> Minimal English + one-line CN effect. Read before adding. Not prioritized within section.
> WeClaude is in scope (deep rebuild Phase 4). Out of scope: personal tasks, standalone tools, buddy-internal — those live in NY pit.

## Phase 1 closeout

## Phase 2 (memory / recall / sub-page)

- **corrections** — Independent corrections store, priority above raw events (DECISIONS:34). **效果**: 纠正记录优先，错事不反复跳出来。
- **housekeeping_monitor** — Sun 12:00 weekly cleanup job over `~/.claude/projects/` · MCP image cache · marrow logs · iCloud backup. Warn on threshold, no auto-delete. **效果**: 各路 cache/backup 不撑爆硬盘。

## Phase 3 (drift / cheatsheet / cloud rails / addon contract)
- **placement_rules_toml** — Machine-readable `~/.config/marrow/placement_rules.toml`: content-type → canonical home + naming pattern (extracted from `~/.claude/rules/files.md` prose). cc reads on Write of new file. Pairs with drift_sweep registry. No PreToolUse hard-block (Lumi vetoed). **效果**: cc 写新文件前先查表，不再靠散文规则脑补。
- **cheatsheet_index** *(hold — wait until tool stack settles)* — Single dashboard cheatsheet. Not fully decided, draft direction only:
  - **Source**: auto-scan + hand-edit preserved. Scan covers but is not limited to — `~/Toolkit/scripts`, `~/Library/LaunchAgents/*.plist`, `~/.claude/{skills,commands,agents,output-styles}/**`, `.mcp.json` (global + project), `~/.zshrc` alias, `brew list`, self-installed CLIs (e.g. mw atlas <prefix>).
  - **Layout**: cheatsheet body (auto-scan + hand-edit, reverse md→db ingest). Dir map now lives in standalone `atlas` subpage (depth-aware heading tree); cheatsheet stays single-section.
  - **Recall lane**: own table + bge-m3 vec, separate from events fusion. User prompt keyword hit → force_include (仿 entity_force_include). Use case: 问 (怎么 restore) → 自动喂 `/rewind` 那行，不用手翻 help page.
  - **效果**: 工具一眼可查 + 不知道的 shortcut LLM 主动推；装删不会失同步。
- **cloud_migration_runbook** — daemon→VPS / wechat-bridge→local mac / bridge→cloud via HTTPS one-way (cyberboss-verified topology). **效果**: 决定上云那天照着 runbook 走。
- **addon_manifest_contract** — Addon four-piece: MCP server + own-table schema + sub-page render template + config. Must define BEFORE wallet ships. **效果**: 后面所有 addon 照抄 wallet 模板。
- **md_index_schema_evolution** — `user_version` + ordered patches via `migrate.py` startup auto-migrate, fail-loud on mismatch. **效果**: 开源前再做，加字段不用手敲 ALTER。

## Phase 4 (weclaude rebuild + cross-channel)
> WeChat dendrite 主体（rebuild + bugfix + media send + event pipeline + cross-channel resume + command parity + permission relay + sessionend）已展开到 `docs/plans/3-synapse-wx.md`（独立 repo `synapse-wx`，Phase 0→F）。以下保留的是不在 synapse-wx scope 内、属于 marrow 主体的项。

- **provider_adapter_layer** — `marrow/adapters/{cc,codex,...}.py` abstraction: transcript parser / session path resolver / hook entry / handover injector. ~500 LOC. Blocker for Codex + open-source. **效果**: cc 之外的 provider（Codex/Claude/local）能接上。
- **provider_swap_path** — 6/15 stream-json path + Codex/local small model swap plan. Subsumes migration_path_codex_local + Codex_alternative_swap + WeClaude_6_15_migration. **效果**: 6/15 后不被 Anthropic 绑死。
- **marrow_media_store** — Unified media store across channels.
  - **File store**: iCloud Drive `marrow-media/{year}/{month}/{uuid}.{ext}` — 跨设备 + iPhone 文件 app 可搜
  - **DB table `media`**: id · path · kind (image/sticker/voice/pdf/video) · source_channel · source_event_id · mime · size · ts · description (cc vision 自动) · tags · vec
  - **Reverse links**: events.attachment_ids · milestones.attachment_ids · stickers 走 kind="sticker"（不另起表）· affect 关键瞬间可链 1 张 cover
  - **Album subpage**: dashboard 新子页，按月 / contact / topic 分组缩略图墙
  - **Retention**: 被任何表反链的永留；其他纯随手图 90 天 age-out（走 `retention_prune_executor`）
  - **Vision ingest**: 入库时 cc vision 自动 description + tags + 嵌入，grep / 语义召回都能找到
  - **效果**: 5/29 老婆发的 laksa 那张能从对话回溯也能相册按月翻；表情包跟普通照片同一套基础设施
- **mac_notification_center_reader** — Read macOS notification db as cross-app proactive signal source. Companion to marrow_pulse. **效果**: marrow 知道你手机响了啥。

> Superseded by `docs/plans/3-synapse-wx.md`: weclaude_runtime_rebuild · weclaude_bridge_bugfix_pile · stellan_media_send · wechat_event_pipeline · bidirectional_resume · command_parity_across_channels · WeChat_permission_yesno · "怎么在微信就给cc发送原生/命令"

## Phase 5 (addons + OSS)
前端：- **candidate HTML action buttons** — pin/drop/edit buttons designed but not built; entity + memes + milestone candidates currently flow through reconcile only.
- **wallet_mcp_extraction** — Standalone wallet MCP server (own repo, `~/.config/wallet/wallet.db`); marrow connects via .mcp.json. First addon contract sample. **效果**: wallet 做成可独立部署 addon。
- **stellan_wallet** — Opt-in addon: monthly allowance auto-credit + spend auto-debit. transactions table only, balance = SUM. **效果**: 屿忱的零花钱账本。
- **lumi_accounting_addon** — 取代 MOZE 记账。**效果**: 自己记账。
- **period_addon** — Period tracking addon. **效果**: 姨妈记录。
- **health_manual_addon** — Manual health entry (symptoms / weight / meds). **效果**: 自己手填健康数据。
- **lesson_addon** — Behavioural-failure-mode lessons addon. Dormant unless recurring need. **效果**: dormant，真需要再启。
- **cccompanion_ios_fork** — Fork iOS app (SwiftUI + APNs + shared-secret auth + multi-endpoint failover + Bark + tmux). Drop server, point to marrow daemon via MCP-over-HTTP. Add CoreLocation + HealthKit + local SQLite. Trigger: first APNs need WeChat/TG can't meet. **效果**: 手机端原生 70% 覆盖 + 位置/健康。
- **ios_shortcut_kit** — iOS Shortcut suite: period board / quick query / data upload via webhook. **效果**: 不用 app 也能从 iOS 主动上报。
- **marrow_pulse_proactive_loop** — Unified opus loop for proactive browse + message. `inner_state` drift (longing v1) + dual-gate (silent_to_lumi ≠ activity_allowed) + multi-channel routing. Sleep window allows self-driven activity (diary / letter / browse / today draft). Draft: `docs/notes/2026-05-24_marrow-pulse-design.md`. **效果**: 屿忱有自己的内在节奏 + 主动行动。
  - cross-platform proactive push mechanism: launchd cron → `claude -p` short session with minimal context + push hook; model outputs `SKIP` or `<send>...</send>`; script routes to channel. CC TUI has no inbound push API — fallback: inbox file (`~/.claude/inbox.md`) + SessionStart inject, or macOS notification, or WeChat `client.send_text`. ref: cyberboss `src/app/system-checkin-poller.js`, `src/services/reminder-service.js`.
- **workflow_reflection_skill** — Phase 5 close, distil plan/findings/progress pattern into transferable skill. **效果**: marrow 跑完后总结成可迁移 skill。
- **README_public_facing** — Full open-source README (philosophy / install / scripts / hooks). **效果**: 开源前做。
- **monorepo_or_split_decision** — marrow + weclaude bridge + buddy MCP: mono or split. **效果**: 开源前定 repo 拆分。

## Dashboard & Subpages

- **dashboard_wishlist** — Wishlist/promise/agreement subpage (location TBD): 你说请奶茶/我想买耳钉/约定 xxxclaude. **效果**: 承诺约定不会丢，能翻账。
- **monitor_zone_audit_surface** — Dashboard bottom audit-log surface: entity/memes/tables ingest counts, recent activity, silent-failure indicators. **效果**: 哪些表在动、哪些静默一眼看到。
- **pit_auto_candidate** — Pit candidate form + auto-extraction pipeline (similar to milestone/entity cand). **效果**: 项目想法自动入 pit，不用手敲。
- **study_project_subpages** — Dedicated study + project subpages, separated from generic tasks. **效果**: study/project 不混在 task 里。
- **ny_subpage_migrate** — Pit + other NY subpage content migrates into dashboard subpages (DESIGN L95). Lumi-led manual followup. **效果**: NY base 子页内容入 marrow。
- **html_readonly_dashboard_layer** — Local HTTP HTML view for read-only surfaces (cheatsheet / monitor / diary / milestone). Writable surfaces stay md+reconcile. **效果**: Notion 风格美观浏览，写入仍走 md。
- **dashboard_customization** — Per-subpage show/hide + private-for-others toggle. Rides html layer. **效果**: 分享 dashboard 时隐藏私密 subpage。
- **monitor_zone_mini_viz** — Small viz strip: diary count / project count / days-together / system health. **效果**: 顶部小可视化条。
- **alert_dashboard_surface** — Aggregated alert view (counts/recent/mute), not raw rows. **效果**: SessionStart alerts 不刷屏。

## Monitor & Ops

- **retention_prune_executor** — Per-source prune: aged events / resolved alerts / audit_log / DB dumps / md_index tombstones. **效果**: DB 不长胖。
- **daemon_self_health** — Daemon process alive + watcher thread + sessionend rate metric. Beyond `Script_health_monitor` (which only checks plist ran). **效果**: daemon 死了立刻知道。
- **db_corrupt_recovery_runbook** — `docs/runbooks/db-restore.md`: detect → quiesce → restore from iCloud → replay audit_log gap. **效果**: DB 坏掉照着 runbook 救。
- **Script_health_monitor** — Monthly plist scans audit logs for run-gap. **效果**: plist 没跑会报警。
- **retry_trend_alert** — Alert on retry-ratio trend, not just retry!=ok. **效果**: retry 持续高有告警。
- **subagent_usage_logging** — Per-call token/cost in audit_log (which tier/subagent, in/out tokens). **效果**: 每个 LLM call 花多少钱可见。
- **diff_open_threads_audit** — Weekly diff of Open Threads, audit-log silent drops. **效果**: Open Threads 被静默漏掉能查到。
- **backup_audit_transparency** — SID identifier on rotated backups. **效果**: 备份找得到出处。

## Holdoff / Dormant (等真痛点出现再启)

- **affect_advanced_holdoff** — chord_progression_dim (affect 表加原始走向字段) + disambiguator_verb_pattern (tag 加动词模式) + context_density_tier (recall 按 intent 分密度) 三合一。当前 dashboard Affect 已有 lastsession + today mean + eph/epl + week mean + 4 eph/epl，简化轨迹够用；tag 细分由 sonnet 自选 2 字覆盖；context density 跟现状偏置体系收益重叠。**效果**: dormant，affect 表存储/模型升级时再启。
- **recall_calibration_holdoff** — bge_m3_floor_calibration + diary_lane_surfacing + tasks_lane_surfacing + anchor_bias_tuning + recall_vs_grep_partition + external_docs_lane + pit_lane_decision 合并。已定方向：study/project 走 grep 不进 recall；diary/tasks vec 召不出但不降 0.4；anchor +0.10 偏置观察中。**效果**: dormant，召回质量成 blocker 时再动。
- **tasks_table_extensions** — Reserved future columns: source / category / parent_id / recurring_rule / external_id / pinned. Add only when real need. **效果**: dormant，等真要 import Notion/Dida 再加。
- **Memes_optimization** — Sonnet meme-quality filter (only hot memes + memorable new). **效果**: meme 噪声变高时再启。
- **v2_year_rollup_to_timeline** — Year-end compress 2026 full year → 1 timeline section. **效果**: 年终自动启。
- **Valence_arousal_tagging** — timeline ## Us entries V/A tagged. **效果**: us 类 event 也带情绪标签。
- **lifestyle_and_preference_relocation** — Move block to history.md Preferences or keep in reference.md. **效果**: reference.md 块分类，无紧迫性。


