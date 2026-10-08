# Phase 3.2 — Tag System

## Architecture Design

### DESIGN ONLY / CANDIDATE（Contract Freeze 前的设计修订版）

> 文档类型：**架构设计（设计文档，非契约）**。可作为 Phase 3.2 Implementation Contract 的输入，
> 但本身不是冻结契约。
> 阶段：**Phase 3.2 — Tag System**
> 日期：2026-10-08
> 权威契约（从高到低）：
> 1. `docs/phase3/PHASE3_0_CONTRACT.md`（Phase 3 首期 Architecture / Scope Contract）
> 2. `docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md`（Search & Taxonomy Review）
> 3. `docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md`（User Write Foundation，已实现）
> 前序：Phase 3.1 = CLOSED / PASS（tag `phase-3.1-closed`，HEAD `99aa0d1`）
> 本文件**只做设计**。未修改任何功能代码 / schema / migration / 数据库 / 测试 / CLI / GUI；
> 未创建 Tag；未实现 TagWriteService / TagQuery；未 commit / tag。
> 本版本 = 上一轮设计评审的**修订收敛版**，落实 D1–D6（见 §0）。

---

## 0. 本次修订摘要（D1–D6）

| # | 修订 | 结果 |
| :-- | :--- | :--- |
| **D1** | 冻结 Tag scope = **GLOBAL** | 删除原 Open Question U3；见 §4 |
| **D2** | **删除** `TagQuery.resolve()` | 只保留确定性的 read API；见 §13 |
| **D3** | 明确 `set_favorite()` 语义 | 仅为保留系统 Tag 的 domain convenience；底层唯一事实仍是 `resource_tags`；见 §10 / §11 |
| **D4** | 明确 `resource_count` = **derived read data** | 不落库、不加列、不加 counter cache；见 §15 |
| **D5** | 明确 `color` / `category` 语义 | 只是现有 Tag metadata，不引入 taxonomy / classification；见 §16 |
| **D6** | **删除** Phase 3.2 的可选 CLI 实现 | 3.2 只做 domain / service / query foundation；入口属 3.5；见 §2 |

---

## 1. Scope

Phase 3.2 只处理一件事：

> **用户如何给 Resource 做组织和标记。**

设计覆盖：

1. **Tag model**：数据模型、identity、name、`name_key`、system/user 区分、uniqueness、ownership、lifecycle；
2. **Tag CRUD**：create / rename / delete；
3. **Resource ↔ Tag**：assign / unassign / list；
4. **Collision**：name normalization、`name_key` 生成、create/rename 冲突、大小写、空白 / Unicode；
5. **System Tag**：system 与 user 的区别、ownership、reserved key、不可 rename / delete；
6. **Favorite**：保留系统 Tag 表达，禁止第二套持久化；
7. **Write architecture**：`TagWriteService`；
8. **Query Layer**：Tag / Resource↔Tag / Favorite 的**只读基础事实**；
9. **Ownership**：把 Phase 3.1 的 ownership 原则扩展到 Tag；
10. **Schema / migration 评估**。

交付物：本设计文档 + `docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md`（FROZEN / PASS）。
本阶段**不实现**任何功能。

---

## 2. Non-Goals

```text
Search Query Model
field:value
AND / OR / NOT
全文搜索
Tag 搜索语法（tag: / favorite: / prefix / fuzzy）
tag filtering / favorite filtering / BrowserScope tag filtering
GUI Tag Management
GUI Favorite UI
CLI / GUI 用户入口（属 Phase 3.5）
自动分类 / 自动打标
Tag ↔ Resource Type 自动转换
Tag ↔ Usage Category 自动转换
AI / 语义 / 感知分类
Collection
任何 schema / migration / 新表 / 新列 / 新索引
任何文件移动 / 改名 / 删除 / 下载 / 联网
```

特别声明：

> **`TagQuery` 是 read model，不是 Search Engine。**
> Query Layer 暴露 Tag **不等于** Search 已实现。

Phase 3.2 **不修改** `main.py` / `cli_query.py` / `ui/*`（除 ownership / UI guard 测试所必需的纯测试修改），
**不新增任何用户入口**。

---

## 3. Repository Baseline

以仓库当前真实状态为准（只读实测）：

| 项 | 现状 |
| :--- | :--- |
| HEAD / branch | `99aa0d1` / `main`；评审开始时工作区 clean |
| schema | `SCHEMA_VERSION == 2`；`MIGRATIONS == {1, 2}`；业务表 **16** |
| `tags` | 已存在：`id, name, name_key UNIQUE, color, category, created_at, updated_at` |
| `resource_tags` | 已存在：`resource_id`(FK CASCADE), `tag_id`(FK CASCADE), `origin CHECK('user','auto')`, `created_at`；PK `(resource_id, tag_id)` |
| 索引 | `idx_resource_tags_tag(tag_id)` |
| **Tag 运行期使用** | **零**：`tags` / `resource_tags` 不出现在任何 INSERT/UPDATE/DELETE / 查询中（仅 schema + 测试夹具） |
| 持久工作库（只读） | `resources=0`、`tags=0`、`resource_tags=0`、`collections=0`、`schema_version='2'` |
| 归一化 | `core/database/db.py::normalize_name_key(text) = (text or "").strip().casefold()`（注释已写明用于标签去重） |
| 用户写服务 | `core/app/resource_write.py::ResourceWriteService`（只写 `display_name` / `notes` / user type + `type_source`） |
| Query Layer | `core/query/queries.py`；`_execute_select` 仅放行 `SELECT` / `WITH`，否则 `ReadOnlyViolation` |
| Ownership guard | 仅 `core/scanner/store.py`（machine）与 `core/app/resource_write.py`（user）可写 `resources` |
| 机器写入者 | `store.py` 不触碰 `tags` / `resource_tags`；全仓无 `DELETE FROM resources` |

结论：**Tag 所需的两张表已存在且完全未被使用**，3.2 在零 schema 变更下即可落地。

---

## 4. Global Tag Scope（D1 — FROZEN）

### 4.1 冻结结论

```text
Tag 是 GLOBAL organization data，不是 per-library data。
```

- 一个 Tag 在**整个库集合**内只有一个 identity（`tags.name_key` 全局唯一）；
- 一个 Tag 可标注**任意 library 以及 `library_id IS NULL` 的资源**；
- `resource_tags` 只表达 `(resource, tag)`，**不携带 `library_id`**；
- 不存在「同名但属于不同 library 的 Tag」。

### 4.2 依据

1. **schema 已天然是 global**：`tags.name_key` 是**全局 UNIQUE**，`tags` 没有 `library_id` 列。
   per-library 语义在 schema v2 下**不可表达**（会需要 `tags.library_id` + 复合唯一键）。
2. **identity 模型是 global**：`resources.file_path_key` 全局唯一、不含 `library_id`
   （Phase 3.0 §6.1）；Resource identity 与 scan root 无关，因此组织它的 Tag 也应与 scan root 无关。
3. **Library 是 machine fact，不是 organization**：Phase 3.0 §5 明确 Library = 扫描根目录 /
   扫描范围（machine fact），Category（用户分类）与 Library/Path 彻底分离。
4. **`library_id` 可空**：`resources.library_id` 允许 `NULL`（Phase 3.0 §6.3 已登记
   `mark_missing` 的既有边界）。per-library Tag 会让这类资源无法被组织；global 不受影响。
5. **改分类不动文件 / 不迁移**：Phase 3.0 §5 冻结「改分类只写数据库；移动不迁移分类」——
   这与 Tag 独立于 physical location / library 一致。

### 4.3 与 Phase 3.0 U3 的关系（显式记录）

Phase 3.0 §14.3 曾把 U3「组织范围是否全局（倾向全局，与身份一致）」列为
**[OPEN-EVIDENCE]**（证据缺口：无多库真实样本），并在 §16.4 规定「OPEN-EVIDENCE 项在取得证据前不得实现」。

Phase 3.2 的处置：

```text
本阶段不新增任何 per-library 能力；
只是声明「在冻结的 schema v2 + 全局 identity 下，Tag 只能且必须是 global」。
```

- 这不是「凭证据决定 U3」，而是**对冻结 schema 表达能力的边界声明**：per-library 方案在 v2 下不可实现；
  若未来确实需要，属**新的 architecture / schema change**，必须另行走 Phase 3.0 §16 变更控制
  （评审 + 更新 Contract + 用户确认），**不得**作为 Phase 3.2 的隐藏能力。
- 因此 U3 在 Phase 3.2 范围内**关闭为 GLOBAL**；per-library 转入
  **[FUTURE-CANDIDATE]（需 schema 变更）**，不再是本阶段的 Open Question。

---

## 5. Tag Domain Model

```text
Tag
 ├─ id          INTEGER PK                （surrogate identity）
 ├─ name        TEXT NOT NULL             （display text）
 ├─ name_key    TEXT NOT NULL UNIQUE      （normalized business identity）
 ├─ color       TEXT NULL                 （现有 metadata，见 §16）
 ├─ category    TEXT NULL                 （现有 metadata，见 §16）
 ├─ created_at  TEXT NOT NULL DEFAULT (datetime('now'))
 └─ updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
```

Tag 属于 **user-owned organization data**，不是 machine fact。Tag **不得**被定义成：

```text
MOD dependency
Resource relationship
semantic fact
machine-derived fact
Resource Type 的替代物
Usage Category 的替代物
```

三条语义轴保持分离（Phase 3.0.2 §4.3 / §7.3）：

```text
Resource Type   = 这个资源是什么
Usage Category  = 资源里的 MOD 被用在哪
Tag             = 用户想如何组织这个资源
```

system / user 区分：**由保留 key 派生**，不落列（见 §9）。

---

## 6. Resource ↔ Tag Model

```text
Resource
   │
   │ N:M
   ▼
resource_tags
   │
   ▼
Tag
```

| 列 | 语义 |
| :--- | :--- |
| `resource_id` | FK → `resources(id)`，`ON DELETE CASCADE` |
| `tag_id` | FK → `tags(id)`，`ON DELETE CASCADE` |
| `origin` | Phase 3.2 恒为 `'user'`；`'auto'` 保留但**不使用** |
| `created_at` | 赋值时间 |
| PK `(resource_id, tag_id)` | 同一 Tag 不重复赋给同一资源（去重） |

事实边界：

- **唯一持久化事实** = `resource_tags` 行；assign / unassign 只改这张表；
- Scanner / Parser **永不动**这张表；
- 资源行不会被扫描硬删除，因此 assignment 会随资源保留（Phase 3.0 §6.3）。

---

## 7. Tag Identity / name_key

| 概念 | 载体 | 性质 |
| :--- | :--- | :--- |
| surrogate identity | `tags.id` | 内部引用键（`resource_tags.tag_id`） |
| business identity | `tags.name_key`（UNIQUE） | 归一化后的稳定身份；跨库全局唯一 |
| display text | `tags.name` | 可读文本；用户 Tag 可被 rename 改写 |

`name_key` 生成规则（**复用既有 policy，不新造**）：

```text
name_key = normalize_name_key(name)
         = (name or "").strip().casefold()
```

冻结语义：

1. **大小写不敏感**：`Favorite` / `favorite` / `FAVORITE` 归一化后相同 ⇒ 视为同一 key（冲突）；
2. **空白**：仅去除首尾空白（`strip()`）；**内部空白保留**（不做内部折叠）；
3. **Unicode**：使用 Python `str.casefold()`（Unicode-aware）；**本阶段不引入 NFC/NFKC 归一化**；
4. **空白 / 空串 / 非字符串 ⇒ 拒绝**（`InvalidTagValue`）；
5. `name_key` 是**派生值**：由 create / rename 时的 `name` 计算，不作为独立用户输入；
6. 除 `rename`（重新计算）外，`name_key` 不单独变更。

> 已知边界（登记，不在本阶段解决）：未做 NFC/NFKC 意味着视觉相同、但码点组合不同的名称可能
> 生成不同 `name_key`。此为**复用既有仓库 policy 的已知代价**，不扩大规范化范围；
> 若未来出现真实需求，属独立评审。

---

## 8. Collision Policy

| 操作 | 条件 | 结果 |
| :--- | :--- | :--- |
| `create_tag` | `name_key` 已被任一 Tag 占用 | **拒绝** `TagNameConflict`（不合并、不静默复用） |
| `create_tag` | `name_key` 属保留系统 key | **拒绝** `ReservedTagName` |
| `rename_tag` | 新 `name_key` 已被**其它** Tag 占用 | **拒绝** `TagNameConflict`（Phase 3.0 §4.1：拒绝，不自动 merge） |
| `rename_tag` | 新 `name_key` 属保留系统 key | **拒绝** `ReservedTagName` |
| `rename_tag` | 新 `name_key` = 自身当前 key | **允许**（幂等；仅可能更新 `name` / `updated_at`） |
| 任意 | `name` 为空白 / 非字符串 | **拒绝** `InvalidTagValue` |

兜底：`tags.name_key` 的 `UNIQUE` 约束是最后防线；服务在插入 / 更新前做显式检查，
并防御性地把 `sqlite3.IntegrityError`（UNIQUE）映射为 `TagNameConflict`。

明确禁止：

```text
自动 merge（首期不做）
静默复用已存在的 Tag（create 不返回既有 tag）
大小写视为不同 Tag
```

---

## 9. System Tag Model

### 9.1 判定方式（零 schema）

```text
is_system_tag = (name_key ∈ RESERVED_SYSTEM_TAG_KEYS)
```

- 注册表在代码中（`core/models/tags.py`，纯数据，无 DB 依赖）；
- **不新增** `tags.is_system` 列（保持 schema v2 零变更）。

### 9.2 保留 key

```text
RESERVED_SYSTEM_TAG_KEYS = { "favorite" }

SYSTEM_TAGS["favorite"]:
    name_key = "favorite"
    name     = "Favorite"      （display；本地化留 3.5）
```

### 9.3 语义

| 维度 | 规则 |
| :--- | :--- |
| ownership | **System-owned**（系统 bootstrap 定义行），不是普通用户数据 |
| 初始化 | `TagWriteService.ensure_system_tags()` 幂等保证存在（**lazy / on-demand**；见 §11） |
| rename | **禁止**（`SystemTagImmutable`） |
| delete | **禁止**（`SystemTagImmutable`） |
| 用户创建同 key | **禁止**（`ReservedTagName`） |
| assign / unassign | **允许**（与普通 Tag 同一路径，`origin='user'`） |

### 9.4 边界

若历史库存在 `name_key = "favorite"` 的用户行，按 §9.1 会被视为系统 Tag。
当前真实库 `tags=0`，该情形不存在；登记为边界，不额外增加机制。

---

## 10. Favorite Model

```text
favorite
    ↓
reserved system Tag（name_key = "favorite"）
    ↓
resource_tags
```

冻结规则：

1. Favorite 的**唯一持久化事实**是 `resource_tags`；
2. **禁止** `resources.favorite` 列；
3. **禁止** 独立 `favorites` 表；
4. Favorite 与普通 Tag 使用**同一 persistence path、ownership path、transaction discipline**；
5. `set_favorite()` 只是 domain convenience，不是第二套机制（见 §11.4）。

等价关系（契约级）：

```text
set_favorite(resource, True)   ≡  assign_tag(resource, reserved_favorite_tag)
set_favorite(resource, False)  ≡  unassign_tag(resource, reserved_favorite_tag)
```

Query 侧只读暴露（见 §13 / §14）：

```text
TagQuery.is_favorite(resource_id) -> bool
TagQuery.favorite_resource_ids()  -> list[int]
ResourceDetail.is_favorite        -> bool
```

---

## 11. TagWriteService Architecture

### 11.1 定位

```text
ResourceWriteService  →  Resource-owned user data     （display_name / notes / user type）
TagWriteService       →  Tag-owned user organization   （tags / resource_tags）
Query Layer           →  read-only Tag / Resource↔Tag facts
```

`TagWriteService` 是 **`tags` / `resource_tags` 的唯一 runtime writer**。
它是 Tag 域的「单一薄写服务」，与 `ResourceWriteService` 对称；不吞并、不膨胀既有服务。

### 11.2 允许的写操作

```text
TagWriteService
    ├── create_tag
    ├── rename_tag
    ├── delete_tag
    ├── assign_tag
    ├── unassign_tag
    ├── set_favorite
    └── ensure_system_tags
```

### 11.3 事务 / 幂等 / 存在性

- 每个 public 写方法 = **一个 `db.transaction`**；失败整体回滚并原样抛出；
- **存在性优先**：目标不存在 ⇒ 显式错误（不靠「affected rows = 0」猜测）；
- `assign_tag` / `unassign_tag` / `set_favorite` / `ensure_system_tags` **幂等**；
- `create_tag` **不幂等**（冲突必须显式报错，避免掩盖 merge）。

### 11.4 `set_favorite` 语义（D3）

```text
set_favorite(resource_id, favorite: bool) -> None
```

- 先检查 resource 存在；不存在 ⇒ `ResourceNotFound`；
- 内部 `ensure_system_tags()`，取得保留 `favorite` Tag 的 id；
- `favorite=True` ⇒ 走 `assign_tag`（幂等）；
- `favorite=False` ⇒ 走 `unassign_tag`（幂等）；
- **不写任何第二套 Favorite 状态**；底层事实永远只有 `resource_tags`。

### 11.5 系统 Tag 初始化

- `ensure_system_tags()`：对每个 `SYSTEM_TAGS` 条目执行幂等
  `INSERT … ON CONFLICT(name_key) DO NOTHING`；
- 调用时机（**lazy / on-demand — Phase 3.2 冻结语义**）：**不**在 `database.initialize()`
  之后 eager 预置；`ensure_system_tags()` 是**权威、幂等**的 bootstrap seam，
  由 `set_favorite()` 在**自身事务内**按需调用；fresh DB 在尚未发生任何 Tag 写入时可以
  **暂时没有** `favorite` 行（`TagQuery` 只读，**不负责** bootstrap）；
  startup eager bootstrap **不属于 Phase 3.2**，留待后续 CLI / GUI integration 阶段再考虑 wiring；
- Query Layer **永不**创建行；`ensure_system_tags()` 属系统 seed（数据写入，非 DDL）。

---

## 12. Ownership Rules

| Data | Owner | 唯一 Writer |
| :--- | :--- | :--- |
| `tags`（user Tag） | User | `TagWriteService` |
| `tags`（reserved system Tag 定义行） | System（bootstrap） | `TagWriteService.ensure_system_tags()` |
| `resource_tags` | User | `TagWriteService` |
| `resources` user fields | User | `ResourceWriteService`（不变） |
| `resources` / `mods` / 关系 machine facts | Machine | `ResourceStore`（不变） |

**禁止直接写 `tags` / `resource_tags` 的角色**：

```text
Scanner
Parser
ResourceWriteService
Query Layer
GUI
CLI
```

补充冻结：

- Scanner / Parser 继续**只产生 machine facts**，绝不自动制造用户 Tag；
- Phase 3.2 所有 Resource ↔ Tag assignment：`origin = 'user'`；
  `origin = 'auto'` 保留 schema 能力但**本阶段不使用**；
- ownership guard 必须扩展为：`tags` / `resource_tags` 的写语句**只允许**出现在
  `core/app/tag_write.py`。

---

## 13. Query Layer Read Model

### 13.1 定位

`TagQuery` 是**只读 read model**，经 `_execute_select`（仅 `SELECT` / `WITH`）访问数据库；
它**不是** Search Engine，也**不**构成未来 Search Query Model 的前身。

### 13.2 最终 API（D2 — `resolve()` 已删除）

```text
TagQuery
    list()                    -> list[TagSummary]      # 全部 Tag（含 system），稳定排序
    get(tag_id)               -> TagSummary | None
    find_by_name(name)        -> TagSummary | None     # 精确 name_key 查找
    for_resource(resource_id) -> list[TagSummary]      # 该资源的 Tag
    resource_ids(tag_id)      -> list[int]             # 该 Tag 的资源 id
    system_tags()             -> list[TagSummary]      # 保留系统 Tag 子集
    is_favorite(resource_id)  -> bool
    favorite_resource_ids()   -> list[int]
```

**明确删除** `resolve(target)`：其「id / 名称 / 其它多种形态」的宽泛语义不可稳定冻结，
且易滑向 Search 语义。需要按 id 用 `get()`；需要按名用 `find_by_name()`。

### 13.3 `find_by_name` 的严格契约

```text
find_by_name(name):
    key = normalize_name_key(name)     # strip + casefold
    key 为空            -> None
    否则按 name_key = key 精确查找     -> TagSummary | None
```

- **精确匹配**，不做 `LIKE`、不做前缀、不做模糊、不做分词；
- 不返回多个结果；不做「猜测」；
- 它不是搜索入口，只是 identity 解析（拿一个已知名字对应的 Tag）。

### 13.4 只读失败语义

- `get` / `find_by_name`：未找到 ⇒ `None`；
- `for_resource` / `resource_ids`：目标不存在 ⇒ 返回空列表（不抛异常）；
- 读 API **不写库**、不创建系统 Tag。

---

## 14. TagSummary / ResourceDetail

### 14.1 新增 DTO：`TagSummary`

```text
@dataclass(frozen=True)
class TagSummary:
    id: int
    name: str
    name_key: str
    color: str | None
    category: str | None
    is_system: bool
    resource_count: int = 0     # derived（见 §15）
```

`is_system` 为**派生值**（`name_key ∈ RESERVED_SYSTEM_TAG_KEYS`），非持久列。

### 14.2 追加字段：`ResourceDetail`（additive，置末尾、带默认值）

```text
ResourceDetail
    ...（既有字段不变）
    tags: tuple[TagSummary, ...] = ()
    is_favorite: bool = False
```

- 只增不改：既有构造方式保持有效（Phase 2.3 / 3.1 兼容原则）；
- 由 `ResourceQuery.get()` 只读填充，`BrowseService` 只读转发；
- **不**把 `tags` 塞进 `ResourceSummary`（避免列表行 N+1 COUNT，见 §15.3）。

---

## 15. `resource_count` Derived Semantics（D4）

### 15.1 冻结定义

```text
TagSummary.resource_count
    = Query Layer 读取时计算的 derived value
    = 该 Tag 在 resource_tags 中的关联资源数
```

- **不是** Tag persisted state；
- **不得**新增 `tags.resource_count` 列；
- **不得**新增 counter cache / 冗余计数 / 触发器维护的计数；
- 唯一事实来源仍是 `resource_tags`。

### 15.2 一致性

`resource_count` 必须与 `resource_ids(tag_id)` 的长度一致（同一事实的两种只读视图）。
删除 Tag 时，FK cascade 会移除其 `resource_tags`，因此不存在悬空计数。

### 15.3 性能约束（设计层）

> implementation 应避免对 Tag list 产生明显的 N+1 COUNT 查询；
> 可通过一次聚合查询（如 `LEFT JOIN resource_tags … GROUP BY tags.id`）取得全部 count。

具体 SQL 措辞留到 implementation；本条只冻结「derived + 不落库 + 需一次性聚合」的约束。

---

## 16. `color` / `category` Semantics（D5）

现有 schema 已有 `tags.color` / `tags.category`。Phase 3.2 允许**读写暴露**，但冻结：

> `color` / `category` 只是现有 Tag metadata，
> **不在 Phase 3.2 引入任何新的 taxonomy / classification semantics。**

明确禁止把 `category` 解释为或自动影响：

```text
Resource Type
Usage Category
Search field
Taxonomy
```

补充：

- `color` / `category` 为可选文本，采用与既有可选文本一致的归一化
  （`None` / 空白 ⇒ `NULL`；否则 `strip()` 后保存）；
- 它们**不**参与 identity、**不**参与 collision、**不**影响 assign / unassign；
- 它们**不**自动影响 `resource_type` / `type_source` / `resource_mod_usages.property`；
- 它们不作为 Query 的筛选维度（属 3.3 之后的独立决策）。

---

## 17. Schema / Migration Decision

```text
SCHEMA_VERSION == 2
MIGRATIONS == {1, 2}
NO MIGRATION REQUIRED
```

`tags` / `resource_tags` 现有结构**足以**支持 Phase 3.2：

- `name_key UNIQUE` ⇒ global identity + 去重；
- PK `(resource_id, tag_id)` ⇒ assignment 去重与幂等基础；
- 双向 `ON DELETE CASCADE` ⇒ 普通 Tag 删除时自动清理关联；
- `origin` CHECK ⇒ `'user'` / `'auto'`，本阶段只用 `'user'`。

**不得**为 Phase 3.2 新增：

```text
is_system
resource_count
favorite column
favorites table
library_id
```

per-library 若将来需要，属**独立 schema / architecture change**（见 §4.3）。

---

## 18. Error Semantics

`TagWriteService` 异常层次：

```text
TagWriteError(Exception)                 # 基类
 ├─ TagNotFound(tag_id)                  # 目标 Tag 不存在
 ├─ TagNameConflict(name_key)            # create / rename 与既有 Tag 冲突
 ├─ ReservedTagName(name_key)            # 目标是保留系统 key
 ├─ SystemTagImmutable(tag_id)           # 试图 rename / delete 系统 Tag
 └─ InvalidTagValue(field, value)        # 空白名 / 非字符串 / 非法值
```

约定：

- 资源不存在 ⇒ 复用 `core.app.resource_write.ResourceNotFound`（保持单一语义）；
- 任何失败：单个事务整体回滚 + **原样抛出**（不吞异常、不静默降级）；
- `create_tag` 冲突**必须报错**，不得返回既有 Tag；
- Query Layer 读 API 不抛「未找到」异常（返回 `None` / 空列表）。

---

## 19. Test Strategy

### 19.1 写侧不变式

```text
T-A  name_key = normalize_name_key(name)；大小写不敏感；空白名被拒绝
T-B  create 冲突 ⇒ TagNameConflict（不合并、不静默复用）
T-C  rename 到已占用 key ⇒ TagNameConflict；rename 系统 Tag ⇒ SystemTagImmutable
T-D  delete 系统 Tag ⇒ SystemTagImmutable；delete 普通 Tag 级联清理其 resource_tags
T-E  assign / unassign 幂等；origin 恒为 'user'
T-F  set_favorite 幂等；等价于 assign/unassign 保留系统 Tag；用户不能创建 'favorite'
T-G  Scanner 重扫后 resource_tags 保留（资源行不删、机器 writer 不碰 Tag）
T-H  仅 TagWriteService 写 tags / resource_tags
```

### 19.2 读侧 / 兼容性不变式

```text
T-I   TagQuery 只发 SELECT / WITH；不写库、不创建系统 Tag
T-J   find_by_name 为精确匹配（空 / 未知 ⇒ None；不做模糊）
T-K   resource_count == len(resource_ids(tag_id))
T-L   TagSummary / ResourceDetail 追加字段带默认值，既有构造保持有效
T-M   SCHEMA_VERSION==2 / MIGRATIONS=={1,2} / 16 表不变
T-N   ui / cli / scanner / parser / resource_write / query 不得写 tags / resource_tags
```

### 19.3 验证层级

focused（Tag 写 / 读）→ 全量 `pytest`（≥ 现有基线）→ schema 冻结断言 → ownership guard →
rescan 保真不变量。

---

## 20. Phase 3.3 Boundary

3.2 完成后，以下事实**已可被 Query Layer 只读获取**：

```text
Tag facts
Favorite facts
Resource ↔ Tag facts
```

以下全部**留给 Phase 3.3**：

```text
Search Query Model
field:value
tag:
favorite:
AND
OR
NOT
full text search
tag filtering
favorite filtering
BrowserScope tag filtering
unified search syntax
```

> **TagQuery 是 read model，不是 Search Engine。**

---

## 21. Implementation Contract Draft

正式候选契约见：`docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md`。要点：

```text
Write:  TagWriteService.create_tag / rename_tag / delete_tag /
        assign_tag / unassign_tag / set_favorite / ensure_system_tags
Read:   TagQuery.list / get / find_by_name / for_resource /
        resource_ids / system_tags / is_favorite / favorite_resource_ids
DTO:    TagSummary；ResourceDetail += tags / is_favorite
Schema: NO MIGRATION REQUIRED
```

该 Contract 已 **FROZEN / PASS**；system-tag bootstrap 采用 **lazy / on-demand**；
Phase 3.2 implementation 已 **COMPLETE / AUDIT PASS**；
Phase 3.2 **尚未 CLOSED**（Git closure 未执行）。
