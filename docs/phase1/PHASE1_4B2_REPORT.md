# Phase 1.4-B.2 Report — Missing MOD Query（`has_missing_mods` 只读筛选）

> 版本：Phase 1.4-B.2 · schema v2（**未改动**）· 2026-10-06
>
> 目标：给 `ResourceQuery.list/count` 增加只读筛选 `has_missing_mods`，
> 让资源列表能筛出「依赖了本地未安装 MOD」的资源。**纯只读派生，不新增持久化状态。**
>
> 严格边界（全部遵守）：不改 schema/migrations、不新增字段/表/索引、
> 不改 Parser/Scanner/ResourceStore/models、不改 `resources_fts`、
> 不改 Search Core 已有语义、不改 `review_reasons`/`needs_review`、
> 不进 `ui/`、不改 `main.py`、不新增 CLI 命令、不碰真实样本、
> 不实现 Preview / 跨语言 / 别名 / 模糊 / AI 搜索、不新增 `resources.has_missing_mods` 之类字段。

---

## 1. 实际修改文件

**新增**

| 文件 | 说明 |
| :-- | :-- |
| `tests/test_missing_mods.py` | `has_missing_mods` 只读筛选测试（23 项） |
| `docs/phase1/PHASE1_4B2_REPORT.md` | 本报告 |

**修改**

| 文件 | 改动 |
| :-- | :-- |
| `core/query/queries.py` | `_resource_where` 增加 `has_missing_mods` 子句；`ResourceQuery.list/count` 增加同名参数；`list` docstring 说明与 `has_mods` 的区别 |
| `core/__init__.py` | `__version__` 0.7.0 → 0.7.1；`__phase__` → `Phase 1.4-B.2 (Missing MOD Query)` |
| `README.md` | 状态行、路线图、文档表同步 |

**未改动**：`core/database/schema.py`、`core/database/db.py`、`core/parsers/*`、
`core/scanner/*`（含 `store.py`）、`core/models/*`、`core/library/store.py`、
`core/thumbnails/*`、`core/query/search.py`、`core/query/dto.py`、
`cli_query.py`、`main.py`、`ui/*`、真实样本。

---

## 2. 「missing MOD」的真实定义（实现前核对，未假设）

核对到的实际结构：

| 表 | 关键列 |
| :-- | :-- |
| `mods` | `id` / `guid`(UNIQUE) / `name` / `author` / … —— **本地已安装**的 zipmod |
| `resource_mods` | `(resource_id, mod_guid)` 汇总；`mod_id INTEGER REFERENCES mods(id)`，未安装时为空 |
| `resource_mod_usages` | `(resource_id, mod_guid, property)` 逐槽位**使用事实** |

既有只读逻辑：`ModQuery.missing()` 的定义是

```sql
SELECT u.mod_guid ...
FROM resource_mod_usages u LEFT JOIN mods m ON m.guid = u.mod_guid
WHERE m.id IS NULL GROUP BY u.mod_guid
```

**结论：一个资源「有没有缺失 MOD」= 它的 `resource_mod_usages.mod_guid` 中，
至少有一个在 `mods` 表里找不到对应行。** 本阶段采用与 `ModQuery.missing()`
完全相同的口径（`resource_mod_usages LEFT JOIN mods`），保证资源级与 MOD 级一致。

---

## 3. API

```python
ResourceQuery.list(
    ...,
    has_missing_mods: bool | None = None,
    ...
) -> list[ResourceSummary]

ResourceQuery.count(..., has_missing_mods: bool | None = None) -> int
```

语义：

- `None`：不增加任何条件，行为与之前完全一致；
- `True`：只返回**至少依赖了一个未安装 MOD** 的资源；
- `False`：只返回**不存在未安装 MOD 依赖**的资源。

---

## 4. `has_mods` 与 `has_missing_mods` 的区别

| 参数 | 语义 |
| :-- | :-- |
| `has_mods` | 有没有 MOD 依赖（**无论是否安装**）——基于 `resource_mod_usages` 是否有行 |
| `has_missing_mods` | 依赖里有没有**本地未安装**的 MOD |

关系（已用测试固定）：

```
has_missing_mods=True  一定是  has_mods=True  的（真）子集
has_mods=False  且  has_missing_mods=True  →  永远为空
has_mods=True   且  has_missing_mods=False →  正常情况，非空
```

即：**「有 MOD 依赖」≠「有缺失 MOD」**；四种组合（无依赖 / 全部已装 / 部分缺失 / 全部缺失）
都能被这两个参数区分，**没有**把 `has_missing_mods=True` 等同于 `has_mods=False`。

---

## 5. 实现方式

在 `_resource_where` 中用 **EXISTS / NOT EXISTS**（不是 COUNT）表达：

```sql
-- has_missing_mods=True
EXISTS (
    SELECT 1 FROM resource_mod_usages u
    LEFT JOIN mods m ON m.guid = u.mod_guid
    WHERE u.resource_id = r.id AND m.id IS NULL
)

-- has_missing_mods=False
NOT EXISTS ( ...同上... )
```

- **EXISTS 语义**：`resource_mod_usages` 主键是 `(resource_id, mod_guid, property)`，
  同一个 missing MOD 可以有多条 usage（不同 property）；`EXISTS` 不会因重复关系
  改变判断，也不会让资源在结果里重复出现（有专门测试）。
- **只读**：语句经 `_execute_select` 护栏；不 UPDATE `resources`、不写缓存、
  不改 `needs_review`、不新增派生列、不在 Python 里逐资源扫描。
- **与其它筛选是 AND**：`query` / `resource_type` / `library_id` / `needs_review` /
  `property_category` / `has_mods` / `mod_guid` 等可任意组合；排序 / 分页保持不变。

---

## 6. 测试数量与结果

新增 `tests/test_missing_mods.py`，共 **23** 项：

| 组 | 覆盖 |
| :-- | :-- |
| 四种基本情形 | 无依赖 / 全已装 / 单个缺失 / 多个缺失 / 部分已装部分缺失 |
| 三态 | `True` / `False` / `None`；两者计数之和 == 总数 |
| 与 `has_mods` 区分 | 真子集关系、`has_mods=False + missing=True` 为空、`has_mods=True + missing=False` 非空 |
| 组合筛选 | `query`（含按路径命中）/ `library_id` / `resource_type` / `needs_review` / `property_category` / `mod_guid` |
| 排序分页 | `order_by` + `limit/offset` + `descending` |
| 一致性 | 多组 scope 下 `count() == len(list())` |
| 重复关系 | 同一 missing MOD 多行 usage：只出现一次、判断不翻转 |
| 空库 | 三态均返回空 / 0 |
| 口径一致 | 资源级筛选结果 == `ModQuery.missing()` 各 guid 的资源并集 |
| 只读不变量 | `total_changes` / `needs_review` / `app_meta` / `mods` 行数 / `resource_mod_usages` 行数 前后不变 |
| 真实样本 | 见 §7 |

**全量 pytest 结果：**

```text
450 passed in 23.24s
0 failed / 0 xfailed        （1.4-B.1 基线 427 + 新增 23）
```

---

## 7. 真实样本验证（临时库，只读）

`resources_total 35`：

```text
resources_total                35
has_missing_mods=True          14   （list() 也是 14 条）
has_missing_mods=False         21
14 + 21 == 35                  True
has_mods=True / False          20 / 15
missing(True) ⊆ has_mods(True) True
distinct_missing_mods          134
installed_mods / orphan_mods   13 / 3
资源并集(各 missing guid 的 resources) == 14 == has_missing_mods=True 集合   True
total_changes 2406 -> 2406     True
sample 36 文件 sha256 / size+mtime_ns 前后一致  True
```

### 统计口径说明（为什么 134 ≠ 14）

- **134** 是**缺失 MOD 的 guid 数量**（distinct `resource_mod_usages.mod_guid`
  在 `mods` 里没有对应行）——单位是「MOD」。
- **14** 是**引用了至少一个缺失 MOD 的 resource 数量**——单位是「资源」。
- 两者单位不同，**本来就不应该相等**；一个资源可以缺多个 MOD，
  一个缺失 MOD 也可以被多个资源引用。
- 二者之间的正确关系是：`has_missing_mods=True` 的资源集合 == 所有缺失 guid
  对应资源集合的并集（实测 `True`）。

第 13 条要求里「与现有 missing MOD 统计之间的关系」即上述并集关系；本阶段**没有**
强行让 134 与 14 相等。

---

## 8. 只读不变量

- 合成库：连续多次 `list/count(has_missing_mods=True/False)` 前后，
  `total_changes` 不变、`needs_review` 各行不变、`app_meta` 全表不变、
  `mods` 与 `resource_mod_usages` 行数不变。
- 真实样本（临时库）：`total_changes` 保持 `2406 → 2406`；`app_meta` 与 `mods` 行数不变。
- 全部语句只经 `_execute_select`（只允许 `SELECT` / `WITH`）；本阶段未新增任何写语句。

---

## 9. schema / migrations / FTS

**均不变。** `SCHEMA_VERSION == 2`、`MIGRATIONS == [1, 2]`；未新增字段/表/索引；
`resources_fts` 未改动。

---

## 10. 是否修改真实样本

**未修改。** 真实样本目录只读（未写入、未重建索引、未 touch、未生成临时文件）：
sha256（36 文件）与 `size + mtime_ns` 前后一致。

---

## 11. 是否发现 P0 / P1 / P2

- **P0：无。**
- **P1：无。**
- **P2（记录，未修）：**
  1. `resource_mods`（汇总表）当未安装时 `mod_id` 为空，理论上也能表达 missing；
     本阶段刻意只采用 `resource_mod_usages` 一种口径，避免两套口径漂移。
  2. 反斜杠路径 / 大小写等与 `mod_guid` 语义无关，不影响本筛选。
  3. 早期 P2（`resources_fts.author` 死列、`metadata_json.plugin_count` 冗余、
     跨语言/别名搜索、`LibraryQuery.resolve` 等）维持不变。

---

## 12. 本阶段没有做的事情

- 没有改 schema / migrations / 索引 / `resources_fts`。
- 没有改 Parser / Scanner / ResourceStore / models / `core/library/store.py`。
- 没有改 Search Core 语义（`core/query/search.py` 未动）。
- 没有改 `review_reasons` / `needs_review` 写入逻辑。
- 没有进入 `ui/`、没有改 `main.py`、没有新增 CLI 命令。
- 没有实现 Preview orchestration、没有实现跨语言 / 别名 / 模糊 / AI 搜索。
- 没有新增 `resources.has_missing_mods` 等持久化字段，没有写缓存。
- 没有把 `has_missing_mods=True` 等同于 `has_mods=False`。

---

## 13. 对 Phase 1.4-B 后续的建议

1. **Browse 读模型组装（可不做）**：`LibraryQuery` + `ResourceQuery(has_missing_mods=...)`
   已经足以支撑「缺 MOD 视图」；若需要，可再补一个只读聚合（例如按 Library 统计缺 MOD 资源数）。
2. **CLI 薄适配（待确认）**：是否给既有 `query resources` 增加 `--has-missing-mods`，
   由你决定；本阶段按边界未加。
3. **GUI（1.4-C）**：待只读读模型稳定后再进入；`ui/` 只调用 `core.query` + `core.thumbnails`。
4. **避免过度扩展**：不要把 missing / orphan / needs_review 混成一个「健康分」——它们是
   互相独立的只读派生维度。

---

### 附：验收对照

| 指令要求 | 结果 |
| :-- | :-- |
| 核对 missing MOD 的真实结构 | ✅ `resource_mod_usages LEFT JOIN mods`，与 `ModQuery.missing()` 同口径 |
| `has_missing_mods` 参数（True/False/None） | ✅ list 与 count 一致 |
| 用 EXISTS / NOT EXISTS，不用 COUNT | ✅ |
| 不写库 / 不写缓存 / 不改 needs_review / 不新增字段 | ✅（有只读不变量测试） |
| 与 `has_mods` 明确区分 | ✅ 四种组合有测试 |
| 与 query / library / type / needs_review / category / 排序分页组合 | ✅ 均有测试 |
| 重复关系不影响判断 | ✅ |
| 空数据库 | ✅ |
| 全量 pytest 0 failed / 0 xfailed | ✅ 450 passed |
| schema v2 / migrations / FTS 不变 | ✅ |
| 真实样本不变 | ✅ sha256 + size + mtime_ns |
| `__version__` / `__phase__` | ✅ 0.7.1 / `Phase 1.4-B.2 (Missing MOD Query)` |
