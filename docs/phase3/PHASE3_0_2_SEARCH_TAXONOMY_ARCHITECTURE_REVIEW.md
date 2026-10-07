# Phase 3.0.2 — Search & Taxonomy Integration Design Review

> 阶段：**Phase 3.0.2 — Search & Taxonomy Integration Design（DESIGN ONLY / READ-ONLY）**
> 日期：2026-10-07
> 前置：Phase 3.0 = CLOSED / PASS（tag `phase-3.0-closed`，HEAD `c2fd527`）
> 权威契约：`docs/phase3/PHASE3_0_CONTRACT.md`（Phase 3.0 冻结版，保持权威）
> 路线图：P3.0.1（3.0 → 3.0.2 → 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6，保持不变）
> 本阶段产出：**仅本文件**

> ⚠️ **本阶段不实现任何东西。**
> 未修改代码 / schema / migration / 依赖 / CLI / GUI / Parser / Scanner / Query implementation；
> 未创建 commit / tag；未创建索引；未实现 Tag / Favorite / User Write Service / Query Parser。
> 发现 Gap 的处理方式是 **记录 → 提 Recommendation**，而不是顺手修改。

---

## 0. 背景与定位

### 0.1 本阶段要回答的唯一问题

> **KKS Resource Manager 是否可以在现有 Phase 1 / Phase 2 架构上，逐步形成一个类似
> Everything 的「即时搜索体验」，但搜索对象从 File 升级为 Resource？**

### 0.2 本阶段新增的参考对象（明确识别）

```text
Everything = Voidtools Everything Search（Windows 文件名/路径即时搜索软件）
官网      : https://www.voidtools.com/
文档      : https://www.voidtools.com/support/everything/
```

它在本项目中的定位**只有一个**：

```text
Everything  →  Search Architecture Reference
```

**不是** implementation dependency，**不是** 要复刻的 clone，**不是** 依赖项。

### 0.3 本阶段不发生的事

- 不重新规划整个 Phase 3；不推翻 P3.0.1；不修改 P3.0 Contract。
- 不引入 AI / 语义搜索 / 感知哈希 / 内容搜索。
- 不引入 Elasticsearch / Lucene / 倒排索引 / 独立搜索引擎。
- 不实现任何 Search Service / Query Parser / Tag / Favorite / User Write。

### 0.4 证据来源

| 类别 | 来源 |
| :--- | :--- |
| Everything 官方 | `voidtools.com/support/everything/`（Features）、`/searching/`（搜索用法）、`/indexes/`（索引机制） |
| 本项目契约 | `docs/phase3/PHASE3_0_CONTRACT.md`（冻结版） |
| 真实 schema | `core/database/schema.py`（SCHEMA_VERSION == 2，16 表） |
| 查询层 | `core/query/{queries,dto,browse,search,property_map}.py` |
| 样本证据 | `docs/phase1/SAMPLE_ANALYSIS.md`（22 卡 + 13 zipmod 实测） |
| 外部研究 | `docs/phase2/PHASE2_0_B_RESEARCH.md` |

---

## 1. Executive Summary

**结论：Yes。** 本项目可以在现有架构上逐步形成 Everything 式的「即时搜索体验」，
且搜索对象是 **Resource** 而非文件路径；不需要任何外部搜索引擎。

理由（一句话版）：

```text
Existing machine facts + Content Identity + Resource Taxonomy
             + User-owned organization + SQLite / indexed Query Layer
        ↓
   Resource Search Engine（第一阶段用 SQLite 即可）
```

关键发现：

1. **Search backend 已经存在**：Query Layer（`core/query/queries.py` 的 6 个只读类）
   是唯一持有 SQL 的层；其中 `ResourceQuery` 已支持 12 类筛选 + 文本检索 + 排序 + 分页；
   SQLite 索引覆盖主要过滤维度。
2. **文本检索基础设施已经存在**：`resources_fts`（FTS5 trigram）已启用，用于
   `name` / `display_name` 的 ≥3 字子串（含中日文），并有 LIKE 回退。
   ⇒ **不需要** 新引入 FTS；现有 FTS 是否足够是第一阶段的答案。
3. **Taxonomy 的现成落点已经存在**：`resource_type`（10 值，含
   `character_card/outfit_card/scene_card/mod/skin/eyes/hair/accessory/other/unknown`）
   + `type_source`（auto/user）。
4. **但有一个必须点破的边界**：Phase 1 样本分析已证明
   `skin / eyes / hair / accessory` 在真实数据里是**卡片→MOD 的槽位语义**
   （`resource_mod_usages.property`），**不是文件类型**；把它们当作 Resource Type
   会自动产生错误分类 ⇒ taxonomy 必须把「**文件是什么**」与「**MOD 被用在哪**」分开。
5. **最大的 Contract 风险是「查询语法」**：`field:value` + `AND / OR / NOT` 这类
   **结构化文本查询语法**目前**不在** Phase 3.0 冻结的 In Scope 内；
   要采纳它必须先走 Contract 变更控制，**不得**在实现阶段偷偷加。
6. **Search / User Write 分离可以完整保持**：搜索只经只读 Query Layer；
   用户修改只经 User Write Service；GUI 不直连 SQLite。

```text
Phase 3.0.2 = 设计评审完成，未进入实现。
```

---

## 2. Current Architecture

### 2.1 当前 Resource Model（Q1）

```text
文件（.png / .zipmod / .zip）
   ↓ 扫描 + 解析（只读）
Resource = resources 表一行（一个文件 = 一个资源，1:1）
   ├─ Machine facts：path / size / mtime / extension / sha256 / card_marker /
   │                 metadata_json / parse_status / scan_status / name(解析名)
   ├─ Relations：resource_mods / resource_mod_usages / resource_plugins / resource_authors
   └─ User data（部分尚未有写入者）：display_name / notes / type override /
                                      tags（未启用）/ collections（未启用）
```

- **File ≡ Resource（1:1）**，`resources.file_path_key` 全局唯一（Phase 2 冻结）。
- Resource 身份 = 路径；内容身份 = `sha256`；MOD 逻辑身份 = `mods.guid`。
- **File ≠ Resource** 是 P3.0.2 的搜索定位前提：搜索应返回 **Resource**，而非路径字符串。

### 2.2 当前 Query Layer（Q2）

`core/query/queries.py` 的 6 个只读类：

| 类 | 职责 |
| :--- | :--- |
| `LibraryQuery` | Library 列表 / 计数 / 单库 |
| `ResourceQuery` | 资源 count / list / summary / resolve / get / usages / mods / plugins / authors / metadata / review_reasons / duplicates |
| `ModQuery` | 已安装 / 缺失 / 孤立 / 详情 / 反查资源 / usage |
| `AuthorQuery` | 作者列表 / 查找 / 反查资源 |
| `PluginQuery` | 插件列表 / 反查资源 |
| `UsageQuery` | 全库 usage / 按资源 / 按 MOD / 类别统计 / unknown property |

护栏：`_execute_select()` **只放行 `SELECT` / `WITH`**，否则抛 `ReadOnlyViolation`。
编排层：`BrowseService`（无自有 SQL，复用上面 6 个类）。

### 2.3 当前数据库如何表达 Resource（Q3）

`resources` 表（关键列）：`id`、`resource_type`、`type_source`、`library_id`、
`name`、`display_name`、`file_path`、`file_path_key`、`relative_path`、`file_size`、
`modified_time`、`extension`、`sha256`、`quick_hash`(deprecated)、`content_key`(deprecated)、
`metadata_json`、`scan_status`、`parse_status`、`parse_error`、`needs_review`、`card_marker`。

关系表：`resource_mods`、`resource_mod_usages`、`resource_plugins`、`resource_authors`、
`mods`、`authors`、`libraries`、`tags`/`resource_tags`（未启用）、`collections`/`resource_collections`（未启用）。

### 2.4 当前可搜索字段（Q4）

**文本检索（`query`）覆盖**：

| 面 | 走哪条路 |
| :--- | :--- |
| `resources.name` / `display_name` | ≥3 字 → FTS5 trigram；1–2 字或 FTS 不可用 → LIKE |
| `resources.relative_path` | **恒走 LIKE**（含文件名/目录） |
| `authors.name` / `resource_authors.raw_name` | EXISTS + LIKE |

**结构化筛选维度（`_resource_where`）**：
`resource_type`、`game`（→ `card_marker`）、`card_marker`、`library_id`、`scan_status`、
`needs_review`、`has_mods`、`has_missing_mods`、`mod_guid`、`plugin_guid`、`author_id`、
`property_category`。

**排序白名单**：`id`、`name`、`display_name`、`file_size`、`modified_time`、`created_at`、`updated_at`。

**当前缺失的搜索入口**：`tag` / `favorite`、`sha256`（内容身份）、`duplicate`、
`extension`、`file_size` 区间、`modified_time` 区间、`notes`（FTS 有列但未被 MATCH 使用）。

### 2.5 当前数据库索引（Q5）

| 表 | 索引 |
| :--- | :--- |
| `resources` | UNIQUE on `file_path_key`；`idx_resources_type`、`idx_resources_library`、`idx_resources_author_id`、`idx_resources_sha256`、`idx_resources_quick_hash`(unused)、`idx_resources_content_key`(unused)、`idx_resources_needs_review`(partial WHERE=1)、`idx_resources_relative`、`idx_resources_card_marker` |
| `resource_tags` | PK(`resource_id`,`tag_id`) + `idx_resource_tags_tag`(tag_id) |
| `resource_mods` | PK(`resource_id`,`mod_guid`) + `idx_resource_mods_guid` / `_resource` |
| `resource_mod_usages` | PK(`resource_id`,`mod_guid`,`property`) + `_guid` / `_resource` / `_property` |
| `resource_plugins` | PK(`resource_id`,`plugin_guid`) + `idx_resource_plugins_guid` |
| `resource_authors` | PK(`resource_id`,`author_id`) + `idx_resource_authors_author` |
| `mods` | UNIQUE `guid`、`idx_mods_guid` / `_file_path_key` / `_resource` |
| 其它 | `idx_duplicate_*`、`idx_scan_records_library`、`idx_resource_collections_col` |

**未被索引（潜在排序/过滤成本）**：`extension`、`file_size`、`modified_time`、`scan_status`、`notes`、`source`、`series`。

---

## 3. Current Query Layer（深入）

### 3.1 文本检索路由（已实现）

```text
空/空白      → 无文本条件
1–2 字       → LIKE '%q%'（已转义）
≥3 字 + FTS  → resources_fts MATCH，列限定 {display_name, name}
FTS 不可用   → 全部长度回退 LIKE
```

`resources_fts` = FTS5 `trigram`，`content='resources'`，三支同步触发器；
FTS 是**尽力启用**，失败时 `app_meta.fts_enabled=0` 并全程 LIKE 回退，不阻塞启动。

### 3.2 组合与编排

- `BrowserScope.filters()` 是「作用域 → ResourceQuery 参数」的**唯一转换点**；
  `count` 与 `list` 共用同一份 filters（不可能漂移）。
- `BrowseService` 无自有 SQL；`ui/` 不 import `sqlite3` / `*Query` 类（有静态测试守护）。

### 3.3 当前 Query Layer 的结构性观察（Gap 线索）

| 观察 | 说明 |
| :--- | :--- |
| 只有「参数集合」，没有「查询模型对象」 | 今天 `BrowserScope` 承担了统一作用域，但**没有**文本语法 → 结构化条件的编译层 |
| `_RESOURCE_SUMMARY_COLUMNS` 含 4 个相关子查询（mod/usage/plugin/author count） | 每行 4 次子查询；大结果集下的成本随行数增长 |
| `BrowseService.page()` 逐行取作者（N+1） | 作者显示名逐行查询 |
| `relative_path` / 作者检索恒走 LIKE | 前缀通配 → 无法用普通索引，全扫 |
| `resource_type` 只反映机器/用户类型 | 与 usage 槽位语义（property_category）是两条轴，不能混 |

---

## 4. Current Resource Taxonomy

### 4.1 现有 `resource_type` 取值（schema CHECK，10 值）

```text
character_card, outfit_card, scene_card, mod, skin, eyes, hair, accessory, other, unknown
```

`AUTO_DETECTABLE_TYPES`（core/models）= `character_card / outfit_card / scene_card / mod / unknown`。

### 4.2 实际能被机器可靠产出的类型（当前代码事实）

| 类型 | 当前是否产出 | 依据 |
| :--- | :--- | :--- |
| `character_card` | ✅ | `parsers/card.py` marker 命中（`KoiKatuCharaSun` / `KoiKatuChara`） |
| `mod` | ✅ | zipmod 有 `manifest.xml` + guid（store 硬编码 `'mod'`） |
| `unknown` | ✅ | 默认值（marker 不识别 / 解析失败保留） |
| `outfit_card` / `scene_card` | ❌ 未产出 | 枚举允许，但**没有对应 Parser** |
| `skin` / `eyes` / `hair` / `accessory` | ❌ 未产出，**且被明确禁止**作为 PNG 文件类型自动写入 | Phase 1.2-A 硬约定（v2 schema 注释） |
| `other` | ❌ 未产出 | 枚举允许，无生产者 |

### 4.3 必须点破的 Taxonomy 边界（关键）

真实样本（`SAMPLE_ANALYSIS.md` §D）证明：

```text
「眼睛 / 皮肤 / 衣服 / 配饰 / 头发」在真实数据里是
【卡片与 MOD 的关系属性】（resource_mod_usages.property），
不是某个 PNG 文件的类型。
```

因此存在**三条互不相同的语义轴**，必须分开：

| 轴 | 回答的问题 | 载体 | 类别 |
| :--- | :--- | :--- | :--- |
| **Resource Type（Taxonomy）** | 「这个资源**是什么**」 | `resources.resource_type` + `type_source` | 机器 + 用户覆盖 |
| **Usage Category** | 「某张卡在**哪个槽位**用了这个 MOD」 | `resource_mod_usages.property` → `property_map`（face/body/clothes/accessory/hair/makeup/unknown） | 机器（派生） |
| **Tag** | 「用户希望**如何组织**这个资源」 | `tags` / `resource_tags`（P3.0 首期启用） | 用户 |

**结论**：用户的候选清单（Character / Clothing / Skin / Eyes / Hair / Accessory / Other / Unknown）
**不能整份当作 `resource_type` 使用**；其中 `skin/eyes/hair/accessory`（以及 `clothing`）
更接近 **Usage Category**，而非 Resource Type。把它们当文件类型会重演 Phase 1 已避免的错误。

---

## 5. Machine / User Ownership Analysis

### 5.1 User-owned data 当前如何表达（Q6）

| 用户数据 | 载体 | 现状 |
| :--- | :--- | :--- |
| 展示名 | `resources.display_name` | 列存在；**Contract §3.1（解法 B）已冻结为纯用户数据**，但**尚未实现**（Scanner 仍写它） |
| 备注 | `resources.notes` | 列存在，零写入 |
| 类型覆盖 | `resources.type_source` + `resource_type` | 列存在；store 已尊重 `type_source='user'`；无写入者 |
| 标签 | `tags` / `resource_tags` | 表存在，零写入 |
| 收藏 | （保留系统 Tag，P3.0 决定） | 未实现 |
| 来源 / 系列 / 描述 / 作者备注 | `source` / `series` / `description` / `authors.notes` | 列存在，未启用 |

### 5.2 User Write Foundation 应该放在哪里（Q7）

```text
core/app/<user-write-service>   （对称于既有 LibraryAdminService）
   ↓
写 tags / resource_tags / display_name / notes / type override
```

- 单一写服务是**唯一**用户数据写入口（Contract §9）；
- 不经 Query Layer、不在 UI 写 SQL；
- 搜索侧永远只读（§10）。

### 5.3 Scanner / Parser 是否存在覆盖 User-owned data 的风险（Q8）

| 风险 | 现状 | 结论 |
| :--- | :--- | :--- |
| `resource_type` 被重扫覆盖 | store 已判断 `type_source=='user'` 则保留 | ✅ 已有保护（但需写服务真正写入 `'user'`） |
| `display_name` 被重扫覆盖 | **当前 Scanner 写 display_name**（旧启发式） | ⚠️ **Contract §3.1 已冻结修正方向（Scanner 停止写），但尚未实现** |
| `notes` / `source` / `series` / `description` | Scanner 从不写 | ✅ 无风险 |
| `tags` / `resource_tags` | Scanner 从不写 | ✅ 无风险 |
| `needs_review` | Scanner 每轮重算 | ⚠️ 机器布尔；不能承载用户确认（已登记） |

> **重要**：本节只**记录**，不实现。display_name 的 Scanner 行为修正是 Phase 3.x 的事。

---

## 6. Everything Search Architecture Reference

### 6.1 官方资料记录（只读核对）

| 来源 | 关键事实 |
| :--- | :--- |
| `/support/everything/`（Features） | 「a file search engine for Windows」；Quick file indexing；**Instant filename searching**；Fast startup；Small database on disk；**Real-time updating**；Runs entirely offline；No telemetry |
| `/support/everything/searching/` | 输入局部文件名即**即时**出结果；wildcard（`*.pdf`）；`\` 表示完整路径；**空格 = AND**；`|` = OR；`!` = NOT；盘符 `d:`；Advanced Search；Filters / Macros / Regex / Content search |
| `/support/everything/indexes/` | 默认索引本地固定 **NTFS** 卷；数据库在 `%LOCALAPPDATA%\Everything\Everything.db`，运行时驻内存、退出时落盘；**始终索引 name + path**，size/date/attributes 为可选；**实时维护**；已索引信息即时可搜，未索引信息**按需收集（可能很慢）**；另有 Fast sort 索引 |

### 6.2 借鉴要点（映射到本项目）

| Everything 思想 | 本项目映射 |
| :--- | :--- |
| Index-first | 数据已入库 ⇒ 搜索**只查数据库**，绝不重新遍历文件系统 / 重新解析 |
| Instant search | GUI 输入 → Query Model → Query Layer → 快速返回（已有 browse/分页基础） |
| Structured query | `field:value` 概念 + AND/OR/NOT 概念（**此为用户可见新语法，见 §13 Contract Gap**） |
| Field-based search | `type:` / `library:` / `author:` / `hash:` / `tag:` / `favorite:` … 映射到已索引列 |
| Search cost awareness | 已索引列 = 低成本；EXISTS 组合 = 中成本；LIKE 全扫 / 需读文件 = 高成本 |
| 「未索引信息按需收集」 | 未来若需要读文件才能得到的条件，必须显式标为高成本（Phase 3 不做） |

### 6.3 Everything Reference Boundary（明确）

```text
Adopt:
- index-first
- fast indexed querying
- structured query
- field-based search
- AND / OR / NOT concepts
- search cost awareness

Do not adopt automatically:
- Everything internal implementation
- Everything database format
- Everything Windows indexing implementation
- full Everything syntax compatibility
- external search engine dependency
```

补充边界（本项目专属）：

- **不采纳**：NTFS MFT / USN journal / 卷级实时文件索引（本项目不监听文件系统）；
- **不采纳**：Everything 的 `.db` 格式与内存索引结构；
- **不采纳**：内容搜索（Content Searching，索引文件内容）——本项目不读文件内容入库；
- **不采纳**：完整 Everything 语法兼容（我们只设计适合本项目的子集）；
- **不采纳**：任何外部搜索引擎依赖（Elasticsearch / Lucene 等）。

---

## 7. KKS Taxonomy Reference

### 7.1 参考来源与边界

外部 KKS 资源分类项目 / 生态资料**只作 taxonomy reference**，**不是**本项目 Contract；
**不得复制其 schema**。本项目 taxonomy 必须自建，且回答的是
「**这个 Resource 是什么**」，与 Tag（「用户想怎么组织」）严格独立。

### 7.2 候选 taxonomy 与本项目现状的对照

| 候选类别 | 现有落点 | 能否机器判定 | 建议 |
| :--- | :--- | :--- | :--- |
| **Character** | `resource_type='character_card'` | ✅ 可（marker） | 采用 |
| **Clothing** | `outfit_card`（服装卡）**或** `mod`（服装 MOD） | ⚠️ 概念混杂 | 拆分为「服装**卡**资源类型」与「MOD + usage 槽位」，**不要**当单一文件类型 |
| **Skin / Eyes / Hair / Accessory** | 现枚举有同名值，但**被禁止**作为 PNG 文件类型自动写入 | ❌ 不可（且不应自动判定） | 归入 **Usage Category**（property_map 已覆盖 face/body/clothes/accessory/hair/makeup），或由用户 override |
| **Other** | `other` | — | 保留占位 |
| **Unknown** | `unknown` | ✅ 默认 | 保留（配 `needs_review`） |
| （现有）`scene_card` | `scene_card` | ❌ 未实现 | 保留占位 |
| （现有）`mod` | `mod` | ✅ 可（manifest+guid） | 采用 |

### 7.3 Taxonomy 边界结论

```text
Resource Taxonomy  ≠  Usage Category  ≠  Tag
    (是什么)          (用在哪)          (用户怎么组织)
```

- 现有 `resource_type` 枚举**足以承载**「资源是什么」这一轴（无需 schema 变更）；
- `skin/eyes/hair/accessory` 保留枚举占位，但**不得**由路径/文件名自动推断；
- 「Clothing」必须拆成「服装卡资源」与「MOD 使用槽位」两件事；
- Tag 与 Type **双向都不自动转换**（不因 `tag:character` 自动设 type；也不因 `type=character` 自动建 tag）。

---

## 8. Search Architecture Gap Analysis

### 8.1 目标搜索面 vs 现状（Q13 / Q14 / Q15 / Q16）

| 目标搜索入口 | 现状 | 可完全由 SQLite 完成？ | 成本 |
| :--- | :--- | :--- | :--- |
| Name | ✅ 已有（FTS/LIKE） | ✅ | 低–中（FTS 低；LIKE 中） |
| Path | ✅ 已有（relative_path LIKE） | ✅ | 中（前缀通配全扫） |
| Extension | ❌ 无过滤入口（列存在，未索引） | ✅ | 中（无索引） |
| Type | ✅ 已有（`resource_type`，已索引） | ✅ | 低 |
| Library | ✅ 已有（`library_id`，已索引） | ✅ | 低 |
| SHA256 / Content Identity | ❌ 无过滤入口（`sha256` 已索引） | ✅ | 低 |
| Duplicate status | ⚠️ 有派生查询（`duplicates()`），无「按重复过滤」入口 | ✅ | 低–中（`GROUP BY sha256`） |
| Tag | ❌（首期 In Scope，未实现） | ✅ | 低（`resource_tags` 有索引） |
| Favorite | ❌（= 保留系统 Tag） | ✅ | 低 |
| Display Name | ✅ 已在文本面（FTS/LIKE） | ✅ | 低–中 |
| User classification（type override） | ⚠️ 数据列已有，未暴露「effective type」 | ✅ | 低 |

**结论**：目标搜索面的**每一个入口都能由 SQLite + 现有 schema 完成**；
不存在必须外包给搜索引擎的项。

### 8.2 需要「额外计算」的项

| 项 | 是否 Phase 3 | 说明 |
| :--- | :--- | :--- |
| 组合条件、布尔逻辑 | 部分（结构化）；**文本语法待批准** | 见 §13 Contract Gap |
| duplicate 过滤 | 派生（`GROUP BY sha256`），无需读文件 | 低成本 |
| 需读文件的搜索（重新解析、重新哈希） | ❌ 不属 Phase 3 | 违反 index-first |
| 图像相似 / 语义相似 | ❌ 明确不做 | 高成本且无数据源 |

### 8.3 是否真的需要 FTS（Q17）

```text
不需要「新引入」FTS —— FTS 已经存在并在使用。
```

- `resources_fts`（FTS5 trigram，`content='resources'`）已建，三支触发器同步；
- 用于 `name` / `display_name` 的 ≥3 字子串（trigram 支持中日文）；
- 1–2 字与 FTS 不可用时自动 LIKE 回退；
- **注意**：FTS 索引了 `notes` / `series` / `description` / `author` 列，但当前
  MATCH 只限定 `{display_name, name}`；作者走 `resource_authors` LIKE。
  ⇒ 未来若要「搜备注 / 搜系列」，FTS 列已就绪，属**未来选项**，不在本阶段实现。

### 8.4 潜在全表扫描问题（Q18）

| 场景 | 原因 | 影响 |
| :--- | :--- | :--- |
| `relative_path LIKE '%q%'` | 前导通配，无法用索引 | 全表扫描 |
| 作者检索 `LIKE` | 关系 + LIKE | 全表扫描（authors/resource_authors） |
| 1–2 字查询 | 走 LIKE | 全表扫描 |
| `order_by` = `file_size` / `modified_time` | 无索引 | 排序成本 |
| `extension` / `scan_status` 过滤 | 无索引 | 过滤成本 |
| `_RESOURCE_SUMMARY_COLUMNS` 4 个相关子查询 | 每行 4 次 | 随行数增长 |
| `BrowseService` 作者 N+1 | 逐行查询 | 随行数增长 |

> 说明：这些都**不是当前阻塞项**（无大规模真实库证据），属 **Phase 3 之后的性能候选**；
> 本阶段只记录，不优化。

---

## 9. SQLite / Index Assessment

### 9.1 结论

```text
当前 SQLite + Query Layer + 既有索引【足以】支撑第一阶段的 Resource Search。
```

依据：

1. 目标过滤维度中，`resource_type` / `library_id` / `sha256` / `card_marker` /
   `relative_path` / `needs_review` 均有索引；
2. 关系维度的 EXISTS 子查询各自命中既有索引（resource_mod_usages / resource_plugins /
   resource_authors / resource_tags）；
3. 文本检索已有 FTS5 trigram + LIKE 回退；
4. 数据规模在本项目历史上为「数十资源」量级（真实样本 35）；无证据表明需要外部引擎。

### 9.2 明确不采纳的基础设施

| 基础设施 | 结论 |
| :--- | :--- |
| Elasticsearch / Lucene / 独立搜索引擎 | ❌ 不采纳（复杂度远超需要，违反本地优先/单文件定位） |
| 自建倒排索引 / 内存索引引擎 | ❌ 不采纳（SQLite 已足够；Everything 的索引机制属其内部实现，不迁移） |
| 内容索引（读文件内容） | ❌ 不采纳 |

### 9.3 未来选项（记录，不实现）

- 若出现真实大规模库的性能问题：**先**补普通索引（`extension` / `file_size` / `modified_time` / `scan_status`），
  再评估是否扩展 FTS 列；**最后**才考虑其他结构。
- 结构化查询若扩展：可评估在 FTS 上叠加字段限定（仍属 SQLite）。
- 所有这些都属 **future option**，不是本阶段动作。

---

## 10. Query Model Recommendation

### 10.1 目标（设计，不实现）

```text
GUI Filters ──┐
              ├──> Query Model ──> Query Layer（唯一执行点）──> SQLite
Text Query ───┘
```

**不应该存在两套搜索系统**：GUI 过滤与文本查询必须编译到**同一个 Query Model**。

### 10.2 推荐形态（候选，待 Phase 3.x 设计细化）

| 组件 | 职责 | 说明 |
| :--- | :--- | :--- |
| **Query Model** | 表达「一次查询」的结构化对象（字段 → 条件集合） | 可复用/扩展现有 `BrowserScope` 的思路，但**是否新建类型**由 3.x 决定 |
| **Compilers** | GUI 控件 → Query Model；文本语法 → Query Model | 两入口，同一模型 |
| **Query Layer** | 唯一 SQL 执行点，继续只读护栏 | 不因搜索而获得 UPDATE/DELETE 权限 |
| **Text Query Grammar** | 可选：`field:value`、AND(空格)、OR(`|`)、NOT(`!`/`-`) | **采纳前需 Contract 变更控制**（见 §13） |

### 10.3 字段候选（设计目标，非实现承诺）

```text
name:        → resources.name / display_name（文本面）
path:        → resources.relative_path（文本面）
ext:         → resources.extension
type:        → effective type（type_source='user' 时用用户值）
library:     → libraries / library_id
author:      → resource_authors / authors
mod:         → resource_mod_usages / mods
plugin:      → resource_plugins
tag:         → tags / resource_tags（P3.0 首期）
favorite:    → 保留系统 Tag
hash:        → resources.sha256
duplicate:   → 派生（GROUP BY sha256）
review:      → needs_review / review reasons
```

### 10.4 分层约束（必须保持）

```text
Search  →  Query Layer（只读）
User Write → User Write Service（唯一写入口）
GUI  →  Service / Query Layer，绝不直连 SQLite
```

---

## 11. Phase 3.1–3.5 Recommended Adjustments

> 以下为**建议**，不改变 P3.0.1 的路线次序，也不修改 Contract。
> 标 **[需变更控制]** 的项属于 Contract 范围之外，采纳前必须走 §16 流程。

| 子阶段 | P3.0.1 原意 | 本阶段建议（不改变次序） |
| :--- | :--- | :--- |
| **3.1 User Write Foundation** | 建立用户写入基础 | 保持；服务边界对齐 Contract §9；**不引入**搜索/语法；先解决 display_name 归属（Contract §3.1）落地 |
| **3.2 Tag System** | 标签体系 | 保持；Favorite = 保留系统 Tag；Tag 重命名冲突 = 拒绝不合并；确保 `resource_tags` 索引可用于后续过滤 |
| **3.3 Search & Query Foundation** | 搜索/查询基础 | **建议**：在此引入 **Query Model** 统一现有 GUI 过滤；加入 tag filter（In Scope）；**文本布尔语法属新增能力 → [需变更控制]** |
| **3.4 User Classification & Search** | 用户分类与搜索 | 让 **effective type**（user override 优先）进入搜索面；display_name 按 §3.1 变为可搜的用户值；favorite 经 Tag 可搜 |
| **3.5 CLI / GUI Integration** | CLI/GUI 集成 | CLI 与 GUI **共享 Query Model**；GUI 不直连 SQLite；先 CLI 验证 API 再 GUI（沿用既有边界） |

补充建议（不改路线）：

- 3.3 之前**不要**引入文本布尔语法；先证明结构化 Query Model 足够。
- taxonomy 在 3.4 只做「effective type」接线，**不**新增类型值、**不**做路径推断。

---

## 12. Risks

| # | 风险 | 说明 | 缓解 |
| :-- | :--- | :--- | :--- |
| R1 | **查询语法范围蔓延** | `field:` + AND/OR/NOT 不在冻结 In Scope，易被「顺手实现」 | 先走 §16 变更控制；或把文本语法后置 |
| R2 | **Taxonomy 与 Usage Category 混淆** | 把 skin/eyes/hair/accessory 当文件类型会重演 Phase 1 错误 | §4.3 / §7.3 明确三轴分离 |
| R3 | **Tag 与 Type 自动互转** | 会破坏「用户组织」与「资源是什么」的独立性 | 明确禁止双向自动转换 |
| R4 | **两套搜索系统** | GUI 过滤与文本查询各写 SQL | 强制共享 Query Model + Query Layer |
| R5 | **全表扫描 / 性能** | LIKE / 无索引排序 / 相关子查询 / N+1 | 记录为 future option，先测真实规模 |
| R6 | **GUI 越权直连 DB** | GUI 绕 Query Layer 或写 SQL | 既有静态测试守护保持 |
| R7 | **FTS 可用性差异** | 部分 SQLite 无 FTS5 | 已有 LIKE 回退，保持 |
| R8 | **多库组织范围未定（Contract U3）** | 组织/搜索是全局还是 per-library | 保持 OPEN-EVIDENCE，不在本阶段决定 |
| R9 | **display_name 归属未落地** | Contract §3.1 已冻结，实现未做 | 属 3.1/3.4，本阶段不实现 |

---

## 13. Contract Gaps

> 原则：发现 Gap → 记录 → 提 Recommendation；**不自行修改 Contract**（用户明确要求）。

| # | Gap | 说明 | 建议 |
| :-- | :--- | :--- | :--- |
| **G1** | **统一 Query Model 不在 Contract 明列** | Contract §12-6 只写「按标签浏览 = 只读标签筛选（additive）」；**没有**「统一搜索模型」条目 | 若决定在 3.3 引入 Query Model，属**架构选择**（不新增用户能力）时可视为在 In Scope 内实现既有筛选；**若包含用户可见文本语法则属新增能力** |
| **G2** | **结构化文本查询语法（`field:` + AND/OR/NOT）超出冻结 In Scope** | Contract In Scope 无此项；这是本阶段新识别的候选能力 | **[需变更控制]** 按 Contract §16：新增评审 + 更新 Contract + 用户确认；本阶段不实现、不改 Contract |
| **G3** | **`favorite:` / `tag:` 作为用户可见搜索字段** | Contract 只冻结「Tag 体系 + 只读标签筛选」，未冻结「文本语法中的 tag: 字段」 | 同 G2：先实现标签筛选；文本语法单独批准 |
| **G4** | **Taxonomy 未在 Contract 正式定义** | Contract §5 讲 Category vs Library/Path，§2 讲所有权，但**没有**「Resource Taxonomy」的显式定义 | 建议在后续 Contract 修订（或 3.x 设计）中补一节 Taxonomy 边界；**本阶段不修改** |
| **G5** | **effective type 的搜索语义未明列** | Contract §3 定义了 `type_source` 优先级，但未说「搜索用 effective type」 | 属实现细化；建议写入 3.4 设计 |

**STOP 提示**：G2 / G3 属于「Contract 本身不足」的情形。按本轮要求：
**已明确指出 Contract Gap，未自行修改 Contract**。

---

## 14. Explicit Non-Implementation Statement

```text
本阶段（Phase 3.0.2）为 DESIGN ONLY / READ-ONLY。

未做（全部未做）：
- 未修改代码
- 未修改 schema
- 未修改 migration
- 未修改依赖
- 未修改 CLI / GUI
- 未修改 Parser / Scanner
- 未修改 Query implementation
- 未实现 Search Service / Query Parser / Tag / Favorite / User Write Service
- 未创建索引
- 未创建 commit / tag

唯一新增：本文件 docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md
```

---

## 15. 问题 A–F 答案索引

| 问题 | 位置 | 摘要 |
| :--- | :--- | :--- |
| A. Current Architecture（Q1–Q5） | §2 | 1:1 File=Resource；6 个只读 Query 类；resources+16 表；可搜索字段=文本(name/display_name/path/author)+12 筛选；索引见 §2.5 |
| B. User Data（Q6–Q8） | §5 | 用户数据载体多数已存在但多未启用；写基础应为 `core/app` 单一写服务；display_name 有覆盖风险（Contract §3.1 已冻结修正方向，未实现） |
| C. Taxonomy（Q9–Q12） | §4 / §7 | 现枚举可承载类型轴；机器只能可靠产出 character_card/mod/unknown；skin/eyes/hair/accessory 属 Usage Category 而非文件类型；user override 经 type_source |
| D. Search（Q13–Q18） | §8 | Query Layer 可演化成统一搜索层；列可索引；目标入口均可由 SQLite 完成；FTS 已存在不需新增；存在 LIKE/排序/子查询成本点 |
| E. Everything-inspired（Q19–Q23） | §6 | index-first / instant / structured / field-based / cost awareness 可映射；Everything 内部实现/DB 格式/Windows 索引/完整语法/外部引擎不采纳；SQLite 可作第一阶段后端 |
| F. GUI / CLI（Q24–Q26） | §10 / §11 | GUI 与 Text Query 共享 Query Model；CLI 可先验证 Query/Service API；GUI 不得直连 SQLite（既有守护） |

---

## 16. 阶段结束条件核对

| 条件 | 状态 |
| :--- | :--- |
| P3.0 Contract remains authoritative | ✅ 未修改 Contract |
| P3.0.1 roadmap remains intact | ✅ 3.1–3.6 次序未改 |
| Everything 被明确识别为 Voidtools Everything Search | ✅ §0.2 |
| Everything 仅作为 Search Architecture Reference | ✅ §0.2 / §6.3 |
| Resource 被定义为主要 Search Object | ✅ §0 / §2.1 / §10 |
| KKS Resource Taxonomy boundary 明确 | ✅ §4.3 / §7.3 |
| Machine / User ownership 保持分离 | ✅ §5 |
| Search / User Write 保持分离 | ✅ §5.2 / §10.4 |
| Query Model boundary 明确 | ✅ §10 |
| GUI / CLI 可以共享 Query Model | ✅ §10.1 / §11 |
| SQLite / index strategy 已完成评估 | ✅ §9 |
| 没有未经批准的 Contract 修改 | ✅ §13（仅记录 Gap） |
| 没有 implementation | ✅ §14 |
| 没有 schema / dependency / code 修改 | ✅ §14 |

前置：**Phase 3.0.2 — DESIGN REVIEW COMPLETE**（待用户确认）。

---

## 17. 最终判断

> **KKS Resource Manager 是否可以在现有 Phase 1 / Phase 2 架构上，逐步形成一个类似
> Everything 的「即时搜索体验」，但搜索对象从 File 升级为 Resource？**

```text
Yes.

Existing machine facts
        +
Content Identity (sha256)
        +
Resource Taxonomy (resource_type + type_source)
        +
User-owned organization (tags / favorite / display_name / notes)
        +
SQLite / indexed Query Layer (existing indexes + existing FTS5 trigram)
        ↓
Resource Search Engine（第一阶段后端 = SQLite，无需外部引擎）
```

保留条件（不满足则需修正）：

1. **Taxonomy 边界**：不得把 skin/eyes/hair/accessory 当文件类型自动判定（§4.3）。
2. **Contract 变更控制**：任何用户可见文本查询语法（`field:` + AND/OR/NOT）在实现前
   必须先走 Contract §16 变更控制（§13 G2/G3）。
3. **性能证据**：大规模库的成本点（LIKE / 无索引排序 / 子查询 / N+1）需要真实基准后再优化。

> 本阶段结束。**不进入 Phase 3.1 实现**，等待下一步指令。
