# Phase 1.4-A Report — Search Core（只读文本检索）

> 版本：Phase 1.4-A · schema v2（**未改动**）· 2026-10-06
>
> 目标：在现有只读 Query Layer 内实现统一的资源文本检索
> `ResourceQuery.list/count(query=...)`，支持名称/作者子串与 CJK 短查询，
> 并与现有结构化筛选、排序、分页组合。**不改 schema / Parser / Scanner /
> ResourceStore / models / review_reasons；不进入 GUI；不碰真实样本。**

---

## 1. 实际修改文件

**新增**

| 文件 | 说明 |
| :-- | :-- |
| `core/query/search.py` | 检索路由与安全转义（纯函数，不执行 SQL） |
| `tests/test_search_core.py` | Search Core 专用测试（65 项） |
| `docs/phase1/PHASE1_4A_REPORT.md` | 本报告 |

**修改**

| 文件 | 改动 |
| :-- | :-- |
| `core/query/queries.py` | 新增只读 `_fts_available` / `_text_search_clause`；`_resource_where` 增加 `conn` 与 `query`；`ResourceQuery.list/count` 增加 `query=` 参数 |
| `core/query/__init__.py` | 导出检索路由的公共 API 与常量 |
| `core/__init__.py` | `__version__` 0.5.0 → 0.6.0；`__phase__` → `Phase 1.4-A (Search Core)` |
| `README.md` | 状态行与路线图同步 |

**未改动**：`core/database/schema.py`、`core/database/db.py`、`core/parsers/*`、
`core/scanner/*`（含 `store.py`）、`core/models/*`、`core/thumbnails/*`、`cli_query.py`、
`main.py`、`ui/*`、真实样本目录。

---

## 2. Search Core 的最终 API

### Query Layer（核心交付）

```python
ResourceQuery.list(
    *,
    # 现有筛选（全部保留）
    resource_type=None, game=None, card_marker=None, library_id=None,
    scan_status=None, needs_review=None, mod_guid=None, plugin_guid=None,
    author_id=None, property_category=None, has_mods=None,
    # Phase 1.4-A 新增
    query: str | None = None,
    # 现有排序 / 分页
    order_by="id", descending=False, limit=None, offset=0,
) -> list[ResourceSummary]

ResourceQuery.count(..., query: str | None = None) -> int
```

`query` 与所有结构化筛选是 **AND** 关系；`None` / `""` / 纯空白不追加任何文本条件，
行为与改动前的 `list/count` 完全一致。

### 检索路由（`core/query/search.py`，公共导出）

```python
FTS_MIN_LENGTH = 3
SEARCH_MODE_NONE / SEARCH_MODE_LIKE / SEARCH_MODE_FTS

normalize_query(value) -> str | None
plan_search(value, *, fts_available: bool) -> SearchPlan   # .text / .mode / .is_active
like_pattern(text) -> str                 # 转义 % / _ / \ 后的 '%...%'
fts_match_expression(text) -> str         # 安全短语表达式 '{display_name name} : "..."'
```

> `search.py` **不接收连接、不执行 SQL**；SQL 的拼装与执行仍全部留在
> `queries.py` 的只读护栏（`_execute_select`）之内。

---

## 3. 查询路由规则

| 查询 | 追加的条件 | 说明 |
| :-- | :-- | :-- |
| `None` / `""` / 纯空白 | 无 | 与改动前行为一致 |
| 1–2 字 | `LIKE '%q%'`（name / display_name）+ 作者关系 LIKE | FTS5 trigram 只索引 ≥3 字子串 |
| ≥ 3 字（FTS 可用） | `resources_fts MATCH` + 作者关系 LIKE | 长查询走索引 |
| 任意长度（FTS 不可用） | 全部退化为 LIKE | 见 §6 |

长度按 **Unicode 字符数**计算（CJK 与 ASCII 一致，不看字节）。
实际编译进 WHERE 的片段形如：

```sql
(  <name/display 条件>                                     -- FTS 或 LIKE
   OR EXISTS (SELECT 1 FROM resource_authors ra
              JOIN authors a ON a.id = ra.author_id
              WHERE ra.resource_id = r.id
                AND (a.name LIKE ? ESCAPE '\' OR ra.raw_name LIKE ? ESCAPE '\'))
)
```

---

## 4. FTS / LIKE 的实现方式

- **不新建、不重建 FTS 表**：复用既有 `resources_fts`（FTS5 trigram，`content='resources'`）
  与既有触发器；本阶段没有触碰 `schema.py` / `db.py`。
- **FTS 路径**：

  ```sql
  r.id IN (SELECT rowid FROM resources_fts WHERE resources_fts MATCH ?)
  ```

  MATCH 参数是 `fts_match_expression(text)`，即 `{display_name name} : "<短语>"`。
  用 **列集合**限定 `display_name` / `name`，使 FTS 与 LIKE 两路覆盖**同样的列**
  （FTS 表里还有 `author`/`series`/`description`/`notes`，其中 `author` 是死列，
  其余基本为空；显式限定列可避免将来语义漂移）。
- **LIKE 路径**：

  ```sql
  (r.name LIKE ? ESCAPE '\') OR (r.display_name LIKE ? ESCAPE '\')
  ```

  模式由 `like_pattern(text)` 生成，`%` / `_` / `\` 被转义成字面量。
- **FTS 可用性判定 `_fts_available(conn)`**：只读 `app_meta.fts_enabled`（须为 `'1'`）
  且 `sqlite_master` 中存在 `resources_fts`；任何缺失/读取失败都返回 `False`（退化为 LIKE）。

---

## 5. 作者搜索实现方式

- **只经关系表**：`resource_authors` JOIN `authors`，用 `EXISTS` + LIKE 匹配
  `authors.name` 与 `resource_authors.raw_name`。
- **绝不使用 `resources.author`**：该列是 v1 死列，Phase 1.2 起不再写入。
  测试显式断言 `resources.author` 全为空，作者命中只能来自关系表。
- 作者这一路**始终用 LIKE**（与查询长度无关），因此 FTS 是否启用都不改变作者搜索语义。

---

## 6. FTS fallback 行为

- 触发条件：`app_meta.fts_enabled != '1'`，或 `resources_fts` 表不存在，或读取失败。
- 行为：**所有长度**的查询都走 LIKE，结果与 FTS 路径**逐行一致**（有测试断言）。
- 只读：判定过程只 SELECT，**不修改** `fts_enabled`（测试在查询前后核对取值不变）。

---

## 7. 测试数量与结果

新增 `tests/test_search_core.py`，共 **65** 项（含 parametrize）：

| 组 | 覆盖 |
| :-- | :-- |
| 纯函数 | `normalize_query` / `plan_search` 路由 / `like_pattern` 转义 / `fts_match_expression` 转义 |
| 基本行为 | `None`、`""`、纯空白、ASCII、中文/日文子串 |
| 长度路由 | 1 字/2 字 → LIKE；3 字/4 字 → FTS；CJK 按字符计数 |
| 路由生效 | monkeypatch 断言 ≥3 字真的调用 FTS 表达式、2 字不调用 |
| FTS 回退 | `fts_enabled=0` 后结果与 FTS 一致，且状态不被修改 |
| 输入安全 | 引号、`NEAR(`、`*`、`:`、`{}`、`()`、`%`、`_`、多词、中英混合等不抛异常、不扩大结果 |
| 作者搜索 | 关系命中、`raw_name` 命中、大小写不敏感、FTS 关闭仍命中 |
| 组合 | `query` + type / library / needs_review / property_category / has_mods |
| 排序分页 | `query` + `order_by` + `limit/offset`；`list` 与 `count` 语义一致 |
| 只读不变量 | `total_changes`、`needs_review`、`app_meta` 全表前后不变 |
| 真实样本 | 见 §8 |

**全量 pytest 结果：**

```text
395 passed in 19.47s
0 failed / 0 xfailed        （基线 330 + 新增 65）
```

---

## 8. 真实样本验证结果

样本：`G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike`（22 卡 + 13 zipmod）。
扫描进**临时库**后验证（不写真实样本）：

```text
fts_enabled True    resources_fts 行数 35    resources 35

「さやか」(3 字) → FTS  → 命中资源 [4]
「さや」  (2 字) → LIKE → 命中资源 [4]
「佐倉杏子」(4 字) → FTS → 命中资源 [3]
「杏子」  (2 字) → LIKE → 命中资源 [3]
作者 「Evaan」      → 命中 5 个资源（经 resource_authors + authors）

FTS 关闭（fts_enabled=0）后，上述查询结果与 FTS 路径完全一致：True
```

### ⚠️ 一个重要事实发现（需要你决策，本阶段未扩范围）

指令要求验证「沙耶香」「沙耶」「佐仓杏子」。实测这三串**不属于可搜索字段**：

- 真实卡片的**文件名**是中文（`... 美树沙耶香.png` / `... 佐仓杏子.png`）；
- 但卡片内解析出的 `name`（来自 `Parameter` 的 lastname/firstname）是**日文**：
  `美樹さやか`（U+7F8E U+6A39 U+3055 U+3084 U+304B）与
  `佐倉杏子`（U+4F50 U+5009 U+674F U+5B50）。
- 注意「仓/倉」是**不同字符**，所以「佐仓杏子」不会命中「佐倉杏子」。

Search Core 的搜索字段是 `resources.name` / `resources.display_name`（+ 作者关系），
**不含** `file_path` / `relative_path`，因此按文件名串搜索不会命中。
这是既有 schema/query 语义的边界，不是实现缺陷；是否把路径纳入检索属于**扩大范围**，
本阶段**没有做**（若做，还需要处理「路径走 LIKE、名称走 FTS」造成的 FTS/LIKE 不一致，
详见 §14）。

---

## 9. 只读不变量验证

- 合成库：`total_changes` 在批量检索前后不变；`needs_review` 全部行值不变；
  `app_meta` 全表键值不变（有测试断言）。
- 真实样本（临时库）：检索前后 `total_changes` 保持 `2406 → 2406`；`needs_review=1` 计数保持 0。
- 所有 SQL 仍经 `_execute_select`（只允许 `SELECT` / `WITH`）；本阶段未新增任何写语句。

---

## 10. schema 是否保持 v2

**保持 v2。** `SCHEMA_VERSION == 2`，`MIGRATIONS == [1, 2]`，无新增迁移、无新增列、
无新增表；FTS 表沿用既有 `resources_fts`，未重建。

---

## 11. 是否修改真实样本

**未修改。** 真实样本目录整树 sha256 在验证前后一致（36 个文件，`sha_before_after_equal True`）；
`sample_root` 会话夹具也在测试会话前后自动断言一次。

---

## 12. 是否发现 P0/P1/P2

- **P0：无。**
- **P1：无。**
- **P2（记录，未修）：**
  1. 搜索字段不含 `file_path` / `relative_path`，因此文件名串（如「沙耶香」）搜不到；
     而卡片解析名可能是日文（`美樹さやか`）。这是真实用户最容易困惑的点（见 §8）。
  2. `resources_fts` 的 `author` 列对应死列 `resources.author`，若将来有人用裸 `MATCH`
     会误以为作者可搜；本阶段用列集合限定 `{display_name name}` 规避，但 FTS 表本身仍冗余。
  3. 名称与文件名的中文/日文混用，导致「同一角色的两种写法」无法互搜（是否要同义词/多写法
     索引是后续产品决策，非本阶段范围）。

---

## 13. 本阶段没有做的事情

- 没有改 schema / 迁移 / FTS 表结构。
- 没有改 Parser / Scanner / ResourceStore / models。
- 没有改 `review_reasons` 语义，没有新增 review reason，没有改 `needs_review` 写入逻辑。
- 没有进入 GUI（未改 `ui/*`、`main.py`）。
- 没有新增 CLI 命令族（`cli_query.py` 未改；`query resources --search` 仍待你确认）。
- 没有实现标签 / Collection / 重复检测 / 批量文件操作 / 复杂自动分类。
- 没有引入外部 API / AI，没有联网。
- 没有把 `file_path` / `relative_path` 纳入检索（见 §12）。

---

## 14. 对 Phase 1.4-B 的建议

1. **先决策「搜索字段是否包含路径」**：若要把文件名串也搜到，正确做法是让
   **FTS 与 LIKE 覆盖同一组字段**（否则 FTS 开/关结果会不一致）。可选：
   - 方案 A：搜索字段固定为 `name`/`display_name`（+作者关系）——本阶段现状；
   - 方案 B：新增一个 `relative_path`/`file_path` 的检索列或独立 FTS 表——**需要 schema 变更**，
     必须单独评估（本阶段按约束未做）。
2. **libraries 只读查询**：左侧导航需要「库列表 + 资源/缺失/待确认计数」；建议在 Query Layer
   补一个只读 `LibraryQuery`，避免 UI 直接依赖写层 `LibraryStore`。
3. **「缺 MOD 的资源」筛选**：真实样本 `missing=134` 是最实在的管理痛点，建议在
   Query Layer 增加 `has_missing_mods` 之类的只读过滤（纯 EXISTS，不改 schema）。
4. **CLI 薄适配（待确认）**：可给既有 `query resources` 增加可选 `--search`，仅作为
   Query Layer 的展示适配，不新增命令族、不新增数据访问路径。
5. 仍**不建议**在 1.4 扩展 review 规则或做「已确认/已忽略」持久化（需 schema + 无真实数据驱动）。

---

### 附：验收对照

| 指令要求 | 结果 |
| :-- | :-- |
| `ResourceQuery.list/count(query=...)` | ✅ |
| 空查询等于原行为 | ✅ |
| 1–2 字 LIKE / ≥3 字 FTS | ✅ |
| 不重建 FTS 表 | ✅ 复用既有 `resources_fts` |
| FTS disabled → 全 LIKE 且结果一致 | ✅ |
| FTS 输入安全（引号/特殊字符/多词/混合） | ✅ 24 项参数化 |
| 作者经关系表、不依赖 `resources.author` | ✅ |
| 与现有筛选/排序/分页组合、list/count 一致 | ✅ |
| 只读（`total_changes` 等不变） | ✅ |
| 真实样本 sha256 不变 | ✅ |
| schema 保持 v2 | ✅ |
| 不进入 GUI / 不扩 CLI / 不改 review | ✅ |
