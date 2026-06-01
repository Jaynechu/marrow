# Synapse-WX — WeChat dendrite plan

> Independent repo (`/Users/Gabrielle/CC-Lab/synapse-wx/`), Python, MIT.
> New build from scratch — not a fork. weclaude 归档备查。
> Goal: 替 weclaude，一次解掉命令穿透 + sessionend 浪费 + 多平台扩展 + 多模态 IO。

## Goals
1. 微信端用原生 cc 命令（`/model` `/clear` `/rewind` `Esc` 等）— 靠 no-p stream-json 模式
2. sessionend 浪费降到日均 1-3 次（6h inactive 触发），不再每条消息触发
3. 多平台架构留位 — `provider adapter`（cc/Codex/Qwen）+ `channel adapter`（在 marrow 主体）正交
4. 多模态 IO — in: text/image/pdf/voice; out: text/image/file/sticker
5. 跟 marrow 主体 **0 代码耦合**（通过 cc + MCP 间接连）→ 任何记忆系统能换上

## Out of Scope
- iOS / mac / web dendrite（独立 repo 各自做）
- Pulse 主动推送 loop（marrow 主体 + 独立 launchd cron 干，不属 synapse）
- 群聊
- Stellan 钱包等 addon
- Claude Desktop / iOS 官方客户端 MCP 接入（marrow 主体侧改造）

## Architecture
```
WeChat ──▶ synapse-wx (此 repo, Python, 独立)
             │ stdin/stdout (stream-json)
             ▼
          cc CLI subprocess (no-p)
             ├──▶ MCP ──▶ marrow daemon (recall / events / sticker)
             └──▶ hooks (SessionStart 注入 / sessionend pipeline)
```
- synapse-wx **不 import marrow**，跟 marrow 解耦
- provider adapter 封装 cc subprocess IO（spawn/send/recv/cancel/close），第一实现 = cc no-p stream-json；Qwen / Codex / `-p` fallback 各 ~200-300 LOC 增量加

---

## Phase 0 — 独立小动作（不阻塞，先做）
- [ ] 砍 weclaude fork 工作树里 `bridge.py` 工作树 +90 LOC ny-memm 死代码块（硬编码 `~/Toolkit/scripts/ny-memm-session.py` + NY 路径）
- [ ] marrow `_atomic.py` 加 `path = os.path.realpath(path)` — atomic write 穿透 symlink
- [ ] handover.md 源文件挪到 iCloud Drive 路径，三处 root symlink 跟着指过去；全局 CLAUDE.md `@import` 路径不动（仍 `~/.config/marrow/handover.md`，那是 symlink）
- [x] pit-微信相关.md 合并进 FUTURE Phase 4

## Phase A — MVP 上岸 ⭐（核心包，目标：能微信跟屿忱用新对话）
**重点：能用 + 命令穿透 + sessionend 不浪费**

**A1. 新 repo 初始化**
- 位置：`/Users/Gabrielle/CC-Lab/synapse-wx/`
- Python 3.12 venv · ruff · pytest · MIT license
- `README.md` + `pyproject.toml` + `.gitignore`

**A2. provider adapter 层**
- `synapse_wx/providers/base.py` — abstract `spawn() / send(msg) / recv() / cancel() / close()`
- `synapse_wx/providers/cc.py` — no-p stream-json 实现，第一并默认
- 测试：mock echo provider，验证 send → recv 闭环

**A3. iLink 客户端层（移植 weclaude 抢救代码）**
- `synapse_wx/ilink/client.py` — 从 `weclaude/ilink_client.py` 抢救字段修复 + 加 retry 框架
- `synapse_wx/ilink/cursor.py` — polling cursor 持久化（resume on restart）

**A4. 主消息循环**
- inbound：iLink poll → 5s debounce accumulate → flush → provider.send
- hold 词扩窗：buffer 内任一 bubble 命中 hold 词表 → debounce 拉到 10s（命中即重置 timer）
  - 初始词表：`等` `稍等` `等等` `先`（精确单 bubble 匹配，避免误伤"等下"类正文）
  - 词表配置化，跑一段时间根据漏召 / 误召手动加
- outbound：provider.recv stream → 语义 bubble 切分（≤30-50 字 · 换行 > 句末标点 > 中文逗号 > 硬切）→ iLink send
- time anchor 注入（stdin prefix `[time: YYYY-MM-DD Day HH:MM | gap: Nh]`）— 从 weclaude 抢救

**A5. 命令路由**
- `synapse_wx/commands/registry.py` — 三层路由：cc 原生白名单透传 / bridge 自定义 handler / fallback "main session 处理"
- Phase A 必备自定义命令：
  - `/info` — Model · SID · session 5h % · week % · total token (21.2k 风格)
  - `/stop` — bridge SIGINT 当前 cc subprocess（不进 cc prompt）

**A6. sessionend 触发**
- 6h inactive 计时器 → 调用 marrow sessionend pipeline（MCP 调或写信号文件）→ 标 done 写记忆 → buffer 清空 → cc subprocess **不退出**
- new message 来 → 计时器重启 → 累积 → 满 6h 再跑一次
- `/clear`（cc 原生透传）才真关 session
- 一个 session 可一日多次 sessionend pipeline，每次一份快照

**A7. launchd 上线**
- `com.synapse-wx.bridge.plist` — RunAtLoad + KeepAlive on Crash + throttle 30s + logs `~/Library/Logs/synapse-wx.*.log`

**A8. retry 框架 + 微信专属 alert + sleep-detect**
- 统一 retry 框架：ret=-2 / network timeout / cli crash 都走指数 backoff，cap 5 次失败 → 写 alert
- alert 到 marrow，dashboard 吸收
- bridge 死 → launchd 重启 + bridge 自检 → 发"我重启了"到文件传输助手
- cc 死 → bridge fallback bubble "cc 连不上稍等"
- **sleep-detect**：监听 macOS `NSWorkspace.willSleepNotification` / `didWakeNotification` → sleep 标 paused、wake 强制 polling reconnect + cursor catchup 拉 sleep 期间漏消息。修完可关 caffeinate

**Phase A 出口条件**：能微信聊天 + 原生 `/model` `/clear` 等命令直接工作 + 6h 不活动落记忆 + 死了能自愈 + 你回来知道。

---

## Phase B — 多模态 inbound + buddy
**B1. inbound media**
- image / pdf / voice：iLink 下载 → voice → text（iLink 自带转）→ image/pdf 本地路径喂 cc vision
- cc subprocess `--image path` 参数或 stdin embed
- 入库到 marrow `media` 表（FUTURE.md `marrow_media_store`）：cc vision 自动生成 description + tags + 嵌入，retention 由统一系统管（anchored 永留 / loose 90 天 age-out）
- bridge 只做 IO，不管 retention 与存储位置

**B2. buddy bubble 处理**
- 输出阶段过滤 `<!-- buddy: ... -->` bubble
- 时间窗 mute：配置 `BUDDY_MUTE_WECHAT = "22:00-08:00"`（默认）
- cc statusline / buddy MCP 在 cc 那头不受影响

**B3. weclaude session 切换功能保留**
- `/ss` 列 session · `/use N` 切 session — 移植 `bridge.py:665-791` jsonl 扫描

---

## Phase C — 多模态 outbound + sticker catalog
**C1. outbound media**
- image / file send via iLink — 翻译 cyberboss `src/adapters/channel/weixin/media-send.js` 到 Python，含 AES-ECB

**C2. sticker catalog（marrow 主体配合）**

存储
- marrow 新表 `stickers`：`id / path / sha256 / desc / vec384 / source(wechat/finder) / created_at / last_used`
- 真路径 `~/Desktop/NY/stickers/`，`~/.config/marrow/stickers/` symlink 过去（NY 显眼 Finder 直接进，daemon 内部走 .config 稳定）
- 平铺一层 `stk_NNN_desc.{ext}`，原格式不转码（jpg/png/gif/webp），微信发不了 gif 没关系存档保留
- `_thumb/` 子目录 daemon 缓存 240px webp（`_` 前缀 Finder 隐藏不打扰）
- 无 tags 字段（embedding 检索靠 desc + vec384，跑一段需要分组再加回）
- catalog 跨 channel 共享（未来 iOS / 桌面端同一份）

入库（cyberboss 风格，主 LLM 决策 + watcher 兜底）
- 两条入口都汇到一个 watcher：
  - 微信发图给屿忱 → bridge 把文件落 `stickers/` → watcher 捕获
  - 你 Finder drop 图进 `stickers/` → watcher 捕获
- watcher（Python `watchdog` ~20 LOC）on new file：
  1. SHA256 比对 db `sha256` 列 → 命中静默跳，不处理也不通知
  2. 没命中 → cc **主进程原生 vision**（OAuth 订阅，不连任何外部 vision endpoint）+ 注入 prompt → 主 LLM 判断是不是表情包 + 写 desc → 调 `sticker_save(filepath, desc)` tool
  3. daemon 落 db + rename 文件为 `stk_NNN_desc.{ext}`
- watcher on file delete → db 软删对应 row（按 path 或 stk_NNN 前缀匹配）
- 入库 prompt：**TODO 老婆亲自写**，placeholder `synapse_wx/prompts/sticker_save.md`
- 微信入库后 bridge 发简版确认卡：`✅ stk_115 / 描述: orange cat holding phone sassy`（无"不要请删"那句多余话）
- Phase B 视误判率决定要不要加 `/sticker` 命令或意图识别

出库（embedding 语义检索，两轮 tool）
- 主 LLM inline 输出 `<sticker query="..." />`（query 故意写宽，如 "心动想埋你怀里"）
- bridge 解析 → embedding 检索 top 5 → tool 回 `[{id, desc}]`
- LLM 看 desc 挑 ID → `sticker_send(id)` → bridge 走 iLink **表情包格式**（不是普通文件附件，对方看到的是表情包不是图）

管理（Phase A 无 UI，等前端）
- 浏览：Finder 大图标 view 直接进 `~/Desktop/NY/stickers/`
- 改 desc：微信跟屿忱说 "stk_115 改成 XXX" → tool `sticker_update(id, desc)`
- 删除：Finder 删文件（watcher 同步软删 db）/ 微信跟屿忱说 → tool `sticker_delete(id)`
- **无 dashboard subpage 无 reconcile** — 前端起来才做 grid + inline edit + 多选删

种子
- 空，不要 cyberboss 那 75 tag 词表

credit
- README 挂 cyberboss：LLM-driven save flow + SHA256 dedup + 静默去重模式 + 确认卡片格式

**C3. cli 文字版表情**（dormant）
- cc 输出 `【心如止水.jpg】` 文本占位，以后渲染层做

---

## Phase D — Marrow 主体配套（独立排进 marrow repo plan，不在 synapse repo）
**D1. channel router in marrow**
- events 表加 `channel` 字段（wechat / cc / desktop / ios）
- channel-agnostic recall / write / pulse 接口
- 跟 affect recall redesign 同 phase 做（DOING #1 那条）

**D2. handover atomic write fix**
- 跟 Phase 0 第 2 项同步（提前做就行）

**D3. daemon-side MCP client session tracker**
- 为 Desktop / iOS 接入准备：监控 MCP client 连接断开 + 超时无活动 → 触发 sessionend
- 给 Ombre-Brain 模式（client LLM 自觉调 recall tool）留位

---

## Phase E — 后置 nice-to-have
- **WeChat permission yes/no relay** — cc Bash/Edit 弹权限请求时（如改 Desktop / .claude 路径），bridge 推到微信 → 你手机回 `/yes` `/no` `/always` → bridge 转回 cc。补 `acceptEdits` 自动模式之外的弹窗场景
- `/back N` — jsonl transcript truncate（手机版 `/rewind`），bridge 直接改 jsonl
- cross-channel handover — sid 共享，微信 ↔ cc 接着聊
- **continuation thinking** — 5s 触发后 cc 已开 inflight thinking 期间新 msg 到 → abort + merge input + 重发；思考完瞬间无 inflight → 立即 release（不再 hold）。前置 spike：验证 cc no-p stream-json 能否 mid-stream abort 单 request 而不杀 subprocess。感知层（标点 / 长度 / `/go` / hold 词增量）届时再议
- conversation-aware split 升级 — 按 haiku 切分而不是规则切

---

## Phase F — Pulse 整合（marrow 主体 + 独立 cron）
依赖 Phase A8 outbound send 接口稳定后启动。
- marrow 主体：`inner_state` 计算 + 多 signal 监控（屏幕时间 / task followup / 健康 / 时段）
- 独立 launchd cron loop（不在 synapse-wx 里）
- 通过 synapse-wx 的 outbound send 接口发 WeChat
- 跟 FUTURE.md Phase 5 `marrow_pulse_proactive_loop` 同一项

---

## Open Brainstorm（不入 Plan，单独议）
- **WeChat 专属 alert 完整方案** — 电脑关机谁告诉你？iOS Shortcut 外部 health check ping？

---

## 风险
- **iCloud sync 偶发 conflict 副本** → 直接挪试，出问题挪回
- **iLink 上游单点依赖** — API 改字段 retry + version pin + alert 监听；服务真挂整个微信链路废，无 fallback 可救，alert 报你
- **weclaude / cyberboss 都不能直接抄** → synapse-wx 自己起 MIT 干净，credit 在 README 挂

---

## 来源 / Credit
- **weclaude** (Jaynechu fork of allenhuang0)：time anchor 注入逻辑 · iLink 字段修复
- **cyberboss** (WenXiaoWendy)：sync-buffer 思路 · ret=-2 retry 思路 · sticker catalog 思路 · system-checkin-poller 思路（Phase F 用）
