# Phase 3.1 — Step 6 Final Audit / Closure Report

> 阶段：**Phase 3.1 — User Write Foundation（Final Audit / Closure Review）**
> 日期：2026-10-07
> 审计依据：`docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md` + `docs/phase3/PHASE3_0_CONTRACT.md`
> 审计性质：**只读审计**。本步骤未修改任何功能代码 / schema / migration / 测试；
> 唯一新增物为本文件，另对 `PHASE3_1_LOG.md` 做了一处**非语义**的措辞澄清（见 §10）。
> 未创建 commit / tag；未 push；`phase-3.0-closed` 未移动。

> 结论：**Phase 3.1 — CLOSED / PASS**

---

## 1. 审计范围

Step 1–5 的实现（ResourceWriteService / Scanner ownership / Effective display name /
Read model / CLI）是否满足冻结契约；Invariant A–F；写边界；CLI 边界；
Query Layer 只读性；ownership guard；scope；文档一致性；完整测试集；Git / tag 状态。

---

## 2. Ownership（Contract §3）

| Data | Owner | Writer | 审计结果 |
| :--- | :--- | :--- | :--- |
| `name` | Machine | `ResourceStore` | ✅ |
| `file_path` / `file_path_key` / `relative_path` / `file_size` / `modified_time` / `extension` / `sha256` / `card_marker` / `metadata_json` / `parse_status` / `parse_error` / `scan_status` / `last_scanned_at` / `id` / `created_at` | Machine | `ResourceStore` | ✅ |
| `display_name` / `notes` | User | `ResourceWriteService` | ✅ |
| `resource_type`（`type_source='auto'`） | Machine | `ResourceStore`（INSERT 仅写 `'auto'`） | ✅ |
| `resource_type`（`type_source='user'`） | User | `ResourceWriteService` | ✅ |
| `type_source` | ownership marker | `'auto'` ← `ResourceStore` INSERT；`'user'` ← `ResourceWriteService`；无 `user→auto` | ✅ |
| `updated_at` | 系统簿记（豁免） | 两个 writer 的 UPDATE 均更新 | ✅ |

**结论**：无其它 runtime writer 越过 ownership boundary。

代码证据：

- `core/scanner/store.py` 的 19 个 SQL 字符串字面量中**不含** `display_name` / `notes` / `'user'`（tokenize 级核对）；
- `core/app/resource_write.py` 的 `_USER_WRITABLE_COLUMNS = {display_name, notes, resource_type, type_source}`，
  SQL 由该白名单 + `updated_at` 构造。

---

## 3. Invariants A–F

| Invariant | 内容 | 对应测试 | 结果 |
| :--- | :--- | :--- | :--- |
| **A** | 用户 `display_name` + Scanner 改 `name` ⇒ `display_name` 保持 | `tests/test_scanner.py::test_rescan_keeps_user_display_name_when_name_changes` | ✅ PASS |
| **B** | clear `display_name` ⇒ `NULL` ⇒ effective 回退 `name` | `tests/test_scanner.py::test_invariant_b_clear_display_name_falls_back_to_name` | ✅ PASS |
| **C** | `display_name == name` 仍是 override，Scanner 不覆盖 | `tests/test_scanner.py::test_invariant_c_equal_to_name_override_survives_rescan` | ✅ PASS |
| **D** | `type_source='user'` ⇒ rescan 不覆盖 `resource_type` | `tests/test_scanner.py::test_rescan_does_not_touch_notes_or_user_type` | ✅ PASS |
| **E** | 用户 `notes` + rescan ⇒ 不变 | `tests/test_scanner.py::test_rescan_does_not_touch_notes_or_user_type` | ✅ PASS |
| **F** | machine writer 不写 user 列；user writer 只写允许列 | `tests/test_ownership_guard.py`（4 个）+ `tests/test_resource_write.py::test_user_write_sql_only_targets_user_columns` | ✅ PASS |

Invariant F 证据细节：

- 静态：`core/**`、`ui/**`、`main.py`、`cli_query.py` 中能写 `resources` 的模块**只有**
  `core/scanner/store.py` 与 `core/app/resource_write.py`；
- 运行时（真实扫描，INSERT + UPDATE 两条路径，`set_trace_callback`）：
  对 `resources` 的写入不含 user-owned columns；
- 用户 writer 的 SET 目标集合只能是
  `{display_name, updated_at}` / `{notes, updated_at}` / `{resource_type, type_source, updated_at}`；
- `resources_fts`（FTS 触发器）不被误判为 `resources` 写入。

---

## 4. Write Boundary

| 要求 | 结果 |
| :--- | :--- |
| `ResourceWriteService` 是唯一 runtime user-data 写入口 | ✅ |
| 每个 public write method = 一个 `db.transaction` | ✅（`_update_user_columns` 统一包裹） |
| not found → `ResourceNotFound` | ✅ |
| invalid type → `InvalidResourceValue`（且不写库） | ✅ |
| 失败 rollback + 原样抛出（不吞异常） | ✅（`test_failed_write_rolls_back_and_propagates`） |
| 相同值重复写入安全（幂等） | ✅（`test_set_display_name_is_idempotent`） |
| 不存在整行覆盖 | ✅（SET 只含本次操作列 + `updated_at`） |
| 无 Query Layer write | ✅（`_execute_select` 仍只放行 `SELECT` / `WITH`） |
| CLI 不直接写数据库 | ✅ |
| UI 不直接写数据库 | ✅（`ui/**` 无 `sqlite3` / 无写服务调用） |

---

## 5. CLI Boundary

命令（`main.py` → `resource` 子命令）：

```text
resource set-display-name <id|路径> <名称>
resource set-display-name <id|路径> --clear
resource set-notes        <id|路径> <备注>
resource set-notes        <id|路径> --clear
resource set-type         <id|路径> <类型>
```

调用链：`CLI → ResourceQuery.resolve() → ResourceWriteService → DB`。

| 要求 | 结果 |
| :--- | :--- |
| id 可解析 / path 可解析 | ✅（`test_cli_resolves_target_by_id` / `..._by_path`） |
| path_key / relative_path 既有 resolve 语义未破坏 | ✅（复用 `ResourceQuery.resolve()`，未新增解析算法） |
| 参数错误 exit 2 | ✅（缺 value / `--clear` 与 value 冲突 / 无子命令） |
| target 不存在 exit 1 | ✅ |
| invalid type exit 1 | ✅（且未写库） |
| 其他 write error exit 1 | ✅ |
| 不打印 traceback | ✅（`_report_write_error` 输出简洁消息） |
| 不 import `sqlite3` | ✅ |
| 不调用 `ResourceStore` | ✅ |
| 不执行 INSERT / UPDATE / DELETE | ✅ |

---

## 6. Effective Display Name

唯一权威实现位于 `core/query/dto.py`（`ResourceSummary`）：

```text
effective_display_name = display_name  if (display_name is not None and display_name.strip() != "")
                         else name
title                  = effective_display_name → relative_path 文件名 → file_path
```

| 要求 | 结果 |
| :--- | :--- |
| UI 只是委托（`ui/resource_model.display_title` → `resource.title`） | ✅ |
| UI 无重复 fallback chain | ✅ |
| 历史空白 `display_name` 读取时视为无 override | ✅（Contract §4.4） |
| 无自动迁移 / 清理历史数据 | ✅ |

测试：`tests/test_effective_display_name.py`（22 passed）。

---

## 7. Read Model

| 要求 | 结果 |
| :--- | :--- |
| `ResourceSummary.type_source` / `notes` 为 additive（末尾 + 默认值） | ✅（默认 `"auto"` / `None`） |
| Query Layer 只执行 `SELECT` / `WITH` | ✅（`_ALLOWED_KEYWORDS = ("select", "with")` 未改） |
| Query Layer 未获得 write capability | ✅（`core/query/queries.py` diff 仅 SELECT 列 + 映射） |
| 能正确读取 `notes` / `type_source` | ✅（`tests/test_read_model_exposure.py`，9 passed） |
| 未反向调用 `ResourceWriteService` | ✅（query 包内无该 import） |

---

## 8. Ownership Guard 最终检查

```text
core/**、ui/**、main.py、cli_query.py 中对 resources 的 INSERT / UPDATE / DELETE：

  core/scanner/store.py       （machine writer）  —— 允许
  core/app/resource_write.py  （user writer）     —— 允许
  其它文件                     —— 0 处

resources_fts 未被计入（FTS 触发器 / 内部语句）—— 无 ownership violation。
```

运行：`tests/test_ownership_guard.py`（4 passed）。

---

## 9. Scope Audit

| 排除项 | 结果 |
| :--- | :--- |
| GUI 编辑 | ✅ 未进入（`ui/**` 无写能力） |
| Tag / Favorite / Collection | ✅ 未进入（无任何写入者） |
| `type_source` `user → auto` | ✅ 未进入（无 revert API） |
| Query Layer boolean text syntax | ✅ 未进入 |
| 自动迁移 / 清理历史 `display_name` | ✅ 未进入 |
| schema v3 / 新 table / 新 column / 新 index / migration | ✅ 未进入 |
| Parser 行为变化 | ✅ 未进入（`core/parsers/**` diff 为空） |
| 文件移动 / 重命名 / 删除 / 下载 | ✅ 未进入（唯一文件写入仍是既有 `data/thumbnail_cache/`） |
| AI / semantic / similarity / perceptual hash | ✅ 未进入 |
| relocation / movement detection | ✅ 未进入 |
| new identity key | ✅ 未进入 |

```text
SCHEMA_VERSION = 2
MIGRATIONS     = [1, 2]
业务表          = 16
core/database/** diff = 空
```

---

## 10. Documentation Consistency

| 文档 | 审计结果 |
| :--- | :--- |
| `docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md` | ✅ 与实现一致；本步骤未修改 |
| `docs/phase3/PHASE3_1_LOG.md` | ✅ 已反映 Step 1–5 全部完成、基线 825、文件清单与 `git status` 一致；本步骤仅做一处**非语义**措辞澄清（Step 4 段落中「CLI 暴露属 Step 5，本步不做」改为明确说明用户编辑入口已在 Step 5 于 `main.py` 实现），未改变任何结论 |

---

## 11. 完整测试

```text
python -m pytest -q -p no:cacheprovider
→ 825 passed, 0 failed
```

关键测试文件：

| 文件 | 结果 |
| :--- | :--- |
| `tests/test_ownership_guard.py` | 4 passed |
| `tests/test_resource_write.py` | 35 passed |
| `tests/test_scanner.py` | 43 passed |
| `tests/test_effective_display_name.py` | 22 passed |
| `tests/test_read_model_exposure.py` | 9 passed |
| `tests/test_cli_resource_write.py` | 14 passed |
| `tests/test_library_cli.py` / `tests/test_query_cli.py` | 11 / 28 passed |
| `tests/test_gui_smoke.py` | 19 passed |
| `tests/test_database_schema.py` / `tests/test_migration_v2.py` | 9 / 27 passed |

---

## 12. Git / Tag

```text
HEAD                        = ae3529aeaf199eab2949fa14bc25977521186469
phase-3.0-closed（commit）   = c2fd52718bbfbae4576207bfdbbed8f524f906de
phase-3.0-closed（tag obj）  = ba30bc436175b3cbd181c25427cb80b855a80e09（annotated tag，未改动）
```

> 说明：`phase-3.0-closed` 是 **annotated tag**，因此 `git rev-parse phase-3.0-closed`
> 返回 tag 对象 SHA（`ba30bc43…`，自 Phase 3.0 关闭时即如此）；
> 其指向的 commit 是 `c2fd52718…`（`git rev-parse phase-3.0-closed^{commit}`）。两者均未改变。

本步骤：未 commit、未 tag、未 push。

---

## 13. 最终结论

```text
Phase 3.1 — CLOSED / PASS
```

（Step 1–5 全部完成并通过审计；无未决 blocker；未扩张范围。）
