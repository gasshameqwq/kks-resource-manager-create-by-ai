# Phase 1.4-B.3 Report — Browse Read Model

> 版本：Phase 1.4-B.3 · schema v2（**未改动**）· 2026-10-06
>
> 目标：实现最小可用的 Browse Read Model，让未来 PyQt6 GUI **只调用 core 层**即可完成
> 「Library 列表 → 资源列表（搜索/筛选/排序/分页）→ 详情」的组合，不需要自己拼接。

---

## 1. 实际修改文件

**新增**

| 文件 | 说明 |
| :-- | :-- |
| `core/query/browse.py` | `BrowserScope` / `ResourceListItem` / `BrowsePage` / `BrowseService` |
| `tests/test_browse.py` | Browse Read Model 测试（50 项） |
| `docs/phase1/PHASE1_4B3_REPORT.md` | 本报告 |

**修改**

| 文件 | 改动 |
| :-- | :-- |
| `core/query/__init__.py` | 导出 Browse 层的 4 个公共对象 |
| `core/__init__.py` | `__version__` → 0.8.0；`__phase__` → `Phase 1.4-B.3 (Browse Read Model)` |
| `README.md` | 状态行、路线图、文档表同步 |

**未改动**：`schema.py` / migrations、`db.py`、`parsers/*`、`scanner/*`（含 `store.py`）、
`models/*`、`library/store.py`、`thumbnails/*`、`query/dto.py`、`query/search.py`、
`query/queries.py`、`cli_query.py`、`main.py`、`ui/*`、真实样本。

> **版本说明**：指令写「从当前 0.6.1 递进」，但仓库实际当前版本是 **0.7.1**
> （1.4-A→0.6.0，1.4-A.1→0.6.1，1.4-B.1→0.7.0，1.4-B.2→0.7.1）。
> 本轮按实际递进到 **0.8.0**（新的 Browse 能力，minor bump）。

---

## 2. Browse 层的职责

`BrowseService` 只做两件事：**查询编排** 与 **行模型组合**。

- 左栏：`libraries()` → 直接复用 `LibraryQuery.list()`。
- 中栏：`page(scope, limit, offset, with_review_reasons)` → 用**同一个 scope** 调
  `ResourceQuery.count()` 与 `ResourceQuery.list()`，再补上行所需的跨实体信息。
- 右栏：`detail(id)` → 直接复用 `ResourceQuery.get()`。
- 便捷：`review_reasons(id)` → 直接复用 `ResourceQuery.review_reasons()`。

它**不重新定义**任何筛选语义、不改变 review reason 语义、不执行 preview、不持有状态。

---

## 3. 为什么 Browse 层没有 SQL

SQL 的唯一归属是 `LibraryQuery` / `ResourceQuery`（它们持有 `_execute_select` 只读护栏）。
如果 Browse 自己写 SQL：

- 会出现**第二份事实来源**，与 Query Layer 的筛选/分类语义漂移；
- 会绕过「所有查询集中在一处」的约定；
- 将来改 schema / 加筛选时需要改两处。

因此本层**只有编排**：`BrowseService` 只 import `LibraryQuery` / `ResourceQuery`，
源码中不存在 `.execute(`，也不含任何 `SELECT `（有测试断言这一点）。

---

## 4. 为什么没有修改 `ResourceSummary`

`ResourceSummary` 是「资源自身事实」的载体（`id / resource_type / name / display_name /
file_path / relative_path / extension / card_marker / file_size / modified_time /
library_id / scan_status / parse_status / needs_review / mod_count / usage_count /
plugin_count / author_count`）。列表行额外需要的三样都不属于 `resources` 行本身：

| 缺的信息 | 性质 | 归属 |
| :-- | :-- | :-- |
| Library 名 | 跨实体（`library_id → name`） | `ResourceListItem.library_name` |
| 作者名 | 跨关系表（`resource_authors` + `authors`） | `ResourceListItem.authors` |
| `has_missing_mods` 标记 | 派生 | **v1 不加**（只作为筛选） |

所以新增 `ResourceListItem` 承载前两者，`ResourceSummary` 保持完全不变（其它调用方
如 Search / CLI / ModQuery 都不受影响）。

---

## 5. list / count 的 scope 一致性

`BrowserScope.filters()` 是**唯一**的 scope → 参数转换点，返回 `ResourceQuery.count/list`
都能接受的 12 个筛选键（不含只作用于 list 的 `order_by` / `descending`）：

```python
filters = scope.filters()
total = self._resources.count(**filters)
rows  = self._resources.list(**filters, order_by=..., descending=..., limit=..., offset=...)
```

因此不可能出现「总数用一套条件、行用另一套条件」的漂移；调用方（GUI）也不再需要把
同一组参数拼两遍。测试里还有一条断言：`set(scope.filters()) <=` `ResourceQuery.count/list`
的签名参数集合，防止将来新增字段时漏配。

---

## 6. 作者与 Library 名的组合方式

- **Library 名**：`page()` 取本页所有 `library_id` 的去重集合，**一次性**调用
  `LibraryQuery.list()` 建立 `id → name` 映射（不对每行再查一次）。
  含 disabled Library（名字仍要能显示）；`library_id` 为 `None` 时 `library_name=None`。
- **作者名**：逐行调用 `ResourceQuery.authors(id)`，取 `name` 组成 **tuple**
  （保留 `0 / 1 / 多个` 与顺序，不压成字符串）。
  这是当前实现里的 N+1；按指令要求**本轮不做批量优化**（规模小，且需要实测证据再动）。

---

## 7. review_reasons 的可选加载

- `page(..., with_review_reasons=False)`（默认）**完全不查询** review reasons ——
  测试用 monkeypatch 断言 `ResourceQuery.review_reasons` 的调用次数为 0。
- `with_review_reasons=True` 时才逐行调用，且只针对**本页**（受 `limit` 约束，
  测试断言 `limit=3` 时只调用 3 次）。
- reason 的**语义**仍然 100% 来自 `ResourceQuery.review_reasons()`；Browse 不新增、
  不修改任何 reason。

---

## 8. PreviewService 为什么不进入 Browse

- `PreviewService` 是**文件系统派生的可丢弃缓存**，不是数据库读模型；
- 它的入参可以直接是 `ResourceSummary`（`PreviewService._resolve` 接受带
  `file_path` / `extension` / `resource_type` 的对象）；
- 若在列表查询里顺手生成缩略图，会把磁盘 IO / 解码放进查询路径，阻塞 UI。

因此分工是：**Browse 给出行模型（含 `ResourceSummary`），GUI 在后台按需调用
`PreviewService.get_or_generate(item.resource)`**。测试断言 `browse.py` 的 import
中不含 `core.thumbnails`，源码不依赖 PreviewService。

---

## 9. 测试结果

新增 `tests/test_browse.py`，共 **50** 项，覆盖：

空库 / 单库 / 多库 / disabled 库 / `resource_count` / 空结果 /
单页 / 多页 / offset / `total` 与 items 一致 / `filters()` 单一转换点 /
search（含按 `relative_path` 命中）/ `resource_type` / `game` / `library_id` /
`needs_review` / `has_mods` / `has_missing_mods` / `mod_guid` / `plugin_guid` /
`author_id` / `property_category` / `order_by` / `descending` /
`page()` 与 `ResourceQuery.count/list` 完全一致（顺序与 ID）/
library_name（含 disabled 与 None）/ 作者 0-1-多 /
`with_review_reasons` 默认不查询、按需查询、受 limit 约束 /
detail 复用 `ResourceQuery.get()` / 不存在 id 返回 None /
review_reasons 转发 / 只读不变量（`total_changes`、`needs_review`、`app_meta`、
资源与关系表行数）/ 无自有 SQL 与无 Preview 依赖 / schema v2。

```text
500 passed in 24.25s
0 failed / 0 xfailed        （1.4-B.2 基线 450 + 新增 50）
```

---

## 10. 真实样本结果（临时库，只读）

样本：`G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike`。11 项检查全部通过：

```text
1  default BrowsePage        total 35 / items 35
2  libraries                 1 个（resource_count 35）
3  搜索「沙耶香」            total 1（命中资源 id 4，经 relative_path）
4  has_missing_mods=True     total 14 / items 14
5  分页                      total 35 / 最后一页 5 条（limit 10, offset 30）
6  作者显示                   author=Evaan → 5 条，authors 为 ('Evaan',)；library_name 已填
7  with_review_reasons=True  本页 5 条全部为 ()（样本 needs_review=0，未造数据）
8  ResourceDetail             id 4：mods 1 条、authors []（该卡无 marco.authordata）
9  Browse 全流程             total_changes 2406 → 2406（不变）
10 schema                    SCHEMA_VERSION 2 / MIGRATIONS [1, 2]
11 真实样本 36 文件           sha256 前后一致；size + mtime_ns 前后一致
```

> `needs_review = 0` 是样本的客观状态，**没有**为了验证 review reason 而人为造数据；
> 该逻辑由合成测试覆盖。

---

## 11. 只读不变量

- 合成库：多次 `libraries / page / detail / review_reasons` 前后，`total_changes` 不变，
  `needs_review` 各行不变，`app_meta` 不变，`resources / libraries / mods /
  resource_mod_usages` 行数不变。
- 真实样本（临时库）：`total_changes` 保持 `2406 → 2406`；`needs_review=1` 计数保持 0。
- Browse 层不执行任何写语句（它没有 SQL）；底层 `ResourceQuery / LibraryQuery` 仍在
  `_execute_select` 只读护栏内。

---

## 12. schema 与真实样本

- **schema 仍为 v2**：`SCHEMA_VERSION == 2`、`MIGRATIONS == [1, 2]`；
  未新增字段/表/索引/view，未改 `resources_fts`。
- **真实样本未修改**：仅只读（扫描到临时库）；sha256（36 文件）与
  `size + mtime_ns` 前后一致，未 touch、未生成临时文件。

---

## 13. 未做的 P2 / 未来优化

1. **作者 N+1**：`page()` 逐行取作者（`ResourceQuery.authors`）。本轮按指令保持简单；
   若将来页面规模导致实测变慢，再在 `ResourceQuery` 加批量方法（仍只读、零 schema）。
2. **`has_missing_mods` 行内标记**：v1 只作为筛选 / 「缺 MOD」专门视图，不进 DTO。
   若将来通用列表需要 badge，再单独评估（可能需要 `ResourceSummary` 之外的字段）。
3. **review reasons 批量加载**：同上，当前只在「待确认」视图按需逐行取。
4. **排序白名单**：`order_by` 仍只有 `id / name / display_name / file_size /
   modified_time / created_at / updated_at`；按作者或缺失状态排序未实现。
5. 早期 P2（`resources_fts.author` 死列、`metadata_json.plugin_count` 冗余、
   跨语言/别名搜索、`LibraryQuery.resolve`）维持不变。

---

## 14. 本轮明确没有做

- 没有进入 GUI（`ui/*`、`main.py` 未动）。
- 没有改 schema / migration / view / cache / persistence。
- 没有做 alias / 跨语言 / 模糊 / AI 搜索。
- 没有 health score，没有把 missing MOD / orphan / review 合并。
- 没有为 GUI 加持久化字段（favorite 等）。
- 没有改 `ResourceSummary` / `ResourceDetail`。
- 没有在 Browse 层调用 `PreviewService`，没有实现缩略图生成 / 后台线程 / 进度。
- 没有新增批量 Query API（N+1 优化留待有实测证据时再做）。

---

### 附：验收对照

| 指令要求 | 结果 |
| :-- | :-- |
| `BrowserScope` 字段与 ResourceQuery 语义一致 | ✅ |
| `ResourceListItem`（不改 ResourceSummary；authors 为 tuple；review_reasons 默认空） | ✅ |
| `BrowsePage`（items/total/limit/offset） | ✅ |
| `BrowseService.libraries/page/detail/review_reasons` | ✅ |
| Browse 层无自有 SQL | ✅（测试断言无 `.execute(` / 无 `SELECT `） |
| 只复用 `LibraryQuery` / `ResourceQuery` | ✅（测试断言 import） |
| `page()` 的 list/count 用同一 scope | ✅（`filters()` 单一转换点 + 测试） |
| Library 名一次映射、不逐行查 | ✅ |
| 作者按行取、保留 tuple | ✅ |
| `with_review_reasons` 默认不查、按需查、受 limit 约束 | ✅ |
| 不调用 PreviewService | ✅ |
| 不新增 schema/migration/view/cache/badge/health/alias | ✅ |
| 新增测试全部通过 | ✅ 50 项 |
| 全量 pytest 0 failed / 0 xfailed | ✅ 500 passed |
| 真实样本 11 项验证 | ✅ 全部通过 |
| schema v2 / migrations 不变 | ✅ |
| `__version__` / `__phase__` | ✅ 0.8.0 / `Phase 1.4-B.3 (Browse Read Model)` |
