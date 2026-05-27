# drift-sweep + paths + ssarchive (3 wt parallel)

Goal: 一晚做完 drift_sweep L1 · paths.toml L2 · session_archive_skip_manual 三件，pytest 全绿合并。

Architecture: 三个独立 worktree 并发 sonnet。Lumi 已锁 scope，跑的 session 不要重新 grill。

Tech: Python · watchdog · ripgrep subprocess · sqlite · toml · pytest.

## Authorized roots (drift_sweep + dir_tree 共用)
- `~/cc-lab/`
- `~/.config/marrow/`
- `~/.claude/`
- `~/Toolkit/`
- `~/Desktop/NY/`
- `~/Library/Mobile Documents/com~apple~CloudDocs/Study/`

## Exclude (硬编码到 scanner)
- 二进制: `.jpg .jpeg .png .gif .pdf .db .sqlite .sqlite-wal .sqlite-shm .pyc .zip .whl .tar .gz .dmg .so .dylib .o`
- 目录: `.git __pycache__ node_modules .venv venv .DS_Store logs archives drift_backup`
- 大小: >10MB skip

## wt-drift — drift_sweep L1
- 扩展现有 marrow watcher (`marrow/watcher.py` 或新模块) 监听 6 个 roots
- Trigger A: watchdog `on_moved` → 同 root mv，src+dest 一次性拿到
- Trigger B: watcher 后台维护 basename → (path, size, mtime) cache; `on_deleted` 时入待匹配队列 (TTL 30min); `on_created` 时同 basename + size 完全相同 → 当跨 root mv (含桌面中转停留场景); 同时算 new 文件 hash 存 cache 备后续核对
- Trigger C: 推断不上的 deleted → "悬挂引用模式"，扫引用：refs=0 静默丢弃 (避免 notes 日常清理刷屏)；refs≥1 写报告但不替换
- Trigger D: CLI `mw drift <old> <new>` 手动起 (batch / 强制 / 兜底)
- Batch debounce: 30 秒窗口内多个 mv/rename/delete 合并成单个 batch pending + 单个 alert "drift batch: N ops"，避免刷屏；confirm 一次全 apply
- 流程: catch → ripgrep 扫所有 roots 找 old → 写 `~/.config/marrow/drift_pending/<id>.json` (含 src/dest/refs[file:line] + diff preview) → dashboard Alert "drift ready: <old> → <new> [N refs in M files]"
- Apply: `mw drift confirm <id>` → git 区先 `git add` 再替换 (revertable) · 非 git 区拷贝原文到 `~/.config/marrow/drift_backup/<id>/` → ripgrep 替换 → 清 pending
- Reject: `mw drift reject <id>` → 丢 pending，不动文件
- Match rule: path-shaped string only —
  - 含 `/` 或 `.<ext>` 或 在 `"..." / '...' / \`...\`` 边界内
  - 替换时 word-boundary 双侧
  - 纯名字提及 (e.g. `marrow project` 散文里) 不动
- 副产物: 每次跑完 (auto / CLI / confirm) 刷新 `~/.config/marrow/dir_tree.md` (每 root 一棵 tree, max-depth=4, exclude 同上)
- pytest fixtures (`tests/test_drift_sweep.py`):
  - `test_same_root_mv_dry_run` — 造 3 文件互引，mv A→B，断言 pending 有 ≥3 refs，原文件未动
  - `test_confirm_applies` — confirm 后 grep A=0, grep B=3, backup 存在
  - `test_reject_discards` — reject 后 pending 不存在，文件未动
  - `test_dangling_delete` — 删 A，断言报告含 refs 但文件未替换
  - `test_path_shaped_only` — `marrow project` 散文不动，`marrow/foo.py` 改
  - `test_dir_tree_refresh` — 跑完 dir_tree.md 含新路径不含旧路径

## wt-paths — paths.toml L2
- 扫 `marrow/**/*.py` 找 hardcode: `~/.config/marrow/...` · `~/Desktop/NY/...` · `~/Library/Mobile Documents/...` · `/tmp/marrow_*`
- 抽 `~/.config/marrow/paths.toml`:
  ```
  marrow_db = "~/.config/marrow/marrow.db"
  ny_root = "~/Desktop/NY"
  dashboard_md = "~/Desktop/NY/dashboard.md"
  handover_md = "~/.config/marrow/handover.md"
  drift_pending_dir = "~/.config/marrow/drift_pending"
  drift_backup_dir = "~/.config/marrow/drift_backup"
  dir_tree_md = "~/.config/marrow/dir_tree.md"
  logs_dir = "~/.config/marrow/logs"
  ```
- 加载层 `marrow/paths.py`: `load_paths()` 返回 dataclass，import 时 expanduser + env override `MARROW_PATHS_FILE`
- 全代码引用换 `paths.xxx`
- Backward compat: 没 paths.toml 时 fallback 到 hardcode default
- pytest (`tests/test_paths_toml.py`):
  - `test_load_default` — 无 toml 时 fallback 路径正确
  - `test_load_custom` — `MARROW_PATHS_FILE=/tmp/test.toml` override 生效
  - `test_no_regression` — `mw recall hi` / `mw refresh` / sessionend dummy 跑通

## wt-ssarchive — session_archive_skip_manual
- `mm+` UserPromptSubmit hook: 立即对 sid 跑 `mw sessionend rerun <sid>` (强制覆盖 done 标记 + ≤3-turn auto-skip). `mm+` 不带参 = 当前 session sid; `mm+ <sid>` = 指定 sid. 场景: 本 session 不关想 handover 给 next / endhook 失败 resume 后手动补跑 / 历史 closed sid 补跑
- `mm-` UserPromptSubmit hook: 检测前缀 → 写 `audit_log` 行 `(sid, action='manual_skip', status='skip')`
- sessionend pipeline 启动时查 audit_log skip flag → 跳过 LLM + diary + handover write
- resume hook 顶 skip: cc 内置 resume event 触发时清除对应 sid 的 skip flag (新 audit_log 行 status='skip_cleared')
- ≤3-turn auto skip 保留不动
- pytest (`tests/test_session_archive_skip.py`):
  - `test_mm_minus_writes_skip_flag` — mm- 后 audit_log 有 skip 行
  - `test_skip_blocks_sessionend_llm` — skip 标了 sessionend 不调 LLM (mock LLM)
  - `test_mm_plus_reruns_sid` — mm+ <sid> 后 sessionend pipeline 产出落库
  - `test_resume_clears_skip` — resume 后 audit_log 有 skip_cleared 行
  - `test_auto_3turn_still_works` — ≤3-turn 仍 auto skip

## Dispatch order
1. main session 一次 message 起 3 个 worktree-implementer (sonnet)，isolation=worktree
2. 各 wt 自带 pytest 跑绿才报 done
3. 合并顺序: wt-paths (基建) → wt-drift (用 paths) → wt-ssarchive (独立)
4. 全合并后 main 跑 full `pytest -q` 确认无 regression
5. PROGRESS.md append 3 行 delta，commit

## Done condition (machine-checkable)
```
cd ~/cc-lab/marrow && pytest tests/test_drift_sweep.py tests/test_paths_toml.py tests/test_session_archive_skip.py -q
# exit 0 + 全部测试通过
```

## Echo on completion
```
pytest tests/test_drift_sweep.py tests/test_paths_toml.py tests/test_session_archive_skip.py -v
ls ~/.config/marrow/paths.toml ~/.config/marrow/dir_tree.md
git log --oneline -5
```
