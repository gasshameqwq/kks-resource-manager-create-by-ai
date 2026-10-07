# Phase 1.3 报告：数据模型审计 + 只读查询层（1.3-A）

> 版本：Phase 1.3（Query Layer）· schema v2（**未改动**）· 2026-10-06
>
> 前置：Phase 1.2-A/B/C/D 已完成，基线 `resources=35 / mods=13 /
> resource_mod_usages=1527 / resource_mods=315 / resource_plugins=206 /
> resource_authors=14 / authors=3`，真实样本目录 sha256 前后一致。

本报告包含两部分：

1. **第一轮架构/数据模型审计**（不改任何代码/schema）。
2. **Phase 1.3-A：只读查询层实现**（新增 `core/query/`，无 schema/Parser/Scanner 改动）。

---

## 第一部分：数据模型审计（第一轮结论）

### 1.1 关系图

```
app_meta                (schema_version / fts_enabled …)
libraries ──1:N──► resources ──N:M──► tags          (resource_tags)
   │                   │   └──N:M──► collections     (resource_collections)
   │              author_id N:1
   │                   ▼
   │                authors
   ├──1:N──► mods            (zipmod；guid 唯一；resource_id 指回资源行)
resources ──1:N──► resource_mods         (每 (resource, mod_guid) 汇总：ref_count / mod_id)
resources ──1:N──► resource_mod_usages   (每 (resource, mod_guid, property) 明细)
resources ──1:N──► resource_plugins      (KKEx 插件，与 MOD 无关)
resources ──N:M──► authors               (resource_authors；ordinal + raw_name)
resources ──N:M──► duplicate_groups      (duplicate_members；Phase 4，当前空)
scan_records ──N:1──► libraries
resources_fts (FTS5/trigram + 触发器)
```

### 1.2 逐题结论

| # | 问题 | 结论 |
| :-- | :-- | :-- |
| 1 | 资源唯一身份 | `resources.id`（代理键）+ `file_path_key`（归一化路径，UNIQUE）。**文件级身份**；`dataID` 只作元数据 |
| 2 | 物理文件 ↔ resource | 当前 **1:1**。zipmod = 1 行 `resources(type='mod')` + 1 行 `mods`（`mods.resource_id` 关联） |
| 3 | MOD 唯一身份 | `mods.guid`（manifest.xml）；依赖侧用字符串 `mod_guid`，与 `mods.id` 解耦（支持未安装） |
| 4 | 作者唯一身份 | `authors.name_key`（trim+casefold）；哨兵 `[Unknown]` 不建实体 |
| 5 | 一个资源几个 MOD | 0..N（实测单卡最多 43 个唯一 MOD） |
| 6 | 一个 MOD 被几个资源用 | 0..N（0 = 孤立；实测单 MOD 最多 12 张卡共用） |
| 7 | 一个资源几个作者 | 0..N（`resource_authors`；样本最多 2） |
| 8 | 一个作者几个资源 | 0..N（Anonymous 6 / Evaan 5 / Azurou 3） |
| 9 | 插件为何独立 | 插件无 manifest、不是 zipmod，混入 mods 会污染「缺失/孤立 MOD」与依赖图 |
| 10 | `resource_mods` vs `resource_mod_usages` | usages = 逐槽位事实；resource_mods = 按 (resource,mod) 的汇总投影（ref_count / mod_id） |
| 11 | 事实 vs 派生 | 事实：resources 文件/解析字段、usages、plugins、resource_authors、mods、scan_records；派生：`ref_count`、`mod_id`、`metadata_json.plugin_count` |
| 12 | 一致性风险字段 | `ref_count`、`metadata_json.plugin_count`、死字段 `resources.author/author_id`、`mods.description/game/md5`、恒 `'uses'` 的 `relation` |

### 1.3 `resource_mod_usages` 主键审计

对真实样本重跑 Parser 并与库内对照：

| 检查 | 结果 |
| :-- | --: |
| 原始 dependency 记录数 | 1527 |
| 库内 usage 行数 | 1527（相等，无丢失） |
| `(resource,mod_guid,property)` 重复 | 0 |
| 同 MOD + 同 property + 不同 `slot` | 0 |
| 同 MOD + 同 property + 不同 `local_slot` | 0 |
| 同 MOD + 同 property + 不同 `category_no` | 0 |

函数依赖实测：`property → category_no` 不成立；(mod,property) → category_no 成立；
(mod,property) → slot **不成立**（114 个键跨卡带多个 slot）——说明 slot/local_slot 是
**每卡的解析值**，property 才是稳定的槽位地址。结论：**保持主键 A**（方案 B 反而在
NULL 场景削弱去重）；仅当未来需要 per-usage 身份时才升级到方案 C（代理键 + UNIQUE）。

**代码语义**：Parser 是纯透传，不去重；`ResourceStore._replace_usages` 用
`seen.setdefault` 静默合并重复 `(mod_guid, property)`。样本 0 触发，属 P2（backlog）。

### 1.4 资源类型架构

保持 **架构 B**（MOD 是物理实体，眼睛/皮肤/头发/衣服/配饰语义由 `property` 表达）。
真实的 `ChaFileFace.* / ChaFileBody.* / ChaFileClothes.* / ChaFileAccessory.*` 只在
usage 里出现，没有独立的「眼睛/皮肤 PNG」。不新增 `resource_type`，不实施 A。

### 1.5 metadata_json 审计

8 个键中：`plugin_count` 是唯一**冗余**（权威值 = `COUNT(resource_plugins)`，实测 22/22 一致）；
`authors_raw` 是哨兵/原始顺序的**唯一**留存处，必须保留；`embedded_texture_count` 无冗余来源；
其余为纯解析元数据。结论：**不提升任何键为列**。`card_marker` 已正确地作为列存在。

### 1.6 第一轮决策表

| 项目 | 当前状态 | 是否需要修改 | 推荐方案 | 修改阶段 |
| :-- | :-- | :-- | :-- | :-- |
| resource identity | id + file_path_key | 否 | 保持文件级身份 | 不改 |
| resource_mod_usages PK | (resource,mod,property) | 否 | 保持 A | 不改 |
| resource_mods | 汇总 + ref_count | 否 | 保留；未来可改视图 | 不改 |
| authors | name_key 唯一 | 否 | 保持 | 不改 |
| plugins | resource_plugins | 否 | 保持 | 不改 |
| resource type | 架构 B | 否 | 保持 | 不改 |
| metadata_json | 8 键 | 否 | plugin_count 视为派生 | 不改 |
| scan_records | 无 files_parsed | 否 | 保持 | 不改 |
| duplicate detection | 空 | 否 | 留 Phase 4 | 不改 |
| query layer | 未实现 | **是** | 新增只读查询层 | **1.3-A** |

---

## 第二部分：Phase 1.3-A 实现（只读查询层）

### 2.1 范围与不变量

- **不动** schema / Parser / Scanner / 真实样本；**不迁移**数据。
- 查询层**只读**：所有语句经 `_execute_select`，非 `SELECT`/`WITH` 抛 `ReadOnlyViolation`。
- 不暴露 cursor，只返回不可变 DTO；不依赖 UI / Scanner。
- 权威来源：`resource_mod_usages`（使用事实）、`resource_plugins`（插件事实）、
  `resource_authors`（作者关系）、`COUNT(resource_plugins)`（插件数）。
  `metadata_json.plugin_count` **不作**事实来源；`resource_mods.ref_count` 仅作便利值。

### 2.2 Property classification 设计

单一事实来源 `core/query/property_map.py`。规则：把 `property` 按 `.` 切段，取**第一个**
恰好等于已知块名的段作为类别；否则 `unknown`（**绝不静默丢弃**）。

真实样本（1527 条 / 497 个不同 property）实测分布：

| 类别 | 块名 token | usage 行数 |
| :-- | :-- | --: |
| accessory | `ChaFileAccessory` | 1129 |
| clothes | `ChaFileClothes` | 280 |
| face | `ChaFileFace` | 62 |
| body | `ChaFileBody` | 25 |
| hair | `ChaFileHair` | 18 |
| makeup | `ChaFileMakeup` | 13 |
| unknown | — | 0 |

> **关键发现**：真实数据里还有第 6 个块 `ChaFileMakeup`（`PaintID1/PaintID2/cheekId/
> eyeshadowId/lipId`），用户需求清单里没有列出。为避免丢失信息，把它单列为 `makeup`
> 类别，而不是丢进 `unknown` 或错误并入 `face`。

粗粒度原则：`face ≠ eyes`（`ChaFileFace` 同时含眉毛/鼻子/嘴/脸型），`body ≠ skin`。

SQL 谓词由同一份映射生成，用**整段**匹配 `('.' || property || '.') LIKE '%.<token>.%'`
（避免 `NotARealChaFileFace` 之类子串误判），并由测试断言与 Python 分类逐行一致。

### 2.3 游戏格式映射

`core/query/card_format.py`：`KKS → KoiKatuCharaSun`、`KK → KoiKatuChara`，
集中管理，避免查询层硬编码 marker。

### 2.4 Query Layer API

| 类 | 方法（节选） | 能力 |
| :-- | :-- | :-- |
| `ResourceQuery` | `count / list / summary / get` | 资源列表（按类型/格式/库/状态/需确认/MOD/插件/作者/语义类别筛选，排序分页）、单资源详情 |
| `ResourceQuery` | `usages / mods / plugins / authors / metadata / authors_raw` | 资源 → MOD 明细/汇总、插件、作者、metadata、原始作者列表 |
| `ModQuery` | `installed / missing / orphan / get / exists / detail` | 已安装/缺失/孤立 MOD、单 MOD 详情 |
| `ModQuery` | `resources / usages` | MOD → 资源、MOD → 逐槽位 usage |
| `AuthorQuery` | `list / get / find_by_name / resources` | 作者列表/详情（归一化查找）、作者 → 资源 |
| `PluginQuery` | `list / get / resources` | 插件列表/详情、插件 → 资源 |
| `UsageQuery` | `for_resource / for_mod / category_counts / resources_using / mods_in_resource / unknown_properties` | 逐槽位事实查询、语义类别统计、unknown 审计 |

DTO（`core/query/dto.py`，全部 `frozen=True`）：`ResourceSummary / ResourceDetail /
ModSummary / ModDetail / ModUsage / ResourceModRef / ResourceAuthor / AuthorSummary /
PluginSummary / PropertyCategoryCount`。

### 2.5 实现文件变更列表

**新增**

| 文件 | 说明 |
| :-- | :-- |
| `core/query/__init__.py` | 查询层公共导出 |
| `core/query/property_map.py` | property → 语义类别（唯一事实来源 + SQL 谓词生成） |
| `core/query/card_format.py` | KK/KKS ↔ card_marker 映射 |
| `core/query/dto.py` | 不可变 DTO |
| `core/query/queries.py` | `ResourceQuery/ModQuery/AuthorQuery/PluginQuery/UsageQuery` + 只读护栏 |
| `tests/test_property_map.py` | 分类层单元测试（含 SQL↔Python 一致性） |
| `tests/test_query_layer.py` | 查询层合成 + 真实样本测试 |
| `docs/phase1/PHASE1_3_REPORT.md` | 本报告 |

**修改**

| 文件 | 改动 |
| :-- | :-- |
| `core/__init__.py` | `__version__` 0.3.0 → 0.4.0；`__phase__` → `Phase 1.3 (Query Layer)` |

**未改动**：`core/database/schema.py`、`core/database/db.py`、`core/parsers/*`、
`core/scanner/*`、`core/models/*`、真实样本目录。

### 2.6 测试结果

- 新增 40 个用例（`test_property_map.py` 9 + `test_query_layer.py` 31）。
- **全套 `pytest`：274 passed，0 failed，0 xfailed**（Phase 1.2 基线 234 + 新增 40）。
- 真实样本目录 sha256 由 `sample_root` 会话夹具在前后自动比对，**未变化**。

覆盖点：每种查询正常结果、不存在的 resource/mod/plugin/author、missing MOD、orphan MOD、
property 分类、unknown property、一个 MOD 多资源、一个资源多 MOD、同一 MOD 跨资源不同 slot、
查询层零写操作（`total_changes` 不变 + 写语句被拒）、与真实样本基线一致。

### 2.7 真实样本查询结果（验收证据）

| 查询 | 结果 |
| :-- | :-- |
| 资源总数 / 卡片 / MOD 文件 | 35 / 22 / 13 |
| 格式筛选 | KKS = 21，KK = 1，其余 13 = zipmod（无 marker） |
| MOD 已安装 / 缺失 / 孤立 | 13 / **134** / **3**（NoHair、elven_panst、koikatu.AltSlot.co_bot_19） |
| 插件去重数 / 作者数 | 29 / 3 |
| 语义类别 usage 统计 | accessory 1129、clothes 280、face 62、body 25、hair 18、makeup 13、unknown 0（合计 1527） |
| 作者 → 资源 | Anonymous 6、Evaan 5、Azurou 3 |
| 插件 → 资源（示例） | moreAccessories 22、com.bepis.sideloader… 21、KKABMPlugin.ABMData 12 |
| MOD 共享（naginata） | 命中 2 个资源（红豆 / 长尾景虎），property 不同 |
| 无 MOD 卡片（罗德尼） | mod_count = 0，plugin_count = 1 |
| `ref_count` 复核 | 315 条 (resource,mod) 全部 == 对应 usage 行数 |
| 查询层写操作 | 0（`total_changes` 不变） |

### 2.8 是否出现新的 P0/P1 数据模型问题

**没有。** 本轮为纯新增只读层，未触碰 schema/Parser/Scanner；基线数字与 sha256 全部保持。
审计中发现的均为 P2（见 backlog）。

### 2.9 Backlog（本阶段明确不处理）

- `_replace_usages` 静默合并重复 `(mod_guid, property)`（建议未来加计数/告警，不改 schema）。
- `metadata_json.plugin_count` 冗余（权威值 = `COUNT(resource_plugins)`）。
- 死字段 `resources.author` / `author_id`；`mods.description` / `game` / `md5`。
- `resource_mods.relation` 恒为 `'uses'`。
- `mods.author` 未归一化 → 「作者制作的 MOD」暂不可建模。
- Phase 4 duplicate detection。

### 2.10 下一阶段建议

1. **1.3-B（推荐）**：把查询层接入 CLI（`main.py` 新增 `query` 子命令），
   用真实样本演示「资源→MOD / MOD→资源 / 缺失 / 孤立 / 语义筛选」，作为 UI 之前的可见验收。
2. **1.3-C**：缩略图缓存 + 「待确认」流程（Phase 1.3 原计划），仍不改 schema。
3. 只有在真实需求出现时，才考虑：方案 C（per-usage 代理键）、把 `plugin_count`
   改为视图/删除、作者→MOD 建模。**在此之前不改 schema。**

---

## 第三部分：Phase 1.3-B —— CLI Query 验收层

> 目标不是把 CLI 做漂亮，而是验证「当前 Query Layer 是否足以作为未来 GUI 的数据访问基础」。

### 3.1 命令设计

```text
python main.py query resources   [--type T] [--game KKS|KK] [--library ID] [--status S]
                                 [--needs-review] [--mod GUID] [--plugin GUID] [--category C]
                                 [--with-mods | --without-mods] [--order F] [--desc]
                                 [--limit N] [--offset N] [--json]
python main.py query resource <id|path|key>      [--json]
python main.py query resource-mods <resource>    [--json]
python main.py query resource-plugins <resource> [--json]
python main.py query resource-authors <resource> [--json]
python main.py query mods                        [--json]
python main.py query mod <guid>                  [--json]
python main.py query mod-resources <guid>        [--json]
python main.py query mod-usages <guid> [--category C] [--json]
python main.py query authors                     [--json]
python main.py query author <name|id>            [--json]
python main.py query author-resources <name|id>  [--json]
python main.py query plugins                     [--json]
python main.py query plugin <guid>               [--json]
python main.py query plugin-resources <guid>     [--json]
python main.py query missing-mods                [--json]
python main.py query orphan-mods                 [--json]
python main.py query usages [--resource R] [--mod GUID] [--category C] [--limit N] [--offset N] [--json]
python main.py query usage-categories [--resource R] [--mod GUID] [--json]
python main.py query unknown-properties [--resource R] [--mod GUID] [--json]
```

退出码：`0` 成功（含「查询成功但结果为空」）；`1` 目标不存在（Resource/MOD/Plugin/Author not found）；
`2` 参数错误（未知 game / category / order 等）。所有错误都是**单行消息到 stderr**，不抛 traceback。

### 3.2 展示层分层（严格）

```text
CLI arguments  ->  Query Layer (core.query)  ->  DTO  ->  CLI formatter
```

CLI（`cli_query.py`）只做参数解析与格式化；**不拼 SQL、不知道表结构、不判断
missing/orphan、不分类 property、不解析 metadata_json、不做 author normalization**。

### 3.3 Query Layer 需要的调整（4 处，均为查询层职责）

| 新增 | 原因 | 归属 |
| :-- | :-- | :-- |
| `ResourceQuery.resolve(id/path/key)` | `query resource <id/path/key>` 的身份解析 | 查询层（不是 CLI 打补丁） |
| `ResourceQuery.list/count(has_mods=…)` | 「无 MOD 的角色卡」筛选 | 查询层 |
| `AuthorQuery.resolve(name/id)` | `query author <name/id>` | 查询层 |
| `UsageQuery.all(...)` + `UsageQuery.category_stats(...)` + DTO `PropertyCategoryStats` | 全库 usage 查询 + 每类别 usage/资源/MOD 统计 | 查询层 |

未出现「CLI 自己拼 SQL / 自己判断 missing、orphan、category」等情况。

### 3.4 实现文件变更

**新增**

| 文件 | 说明 |
| :-- | :-- |
| `cli_query.py` | `query` 子命令的 parser + handlers + 人读/JSON formatter（薄适配层） |
| `tests/test_query_cli.py` | CLI 验收测试（合成 12 + 真实样本 6） |

**修改**

| 文件 | 改动 |
| :-- | :-- |
| `main.py` | 注册 `query` 子命令并 dispatch；docstring 增加用法 |
| `core/query/dto.py` | 新增 `PropertyCategoryStats` |
| `core/query/queries.py` | `resolve` ×2、`has_mods` 过滤、`UsageQuery.all` / `category_stats` |
| `core/query/__init__.py` | 导出 `PropertyCategoryStats` |
| `core/__init__.py` | 版本 0.4.0 → 0.5.0；`__phase__` → `Phase 1.3 (Query Layer + CLI)` |

**未改动**：`core/database/schema.py`、`core/database/db.py`、`core/parsers/*`、
`core/scanner/*`、`core/models/*`、真实样本目录。

### 3.5 测试结果

- 新增 **22** 个用例（`test_query_layer.py` +4，`test_query_cli.py` +18）。
- **全套 `pytest`：296 passed，0 failed，0 xfailed**（1.3-A 的 274 + 22）。
- 真实样本目录 sha256：测试会话前后一致（`sample_root` 夹具自动断言）。
- 数据库文件 sha256：CLI 查询前后一致（合成 + 真实样本各一条测试断言）。

### 3.6 真实样本 CLI 验收（15 个核心场景）

| # | 场景 | 命令 | 结果 |
| --: | :-- | :-- | :-- |
| 1 | 全部资源 | `query resources` | 35 |
| 2 | 角色卡资源 | `query resources --type character_card` | 22 |
| 3 | KK / KKS 筛选 | `--game KKS` / `--game KK` | 21 / 1 |
| 4 | 资源 → MOD | `query resource-mods <沙耶香卡>` | 1 个 MOD，`ref=4`，category=accessory |
| 5 | MOD → 资源 | `query mod-resources com.Quokka.naginata` | 2 |
| 6 | MOD 的 usage | `query mod-usages com.Quokka.naginata` | 2 条，property 不同 |
| 7 | 角色卡插件 | `query resource-plugins <ユウキ>` | 21 |
| 8 | 插件 → 资源 | `query plugin moreAccessories` | 22 |
| 9 | 缺失 MOD | `query missing-mods` | 134 |
| 10 | 孤立 MOD | `query orphan-mods` | 3（NoHair / elven_panst / koikatu.AltSlot.co_bot_19） |
| 11 | 作者及其资源 | `query author-resources Evaan` | 5 |
| 12 | 按语义类别 | `query usages --category clothes` | 280（总计） |
| 13 | makeup | `query usages --category makeup` | 13 |
| 14 | unknown property | `query unknown-properties` | 0（样本无未知块） |
| 15 | 无 MOD 角色卡 | `query resources --type character_card --without-mods` | 2 |

类别统计（`query usage-categories`）：face 62 / body 25 / clothes 280 / accessory 1129 /
hair 18 / makeup 13 / unknown 0（合计 1527）。

### 3.7 数据库是否完全未修改

**未修改。** 合成库与真实样本库的 `.db` 文件 sha256 在查询前后完全一致；
真实样本目录整体 sha256 也一致。CLI 全部走只读 Query Layer，未产生任何写语句。

### 3.8 是否发现新的 P0/P1

**没有。** 本轮为新增 CLI 适配层 + 4 处查询层能力补充，未触碰 schema/Parser/Scanner。

### 3.9 P2 backlog 新增

- 无新增实质问题。仅记录：`query usages` 全库默认会打印 1527 行，实际使用建议配 `--limit`
  （未来 GUI 会分页，不影响当前 Query Layer）。

### 3.10 对 Phase 1.3-C 的建议

**结论：当前 Query Layer 已足以作为未来 GUI 的数据访问基础（YES）。**

因此：

1. **停止扩充 CLI**（1.3-B 验收已达成，不再加命令）。
2. 进入 **Phase 1.3-C**：缩略图缓存 + 「待确认」流程（仍不改 schema）。
3. GUI（1.4）只调用 `core.query`，不新增数据访问路径；若发现缺口，对应能力补进 Query Layer。
