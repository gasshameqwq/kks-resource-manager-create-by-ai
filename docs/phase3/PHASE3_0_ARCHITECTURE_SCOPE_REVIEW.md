# Phase 3.0 — Architecture / Scope Review（只读）

> 阶段：**Phase 3.0（Architecture / Scope Review，只读 + 设计）**
> 日期：2026-10-07
> 权威前序契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`、`docs/phase2/PHASE2_FINAL_CLOSURE_REPORT.md`
> 前序基线：Phase 1（`docs/phase1/PHASE1_FINAL_REPORT.md` = CLOSED / PASS）、
> Phase 2（`docs/phase2/PHASE2_FINAL_CLOSURE_REPORT.md` = CLOSED / PASS）
> 本阶段产出：**仅本文件**。
> 本阶段**未**修改代码 / schema / migration / models / parser / scanner / store / query /
> DTO / CLI / GUI / tests / 既有文档；**未**创建 commit、**未**创建 tag、**未**执行 migration；
> **未**改动 Git 历史。

> ⚠️ 本文件是 **Phase 3.0 的候选分析**，**不是** Phase 3 的正式 Contract。
> 它**不决定** Phase 3.1 / 3.2 / 3.3 的最终内容，只给出候选拆分与依据。
> 在正式 Architecture / Scope Contract 冻结之前，**不得进入任何 Phase 3.x 实现**。

---

## 0. 只读声明 / Git 基线 / 方法与证据

### 0.1 只读声明

本阶段全程只读。允许的动作只有「读代码 / 读文档 / 只读查询数据库 / 运行既有验收通道」；
唯一新增物是本文件。明确**未做**：

- 未改代码、未改 schema（`core/database/schema.py` 零改动）、未改 migration、未改测试；
- 未创建 commit、未创建 tag、未新增 remote、未 push；
- 未移动 / 重命名 / 删除任何文件；
- 未实现任何 Phase 3 功能（tags / collections / favorites / review / GUI 管理 … 一律未做）。

### 0.2 Git 基线（本阶段开始时实测）

```text
branch      main
HEAD        202c285d2e319391e618347a4e46cb0607d84495   （HEAD 全值）
HEAD short  202c285d
tag         phase-2.0-closed / phase-2.1-closed / phase-2.2-closed
            phase-2.3-closed / phase-2.4-closed        （5 个 tag 齐备）
working tree  clean（本阶段开始前 `git status --short` 为空）
remote      none（无 remote、无 push）
```

### 0.3 验收通道实测（本阶段重跑，只读）

```text
.venv\Scripts\python.exe -m pytest -q -rs   → 734 passed / 0 failed / 0 skipped（38.75 s）
node tools/validate_schema.mjs               → 16 表 / 全项 OK / exit 0
node tools/check_model_sync.mjs              → schema ↔ models 一致 / exit 0
```

只读查询持久库 `data/kks_resource_manager.db`（`mode=ro`）：

```text
libraries 0 / resources 0 / mods 0 / tags 0 / collections 0 / duplicate_groups 0
schema_version = 2
```

> 说明：持久工作库当前是**空库**；Phase 1 / Phase 2 报告里的样本数字来自**临时库上的只读样本验证**，
> 不是这个持久库。此事实与 Phase 2.0-A §12-F0-b 的结论一致。

### 0.4 主要证据来源

| 类别 | 来源 |
| :--- | :--- |
| Phase 1 契约 | `docs/phase1/PHASE1_FINAL_REPORT.md`、`PHASE1_3C_AUDIT.md`、`PHASE1_4C_CLOSURE_REPORT.md`、`PHASE1_5_DESIGN_REVIEW.md` |
| Phase 2 契约 | `docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`、`PHASE2_1/2.2/2.3_CLOSURE_REPORT.md`、`PHASE2_FINAL_CLOSURE_REPORT.md` |
| 基线复审 | `docs/PHASE2_0_A_BASELINE_REVIEW.md` |
| 外部研究 | `docs/phase2/PHASE2_0_B_RESEARCH.md`（14 个项目 + 来源链接） |
| 真实样本 | `docs/phase1/SAMPLE_ANALYSIS.md`、`tests/conftest.py::sample_root`（会话级 sha256 前后一致断言） |
| 实际代码 | `core/database/schema.py`、`core/models/__init__.py`、`core/query/{queries,dto,browse}.py`、`core/scanner/*`、`core/parsers/*`、`cli_query.py`、`ui/*` |
| Git | 本阶段只读 `git status / log / rev-parse / tag` |

外部生态补充核对（只读抓取，非项目文件）：
`IllusionMods/KKManager` README（确认「浏览已安装 zipmod/插件并查看信息」+「自动从互联网查找并安装更新」）。
其余外部结论沿用仓库既有 `PHASE2_0_B_RESEARCH.md`（附来源链接）。

---

## 1. Executive Summary

**一句话结论**：Phase 1 建立了「我有什么资源」，Phase 2 建立了「文件的字节内容身份与字节重复」。
系统现在是一个**可靠的、只读的、可搜索的本地资源索引**；它仍然**不是一个资源管理器**——
用户无法组织、标注、归类、确认或修正任何东西。

本阶段的核心发现：

1. **Phase 2 的实际能力比原路线图小得多，但真实且可用。**
   实际交付 = 内容身份（`resources.sha256` 真正写入）+ 字节重复派生查询 + Query/CLI/GUI 只读暴露。
   **没有**新增 schema、没有持久化重复、没有新语义身份、没有依赖图、没有 tags/collections。

2. **最大能力缺口不是「再加一个查询」，而是整个「用户组织 / 管理」层缺失。**
   `tags` / `resource_tags` / `collections` / `resource_collections` 四张表自 v1 起存在，
   但**零写入者、零 Query API、零 CLI、零 GUI**；`resources.notes` / `display_name` /
   `type_source='user'` 三条「可人工修正」的落点**没有任何用户入口**。
   「默认只读」是硬约束，但「可人工修正」目前**只有数据库支持，没有实现表面**。

3. **身份现状**：
   - **File / Resource identity = 路径**（`file_path_key`，全局唯一）——改名/移动即变成「新资源」；
   - **Content identity = `sha256`**（原始字节）——只证明 byte-identical，**不**证明同角色 / 同变体；
   - **Logical identity = `mods.guid`**（MOD 唯一）——同域参考实现一致；
   - **Family / Variant identity = 不存在**，且当前**没有数据源**可以建立。

4. **关系现状**：唯一可靠的跨实体关系是「**资源使用了哪些 MOD**」（`resource_mods` /
   `resource_mod_usages`，来自卡片 KKEx sideloader 表）。
   **`uses` 不能证明 `requires`**：manifest.xml 没有依赖字段，KKManager 的 `ModInfoBase` 也没有；
   「缺失 MOD」只表示「被引用但本地没安装」，**不表示依赖不满足**。

5. **相似性 / 变体**：当前只能可靠证明**字节完全相同**（sha256）。「同角色重导出」「跨格式同角色」
   在真实样本里**确实存在**（HigashiyamaKobeni ×2 同大小不同 sha256；Kugisaki KKS vs KK），
   但**不可计算**（NOT DETECTABLE WITH CURRENT EVIDENCE）。任何 `same resource / version / variant`
   只能作为**候选关系 + 人工确认**，不得自动建为事实。

6. **外部生态**：KKManager 与同域生态解决的问题是「已安装 mod 清单 + 在线更新 + 清理重复文件 + 卡片浏览」，
   数据源是本地游戏目录 + manifest.xml + 在线服务器。**在线更新、安装到游戏目录、删除重复文件**
   与本项目「本地优先 / 默认只读 / 位置与分类分离」三条硬约束**直接冲突**，只能借鉴概念、不能照搬行为。

7. **架构建议（候选，不是决定）**：Phase 3 若要做「资源管理」，应把重点放在
   **数据库层的虚拟组织**（tags / collections / favorites / notes / review），
   **绝不**用文件系统 move / rename / delete 实现组织。组织必须锚定稳定的 `resources.id`，
   因此**首个必须解决的架构问题**是「写入 / 变异（mutation）语义 + 组织数据的持久化边界」，
   而不是 GUI 按钮。

8. **本报告不决定 Phase 3.1 / 3.2 / 3.3 的最终拆分**，只给出候选工作流与依据（§11），
   并明确 OUT OF SCOPE（§12）与验收边界（§14）。

```text
Phase 3.0（本报告）= 候选范围 / 架构 / 证据分析，未冻结任何 Phase 3 Contract。
```

---

## 2. Phase 2 Actual Baseline

> 本节**只按实际代码与已封存契约**描述（不按路线图描述）。

### 2.1 Phase 2 真正建立了什么能力

| # | 能力 | 载体（实际代码 / 契约） | 证据 |
| :-- | :--- | :--- | :--- |
| 1 | **文件字节内容身份真正落地** | 扫描重解析时写入 `resources.sha256`（Phase 2.1） | `core/scanner/hashing.py::sha256_of_file`；`scanner._process_file` 在 `parsed.success` 时计算；`ResourceStore.upsert_card_resource / upsert_mod_resource` 的 `sha256: str` 必填参数；`tests/test_content_identity.py`（14） |
| 2 | **哈希读取一致性（C7）** | 读取窗口 `stat_before → parse → sha256 → stat_after`；窗口内 `(size, mtime)` 变化则整体不提交 | `scanner._process_file`；`PHASE2_0_C` §5.6 / §13.3 C7；`test_c7_*` |
| 3 | **字节重复派生能力** | `ResourceQuery.duplicates()`：`GROUP BY sha256 HAVING count(*)>=2`，只读、不落库 | `core/query/queries.py`；`tests/test_duplicate_query.py`（13） |
| 4 | **重复读模型 DTO** | 不可变 `DuplicateGroup(sha256, resources)` + `member_count` | `core/query/dto.py`；`core/query/__init__.py` 导出 |
| 5 | **单资源视角重复组** | `ResourceQuery.duplicate_group_for(resource_id)` | `core/query/queries.py`；`tests/test_query_surfacing.py` |
| 6 | **Query / DTO 暴露** | `ResourceSummary.sha256`（additive、末尾、默认 `None`）；`_RESOURCE_SUMMARY_COLUMNS` 增 `r.sha256` | `core/query/dto.py`、`core/query/queries.py` |
| 7 | **Browse 只读转发** | `BrowseService.duplicates()` / `duplicate_group_for()`（无自有 SQL） | `core/query/browse.py` |
| 8 | **CLI 暴露** | `query duplicates`（人类可读 + `--json`）；`_resource_obj()` 增 `sha256` 键（additive） | `cli_query.py`；`tests/test_query_cli.py`（28） |
| 9 | **GUI 暴露** | DetailPanel Basic 区新增「内容哈希」（截断 + tooltip 全值）与「字节完全相同的资源数」 | `ui/detail_panel.py`、`ui/main_window.py`；`tests/test_gui_detail.py` |

### 2.2 阶段数字（实测）

| 节点 | 全量 pytest |
| :--- | ---: |
| Phase 1 基线 | 671 |
| + 2.1 内容身份 | 685 |
| + 2.2 字节重复 | 698 |
| + 2.3 Query/CLI/GUI 暴露 | **734** |
| 本阶段重跑 | **734 passed / 0 failed / 0 skipped** |

### 2.3 Phase 2 **没有**建立什么（同样重要）

| 未建立 | 证据 |
| :--- | :--- |
| 无 schema v3 / 无 migration | `SCHEMA_VERSION == 2`、`MIGRATIONS == {1,2}`、业务表 16；`core/database/schema.py` 全期零改动 |
| 无新表 / 无新列 / 无新索引 | 沿用既有 `resources.sha256` + `idx_resources_sha256` |
| 无持久化重复 | `duplicate_groups` / `duplicate_members` 仍零写入（`total_changes` 不变有守门测试） |
| 无 `canonical` / `dismiss` / `confirmed` 概念 | 无相关写入 API / DTO / CLI / GUI |
| 无 same-character / semantic / perceptual duplicate | 无 phash / embedding / opencv / ocr 依赖 |
| 无 Resource-level 新语义身份 | `sha256` 只是派生值 + 索引，不是唯一键、不是实体 |
| 无 MOD→MOD 依赖图 / 版本实体 / 版本比较 | manifest 无依赖字段；`mods` 一行/ GUID |
| 无 Tags / Collections / Favorites / Review 状态 | 相关表零写入；`ui/` / `cli_query.py` 无相关入口 |
| `quick_hash` / `content_key` 保持 deprecated / unused | 全仓不写、不读、不删 |
| File ≡ Resource（1:1）未变 | `file_path_key UNIQUE` 未动 |

### 2.4 Phase 2 的实际语义边界（面向用户）

- `sha256` 相等 **只**表示**文件字节完全相同**（byte-identical）。
- 它**不**表示：同角色、同 MOD、同逻辑资源、同版本、同变体、视觉相同。
- 全部用户可见文案（CLI / GUI）都限定为「字节完全相同」。

---

## 3. Current Capability Gaps

> 排序依据：**从 Resource Manager 最终目标出发**（本地、可搜索、可分类、可关联、可人工修正），
> 不是简单功能罗列。

### 3.1 最终目标（来自 `README.md` / `docs/ARCHITECTURE.md` 的定位声明）

```text
本地、可搜索、可分类、可关联的 KKS 资源数据库；
角色 → 用了什么 MOD；MOD → 被谁使用；作者 → 发布了什么；
Collection → 包含什么；标签 → 对应什么；
位置与分类完全分离：打标签 / 加入 Collection 不移动文件、不改文件名。
```

### 3.2 缺口排序（G1 最大 → 越小越靠后）

| 排名 | 缺口 | 现状（代码事实） | 为什么排在这里 |
| :-- | :--- | :--- | :--- |
| **G1** | **用户组织层完全缺失** | `tags` / `resource_tags` / `collections` / `resource_collections` 四表零写入、零 Query API、零 CLI、零 GUI | 最终目标的一半（「可分类 / 可关联 / 标签 → 对应什么 / Collection → 包含什么」）完全没有实现载体；这是与「资源管理器」定位差距最大的一环 |
| **G2** | **「可人工修正」没有用户入口** | `type_source='user'` 会被重扫保留、`display_name` 会被重扫保护、`resources.notes` 列存在——但**没有任何写路径**能把它们设成 user 值 | 三条硬约束中的第三条目前只是「数据层预留」，不是能力；且组织层必然需要用户写路径 |
| **G3** | **没有写作/变异（mutation）架构** | 现有写路径只有：`LibraryStore`（库表）与 `Scanner/ResourceStore`（扫描入库）；没有面向「用户数据」的写服务 | 一旦引入组织/标注，就要引入第一类**持久用户数据**与其生命周期；这是架构问题，不是 UI 问题 |
| **G4** | **关系覆盖只到「使用事实」** | 可靠关系 = resource→mod(usage) / resource→plugin / resource→author；无 resource↔resource、无 MOD→MOD、无 author→MOD、无 collection | 「可关联」目前只是单向使用事实，不是任意端可查的关联网 |
| **G5** | **身份只有路径（+ MOD guid）** | `file_path_key` 全局唯一；改名/移动 = 新资源；旧行转 `missing` | 对真实使用者是硬伤：文件一移动，任何「组织/标注」都会与其脱钩（见 §13 风险） |
| **G6** | **无「候选关系 + 人工确认」原语** | `review_reasons` 是只读推导；`needs_review` 是布尔、每轮重扫被覆盖；无 confirm/dismiss 状态 | 任何「相似/同角色/重复确认」都依赖这一原语；没有它就只能自动建事实（本项目明确禁止） |
| **G7** | **GUI 只做 surfacing，不做 management** | GUI 写操作仅 Library add/enable/disable/remove + Scan；其余只读 | GUI 是否进入管理，取决于先有 domain model（见 §8） |
| **G8** | **跨库视图 / 多库语义未定** | `file_path_key` 跨库全局唯一；浏览恒限定所选 Library；`library_id` 是「最后扫到的库」 | 与组织层交互（组织是全局还是 per-library）未定 |
| **G9** | **性能 / 规模技术债（无证据）** | 作者 N+1、LIKE 全表扫描、`db.connect()` 无 `busy_timeout` | 无真实大库证据，优先级低于 G1–G6 |

**结论**：Phase 3 若要对齐「资源管理器」目标，第一位应解决 **G1（组织层）+ G2（人工修正入口）+ G3（写架构）**，
并明确 **G5（移动即失联）** 与 **G6（候选 + 确认）** 的处理边界；G7 是 G1–G3 的下游；
G8/G9 可后置或按证据触发。

---

## 4. Resource Identity Analysis

> 任务要求：分别说明 `file_path_key` / `sha256` / PNG 内部身份 / MOD GUID / 其它已有标识
> **各自能证明什么**，并区分 File / Content / Resource / Possible Family / Variant identity。
> 原则：**没有证据不引入新的语义身份**。

### 4.1 逐项分析

#### 4.1.1 `file_path_key`（归一化路径）

- **定义**：`normalize_path_key` = 展开 `~` → 绝对化 → 统一分隔符 → 去尾斜杠 → `casefold()`；
  `resources.file_path_key` 是 `TEXT NOT NULL UNIQUE`（**全局唯一，不含 library_id**）。
- **能证明**：「**该物理文件位于这个归一化路径**」。同一 key ⇒ 同一路径的同一文件；
  不同 key ⇒ 不同路径（即使内容相同，也是两条资源行）。
- **不能证明**：文件内容（改名/移动后 key 变化，内容未变也一样）；跨机器稳定性；软链接等价
  （`normalize_path_key` 刻意**不做** `Path.resolve()`）。
- **语义定位**：这是当前系统里 **Resource 的业务身份**，也是事实上的 **File identity**
  （因为 File ≡ Resource 1:1）。它本质是 **Path identity**。

#### 4.1.2 `sha256`（内容身份）

- **定义**：对整个文件**原始字节**做 SHA-256，64 位小写十六进制；`idx_resources_sha256` 存在
  （**索引，不是唯一键**）。
- **能证明**：`sha256(A) == sha256(B)` ⇒ **A 与 B 的字节完全相同**（byte-identical），
  且这是唯一被正式承认的等价判据（Phase 2 契约 D1/C4）。
- **不能证明**：同角色、同 MOD、同逻辑资源、同版本、同变体、视觉相似。
- **失效规则**：只由 `size` / `mtime` 变化或 `mode='full'` 触发重算；
  「同 size 同 mtime 但内容被替换」是**已知盲区**（Phase 1 既有增量门不变式）。
- **重要细微点**：`sha256` 覆盖**整个文件**（PNG 数据流 + 卡片尾部容器 + msgpack 数据区，
  含 `About.dataID`）。因此「两张图完全相同但 dataID 不同」的卡 **sha256 不同**。
  ⇒ 它**不是**「图片内容身份」，而是「**文件字节身份**」。

#### 4.1.3 PNG 内部身份 / 元数据

| 项 | 位置 | 能证明 | 不能证明 |
| :--- | :--- | :--- | :--- |
| `card_marker`（KoiKatuCharaSun / KoiKatuChara） | PNG 尾部容器头 | **卡片格式 / 游戏版本族**（KKS vs KK） | 身份（同一角色可有两个 marker；样本 Kugisaki 即 KKS+KK 两份） |
| `card_version` | 容器头 | 容器格式版本字符串 | 业务版本 / 变体 |
| `dataID`（About.dataID） | msgpack `About` | 仅 metadata；样本显示两卡只差 dataID | **不是身份**（每次保存可能变化，KK 卡甚至没有 `About`） |
| `userID`（About.userID） | msgpack `About` | 卡上的制作者 id（metadata） | 不是身份（KK 卡不可得） |
| `embedded_texture_count` | 数据区 PNG 签名计数 | 卡内嵌贴图**数量** | 贴图的类型 / 内容 / 归属（Phase 1 明确不解释） |
| `face_preview_kind` | 容器头 | 面部预览图格式（png/jpeg） | 身份 / 内容 |
| `block_sizes` / `lst_info` | 容器结构 | 结构诊断 | 身份 |

- **不存在**「PNG 像素身份」：系统**从未**对主图或任何内嵌贴图单独做哈希 / 感知哈希。
- **不存在**「卡片逻辑身份」：`dataID` 被明确定义为 metadata，不是身份（schema 注释 + 样本分析 J8）。

#### 4.1.4 MOD GUID

- **定义**：`mods.guid TEXT NOT NULL UNIQUE`，来自 zipmod 内 `manifest.xml`（属性式或子元素式）。
- **能证明**：**逻辑 MOD 身份**（同 GUID ⇒ 同一逻辑 MOD），与文件路径、版本、字节无关。
  真实样本 13 个 zipmod / 13 distinct guid（0 碰撞）。
- **不能证明**：同版本、同字节、同「变体」（variant）、同作者实体（`mods.author` 是自由文本，
  不与 `authors` 实体相连）。
- **已知后果（Phase 2 冻结）**：`mods` 一个 GUID 一行；同 GUID 多文件/多版本会**塌成一行**，
  后扫到的覆盖前者的 manifest 字段（无历史、无版本实体）。这是**产品语义**，不是缺陷。

#### 4.1.5 其它已有标识

| 标识 | 约束 | 能证明 | 边界 |
| :--- | :--- | :--- | :--- |
| `authors.name_key` | UNIQUE（trim + casefold） | **作者身份（弱）** | 无别名/外部 id；同人不同写法会分裂；`[Unknown]` 不建行 |
| `libraries.root_path_key` | UNIQUE | Library 身份（路径） | 改根路径 = 另一个 Library |
| `resource_plugins.plugin_guid` | 复合主键的一部分 | 插件**字符串键**（KKEx 键） | **无实体表、无版本、无来源** |
| `resources.file_size` / `modified_time` | 无 | 无（增量快捷门） | 不是身份；样本已证明同 size 可不同内容 |
| `resources.relative_path` | 无 | 无（展示 / 检索面） | 不是身份 |
| `metadata_json.*` | 无 | 无（宽松元数据） | 明确不作身份 |

### 4.2 四类身份的明确区分

| 身份类型 | 当前载体 | 稳定性 | 受路径变化影响 | 是否为「事实级」身份 |
| :--- | :--- | :--- | :--- | :--- |
| **File Identity** | `file_path_key`（= Resource 身份） | 路径稳定则稳定 | **是**（改名/移动 ⇒ 新 key） | 是（但只是「路径上的文件」） |
| **Content Identity** | `resources.sha256`（派生值 + 索引） | 内容不变则稳定 | 否 | 是（**仅** byte-identical） |
| **Resource Identity** | `file_path_key` | 同上 | **是** | 是（业务身份 = 路径） |
| **Possible Family / Variant Identity** | **无** | — | — | **否（当前不存在，且无数据源）** |

补充：对 zipmod 资源，**Logical MOD Identity（`mods.guid`）**是独立于上述四类的一条身份轴，
它属于「MOD 逻辑身份」，不是「资源族 / 变体」。

### 4.3 结论与纪律

1. 当前系统里**同时存在三条互不统属的身份轴**：路径（`file_path_key`）、内容（`sha256`）、
   逻辑 MOD（`mods.guid`）。它们服务不同问题，**不应被合并**。
2. **没有** Family / Variant identity；**任何**「同角色 / 同版本 / 同变体」都不是当前可证明的身份。
3. 若要引入新的语义身份，**必须先有数据源 + 真实样本 + 可验证判据**；
   本阶段**没有**找到这样的数据源（见 §6）。

---

## 5. Relationship Model Analysis

### 5.1 当前系统**能够可靠证明**的关系

| # | 关系 | 载体 | 数据来源 | 语义 |
| :-- | :--- | :--- | :--- | :--- |
| R1 | resource → MOD（**逐槽位使用**） | `resource_mod_usages`（PK resource_id + mod_guid + property） | 卡片 KKEx `com.bepis.sideloader.universalautoresolver` 的 info 记录 | **权威使用事实**：「这张卡在这个槽位用了这个 MOD」 |
| R2 | resource → MOD（**汇总**） | `resource_mods`（PK resource_id + mod_guid；`ref_count` = usage 行数；`relation` 恒 `'uses'`） | 由 R1 汇总（同事务先删后插） | 使用事实的汇总；含**未安装** MOD（`mod_id` 可空） |
| R3 | resource → plugin | `resource_plugins`（PK resource_id + plugin_guid） | 卡片 KKEx 键集合 | 插件 ≠ MOD（无 manifest） |
| R4 | resource → author（多作者） | `resource_authors` + `authors` | 卡片 KKEx `marco.authordata` | 多对多；`[Unknown]` 不建实体 |
| R5 | resource → library | `resources.library_id`（FK SET NULL） | Scanner 写入 | 一个资源至多属于一个库 |
| R6 | MOD → 自己的资源文件 | `mods.resource_id`（FK SET NULL） | zipmod 入库回填 | zipmod 文件那一行 `resources` |
| R7 | MOD → library | `mods.library_id`（FK SET NULL） | 扫描更新 | 随最后扫描更新 |
| R8 | **byte-duplicate** | 派生：`GROUP BY sha256`（**不落库**） | `resources.sha256` | 字节完全相同的资源组 |

**由 Query Layer 推导（不是 DB 事实，但口径稳定）**：
「缺失 MOD」（usage 引用但 `mods` 无对应行）、「孤立 MOD」、property 语义类别
（face/body/clothes/accessory/hair/makeup/unknown）、review reason、`has_missing_mods`、
资源行计数（mod/usage/plugin/author）。

### 5.2 当前系统**无法可靠证明**的关系（含任务特别关注项）

| 关系 | 能否证明 | 依据 |
| :--- | :--- | :--- |
| **`uses` ⇒ `requires` / dependency** | ❌ **不能** | 见 §5.3（专门分析） |
| MOD → MOD（依赖 / 前置 / 冲突） | ❌ 不能 | 无表、无列、无推导；manifest 无依赖字段 |
| resource → resource（非重复） | ❌ 不能 | 除 `duplicate_*`（预留、零写入）外无任何资源间关系 |
| **author → MOD（实体级）** | ❌ 不能 | `mods.author` 是自由文本，**不与 `authors` 实体相连**；`authors` 只关联 resources |
| plugin → MOD | ❌ 不能 | `resource_plugins` 只是字符串键，无插件实体、无关联 |
| plugin 实体（版本 / 来源） | ❌ 不能 | 无 `plugins` 表 |
| tag / collection → resource | ❌ 不能（未实现） | 四表存在但零写入、零 API |
| duplicate 确认组 / canonical / dismissed | ❌ 不能 | `duplicate_*` 零写入；能力是派生查询 |
| 同角色 / 同变体 / 同版本 | ❌ 不能 | 见 §6 |

### 5.3 专门检查：`uses` 是否能够证明 `requires` / dependency

**结论：不能。`uses` 与 `requires` 是语义不同的两类边，当前数据只能证明前者。**

证据链（逐层）：

1. **MOD 侧没有依赖声明**：`parse_manifest_xml` 的 `_MANIFEST_FIELDS = (guid, name, author,
   version, website)`——**没有** dependency / required / loadAfter 一类字段。
2. **同域参考实现也没有**：KKManager 的 `ModInfoBase` 字段只有
   guid / name / version / author / description / website / games（见 `PHASE2_0_B` §5.2）。
3. **`relation` 常量**：`resource_mods.relation` CHECK 允许 `uses|embeds`，但写入层**硬编码 `'uses'`**，
   `'embeds'` 全仓零写入（Phase 2 明确 KEEP 但不启用）。
4. **卡片引用的语义是「使用」不是「依赖」**：卡片 sideloader 表记录的是
   「这张卡在这个槽位引用了这个 ModID」；计数（样本 144 引用 / 13 已安装 / 134 缺失）
   全部是 **usage 语义**，不是依赖满足语义。
5. **契约已冻结**：`PHASE2_0_C` §7.1（Q-D1）= **NO**；§13.8 X3 =
   「无 MOD→MOD 边；缺失 MOD 只表示 referenced-but-not-installed，从不表示 dependency unsatisfied」。

因此：**不得**因为「概念上合理」就把 usage 升级为 dependency；**不得**建立没有数据源的依赖图。

### 5.4 关系模型结论

- 唯一可靠的跨实体边是 **R1/R2（资源使用 MOD）**；它是本系统最有价值的既有关系资产。
- 「缺失 MOD」是 usage 的补集，**不是**依赖问题。
- 组织层（tag/collection）与候选关系（similar/variant）若要进入 Phase 3，
  必须**新建**语义，并明确「DB 事实 / 派生候选 / 用户确认」三种状态（见 §7 / §10）。

---

## 6. Variant / Similarity Feasibility

> 任务要求：调查 same resource / version / variant / same character / visual similarity /
> semantic similarity 是否存在足够数据支撑，并按**证据强弱**分级。

### 6.1 证据分级

#### Tier 1 — 可证明的事实（当前即可用）

| 关系 | 判据 | 可靠性 | 样本证据 |
| :--- | :--- | :--- | :--- |
| **byte-identical（同内容副本）** | `sha256` 相等 | 高（字节完全相同） | 1 组：Kugisaki KKS ×2（不同目录，同 sha256 `ee44ba20…`，同 dataID） |
| **same logical MOD** | `guid` 相等 | 高（manifest 声明） | 13 zipmod / 13 distinct guid，样本 0 例重复 |

#### Tier 2 — 只能作为**候选**（必须人工确认，不能建为事实）

| 候选 | 判据 | 为什么只是候选 |
| :--- | :--- | :--- |
| 同一文件被改名/移动 | 内容 `sha256` 相同 + 一条 `missing` 行 | 当前**不做移动检测**；改名/移动一律是「新行 + 旧行 missing」；用 sha256 反推移动是**未来候选能力**，非现状 |
| 同大小 | `file_size` 相等 | **样本反例**：两张 HigashiyamaKobeni 同为 481,250 B，sha256 不同 |
| 同名 | `name` / `display_name` 相等 | **样本反例**：3 张不同 HigashiyamaKobeni 同名；文件名冲突（`KK_317794.png`） |
| 同作者 + 同名 | `resource_authors` + `name` 相等 | 仍非身份（同名卡可同作者）；只能作候选 |
| 同 marker + 同名 | `card_marker` + `name` | 同上；且 marker 只是格式 |

#### Tier 3 — NOT DETECTABLE WITH CURRENT EVIDENCE（当前不可计算）

| 关系 | 样本证据（存在但不可算） | 为什么不可算 |
| :--- | :--- | :--- |
| **same character / re-export** | HigashiyamaKobeni ×2：同 481,250 B、**不同 sha256、不同 dataID** | 无稳定判据；dataID 每次保存可能变；无内容归一化摘要 |
| **same character / 跨格式** | Kugisaki：KKS `ee44ba20…` vs KK `87436741…`（KK 卡无 `About`） | 格式不同、字节不同，无判据 |
| **version（作为变体关系）** | `mods.version` 是自由字符串（样本含 `"0"`） | 无比较语义；同 GUID 不共存多版本；卡片无版本概念 |
| **variant / family** | 无任何样本定义 | **没有数据源** |
| **visual similarity（感知哈希）** | 未尝试 | 需图像提取 + 感知哈希模型；`PHASE2_0_B` §9 明确 KKS 重复问题不是「长得像」；且本片 sha256 含尾部 dataID，视觉相同≠文件相同 |
| **semantic similarity** | 未尝试 | 无本地模型；引入 AI / 网络违反硬约束 |

### 6.2 结论与强制要求

1. **只有 Tier 1 可以自动建为事实**：byte-identical（已有）+ same GUID（已由 MOD 身份表达）。
2. **Tier 2 一律只能作为「候选关系」**，且必须走**人工确认**（review / confirm / dismiss），
   在确认前**不得**进入任何「事实」视图或统计。
3. **Tier 3 不进入 Phase 3 的自动能力**；若需要，只能作为用户**手工**关联（如 tag / collection），
   或作为未来有真实数据源时的独立立项。
4. 任何候选判据都必须写明**数据来源 + 可验证性**；没有来源的候选不得实现。

---

## 7. Organization Model Candidate

> 任务要求：评估 Tags / Collections / Favorites / Review State / User Notes & Curation
> 是否适合进入 Phase 3；并确认 **Organization 应首先是数据库层的虚拟组织，而不是文件系统操作**。

### 7.1 先确认结论

```text
Organization 必须是数据库层的虚拟组织：只写数据库行，锚定 resources.id；
绝不 move / rename / delete / 改写用户文件，也不改文件名或目录结构。
```

依据：`README.md` 硬约束「位置与分类分离」；`docs/ARCHITECTURE.md` §2「打标签/加入 Collection
不移动文件」；`schema.py` 注释「Collection 与文件目录结构完全分离」；
`constants`: `core/` 与 `ui/` 中不存在 `os.remove/rename`、`shutil.move/rmtree`（Phase 2.0-A §10.1 已核查）。

### 7.2 逐项评估

| 能力 | 现有 schema | 是否适合 Phase 3 | 需要新建什么 | 关键约束 |
| :--- | :--- | :--- | :--- | :--- |
| **Tags** | `tags`（name_key UNIQUE、color、category）+ `resource_tags`（origin user/auto） | ✅ 适合（**首选**） | core 写服务（create/rename/delete tag、assign/unassign）、Query 投影、CLI/GUI 入口 | 只作为 DB 行；`origin='auto'` 保留但**不得**自动打标 |
| **Collections** | `collections`（name_key UNIQUE、description、sort_order）+ `resource_collections`（sort_order） | ✅ 适合 | 同上（collection CRUD + 成员管理） | 与目录结构无关；不移动文件 |
| **Favorites** | **无专用表** | ⚠️ 适合但需先定表示 | 建议**复用** tag 或 collection，**不要**新加 `favorites` 表 | 避免同一语义两套载体；无样本需求支撑新建表 |
| **Review State** | `resources.needs_review`（布尔，重扫会覆盖） | ⚠️ 条件性适合 | 若要持久化 confirm/dismiss ⇒ 需要 schema（候选 v3）；仅「展示 review reason」则无需 | `needs_review` 现在**不能承载人工结论**；review reason 仍是只读推导 |
| **User Notes / Curation** | `resources.notes`（列存在、无写路径）；`display_name`（列存在、无写路径） | ✅ 适合 | core 写服务（set notes / set display_name / 手工改 type_source='user'） | 需与重扫保护规则对齐（现有 store 已保护 user 值） |

### 7.3 适合进入 Phase 3 的理由

1. **表结构大多已存在**（tags/collections），不需要为了组织而必然升级 schema；
2. 全部可锚定 **`resources.id`**（稳定代理键），**不依赖**新的语义身份；
3. **不需要 AI / 网络 / 自动语义判断**；
4. **不触碰用户文件**（保持三条硬约束）；
5. 直接补齐最终目标缺口 G1/G2（§3.2）；
6. 是「可人工修正」这条硬约束的**唯一**实现路径。

### 7.4 进入 Phase 3 必须正视的代价

- 这是本项目**第一次引入持久化的用户写数据**（更早只有 Library 记录与扫描入库）；
  需要定义**变异语义**：创建 / 重命名 / 删除 / 幂等 / 冲突 / 事务边界。
- 需要定义**组织的稳定性**：组织锚定 `resources.id`，但**文件移动会产生新 id**（§13 风险）。
- 需要定义**多库语义**：组织是全局还是 per-library（现状 `file_path_key` 全局唯一）。
- Favorites 的表示必须先定一种，避免 tag 与 collection 双轨。

---

## 8. Resource Manager GUI Candidate

> 任务要求：评估 Phase 3 是否应从 Phase 2 的 read-only surfacing 进入真正的 management workflow；
> 明确哪些 GUI 操作需要先有稳定 domain model，哪些可以后置。

### 8.1 GUI 现状（代码事实）

| 能力 | 现状 | 通道 |
| :--- | :--- | :--- |
| 只读浏览（Library / 资源网格 / 搜索 / 筛选 / 排序 / 详情 / 关系反查） | ✅ 已完成 | `GUI → BrowseService → Query Layer → DTO` |
| Library 管理（Add / Enable / Disable / Remove） | ✅ 已完成 | `GUI → core.app.LibraryAdminService → LibraryStore` |
| 扫描（增量 / 全量，后台 worker） | ✅ 已完成 | `GUI → ScanWorker → core.app.run_scan → LibraryScanner` |
| 缩略图 | ✅ 已完成 | `GUI → PreviewWorker → PreviewService`（只写缓存） |
| **Tags / Collections / Favorites / Notes / Review 管理** | ❌ 完全没有 | — |
| 文件操作（移动 / 删除 / 批量） | ❌ 完全没有（且属 Phase 5 / 禁区） | — |

架构护栏（有静态测试守护）：`ui/` 不 import `sqlite3` / `*Query` 类；写只经 `core.app` 服务；
读只经 `BrowseService`；GUI 不维护第二份资源状态。

### 8.2 「先有稳定 domain model 才能做 GUI」的操作（必须先做 core）

| GUI 操作 | 依赖的 domain model / 写服务 | 为什么不能先做 GUI |
| :--- | :--- | :--- |
| 打标签 / 去标签 | tag 实体 + `resource_tags` 写服务 + 幂等语义 | 否则 GUI 会自己拼 SQL / 业务规则，破坏 ui→core 单向 |
| 加入 / 移出 Collection | collection + `resource_collections` 写服务 | 同上 |
| 收藏（Favorite） | 先定「tag 或 collection」的**唯一**表示 | 表示未定则 GUI 无从绑定 |
| 编辑备注 / 显示名 | `resources.notes` / `display_name` 写服务 + 重扫保护规则 | 现有保护逻辑在 store 内，GUI 不能复制 |
| 人工确认类型 | `type_source='user'` 写服务 | 同上 |
| Review 确认 / 忽略 | 持久 review state（可能需 schema） | 没有持久状态则「确认」无处存放 |
| 重复组确认 / 保留项 | 持久 duplicate 组（可用预留表）或明确不做 | canonical / dismiss 目前无载体 |

### 8.3 可以后置的 GUI 项

- 跨库全局视图（P2.1）、`scan_status` 筛选（P2.2）、orphan MOD 视图（P2.3，CLI 已有、GUI 未接线）；
- 更大规模的批量编辑 / 批量打标（需要先有单元写服务）；
- 高级统计 / 仪表盘；可持久化 UI 状态（属 non-goal）。

### 8.4 结论（候选）

> **Phase 3 可以进入 management workflow，但 GUI 必须是「消费者」，不是「定义者」。**
> 顺序应为：**domain model + core 写服务 → Query/投影 → CLI 或 GUI 入口**。
> 在写服务冻结前，**不应**开始任何管理类 GUI 控件实现。
> 文件系统操作（移动/删除/批量）保持 Phase 5 / 禁区，不进入 Phase 3。

---

## 9. External Ecosystem Findings

> 仓库已有外部研究：`docs/phase2/PHASE2_0_B_RESEARCH.md`（14 个项目，附来源链接）。
> 本节在其基础上聚焦回答任务的 5 个问题，并补充一次只读核对（KKManager README）。
> 目标**不是**复制功能列表，而是判断「解决什么问题 / 依赖什么数据源 / 是否适配 / 是否冲突 / 是否需要重新建模」。

### 9.1 KKManager（同域，最重要）

- **解决的问题**：浏览已安装 zipmod 与插件并查看信息；浏览卡片与场景；**自动从互联网查找并安装更新**；
  安装插件 / mod；修复部分常见问题。（README 实测文本）
- **数据源**：本地游戏目录 + zipmod `manifest.xml` + 在线更新服务器。
- **适合本项目**：以 `Guid` 作为 mod 逻辑键（本项目已一致）；卡片浏览；「已安装 / 缺失」的区分。
- **与本地优先定位冲突**：在线更新 / 下载；安装进游戏目录；**删除/清理重复文件**（默认只读禁止）。
- **值得借鉴但需重新建模**：同 GUID 归组的概念——本项目保留「一行/GUID」，但**不删除**任何文件、
  不建立版本实体（Phase 2 已冻结）。

### 9.2 KKTools（MIT，卡片解析内核）

- **解决的问题**：KKS/KK 卡片（PNG 尾部 MessagePack）解析；PyQt6 `QThread` 后台任务模式。
- **数据源**：卡片文件字节。
- **适合**：解析正确性 + worker 模式（本项目已参考/复用，见 `THIRD_PARTY.md`）。
- **冲突**：无（它是解析库，不是管理器）。
- **重新建模**：无（沿用）。

### 9.3 IllusionMods / BepInEx / Sideloader 生态

- **解决的问题**：解释 KKS/KK 的 zipmod 生态运行方式——zipmod 由 BepInEx + Sideloader 加载，
  `manifest.xml` 是元数据源，卡片 KKEx 的 auto-resolver 记录是「使用」来源。
- **适合本项目**：确认「usage 来源」与「MOD 元数据来源」是**两个不同数据源**，二者都不含依赖声明。
- **冲突**：无（仅生态背景）。
- **重新建模**：把「卡片使用了哪些 MOD」与「MOD 需要哪些 MOD」严格分开（本项目已如此）。

### 9.4 依赖型管理器（CKAN / Fabric / Vortex / MO2 / r2modman）

- **解决的问题**：安装 / 卸载 / 启用 / profile / 冲突 / load order / **依赖解析与版本约束**。
- **数据源**：**中央元数据库**（CKAN）或 mod 自带**显式依赖声明**（Fabric `fabric.mod.json`）
  或在线包中心（Thunderstore / Nexus）。KKS zipmod **没有**等价依赖字段。
- **适合本项目**：`depends / conflicts / provides` 的**词汇表**可作命名参考；profile 的「一组启用项」
  概念可映射为 **Collection**（虚拟组织）。
- **冲突**：依赖求解 / 版本约束 / install-to-game / VFS / load order——本项目不安装、不联网、无数据源。
- **重新建模**：**不建模**依赖图（无数据源）；profile → 重新建模为 DB 虚拟 Collection。

### 9.5 资产库 / 媒体库（PhotoPrism / Immich / Hydrus / beets）

- **解决的问题**：资产的组织 / 浏览 / 标签 / 相册 / 去重 / 相似。
- **数据源**：文件 + EXIF/sidecar（PhotoPrism/Immich）；内容哈希 + **感知哈希**（Hydrus）；
  在线元数据（beets / MusicBrainz）。
- **适合本项目**：**用户组织层**（标签 / 相册）与 identity 线正交——本项目表结构已预留；
  Hydrus 的「**potential duplicates → confirmed duplicates vs alternates**、每组一个 king」
  是「候选 + 人工确认」的最佳概念参考。
- **冲突**：多用户 / 云同步（Immich）；在线元数据（beets）；AI 标注（PhotoPrism）；
  感知哈希（Hydrus）——KKS 的重复问题不是「长得像」。
- **重新建模**：1:N（Photo/Asset ↔ File）只有在**真实 1:N 样本**出现时才考虑
  （Phase 2 已判定当前无样本，File ≡ Resource 保持）。

### 9.6 重复文件工具（fdupes / rmlint / czkawka / restic）

- **解决的问题**：判定重复并**回收磁盘空间**（fdupes 漏斗：size → 摘要 → 逐字节；rmlint paranoia；
  czkawka 多模式；restic 内容寻址存储）。
- **数据源**：文件字节。
- **适合本项目**：漏斗判定的思路（本项目已用 sha256 一步到位）；rmlint 的缓存/重放思路对大规模扫描有参考价值。
- **冲突**：**删除 / 清理**导向；restic 的存储层复杂度。
- **重新建模**：只保留「判定」，服务用户**确认后可整理**（但删除属 Phase 5，且需 Preview/Confirm/Undo）。

### 9.7 对任务 5 个问题的直接回答

| 问题 | 回答 |
| :--- | :--- |
| 1. 它们解决了什么问题？ | 已安装/可安装 mod 的清单与更新（KKManager/通用管理器）；依赖求解（CKAN/Fabric）；资产组织与相似/重复（媒体库/重复工具） |
| 2. 依赖什么数据源？ | 本地游戏目录 + manifest.xml + 卡片 KKEx（KKS）；在线服务器/中央仓库（KKManager/CKAN/Thunderstore/Nexus）；显式依赖声明（Fabric）；文件字节（重复工具）；EXIF/sidecar/在线元数据（媒体库） |
| 3. 哪些能力适合本项目？ | GUID 逻辑身份（已有）、卡片解析（已用）、usage 事实（已有）、「usage≠dependency」的区分（已有）、「suggested→confirmed」重复概念、用户组织层（标签/相册）、profile→Collection 的映射 |
| 4. 哪些与 Local-first Resource Manager 冲突？ | 网络更新/下载、安装进游戏目录、VFS/load order、文件删除/移动、云同步/多用户、AI 标注、感知哈希 |
| 5. 哪些值得借鉴但需重新建模？ | 依赖图（无数据源 ⇒ 不做）、duplicate 确认（在派生 byte 组之上加用户确认状态）、1:N File/Asset（无样本 ⇒ 不拆）、profile（→ DB 虚拟 Collection）、version（→ 仅 metadata，不作身份/比较） |

### 9.8 关于早期 roadmap 的漂移（重要）

`README.md` / `docs/ARCHITECTURE.md` 的路线图仍写：

```text
Phase 2 = MOD 索引 + GUID + 依赖关系      （与实际 Phase 2 不符）
Phase 3 = 分类 + 标签 + 作者 + Collection   （早期设想，已被 Phase 2 实践改写）
Phase 4 = 重复检测 + 资源关系               （实际字节重复已在 Phase 2 完成）
```

这是**已知文档漂移**（Phase 2.2 / 2.3 / 2.4 报告中均已登记为非阻塞）。
因此：**不得**把「Phase 3 = Tags/Collections」当作既有 Contract；
它只是一个**候选**，需要在本阶段重新论证（本报告 §7 已给出支持与代价）。

---

## 10. Candidate Phase 3 Architecture

> 以下是**候选架构**，不是冻结设计。目的是给出「若做资源管理，架构上必须回答什么」。

### 10.1 架构原则（沿用并强化既有纪律）

1. 证据驱动：没有数据源 / 没有真实样本支持的模型**不实现**；
2. 本地优先：运行时零网络、零云 AI；
3. 默认只读用户文件：扫描 / 解析 / 组织**绝不** move / rename / delete / 改写用户文件；
4. 位置与分类分离：组织 = DB 虚拟组织；
5. 人工优先：自动只写「可可靠确认」的结论，其余落候选 / 待确认；
6. 分层单向：`ui → core`；写经 `core.app` 服务；读经 Query / Browse；`ui` 无 SQL；
7. schema 只追加：任何 DDL 变更都必须新增版本，不改历史迁移；
8. 不引入通用 Entity/Relation 抽象（除非证据证明必要）。

### 10.2 候选能力支柱（候选，不预设优先级顺序）

| 支柱 | 内容 | 语义状态 | 依赖 |
| :--- | :--- | :--- | :--- |
| **P1 用户组织（DB 虚拟）** | Tags / Collections / Favorites（复用表示）/ Notes / display_name / 手工类型 | **用户事实** | 写服务 + `resources.id` 锚点 |
| **P2 策展 / Review** | 持久 review state（pending/confirmed/dismissed）+ 现存 review reason 展示 | 混合：state=用户事实，reason=派生 | 可能需 schema v3 |
| **P3 候选关系（只读候选 + 人工确认）** | 仅在有判据处：byte 重复确认（dismiss/canonical，可用预留表）、同 GUID、未来同 size+name 候选 | **候选**（确认前不是事实） | 确认语义载体 |
| **P4 写 / 服务层** | 对称于 `LibraryAdminService` 的薄写服务（如 `TagService` / `CollectionService` / `CurationService`） | 架构 | 变异语义 |
| **P5 组织投影 / 浏览** | 按 tag/collection/favorite 过滤、分组视图、计数 | 派生视图 | P1/P4 |

### 10.3 关键架构分叉（必须由正式 Contract 决定，不在本报告决定）

| 分叉 | 选项 A | 选项 B | 影响 |
| :--- | :--- | :--- | :--- |
| **Schema** | **v2 中立**：只用现有 tags/collections/notes/display_name + 预留 duplicate 表 | **需要 v3**：持久 review state（confirm/dismiss）等 | 决定是否需要新 migration 阶段 |
| **表示** | Favorite = 一个 tag 或一个系统 Collection | 新建 `favorites` 表 | 避免同一语义双轨 |
| **入口** | core 写服务 + CLI 先行 | core 写服务 + GUI 先行 | 影响验收方式与回归面 |
| **组织范围** | 全局（与 `file_path_key` 全局唯一一致） | per-library | 影响多库语义 |
| **移动即失联** | 接受（改名 = 新资源，组织脱钩） | 用内容身份检测「移动」（候选能力） | 影响组织数据长期可用性 |
| **候选关系** | 只做 byte 重复确认 | 扩展到同 size+name 候选 | 影响「候选 + 确认」范围 |

### 10.4 明确**不进入**候选架构的东西

新语义身份键；MOD Version 实体 / 版本比较；MOD→MOD 依赖图；1:N File/Resource 拆分；
通用 Entity/Relation 表；same-character / visual / semantic similarity 事实；
自动打标 / 自动整理 / 自动删除；网络 / 下载 / watcher / 云同步。

---

## 11. Candidate Phase 3 Work Breakdown

> ⚠️ **本节不决定 Phase 3.1 / 3.2 / 3.3 的最终内容**，只给出**候选工作流 + 依据 + 依赖**。
> 正式拆分必须由下一份 Contract 冻结。

### 11.1 候选工作流（每项都可独立验收）

| 候选 ID | 内容 | 是否需 schema | 证据 / 依据 | 前置依赖 |
| :--- | :--- | :--- | :--- | :--- |
| **C0** | Phase 3.0 Architecture / Scope Contract（形式化本报告） | 否 | 本文件 | — |
| **C1** | 组织写服务基础：tag/collection CRUD + 成员 assign/unassign（幂等、事务） | 否（用现有表） | tags/collections 表已存在 | C0 决定表示与入口 |
| **C2** | 组织读取 / 浏览投影：按 tag/collection/favorite 过滤 + 计数 + BrowseScope 扩展 | 否 | Query 层已有筛选模式 | C1 |
| **C3** | Favorite 的单一表示（tag 或系统 collection） | 否 | 避免双轨 | C0 先定表示 |
| **C4** | 用户备注 / display_name / 手工类型（激活「可人工修正」） | 否（列已存在） | `resources.notes/display_name/type_source` 已存在且 store 已保护 user 值 | C1 的写服务模式 |
| **C5** | Review / 策展状态（pending/confirmed/dismissed） | **可能需 v3** | `needs_review` 每轮重扫被覆盖，无法承载人工结论 | C0 决定是否做持久状态 |
| **C6** | 重复组确认（dismiss / canonical），基于派生 byte 组 | 否（可用 `duplicate_groups/members` 预留表） | 预留表自 v1 存在、零写入；Hydrus 的 suggested→confirmed 概念 | C0 决定是否纳入 |
| **C7** | GUI 管理入口（消费 C1–C4 服务） | 否 | GUI 只做消费者 | C1–C4 冻结 |
| **C8** | 候选关系（同 size+name / 同 GUID 提示），仅候选 + 确认 | 否 / 需确认载体 | Tier 2 判据（§6） | C5/C6 的确认语义 |

### 11.2 候选排序逻辑（给出依据，不强行定序）

- **必须先**：C0（Contract）——否则任何实现都可能重蹈「为完整而加功能」。
- **schema 中立优先**：C1/C2/C3/C4 可在 v2 内完成（不动 schema），风险最低。
- **写服务先于 GUI**：C7 依赖 C1–C4；否则 GUI 会承担业务规则，破坏分层。
- **schema 变更单独决策**：C5（review state）与「C6 若需持久化」是唯一的 schema 风险点，
  应作为**独立分叉**评审，不与组织功能捆绑。
- **候选关系最后**：C8 依赖「候选 + 确认」原语；在确认语义未定义前不得实现。

### 11.3 本报告**不**给出的东西

- 不指定 3.1 / 3.2 / 3.3 的编号与切分；
- 不指定必须先做 CLI 还是 GUI；
- 不指定 Favorite 用 tag 还是 collection；
- 不指定是否引入 v3；
- 不写任何 SQL / DDL / API 签名。

---

## 12. Explicit OUT OF SCOPE

> 以下为**建议**写入 Phase 3 Contract 的 OUT OF SCOPE（本报告不代为冻结，但给出依据）。

| # | OUT OF SCOPE 项 | 依据 |
| :-- | :--- | :--- |
| 1 | 文件系统操作：move / rename / delete / 改写用户文件 | 「默认只读」硬约束；删除属 Phase 5（Preview/Confirm/Undo） |
| 2 | 自动文件整理 / 自动重命名 / 自动分类 | 硬约束 + 无证据 |
| 3 | AI 分类 / 语义判断 / 云端 API | 「本地优先 + 禁止云端 AI」 |
| 4 | 网络：下载 / 更新 / 在线元数据 / 云同步 / 多用户 | 「本地优先、零网络」；单机单用户定位 |
| 5 | filesystem watcher / 自动扫描 / 自动刷新 | Phase 1.5-D 明确定义为需真实证据驱动的禁区 |
| 6 | 新语义身份键（Family / Variant / logical-resource id） | 无数据源、无样本（§4/§6） |
| 7 | MOD Version 实体 / 多版本共存 / 版本比较 | manifest version 自由字符串；样本 0 例（Phase 2 冻结） |
| 8 | MOD→MOD 依赖图 / 版本约束求解 | manifest 无依赖字段；无数据源（§5.3） |
| 9 | 1:N File/Resource 拆分 / `files` 表 | 无 1:N 真实样本（Phase 2 §4 冻结） |
| 10 | 通用 Entity / Relation 抽象表 | 证据不支持 |
| 11 | same-character / visual / semantic similarity **事实** | NOT DETECTABLE WITH CURRENT EVIDENCE（§6） |
| 12 | 自动打标 / 自动 Collection 分配 | 与「人工确认优先」冲突 |
| 13 | 自动删除重复 / 批量文件操作 | 硬约束 + Phase 5 |
| 14 | 将「缺失 MOD」解释为依赖不满足 | §5.3 |
| 15 | 把早期 roadmap（Phase 3 = 标签+分类）自动升级为 Contract | §9.8 文档漂移 |
| 16 | `quick_hash` / `content_key` 的清理 / 启用 | Phase 2 已定为 deprecated / unused；清理属独立 schema cleanup 阶段 |

---

## 13. Risks / Unknowns

### 13.1 高风险（会影响 Phase 3 是否成立）

| # | 风险 | 说明 | 缓解建议 |
| :-- | :--- | :--- | :--- |
| R1 | **没有真实组织需求证据** | 持久工作库 0 资源；真实样本是只读测试夹具（36 文件 / 1 库）；tags/collections 目前**零使用** | 在冻结 Contract 前收集最低限度的真实使用信号；避免仅凭「表已存在」就实现 |
| R2 | **文件移动 ⇒ 组织脱钩** | 组织锚定 `resources.id`；改名/移动 = 新 id ⇒ 旧行的标签/Collection 不跟随 | 明确接受或定义「移动检测」候选能力（可借内容身份），并写进 Contract |
| R3 | **首次引入持久用户数据** | 之前没有用户组织写入；变异语义（创建/重命名/删除/幂等/冲突）未定义 | 先冻结写服务语义，再谈 GUI |
| R4 | **schema 分叉不明** | v2 中立可做 tags/collections/notes；持久 review / 重复确认可能需 v3 | 把 schema 决策作为独立分叉评审，不捆绑 |
| R5 | **「候选关系」边界失控** | Tier 2 判据弱（同 size 有反例、同名有反例） | 强制「候选 ≠ 事实」，确认前不进统计/事实视图 |

### 13.2 中等风险

| # | 风险 | 说明 |
| :-- | :--- | :--- |
| R6 | 多库语义未定（`file_path_key` 跨库全局唯一；组织范围未定） | 组织是全局还是 per-library 未决定 |
| R7 | 写并发 / `busy_timeout` 缺失 | 首次出现「用户写 + 扫描写」并发；单扫描策略目前掩盖了它 |
| R8 | 文档漂移误导 | README/ARCHITECTURE 路线图与实际 Phase 2 不符，可能诱导错误 Contract |
| R9 | GUI 边界侵蚀 | 管理类 GUI 若先于写服务，容易把业务规则塞进 UI |
| R10 | `duplicate_groups/members` 若启用，需定义生命周期 | 资源消失 / 内容变化时的组维护规则 |
| R11 | `_RESOURCE_SUMMARY_COLUMNS` 已含 `r.sha256`，`duplicates()` 再选一次同名列 | Phase 2.3 已评估为「低 / 已消解」（按名取首列、值相同）；新代码勿假设唯一列名 |

### 13.3 数据 / 证据缺口（沿用 Phase 1–2 已知项）

- 无加密 zipmod 样本；无「同 GUID 多版本」样本；无「同一文件移动后重扫」样本；
- 无「同一角色两次保存」实验（dataID 是否变仅有间接证据）；
- 无多库重叠样本；无独立存在的眼睛/皮肤贴图文件样本；无头发槽位样本；无 >7 套服装样本；
- 无真实大规模库（性能与哈希策略缺少基准）。

### 13.4 未知（需在 Contract 前回答）

1. Phase 3 的**唯一主目标**是「用户组织」还是「策展/确认」还是两者并行？
2. Favorite 的表示是什么？组织范围是全局还是 per-library？
3. 是否引入持久 review state（⇒ v3）？
4. 是否启用预留的 `duplicate_groups/members`（⇒ 持久重复确认）？
5. 「文件移动 ⇒ 组织脱钩」是接受还是处理？

---

## 14. Recommended Phase 3 Acceptance Boundaries

> 建议写入正式 Phase 3 Contract 的验收边界（方案级，不含实现细节）。

1. **文件系统不变量不变**：Scanner / Parser / GUI / 写服务在任何情况下都**不** move / rename /
   delete / 改写用户文件；唯一允许的文件写入是派生缓存 `data/thumbnail_cache/`。
2. **本地优先不变**：运行时零网络、零云 AI；不新增网络依赖。
3. **语义分级强制**：所有新关系/结论必须标注为
   「**DB 事实**」、「**派生候选**」或「**用户确认**」之一；候选在确认前不得进入事实视图/统计。
4. **组织 = DB 虚拟组织**：tag / collection / favorite / notes 一律只写数据库，锚定 `resources.id`，不动文件。
5. **schema 只按需追加**：能落在既有表（tags/collections/notes/display_name/预留 duplicate 表）的，
   不新增 schema；确需新增时，遵循「只追加 migration + `MIGRATION_ADDED_COLUMNS` 幂等加列」规则。
6. **分层单向保持**：`ui → core`；写经 `core.app` 服务；读经 Query/Browse；`ui` 无 `sqlite3`、无 `*Query`、
   无 SQL。新增管理功能必须复用该边界。
7. **向后兼容**：既有 Query DTO / CLI JSON 字段只增不改语义；schema v2 既有语义不得回改。
8. **确定性 / 幂等**：组织写操作（创建 / 删除 / assign / unassign）必须确定性、可重复执行、
   可安全重试；冲突有明确语义。
9. **回归**：现有 **734 passed** 不得减少 / 削弱；新增能力必须有 focused 测试；
   真实样本 `tests/conftest.py::sample_root` 会话级 sha256 前后一致的只读不变量必须继续成立。
10. **独立验收**：每个子阶段必须独立可验收（实现 → 测试 → 无回归 → 更新文档 → 才进下一步），
    不得把多个能力打包成一个不可分割的大阶段。
11. **Contract 冻结门**：在正式 Phase 3 Architecture / Scope Contract 冻结前，
    **不得进入任何 Phase 3.x 实现**（本报告 §11 只是候选）。

---

## 15. Recommended Next Step

> 本报告**不**启动 Phase 3.1。下一步是产出一份**正式的 Phase 3.0 Architecture / Scope Contract**，
> 由该 Contract 冻结 Phase 3 的范围与拆分。

建议该 Contract 至少回答并冻结以下决策：

1. **唯一主目标**：Phase 3 是否以「用户组织层（G1）+ 人工修正入口（G2）+ 写架构（G3）」为核心？
2. **Schema 分叉**：v2 中立（tags/collections/notes）还是需要 v3（持久 review / 重复确认）？
3. **表示决策**：Favorite 用 tag 还是系统 collection？组织范围全局还是 per-library？
4. **写服务架构**：`core.app` 薄写服务的职责边界、变异语义（创建/重命名/删除/幂等/事务）。
5. **移动即失联**：接受，还是把「基于内容身份的移动检测」列为候选？
6. **候选关系策略**：只做 byte 重复确认，还是扩展到 Tier 2（同 size+name）候选？确认的持久化载体是什么？
7. **入口顺序**：core 写服务 → CLI / GUI 的先后。
8. **OUT OF SCOPE 冻结**：采用本报告 §12（或经评审修正后的版本）。
9. **验收边界冻结**：采用本报告 §14。

建议同时补充一件**真实证据**：在冻结组织功能范围前，取得最低限度的真实使用信号
（用户自己库中的组织诉求），以避免重蹈「为完整而加功能」。

```text
下一步 = 编写并冻结 Phase 3.0 Architecture / Scope Contract；
在该 Contract 冻结前，不进入 Phase 3.x 实现。
```

---

## 附录 A — 任务问题 A–H 的答案索引

| 任务问题 | 本报告位置 | 摘要 |
| :--- | :--- | :--- |
| **A. Phase 2 真正建立了什么能力** | §2 | 内容身份（sha256 写入 + C7）+ 字节重复派生查询 + Query/CLI/GUI 只读暴露；无 schema/无持久化/无新语义身份 |
| **B. 当前最大能力缺口** | §3 | G1 用户组织层缺失 → G2 人工修正无入口 → G3 无写架构 → G4 关系只到 usage → … |
| **C. Resource Identity** | §4 | 路径=File/Resource 身份；sha256=内容身份（仅 byte）；GUID=MOD 逻辑身份；Family/Variant 不存在且无数据源 |
| **D. Resource Relationship** | §5 | 可靠：resource→mod(usage)/plugin/author、mod→file、library；`uses` **不能**证明 `requires`；MOD→MOD / author→MOD / resource↔resource 均不可证明 |
| **E. Variant / Similarity** | §6 | Tier1 可证明（byte / GUID）；Tier2 仅候选（同 size/同名，有反例）；Tier3 不可算（同角色/版本/变体/视觉/语义） |
| **F. Organization** | §7 | Tags/Collections/Notes 适合且表已存在；Favorites 需先定表示；Review State 可能需 schema；**组织必须是 DB 虚拟组织** |
| **G. Resource Manager GUI** | §8 | 可进入 management，但 GUI 必须是消费者；先 domain model + 写服务，文件操作后置/禁区 |
| **H. 外部项目借鉴** | §9 | KKManager/KKTools/IllusionMods 生态 + 依赖型 + 资产库 + 重复工具；解决什么问题/数据源/适配/冲突/需重新建模逐项回答 |

## 附录 B — 本阶段禁止事项核对

| 禁止项 | 状态 |
| :--- | :--- |
| 修改代码 | ✅ 未做（仅新增本报告） |
| 修改 schema | ✅ 未做（`SCHEMA_VERSION == 2` 未动） |
| 修改 migration | ✅ 未做 |
| 修改测试 | ✅ 未做 |
| 创建 commit | ✅ 未做 |
| 创建 tag | ✅ 未做 |
| 决定 Phase 3.1 / 3.2 / 3.3 最终内容 | ✅ 未做（§11 仅候选） |
| 引入 AI / 自动语义 / 自动整理 / 自动删除 / 下载器 / watcher | ✅ 未做（均在 OUT OF SCOPE） |
| 为「功能完整」建立无数据源的关系 | ✅ 未做（§4/§5/§6 明确无数据源即不建） |

```text
PHASE 3.0 = Architecture / Scope Review（只读）—— 报告完成，等待正式 Contract 冻结。
```
