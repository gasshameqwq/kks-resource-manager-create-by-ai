# Phase 3.1 — Implementation Log（User Write Foundation）

> 阶段：**Phase 3.1 — User Write Foundation（IMPLEMENTATION IN PROGRESS）**
> 日期：2026-10-07
> 实施依据：`docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md`（冻结）+ `docs/phase3/PHASE3_0_CONTRACT.md`
> 本文件是**实施日志**（记录已完成的 Step、文件、测试与状态），不是契约、不改变任何契约。

---

## 0. 当前状态总览

| 项 | 值 |
| :--- | :--- |
| 已完成 Step | **Step 1 / Step 2 / Step 3 / Step 4 / Step 5** |
| 未开始 Step | Step 6 剩余部分（除已建立的 ownership guard） |
| SCHEMA_VERSION | `2`（未变） |
| MIGRATIONS | `[1, 2]`（未变） |
| schema / migration / `core/database/**` | **零改动** |
| commit | **未创建任何 commit**（按各 Step 要求；由用户决定何时提交） |
| `phase-3.0-closed` tag | 未移动（仍指向 `c2fd527`） |
| `main` HEAD | `ae3529a`（3.0.2 Design Review 入库 commit） |

### 测试基线演进

```text
Phase 3.1 之前（基线）      734 passed
Step 1（ResourceWriteService）769 passed
Step 2 + Step 3               802 passed
Step 4（Read Model Exposure） 811 passed
Step 5（CLI User Write Entry）825 passed
```

全部通过；完整测试集命令：

```text
python -m pytest -q -p no:cacheprovider
```

> 说明：`-p no:cacheprovider` 与 `PYTHONDONTWRITEBYTECODE=1` 仅用于避免写入测试缓存，
> 不改变测试集合。

---

## 1. Step 1 — ResourceWriteService

| 项 | 内容 |
| :--- | :--- |
| 新增 | `core/app/resource_write.py` |
| 修改 | `core/app/__init__.py`（导出 Service / 异常） |
| 测试 | `tests/test_resource_write.py`（35 个） |

**内容**

- `ResourceWriteService(conn)`：Phase 3.1 **唯一**的用户数据 runtime 写入口；
- API：`set_display_name` / `set_notes` / `set_resource_type`；
- 异常：`ResourceWriteError` / `ResourceNotFound` / `InvalidResourceValue`；
- 只写 `display_name` / `notes` / `resource_type` / `type_source`（+ 系统簿记 `updated_at`），
  不整行覆盖、不写任何 machine fact；
- 每个 public 写方法 = 一个 `db.transaction`；失败回滚并原样抛出；
- `display_name` 归一化：`None` / `""` / 纯空白 ⇒ `NULL`；非空 ⇒ `strip()` 后保存；
  与 `name` 相同仍是有效 override（不做 `==` 判断）。

---

## 2. Step 2 — Scanner ownership 修正

| 项 | 内容 |
| :--- | :--- |
| 修改 | `core/scanner/store.py` |
| 测试 | `tests/test_scanner.py`（新增 7 个）、`tests/test_ownership_guard.py`（静态 + 运行时） |

**删除的 `display_name` 写入**

```text
upsert_card_resource INSERT  → 移除 display_name 列 + parsed.name 值
upsert_card_resource UPDATE  → 移除 display_name = ? 与「等于旧 name 才跟随」启发式
upsert_mod_resource  INSERT  → 移除 display_name 列 + display 值
upsert_mod_resource  UPDATE  → 移除 display_name = ? 与同一启发式
```

**保留不变**：`name` 与全部 scanner-derived fields、parse/scan 状态；
新建资源仍写 `type_source = 'auto'`（Contract 允许的 machine 初始化）；Parser 未改。

> 由此 `display_name` 成为**纯用户数据**：无 override 时 DB 值为 `NULL`，
> 只由 `ResourceWriteService` 写入。

---

## 3. Step 3 — Effective display name 统一

| 项 | 内容 |
| :--- | :--- |
| 修改 | `core/query/dto.py`（`ResourceSummary`）、`ui/resource_model.py` |
| 测试 | `tests/test_effective_display_name.py`（22 个） |

**core 唯一权威实现**（`core/query/dto.py`）

```text
effective_display_name = display_name   if (display_name is not None and display_name.strip() != "")
                         else name

title = effective_display_name → relative_path 的文件名 → file_path
```

- `ui/resource_model.display_title()` 改为薄委托：`return resource.title`，UI 不再自带 fallback chain；
- 历史遗留空白 `display_name`（`''` / 纯空白）**读取时**按「无 override」处理；不做任何自动迁移/清理。

---

## 4. Step 4 — Read Model Exposure（本次完成）

| 项 | 内容 |
| :--- | :--- |
| 修改 | `core/query/dto.py`（additive 字段）、`core/query/queries.py`（SELECT + mapping） |
| 测试 | `tests/test_read_model_exposure.py`（9 个） |

**`ResourceSummary` 新字段**（additive，置于末尾，均带兼容默认值）

```text
type_source: str       = "auto"    # resources.type_source 只读值（'auto' / 'user'）
notes:       str | None = None     # resources.notes 只读值
```

**Query Layer 变化（仍只读）**

```text
_RESOURCE_SUMMARY_COLUMNS  += r.type_source, r.notes
_row_to_resource_summary() += type_source=row["type_source"], notes=row["notes"]
```

- `_execute_select` 护栏未改（仍只放行 `SELECT` / `WITH`）；
- 未新增任何写能力，未调用 `ResourceWriteService`；
- 未改动 `cli_query.py`（CLI 只读查询层保持原样；用户编辑入口在 Step 5 于 `main.py` 实现）；
- 兼容性：全仓库 `ResourceSummary(...)` 构造均为关键字构造，新字段带默认值，
  旧式关键字 / 位置构造均保持有效。

---

## 5. Step 5 — CLI 用户编辑入口（本次完成）

| 项 | 内容 |
| :--- | :--- |
| 修改 | `main.py`（新增 `resource` 子命令 + 薄适配 handler） |
| 测试 | `tests/test_cli_resource_write.py`（14 个） |

**命令**

```text
python main.py resource set-display-name <id|路径> <名称>
python main.py resource set-display-name <id|路径> --clear
python main.py resource set-notes        <id|路径> <备注>
python main.py resource set-notes        <id|路径> --clear
python main.py resource set-type         <id|路径> <类型>
```

**分层与实现**

```text
CLI（main.py，仅参数解析）
  → ResourceQuery.resolve()          # 只读解析 target（id / 路径 / path_key / relative_path）
  → ResourceWriteService             # 唯一用户数据写入口
  → DB
```

- `--clear` 传 `None` 给写服务（CLI 不自己写 NULL）；值的归一化由写服务负责；
- `set-type` 不提供 clear / revert；
- 错误处理：参数冲突 / 缺值 → exit 2；target 不存在 → exit 1；非法 type → exit 1；
  其他写服务异常 → exit 1（带简洁消息，不打印 traceback）；
- CLI 不 import `sqlite3`、不执行 INSERT/UPDATE/DELETE、不调用 `ResourceStore`。

---

## 6. Ownership Guard（Step 2 起建立，Step 5 后仍有效）

`tests/test_ownership_guard.py`：

1. **静态**：`core/**`、`ui/**`、`main.py`、`cli_query.py` 中能写 `resources` 的模块
   只有 `core/scanner/store.py`（machine）与 `core/app/resource_write.py`（user）；
   `resources_fts` 不被误判。
2. **UI / CLI** 不 import `sqlite3`。
3. **运行时**：真实扫描（INSERT + UPDATE 两条路径）实际执行的 SQL 中，
   对 `resources` 的写入不含 `display_name` / `notes` / `'user'`，
   且 Scanner 仍正常写 `name`。

---

## 7. 当前工作区（未提交）文件清单

```text
已修改（tracked）:
  core/app/__init__.py          (Step 1)
  core/query/dto.py             (Step 3 + Step 4)
  core/query/queries.py         (Step 4)
  core/scanner/store.py         (Step 2)
  ui/resource_model.py          (Step 3)
  main.py                       (Step 5)
  tests/test_scanner.py         (Step 2/3)
  tests/test_search_core.py     (修正旧 Scanner 行为断言)

新增（untracked）:
  core/app/resource_write.py
  tests/test_resource_write.py
  tests/test_effective_display_name.py
  tests/test_ownership_guard.py
  tests/test_read_model_exposure.py
  tests/test_cli_resource_write.py
  docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md
  docs/phase3/PHASE3_1_LOG.md   （本文件）
```

> 未创建 commit；`main` HEAD 仍为 `ae3529a`，`phase-3.0-closed` 未移动。

---

## 8. 明确未做（保持 Phase 3.1 范围内 / 或属后续 Step）

- Step 6 剩余部分（除已建立的 ownership guard）—— **未做**；
- GUI 编辑资源字段 —— **未做**（Phase 3.1 不纳入）；
- Tag / Favorite / Collection —— **未做**；
- `type_source` 的 `'user' → 'auto'` 回退 —— **未做**（Contract §2-15 明确收窄）；
- Query Layer 文本布尔语法（`field:` + AND/OR/NOT）—— **未做**；
- 自动迁移 / 清理历史 `display_name` —— **未做**；
- schema / migration / 新表 / 新列 / 新索引 —— **未做**。
