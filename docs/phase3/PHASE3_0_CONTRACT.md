# Phase 3.0 — Architecture / Scope Contract（冻结版）

> 文档类型：**Phase 3 首期 正式 Architecture / Scope Contract（FROZEN）**
> 日期：2026-10-07
> 依据（决策依据，权威顺序从下到上）：
> 1. `docs/phase3/PHASE3_0_ARCHITECTURE_SCOPE_REVIEW.md`（审查）
> 2. `docs/phase3/PHASE3_0_SIMPLE_SUMMARY.md`（摘要）
> 3. `docs/phase3/PHASE3_0_DECISION_REPORT.md`（**决策依据**：D1–D5）
> 前序基线：Phase 1 = CLOSED / PASS；Phase 2 = CLOSED / PASS（tag `phase-2.4-closed`，HEAD `202c285d`）
> 本文件：**只做设计文档**。未改代码 / schema / migration / 测试，未实现任何功能，
> 未创建 commit / tag。

> **修订记录**
> - r1（2026-10-07，Freeze Gate 后 Contract 修订轮）：采用**解法 B** 修正 `display_name` 语义
>   （消除 B1）；并冻结 Favorite 系统标签、Tag 重命名冲突、byte-duplicate 分层、F7 既有边界。

> **冻结声明**：本 Contract 冻结 **Phase 3 首期的能力与架构边界**。
> 它**不**决定 Phase 3 后续子阶段的编号与实施顺序。
> **在本 Contract 被确认之后，任何扩大首期范围的行为都必须走 §16 变更控制，不得擅自扩大。**

---

## 0. 术语与状态标记

本 Contract 对每一项使用三种状态标记：

| 标记 | 含义 |
| :--- | :--- |
| **[FROZEN]** | 已冻结决策；实现必须遵守，不得单方面更改 |
| **[FUTURE-CANDIDATE]** | 明确的未来候选；**不属于**首期，需另立评审 |
| **[OPEN-EVIDENCE]** | 尚缺证据；在取得证据前不决定、不实现 |

---

## 1. Phase 3 核心目标 [FROZEN]

```text
在【不移动 / 不改名 / 不删除 / 不下载文件、不联网、不引入 AI 或语义判断、
   不把推测关系当成事实】的前提下，
把系统从「只读索引」扩展为「可组织、可标注、可人工修正的本地资源管理器」，
并明确划清【机器事实】与【用户数据】的边界。
```

三条可验证子目标：

1. **可组织**：用户能对资源建立分类信息（Phase 3 首期 = **Tag 单一机制**，见 §4）。
2. **可修正**：用户能修正展示名 / 备注 / 类型（激活既有 `type_source` 机制）。
3. **边界清晰**：机器事实与用户数据分层、分写、分权；重扫永不覆盖用户修改；
   管理操作永不触碰用户文件。

**明确不做**：为「功能完整」而增加关系、身份、分类引擎、自动整理，或任何无数据源能力。

---

## 2. 用户数据 / 机器事实所有权 [FROZEN]

### 2.1 机器事实（Scanner / Parser 权威；重扫覆盖是正确行为）

| 载体 | 字段 |
| :--- | :--- |
| `resources` | `file_path`、`file_path_key`、`relative_path`、`file_size`、`modified_time`、`extension`、`sha256`、`card_marker`、`metadata_json`、`name`（解析名）、`parse_status`、`parse_error`、`scan_status`、`last_scanned_at` |
| `resources`（系统） | `id`、`created_at`、`updated_at` |
| `mods` | 全部（`guid` / `name` / `author` / `version` / `website` / `file_path` / `resource_id` / `library_id`） |
| 关系表 | `resource_plugins`、`resource_mod_usages`、`resource_mods`、`resource_authors`、`authors`（由解析结果重建） |

### 2.2 用户数据（用户权威；Scanner / Parser **永不写入**）

| 载体 | 字段 | 首期状态 |
| :--- | :--- | :--- |
| `resources` | `notes` | 首期可写（用户备注） |
| `resources` | `display_name` | 首期可写（**用户覆盖展示名**；纯用户数据，`NULL`=未覆盖；语义见 §3.1） |
| `resources` | `source` / `series` / `description` | 列存在，保留给用户；**首期不强制启用**（可后置） |
| `tags` / `resource_tags` | 全部 | 首期启用（见 §4） |
| `collections` / `resource_collections` | 全部 | **首期不启用**（见 §4 / §13） |
| `authors.notes` | 用户备注 | 列存在；首期不强制启用 |

> **契约修正声明（r1，显式授权）**：`display_name` 在此被明确为**纯用户数据**。
> 这**修正**了 Phase 1 既有 Scanner 行为（旧行为：Scanner 在 INSERT / UPDATE 时写 `display_name`）。
> 修订后：**Scanner / Parser 不得再写 `display_name`**；该修正属于本 Contract 显式授权的
> 契约修正（§3.1 / §16），**不改变 schema v2**（`display_name` 列在 v1 即存在）。

### 2.3 预留 / 未启用（不参与首期）

| 字段 | 状态 |
| :--- | :--- |
| `resources.quick_hash` / `content_key` | deprecated / unused（Phase 2 冻结，沿用） |
| `resources.thumbnail_path` | 从未写入（缩略图走文件名 key，不落此列） |
| `resources.author` / `author_id` | 死列（作者经 `resource_authors` 表达） |
| `resources.needs_review` | 机器布尔，重扫重算；**不能承载用户确认** |
| `duplicate_groups` / `duplicate_members` | 预留、零写入（首期不启用） |

### 2.4 分离机制 [FROZEN]

```text
字段所有权契约 + 优先级规则（§3）+ 单一写服务（§9）+ 护栏测试。
```

- 机器写入者**不得**触碰 §2.2 的用户数据列；
- 用户写入**必须**经 §9 的单一写服务，**不得**经 Query Layer、**不得**在 UI 里写 SQL；
- 首期**不新增数据层、不新增 schema**（§8）。

---

## 3. Shared Field 优先级 与 display_name 语义 [FROZEN]

### 3.1 `name` / `display_name` / effective display name（解法 B，冻结）

```text
name         = Parser / Scanner 的机器解析名（机器事实）
display_name = 用户覆盖值，可为 NULL（纯用户数据）

effective_display_name =
    display_name IS NOT NULL ? display_name : name
```

冻结语义（1–11）：

1. `name` 是机器事实，由 Parser / Scanner 管理。
2. `display_name` 是**纯用户数据**。
3. `display_name = NULL` 表示「用户没有设置覆盖值」。
4. `display_name != NULL` 表示「用户明确设置了展示名」。
5. **Scanner / Parser 不得写入 `display_name`**。
6. Scanner / Parser 可以继续更新 `name`。
7. 用户把 `display_name` 设置为与 `name` **完全相同**，**仍**视为明确的用户覆盖（因为它是非 NULL）。
8. Parser 后续改变 `name` 时，只要 `display_name IS NOT NULL`，用户展示名**保持不变**。
9. 用户清除展示名 ⇒ `display_name = NULL` ⇒ 最终展示重新回到当前 `name`。
10. **不新增** `display_name_source` / `is_user_override` / 任何隐藏标记。
11. **不新增** schema / migration；保持 `SCHEMA_VERSION == 2`。

> 说明：`NULL` 与非 `NULL` 是标准 SQL 语义，**不是隐藏状态字段**；
> 该规则不依赖任何「值是否等于旧 `name`」的隐式启发式。

### 3.2 其余 Shared Field 优先级

除 `display_name`（已归为纯用户数据，见 §3.1）外，「一个字段、两种来源」的字段必须遵守：

| 字段 | 机器写入 | 用户写入 | **优先级规则** |
| :--- | :--- | :--- | :--- |
| `resources.resource_type` | `auto`（Parser：`character_card` / `mod` / `unknown`） | 用户修正 | `type_source='user'` 时**用户值胜出**；重扫**不得**覆盖 |
| `resources.type_source` | 默认 `auto` | 切换为 `user` | 共享字段的**开关**，不是自由文本 |

约定：新增任何「机器 + 用户」双来源字段，必须同时定义其优先级与开关；否则视为用户数据（§2.2）。

---

## 4. Tag / Favorite 模型 [FROZEN]

```text
Phase 3 首期【只实现 Tag 单一机制】。
Favorite（收藏）= 一个【保留系统标签】（稳定 name_key），不是新表。
Collection = 【FUTURE-CANDIDATE】：表保留预留，首期不做写 API / 查询 / GUI。
明确【不】同时做两套机制。
```

### 4.1 Tag 能力（首期）

- 创建 / 列表 / 重命名 / 删除标签；
- 给资源加标签 / 去标签；标签来源 `resource_tags.origin = 'user'`；
- 标签是用户数据，只写数据库，**不动文件**。
- **重命名冲突（冻结）**：当目标 `name_key` 已被其它 Tag 占用时，**拒绝操作**
  （首期**不做自动合并**，不增加 merge 语义）。

### 4.2 Favorite 表示（首期）

- 用**保留系统标签**表示，该标签有**稳定 `name_key`**（系统保留）；
- 用户可正常「加收藏 / 去收藏」（即 tag assign / unassign）；
- **不允许**普通 Tag 管理操作**删除或重命名**该保留系统标签；
- **禁止**为 Favorite 新建 `favorites` 表（无证据，且会造成第三套机制）。

### 4.3 选择理由（依据 Decision Report D2）

1. 一个机制覆盖标签 + 收藏，无需第二套模型；
2. 表已存在，成本最低、风险最小，无需 schema 变更；
3. 避免 Tag/Collection 双轨导致的「同一条信息存哪」长期歧义；
4. Collection 的独特价值（专辑内排序 / 策展 UX）目前**缺乏需求证据**。

---

## 5. Category 与 Library / Path 的边界 [FROZEN]

| 概念 | 职责 | 载体 | 类别 |
| :--- | :--- | :--- | :--- |
| **Category（用户分类）** | 「我认为它是什么 / 属于哪里」——标签、收藏、（未来）集合、用户类型修正 | `tags` / `resource_tags` / `type_source` + `resource_type` | **用户数据** |
| **Library** | 扫描根目录 / 扫描范围 | `libraries` + `resources.library_id` | **机器事实** |
| **Path** | 文件物理位置 + 资源身份 | `resources.file_path` / `file_path_key` / `relative_path` | **机器事实** |

三条冻结规则：

1. **改分类只写数据库**：用户修改分类 ⇒ 只写标签 / 用户类型 / 展示名 / 备注；
   **绝不** move / rename / delete / 改写文件，也不改目录结构。
2. **移动不迁移分类**：文件移动 / 改名 ⇒ 归一化路径变化 ⇒ **新资源行**；
   旧行**保留**并标记 `scan_status='missing'`（连同其用户数据一起保留，不删除）；
   用户分类**不会自动迁移**到新行（relocation 见 §6，首期不实现）。
3. **禁止目录结构隐式推导分类**：不得用目录名 / 文件名 / 路径推断「用户分类 / 标签 / 收藏」；
   不得因文件在某文件夹就自动打标签或自动归类。
   说明：搜索命中 `relative_path` 是**检索**行为，不是**分类推导**，两者必须区分。

---

## 6. 当前身份模型及其限制 [FROZEN]

### 6.1 身份模型（保持现状）

| 身份 | 载体 | 稳定性 |
| :--- | :--- | :--- |
| File / Resource 身份 | `file_path_key`（归一化路径，全局唯一，不含 library_id） | 路径稳定则稳定；**移动/改名 ⇒ 变** |
| Content 身份 | `resources.sha256`（原始字节；索引，非唯一键） | 内容不变则稳定；只证明 byte-identical |
| MOD 逻辑身份 | `mods.guid`（唯一） | 与路径无关 |
| Family / Variant 身份 | **不存在** | 且当前无数据源 |

### 6.2 SHA-256 能证明 / 不能证明

| | 内容 |
| :--- | :--- |
| **能证明** | 两份文件**字节完全相同**（byte-identical）——唯一被承认的等价判据 |
| **不能证明** | 同角色、同 MOD、同逻辑资源、同版本、同变体、视觉相似、语义相似 |
| **失效边界** | 只由 `size` / `mtime` 变化或 `mode='full'` 触发重算；同 size 同 mtime 替换是已知盲区 |
| **覆盖范围** | 整个文件字节（含 PNG 尾部容器与 `About.dataID`）⇒ 图像相同但 dataID 不同 ⇒ hash 不同 |

### 6.3 文件移动 / 改名（明确边界，不是模糊状态） [FROZEN]

```text
- Phase 3 首期【不实现 relocation / 移动检测】；保持「路径身份 + 内容身份」现状。
- 移动后 = 新行 + 旧行 scan_status='missing'；用户数据【保留在旧行】；
  Phase 3 首期【不提供】自动或手动的重新关联入口。
- sha256 继续只作内容身份，不承担资源连续性。
- 未来触发条件（满足才重新立项）：出现真实用户「移动文件后希望保留标签/收藏」的需求；
  且须先解决「字节相同副本导致匹配歧义」与「内容同时变化不可识别」两个约束。
```

结论：当前身份模型**对 Phase 3 首期足够**；不引入新的身份键。

> **既有已知边界（登记，不进入 Phase 3 实现）**：`ResourceStore.mark_missing` 当前按
> `library_id = ?` 过滤，因此 `library_id IS NULL` 的资源**不会**被后续扫描标记为 `missing`。
> 这是 Phase 1 / Phase 2 的既有行为（Phase 2.0-A F7），本 Contract 仅**登记**；
> **不得**借此修改 Scanner / Store 行为。

---

## 7. Relationship 分级与首期边界 [FROZEN]

### 7.1 分级（判据）

| 级别 | 含义 | 当前关系 |
| :--- | :--- | :--- |
| **A. 有可靠数据来源（DB 事实）** | 由 Parser 从真实结构读出并入库 | resource→MOD（逐槽位 usage / 汇总）、resource→plugin、resource→author、MOD→自己的文件、resource/MOD→library |
| **B. 可靠派生** | 由既有列只读推导 | 缺失 MOD、孤立 MOD、property 语义类别、review reason、byte-duplicate 组 |
| **C. 仅候选（判据弱，有反例）** | 只能提示，不能当事实 | 同大小、同名（+作者）、同 marker+同名；relocation（字节匹配，含歧义） |
| **D. 必须用户人工确认** | 任何「相似 / 同一 / 相关」的断言 | C 类候选的确认结果；用户手工关联 |
| **E. 无数据来源（禁止凭空建立）** | 语义上可能，但数据里没有 | MOD→MOD 依赖、版本约束、same-character、visual/semantic similarity |

### 7.2 首期关系边界 [FROZEN]

```text
- Phase 3 首期【不新增任何自动关系】：不做依赖图、不做相似图、不做 MOD→MOD、
  不新增 resource↔resource 关系类型。
- 既有 A 类关系与 B 类派生【保持现状、保持只读】，语义一字不改。
- 「关系表达」在首期通过【Tag（组织）】实现，而不是新建关系表。
- C 类候选 / D 类人工确认（含 Byte-Duplicate 的 confirm/dismiss/canonical）【推迟】，不进首期。
- 严禁：为「完整」而凭空建立任何 E 类关系。
```

### 7.3 特别重申：`uses` ≠ `requires` [FROZEN]

- `manifest.xml` 无依赖字段；KKManager `ModInfoBase` 亦无；`resource_mods.relation` 恒为 `uses`；
- 「缺失 MOD」= 被引用但未安装，**不表示依赖不满足**；
- 因此 **MOD→MOD 依赖图属 E 类，禁止建立**。

### 7.4 Byte-duplicate 分层（澄清，不改变 Phase 2.2 / 2.3 语义） [FROZEN]

- **检测结果**（哪些资源 `sha256` 相同）属于现有 **B 类可靠派生**，由 Query Layer 只读计算，**不落库**；
- **confirm / dismiss / canonical** 是**用户确认层**，属于 **D 类**；
- 该用户确认层仍是 **Phase 3 首期 Out of Scope**（§13-7）；
- 本澄清**不改变** Phase 2.2 / 2.3 的既有语义（`duplicate_*` 继续预留、零写入）。

---

## 8. Schema v2 零变更结论 [FROZEN]

```text
Phase 3 首期【不需要 schema 变化】，保持 SCHEMA_VERSION == 2、16 张业务表。
```

理由：Tag 所需 `tags` / `resource_tags` 已存在（含 `origin='user'`、`color`、`category`）；
用户标量字段 `notes` / `display_name` / `source` / `series` / `description` 已存在；
用户类型修正所需 `type_source` 已存在；Favorite 用保留标签表达 ⇒ 不需新表。

> 注：解法 B 对 `display_name` 的语义修正（§3.1）**不需要 schema 变化** ——
> `display_name` 列在 v1 即存在；修正只涉及**写入规则**（Scanner 不再写它）与**读取规则**
> （`display_name or name`），两者都不是 DDL。

**首期禁止**：创建 v3、新增 migration、新增表 / 列 / 索引。

**明确推迟的 schema 事项（[FUTURE-CANDIDATE]，属独立评审，不属首期）**：

| 事项 | 可能需要的 schema | 触发条件 |
| :--- | :--- | :--- |
| 持久 review 状态（confirmed/dismissed） | 新列或新表（候选 v3） | 首期之后，若确认流程被纳入范围 |
| 重复组持久化确认 / canonical | 可用既有预留表，但需定义生命周期 | 出现用户「标记保留项 / 忽略」真实需求 |
| relocation / 移动重关联 | 无新 schema 也可能可行，但需定义歧义规则 | 出现真实移动保留需求 |

> 若未来确需 schema 变化：**只追加新版本迁移**，不改 `_V1_SQL` / `_V2_SQL`，
> 加列走 `MIGRATION_ADDED_COLUMNS`（幂等）。

---

## 9. 用户写入的单一写服务原则 [FROZEN]

```text
所有用户写入必须经【单一薄写服务】（对称于既有 LibraryAdminService），
不得经 Query Layer，不得在 UI 内拼 SQL。

写服务必须定义：事务边界 / 幂等 / 冲突语义 / 错误语义。

分层保持单向：ui → core；写经写服务；读经 Query / Browse；core 永不 import PyQt6。
```

- 写服务是**唯一**的用户数据写入口；
- 机器写入（Scanner / ResourceStore）继续只写 §2.1 的机器事实列；
- 写服务**不**负责扫描、解析、文件操作。

---

## 10. Query Layer 继续只读 [FROZEN]

```text
Query Layer 保持只读：_execute_select 只放行 SELECT / WITH，否则抛 ReadOnlyViolation。
```

- 按标签浏览等新读能力必须是 **additive SELECT**（只读），不得改变既有筛选语义；
- 用户写入**不得**通过 Query Layer；
- DTO 变更必须向后兼容（新增字段带默认值、置末尾），沿用 Phase 2.3 惯例。

---

## 11. 文件系统只读边界 [FROZEN]

```text
管理资源的信息 与 直接操作资源文件 必须保持边界。
默认不移动 / 不改名 / 不删除 / 不下载文件、不联网、不引入 AI / 语义判断、
不把推测关系当成事实。
```

| 原则 | 首期要求 |
| :--- | :--- |
| 不移动文件 | 组织只写 DB；不得 `move` |
| 不改名文件 | 展示名只写 `display_name` 列；不得 rename |
| 不删除文件 | 标签删除只删 DB 行；不得 remove |
| 不下载 / 不联网 | 不新增网络依赖、运行时不发请求 |
| 不引入 AI / 语义判断 | 无 embedding / phash / 云端 API |
| 不把推测当事实 | 候选/推测不得写入事实字段或事实视图 |

唯一允许的文件写入保持为派生缓存 `data/thumbnail_cache/`（既有 PreviewService，未变）。

---

## 12. In Scope（Phase 3 首期，能力级） [FROZEN]

> 只冻结**能力范围**，不写死子阶段编号与顺序（§15）。

1. **Tag 体系（唯一组织机制）**：创建 / 列表 / 重命名 / 删除标签；给资源加 / 去标签；
   来源 `origin='user'`。
2. **Favorite**：以保留系统标签实现的收藏（加 / 去收藏）。
3. **用户标量修正**：备注（`notes`）、展示名**覆盖**（`display_name`，含清除为 `NULL`）、
   类型修正（`type_source='user'`）（`display_name` 语义见 §3.1）。
4. **单一写服务**：事务 / 幂等 / 冲突语义明确（§9）。
5. **字段所有权契约 + 护栏**：机器写入者不得写用户列（含测试）。
6. **按标签浏览**：Query / Browse 增加**只读**标签筛选（additive）。
7. **至少一个入口（CLI 与/或 GUI）**：入口先后顺序为未决项（§14-OPEN-EVIDENCE）；
   GUI 必须消费写服务，不得写 SQL。

---

## 13. Out of Scope（Phase 3 首期，明确排除） [FROZEN]

| # | 排除项 | 依据 |
| :-- | :--- | :--- |
| 1 | 移动 / 改名 / 删除 / 下载文件 | §11 核心边界；删除属 Phase 5 |
| 2 | 联网 / 在线元数据 / 云同步 / 多用户 | 本地优先、零网络 |
| 3 | AI / 语义判断 / 自动打标 / 自动整理 / 自动分类 | 硬约束 + 无证据 |
| 4 | filesystem watcher / 自动扫描 / 自动刷新 | Phase 1.5-D 明确定义为需证据驱动 |
| 5 | **Collection** | §4：避免双轨，需求证据不足 |
| 6 | **持久 review 状态 / 确认流程** | §8：需独立 schema 决策 |
| 7 | **Byte-duplicate 的 confirm / dismiss / canonical 持久化** | §7：候选/确认层推迟 |
| 8 | **relocation / 移动检测 / 资源连续性** | §6：明确记录为边界 |
| 9 | MOD→MOD 依赖图 / 版本约束 / 版本实体 | 无数据来源 |
| 10 | 新语义身份键（Family / Variant / logical resource） | 无数据源 |
| 11 | same-character / visual / semantic similarity（事实） | NOT DETECTABLE |
| 12 | 1:N File/Resource 拆分 / 通用 Entity-Relation 表 | 无样本 |
| 13 | 把推测关系当事实 | §11 核心边界 |
| 14 | 首期 schema v3 / 任何 migration | §8 |
| 15 | 把早期 roadmap（Phase 3=标签+分类）当既有 Contract | 已知文档漂移 |

---

## 14. 决策分类

### 14.1 已冻结决策 [FROZEN]

| ID | 决策 |
| :-- | :--- |
| D1 | 用户数据 / 机器事实以「字段所有权契约 + 优先级 + 单一写服务 + 护栏」分离；首期不新增数据层/schema |
| D2 | 首期只做 Tag；Favorite = 保留系统标签；Collection 暂缓 |
| D3 | Category 与 Library/Path 彻底分离；改分类只写 DB；移动不迁移分类；禁止目录结构推导分类 |
| D4 | 路径身份 + sha256 足够；首期不做 relocation；明确记录边界 |
| D5 | 首期不新增自动关系；既有 usage/派生保持只读不变；禁止凭空建关系 |
| S1 | 首期零 schema 变更，保持 `SCHEMA_VERSION == 2`、16 表 |
| S2 | 用户写入经单一写服务；Query Layer 继续只读 |
| S3 | 文件系统只读边界不变 |
| S4 | `name`=机器事实；`display_name`=纯用户数据（`NULL`=未覆盖）；`effective_display_name = display_name or name`；Scanner/Parser 不得写 `display_name`（解法 B，显式修正 Phase 1 行为） |

### 14.2 明确的未来候选 [FUTURE-CANDIDATE]

| ID | 候选 | 前置 |
| :-- | :--- | :--- |
| F1 | Collection（策展 / 排序） | 先给出「为什么 Tag 不够」的真实需求证据 |
| F2 | 持久 review 状态（confirmed/dismissed） | 独立 schema 评审 |
| F3 | 重复组持久化确认 / canonical / dismiss | 定义生命周期 + 真实需求 |
| F4 | relocation / 移动重关联 | 真实移动需求 + 歧义规则 |
| F5 | 候选关系（同大小/同名等）+ 人工确认 | 确认语义载体 |
| F6 | `source` / `series` / `description` / `authors.notes` 的用户启用 | 真实需求 |

### 14.3 尚未有证据的问题 [OPEN-EVIDENCE]

| ID | 问题 | 证据缺口 |
| :-- | :--- | :--- |
| U1 | 真实组织需求与标签粒度 | 持久工作库 0 资源；标签/集合零使用 |
| U2 | 入口先后：core→CLI 先，还是 core→GUI 先 | 无真实使用反馈 |
| U3 | 组织范围是否全局（倾向全局，与身份一致） | 无多库真实样本 |
| U4 | 何时需要持久 review 状态 | 样本 `needs_review=0` |
| U5 | 移动场景真实发生率与容忍度 | 无真实移动样本 |

> 以上 [OPEN-EVIDENCE] 项在取得证据前不决定、不实现。

---

## 15. 不写死子阶段编号与顺序 [FROZEN]

```text
本 Contract 只冻结 Phase 3 首期的能力与架构边界，
【不】决定也不写死后续子阶段的编号（如 3.1 / 3.2 / 3.3）与实施顺序。
后续子阶段的切分与排期，由 Contract 被确认之后另行决定。
```

---

## 16. 变更控制（禁止擅自扩大范围） [FROZEN]

```text
1. 本 Contract 冻结后，任何扩大 Phase 3 首期范围的行为都必须：
   （a）新增一次「范围 / 架构评审」；并且
   （b）更新本 Contract（或产出新版本）；并且
   （c）经用户明确确认。
2. 【FROZEN】决策不得在实现阶段被顺带更改；
   如需更改，必须先走 (a)(b)(c)。
3. 【FUTURE-CANDIDATE】项不得在首期实现中被「顺手一起做」。
4. 【OPEN-EVIDENCE】项在取得证据前不得实现。
5. 本 Contract 不修改 Phase 1 / Phase 2 的既有契约；
   schema v2 / Content Identity / Byte Duplicate / Query Layer 只读护栏保持原样。
   唯一例外：`display_name` 的写入归属由本 Contract **显式修正**（§3.1，解法 B）——
   这是经用户确认的**授权修正**，不涉及 schema，也不改变 Phase 2 语义。
6. 除 §3.1 的授权修正外，本 Contract 不得改动 Phase 1 的任何其它既有行为。
```

---

## 17. Definition of Done（Phase 3.0）

Phase 3.0 视为完成，当且仅当：

1. 本 Contract 被用户确认（冻结）；
2. D1–D5 + S1–S4 在 Contract 中记录；除 D1 关于 `display_name` 的细节由 §3.1（解法 B）细化外，
   与 Decision Report 无冲突；
3. In Scope / Out of Scope 与 Decision Report 一致，且**未扩大**；
4. Schema 结论明确：首期零变更；且**未偷偷引入 v3**；
5. 与 Phase 2 的兼容性检查通过；
6. 风险 / 未来候选 / 待证据问题均已分类登记；
7. **在以上全部满足之前，不进入任何 Phase 3.x 实现。**

> 本 Contract 已按上述 1–6 编制；第 1 项（用户确认）待用户执行。
> 若用户确认，Phase 3.0 进入最终关闭与 Git 收尾（`commit` / `tag` 由用户决定）。

---

## 附录 A — 与 Decision Report 的一致性声明

本 Contract 的每一项决策**均取自** `docs/phase3/PHASE3_0_DECISION_REPORT.md`
的 D1–D5、Schema 结论、In Scope、Out of Scope 与核心边界，**未新增任何首期能力**。

> 说明（r1）：`display_name` 的实现语义在 Freeze Gate 后被明确为解法 B（§3.1）。
> Decision Report §3.1 曾把 `display_name` 列为「共享字段（值 ≠ 旧 `name` 时保留，否则跟随解析名）」，
> 该细节与解法 B **不一致**；按用户确认的解法 B，本 Contract §3.1 为该字段的**权威冻结语义**。
> 按本轮约束，**Decision Report 未被修改**；其 §3.1 相应细节视为被本 Contract 取代。

| Decision Report | 本 Contract | 一致性 |
| :--- | :--- | :--- |
| D1 用户数据/机器事实分离 | §2 / §3 / §9 | ✅ 一致 |
| D2 只做 Tag；Favorite=保留标签；Collection 暂缓 | §4 / §13-5 | ✅ 一致 |
| D3 Category vs Library/Path 分离 | §5 | ✅ 一致 |
| D4 身份模型 + 不解决 relocation | §6 | ✅ 一致 |
| D5 首期不新增自动关系 | §7 | ✅ 一致 |
| Schema 首期零变更 | §8 | ✅ 一致 |
| In Scope | §12 | ✅ 一致，未扩大 |
| Out of Scope | §13 | ✅ 一致，未缩小 |
| 核心边界（管理信息 vs 文件操作） | §11 | ✅ 一致 |
| display_name 语义修正（解法 B） | §2.2 / §3.1 / §12-3 | ✅ 修正 B1；D1 的细化，未扩大范围 |
| Favorite 系统标签规则 | §4.2 | ✅ 补充 D2 可执行细节，未扩大能力 |
| Tag 重命名冲突（拒绝，不合并） | §4.1 | ✅ 补充 D2 可执行细节，未扩大能力 |
| Byte-duplicate 分层澄清 | §7.4 | ✅ 澄清 D5，未改变 Phase 2.2 / 2.3 语义 |
| F7 既有边界登记 | §6.3 | ✅ 仅登记，不进入实现，不改 Scanner |

## 附录 B — 本轮只读合规核对

| 禁止项 | 状态 |
| :--- | :--- |
| 修改代码 | ✅ 未做 |
| 修改 schema | ✅ 未做（`SCHEMA_VERSION == 2`） |
| 创建 migration | ✅ 未做 |
| 修改测试 | ✅ 未做 |
| 实现 Tag / Favorite / 用户编辑 / Query tag filter | ✅ 未做 |
| 创建 commit | ✅ 未做 |
| 创建 tag | ✅ 未做 |
| 修改既有文档 | ✅ 未做（Review / Simple Summary / Decision Report 均原样保留） |
| 唯一新增物 | 本文件 `docs/phase3/PHASE3_0_CONTRACT.md` |

> **r1 修订轮补充**：本轮仅修订 `docs/phase3/PHASE3_0_CONTRACT.md`（允许项）；
> Review / Simple Summary / Decision Report **未修改**；未改代码 / schema / migration / 测试；
> 未创建 commit / tag；未进入 Phase 3.1。
