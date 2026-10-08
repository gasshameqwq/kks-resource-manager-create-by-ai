# Phase 3.2 — Implementation Contract（Tag System）

> 文档类型：**实施前冻结的 Implementation Contract —— FROZEN / PASS（Freeze 审计通过）**
> 日期：2026-10-08
> 权威层级（从高到低）：
> 1. `docs/phase3/PHASE3_0_CONTRACT.md`（Phase 3 首期 Architecture / Scope Contract，最高权威）
> 2. `docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md`
> 3. `docs/phase3/PHASE3_2_TAG_SYSTEM_ARCHITECTURE_DESIGN.md`（本阶段设计）
> 4. 本文件 —— Phase 3.2 实施契约，**不得与上级冲突**
> 前置：Phase 3.1 = CLOSED / PASS（tag `phase-3.1-closed`，HEAD `99aa0d1`）
> 本文件：**只做实施前冻结。未修改任何功能代码 / schema / migration / 测试 / CLI / GUI。**

> **状态声明**：本文件已 **FROZEN / PASS**（Design Revision PASS → Contract Freeze 审计通过）。
> 冻结的是 Phase 3.2 的实施范围、所有权、写边界、语义与测试不变式。
> Phase 3.2 implementation 已 **COMPLETE / AUDIT PASS**（Final Audit PASS）；
> Phase 3.2 **尚未 CLOSED**（Git closure 未执行）；实现必须严格按本文件执行。

> **冻结声明**：本文件冻结 Phase 3.2（Tag System）的**范围、所有权、写边界、语义与测试不变式**。
> 任何扩大 3.2 范围的行为，必须先走 `PHASE3_0_CONTRACT.md` §16 变更控制
> （新增评审 + 更新 Contract + 用户确认）。

---

## 0. 本阶段唯一目标

```text
在已有的「用户数据写入边界」之上，建立 Tag 组织机制：
用户可以创建 / 重命名 / 删除 Tag，并把 Tag 赋给 / 移出 Resource；
Favorite 通过保留系统 Tag 表达；
所有 Tag 事实可被 Query Layer 只读获取。
```

交付物是 **domain / service / query foundation**，不是用户入口（入口属 Phase 3.5）。

---

## 1. Scope（Phase 3.2 只负责这些）

1. **Tag model**：`id` / `name` / `name_key`（UNIQUE）/ `color` / `category` / timestamps。
2. **Tag CRUD**：`create_tag` / `rename_tag` / `delete_tag`。
3. **Resource ↔ Tag**：`assign_tag` / `unassign_tag`（+ 只读 list）。
4. **Collision**：`name_key` 归一化、create/rename 冲突拒绝、大小写不敏感、空白 / Unicode 规则。
5. **System Tag**：保留 key 注册表；system Tag 不可 rename / delete；用户不可占用其 key。
6. **Favorite**：保留系统 Tag（`name_key='favorite'`），持久化只经 `resource_tags`。
7. **TagWriteService**：`tags` / `resource_tags` 的唯一 runtime writer。
8. **TagQuery**：只读 read model（Tag / Resource↔Tag / Favorite 基础事实）。
9. **Ownership guard 扩展**：`tags` / `resource_tags` 写路径守卫。
10. **Schema 冻结**：零变更。

### 1.1 Tag Scope（GLOBAL — 冻结）

```text
Tag scope = GLOBAL organization data（非 per-library）。
```

- `tags.name_key` 全局唯一；**不增加 `library_id`**；
- 一个 Tag 可标注任意 library 以及 `library_id IS NULL` 的资源；
- per-library Tag **不属 Phase 3.2**，属未来 schema / architecture change；
- 依据见设计文档 §4（schema v2 不可表达 per-library；全局 identity 与 `file_path_key` 一致）。

---

## 2. Explicit Non-Goals（Phase 3.2 明确不做）

| # | 排除项 |
| :-- | :--- |
| 1 | Search Query Model |
| 2 | `field:value` / `tag:` / `favorite:` 文本语法 |
| 3 | AND / OR / NOT / 全文搜索 / 统一搜索语法 |
| 4 | tag filtering / favorite filtering / BrowserScope tag filtering |
| 5 | GUI Tag Management / GUI Favorite UI |
| 6 | CLI / GUI 用户入口与最终 UX（属 Phase 3.5） |
| 7 | 修改 `main.py` / `cli_query.py` / `ui/*`（除 guard 测试所必需的纯测试修改） |
| 8 | Collection |
| 9 | 自动分类 / 自动打标 / Tag ↔ Resource Type 自动转换 / Tag ↔ Usage Category 自动转换 |
| 10 | AI / 语义 / 感知分类 |
| 11 | 文件移动 / 改名 / 删除 / 下载 / 联网 |
| 12 | schema v3 / migration / 新表 / 新列 / 新索引 |
| 13 | Scanner / Parser 行为修改 |
| 14 | `origin='auto'` 的任何使用 |

---

## 3. Ownership Table（冻结）

| Data | Owner | 唯一 Writer |
| :--- | :--- | :--- |
| `tags`（user Tag） | User | `TagWriteService` |
| `tags`（reserved system Tag 定义行） | System（bootstrap） | `TagWriteService.ensure_system_tags()` |
| `resource_tags` | User | `TagWriteService` |
| `resources.display_name` / `notes` / user type + `type_source` | User | `ResourceWriteService`（不变） |
| `resources` / `mods` / 关系 machine facts | Machine | `ResourceStore`（不变） |

**冻结结论**：

```text
TagWriteService = tags / resource_tags 唯一 runtime writer
```

**禁止直接写 `tags` / `resource_tags` 的角色**：

```text
Scanner · Parser · ResourceWriteService · Query Layer · GUI · CLI
```

- Scanner / Parser 继续**只产生 machine facts**；
- 3.2 所有 Resource ↔ Tag assignment：`origin = 'user'`；
  `origin = 'auto'` 保留 schema 能力但**不使用**。

---

## 4. Frozen Semantics（冻结语义）

### 4.1 Identity

```text
tags.id       = surrogate identity
tags.name_key = normalized business identity（全局 UNIQUE）
```

`resource_tags.tag_id` 引用 surrogate `id`；`name_key` 用于去重 / 查名。

### 4.2 Normalization

复用现有 `core.database.db.normalize_name_key()`：

```text
name_key = (name or "").strip().casefold()
```

- 大小写不敏感；
- 仅去首尾空白，内部空白保留；
- **不引入** NFC/NFKC；
- 空白 / 空串 / 非字符串 ⇒ `InvalidTagValue`。

### 4.3 Collision

```text
create collision → reject（TagNameConflict）
rename collision → reject（TagNameConflict）
```

- 禁止自动 merge；
- create **不**静默复用既有 Tag；
- 保留系统 key 冲突 ⇒ `ReservedTagName`；
- DB `UNIQUE(name_key)` 兜底，`IntegrityError` 防御性映射为 `TagNameConflict`。

### 4.4 System Tag

```text
reserved key  = favorite
display name  = Favorite
name_key      = favorite
```

System Tag：

- **不可 rename**（`SystemTagImmutable`）；
- **不可 delete**（`SystemTagImmutable`）；
- 普通用户**不可创建相同 reserved key**（`ReservedTagName`）；
- 允许 assign / unassign（与普通 Tag 同一路径）。

system 判定 = `name_key ∈ RESERVED_SYSTEM_TAG_KEYS`（**不新增 `is_system` 列**）。

**System Tag Bootstrap（Phase 3.2 = lazy / on-demand；EXEC-1 决策）**：

- 系统 Tag 由 `TagWriteService` **按需**保证存在；`ensure_system_tags()` 是**幂等的、权威的** bootstrap seam；
- `set_favorite()` **必须在其自身事务内**确保 Favorite 系统 Tag 存在（不得依赖启动期预置）；
- fresh DB 若尚未发生任何 Tag 写入，可以**暂时没有** `favorite` 行；此时
  `TagQuery.system_tags()` 可以为空，`TagQuery.is_favorite(resource_id)` 必须返回 `False`；
- **startup eager bootstrap 不属于 Phase 3.2**，属后续 CLI / GUI integration；
- **禁止**通过修改 `database.initialize()` 实现该 bootstrap（不得扩大 database / schema 职责）。

### 4.5 Favorite

```text
唯一持久化事实 = resource_tags
```

- 禁止 `resources.favorite` 列；
- 禁止 `favorites` 表；
- `set_favorite(r, True)` ≡ `assign_tag(r, favorite_tag)`；
- `set_favorite(r, False)` ≡ `unassign_tag(r, favorite_tag)`；
- Favorite 与普通 Tag 使用**同一 persistence / ownership / transaction** 路径。

### 4.6 Assignment

```text
origin = 'user'
assign   = idempotent
unassign = idempotent
```

### 4.7 Delete

- 普通 Tag 删除：`resource_tags` 关联经既有 **FK cascade** 清理；
- System Tag：**不允许删除**；
- 删除不触碰任何文件、不触碰 `resources` 的 machine facts。

---

## 5. Write Boundary（冻结）

```text
TagWriteService 是 Phase 3.2 tags / resource_tags 写入的唯一 runtime boundary。
```

| 维度 | 冻结语义 |
| :--- | :--- |
| 事务边界 | 单个 public 写方法 = 一个 `db.transaction`；失败整体回滚并原样抛出 |
| 幂等 | `assign` / `unassign` / `set_favorite` / `ensure_system_tags` 幂等；`create` 不幂等（冲突必须报错） |
| 存在性 | 存在性优先：resource 不存在 ⇒ `ResourceNotFound`；tag 不存在 ⇒ `TagNotFound` |
| 冲突 | 见 §4.3 |
| 错误 | 见 §6；不吞异常、不静默降级 |

### 5.1 机器 / 其它 writer 不得写 Tag

```text
Scanner · Parser · ResourceWriteService · Query Layer · GUI · CLI
    → 永不直接写 tags / resource_tags
```

### 5.2 Ownership guard 扩展（实现阶段）

- `tags` / `resource_tags` 的 `INSERT` / `UPDATE` / `DELETE` 只允许出现在
  `core/app/tag_write.py`；
- Scanner 运行时 trace 必须证明扫描过程不写 Tag 表；
- guard 正则需接受 `INSERT OR IGNORE INTO tags …` 形式
  （既有 resources 正则未覆盖 `OR IGNORE`，建议一并收紧，属**纯测试**变更）。

---

## 6. Error Semantics（冻结）

```text
TagWriteError(Exception)                 # 基类
 ├─ TagNotFound(tag_id)
 ├─ TagNameConflict(name_key)
 ├─ ReservedTagName(name_key)
 ├─ SystemTagImmutable(tag_id)
 └─ InvalidTagValue(field, value)
```

- 资源不存在 ⇒ 复用 `core.app.resource_write.ResourceNotFound`；
- 失败 ⇒ 回滚 + 原样抛出；
- Query Layer 读 API：未找到 ⇒ `None` / 空列表（不抛「未找到」异常）。

---

## 7. API Contract（冻结）

### 7.1 `TagWriteService`（`core/app/tag_write.py`）

```text
create_tag(name: str, *, color: str | None = None, category: str | None = None) -> int
    # 返回新 Tag 的 id；name_key = normalize_name_key(name)
    # 空白 => InvalidTagValue；reserved => ReservedTagName；已占用 => TagNameConflict

rename_tag(tag_id: int, new_name: str) -> None
    # 不存在 => TagNotFound；system => SystemTagImmutable
    # 空白 => InvalidTagValue；reserved => ReservedTagName
    # 冲突 => TagNameConflict；新 key == 自身 key => 允许（幂等）
    # 写 name = new_name.strip()、name_key、updated_at = datetime('now')

delete_tag(tag_id: int) -> None
    # 不存在 => TagNotFound；system => SystemTagImmutable
    # DELETE tags；resource_tags 经 FK cascade 清理

assign_tag(resource_id: int, tag_id: int) -> None
    # resource 不存在 => ResourceNotFound；tag 不存在 => TagNotFound
    # INSERT OR IGNORE INTO resource_tags(resource_id, tag_id, origin) VALUES (?, ?, 'user')
    # 幂等

unassign_tag(resource_id: int, tag_id: int) -> None
    # resource 不存在 => ResourceNotFound；tag 不存在 => TagNotFound
    # DELETE FROM resource_tags WHERE resource_id = ? AND tag_id = ?
    # 幂等（未赋过也为成功）

set_favorite(resource_id: int, favorite: bool) -> None
    # resource 不存在 => ResourceNotFound
    # ensure_system_tags() → 取 favorite tag id
    # favorite=True  => assign 语义（幂等）
    # favorite=False => unassign 语义（幂等）

ensure_system_tags() -> None
    # 对每个 SYSTEM_TAGS：INSERT … ON CONFLICT(name_key) DO NOTHING（幂等）
    # = 权威 bootstrap seam（Phase 3.2 采用 lazy / on-demand；
    #   启动期 eager bootstrap 属后续 CLI / GUI integration）
```

### 7.2 `TagQuery`（`core/query/tag_queries.py`，只读）

```text
list()                    -> list[TagSummary]      # 全部 Tag（含 system）
get(tag_id)               -> TagSummary | None
find_by_name(name)        -> TagSummary | None     # 精确 name_key 匹配（空 => None）
for_resource(resource_id) -> list[TagSummary]
resource_ids(tag_id)      -> list[int]
system_tags()             -> list[TagSummary]
is_favorite(resource_id)  -> bool
favorite_resource_ids()   -> list[int]
```

**`resolve()` 已删除**，不在 Phase 3.2 API 内（见设计文档 §13.2）。

### 7.3 DTO（additive）

```text
TagSummary(id, name, name_key, color, category, is_system, resource_count=0)
ResourceDetail += tags: tuple[TagSummary, ...] = ()
ResourceDetail += is_favorite: bool = False
```

- 追加字段**置于末尾、带默认值**；既有构造 / 既有调用保持有效（Phase 2.3 / 3.1 惯例）；
- `is_system` 为派生值（`name_key ∈ RESERVED_SYSTEM_TAG_KEYS`），非持久列。

### 7.4 TagQuery — Forbidden Surface（冻结）

Phase 3.2 `TagQuery` **不得**包含：

```text
resolve()
tag:
favorite:
field:value
AND / OR / NOT
Search Query Model
BrowserScope tag filtering
```

以上全部属于未来阶段（Phase 3.3+）。`TagQuery` 仅提供 §7.2 列出的只读基础事实。

### 7.5 依赖方向（防 import cycle）

```text
core/query/queries.py      →   core/query/tag_queries.py    （单向）
core/query/tag_queries.py  ✗→   core/query/queries.py        （禁止反向 import）
```

`TagQuery` 只依赖 `core.query.dto` / `core.models.tags` 与只读 SQL，
不得反向依赖 `queries.py`；全部数据库访问经现有 `_execute_select`（仅 `SELECT` / `WITH`）。

---

## 8. Derived `resource_count`（冻结）

```text
TagSummary.resource_count = Query Layer 读取时计算的 derived value
                          = 该 Tag 的 resource_tags 关联资源数
```

- 不落库；**不新增** `tags.resource_count` 列；**不加** counter cache；
- 必须与 `len(resource_ids(tag_id))` 一致；
- implementation 须避免 Tag list 的 N+1 COUNT（一次聚合查询）。

---

## 9. `color` / `category`（冻结）

- 只是**现有 Tag metadata**，可读写暴露；
- **不**引入新的 taxonomy / classification semantics；
- `category` **不得**被解释为 / 自动影响 Resource Type、Usage Category、Search field、Taxonomy；
- 不参与 identity / collision / assign；
- 可选文本按 `None`/空白 ⇒ `NULL`、否则 `strip()` 保存。

---

## 10. Query Boundary（不进入 Search）

```text
TagQuery = read model（只读基础事实）
TagQuery ≠ Search Engine
```

Phase 3.2 **不**提供：搜索语法、`tag:` / `favorite:` 字段、布尔组合、过滤接线、排序语义。
Query Layer 只经 `_execute_select`（`SELECT` / `WITH`）读取。

---

## 11. Implementation Steps（仅计划，不执行）

```text
Step 1  core/models/tags.py：SystemTagSpec / SYSTEM_TAGS / RESERVED_SYSTEM_TAG_KEYS / is_system_tag_key()
Step 2  core/app/tag_write.py：TagWriteService + 异常
Step 3  core/app/__init__.py：导出
Step 4  core/query/dto.py：TagSummary + ResourceDetail 追加字段
Step 5  core/query/tag_queries.py：TagQuery
Step 6  core/query/queries.py + browse.py：ResourceQuery.get 填充、BrowseService 只读转发
Step 7  core/query/__init__.py：导出
Step 8  System Tag bootstrap（lazy / on-demand）：ensure_system_tags() 为幂等权威 seam；
        set_favorite() 在自身事务内保证 favorite；不修改 database.initialize()；
        startup eager bootstrap 属后续 CLI / GUI integration（不在 Phase 3.2）
Step 9  tests/test_tag_write.py + tests/test_tag_query.py
Step 10 tests/test_ownership_guard.py + tests/test_gui_smoke.py 扩展
Step 11 文档：LOG / Closure（实现后）
```

**Step 中不含 CLI / GUI 用户入口**（D6）；Phase 3.2 不修改 `main.py` / `cli_query.py` / `ui/*`
（guard 测试除外）。

---

## 12. Test Invariants（冻结）

```text
T-A  name_key = normalize_name_key(name)；大小写不敏感；空白名被拒绝
T-B  create 冲突 ⇒ TagNameConflict（不合并、不静默复用）
T-C  rename 到已占用 key ⇒ TagNameConflict；rename 系统 Tag ⇒ SystemTagImmutable
T-D  delete 系统 Tag ⇒ SystemTagImmutable；delete 普通 Tag 级联清理 resource_tags
T-E  assign / unassign 幂等；origin 恒为 'user'
T-F  Favorite 持久化只经 resource_tags（无第二套机制）；set_favorite 幂等；等价于 assign/unassign 保留系统 Tag；用户不能创建 'favorite'
T-G  Scanner 重扫后 resource_tags 保留；机器 writer 不写 Tag
T-H  仅 TagWriteService 写 tags / resource_tags
T-I  TagQuery 只发 SELECT / WITH；不写库、不创建系统 Tag
T-J  find_by_name 精确匹配（空 / 未知 ⇒ None）
T-K  resource_count == len(resource_ids(tag_id))
T-L  DTO 追加字段带默认值；既有构造 / 既有测试不回归
T-M  SCHEMA_VERSION==2 / MIGRATIONS=={1,2} / 16 表不变
```

---

## 13. Definition of Done（FROZEN）

Phase 3.2 视为完成，当且仅当：

1. `TagWriteService` 是 `tags` / `resource_tags` 的**唯一** runtime writer；
2. `TagQuery` 只读可用，**不含** `resolve()`，不进入 Search 语义；
3. `TagSummary` / `ResourceDetail`（tags / is_favorite）为 additive、向后兼容；
4. Favorite 只经保留系统 Tag + `resource_tags`，无第二套持久化；
5. §12 不变式全部有自动化测试并通过；
6. `SCHEMA_VERSION == 2`，无 migration / 新表 / 新列 / 新索引；
7. 既有测试全绿（基线 ≥ 当前）；
8. 未越界实现 §2 任何 Non-Goal；未引入 CLI / GUI 用户入口。

---

## 14. 变更控制

```text
1. 本 Contract（冻结版）确认后，任何扩大 Phase 3.2 范围的行为必须走
   PHASE3_0_CONTRACT.md §16（评审 + 更新 Contract + 用户确认）。
2. 【FROZEN】决策不得在实现阶段被顺带更改。
3. §2 Non-Goals 不得被「顺手一起做」。
4. 本 Contract 不修改 Phase 3.0 / 3.0.2 / 3.1 既有契约，不重新打开 Phase 3.0；
   不改动 `phase-3.0-closed` / `phase-3.1-closed` tag。
5. 状态：**FROZEN / PASS**（Design Revision PASS → Contract Freeze 审计通过）。
```

---

## 15. Explicit Phase 3.3 Boundary

留给 Phase 3.3（Search & Query Foundation）：

```text
Search Query Model
field:value
tag:
favorite:
AND / OR / NOT
full text search
tag filtering / favorite filtering
BrowserScope tag filtering
unified search syntax
```

> **TagQuery 暴露 Tag ≠ Search 已实现。**

---

## 16. Schema Decision（冻结）

```text
SCHEMA_VERSION = 2
MIGRATIONS = {1, 2}
NO MIGRATION REQUIRED
```

冻结：**不新增 migration、不修改现有 schema**；不得新增：

```text
is_system
resource_count
library_id
favorite column
favorites table
```

依据（真实仓库）：`core/database/schema.py` 当前 `SCHEMA_VERSION == 2`、`MIGRATIONS == {1, 2}`；
`tags` / `resource_tags` 现有结构（`name_key UNIQUE`、PK 去重、`origin` CHECK、双向 cascade）足够。

---

## 17. Additional Consistency Verifications（冻结）

| # | 检查 | 冻结结论 |
| :-- | :--- | :--- |
| 1 | `TagQuery` 不反向依赖 `queries.py` | 单向依赖，避免 import cycle（见 §7.5） |
| 2 | `TagQuery` 所有 DB 访问经过只读 boundary | 经 `_execute_select`（仅 `SELECT` / `WITH`） |
| 3 | `TagWriteService` 不承担 `ResourceWriteService` 职责 | 只写 `tags` / `resource_tags`，绝不写 `resources` |
| 4 | Scanner / Parser 不产生 Tag | 继续只产 machine facts |
| 5 | `origin='auto'` 保留但不用 | 3.2 恒 `origin='user'` |
| 6 | 不修改 `main.py` / `cli_query.py` / `ui/*` 以提供 Tag UX | 仅允许 guard 测试的纯测试修改 |
| 7 | 不实现 GUI Tag 管理 | ✅ Non-Goal |
| 8 | 不实现 GUI Favorite UI | ✅ Non-Goal |
| 9 | 不实现 CLI Tag UX | ✅ Non-Goal |
| 10 | 不实现 Search / Tag filtering | ✅ Non-Goal |

---

## 18. Freeze Record

```text
Design Revision            → PASS
Implementation Contract    → FROZEN / PASS（本文件）
Phase 3.2 implementation   → COMPLETE / AUDIT PASS
Phase 3.2 CLOSED           → 未达成（需 Git 收尾）
```

冻结时点：2026-10-08；依据 HEAD `99aa0d1`（`phase-3.1-closed`）。
冻结审计对契约文档做了**完整性补齐**（新增 §1.1 / §7.4 / §7.5 / §16 / §17 / §18，
强化 §7.3 / T-F 与状态标记），**未改变任何已冻结语义**，未扩大 scope（见 `PHASE3_2_LOG.md` §17）。

> **EXEC-1 Reconciliation（2026-10-08）**：原 §11 Step 8 要求「`database.initialize()` 之后立即调用
> `ensure_system_tags()`」，与 §2 Non-Goal #7（禁止修改 `main.py` / `cli_query.py` / `ui/*`）冲突。
> 经用户裁决采用 **Option A：Accept Lazy Bootstrap**。本 Contract 仅就此做最小文字澄清
> （§4.4 / §7.1 / §11 Step 8）：Phase 3.2 = **lazy / on-demand** system-tag bootstrap；
> `ensure_system_tags()` 为幂等权威 seam；`set_favorite()` 在自身事务内确保 Favorite Tag；
> **startup eager bootstrap 属后续 CLI / GUI integration**，不是 Phase 3.2 的一部分；
> 禁止用 `database.initialize()` 实现 bootstrap。
> 未改变 Tag 数据模型 / API / 事务 / ownership / schema / DoD 的任何其它内容。

> **Documentation Reconciliation（2026-10-08）**：Architecture Design §9.3 / §11.5 / §21 的
> bootstrap 与 lifecycle 表述已修正为 **lazy / on-demand**（与 Contract §4.4 / §7.1 / §11 Step 8 一致）；
> 本文件生命周期状态更新为 implementation = **COMPLETE / AUDIT PASS**（Phase 3.2 CLOSED 仍未达成）。
> 本次仅文档修正，未改功能代码 / schema / migration / 测试 / CLI / GUI / API / behavior。

---

## 附录 A — 与上级契约的一致性

| 上级条款 | 本 Contract | 一致性 |
| :--- | :--- | :--- |
| Phase 3.0 §4 Tag 单一机制 / Favorite = 保留系统标签 | §1 / §4.4 / §4.5 | ✅ |
| Phase 3.0 §4.1 rename 冲突拒绝、不合并 | §4.3 | ✅ |
| Phase 3.0 §8 零 schema / 16 表 | §16 | ✅ |
| Phase 3.0 §9 单一写服务 | §3 / §5 | ✅（Tag 域独立 writer） |
| Phase 3.0 §10 Query 只读 | §7.2 / §10 | ✅ |
| Phase 3.0 §12 In Scope（Tag / Favorite / 只读标签事实） | §1 | ✅ 子集 |
| Phase 3.0 §13 Out of Scope | §2 | ✅ 未缩小 |
| Phase 3.0 §14.3 U3（OPEN-EVIDENCE） | 设计文档 §4.3 | ✅ 冻结为 GLOBAL（对 schema 能力的边界声明） |
| Phase 3.1 ownership（用户数据 vs machine fact） | §3 / §5 | ✅ 沿用 |
| Phase 3.1 additive DTO 惯例 | §7.3 | ✅ 沿用 |

## 附录 B — 本轮只读合规核对

| 禁止项 | 状态 |
| :--- | :--- |
| 修改功能代码 | ✅ 未做 |
| 修改 schema / migration | ✅ 未做（`SCHEMA_VERSION == 2`） |
| 修改数据库 | ✅ 未做 |
| 修改测试 | ✅ 未做 |
| 修改 CLI / GUI | ✅ 未做 |
| 实现 Tag / TagWriteService / TagQuery / DTO / Search / Collection | ✅ 未做 |
| 创建 commit / tag | ✅ 未做 |

> 新增物：`docs/phase3/PHASE3_2_TAG_SYSTEM_ARCHITECTURE_DESIGN.md`、
> `docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md`、`docs/phase3/PHASE3_2_LOG.md`（设计文档，非功能）。

> **Freeze 审计说明**：本冻结步骤按任务授权**修改了本 Contract 文档**
> （补齐 §1.1 / §7.4 / §7.5 / §16 / §17 / §18，强化 §7.3 / T-F 与状态标记）；
> 除本 Contract 与 LOG 外，未修改任何功能代码 / schema / migration / 测试 / CLI / GUI / 数据库。
