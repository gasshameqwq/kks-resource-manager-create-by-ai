# Phase 3.2 Work Log — Tag System

> 性质：**工作日志（过程记录）**，不是冻结契约，也不是正式 Phase 报告。
> 阶段：**Phase 3.2 — Tag System**（Architecture & Contract Design 已完成；implementation 未开始）
> 日期：2026-10-08
> 权威契约（从高到低）：
> 1. `docs/phase3/PHASE3_0_CONTRACT.md`（Phase 3 首期 Architecture / Scope Contract，最高权威）
> 2. `docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md`（Search & Taxonomy Design Review）
> 3. `docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md`（User Write Foundation，已实现并冻结）
> 前序基线：Phase 3.1 = **CLOSED / PASS**（tag `phase-3.1-closed`，HEAD `99aa0d1`）
> 状态：本文件是本会话的**唯一新增物**。未修改任何功能代码 / schema / migration /
> 测试 / CLI / GUI / 数据库；未 commit / tag / push。
> 说明：Phase 3.2 的正式设计文档 `docs/phase3/PHASE3_2_TAG_SYSTEM_ARCHITECTURE_DESIGN.md`
> **尚未写入仓库**（设计评审按 READ-ONLY 约束只在评审报告中给出内容）。本日志先记录
> 设计结论与实施计划；该设计文档是否落盘由后续授权决定。

---

## 0. 本日志的用途

记录进入 Phase 3.2 实现之前的**只读设计评审结论与实施规划**，供后续
（确认范围 → 冻结 Contract → 分步实现 → 验证 → 收尾）参考。
本文件**不改变**任何 Phase 3.0 / 3.0.2 / 3.1 已封存文档的结论，也不构成新的契约。

**维护约定（2026-10-08 起）**：本日志按「每一步实施后追加记录」维护。
本次对话后续的**每一步**（Contract 冻结、各 Step 实现、验证、Git 收尾，以及其它经用户确认
的动作）都追加到本文件，不新建平行日志。每条记录固定包含：范围冻结 / 变更清单 / 关键决策 /
验证证据 / Git 状态。本文件始终是**过程日志**：不构成冻结契约，也不代替将来的正式
Phase 3.2 Closure Report。

---

## 1. 阶段定位

Phase 3.2 对应 Phase 3.0.2 §11 路线图中的 **3.2 Tag System**（路线次序保持不变）：

```text
3.0   Architecture / Scope Contract        ← CLOSED / PASS（phase-3.0-closed）
3.0.2 Search & Taxonomy Design Review      ← 已入库
3.1   User Write Foundation                ← CLOSED / PASS（phase-3.1-closed，HEAD 99aa0d1）
3.2   Tag System                           ← 本次：设计评审完成，实现未开始
3.3   Search & Query Foundation            （不提前做）
3.4   User Classification & Search         （不提前做）
3.5   CLI / GUI Integration                （不提前做）
```

Phase 3.2 的唯一问题是：

> **用户如何给 Resource 做组织和标记。**（Tag 单一机制；Favorite = 保留系统 Tag。）

---

## 2. 本次记录范围（已完成）

本次已完成的是 **Phase 3.2 Architecture & Contract Design（DESIGN ONLY / READ-ONLY）**：

- 只读检查仓库当前真实状态（schema / 代码 / 测试 / 文档）；
- 产出并冻结一版 Tag System 设计结论（见 §5）；
- 给出实现步骤与 patch plan（见 §7 / §8）；
- **未**修改任何代码 / schema / migration / 数据库；**未**创建 tag / commit；
  **未**实现 Tag / Favorite / Query filter / CLI / GUI / Search / Collection。

因此本日志当前状态为：**设计评审 = 完成；实现 = 未开始**。

---

## 3. 只读审查范围

**文档**

- `docs/phase3/PHASE3_0_CONTRACT.md`
- `docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md`
- `docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md`、`PHASE3_1_LOG.md`、`PHASE3_1_CLOSURE_REPORT.md`

**代码**

- `core/database/{schema,db}.py`
- `core/app/{__init__,resource_write,admin}.py`
- `core/models/__init__.py`
- `core/query/{queries,dto,browse,search,__init__}.py`
- `core/scanner/store.py`（确认机器写入者不触碰 tags）
- `main.py`、`cli_query.py`

**测试**

- `tests/test_ownership_guard.py`、`tests/test_resource_write.py`、`tests/test_database_schema.py`、
  `tests/test_migration_v2.py`、`tests/test_read_model_exposure.py`、`tests/test_gui_smoke.py`

核对方法：**以实际代码 / 实测结果为准**，不依据文件名或报告转述猜测设计。

---

## 4. 基线证据（只读，实测）

| 检查 | 方式 | 结果 |
| :--- | :--- | :--- |
| branch | `git rev-parse --abbrev-ref HEAD` | `main` |
| HEAD | `git rev-parse HEAD` | `99aa0d1`（feat(phase3): establish user write foundation） |
| 工作区 | `git status --porcelain` | **clean**（评审开始时） |
| tag | `git tag -l` | 含 `phase-3.0-closed` / `phase-3.1-closed` |
| schema 版本 | `core/database/schema.py` | `SCHEMA_VERSION == 2`；`MIGRATIONS == {1, 2}`；业务表 **16** |
| `tags` 表 | schema | `tags(id, name, name_key UNIQUE, color, category, created_at, updated_at)` |
| `resource_tags` 表 | schema | `resource_tags(resource_id, tag_id, origin CHECK('user','auto'), created_at)`，PK `(resource_id, tag_id)`，双向 `ON DELETE CASCADE` |
| 索引 | schema | `idx_resource_tags_tag(tag_id)` |
| **Tag 运行期使用** | 全仓检索 | **零**（`tags` / `resource_tags` 未出现在任何 INSERT/UPDATE/DELETE/查询中，仅存在于 schema 与测试夹具） |
| 持久工作库 | `data/kks_resource_manager.db`（只读打开） | `resources=0`、`tags=0`、`resource_tags=0`、`collections=0`、`schema_version='2'` |
| 归一化工具 | `core/database/db.py` | `normalize_name_key(text) = (text or "").strip().casefold()`（注释已写明「用于作者/标签/Collection 去重」） |
| 用户写服务 | `core/app/resource_write.py` | `ResourceWriteService` + `ResourceWriteError/ResourceNotFound/InvalidResourceValue`；`_USER_WRITABLE_COLUMNS={display_name, notes, resource_type, type_source}` |
| Query 只读护栏 | `core/query/queries.py` | `_execute_select` 仅放行 `SELECT` / `WITH`，否则 `ReadOnlyViolation` |
| Ownership guard | `tests/test_ownership_guard.py` | 仅 `core/scanner/store.py` 与 `core/app/resource_write.py` 可写 `resources`；UI/CLI 不得 `import sqlite3` |
| UI 边界 | `tests/test_gui_smoke.py` | `ui/*` 不得 import `ResourceQuery` / `LibraryQuery` / `sqlite3` |
| 机器写入者 | `core/scanner/store.py` | 只写 `resources` / `mods`，并重建 `resource_plugins` / `resource_mod_usages` / `resource_mods` / `resource_authors`；**不触碰** `tags` / `resource_tags`；全仓无 `DELETE FROM resources` |

> 关键结论：**Tag 所需的两张表已存在且完全未被使用**；3.2 的目标是在零 schema 变更前提下，
> 为它们建立唯一的写入口（`TagWriteService`）与只读暴露（`TagQuery`）。

---

## 5. 设计结论摘要（Decision Register）

| ID | 决策 | 说明 / 依据 |
| :--- | :--- | :--- |
| **P3.2-D1** Architecture | 新增 **`TagWriteService`**（与 `ResourceWriteService` 对等） | 避免 `ResourceWriteService` 无限膨胀；「单一写服务」按「**每个 owned entity 一个 runtime writer**」落实；`core/app` 已同时存在 `LibraryAdminService` + `ResourceWriteService`，本决策与既有实践一致 |
| **P3.2-D2** Schema | **NO MIGRATION REQUIRED** | `tags` / `resource_tags` 已在 v1 就绪（`name_key UNIQUE`、PK 去重、`origin` CHECK、双向级联、`idx_resource_tags_tag`） |
| **P3.2-D3** Tag identity | surrogate `tags.id` + business key `name_key`（UNIQUE） | `resource_tags.tag_id` 引用 surrogate；`name_key` 用于去重 / 查名 |
| **P3.2-D4** `name_key` 规则 | 复用 `normalize_name_key`（`strip()` + `casefold()`） | 不新造规范化；trim 只去首尾，casefold 使 `Favorite`/`favorite` 碰撞；不引入 NFC/NFKC |
| **P3.2-D5** Collision | create 冲突 ⇒ **拒绝**；rename 冲突 ⇒ **拒绝**（不合并） | 承接 Phase 3.0 §4.1「重命名冲突拒绝、不做自动合并」；DB UNIQUE 兜底 |
| **P3.2-D6** System Tag | 由**保留 key 注册表**判定（`{"favorite"}`），**不新增 `is_system` 列** | 保持零 schema 变更；system 行由 `ensure_system_tags()` 幂等保证存在 |
| **P3.2-D7** Favorite | `favorite` = 保留系统 Tag（`name_key='favorite'`，`name='Favorite'`），集合只经 `resource_tags` | 明令禁止 `resources.favorite` 列与独立 `favorites` 表（Phase 3.0 §4.2） |
| **P3.2-D8** origin | 3.2 所有赋值均 `origin='user'`；`'auto'` 保留未用 | 禁止 Scanner / Parser 自动制造用户 Tag |
| **P3.2-D9** Ownership | `TagWriteService` 是 `tags` / `resource_tags` 的**唯一** runtime writer；Scanner / Parser 永不写 | 见 §6；扩展 ownership guard 守护 |
| **P3.2-D10** Query | 新增只读 **`TagQuery`**；**不设计 Search Query Model** | Query Layer 只提供基础只读事实；读经 `_execute_select` |
| **P3.2-D11** DTO | 新增 `TagSummary`；`ResourceDetail` **追加** `tags` / `is_favorite`（带默认值、置于末尾） | 沿用 Phase 2.3 / 3.1 的 additive 惯例，向后兼容 |
| **P3.2-D12** 边界 | `tag_id` / `favorite` 过滤进入 `ResourceQuery` / `BrowserScope` ⇒ **留到 3.3** | 3.2 不设计统一查询模型，不做 `tag:` / `favorite:` 文本语法 |

### 5.1 目标模型

```text
Resource ──< resource_tags >── Tag
                (origin='user')

Tag
 └── favorite  ← 保留系统 key（name_key='favorite'）
```

三条语义轴保持分离（Phase 3.0.2 §4.3 / §7.3）：

```text
Resource Type   = 这个资源是什么
Usage Category  = 资源里的 MOD 被用在哪
Tag             = 用户想如何组织这个资源
```

---

## 6. Repository vs Design 一致性核对

| 维度 | 设计目标 | 仓库现状 | 结论 |
| :--- | :--- | :--- | :--- |
| `tags` / `resource_tags` 结构 | 支持 N:M + 去重 + 级联 | 已存在于 v1 | **MATCH**（无需 migration） |
| 归一化策略 | 复用既有 policy | `normalize_name_key` 已存在 | **MATCH** |
| 用户写入口 | Tag 需独立 writer | 仅 `ResourceWriteService`，不写 Tag | **需新增** `TagWriteService` |
| Query 读面 | 只读 Tag 事实 | 无 Tag 查询 | **需新增** `TagQuery` |
| 机器写入者 | 永不写 Tag | `store.py` 未触碰 tags | **MATCH**（并有 guard 守护） |
| System / Favorite | 保留系统 Tag | 无任何实现 | **需新增**（零 schema） |
| 冲突策略 | 拒绝、不合并 | 无实现 | **需新增** |
| schema | 零变更 | v2 / 16 表 | **MATCH** |

**未发现阻塞性冲突**：设计目标与 Phase 3.0 / 3.1 已冻结 Contract 一致；唯一「新增」都是
Contract 已列的 In Scope 项（Tag 体系 + Favorite）。

---

## 7. 计划实现面（patch plan）

> 仅为**计划**，本次未执行。所有写入均为 additive / 零 schema。

**新增文件**

| 文件 | 用途 |
| :--- | :--- |
| `core/models/tags.py` | `SystemTagSpec` / `SYSTEM_TAGS` / `RESERVED_TAG_KEYS` / `is_system_tag_key()`（纯数据，无 DB） |
| `core/app/tag_write.py` | `TagWriteService` + 异常类型（Tag 域唯一写入口） |
| `core/query/tag_queries.py` | `TagQuery`（只读，无 SQL 泄漏到别处） |
| `tests/test_tag_write.py` | 写服务 focused 测试 |
| `tests/test_tag_query.py` | 读模型 focused 测试 |
| `docs/phase3/PHASE3_2_TAG_SYSTEM_ARCHITECTURE_DESIGN.md` | 正式设计文档（待授权落盘） |

**修改文件**

| 文件 | 变更 |
| :--- | :--- |
| `core/models/__init__.py` | 再导出 tags 注册表 |
| `core/app/__init__.py` | 导出 `TagWriteService` 与异常 |
| `core/query/dto.py` | 新增 `TagSummary`；`ResourceDetail` 追加 `tags` / `is_favorite` |
| `core/query/queries.py` | `ResourceQuery.get()` 填充 tags / is_favorite（仅只读 SELECT） |
| `core/query/browse.py` | `BrowseService` 只读转发 Tag 读面 |
| `core/query/__init__.py` | 导出 `TagQuery` / `TagSummary` |
| `tests/test_ownership_guard.py` | 扩展 Tag 写者 allowlist + 运行时 trace |
| `tests/test_gui_smoke.py` | UI import 守卫扩展到 `TagQuery` |
| `main.py`（**可选**） | 薄 CLI 入口；最终 UX 留 3.5 |

**明确不修改**：`core/database/**`（schema / migration / db）、`core/scanner/**`、
`core/parsers/**`、`ui/**`（除 guard 测试）。

---

## 8. 实施步骤计划（暂定，待 Contract 冻结后细化）

```text
Step 1  core/models/tags.py：保留 key 注册表
Step 2  core/app/tag_write.py：TagWriteService + 异常；create / rename / delete / assign / unassign / set_favorite / ensure_system_tags
Step 3  core/app/__init__.py：导出
Step 4  core/query/dto.py：TagSummary + ResourceDetail 追加字段
Step 5  core/query/tag_queries.py：TagQuery（list / get / find_by_name / resolve / for_resource / resource_ids / is_favorite / favorite_resource_ids / system_tags）
Step 6  core/query/queries.py + browse.py：ResourceQuery.get 填充、BrowseService 转发
Step 7  core/query/__init__.py：导出
Step 8  引导：database.initialize() 之后调用 ensure_system_tags()（幂等系统 seed；非 DDL）
Step 9  tests/test_tag_write.py + tests/test_tag_query.py
Step 10 tests/test_ownership_guard.py + tests/test_gui_smoke.py 扩展
Step 11（可选）main.py 薄 CLI
Step 12 文档：设计文档 / Implementation Contract / LOG / Closure（按仓库惯例）
```

### 8.1 暂定 Service 契约

```text
TagWriteService（core/app/tag_write.py）
    create_tag(name, *, color=None, category=None) -> int
    rename_tag(tag_id, new_name) -> None
    delete_tag(tag_id) -> None
    assign_tag(resource_id, tag_id) -> None       # 幂等，origin='user'
    unassign_tag(resource_id, tag_id) -> None     # 幂等
    set_favorite(resource_id, favorite: bool) -> None  # 幂等，基于系统 Tag
    ensure_system_tags() -> None                  # 幂等

异常：TagWriteError 基类 + TagNotFound / TagNameConflict / ReservedTagName /
      SystemTagImmutable / InvalidTagValue；资源不存在复用 ResourceNotFound。
每个 public 写方法 = 一个 db.transaction；失败回滚并原样抛出。

TagQuery（core/query/tag_queries.py，只读）
    list() / get(tag_id) / find_by_name(name) / resolve(target)
    for_resource(resource_id) / resource_ids(tag_id)
    is_favorite(resource_id) / favorite_resource_ids() / system_tags()

DTO
    TagSummary(id, name, name_key, color, category, is_system, resource_count=0)
    ResourceDetail += tags: tuple[TagSummary, ...] = ()
    ResourceDetail += is_favorite: bool = False
```

### 8.2 System Tag / Favorite 语义（暂定）

1. 保留 key：`favorite`（`RESERVED_TAG_KEYS`）。
2. 初始化：`ensure_system_tags()` 幂等 `INSERT … ON CONFLICT(name_key) DO NOTHING`。
3. rename：禁止（`SystemTagImmutable`）。delete：禁止。普通用户创建同名 key：禁止（`ReservedTagName`）。
4. assign / unassign Favorite 与普通 Tag **同一写入路径**（`origin='user'`）。
5. Query 只读暴露：`TagQuery.is_favorite()` / `favorite_resource_ids()`；Favorite 亦出现在 `ResourceDetail.tags`。
6. 不存在第二套 Favorite 持久化（无列、无独立表）。

---

## 9. 验收不变式（暂定）与测试计划

**测试不变式**

```text
T-A  name_key = normalize_name_key(name)；大小写不敏感；空白名被拒绝
T-B  create 冲突 ⇒ TagNameConflict（不合并、不静默复用）
T-C  rename 到已占用 key ⇒ TagNameConflict；rename 系统 Tag ⇒ SystemTagImmutable
T-D  delete 系统 Tag ⇒ SystemTagImmutable；delete 普通 Tag 级联清除其 resource_tags
T-E  assign / unassign 幂等；重复赋值无副作用；origin 恒为 'user'
T-F  Favorite 经保留系统 Tag；set_favorite 幂等；is_favorite 正确；用户不能创建 'favorite'
T-G  Scanner 重扫后 resource_tags 保留（资源行不删、机器 writer 不碰 Tag）
T-H  仅 TagWriteService 写 tags / resource_tags；Scanner / ResourceWriteService 不写
T-I  TagQuery 只发 SELECT / WITH；不写库
T-J  DTO 追加字段带默认值；既有构造 / 既有 825 测试不回归
T-K  SCHEMA_VERSION==2 / MIGRATIONS=={1,2} / 16 表不变
```

**验证计划**：focused（Tag 写 / 读）→ 全量 `pytest`（≥ 现有基线）→ schema 冻结断言 →
ownership guard → rescan 不变量。

---

## 10. Out of Scope / Phase 3.3 边界

**Phase 3.2 不做**

```text
Search Query Model
field:value
AND / OR / NOT
全文搜索
Tag 搜索语法（tag: / favorite:）
GUI Tag Management
GUI Favorite UI
CLI 最终用户体验设计
自动分类
Tag ↔ Resource Type 自动转换
Tag ↔ Usage Category 自动转换
AI 分类
Collection
任何 schema / migration / 文件操作
```

**必须留给 Phase 3.3**

- Search Query Model（统一查询对象）；`field:value` + AND/OR/NOT；全文 / Tag 搜索语法；
- 把 `tag_id` / `favorite` 接线进 `ResourceQuery` 与 `BrowserScope`（按标签浏览的查询模型）。

> 提醒：**Query Layer 暴露 Tag ≠ Search 已实现。**

---

## 11. Risks / Open Questions

1. **Unicode 规范化形式未定义**：仓库 policy 仅 `casefold`，未做 NFC/NFKC；组合字符可能产生
   不同 `name_key`。当前决定：复用既有 policy，不扩大范围（登记为待证据项）。
2. **系统 Tag 展示名 / 本地化**：暂定存储 `name='Favorite'`（使 `name_key == normalize_name_key(name)`
   对所有 Tag 一致成立）；GUI 按保留 key 本地化留 3.5。用户无法创建名为 “Favorite” 的普通 Tag。
3. **历史库若已存在 `name_key='favorite'` 的用户行**：按保留 key 判定会被视为系统 Tag。当前
   真实库中不存在该行（`tags=0`），登记为边界，不额外加机制。
4. **既有 resources guard 正则**：`_RESOURCE_WRITE_RE` 不匹配 `INSERT OR IGNORE/REPLACE INTO resources`；
   Tag guard 需接受 `OR IGNORE` 形式。建议在 3.2 顺手把 resources 正则一并收紧（**仅测试**变更）。
5. **入口时点（U2，OPEN-EVIDENCE）**：Tag 的 CLI / GUI 最终入口仍未定；3.2 可提供薄 CLI，
   最终 UX 归 3.5。
6. **Import 方向**：`queries.py → tag_queries.py` 单向依赖，`tag_queries.py` 不得反向 import `queries.py`。
7. **组织范围（U3，OPEN-EVIDENCE）**：Tag 为全局（非 per-library），与全局身份模型一致；
   保持未决，不在 3.2 决定。

---

## 12. 状态与未做事项

```text
Phase 3.2 Architecture & Contract Design（只读评审）：**完成**
Phase 3.2 Implementation Contract（冻结文件）：未创建
Phase 3.2 TagWriteService / TagQuery / DTO / tests：未实现
Phase 3.2 设计文档 PHASE3_2_TAG_SYSTEM_ARCHITECTURE_DESIGN.md：未写入仓库
schema / migration / 数据库：未修改（SCHEMA_VERSION == 2）
scanner / parser / ResourceWriteService / Query Layer 代码：未修改
CLI / GUI：未实现 Tag / Favorite 入口
Search / Collection：未实现
Git：未 commit、未 tag
```

下一步（待用户确认）：确认设计结论 → （可选）落盘设计文档 → 冻结 `PHASE3_2_IMPLEMENTATION_CONTRACT.md`
→ 按 §8 分步实现。

---

## 13. 只读合规声明（本次设计评审）

| 约束 | 状态 |
| :--- | :--- |
| 未修改功能代码 / schema / migration | ✅ |
| 未修改数据库 / 未创建表 / 列 / 索引 | ✅ |
| 未修改 CLI / GUI / Search / Collection | ✅ |
| 未实现 Tag / Favorite | ✅ |
| 未创建 commit / tag | ✅ |
| 唯一新增物 | 本文件 `docs/phase3/PHASE3_2_LOG.md` |

---

## 14. Git 状态（记录本文档时）

```text
branch  main
HEAD    99aa0d1  （feat(phase3): establish user write foundation）
tags    ... · phase-3.0-closed · phase-3.1-closed
status  ?? docs/phase3/PHASE3_2_LOG.md   （本会话唯一新增文件；未 commit、未 tag）
```

---

## 15. 相关文件

- 权威契约：`docs/phase3/PHASE3_0_CONTRACT.md`、`docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md`、`docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md`
- 前序日志 / 收尾：`docs/phase3/PHASE3_1_LOG.md`、`docs/phase3/PHASE3_1_CLOSURE_REPORT.md`
- 相关代码：`core/database/schema.py`、`core/database/db.py`、`core/app/resource_write.py`、`core/models/__init__.py`、`core/query/{queries,dto,browse}.py`、`core/scanner/store.py`
- 相关测试：`tests/test_ownership_guard.py`、`tests/test_resource_write.py`、`tests/test_database_schema.py`、`tests/test_migration_v2.py`、`tests/test_gui_smoke.py`
- 设计文档（本修订轮已落盘）：`docs/phase3/PHASE3_2_TAG_SYSTEM_ARCHITECTURE_DESIGN.md`
- 候选契约（本修订轮已落盘）：`docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md`

---

## 16. 设计修订记录（Design Revision Before Contract Freeze）

> 范围：**Phase 3.2 Design Revision（DESIGN ONLY / READ-ONLY）**。
> 依据：上一轮 Phase 3.2 Architecture & Contract Design Review + 本次修订要求 D1–D6。
> 性质：**只做设计修订 + 落盘 2 份设计文档**；未修改任何功能代码 / schema / migration /
> 数据库 / 测试 / CLI / GUI；未实现 TagWriteService / TagQuery / DTO；未 commit / tag。

### 16.1 本次修订（D1–D6）

| # | 修订 | 结果 |
| :-- | :--- | :--- |
| D1 | 冻结 Tag scope = **GLOBAL** | 删除原 Open Question U3；见设计文档 §4 |
| D2 | **删除** `TagQuery.resolve()` | 只保留确定性 read API；见契约 §7.2 |
| D3 | 明确 `set_favorite()` 语义 | 仅为保留系统 Tag 的 domain convenience；唯一事实 = `resource_tags`；见契约 §4.5 / §7.1 |
| D4 | `resource_count` = **derived read data** | 不落库、不加列、不加 counter cache；见契约 §8 |
| D5 | `color` / `category` 语义 | 只是现有 Tag metadata，不引入 taxonomy / classification；见契约 §9 |
| D6 | **删除** Phase 3.2 可选 CLI 实现 | 3.2 只做 domain / service / query foundation；入口属 3.5；见契约 §2 / §11 |

### 16.2 D1 的显式记录（对 Phase 3.0 U3 的处置）

- Phase 3.0 §14.3 U3 原为 **[OPEN-EVIDENCE]**；§16.4 规定该状态项「在取得证据前不得实现」。
- Phase 3.2 不新增 per-library 能力；仅声明「在冻结的 schema v2 + 全局 identity 下，Tag 只能且必须是 global」
  —— 这是**对 schema 表达能力的边界声明**，不是凭证据替 U3 定案。
- 因此 U3 在 Phase 3.2 范围内**关闭为 GLOBAL**；per-library 转入
  **[FUTURE-CANDIDATE]（需 schema / architecture change，另行走 §16 变更控制）**。

### 16.3 本轮新增文件

```text
docs/phase3/PHASE3_2_TAG_SYSTEM_ARCHITECTURE_DESIGN.md     （21 节设计文档）
docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md           （CANDIDATE 候选冻结版）
docs/phase3/PHASE3_2_LOG.md                               （本文件，追加本记录）
```

### 16.4 状态

```text
Phase 3.2 Design Revision：完成
Phase 3.2 Architecture Design：已落盘（CANDIDATE）
Phase 3.2 Implementation Contract：已落盘（CANDIDATE，未 CLOSED）
Phase 3.2 implementation：未开始
schema / migration / database / tests / CLI / GUI / 功能代码：未修改
Git：未 commit、未 tag
```

下一步（待用户审核）：确认 Contract → 视为 FROZEN → 才进入 Step 1 implementation。

---

## 17. Contract Freeze 记录（Implementation Contract Freeze）

> 范围：**Phase 3.2 Implementation Contract Freeze（DESIGN ONLY / READ-ONLY）**。
> 依据：`PHASE3_2_TAG_SYSTEM_ARCHITECTURE_DESIGN.md` + `PHASE3_2_IMPLEMENTATION_CONTRACT.md`
> （候选版）+ 当前 HEAD `99aa0d1`（`phase-3.1-closed`）。
> 结论：**Implementation Contract — FROZEN / PASS**。
> 本步骤按任务授权**修改了 Contract 文档**（完整性补齐）；除 Contract 与本 LOG 外，
> 未修改任何功能代码 / schema / migration / 测试 / CLI / GUI / 数据库。

### 17.1 审计结论（A–L）

| 项 | 结论 |
| :-- | :--- |
| A. Tag Scope | GLOBAL 冻结；`name_key` 全局唯一；不增 `library_id`；per-library 属未来 schema / architecture change |
| B. TagWriteService | 唯一 runtime writer；只负责 create / rename / delete / assign / unassign / set_favorite / ensure_system_tags |
| C. TagQuery | 只含 list / get / find_by_name / for_resource / resource_ids / system_tags / is_favorite / favorite_resource_ids；**无 `resolve()`** |
| D. Favorite | `name_key='favorite'` / `name='Favorite'`；唯一持久化 = `resource_tags`；`set_favorite` = assign/unassign 便利封装 |
| E. Schema | `SCHEMA_VERSION=2` / `MIGRATIONS={1,2}`；不增 migration / `is_system` / `resource_count` / `library_id` / favorite column/table |
| F. DTO | `TagSummary(...)`；`ResourceDetail += tags / is_favorite`；`resource_count` 为 read-time derived，不落库 / 不缓存 / 防 N+1 |
| G. Metadata | `color` / `category` 仅为现有 metadata；无 taxonomy / classification / Type / Usage / search-field 语义 |
| H. Normalization | 复用 `normalize_name_key`（`strip()` + `casefold()`）；不引入 NFC/NFKC；冲突 `TagNameConflict`；不自动 merge |
| I. System Tag | `RESERVED_SYSTEM_TAG_KEYS={"favorite"}`；按 reserved key 判定；不增 `is_system` 列；不可 rename / delete；`ensure_system_tags()` 幂等 |
| J. Transaction | 每个 public write = 一个 `db.transaction`；失败回滚 + 原样抛出 |
| K. Ownership guard | 扩展 guard：`tags` / `resource_tags` 写只允许 `core/app/tag_write.py`；Scanner trace 证明不写 Tag 表 |
| L. Tests | 覆盖 normalization / blank / create+rename collision / system protection / 普通删除 / assignment / 幂等 / `origin='user'` / Favorite 持久化+幂等 / rescan / Query 只读 / DTO 兼容 / resource_count / ownership / schema v2 |

### 17.2 额外一致性核对（任务 §3 的 10 项）

| # | 检查 | 结论 |
| :-- | :--- | :--- |
| 1 | `TagQuery` 不反向依赖 `queries.py` | ✅ 契约 §7.5（单向依赖） |
| 2 | `TagQuery` 只经 SELECT / WITH boundary | ✅ 契约 §7.2 / §7.5 / §10 |
| 3 | `TagWriteService` 不承担 ResourceWriteService 职责 | ✅ 契约 §3 / §17-3 |
| 4 | Scanner / Parser 不产生 Tag | ✅ 契约 §3 / §17-4 |
| 5 | `origin='auto'` 保留但 3.2 不用 | ✅ 契约 §3 / §17-5 |
| 6 | 不修改 `main.py` / `cli_query.py` / `ui/*` 提供 Tag UX | ✅ 契约 §2 / §11 / §17-6 |
| 7 | 不实现 GUI Tag 管理 | ✅ Non-Goal |
| 8 | 不实现 GUI Favorite UI | ✅ Non-Goal |
| 9 | 不实现 CLI Tag UX | ✅ Non-Goal |
| 10 | 不实现 Search / Tag filtering | ✅ Non-Goal / §15 |

### 17.3 本轮对 Contract 文档的修改（完整性补齐，不改语义）

| 修改 | 原因 |
| :--- | :--- |
| 状态标记 CANDIDATE → **FROZEN / PASS** | 本步骤即 Contract Freeze |
| 新增 §1.1 **Tag Scope（GLOBAL）** | 任务 A 要求契约显式冻结 global scope / 无 `library_id` |
| 新增 §7.4 **TagQuery Forbidden Surface** | 任务 C 要求显式禁止 `resolve()` / `tag:` / `favorite:` / `field:value` / AND·OR·NOT / Search Query Model / BrowserScope filtering |
| 新增 §7.5 **依赖方向** | 任务 §3-1 / §3-2 要求防 import cycle 且只经只读 boundary |
| 强化 §7.3 DTO 说明 | 任务 F 要求 additive compatibility 明确化 |
| 强化 T-F | 任务 L 要求 Favorite 持久化只经 `resource_tags` |
| 新增 §16 **Schema Decision** | 任务 E 要求契约显式冻结 `SCHEMA_VERSION` / `MIGRATIONS` |
| 新增 §17 **Additional Consistency Verifications** | 任务 §3 的 10 项一致性需在契约内记录 |
| 新增 §18 **Freeze Record** | 记录冻结时点与依据 |
| 修正附录 A 行（§17→§16） | 与新增 Schema 章节对齐 |

以上均为**文档完整性补齐**，未改变任何已冻结语义，未扩大 scope。

### 17.4 状态

```text
Design Revision            → PASS
Implementation Contract    → FROZEN / PASS
Phase 3.2 implementation   → 未开始（等待下一步指令）
Phase 3.2 CLOSED           → 未达成
schema / migration / database / tests / CLI / GUI / 功能代码：未修改
Git：未 commit、未 tag
```

完成 Contract Freeze，停止，等待下一步指令。

---

## 18. Implementation 记录（Phase 3.2 Tag System）

> 范围：**Phase 3.2 Implementation**（按 `PHASE3_2_IMPLEMENTATION_CONTRACT.md` FROZEN）。
> 结论：**Phase 3.2 Implementation = READY FOR AUDIT**。
> 本步骤新增 / 修改功能代码与测试；**未**改 schema / migration / database / CLI / GUI；
> **未** commit / tag / push。

### 18.1 新增文件

| 文件 | 内容 |
| :--- | :--- |
| `core/models/tags.py` | `SystemTagSpec` / `SYSTEM_TAGS` / `RESERVED_SYSTEM_TAG_KEYS` / `FAVORITE_TAG_KEY` / `is_system_tag_key()`（纯数据） |
| `core/app/tag_write.py` | `TagWriteService` + 6 个异常；`tags` / `resource_tags` 唯一 runtime writer |
| `core/query/tag_queries.py` | `TagQuery` 只读 read model（无 `resolve()`） |
| `core/query/readonly.py` | 只读护栏抽出共享（`ReadOnlyViolation` / `_execute_select` / `_fetchall` / `_fetchone`） |
| `tests/test_tag_write.py` | TagWriteService / ownership / transaction focused 测试 |
| `tests/test_tag_query.py` | TagQuery / DTO / read-only focused 测试 |

### 18.2 修改文件

| 文件 | 变更 |
| :--- | :--- |
| `core/models/__init__.py` | 再导出 Tag 注册表 |
| `core/app/__init__.py` | 导出 `TagWriteService` 与异常 |
| `core/query/dto.py` | 新增 `TagSummary`；`ResourceDetail += tags / is_favorite` |
| `core/query/queries.py` | 只读护栏改为共享模块；`ResourceQuery.get()` 只读填充 tags / is_favorite |
| `core/query/browse.py` | `BrowseService` Tag 只读 forward |
| `core/query/__init__.py` | 导出 `TagQuery` / `TagSummary` |
| `tests/test_ownership_guard.py` | 新增 Tag 表写路径护栏 + Scanner trace + rescan 保真测试 |
| `tests/test_gui_smoke.py` | UI import 守卫扩展禁止 `TagQuery` |

### 18.3 关键实现决定

1. **只读护栏抽出共享模块 `core/query/readonly.py`**：Contract §7.5 要求
   `tag_queries` 不得反向 import `queries`，但两者需复用同一只读 boundary。
   故把 `ReadOnlyViolation` / `_execute_select` 抽到 `readonly.py`；
   `queries.py` 保留 `_fetchall` / `_fetchone`（引用本模块的 `_execute_select` 名字），
   以**不破坏**既有 `monkeypatch queries._execute_select` 的 Phase 2 测试点。
   （零行为变更；全量回归验证通过。）
2. **Favorite 唯一事实 = `resource_tags`**：`set_favorite` 内部 `ensure_system_tags` 取
   favorite tag id，再走 assign / unassign 语义；无第二套持久化。
3. **`resource_count` 为读取时派生**：`TagQuery.list()` 用**一次** `LEFT JOIN ... GROUP BY`
   聚合（无 N+1）；不落库、不缓存。
4. **`find_by_name` 精确匹配**：仅 `name_key = normalize_name_key(name)`，无 LIKE / 模糊。
5. **owner guard 收紧**：`_RESOURCE_WRITE_RE` 现接受 `INSERT OR ... INTO` 形式；
   新增 `_TAG_WRITE_RE` 只允许 `core/app/tag_write.py` 写 `tags` / `resource_tags`。

### 18.4 Deviation / Reconciliation（需审计确认）

```text
EXEC-1  Bootstrap 调用点
```

- **Contract §11.5** 要求 `ensure_system_tags()`「应用引导（`database.initialize()` 之后）调用一次」。
- 但 Contract §2 Non-Goal #7 明确**禁止**修改 `main.py` / `cli_query.py` / `ui/*`
  （唯一允许的是 guard 测试的纯测试修改），而启动引导的唯一调用点正在这些文件里。
- **实现选择（未静默改 Contract）**：不修改入口文件；改为
  **惰性保证**——`set_favorite()` 内部在同一事务内幂等 `ensure_system_tags`；
  同时暴露公开 `TagWriteService.ensure_system_tags()` 供 Phase 3.5 入口接线。
- **功能影响**：Favorite 首次使用时自动创建系统 Tag；若库从未发生任何 Tag 写入，
  `tags` 表内不会**预先**存在 favorite 行（此时 `TagQuery.system_tags()` / `list()` 为空）。
  首次 `set_favorite(...)` 之后系统 Tag 立即存在且幂等。
- 请审计裁决是否接受该 reconciliation；如要求「启动即预置」，需要授权修改入口文件（属 3.5）。

### 18.5 测试与验证

| 层 | 命令 | 结果 |
| :--- | :--- | :--- |
| Tag focused | `pytest tests/test_tag_write.py tests/test_tag_query.py tests/test_ownership_guard.py` | **62 passed** |
| Phase 2 guard 回归 | `pytest tests/test_duplicate_query.py tests/test_query_surfacing.py` | passed |
| 全量回归 | `pytest -q` | **883 passed / 0 failed**（基线 825） |
| schema | `python -c`（临时库） | `schema_version=2` / `MIGRATIONS=[1,2]` / **16 表** |
| schema 校验 | `node tools/validate_schema.mjs` | exit 0 |
| model sync | `node tools/check_model_sync.mjs` | exit 0 |
| ownership | `tests/test_ownership_guard.py` | `tags` / `resource_tags` 写**只**在 `core/app/tag_write.py`；Scanner trace 不写 Tag 表 |
| rescan | `tests/test_ownership_guard.py::test_rescan_preserves_resource_tags` | 重扫后 `resource_tags` 保留 |
| read-only | `tests/test_tag_query.py::test_tag_query_performs_no_writes` | 只发 SELECT、`total_changes` 不变 |
| 禁止物 | `rg` on `core/database` | 无 `is_system` / `resource_count` / favorite column / `favorites` table / `library_id` |
| 工作库 | 只读打开 `data/kks_resource_manager.db` | `resources=0` / `tags=0` / `resource_tags=0` / v2（未改动） |

### 18.6 Git 状态（本记录时）

```text
branch  main
HEAD    99aa0d1（未移动）
modified: core/app/__init__.py · core/models/__init__.py · core/query/{__init__,browse,dto,queries}.py
          tests/test_gui_smoke.py · tests/test_ownership_guard.py
new:      core/models/tags.py · core/app/tag_write.py · core/query/{readonly,tag_queries}.py
          tests/test_tag_write.py · tests/test_tag_query.py
docs:     docs/phase3/PHASE3_2_TAG_SYSTEM_ARCHITECTURE_DESIGN.md · PHASE3_2_IMPLEMENTATION_CONTRACT.md · PHASE3_2_LOG.md
未 commit · 未 tag · 未 push
```
