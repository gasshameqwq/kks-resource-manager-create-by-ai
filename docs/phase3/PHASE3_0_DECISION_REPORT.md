# Phase 3.0 — Architecture / Scope Decision Report

> 阶段：**Phase 3.0（Architecture / Scope / Contract Review — 决策轮）**
> 日期：2026-10-07
> 前置产物（**保持不变**）：`docs/phase3/PHASE3_0_ARCHITECTURE_SCOPE_REVIEW.md`、
> `docs/phase3/PHASE3_0_SIMPLE_SUMMARY.md`
> 本文件：**Phase 3.0 的决策报告**。
> 本阶段**仍然严格只读**：未改代码 / schema / migration / 测试，未创建 commit / tag。
> **唯一新增物 = 本文件**；既有两份 Phase 3.0 文档**未修改**。

> ⚠️ 本报告**冻结 Phase 3.0 的边界与决策**，但**不是** Phase 3.1 的实现计划，
> **不决定** Phase 3.1 / 3.2 / 3.3 的编号与切分。
> **在本报告的 Definition of Done（§12）满足、且正式 Contract 被确认之前，不进入任何 Phase 3.x 实现。**

---

## 0. 基线核对（本阶段实测）

```text
HEAD        202c285d2e319391e618347a4e46cb0607d84495
tags        phase-2.0-closed / 2.1 / 2.2 / 2.3 / 2.4   （齐备）
working     clean（本阶段开始时；本阶段只新增本文件）
remote      none
pytest      734 passed / 0 failed / 0 skipped
schema      SCHEMA_VERSION == 2，业务表 16，MIGRATIONS == {1,2}
持久库       libraries 0 / resources 0 / mods 0 / tags 0 / collections 0 / duplicate_groups 0
```

本轮新增核对的代码事实：

| 事实 | 证据 |
| :--- | :--- |
| `resources.notes` **无任何写入者** | 全仓仅在 `LibraryStore` 处理 `libraries.notes`；`resources.notes` 零写入 |
| `type_source` **从未被设为 `user`** | 仅 `store.py` 读取判断；无任何 `type_source = 'user'` 写入 |
| `display_name` 只有 Scanner 写；用户改写保护是**条件式** | `store.py`：仅当 `display_name not in (None, old_name)` 时保留旧值 |
| `tags` / `resource_tags` / `collections` / `resource_collections` **零写入** | 全仓无对应 `INSERT / UPDATE` |
| Query Layer **无 tag 过滤** | `_resource_where` 无任何 `tag` 分支 |
| Query Layer **只读护栏** | `_execute_select` 只放行 `SELECT` / `WITH`，否则抛 `ReadOnlyViolation` |

---

## 1. 当前架构事实

### 1.1 分层与边界（Phase 1 / 2 已建立，未变）

```text
ui/  ──读──►  core.query.BrowseService → Query Layer（只读护栏 SELECT/WITH）
ui/  ──写──►  core.app.LibraryAdminService → LibraryStore        （仅 libraries 表）
ui/  ──扫──►  core.app.run_scan → LibraryScanner → Parser + ResourceStore  （扫描入库）
ui/  ──图──►  PreviewWorker → PreviewService（只写 data/thumbnail_cache/）
core/ 永不 import PyQt6；ui/ 不 import sqlite3、不 import *Query 类、不写 SQL
```

### 1.2 身份现状

- **File / Resource 身份 = 路径**（`file_path_key`，全局唯一，不含 library_id）；
- **Content 身份 = `sha256`**（原始字节；索引，非唯一键；仅证明 byte-identical）；
- **MOD 逻辑身份 = `mods.guid`**（唯一）；
- **Family / Variant 身份 = 不存在**，且当前无数据源。

### 1.3 关系现状

- **可靠 DB 关系**：resource→MOD（逐槽位 usage + 汇总）、resource→plugin、resource→author、
  MOD→自己的文件、resource/MOD→library；
- **派生（只读）**：缺失 MOD、孤立 MOD、property 语义类别、review reason、byte-duplicate 组；
- **不存在**：MOD→MOD、resource↔resource（非重复）、author→MOD（实体级）、tag/collection 关系。

### 1.4 用户数据现状

- `tags` / `collections` 及其关联表自 v1 起存在，**从未被使用**；
- `resources.notes` / `display_name` / `source` / `series` / `description` 存在，但
  **除 `display_name` 外无写入者，且没有任何用户入口**；
- 「可人工修正」目前**只有数据层预留，没有实现表面**。

### 1.5 机器事实 vs 用户数据：现状是「混在同一行 + 两条临时保护规则」

现有保护（隐式、非正式契约）：

1. `type_source == 'user'` ⇒ 重扫不覆盖 `resource_type`；
2. `display_name` 已被用户改写（不等于旧 `name`）⇒ 重扫保留该值。

问题：这两条规则写在 `store.py` 内部，**没有成文的所有权契约**，且
`needs_review` 每轮重扫被重算（无法承载用户确认）。

---

## 2. Phase 3 的核心目标（冻结）

```text
在【不移动/改名/删除/下载文件、不联网、不引入 AI 或语义判断、
   不把推测关系当事实】的前提下，
把系统从「只读索引」扩展为「可组织、可标注、可人工修正的本地资源管理器」，
并明确划清【机器事实】与【用户数据】的边界。
```

拆成三条可验证的子目标：

1. **可组织**：用户能对资源建立自己的分类信息（Phase 3 首期 = 标签体系，见 §4）。
2. **可修正**：用户能修正显示名 / 备注 / 类型（激活既有 `type_source` 机制）。
3. **边界清晰**：机器事实与用户数据**分层、分写、分权**；重扫永不覆盖用户修改；
   管理操作永不触碰用户文件。

> 明确不做：为「功能完整」而增加关系、身份、分类引擎、自动整理或任何无数据源能力。

---

## 3. 问题 1 — 用户数据与机器事实如何分离

### 3.1 字段所有权分类（最终）

**机器事实（Scanner / Parser 权威；重扫覆盖是正确行为）**

| 载体 | 字段 |
| :--- | :--- |
| `resources` | `file_path`、`file_path_key`、`relative_path`、`file_size`、`modified_time`、`extension`、`sha256`、`card_marker`、`metadata_json`、`name`（解析名）、`parse_status`、`parse_error`、`scan_status`、`last_scanned_at` |
| `resources`（系统） | `id`、`created_at`、`updated_at` |
| `mods` | 全部（guid/name/author/version/website/file_path/resource_id/library_id） |
| 关系表 | `resource_plugins`、`resource_mod_usages`、`resource_mods`、`resource_authors`、`authors`（由解析结果重建） |

**用户数据（用户权威；Scanner / Parser 永不写入）**

| 载体 | 字段 | 现状 |
| :--- | :--- | :--- |
| `resources` | `notes`（用户备注） | 列存在，无写入者 |
| `resources` | `display_name`（用户展示名） | 有写入者（Scanner 写解析名），需明确「用户值优先」 |
| `resources` | `source` / `series` / `description` | 列存在，无写入者，保留给用户 |
| `tags` / `resource_tags` | 全部 | 表存在，无写入者 |
| `collections` / `resource_collections` | 全部（Phase 3 首期不启用，见 §4） | 表存在，无写入者 |
| `authors.notes` | 用户备注 | 列存在，无写入者 |

**共享字段（一个字段、两种来源、必须定义优先级）**

| 字段 | 机器写入 | 用户写入 | 优先级规则 |
| :--- | :--- | :--- | :--- |
| `resources.resource_type` | `auto`（Parser 结果：`character_card` / `mod` / `unknown`） | 用户修正 | `type_source='user'` 时用户值胜出；重扫不得覆盖 |
| `resources.display_name` | 首次 = 解析名 | 用户改写 | 一旦用户改过（≠ 旧 `name`），重扫保留；否则跟随解析名 |
| `resources.type_source` | 默认 `auto` | 切换为 `user` | 这是**共享字段的开关**，不是自由文本 |

**预留 / 未启用（不参与 Phase 3 首期）**

| 字段 | 状态 |
| :--- | :--- |
| `resources.quick_hash` / `content_key` | deprecated / unused（Phase 2 冻结） |
| `resources.thumbnail_path` | 从未写入（缩略图走文件名 key，不落此列） |
| `resources.author` / `author_id` | 死列（作者经 `resource_authors` 表达） |
| `resources.needs_review` | 机器布尔，重扫重算；**不能承载用户确认**（见 §3.4） |
| `duplicate_groups` / `duplicate_members` | 预留、零写入（见 §9） |

### 3.2 重扫避免覆盖用户修改的机制（最终）

采用**「显式字段所有权 + 优先级规则 + 单一写入口」**，而不是新数据层：

1. **所有权成文**：本 §3.1 的所有权表即契约；机器写入者不得触碰「用户数据」列。
2. **优先级规则**：共享字段沿用既有 `type_source` 机制（用户值胜出）；
   `display_name` 的「用户值优先」由规则明确（不再依赖隐式条件）。
3. **单一写入口**：所有用户写入必须经一个新的 **薄写服务**（对称于 `LibraryAdminService`，
   暂名 `CurationService`，具体命名/位置由实现阶段定），**不**经 Query Layer、**不**在 UI 里写 SQL。
4. **护栏测试**：新增/扩展静态或单元测试，断言「Scanner / ResourceStore 不得写用户数据列」
   （即机器写入语句的列集合受白名单约束）。

### 3.3 是否需要新的数据层或 schema 结构 → **首期不需要**

理由：

- 用户标量字段（`notes` / `display_name` / `source` / `series` / `description`）**列已存在**；
- 标签体系所需 `tags` / `resource_tags` **表已存在**；
- 引入独立「用户 overlay 表」是为**尚未出现的冲突**预建结构，违反「无证据不建模型」。

### 3.4 唯一确需新结构的场景 → **推迟，不首期做**

| 场景 | 为什么需要新结构 | 结论 |
| :--- | :--- | :--- |
| 持久化 review 状态（confirmed / dismissed） | `needs_review` 每轮重扫被重算，无法承载人工结论 | **推迟**（若纳入，属独立 schema 决策，候选 v3） |
| 持久化重复组确认 / canonical | 可用既有预留表 `duplicate_groups` / `duplicate_members` | **推迟**（首期不启用预留表） |
| 文件移动后重新关联用户数据（relocation） | 需要跨资源的匹配/重链接语义 | **推迟**（见 §6） |

### 3.5 决策 D1

```text
D1（冻结）：用户数据与机器事实分离 = 【字段所有权契约 + 优先级规则 + 单一写入口 + 护栏测试】。
           Phase 3 首期【不新增数据层、不新增 schema】。
           持久 review 状态 / 重复确认持久化 / relocation 均推迟到独立的 schema 决策。
           严禁：机器写入者触碰用户数据列；UI 直接写 SQL；用户写入绕过写服务。
```

---

## 4. 问题 2 — 收藏 / 标签 / Collection 采用什么模型

### 4.1 Tag 与 Collection 的对比

| 维度 | **Tag（标签）** | **Collection（集合）** |
| :--- | :--- | :--- |
| 语义 | 横切标记（可叠加、跨类） | 命名分组 / 专辑（策展集合） |
| 基数 | 资源 ↔ 标签 N:M | 资源 ↔ 集合 N:M |
| 重叠 | 天然允许多标签并存 | 允许多集合，但语义上倾向「归入」 |
| 排序 | 无内在顺序（表已带 `category` 可分组） | `sort_order` 有意义（专辑内排序） |
| 表结构 | `tags` + `resource_tags(origin user/auto)` **已存在** | `collections` + `resource_collections` **已存在** |
| 写入成本 | 低（一个实体 + 一个关联） | 中（实体 + 关联 + 排序/策展 UX） |
| 覆盖「收藏」 | ✅ 可用一个保留标签表达 | ✅ 也可用一个保留集合表达 |
| 风险 | 双轨（若同时做 Collection） | 双轨 + 更多 UX 设计，无证据 |

### 4.2 Phase 3 首期选择 → **只做 Tag**

```text
D2（冻结）：Phase 3 首期【只实现 Tag 单一机制】。
           Favorite（收藏）= 一个【保留系统标签】（稳定 name_key），不是新表。
           Collection = 【暂缓】：表保留预留，首期不实现写 API / 查询 / GUI。
           明确【不】同时做两套机制。
```

选择 Tag 的理由：

1. **一个机制覆盖首期全部诉求**：标签 + 收藏都可由 Tag 表达，无需第二套模型；
2. **成本最低、风险最小**：表已存在，无需 schema 变更；
3. **避免双轨**：Tag 与 Collection 语义重叠，同时做会产生「同一条信息存哪」的长期歧义；
4. **Collection 的独特价值（专辑内排序 / 策展 UX）目前缺乏需求证据**，属「可为完整性而加」；
5. 与既有不变式相容：标签只写数据库，不动文件。

### 4.3 Collection 的处置（明确，不模糊）

- **不是删除**：四张表继续保留（与现状一致，零写入）；
- **不是首期范围**：Phase 3 首期不做 Collection 的写入 / 查询 / GUI；
- **不是永久禁止**：如果在后续阶段取得真实策展/排序需求，可作为**独立子阶段**重新论证
  （届时必须先给出「为什么 Tag 不够」的证据）。

### 4.4 Favorite 的表示（明确）

- 用一个**保留系统标签**（稳定 `name_key`，例如按约定命名的收藏标签）表示；
- 用户在首期只能「加/去收藏」，其底层就是 tag assign/unassign；
- 禁止为 Favorite 新建 `favorites` 表（无证据，且会造成第三套机制）。

---

## 5. 问题 3 — 分类（Category）与位置（Library / Path）彻底分离

### 5.1 职责划分

| 概念 | 职责 | 载体 | 是否机器事实 |
| :--- | :--- | :--- | :--- |
| **Category（用户分类）** | 「我认为它是什么 / 属于哪里」——标签、收藏、（未来）集合、用户类型修正 | `tags` / `resource_tags` / `type_source` + `resource_type` | **否，用户数据** |
| **Library** | 扫描根目录 / 扫描范围 | `libraries` + `resources.library_id` | 是，机器事实 |
| **Path** | 文件物理位置 + 资源身份（`file_path_key`） | `resources.file_path` / `file_path_key` / `relative_path` | 是，机器事实 |

### 5.2 用户修改分类后的行为

```text
D3-a（冻结）：用户修改分类 → 只写数据库行（标签 / 用户类型 / 展示名 / 备注）；
             绝不 move / rename / delete / 改写文件，也不改目录结构。
```

### 5.3 文件移动后的行为

```text
D3-b（冻结）：文件移动 / 改名 → 归一化路径变化 → 生成【新资源行】；
             旧行【保留】并标记 scan_status='missing'（连同其用户数据一起保留，不删除）。
             用户分类【不会自动迁移】到新行（relocation 见 §6，首期不实现）。
```

### 5.4 禁止通过目录结构隐式推导用户分类

```text
D3-c（冻结）：Category 与 Path 之间【不得】存在隐式推导：
  - 不得用目录名 / 文件名 / 路径推断「用户分类 / 标签 / 收藏」；
  - 不得因为文件在某个文件夹里就自动打标签或自动归入某个分类；
  - 解析层只用路径做【身份 / 候选后缀 / relative_path 展示与检索】，
    既有 Parser「不从文件名/目录名判类型」的纪律保持不变。
  说明：搜索时命中 relative_path 是【检索】行为，不是【分类推导】，两者必须区分。
```

### 5.5 决策 D3

```text
D3（冻结）：Category = 用户数据（DB 概念，虚拟组织）；
           Library / Path = 机器事实（位置与身份）；
           两者彻底分离；修改分类不动文件；移动文件不迁移分类（首期）；
           禁止任何「目录结构 → 用户分类」的隐式推导。
```

---

## 6. 问题 4 — 路径身份 + SHA-256 内容身份是否足够

### 6.1 SHA-256 能证明 / 不能证明

| | 内容 |
| :--- | :--- |
| **能证明** | 两份文件**字节完全相同**（byte-identical）；这是唯一被承认的等价判据 |
| **不能证明** | 同角色、同 MOD、同逻辑资源、同版本、同变体、视觉相似、语义相似 |
| **失效边界** | 只由 `size` / `mtime` 变化或 `mode='full'` 触发重算；同 size 同 mtime 替换是已知盲区 |
| **覆盖范围** | 整个文件字节（含 PNG 尾部容器与 `About.dataID`）⇒ 图像相同但 dataID 不同 ⇒ hash 不同 |

### 6.2 文件移动 / 改名的现状

- 路径身份随路径变化 ⇒ **移动 = 新资源行 + 旧行 missing**；
- 旧行**不删除**，其用户数据（标签等，一旦实现）**保留在旧行上**；
  ⇒ 移动造成的**不是数据丢失**，而是「用户数据与新行失去关联」的**重新关联（re-location）问题**；
- 内容身份（sha256）在原理上**可能**用于识别「新行 = 旧 missing 行的同一份内容」，
  但存在两个硬约束：**(a) 字节完全相同的副本会让匹配歧义**（样本已有 Kugisaki ×2）；
  **(b) 内容同时变化 + 移动 ⇒ 无法识别**。

### 6.3 是否在 Phase 3 解决 relocation → **首期不解决，但明确记录边界**

```text
D4（冻结）：
  - Phase 3 首期【不实现 relocation / 移动检测】；保持「路径身份 + 内容身份」现状。
  - 明确边界（不是模糊状态）：移动后 = 新行 + 旧行 missing；用户数据保留在旧行；
    Phase 3 首期【不提供】自动或手动的重新关联入口。
  - sha256 继续只作内容身份，不承担资源连续性。
  - 未来触发条件（满足才重新立项）：出现真实用户「移动文件后希望保留标签/收藏」的需求；
    届时须先解决「字节相同副本导致匹配歧义」与「内容同时变化不可识别」两个约束。
```

### 6.4 结论

当前「路径身份 + SHA-256 内容身份」模型**对 Phase 3 首期足够**：

- 组织数据锚定稳定的 `resources.id`，不依赖 relocation；
- 移动场景被**明确记录为边界**（有确定行为 + 未来触发条件），**不留模糊状态**；
- 不引入新的身份键、不做移动检测、不改身份模型。

---

## 7. 问题 5 — Resource Relationship 应做到什么程度

### 7.1 关系分级（判据 + 现状）

| 级别 | 含义 | 当前关系 |
| :--- | :--- | :--- |
| **A. 有可靠数据来源（DB 事实）** | 由 Parser 从真实数据结构读出并入库 | resource→MOD（逐槽位 usage / 汇总）、resource→plugin、resource→author、MOD→自己的文件、resource/MOD→library |
| **B. 可靠派生（可由事实重算）** | 由既有列只读推导 | 缺失 MOD、孤立 MOD、property 语义类别、review reason、byte-duplicate 组（`GROUP BY sha256`） |
| **C. 仅候选（判据弱，有反例）** | 只能提示，不能当事实 | 同大小、同名（+作者）、同 marker+同名；relocation（字节匹配，含歧义） |
| **D. 必须用户人工确认** | 任何「相似 / 同一 / 相关」的断言 | C 类候选的确认结果；用户手工建立的关联 |
| **E. 无数据来源（禁止凭空建立）** | 语义上可能，但数据里没有 | MOD→MOD 依赖、版本约束、same-character、visual/semantic similarity |

### 7.2 特别重申：`uses` ≠ `requires`

- manifest.xml 无依赖字段；KKManager `ModInfoBase` 亦无；`resource_mods.relation` 恒为 `uses`；
  「缺失 MOD」= 被引用但未安装，**不表示依赖不满足**。
- 因此 **MOD→MOD 依赖图属 E 类，禁止建立**。

### 7.3 Phase 3 首期实现哪些关系 → **不新增任何自动关系**

```text
D5（冻结）：
  - Phase 3 首期【不新增任何自动关系】：不做依赖图、不做相似图、不做 MOD→MOD、
    不新增 resource↔resource 关系类型。
  - 既有 A 类关系（usage 等）与 B 类派生（missing/orphan/review/byte-duplicate）
    【保持现状、保持只读】，语义一字不改。
  - 「关系表达」在 Phase 3 首期通过【Tag（组织）】实现，而不是新建关系表。
  - C 类候选 / D 类人工确认（含 Byte-Duplicate 的 confirm/dismiss/canonical）
    【推迟】，不进首期；其框架（A–E 分级）保留作为未来扩展的判据。
  - 严禁：为「完整」而凭空建立任何 E 类关系。
```

### 7.4 为什么首期不新增关系

1. 唯一可靠关系（usage）**已存在**，无需重做；
2. 其余关系（依赖 / 相似 / 变体）**没有数据来源**，或**判据弱且有反例**；
3. 引入「候选 + 确认」需要确认语义的持久化载体（review state / duplicate 表），
   属独立 schema 决策，不应与首期组织功能捆绑；
4. 组织能力（Tag）本身就能表达用户想要的「相关」，无需发明新关系类型。

---

## 8. 核心原则核查：「管理资源的信息」 vs 「直接操作资源文件」

| 原则 | 现状证据 | Phase 3 决策 | 是否冲突 |
| :--- | :--- | :--- | :--- |
| 不移动文件 | `core/`+`ui/` 无 `shutil.move` / `os.rename` | 保持；组织只写 DB | ✅ 无冲突 |
| 不改名文件 | 无任何改名代码 | 保持；展示名只写 `display_name` 列 | ✅ 无冲突 |
| 不删除文件 | 无 `os.remove`（仅缩略图缓存清理） | 保持；标签删除只删 DB 行 | ✅ 无冲突 |
| 不下载 / 不联网 | `core/` 无网络库；`requirements` 无网络依赖 | 保持 | ✅ 无冲突 |
| 不引入 AI / 语义判断 | 无 AI / 无 embedding / 无 phash | 保持 | ✅ 无冲突 |
| 不把推测当事实 | 类型不明落 `unknown` + `needs_review` | 组织=用户事实；候选=候选（不进事实视图） | ✅ 无冲突 |
| 位置与分类分离 | schema 注释 + 三条硬约束 | D3 强化并加护栏 | ✅ 无冲突 |

**结论**：本报告的决策**与该核心原则完全一致**，且通过 D1（所有权契约）与 D3（分离禁令）
把它从「文档原则」升级为「可测试的契约」。

---

## 9. 与 Phase 2 既有能力的兼容性检查

| Phase 2 产物 | 是否被本决策触碰 | 结论 |
| :--- | :--- | :--- |
| **Schema v2**（16 表 / `SCHEMA_VERSION==2`） | 不新增、不修改 | ✅ 首期**零 schema 变更**；`_V1_SQL` / `_V2_SQL` 不回改 |
| **Content Identity（`resources.sha256`）** | 仍是机器事实；用户数据不写它 | ✅ 不冲突；重扫逻辑不变 |
| **C7 读取一致性** | 不受影响 | ✅ 不变 |
| **Byte Duplicate（`GROUP BY sha256` 派生）** | 保持只读派生；首期不持久化 | ✅ 不变；`duplicate_*` 继续零写入 |
| **Query Layer 只读护栏（`_execute_select`）** | 用户写入**不走** Query Layer | ✅ 写入必须新建写服务；读侧（tag 过滤）为 additive SELECT |
| **`ResourceSummary` / DTO 向后兼容** | 新增字段须 additive（带默认值、置末尾） | ✅ 沿用 Phase 2.3 惯例 |
| **`ui → core` 单向 / GUI 不写 SQL** | 管理类 GUI 必须消费写服务 | ✅ 沿用既有边界 |

> 兼容性附注：Query Layer **当前没有 tag 过滤**；首期需要为「按标签浏览」增加一个
> **只读筛选参数**（新增 `EXISTS (SELECT 1 FROM resource_tags ...)` 分支），
> 属**additive SELECT**，不改变既有筛选语义。

---

## 10. 用户数据 / 机器数据 边界（汇总契约）

```text
机器数据（Scanner/Parser 权威）
  → 重扫覆盖是正确行为
  → 载体：resources 的位置/大小/时间/哈希/解析字段 + 关系表 + mods

用户数据（用户权威）
  → Scanner/Parser 永不写入
  → 载体：tags / resource_tags（首期）+ resources.notes/display_name/source/series/description

共享字段（一个字段两种来源）
  → resource_type：type_source='user' 时用户值胜出
  → display_name：用户改写后重扫保留

写入路径
  → 全部用户写入经单一【薄写服务】；Query Layer 只读；UI 不写 SQL

不得混淆
  → 机器写入者不得触碰用户列；不得用目录结构推导用户分类；
    不得把候选/推测写入事实字段
```

---

## 11. Schema 是否需要变化（明确结论）

```text
结论：Phase 3 首期【不需要 schema 变化】，保持 SCHEMA_VERSION == 2、16 张业务表。
```

理由：

1. Tag 所需 `tags` / `resource_tags` **已存在**（含 `origin='user'`、`color`、`category`）；
2. 用户标量字段 `notes` / `display_name` / `source` / `series` / `description` **已存在**；
3. 用户类型修正所需 `type_source` **已存在**；
4. Favorite 用保留标签表达 ⇒ 不需新表。

**明确推迟的 schema 事项（不是首期，且必须单独评审）**：

| 事项 | 需要的 schema | 触发条件 |
| :--- | :--- | :--- |
| 持久 review 状态（confirmed/dismissed） | 新列或新表（候选 v3） | 首期之后，若确认流程被纳入范围 |
| 重复组持久化确认 / canonical | 可用既有预留表，但需定义生命周期 | 出现用户「标记保留项 / 忽略」真实需求 |
| relocation / 移动重关联 | 无新 schema 也可能可行（匹配逻辑），但需定义歧义规则 | 出现真实移动保留需求 |

若未来确需 schema 变化：**只追加新版本迁移**，不改 `_V1_SQL` / `_V2_SQL`，加列走
`MIGRATION_ADDED_COLUMNS`（幂等）。

---

## 12. Phase 3.0 Definition of Done

Phase 3.0 视为完成，当且仅当：

1. 本报告的 **D1–D5 五项决策**被确认并冻结（用户数据边界 / Tag 单一机制 / 分类与位置分离 /
   relocation 边界 / 关系范围）；
2. **In Scope / Out of Scope** 被确认冻结（§13 / §14）；
3. **Schema 结论**被确认：首期零 schema 变更；推迟项已登记（§11）；
4. **与 Phase 2 的兼容性**检查通过（§9），无冲突；
5. **风险与未决问题**已登记，并区分「已决定」与「需证据」（§15）；
6. 正式 Contract 文档已产出且经用户确认；
7. **在以上全部满足之前，不进入任何 Phase 3.x 实现。**

> 本报告已满足 1–5 的分析前提；是否算「冻结」，取决于用户对 D1–D5 与 §13/§14 的确认。

---

## 13. In Scope（Phase 3 首期，能力级）

> 只定义**能力范围**，不定义 3.1/3.2/3.3 编号与切分。

1. **Tag 体系（唯一组织机制）**：创建 / 列表 / 重命名 / 删除标签；给资源加 / 去标签；
   标签来源 `origin='user'`。
2. **Favorite**：以保留系统标签实现的收藏（加 / 去收藏）。
3. **用户标量修正（激活「可人工修正」）**：备注（`notes`）、展示名（`display_name`）、
   类型修正（`type_source='user'` + `resource_type`）。
4. **写服务层**：对称于 `LibraryAdminService` 的单一薄写服务；事务 / 幂等 / 冲突语义明确。
5. **字段所有权契约 + 护栏**：机器写入者不得写用户列（含测试）。
6. **按标签浏览**：Query / Browse 增加**只读**标签筛选（additive）。
7. **入口（CLI 与/或 GUI）**：至少一个可用入口；**入口先后顺序为未决项**（见 §15），
   GUI 必须消费写服务，不得写 SQL。

---

## 14. Out of Scope（Phase 3 首期，明确排除）

| # | 排除项 | 依据 |
| :-- | :--- | :--- |
| 1 | 移动 / 改名 / 删除 / 下载文件 | 核心原则；删除属 Phase 5 |
| 2 | 联网 / 在线元数据 / 云同步 / 多用户 | 本地优先、零网络 |
| 3 | AI / 语义判断 / 自动打标 / 自动整理 / 自动分类 | 硬约束 + 无证据 |
| 4 | filesystem watcher / 自动扫描 / 自动刷新 | Phase 1.5-D 明确定义为需证据驱动 |
| 5 | Collection（首期不做） | §4：避免双轨，需求证据不足 |
| 6 | 持久 review 状态 / 确认流程 | §3.4 / §11：需独立 schema 决策 |
| 7 | Byte-duplicate 的 confirm / dismiss / canonical 持久化 | §7：候选/确认层推迟 |
| 8 | relocation / 移动检测 / 资源连续性 | §6：明确记录为边界 |
| 9 | MOD→MOD 依赖图 / 版本约束 / 版本实体 | 无数据来源 |
| 10 | 新语义身份键（Family / Variant / logical resource） | 无数据源 |
| 11 | same-character / visual / semantic similarity（事实） | NOT DETECTABLE |
| 12 | 1:N File/Resource 拆分 / 通用 Entity-Relation 表 | 无样本 |
| 13 | 把推测关系当事实 | 核心原则 |
| 14 | 首期 schema v3 | §11：首期零 schema 变更 |
| 15 | 把早期 roadmap（Phase 3=标签+分类）当既有 Contract | 已知文档漂移 |

---

## 15. 风险与未决问题

### 15.1 已决定（不再是开放问题）

- 用户数据 / 机器事实现以「所有权契约」分离（D1）；
- 首期只做 Tag，Favorite=保留标签，Collection 暂缓（D2）；
- 分类与位置彻底分离，禁止目录推导（D3）；
- 首期不做 relocation，明确记录边界（D4）；
- 首期不新增自动关系（D5）；
- 首期零 schema 变更（§11）。

### 15.2 需要进一步证据（不强行决定）

| # | 未决问题 | 证据缺口 | 影响 |
| :-- | :--- | :--- | :--- |
| U1 | 真实组织需求是什么（用户到底想怎么分类） | 持久工作库 0 资源；标签/集合零使用 | 决定 Tag 的分类粒度 / 默认标签 |
| U2 | 入口先后：core→CLI 先，还是 core→GUI 先 | 无真实使用反馈 | 影响验收方式，不影响能力范围 |
| U3 | 组织范围是否全局 | 无多库真实样本（现状 `file_path_key` 全局唯一） | 本报告倾向全局（与身份一致），但需 Contract 确认 |
| U4 | 是否需要（何时需要）review 持久状态 | 样本 needs_review=0，无确认需求证据 | 决定后续是否引入 v3 |
| U5 | 移动场景真实发生率与容忍度 | 无真实用户移动样本 | 决定 relocation 何时触发 |

### 15.3 风险登记

| # | 风险 | 缓解 |
| :-- | :--- | :--- |
| R1 | 组织功能在「零真实需求证据」下开工 | 首期限定 Tag 单一机制；以 U1 为依据再扩展 |
| R2 | 文件移动 ⇒ 用户数据与新行脱钩 | 明确边界（D4）+ 旧行保留（不丢数据）；未来按触发条件处理 |
| R3 | 首次引入用户写入 ⇒ 变异语义风险 | 单一写服务 + 事务 + 幂等 + 护栏测试 |
| R4 | 机器写入者误写用户列 | D1 白名单护栏 + 测试 |
| R5 | 双轨（Tag/Collection）歧义 | D2 首期只做 Tag |
| R6 | Query Layer 被误用于写入 | 只读护栏已存在；写入另建服务 |
| R7 | 文档漂移误导 Contract | 本报告显式标注（§14-15） |

---

## 16. 决策摘要（一页速览）

```text
D1 用户数据/机器事实：字段所有权 + 优先级 + 单一写服务 + 护栏；首期不新增数据层/schema。
D2 组织模型：首期【只做 Tag】；Favorite=保留系统标签；Collection 暂缓（表保留）。
D3 分类 vs 位置：彻底分离；改分类只写 DB；移动不迁移分类；禁止目录结构推导分类。
D4 身份模型：路径身份 + sha256 内容身份足够；首期【不做 relocation】，明确记录边界。
D5 关系：首期【不新增自动关系】；既有 usage/派生保持只读不变；禁止凭空建关系。
Schema：首期【零变更】（SCHEMA_VERSION == 2，16 表）。
兼容：与 Schema v2 / Content Identity / Byte Duplicate / Query Layer 只读护栏无冲突。
边界：管理信息只写 DB；绝不移动/改名/删除/下载文件、不联网、不引入 AI/语义、不把推测当事实。
门禁：本报告 D1–D5 与 In/Out Scope 被确认（冻结）之前，不进入任何 Phase 3.x 实现。
```

---

## 附录 A — 本轮只读合规核对

| 禁止项 | 状态 |
| :--- | :--- |
| 修改代码 | ✅ 未做 |
| 修改 schema | ✅ 未做（`SCHEMA_VERSION == 2`） |
| 创建 migration | ✅ 未做 |
| 修改测试 | ✅ 未做 |
| 创建 commit | ✅ 未做 |
| 创建 tag | ✅ 未做 |
| 修改现有文档 | ✅ 未做（`PHASE3_0_ARCHITECTURE_SCOPE_REVIEW.md`、`PHASE3_0_SIMPLE_SUMMARY.md` 原样保留） |
| 唯一新增物 | 本文件 `docs/phase3/PHASE3_0_DECISION_REPORT.md` |
