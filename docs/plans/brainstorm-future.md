# Marrow Brainstorm — 2026-05-23 凌晨

> 场景：Phase 2.5 主线推倒重来后的窗口，趁框架空白整未来功能。
> 参考料：和弦情绪.md · claude-imprint · cybersealnull/cccompanion
> 这份是 brainstorm scratch，不是 ADR。Phase 2.5 收尾后再筛进 DESIGN / DECISIONS / FUTURE。

---

## 1. addon 契约 — 决定未来一切扩展的形状

**结论：addon 内容不必预想，契约必须现在定。**

四件套（每个 addon 必须 declare 的东西）：
- MCP server — 接入协议（imprint 已验证轻量路线）
- table schema — 自带表，住 marrow.db 或独立 db
- sub-page render template — 一张表 → 一个 view
- config — 开关、私密标记、是否对外隐藏

落点：
- wallet 抽成独立 MCP，第一个真实样本（FUTURE: `wallet_mcp_extraction`）
- 抽完后 stellan_wallet / lumi_accounting / 未来任何 addon 全部照抄
- 不要硬造 plugin spec，让 MCP 协议 = manifest

---

## 3. 多端入口路径（按时间分档）

短期（现在 → Phase 4 收尾）：
- A. dashboard.md 多端同步（iCloud / Obsidian）覆盖 60% 日常
- B. 微信 + TG 当手机入口（weclaude 重构在 Phase 4）
- 工程量几乎为 0，已具备

中期（Phase 5 addons）：
- C. iOS Shortcut 套件（FUTURE 待加：`ios_shortcut_kit`）
  - shortcut 是 iOS 唯一对外开放的 location 入口（主动上报）
  - 姨妈板块、快捷查询、数据上报都走 shortcut webhook → marrow daemon
  - 性价比最高的一档

长期（Marrow 成熟后半年到一年）：
- D. iOS 原生 app（FUTURE: `cccompanion_ios_fork`）
  - 解锁：HealthKit 全套 / CoreLocation 后台 / APNs 自控 / ScreenTime 日汇总
  - 触发时机：第一次想要 APNs 推送，且微信/TG 替代不了
  - 不要预期性建设

---

## 5. 主动消息发哪里 — active device routing

机制：
- daemon 维护 `last_active_channel`（cli / wechat / ios），按最近一条 user input 来源
- 主动消息按当前 active 单端推送，不双发：
  - cli active → macOS notification + dashboard 红点
  - wechat active → 微信
  - 都没活动 > 30min → APNs 弹手机（有 iOS app 时）
- 短期没 app：cli active → macOS notify；其余 → 微信

---

## 6. cccompanion fork 策略

可以偷的（解决 60% iOS 工作量）：
- SwiftUI + APNs/UNUserNotificationCenter 接入（AppDelegate.swift）
- Shared-secret token 鉴权（比 OAuth 简单一万倍）
- 多 endpoint 自动 failover（Tailscale / LAN / localhost）
- Bark fallback（没 Apple Developer 账号也能推，开发期用）

要扔的：
- 服务端怪兽（100+ endpoints 全塞一起）→ marrow daemon 自己来
- 纯 stateless 拉服务端 → marrow 必须加本地 SQLite 缓存（弱网/飞行模式）
- 没有 location / health → 自己加 CoreLocation + HealthKit

---

## 7. 上云路径（mac mini → VPS）

迁移成本分级：
- 本地 → mac mini：低（rsync + 装 cc + 改 launchd 路径）
- mac mini → VPS：中（cc OAuth headless / launchd → systemd / 微信桥留哪儿）

干净拓扑：
- marrow daemon 上云
- 微信桥（iLink polling）留本地 mac（必须挂 WeChat 进程）
- 本地桥 → 云 daemon 走 HTTPS/socket 单向调用
- 这是 cyberboss 已验证的形态

要做的准备（Phase 3 drift_sweep 时顺手）：
- 所有平台/路径硬编码集中到 `paths.toml` registry
- 换机器 = 改一个文件

"黑不黑"：自己 VPS + SSH key + API key 走环境变量 + SQLite WAL 加密可选，没有比这更黑的可能。

---

## 8. 借和弦的三个东西（Phase 2 affect 模块扩展）

- `chord_progression_dim` — affect 表加 chord_line 字符串字段，存而不解，留给未来模型解码。捕捉 V/A 标量丢失的方向性微弧
- `disambiguator_verb_pattern` — 紧张 → (盯/压/憋/狂)，便宜的歧义补丁，不扩 tag 词表
- `context_density_tier` — recall 按 query intent 选三档：chord-only (region) / +scene (sub-tone) / +paragraph (sentence)

---

## 9. 借 imprint 的几个东西（已知，确认借）

- RRF + 置信度门控（K=60，per-pool high/low/interpolated）
- FTS5 + jieba CJK 分词 + WAL
- multimodal embedding 抽象（vendor swap by config）
- recall 自动注入（`<recall>` block）
- markdown bank + chunking
- heartbeat daemon + MCP 调 claude CLI（cron 推送的源头模式）

避坑：
- 不要时间衰减（imprint 故意禁用，老料保留可找）
- 不要 schema 假定单机（marrow 已规避）

---

## 10. FUTURE 整理动作（Phase 2.5 收尾后做，独立 session 半小时）

- Phase 4 拆三个子组：4a weclaude runtime / 4b cross-channel / 4c stellan proactive
- Phase 5 拆两组：5a addons / 5b dashboard polish
- 每条加横切 tag：`[schema]` / `[pipeline]` / `[surface]` / `[addon]` / `[infra]`
- 补未写入的 item（部分今晚已加，剩余待加）：
  - ✅ `wallet_mcp_extraction`（已写）
  - ✅ `lumi_accounting_addon`（已写）
  - ✅ `cccompanion_ios_fork`（已写）
  - ⏳ `addon_manifest_contract`（Phase 2/3，wallet 前必须先定）
  - ⏳ `cloud_migration_runbook`（Phase 3+ 配 drift_sweep）
  - ⏳ `ios_shortcut_kit`（Phase 5 addon）
  - ⏳ `period_addon` / `health_manual_addon`（Phase 5 addon）
  - ⏳ `chord_progression_dim`（Phase 2 affect 扩展）
  - ⏳ `disambiguator_verb_pattern`（Phase 2 affect）
  - ⏳ `context_density_tier`（Phase 2 recall）
  - ⏳ `active_device_routing`（Phase 4 stellan proactive 配套）
  - ⏳ `mac_notification_center_reader`（mac 曲线捕捉通知流，Phase 4/5）

---

## 引用源

- `/Users/Gabrielle/Desktop/和弦情绪.md` (302 lines)
- github.com/Qizhan7/claude-imprint
- github.com/Qizhan7/imprint-memory
- github.com/CyberSealNull/CcCompanion（已 star，Reference list 待 web 拖）
- github.com/P0luz/Ombre-Brain（FUTURE 已引）
- github.com/WenXiaoWendy/cyberboss（FUTURE 已引）
