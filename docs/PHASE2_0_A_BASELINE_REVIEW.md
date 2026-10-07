# Phase 2.0-A Baseline Review

> 阶段：Phase 2.0-A（Phase 1 Baseline Review，**只读审查**）
> 日期：2026-10-07
> 审查对象：仓库**当前实际代码**（不是报告转述）
> 本阶段产出：仅本文件。**未**修改 schema / migration / models / parser / scanner /
> query / app / GUI / CLI / tests / 配置 / 真实样本。
> 明确**未**做：Phase 2 设计、schema v3、Identity System、Duplicate Detection、
> Dependency Graph、Tags / Collections、外部 GitHub 项目研究。

---

## 1. Executive Summary

Phase 1 的收尾结论（`docs/phase1/PHASE1_FINAL_REPORT.md`：**PHASE 1 = CLOSED / PASS**）
在代码层面**成立**。逐条核查 Closure Report 声明的 14 项事实，**没有发现与实际代码
相冲突的内容**：

- schema 仍为 **v2**（`SCHEMA_VERSION = 2`、`MIGRATIONS = {1, 2}`），业务表 **16 张**；
- Parser / Scanner / ResourceStore / Query Layer / BrowseService / CLI 语义与报告一致；
- GUI 读只经 `BrowseService`、写只经 `core.app.LibraryAdminService`、扫描只经
  `core.app.run_scan`；`ui/` 内**没有** `sqlite3` 引用；
- `db.connect()` 未设 `check_same_thread=False`（默认 `True`），后台 worker 自开自关连接；
- Library Remove 严格「只删 `libraries` 行、资源保留、文件不动」；
- Incremental / Full 完全由 `LibraryScanner.scan(mode=...)` 决定；
- 1.5-C / 1.5-D 及所有「禁区」在代码中**均未实现**（只有说明性文字与一处 schema 预留值）。

本次**重新执行**了全部验收通道，结果与 Closure Report 一致：

```text
pytest                     671 passed / 0 failed / 0 skipped   (33.02s)
node tools/validate_schema.mjs     业务表 16/16，全部检查 OK，exit 0
node tools/check_model_sync.mjs    SQL 10 类型 == RESOURCE_TYPES 10，exit 0
```

同时发现一批**报告未逐字列出、但属于既有事实**的观察（详见 §12）：例如
`core/classification/` 是**仅注释的空壳**（实际类型赋值在 parser/store）、
FTS 索引里包含**从不写入**的 `resources.author` 死列、
`resources.file_path_key` 是**跨库全局唯一**、以及**当前 `data/` 数据库是空的**
（Phase 1 报告的样本数字来自临时库，不是这个持久库）。这些是事实澄清与遗留观察，
**不构成对 Closure Report 的实质冲突**，也**不改变** Phase 1 = CLOSED 的结论。

```text
PHASE 2.0-A = PASS
```

---

## 2. Phase 1 Current Architecture

### 2.1 分层（以当前 import 为准）

```text
main.py / cli_query.py          ← 入口 + CLI（参数解析、展示；不含查询逻辑）
      │
      ├── ui/  ──────────────────►  core/            （严格单向：ui → core）
      │     读: BrowseService
      │     写: core.app.LibraryAdminService
      │     扫: core.app.run_scan（经 ui/scan_worker.py）
      │
      └── core/
             app_paths  models  database  library  scanner  parsers
             query  app  thumbnails        （Phase 2 起: mod/   未实现: classification/ duplicate/）
```

事实依据：

- `core/__init__.py` 明确「本包与界面完全解耦，不 import PyQt6」；全仓 `core/` 内
  **没有** 任何 `PyQt6` import（唯一命中是 `core/__init__.py` 的 docstring）。
- `ui/*.py` 的 import 集合只有：PyQt6、`core.query`（`BrowserScope` / `LibrarySummary` /
  `ResourceListItem` / `ResourceSummary` / `ResourceDetail` / `ReviewReason`）、
  `core.models`（`RESOURCE_TYPES`）、`core.thumbnails`、`core.app`
  （`LibraryAdminService` / `run_scan`）、`core.scanner`（`RESULT_SKIPPED` / `SCAN_COMPLETED`）。
  **没有** `core.query.queries` 里的 `*Query` 类，也**没有** `sqlite3`。
- `tests/test_gui_smoke.py::test_ui_does_not_bypass_query_layer` 是这一边界的**静态守卫**：
  逐个检查 `ui/*.py`，禁止 `sqlite3`、`ResourceQuery`、`LibraryQuery`，
  并禁止 GUI 线程直接 `get_or_generate`（preview 必须走 worker）。

### 2.2 各模块当前职责（代码事实）

| 模块 | 职责 | 状态 |
| :--- | :--- | :--- |
| `core/app_paths.py` | 数据目录 / DB / 缩略图缓存 / 日志路径；`KKS_RM_DATA_DIR` 覆盖 | 完成 |
| `core/models/__init__.py` | 领域 dataclass + `RESOURCE_TYPES` / `AUTO_DETECTABLE_TYPES` + 作者哨兵处理 | 部分使用（见 §12-F13） |
| `core/database/schema.py` | 版本化内嵌 DDL（v1 / v2）+ FTS DDL + 表清单常量 | 完成，冻结 v2 |
| `core/database/db.py` | `connect` / `transaction` / `initialize` / `table_names` / 归一化 | 完成 |
| `core/library/store.py` | `libraries` 表 CRUD + 统计 + 删除预览/执行（**只碰 DB**） | 完成 |
| `core/scanner/scanner.py` | 目录遍历 + 增量判定 + 每文件事务 + `scan_records` | 完成 |
| `core/scanner/store.py` | 入库层：`resources` / `mods` / 关系表（先删后插） | 完成 |
| `core/parsers/{card,zipmod}.py` | 只读解析（PNG 卡 / ZIP manifest），绝不抛异常 | 完成 |
| `core/query/*` | 只读查询层 + DTO + 检索路由 + property 分类 + Browse 编排 | 完成 |
| `core/app/admin.py` | 薄写服务 `LibraryAdminService` + 模块级 `run_scan` | 完成 |
| `core/thumbnails/service.py` | 派生缩略图缓存（只读源文件、只写 cache） | 完成 |
| `core/mod/__init__.py` | 「Phase 2 实现」**仅注释**，`__all__ = []` | 空壳 |
| `core/classification/__init__.py` | 「Phase 1 起实现」**仅注释**，`__all__ = []` | 空壳（见 §12-F1） |
| `core/duplicate/__init__.py` | 「Phase 4 实现」**仅注释**，`__all__ = []` | 空壳 |
| `ui/*` | 主窗口 / 左中右三栏 / 过滤器 / 详情 / 预览 worker / 扫描 worker / Library 管理对话框 | 完成 |
| `main.py` | `--init-db` / `--info` / `--version` / `library` / `scan` / `query` / `gui` | 完成 |
| `cli_query.py` | `query` 子命令的**薄适配层**（只解析参数 + 格式化 DTO） | 完成 |

### 2.3 CLI 与 GUI 的入口对照

| 能力 | CLI | GUI |
| :--- | :--- | :--- |
| Library Add / Enable / Disable / Remove | ✅ `main.py library ...` | ✅（1.5-A，`LibraryAdminService`） |
| 扫描（增量 / 全量） | ✅ `main.py scan [--full]` | ✅（1.5-B，`ScanWorker` → `run_scan`） |
| 只读查询 | ✅ `main.py query ...`（`cli_query.py`） | ✅（`BrowseService`） |
| 缩略图 | —（CLI 不涉及） | ✅（`PreviewWorker` + `PreviewService`） |

版本与阶段：`core/__init__.py` → `__version__ = "0.15.0"`、`__phase__ = "Phase 1.5-B (Scan GUI)"`。

---

## 3. Current Schema v2

`core/database/schema.py`：`SCHEMA_VERSION = 2`；`MIGRATIONS = {1: (_V1_SQL, _V1_FTS_SQL), 2: (_V2_SQL, "")}`；
`MIGRATION_ADDED_COLUMNS = {2: (("resources", "card_marker", "TEXT"),)}`。
业务表 = `V1_TABLES`(13) + `V2_TABLES`(3) = **16 张**（本次 `validate_schema.mjs` 实测 16/16）。

### 3.1 v1 表（13）

| 表 | 主要职责 | 主键 / 唯一 | 关键外键 |
| :--- | :--- | :--- | :--- |
| `app_meta` | 应用元信息（`schema_version` / `fts_enabled` / `fts_error`） | `key` PK | — |
| `libraries` | 扫描根目录 | `id` PK；`root_path_key` UNIQUE | — |
| `authors` | 作者实体（去重后） | `id` PK；`name_key` UNIQUE | — |
| `resources` | **核心实体**（一文件一行） | `id` PK；`file_path_key` UNIQUE | `library_id`→libraries(SET NULL)、`author_id`→authors(SET NULL) |
| `tags` | 标签实体 | `id` PK；`name_key` UNIQUE | — |
| `resource_tags` | 资源↔标签 | PK(`resource_id`,`tag_id`) | 双向 CASCADE |
| `collections` | 集合实体 | `id` PK；`name_key` UNIQUE | — |
| `resource_collections` | 资源↔集合 | PK(`resource_id`,`collection_id`) | 双向 CASCADE |
| `mods` | MOD 实体（以 `guid` 为身份） | `id` PK；`guid` UNIQUE；`file_path_key` UNIQUE(可空) | `resource_id`→resources(SET NULL)、`library_id`→libraries(SET NULL) |
| `resource_mods` | 资源→MOD **汇总**关系（含未安装） | PK(`resource_id`,`mod_guid`) | `mod_id`→mods(SET NULL) |
| `duplicate_groups` | 重复组（Phase 4 预留） | `id` PK | — |
| `duplicate_members` | 重复组成员 | PK(`group_id`,`resource_id`) | 双向 CASCADE |
| `scan_records` | 每次扫描的运行记录 | `id` PK | `library_id`→libraries(**CASCADE**) |

### 3.2 v2 表（3）

| 表 | 主要职责 | 主键 | 说明 |
| :--- | :--- | :--- | :--- |
| `resource_plugins` | 资源→插件（KKEx 键）——**与 MOD 严格分离** | PK(`resource_id`,`plugin_guid`) | 插件**不**进 `mods` |
| `resource_mod_usages` | 资源→MOD 的**逐槽位**使用事实 | PK(`resource_id`,`mod_guid`,`property`) | 列含 `slot`/`local_slot`/`category_no` |
| `resource_authors` | 资源↔作者（多作者，含原始写法） | PK(`resource_id`,`author_id`) | 列含 `ordinal`/`raw_name` |

### 3.3 CHECK 约束与枚举（与 models 同步，已验证）

- `resources.resource_type` ∈ 10 值：`character_card, outfit_card, scene_card, mod, skin, eyes, hair, accessory, other, unknown`。
  `core/models.RESOURCE_TYPES` 与之一致；`AUTO_DETECTABLE_TYPES` = 其中 5 个
  （`character_card, outfit_card, scene_card, mod, unknown`）。`check_model_sync.mjs` 通过。
- `resources.type_source` ∈ `auto|user`；`scan_status` ∈ `new|present|missing|error`；
  `parse_status` ∈ `unparsed|ok|partial|failed|skipped`。
- `resource_tags.origin` ∈ `user|auto`；`resource_mods.relation` ∈ `uses|embeds`；
  `duplicate_groups.group_type` ∈ `file|content`、`status` ∈ `suggested|confirmed|dismissed`；
  `scan_records.mode` ∈ `full|incremental`、**`status` ∈ `running|completed|cancelled|failed`**。

### 3.4 当前 FTS

- 虚拟表 `resources_fts`：`fts5(display_name, name, author, series, description, notes)`，
  `content='resources'`、`content_rowid='id'`、`tokenize='trigram'`；
- 三支触发器 `resources_fts_ai` / `_ad` / `_au` 维持同步（外内容表模式）；
- 启用状态存于 `app_meta.fts_enabled`；`db._try_enable_fts()` 失败时静默退化，
  `db.initialize()` **仅在本次真的执行了迁移时**才 `_backfill_fts()`；
- 查询侧 `_fts_available()` 只读地要求「`fts_enabled == '1'` 且 `resources_fts` 存在」，否则全长度回退 LIKE。

### 3.5 模型能表达什么 / 不能表达什么（只列事实，不给方案）

**能表达：**

1. 一个文件 = 一个资源，且该资源至多属于一个 Library（`library_id` 可空）；
2. 资源类型（10 值枚举）、自动/人工来源（`type_source`）、扫描状态、解析状态、`needs_review`；
3. 资源 →（汇总）MOD 依赖，**含未安装 MOD**（`resource_mods.mod_id` 可空）；
4. 资源 → 逐槽位 MOD 使用事实，含槽位号与 property（`resource_mod_usages`）；
5. 资源 → 插件（`resource_plugins`），插件与 MOD 明确不混装；
6. 资源 → 多作者（`resource_authors` + `authors`），保留卡上原始写法与顺序；
7. MOD 实体：一个 `guid` 一行，含 manifest 字段与「本 MOD 自己的资源文件」（`mods.resource_id`）；
8. 任意自由元数据：`resources.metadata_json`（JSON）；
9. 扫描历史：`scan_records`（含 6 个计数列与 `duration_ms`）。

**不能表达（现状事实）：**

1. **File 与 Resource 的分离**：`resources.file_path_key` UNIQUE 强制一文件一行；
   schema 注释明确写「Phase 1 建立；未来可由关系表表达『一文件多资源』」——即目前**未**分离；
2. 资源↔资源的任意关系（除 `duplicate_*` 的重复语义外）；
3. **MOD↔MOD 依赖**（MOD 需要别的 MOD）——没有任何表/列表达；
4. 同一 `guid` 的**多版本共存**：`mods.guid` UNIQUE ⇒ 多版本会塌成一行，`version` 只是列值；
5. 插件作为**独立实体**：只有 `resource_plugins` 关系行，没有 `plugins` 表；
6. 插件↔MOD 的关联；
7. `relation` 的差异化：`resource_mods.relation` CHECK 允许 `uses|embeds`，
   但写入层**硬编码 `'uses'`**（见 §12-F11）；
8. 哈希身份：`resources.sha256` / `quick_hash` / `content_key` 三列存在，但**从未被任何代码写入**（§12-F4）；
9. 标签 / 集合：`tags` / `resource_tags` / `collections` / `resource_collections` 有表，
   但**无写入者、无查询 API、无 GUI**；
10. 重复检测：`duplicate_groups` / `duplicate_members` 有表，但**无写入者、无查询 API、无 GUI**；
11. 卡片的 `outfit_card` / `scene_card`：枚举里有、`AUTO_DETECTABLE_TYPES` 里有，
    但当前 Parser 只产出 `character_card`（PNG + 已知 marker）或失败——
    `core/parsers/__init__.py` 明写「`scene_card`：…（Phase 2）」，即**尚未实现**；
12. `resources.source`（来源）与 `resources.series`（系列）列存在，但扫描路径**从不写入**。

---

## 4. Current Resource Model

### 4.1 代码实际把什么视为 Resource

- **File**：磁盘上的候选文件（`.png` / `.zipmod` / `.zip`，由 `scanner.CANDIDATE_SUFFIXES` 决定是否尝试）。
- **Resource**：`resources` 表的一行，其身份键是 `file_path_key`。
  入库路径：`LibraryScanner._process_file()` → `ResourceStore.upsert_card_resource()`
  或 `upsert_mod_resource()`。
- **resource_type**：下列值由**不同层**给出——
  - PNG 卡片：`parsers.card.parse_card()` 给 `card_type = 'character_card'`（marker 命中时），
    否则 `None` → store 落 `'unknown'`；
  - zipmod：store **硬编码** `resource_type = 'mod'`（仅当解析成功且 GUID 存在）；
  - `outfit_card` / `scene_card` / `skin` / `eyes` / `hair` / `accessory` / `other`：
    schema 允许，但**当前没有任何代码写入**。
- **card**：`resources.card_marker`（KKS=`KoiKatuCharaSun` / KK=`KoiKatuChara`）+ `extension='.png'`；
  marker **只描述格式**，可同角色两种 marker 并存。
- **MOD**：`resources(type='mod')` 一行 **+** `mods` 一行（`guid` 为身份）。
  两者是同一物理文件的两个视角。
- **plugin**：`resource_plugins.plugin_guid` 字符串（KKEx 键），**不是**实体、**不是** MOD。
- **author**：`authors` 实体 + `resource_authors` 关系；`[Unknown]` 只进
  `metadata_json.authors_raw`，不建行。
- **usage**：`resource_mod_usages` 行（逐槽位）。**「usage」不是独立实体**，
  它是「资源→MOD」关系的细粒度事实；语义类别是从 `property` **只读推导**的（§7.2）。

### 4.2 File 与 Resource 是否已明确区分

**没有明确区分。** 依据：

- `resources.file_path_key` 有 UNIQUE 约束 —— **一个文件不可能有两行资源**；
- `schema.py` 在 `resources` 建表处自述「一个文件 = 一个资源（Phase 1 建立；
  未来可由关系表表达『一文件多资源』）」；
- 入库代码按「路径 key → 找到既有行就 UPDATE，否则 INSERT」这一唯一策略行为。

因此当前模型是 **File ≡ Resource（1:1）**。本阶段只陈述该事实，不设计分离方案。

### 4.3 「Resource」的边界在扫描路径上的实际含义

- 只有解析**成功**（`parse_status ∈ {ok, partial}`）的候选文件才会产生 / 更新资源行；
- 解析失败的文件：**若已入库**则保留行并标 `parse_status='failed'`、`scan_status='error'`
  （`mark_parse_failed`）；**若从未入库**则不建行（只记 `ScanIssue`）；
- 文件消失：只把**该 Library 下**且 `scan_status='present'` 的行改成 `missing`，
  绝不删行、绝不删文件（`mark_missing`）。

---

## 5. Current Identity Model

### 5.1 稳定身份（有唯一约束、被代码实际使用）

| 对象 | 身份字段 | 约束 | 使用位置 |
| :--- | :--- | :--- | :--- |
| 资源（文件） | `resources.file_path_key` | UNIQUE NOT NULL | `ResourceStore.find_by_path_key`、扫描增量键、`ResourceQuery.resolve` |
| MOD | `mods.guid` | UNIQUE | `upsert_mod_resource` 的 `ON CONFLICT(guid)`、`resource_mods` / `resource_mod_usages` 的 `mod_guid` |
| 作者 | `authors.name_key` | UNIQUE | `normalize_name_key = trim + casefold`；`_replace_authors` / `AuthorQuery.find_by_name` |
| Library | `libraries.root_path_key` | UNIQUE | `normalize_path_key`（展开 `~`、绝对化、统一分隔符、小写） |
| 标签 / 集合 | `tags.name_key` / `collections.name_key` | UNIQUE | **声明存在，当前无写入者** |
| 插件（弱） | `resource_plugins.plugin_guid` | 复合 PK 的一部分 | 仅作为关系键，**无实体表、无独立身份** |

### 5.2 扫描 / 增量判定字段（**不是**身份）

- `resources.file_size` + `resources.modified_time`：仅用于增量捷径
  （`_process_file` 比较 size 与 mtime，容差 `1e-6`），变了就重解析；
- `last_scanned_at` / `updated_at`：时间戳，非身份；
- 增量判定**不使用哈希**（代码注释与实现一致）。

### 5.3 展示字段（非身份）

`file_path`（展示用绝对路径）、`name`、`display_name`（可被用户改写，重扫时仅在
「`display_name` 仍等于旧 `name`」时才跟随更新）、`relative_path`。

### 5.4 只是 metadata（非身份）

- `metadata_json.data_id`（卡 `About.dataID`）—— **明确不作为身份 / 唯一键**；
  `schema.RESOURCE_METADATA_KEYS` 与 `parsers/models.py` 均写明；store 只把它写进 JSON。
- `metadata_json.user_id`（制作者 id）、`card_version`、`plugin_count`、
  `authors_raw`、`face_preview_kind`、`block_sizes`、`embedded_texture_count`。
- `resources.card_marker`：格式描述（KKS/KK），**非身份**（同角色可有两个 marker）。
- `resources.source`：来源，当前路径从不写入。

### 5.5 目前**没有**真正 identity model 的对象

- **内容哈希**：`sha256` / `quick_hash` / `content_key` 列存在，但**零写入**（§12-F4）；
  因此当前系统**没有**任何内容级身份，只有「路径身份」。
- **插件**：只有字符串键，没有实体、没有版本、没有来源。
- **MOD 版本**：`version` 是 manifest 的一个字段值，不参与身份（`guid` 唯一）。
- **作者别名 / 外部 id**：只有 `name` + `name_key`，无别名表、无外部标识。
- **File（相对于 Resource）**：没有独立的文件实体，`file_path_key` 同时充当
  「文件身份」与「资源身份」。

### 5.6 Phase 1 已确定的身份纪律（代码核对结果：**全部遵守**）

| 纪律 | 代码证据 | 结论 |
| :--- | :--- | :--- |
| card `dataID` 不是身份，只进 metadata | `store.build_card_metadata` 只写 `data_id`；无任何 UNIQUE / 索引基于它 | ✅ 遵守 |
| MOD GUID 是 MOD 唯一身份 | `mods.guid UNIQUE`；`resource_mods` / `resource_mod_usages` 以 `mod_guid` 为键 | ✅ 遵守 |
| 作者用 `name_key` 归一化 | `db.normalize_name_key`（trim+casefold）+ `authors.name_key UNIQUE` | ✅ 遵守 |
| `[Unknown]` 不建作者行 | `core.models.partition_authors` + `_replace_authors` 只对 `real` 建行，`raw` 存 JSON | ✅ 遵守 |

---

## 6. Current Relationship Model

### 6.1 已是数据库事实（DB 内可查、有写入者）

| 关系 | 载体 | 事实细节 |
| :--- | :--- | :--- |
| Library → Resource | `resources.library_id` FK `ON DELETE SET NULL` | 一个资源至多属于一个库 |
| Resource → MOD（汇总） | `resource_mods`（PK `resource_id+mod_guid`） | 含未安装 MOD（`mod_id` 可空）；`ref_count` 为**便利值** |
| Resource → MOD（逐槽位） | `resource_mod_usages`（PK `resource_id+mod_guid+property`） | 权威使用事实；含 `slot` / `local_slot` / `category_no` |
| Resource → Plugin | `resource_plugins`（PK `resource_id+plugin_guid`） | 插件与 MOD 分离 |
| Resource → Author | `resource_authors`（PK `resource_id+author_id`）+ `authors` | 多作者；`[Unknown]` 不入 |
| MOD → 自己的资源文件 | `mods.resource_id` FK `SET NULL` | zipmod 文件那一行 `resources` |
| MOD → Library | `mods.library_id` FK `SET NULL` | 随扫描更新 |
| Library → ScanRecord | `scan_records.library_id` FK **CASCADE** | 删库会删扫描历史 |

写入时机（`ResourceStore`）：卡片/zipmod 每次（重）解析都在**同一事务内**
「先删后插」重建 `resource_plugins` / `resource_mod_usages` / `resource_mods` / `resource_authors`，
因此重扫不产生重复关系行。zipmod 入库后回填 `resource_mods.mod_id`
（把「当时未安装」的依赖连到刚出现的 `mods` 行）。

### 6.2 由 Query Layer **推导**（不落库）

| 推导项 | 位置 | 依据 |
| :--- | :--- | :--- |
| 「缺失 MOD」 | `ModQuery.missing()` | `resource_mod_usages LEFT JOIN mods WHERE m.id IS NULL` |
| 「孤立 MOD」 | `ModQuery.orphan()` | `mods` 中无任何 usage 引用 |
| `has_missing_mods` 筛选 | `_resource_where` | 与 `ModQuery.missing()` 同口径的 EXISTS |
| MOD 的语义类别分布 | `UsageQuery.category_counts` | `classify_property(property)` |
| 「待确认」理由 | `ResourceQuery.review_reasons()` | `parse_status` / `name` / `resource_type` / unknown property |
| Library 资源计数 | `LibraryQuery._COLUMNS` | `COUNT(resources WHERE library_id=…)` |
| 资源行的 mod/usage/plugin/author 计数 | `_RESOURCE_SUMMARY_COLUMNS` | 四个 `COUNT` 子查询（权威来源，不读 `metadata_json`） |

### 6.3 目前**不存在**的关系

- **MOD → MOD**（依赖 / 前置 / 冲突）：无表、无列、无推导。
- **Resource → Resource**：除 `duplicate_*`（schema 预留、无写入者）外无任何关系。
- **Plugin → MOD / Plugin 实体**：插件只以字符串出现在 `resource_plugins`。
- **Tag / Collection → Resource**：表存在，但**无写入者、无 Query API、无 GUI**。
- **Duplicate → Resource**：同上。
- **作者 → MOD / 作者 → Library 的聚合**：只有 `authors → resources`。
- **文件 → 资源的多对多**：不存在（一文件一行）。

### 6.4 GUI 当前能做的关系浏览

- 左栏选 Library（`BrowserScope.library_id` 恒定带上当前库）；
- 过滤条三个**关系下拉**：作者 / 插件 / **缺失 MOD**（`FilterBar.set_relation_options`，
  数据来自 `BrowseService.authors(with_resources=True)` / `plugins()` / `missing_mods()`）；
- 详情面板反查：资源的 MOD / 插件 / 作者 / 逐槽位 usage（`ResourceDetail`）；
- MOD 闭环：从详情面板点 MOD → `MainWindow._on_mod_filter_requested(mod_guid)` →
  中栏按该 `mod_guid` 过滤（`BrowserScope.mod_guid`）；
- 缺失 MOD 与 `has_missing_mods` 开关；
- 注意：`BrowseService.orphan_mods()` 已存在且被测试，但 **GUI 未接线**（§9-P2.3）。

---

## 7. Query / Browse Capabilities

### 7.1 Query 类（唯一持有 SQL 的只读层）

`core/query/queries.py` 的 `_execute_select()` 是**只读护栏**：语句首关键字不是
`select` / `with` 就抛 `ReadOnlyViolation`。公开 API：

- `LibraryQuery`：`list` / `count` / `get`（含只读 `resource_count` 聚合）；
- `ResourceQuery`：`count` / `list` / `summary` / `resolve` / `get` / `usages` / `mods` /
  `plugins` / `authors` / `authors_raw` / `metadata` / `review_reasons`；
- `ModQuery`：`installed` / `missing` / `orphan` / `get` / `exists` / `detail` /
  `resources` / `usages`；
- `AuthorQuery`：`list` / `get` / `find_by_name` / `resolve` / `resources`；
- `PluginQuery`：`list` / `get` / `resources`；
- `UsageQuery`：`all` / `for_resource` / `for_mod` / `category_counts` /
  `category_stats` / `resources_using` / `mods_in_resource` / `unknown_properties`。

筛选维度（`_resource_where`）：`resource_type`、`game`（→marker）、`card_marker`、
`library_id`、`scan_status`、`needs_review`、`has_mods`、`has_missing_mods`、
`mod_guid`、`plugin_guid`、`author_id`、`property_category`、`query`（文本）。
排序白名单：`id,name,display_name,file_size,modified_time,created_at,updated_at`。

### 7.2 检索路由（`core/query/search.py` + `_text_search_clause`）

- 空 / 纯空白 → 不加文本条件；
- 1–2 字 → `LIKE '%q%'`（`%`/`_`/`\` 已转义，配 `ESCAPE '\'`）；
- ≥3 字且 FTS 可用 → `resources_fts MATCH`，列限定 `{display_name name}`，
  整段包成短语并以 `""` 转义，用户输入无法注入 FTS 运算符；
- FTS 不可用 → **所有长度**回退 LIKE；
- 覆盖面：资源 `name`/`display_name` + `relative_path`（**恒走 LIKE，从不进 FTS**）
  + 作者（`resource_authors JOIN authors` 的 `name` / `raw_name`）；
- **不搜** `file_path`（绝对路径噪声）与 `file_path_key`；**不读** `resources.author` 死列。

### 7.3 property 语义分类（`core/query/property_map.py`）

唯一映射：`ChaFileFace→face`、`ChaFileBody→body`、`ChaFileClothes→clothes`、
`ChaFileAccessory→accessory`、`ChaFileHair→hair`、`ChaFileMakeup→makeup`，
其余 → `unknown`（**不静默丢弃**）。SQL 谓词 `sql_category_predicate` 与
Python 侧 `classify_property` 出自同一份映射（有测试保证一致）。
**这是查询层的推导，不是 DB 事实**（DB 只存原始 `property` 字符串）。

### 7.4 Browse Read Model（`core/query/browse.py`）

`BrowserScope` 是筛选 + 排序的**唯一作用域对象**；`filters()` 是
「作用域 → ResourceQuery 参数」的**唯一转换点**，`page()` 用同一份 filters
同时算 `total` 与取行（因此两者不可能漂移）。`BrowseService` **不含任何 SQL**，
只复用上面 5 个 Query 类，并补跨实体信息（Library 名、作者显示名、可选 review reasons）。

---

## 8. GUI / Core Boundaries

| 行为 | 允许的通道 | 代码证据 |
| :--- | :--- | :--- |
| 读（Library / 资源列表 / 详情 / 关系下拉） | `BrowseService` | `ui/browser_panel.py`、`ui/library_panel.py`、`ui/detail_panel.py` 只 import `core.query` 的 DTO / `BrowserScope` |
| 写（Add / Enable / Disable / Remove） | `core.app.LibraryAdminService` | `ui/library_panel.py` / `library_admin_dialog.py` 经 admin service 调用；`_require_admin()` |
| 扫描 | `core.app.run_scan`（经 `ui/scan_worker.py`） | `ScanWorker.run()` 只调 `run_scan`；worker 自开自关连接 |
| 缩略图 | `PreviewService`（经 `PreviewWorker`） | `ui/preview_worker.py`；GUI 线程只 `status()` 轻查 |
| 禁止 | `sqlite3`、任何 `*Query` 类、GUI 线程生成缩略图 | `tests/test_gui_smoke.py` 静态断言 |

GUI 维护的唯一状态：`MainWindow._scanning: dict[library_id, ScanWorker]`
（**任务运行状态**，非资源状态的第二份副本）。扫描完成后的刷新链是
`LibraryPanel.reload(SELECT_KEEP)` → `BrowserPanel.reload_relation_options()` →
`BrowserPanel.reload()`，全部**重新从 Query Layer 读**；`ScanResult` 只用于
「是否成功 / 一句提示 / 是否刷新」，不缓存成 GUI 状态。

线程模型：`db.connect()` 未设 `check_same_thread=False` ⇒ 连接绑定创建线程 ⇒
后台 worker 只拿 `db_path`，在**自己线程**里 `connect` / `close`（`run_scan` 的 `finally`）。
扫描期 UI：单扫描策略（`if self._scanning: return None`，不排队）、按钮禁用、
被扫描库禁止删除（`_on_remove_clicked` 显式二次防护，不只依赖按钮禁用）；
关窗时 `_prepare_to_close()` 先确认、再 `QThreadPool.waitForDone`，
**不主动杀线程、不从 GUI 线程关 worker 连接**。

---

## 9. P2 / P3 Reassessment

以下按 `PHASE1_FINAL_REPORT.md` §8 逐项核对。**只判断，不设计、不改动**。

### 9.1 P2

| # | 项目 | 代码中是否仍存在 | 当前状态 / 证据 | 性质 | 是否可保持现状 |
| :-- | :--- | :--- | :--- | :--- | :--- |
| P2.1 | 跨库全局关系视图 | 是 | `BrowserPanel.scope()` 恒带 `library_id=self._library_id`；关系下拉来自全库，但资源结果是**库内** | 未来需求（无多库真实数据：样本 1 库，工作库 0 库） | 可以保持 |
| P2.2 | `scan_status` GUI 筛选 | 是（缺控件） | `BrowserScope.scan_status` 与 `ResourceQuery` 支持；`ui/filter_bar.py` **无** scan_status 控件 | 未来需求（样本 missing=0，无证据） | 可以保持 |
| P2.3 | orphan MOD 的 GUI 列表 | 是（未接线） | `BrowseService.orphan_mods()` 存在且被测试；`ui/` 中**无**引用（CLI 有 `query orphan-mods`） | 未来需求（属接线，不是新能力） | 可以保持 |
| P2.4 | 缺失 MOD 没有名称 | 是（数据不存在） | 本地无 manifest ⇒ `ModSummary` 只有 `guid` + 计数 | 数据固有，非缺陷 | 必须保持 |
| P2.5 | 扫描后关系筛选被重置 | 是 | `reload_relation_options()` → `set_relation_options()` 会 `clear()` 并重建、索引 0 = 「全部」 | 轻微 UX 技术债（既有行为） | 可以保持（已记录） |
| P2.6 | 作者 N+1 + LIKE 全表扫描 | 是 | `BrowseService.page()` 对每行调 `ResourceQuery.authors(row.id)`；文本检索在 1–2 字 / 无 FTS / `relative_path` / 作者路径上走 LIKE | 性能技术债（无规模证据） | 可以保持 |
| P2.7 | status → UI 映射重复两份 | 是 | `ui/browser_panel.py` 与 `ui/detail_panel.py` 各有一份映射（有意不引入 PreviewManager） | 轻微技术债 | 可以保持 |
| P2.8 | 冗余 / 死字段 | 是 | 见下方明细（已逐一核对代码） | 技术债 | 可以保持（但需在 Phase 2 立项时纳入考量，不得顺手删除） |
| P2.9 | `_replace_usages` 静默合并重复 `(mod_guid, property)` | 是 | `seen.setdefault((dep.mod_id, dep.property), dep)`（`store.py`） | 边缘技术债（样本 0 触发） | 可以保持 |

P2.8 明细（本次逐列核对）：

- `metadata_json.plugin_count`：仍被写入（`build_card_metadata`），而权威值是
  `COUNT(resource_plugins)` —— 冗余**仍在**（查询层已不读它）；
- `resources.author`：仍是**死列**（扫描路径不写；FTS 却仍索引它，见 §12-F4/F5）；
- `resources.author_id`：FK 存在，**从不写入**；
- `mods.description` / `mods.game` / `mods.md5`：列存在，`upsert_mod_resource` **不写**；
  且 `parse_manifest_xml` 的 `_MANIFEST_FIELDS` 也不含这三个字段；
- `resource_mods.relation`：仍恒为 `'uses'`（见 P2.9 的合并逻辑）。

### 9.2 P3

| # | 项目 | 代码中是否仍存在 | 当前状态 / 证据 | 性质 | 是否可保持现状 |
| :-- | :--- | :--- | :--- | :--- | :--- |
| P3.1 | 单扫描策略 | 是（有意为之） | `start_scan()` 中 `if self._scanning: return None`；不排队 | 设计选择 | 可以保持 |
| P3.2 | 关窗超时后可选「现在退出」 | 是 | `_prepare_to_close()` 的两段确认 + 兜底 `waitForDone(5s)`；不杀线程 | 设计选择 | 可以保持 |
| P3.3 | `db.connect()` 无 `busy_timeout` | 是 | `connect()` 只设 `foreign_keys` / `journal_mode=WAL` / `synchronous` / `temp_store` | 潜在技术债（被 P3.1 掩盖） | 可以保持 |
| P3.4 | 项目未 `git init` | 是 | `git status` → `fatal: not a git repository` | 流程 / 版本保护债 | 可以保持（但 Phase 2 涉及 schema 变更时风险上升，见 §12-F14） |

### 9.3 结论

以上 P2/P3 **全部仍与当前代码一致**，无一项已被悄悄实现或已被移除；
**没有任何一项需要在本阶段处理**，也**不应**在本阶段被自动升级成 Phase 2 任务。

---

## 10. Explicit Phase 1 Constraints

### 10.1 禁区核查（是否被「偷偷实现」）

核查方法：对 `core/` / `ui/` / `main.py` / `cli_query.py` 做关键词与结构检索，
并逐文件阅读疑似命中。结果：

| 禁区 | 是否实现 | 说明 |
| :--- | :--- | :--- |
| progress / cancel | ❌ 未实现 | `LibraryScanner.scan()` 签名无回调；无 progress bar / 百分比 / cancel 按钮 / `should_cancel` |
| filesystem watcher | ❌ 未实现 | 无 `QFileSystemWatcher` / `watchdog` / 文件变化检测 / 自动刷新 |
| EventBus | ❌ 未实现 | 仅 `core/app/__init__.py` docstring 写「刻意不引入」 |
| AppController | ❌ 未实现 | 同上 |
| Manager 层 | ❌ 未实现 | 只有 `LibraryAdminService`（薄转发）+ `PreviewService`（派生缓存），无管理抽象层 |
| 通用 Task Framework / 通用 Worker 基类 | ❌ 未实现 | `ScanWorker` 与 `PreviewWorker` 各自独立（`QRunnable` + `QObject` 信号），无共享基类 |
| MVVM / MVC 重构 | ❌ 未实现 | 现有分层未改名、未引入 view-model 体系 |
| AI | ❌ 未实现 | 全仓无 AI / 云 API 调用；仅 docstring 声明「禁止云端 AI」 |
| semantic search | ❌ 未实现 | 检索只有 FTS5 trigram + LIKE 字面量匹配 |
| batch file operations | ❌ 未实现 | 无批量移动 / 删除 / 重命名入口 |
| 自动文件移动 / 删除 | ❌ 未实现 | `os.remove/rename`、`shutil.move/rmtree` 在 `core/` 与 `ui/` 中**零命中** |
| 网络下载 / 在线 Mod 管理 | ❌ 未实现 | 无 `requests` / `urllib` / `httpx` / socket 使用；`requirements.txt` 无网络依赖 |

两个**唯一容易被误读**的命中，已逐一确认**不是**禁区实现：

1. `scan_records.status` 的 CHECK 含 `'cancelled'` —— 这是 **schema 预留值**，
   全仓没有任何代码写入该值（也无 cancel 逻辑）；属设计前瞻，不是功能；
2. `core/thumbnails/service.py` 有三处 `Path.unlink()` —— 全部只作用于
   **`data/thumbnail_cache/` 里的派生缓存文件**（失效缓存、损坏缓存、原子写入的临时文件），
   绝不触碰用户资源；符合「派生数据可丢弃」的既定约定。

**结论：无任何实际代码与 Closure Report 的禁区声明不一致。**

### 10.2 Phase 1 不变量清单（含代码锚点）

| # | 不变量 | 代码锚点 |
| :-- | :--- | :--- |
| 1 | **schema v2 baseline**：`SCHEMA_VERSION = 2`、`MIGRATIONS = {1,2}`、16 张业务表 | `core/database/schema.py`；`tests/test_gui_smoke.py::test_schema_version_unchanged` |
| 2 | **migration 不回改**：只追加版本；加列走 `MIGRATION_ADDED_COLUMNS`（幂等 `_add_column_if_missing`） | `schema.MIGRATION_ADDED_COLUMNS`、`db._add_column_if_missing` |
| 3 | **ui → core 单向依赖**：`ui/` 不 import `sqlite3` / `*Query` 类 | `tests/test_gui_smoke.py::test_ui_does_not_bypass_query_layer` |
| 4 | **Query Layer 只读**：只放行 `SELECT` / `WITH` | `core/query/queries.py::_execute_select` / `ReadOnlyViolation` |
| 5 | **SQLite 是事实来源**；Query Layer 是 GUI 浏览状态来源；GUI 不维护第二份资源状态 | `MainWindow._on_scan_finished` → `_refresh_after_scan`（全部重读）；GUI 只存 `_scanning` 任务状态 |
| 6 | **Parser / Scanner 不修改用户文件** | Parser 只 `open(rb)`；Scanner 只 `os.walk` + `stat`；`tests/conftest.py::sample_root` 用 sha256 前后一致断言 |
| 7 | **Library Remove 不删除资源文件**：只删 `libraries` 行；`resources.library_id`→NULL；`scan_records` 级联删除 | `LibraryStore.remove()` / `preview_removal()`；schema 的 `ON DELETE SET NULL` |
| 8 | **worker 自开自关 SQLite 连接** | `core/app/admin.py::run_scan()` 的 `finally: conn.close()`；`ui/scan_worker.py` |
| 9 | **`check_same_thread=True`**（默认，未改动） | `db.connect()` 无 `check_same_thread` 参数 |
| 10 | **写操作必须显式触发**：Add / Remove 有确认；Remove 文案明确「不删文件、不删资源」 | `ui/library_admin_dialog.py::confirm_remove` |
| 11 | **Incremental / Full 由 Scanner 决定**（GUI 只传 mode） | `LibraryScanner.scan(mode=...)`；GUI 无任何扫描规则 |
| 12 | **disabled 语义由 Scanner 决定**，GUI 只展示 `skipped` + `skip_reason` | `LibraryScanner.scan` 早退分支；`MainWindow._describe_scan_result` |
| 13 | 身份纪律：dataID 非身份 / MOD GUID 唯一 / 作者 `name_key` / `[Unknown]` 不建行 | §5.6 |
| 14 | 验证基线：pytest + 两个 Node 脚本 | 本次重跑结果见 §1 |

---

## 11. Phase 2 Starting Baseline

以下为**当前既成事实**，作为 Phase 2 的起点记录（**不含任何 Phase 2 设计**）：

1. **schema v2 冻结**：16 张业务表 + `resources_fts`（trigram）+ 3 触发器；
   任何 DDL 变更都必须是**新增版本**，不得回改 `_V1_SQL` / `_V2_SQL`。
2. **既有 core 语义稳定**：Parser / Scanner / ResourceStore / Query Layer /
   BrowseService / CLI 语义冻结，Phase 2 不得顺手改动。
3. **分层与边界**：`ui → core` 单向；读经 `BrowseService`、写经 `core.app`、
   扫描经 `run_scan`；GUI 不连库、不写 SQL。
4. **线程模型**：`check_same_thread=True`；后台任务 = `QThreadPool` + `QRunnable` +
   `QObject` 信号；worker 自开自关连接；单扫描策略生效。
5. **只读护栏**：查询层只放行 `SELECT`/`WITH`；Scanner/Parser 全程只读；
   派生缓存（`PreviewService`）可丢弃、只写 `data/thumbnail_cache/`。
6. **唯一事实来源**：SQLite + Query Layer；GUI 无第二份资源状态。
7. **身份现状**：路径身份（`file_path_key`）+ MOD `guid` + 作者 `name_key`；
   内容哈希列存在但未启用；插件无实体；`outfit_card`/`scene_card` 未产出。
8. **关系现状**：Library→Resource、Resource→MOD（汇总 + 逐槽位）、
   Resource→Plugin、Resource→Author 为 DB 事实；missing / orphan / 类别 /
   review reason 为 Query 推导；**MOD→MOD、Resource→Resource、Tag/Collection、
   Duplicate 均不存在**。
9. **Phase 2 起点已具备的素材**：zipmod 已能解析出 `guid/name/author/version/website`
   并写入 `mods`；卡片已能解析出 `ModID` 依赖（含未安装）并写入
   `resource_mods` / `resource_mod_usages`（`mod_id` 会在 MOD 出现时回填）。
10. **验证通道可用**：pytest 671 passed；`validate_schema.mjs` / `check_model_sync.mjs`
    exit 0；真实样本目录存在且 sha256 前后一致断言可运行。

---

## 12. Findings / Gaps

本节的「发现」全部是**代码事实陈述**或**事实澄清**，**不含解决方案**。

### 12.1 与 Closure Report 的一致性

- **F0-a**：Closure Report 声明的 14 项事实，本次逐条用代码核对，**全部成立**，
  未发现**实质冲突**。
- **F0-b（澄清）**：报告 §7 的样本数字（1 Library / 35 Resources / 13 MOD /
  134 缺失 guid 等）来自**临时库上的验证**；当前持久库
  `data/kks_resource_manager.db` 实测为 **0 Library / 0 Resource / 0 MOD**
  （schema v2、`fts_enabled=1`、16 表齐全、`scan_records` 0 行）。
  这是「数据状态」差异，**不是**报告与代码的冲突。

### 12.2 代码事实与报告未逐字列出的观察

- **F1**：`core/classification/` 是**仅注释的空壳**（`__all__ = []`），
  docstring 却写「Phase 1 起实现」。实际类型判定在 `parsers/card.py`
  （marker→`character_card`）与 `scanner/store.py`（zipmod 硬编码 `'mod'`）。
  ⇒ 「Level 1–4 识别优先级」目前是**文档概念，无实现载体**。
- **F2**：`core/mod/` 与 `core/duplicate/` 同为仅注释空壳（分别指向 Phase 2 / Phase 4）。
- **F3**：`core/parsers/models.py::ModDependencyRecord` 的字段名 `mod_id`
  实际承载的是**卡内 ModID（GUID 字符串）**；`store._replace_usages` 用它作为
  `resource_mod_usages.mod_guid` 写入。⇒ 命名与语义不一致（历史命名）。
- **F4**：内容哈希三列 `sha256` / `quick_hash` / `content_key` **零写入**
  （`core/scanner`、`core/parsers`、`core/query` 中无任何赋值路径）。
  ⇒ 当前**没有任何内容级身份 / 去重能力**，只有路径身份。
- **F5**：FTS 索引列包含 `resources.author`，但该列**从不被写入**（死列）。
  ⇒ FTS 的 author 字段实质为空；作者检索实际依赖 `resource_authors JOIN authors`
  （`_text_search_clause` 已如此实现）。
- **F6**：`resources.file_path_key` 是**全局唯一**（不含 `library_id`）。
  ⇒ 同一路径的文件不可能同时归属两个 Library；若同一路径出现在新库的扫描中，
  既有行会被**改挂**到新 Library（`upsert_*` 无条件 `UPDATE library_id`）。
- **F7**：`ResourceStore.mark_missing()` 按 `library_id = ?` 过滤。
  ⇒ 被 Remove Library 置空 `library_id` 的资源（`library_id IS NULL`）
  **永远不会**被后续扫描标记为 missing。
- **F8**：`mods.guid` UNIQUE ⇒ 同一 GUID 的多个版本**不能共存**为多行；
  `version` 只是列值，且重扫时会被后扫到的 manifest 覆盖。
- **F9**：`resource_mods.relation` 恒为 `'uses'`；`'embeds'` 虽在 CHECK 内，
  但**无任何代码写入**。
- **F10**：`tags` / `resource_tags` / `collections` / `resource_collections` /
  `duplicate_groups` / `duplicate_members` 六张表**无写入者、无 Query API、无 GUI**。
- **F11**：`core/models` 的 `ModEntry` / `ModDependency` / `CardSummary`
  三个 dataclass **定义但全仓无引用**（运行时实际用的是 `core/parsers/models.py` 的
  结果类与 `core/query/dto.py` 的 DTO）。`CardSummary.thumbnail_png` 亦无人使用
  （Phase 1.3-C 审计已记录）。
- **F12**：`resources.source` / `resources.series` 列存在但扫描路径不写入。
- **F13**：`resources.card_marker` 是 v2 通过 `ALTER TABLE ... ADD COLUMN` 加入的
  **无 NOT NULL 默认值**可空列，且有索引（`idx_resources_card_marker`）。

### 12.3 运行环境 / 产物观察

- **F14**：项目**未纳入 git**（`git status` → not a repository）。
  Phase 2 若动 schema，将**没有版本回退保护**（Closure Report 的 P3.4 同项）。
- **F15**：`data/thumbnail_cache/` 内除 3 个有效 `.webp` 外，还留有约 1 打
  `.<name>.webp.tmp-<pid>-<hex>` 临时文件（多为 0 字节）。它们由
  `PreviewService._atomic_save()` 的「临时文件 + `os.replace`」流程产生，
  属**可丢弃的派生缓存残留**，不影响数据库与源文件。
- **F16**：`pytest` 本次 671 passed / **0 skipped**，说明真实样本目录
  （`tests/conftest.py::DEFAULT_SAMPLE_ROOT`）当前**存在**且样本用例已实际执行
  （否则会是 skip 而非 pass）。

### 12.4 审查方法与证据边界（本次自查，避免过度推断）

- 本报告结论来自：逐文件阅读 `core/`（database / models / library / scanner /
  parsers / query / app / thumbnails）、`ui/`、`main.py`、`cli_query.py`、
  `tools/*.mjs`、`tests/conftest.py` 与 `tests/test_gui_smoke.py` 的边界断言；
- 关键词检索覆盖禁区清单（progress / cancel / watcher / EventBus / 网络库 /
  文件删除与移动 API 等）；
- **只读方式**查询了 `data/kks_resource_manager.db`（`file:...?mode=ro`，未产生 WAL 写入）；
- 执行 `pytest` 与两个 Node 校验脚本属于验收重跑，仅产生 `__pycache__` /
  `.pytest_cache` 等缓存产物，**未改动任何源码、schema、配置或测试文件**。

### 12.5 需要在 Phase 2 立项时「知道但不要顺手改」的清单

（仅为提醒基线，不是任务）

- schema v2 与 migration 历史（F13、§10.2-1/2）；
- `core/classification` / `core/mod` / `core/duplicate` 空壳语义（F1、F2）；
- 路径身份 vs 内容身份（F4、F6、F8）；
- 死列 / 冗余列 / 命名不一致（F3、F5、F9、F12、P2.8）；
- 未被使用的表与模型（F10、F11）；
- 无版本控制（F14）。

---

## 结论

Closure Report 的 14 项声明与当前代码**逐条一致**，验收通道**重跑通过**，
禁区**确认未被实现**，16 张表 / schema v2 / 单向分层 / 只读护栏 / 线程模型 /
身份纪律**全部保持**。

```text
PHASE 2.0-A = PASS
```

（本阶段到此结束：未进入 Phase 2.0-B，未设计 Phase 2，未改动任何功能代码。）
