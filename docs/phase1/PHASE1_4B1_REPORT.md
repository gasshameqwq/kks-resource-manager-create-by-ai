# Phase 1.4-B.1 Report — Library Query（Libraries 只读查询）

> 版本：Phase 1.4-B.1 · schema v2（**未改动**）· 2026-10-06
>
> 目标：在只读 Query Layer 中增加 Library 的查询能力（列表 + 基础统计），供未来 GUI/Browse 层使用。
> **本阶段不进入 GUI，不实现 Missing MOD / Preview。**
>
> 严格边界（全部遵守）：不改 `schema.py` / migrations、不新增字段/表/索引、
> 不改 Parser / Scanner / ResourceStore / models、不改 Search Core 语义、
> 不改 `review_reasons` / `needs_review` 写入、不修改 `resources_fts`、
> 不进入 `ui/`、不改 `main.py`、不新增 CLI 命令、不修改真实样本。

---

## 1. 实际修改文件

**新增**

| 文件 | 说明 |
| :-- | :-- |
| `tests/test_library_query.py` | Library 只读查询测试（14 项） |
| `docs/phase1/PHASE1_4B1_REPORT.md` | 本报告 |

**修改**

| 文件 | 改动 |
| :-- | :-- |
| `core/query/dto.py` | 新增不可变 DTO `LibrarySummary` |
| `core/query/queries.py` | 新增只读 `LibraryQuery`（list / count / get） |
| `core/query/__init__.py` | 导出 `LibraryQuery` / `LibrarySummary` |
| `core/__init__.py` | `__version__` 0.6.1 → 0.7.0；`__phase__` → `Phase 1.4-B.1 (Library Query)` |
| `README.md` | 状态行、路线图、文档表同步 |

**未改动**：`core/database/schema.py`、`core/database/db.py`、`core/parsers/*`、
`core/scanner/*`（含 `store.py`）、`core/models/*`、`core/library/store.py`、
`core/thumbnails/*`、`core/query/search.py`、`cli_query.py`、`main.py`、`ui/*`、真实样本。

---

## 2. 数据结构确认（不假设，逐项核对）

实现前核对了现有代码：

| 来源 | 事实 |
| :-- | :-- |
| `schema.py` · `libraries` | `id` / `name` / `root_path` / `root_path_key`(UNIQUE) / `enabled`(INTEGER, 默认 1) / `notes`(默认 '') / `created_at` / `updated_at` / `last_scan_at` |
| `schema.py` · `resources` | `library_id INTEGER REFERENCES libraries(id) ON DELETE SET NULL`；有索引 `idx_resources_library` |
| `models.Library` | `name` / `root_path` / `id` / `enabled: bool` / `notes` / `last_scan_at` |
| `core/library/store.py`（写层） | `list_all` / `stats` / `require` / `resolve` / `find_by_path` —— 只碰数据库，不扫目录 |
| `core/query/queries.py` | 已有 `_execute_select` 只读护栏与 `_fetchall/_fetchone`；**当前不 import 写层** |

**结论：现有 schema 完全支持 Library 只读查询，无需任何 migration / 新字段。**

---

## 3. API 与 DTO

### DTO（`core/query/dto.py`，`frozen=True`）

```python
@dataclass(frozen=True)
class LibrarySummary:
    id: int
    name: str
    root_path: str
    enabled: bool
    notes: str
    last_scan_at: str | None
    resource_count: int = 0   # 来自 resources.library_id 的只读聚合（派生，不落库）
```

字段全部来自既有 `libraries` 列；**不含**任何 UI 专用字段（颜色 / 图标 / 选中态 / 展开态）。

### Query（`core/query/queries.py`）

```python
LibraryQuery(conn).list(include_disabled=True) -> list[LibrarySummary]
LibraryQuery(conn).count(include_disabled=True) -> int
LibraryQuery(conn).get(library_id) -> LibrarySummary | None
```

与 `ResourceQuery / ModQuery / AuthorQuery / PluginQuery / UsageQuery` 保持同一风格：
构造函数接连接、方法返回不可变 DTO、内部全部走 `_execute_select`。

---

## 4. 只读实现方式

单条聚合查询，计数由子查询从 `resources.library_id` 得到（不调用写层）：

```sql
SELECT l.id, l.name, l.root_path, l.enabled, l.notes, l.last_scan_at,
       (SELECT count(*) FROM resources r WHERE r.library_id = l.id) AS resource_count
FROM libraries l
[WHERE l.enabled = 1]              -- include_disabled=False 时
ORDER BY l.name COLLATE NOCASE, l.id
```

- 所有语句经 `_execute_select`（只允许 `SELECT` / `WITH`），无 `INSERT/UPDATE/DELETE/CREATE/DROP`。
- **不调用** `LibraryStore`（Query Layer 不依赖写层）——有测试断言 `queries.py` 的 import 行不含 `core.library`。
- 统计口径与写层 `LibraryStore.stats().resources` 一致（测试对照验证），但实现独立。

---

## 5. 边界处理

| 场景 | 行为 |
| :-- | :-- |
| 空数据库 | `list() == []`、`count() == 0` |
| Library 无资源 | 仍然出现在列表里，`resource_count == 0` |
| 多 Library | 每个 Library 独立计数 |
| `include_disabled=False` | 过滤 `enabled = 0`；`list()` 默认包含暂停的 |
| 排序稳定性 | `ORDER BY name COLLATE NOCASE, id`；同名（含仅大小写不同）按 `id` 决出稳定顺序 |
| 不存在的 id | `get(id)` 返回 `None`（含负数），不抛异常 |
| `library_id` 为 NULL 的资源 | 不计入任何 Library（计数之和 = 有归属资源数） |

---

## 6. 测试数量与结果

新增 `tests/test_library_query.py`，共 **14** 项：

| 组 | 覆盖 |
| :-- | :-- |
| 空库 | `list`/`count`（含 `include_disabled=False`）全为 0/空 |
| 单 Library | 字段映射正确；无资源时 `resource_count == 0` |
| 多 Library | 计数分别为 2/1/0；NULL 归属不计入 |
| 空 Library | 仍然列出且 `count=0` |
| 排序稳定性 | 同名大小写不同按 id；重复调用结果一致 |
| 启用/暂停 | `include_disabled` 过滤；暂停库仍带自己的计数 |
| 按 id 查询 | 存在 → DTO；不存在/负数 → `None` |
| 与 `ResourceQuery` 一致 | 每个库的 `resource_count == rq.count(library_id=...)`；NULL 资源不计入 |
| 不依赖写层 | 对照写层 `stats()`；断言 `queries.py` 未 import `core.library` |
| DTO 形状 | 字段集合精确匹配；`frozen` 生效；无 UI 专用字段 |
| 只读不变量 | `total_changes` / `needs_review` / `app_meta` 前后不变 |
| 真实样本 | 见 §7 |

**全量 pytest 结果：**

```text
427 passed in 23.29s
0 failed / 0 xfailed        （1.4-A.1 基线 413 + 新增 14）
```

---

## 7. 真实样本验证（只读）

样本：`G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike`。
用 `LibraryStore` + `LibraryScanner` 扫描进**临时数据库**，再用 `LibraryQuery` 只读查询：

```text
library_count 1        resource_total 35
  lib 1 | enabled True | resources 35

sum_of_counts 35 == resource_query_by_lib 35 == resource_total 35
total_changes 2406 -> 2406（不变）
needs_review 0；app_meta 前后不变
样本 36 个文件：sha256 前后一致 True；size + mtime_ns 前后一致 True
```

- 真实样本目录**只读**：未写入、未重建索引、未 touch、未生成任何临时文件（输出全部写入系统临时目录）。
- 数量关系成立：`Σ resource_count == ResourceQuery.count() == 35`，且等于该 Library 的 `library_id` 过滤结果。

---

## 8. 只读不变量

- 合成库：连续多次 `list / list(include_disabled=False) / count / get` 前后，
  `total_changes` 不变、`needs_review` 各行不变、`app_meta` 全表不变。
- 真实样本（临时库）：`total_changes` 保持 `2406 → 2406`；`needs_review=1` 计数保持 0；`app_meta` 不变。

---

## 9. schema / migrations

**保持 v2 不变。** `SCHEMA_VERSION == 2`、`MIGRATIONS == [1, 2]`；未新增字段/表/索引；
未修改 `resources_fts`。

---

## 10. 是否修改真实样本

**未修改。** sha256（36 文件）、文件大小、`mtime_ns` 前后一致；样本目录未产生任何新文件。

---

## 11. 是否发现 P0 / P1 / P2

- **P0：无。**
- **P1：无。**
- **P2（记录，未修）：**
  1. `LibraryQuery` 暂未提供「按路径解析 Library」的只读入口（写层有 `resolve`）；
     当前 `get(id)` 已满足本阶段需求，是否需要 `resolve` 留待后续按真实需求评估。
  2. 计数子查询在数万资源量级可接受；暂无新增索引需求。
  3. 早期 P2（`resources_fts.author` 死列、`metadata_json.plugin_count` 冗余、
     跨语言/别名搜索等）维持不变。

---

## 12. 本阶段没有做的事情

- 没有改 schema / migrations / 索引 / `resources_fts`。
- 没有改 Parser / Scanner / ResourceStore / models / `core/library/store.py`。
- 没有改 Search Core 语义（`core/query/search.py` 未动）。
- 没有改 `review_reasons` / `needs_review` 写入逻辑。
- 没有进入 `ui/`（GUI 未动），没有改 `main.py`，没有新增 CLI 命令。
- 没有实现 Missing MOD filter，没有实现 Preview orchestration。
- 没有实现跨语言 / 别名搜索。
- 没有为 GUI 预置 UI 专用字段（颜色/图标/选中/展开等）。

---

## 13. 对 Phase 1.4-B 后续的建议

1. **1.4-B.2：`has_missing_mods` 只读筛选**（真实样本 `missing=134`，是当前最实在的管理痛点），
   纯 EXISTS、零 schema；仍留在 Query Layer。
2. **Browse 读模型组装**（可选）：把 `LibraryQuery` + `ResourceQuery` + `review_reasons` 组合成
   「库 → 资源」导航所需的数据，但**不要**在此引入 UI 框架代码。
3. **CLI 薄适配（待确认）**：是否给 `query` 增补 libraries 展示，由你决定；本阶段按边界未加。
4. **GUI（1.4-C）**：等只读读模型稳定后再进入，`ui/` 只调用 `core.query` + `core.thumbnails`。

---

### 附：验收对照

| 指令要求 | 结果 |
| :-- | :-- |
| Query Layer 提供 Library 只读列表 | ✅ `LibraryQuery.list()` |
| 稳定 id / name / root path 等既有事实字段 | ✅ `LibrarySummary` |
| 每个 Library 的资源数量 | ✅ `resource_count`（`resources.library_id` 聚合） |
| 统计不调用 `LibraryStore` | ✅（有断言） |
| 只读护栏 | ✅ 全走 `_execute_select` |
| 空库 / 无资源 / 多库 / 排序 / 不存在 id | ✅ 均有测试 |
| 不新增 UI 专用字段 | ✅（有断言） |
| 新增测试全部通过 | ✅ 14 项 |
| 全量 pytest 0 failed / 0 xfailed | ✅ 427 passed |
| schema v2 / migrations 不变 | ✅ |
| 真实样本保持不变 | ✅ sha256 + size + mtime_ns |
| `__version__` / `__phase__` | ✅ 0.7.0 / `Phase 1.4-B.1 (Library Query)` |
