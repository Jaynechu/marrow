# Reconcile gap — sub-page md→db

> DESIGN.md:68 / DECISIONS.md:62-63 已规定所有手改 md 反向 sync 到 db。
> 现状只盖了 4 张表 + atlas 残，其余 sub-page 手改永远不进 db。

## 现有 reconcile (`marrow/reconcile.py`)
- milestones
- milestone_candidates (dashboard 块)
- tasks (dashboard 块)
- affect (dashboard 块)

## atlas — 残缺
- `marrow/atlas.py:358` `reconcile_atlas` 存在
- 写残：全表 `UPSERT … updated_at=NOW()` 每 tick 盖章，不走 hash diff
- 后果：sync_loop 每 5s 触发 db→md render，打字被吞 (`fork → orkf`)
- 修：UPSERT 前比对 description/naming_hint/depth，真不一样才 bump updated_at

## 待补 reconcile (db-backed sub-page，spec 已存在)
| sub-page | 表 | builder |
|---|---|---|
| diary | diary | `subpage_specs.py:141` |
| memes | memes | `subpage_specs.py:188` |
| goose-bites | goose_bites | `subpage_specs.py:285` |
| profile | entities_live | `subpage_specs.py:58` |
| stickers | stickers (+memes JOIN) | `subpage_specs.py:224` |
| wallet | wallet | `subpage_specs.py:261` |
| projects_index | tasks (派生) | `subpage_specs.py:325` |
| study_index | (待确认) | `subpage_specs.py:366` |

## 非 db-backed (不补)
- cheatsheet — read-only render，hand-edit 已 preserve
- dir_tree — 已被 atlas 替代
- projects/&lt;name&gt;.md — tasks 派生，手改进 db 走 reconcile_tasks 即可

## 决策待定
- 前端走 db CRUD → reconcile 整条路径作废，本 plan 全砍
- 前端走 md → 按上表全补，模板抄 `reconcile_milestones`
