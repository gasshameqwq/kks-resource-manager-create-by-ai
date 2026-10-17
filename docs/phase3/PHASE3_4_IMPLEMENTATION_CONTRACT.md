# Phase 3.4 — Implementation Contract（FROZEN）

> 文档类型：Implementation Contract **正式冻结版**（FROZEN，2026-10-17）
> 状态：**FROZEN · 未授权实施（G-2）· 未授权 Git 收尾（G-3）**
> 修订自：`Phase 3.4 — Implementation Contract（草案 r6 · DRAFT）`（r6 为最终审批草案；本文件在其内容基础上追加 Freeze Record 与冻结状态标记）
> 文件位置：`docs/phase3/PHASE3_4_IMPLEMENTATION_CONTRACT.md`（r6 · FROZEN）
> **证据时点声明**：草案中的源码符号、行号、测试名与「已核实事实」，均来自 **r0 轮次的只读调查**（2026-10-16）。**r1 / r2 / r3 / r4 / r5 / r6 / r7 轮均未运行任何测试**（依据各轮执行记录；仓库内无独立测试产物可核）；r7（冻结）轮仅执行冻结所需的文档修改与 Git 提交。历史测试数字（如 `938 passed`）不得被描述为本轮新执行的结果。
> 标注约定：**【事实-代码】** · **【事实-测试】** · **【事实-文档】** · **【事实-实测】** · **【推断】** · **【未决】** · **[需批准]** · **(r1 修订)** / **(r2 修订)** / **(r3 修订)** / **(r4 修订)** / **(r5 修订)** / **(r6 修订)** / **(r7 冻结)**＝相对上一版的变化标记。

---

## 0. 起草前提、边界与三个授权闸门

### 0.1 前提

1. 本草案是**规划产物**。任何条款在 §11 被用户逐项批准前**一律无效**。
2. 用户已确认的规划决策（方案 A / 纳入 Query Model 架构文档补写 / 暂缓正式定义 Taxonomy / 当前只授权规划）是本草案的**输入**，**不等于**实现范围批准、契约冻结或任何 Git 授权。
3. 历史讨论、建议与本草案内容**不得**被自动视为已批准的实施任务（`WORKFLOW.md` §2、§5.2、§8）。
4. 草案与既有冻结契约冲突时，**一律以既有冻结契约为准**（`PROJECT_STATE.md` §2.2 权威顺序）。

### 0.2 本轮边界

r7（冻结）轮仅修改本文件：更新状态与版本元数据、在 §0.3 标记 G-1 完成、补充 §11 冻结说明，并新增 §12 Freeze Record；未修改或创建其他任何仓库文件，未运行测试，未创建/修改任何 tag，未 push，未执行 G-2；本轮仅创建冻结所需的单文件提交。

### 0.3 三个必须分离的授权闸门（r1）

以下三项是**彼此独立**的决策点，任何一项的完成都**不自动**包含其余两项（`WORKFLOW.md` §6.2、§7、§8）：

| 闸门 | 内容 | 触发条件 | 本草案的态度 |
| :--- | :--- | :--- | :--- |
| **G-1 契约冻结** | 将本草案形成正式 FROZEN 契约 | 用户逐项审核并**明确批准**本草案后，进入正式契约形成流程 | **已完成（2026-10-17）**；冻结**不自动**授权实施 |
| **G-2 实施授权** | Codex 执行 Phase 3.4 | 正式契约冻结后，用户**另行明确授权** | 本草案**不授权**实施 |
| **G-3 Git 收尾授权** | commit / annotated tag / push 等 | 实施结果通过审核后，用户**另行明确授权** | 本草案**不授权**任何 Git 写操作 |

G-1 已于 2026-10-17 完成；G-2 / G-3 **均未授权执行**。

---

## 1. 阶段目标与背景

### 1.1 建议阶段名称

`Phase 3.4 — User Classification & Search`（**保留**，沿用 `PHASE3_0_2` §11 与 `PHASE3_3_IMPLEMENTATION_CONTRACT.md` §15 已使用的名称）。

**名称语义限定**【事实-文档】：本阶段的「User Classification」在现行文档中**只**指「用户类型修正（`type_source='user'`）+ 展示名覆盖（`display_name`）」这两项 Phase 3.1 已交付能力的**可检索性核验**，**不**包含新的分类能力、分类值或自动分类规则（`PHASE3_0_2` §11：「taxonomy 在 3.4 只做『effective type』接线，**不**新增类型值、**不**做路径推断」）。

### 1.2 背景：3.4 的原始定义与本阶段性质

【事实-文档】3.4 的原定内容仅出现在两处，均为**审查级 / 边界声明**，无契约：

| 来源 | 原文要点 |
| :--- | :--- |
| `docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md` §11 行「3.4 User Classification & Search」 | 让 **effective type**（user override 优先）进入搜索面；`display_name` 按 §3.1 变为可搜的用户值；favorite 经 Tag 可搜 |
| `docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md` §15 | 3.4 = effective type（`type_source='user'` 优先）进入搜索面 + `display_name` 作为用户值的搜索语义细化（`PHASE3_0_2` §13-G5） |
| `docs/phase3/PHASE3_3_CLOSURE_REPORT.md`「Scope」 | 重复同一定义，并声明其**不属** 3.3 关闭范围 |

【事实-代码】r0 轮核验显示：上述两项「能力级」描述在当前实现中**已基本成立**（见 §3.1 第 1、3、4 项）。因此本阶段性质为「**语义核验 + 文档补齐 + 必要的测试证据**」，与用户决策 1（方案 A）一致。

【事实-文档】`PHASE3_0_CONTRACT.md` §15 明示总 Contract **不决定也不写死**子阶段编号与顺序 → 3.4 的编号与内容**须由用户另行确认**。

### 1.3 阶段目标（草案建议）

1. 核验 effective type 的现有**读、写、保留、筛选**四条语义路径是否自洽、是否符合已冻结契约。
2. 核验 `display_name` 的**文本搜索面**与**更新后的索引同步**行为（**记录**现行语义，不改行为）。
3. 确认 Phase 3.3 交付的 Query Model 与 Tag/Favorite 只读筛选**无回归**。
4. 记录 `resource_type` / `type_source` / `PropertyCategory` / `name` / `display_name` 的**现有职责与关系**（仅记录现状，不新建 Taxonomy 定义）。
5. 更新 `docs/ARCHITECTURE.md`，使其准确描述 Query Model 与只读筛选的数据流（含已发现的过时表述修正）。
6. **仅在**有测试证据支持、属本阶段范围、且符合冻结架构约束时，提出**最小**实现缺陷修复；否则零功能增量交付。

### 1.4 零功能增量路径（正式条款，r1）

```text
1. 若 §3.1 的核验结论为「原始能力目标均已满足且无实现缺陷」，Phase 3.4
   可以且应当仅交付：
     (a) 逐项有证据的行为核验结论；
     (b) 必要的行为测试（把「已成立的事实」变成可回归的证据）；
     (c) 架构文档修订（§4.1-IS4）；
     (d) 字段职责记录（§4.1-IS5）；
     (e) 阶段文档（实施日志 / 关闭报告 / 项目状态同步）。
2. 不得为制造生产代码差异而新增功能。
3. 若无生产代码变更，Closure Report 必须明确记录这一事实，
   并写明依据（核验结论 + 测试证据 + diff 为空）。
4. 零功能增量 ≠ 可以省略必要验证或验收：
   全量测试、schema 断言、只读护栏、文档一致性核对、
   以及 §8 Definition of Done 的全部条件仍然逐项适用。
```

【推断】该路径在技术上可行，因为原始两项目标在实现层面已基本成立（§1.2、§3.1）。**该推断须由 §7.2 的测试证据确认后才作为结论使用。**

---

## 2. 权威依据与约束优先级

### 2.1 文件清单核对（以实际仓库为准）

| 任务清单项 | 实际仓库 | 差异 |
| :--- | :--- | :--- |
| `docs/WORKFLOW.md` | ✅ 存在（§1–§9） | 无 |
| `docs/PROJECT_STATE.md` | ✅ 存在（§1–§9） | 无 |
| `docs/ARCHITECTURE.md` | ✅ 存在（§1–§12） | 无 |
| `docs/phase3/PHASE3_0_CONTRACT.md` | ✅ 存在（FROZEN） | 无 |
| `docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md` | ✅ 存在（审查级） | 无 |
| `docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md` | ✅ 存在 | 无 |
| `docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md` | ✅ 存在 | 无 |
| `docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md` | ✅ 存在（FROZEN） | 无 |
| `docs/phase3/PHASE3_3_CLOSURE_REPORT.md` | ✅ 存在 | 无 |
| `docs/phase3/PHASE3_3_LOG.md` | ✅ 存在 | 无 |
| — | ✅ 本文件为 3.4 的**首个**文件产物（现为 r6 · FROZEN） | r2 仅在对话中交付 |
| — | ❌ **不存在**「Phase 3 大阶段总工作文档」 | `PROJECT_STATE.md` §2.1 已登记该文档类型「尚未创建」 |

**文件命名无差异**；3.4 此前无任何文件产物，此点曾在 r3 创建前由只读核验确认（**该历史事实目前无法仅凭本文件独立核实**；本文件不将其改写为已证实或已否定）。

### 2.2 权威顺序

冻结 Contract（设计决策权威）> Decision Report / 设计评审 > Implementation Log > Closure Report（阶段验收权威）> `README.md` / `ARCHITECTURE.md` / `PROJECT_STATE.md`（描述性，不得与冻结 Contract 冲突）。

本阶段的上游权威为 `PHASE3_0_CONTRACT.md`。`PHASE3_3_IMPLEMENTATION_CONTRACT.md` 仅在其自身范围（Phase 3.3）内构成设计决策权威。

**Phase 3.3 §10.2 的适用范围（用户确认，2026-10-17；r5 修订）**

1. 用户已明确确认：Phase 3.3 §10.2 的文件限制**原则上只约束 Phase 3.3 自身**，**不自动延伸**为 Phase 3.4 的文件禁令。
2. 该确认**不修改** `PHASE3_0_CONTRACT.md` 的任何冻结条款，**也不授权**超出本契约 §4.3 文件清单的修改。
3. 来源区分：上述范围由**用户决定**；`PHASE3_3_IMPLEMENTATION_CONTRACT.md` §17 第 7 项只是同类问题的**同构先例**，**不是**「子阶段文件限制只约束本阶段」的通用规则明文；§10.2 自身并未写该范围限定。
4. 该确认**不得**被扩大解释为对其它历史限制、架构约束或冻结决策的豁免；Phase 3.4 仍须遵守 §2.3 与 §4.2 的全部约束。

**优先级（P2，r4 修订；r5 补充第 5 条）**

1. **冻结契约是范围与行为判断的最高依据。**
2. 现有测试**只能作为验证证据**，不能推翻、修改或覆盖冻结契约。
3. 如果测试现有预期与冻结契约冲突，**不得为了让测试通过而自动修改实现或契约**；应报告冲突，并按任务授权流程处理。
4. 其他文档、历史说明和测试意图，均不得被解释为高于冻结契约的授权。
5. 若冻结契约之间出现实质冲突且无法在现有授权范围内安全解决，按 `WORKFLOW.md` §3 暂停并报告；报告须保留冲突原文（文件 / 条款 / 行号）、已完成检查、可行选项与待用户决定事项。不得自行修改任一冻结契约。

### 2.3 本阶段必须遵守的上级约束（出处）

| 约束 | 出处 |
| :--- | :--- |
| 零 schema 变更（`SCHEMA_VERSION == 2` / 16 表） | `PHASE3_0_CONTRACT.md` §8、§16.5、§13-14 |
| Query Layer 继续只读；additive；DTO 向后兼容 | 同上 §10 |
| 用户数据经单一写服务；机器写入者不得写用户列 | 同上 §2、§9 |
| 文件系统只读边界 | 同上 §11 |
| `name` = 机器事实；`display_name` = 纯用户数据；`effective_display_name = display_name or name`；禁止用相等性判 override | 同上 §3.1 / §14.1 S4 |
| `[OPEN-EVIDENCE]` 项**取得证据前不得实现** | 同上 §16.4（U1/U4/U5 等） |
| 扩大首期范围须走变更控制：评审 + 更新 Contract + 用户确认 | 同上 §16.1–§16.2 |
| 阶段状态 ≠ 验收 ≠ Git 授权；未经明确授权不得执行 Git 写操作 | `WORKFLOW.md` §6.2、§7、§8 |

---

## 3. 已核实事实、推断与未决事项

### 3.0 证据时点与口径

1. 本节所有【事实-代码】/【事实-测试】/【事实-实测】均来自 **r0 轮次只读调查**（2026-10-16）；**r1–r7 轮均未重新核验本节事实**（r7 仅执行文档冻结与提交；依据各轮执行记录，未由仓库独立核实）。
2. `938 passed`（`PHASE3_3_LOG.md` §5.2）是**历史实施轮的记录**，**不是**收尾轮或本轮的执行结果。
3. 行号为 r0 轮读取时的实际行号；若后续提交改动文件，应重新定位后再引用。
4. 任何【推断】与【未决】在 §7.2 取证前**不得**当作结论。

### 3.1 八项待核实事实的核验结果

**① `ResourceWriteService` 如何更新 `resource_type` 与 `type_source`**
【事实-代码】`core/app/resource_write.py::ResourceWriteService.set_resource_type()`（第 118–130 行）：先校验 `value in core.models.RESOURCE_TYPES`（10 值元组，`core/models/__init__.py` 第 20–31 行），非法值抛 `InvalidResourceValue` 且**不写库**；合法时在**同一事务**内写 `{"resource_type": value, "type_source": "user"}`。写路径经 `_update_user_columns()`（第 134–159 行），白名单 `_USER_WRITABLE_COLUMNS = {display_name, notes, resource_type, type_source}`（第 68–70 行），**总是先做存在性检查**（`_require_resource()`，第 161–166 行）。**无** `'user' → 'auto'` 回退 API。
【事实-代码】关键结论：**`resources.resource_type` 只有一列；用户修正即覆盖该列；不存在保存「机器原类型」的第二列。**

**② Scanner 如何保留用户修正的类型**
【事实-代码】`core/scanner/store.py::upsert_card_resource`（第 159–160 行）：`if existing["type_source"] == "user": resource_type = existing["resource_type"]`，随后 UPDATE 写回该值；zipmod 路径同构（第 243–247 行）。模块 docstring（第 19–20 行）声明本层「**绝不**写 `display_name` / `notes` / `type_source='user'`」。
【事实-测试】`tests/test_scanner.py::test_rescan_does_not_touch_notes_or_user_type`（第 847 行）；`tests/test_ownership_guard.py::test_scanner_executed_sql_never_writes_user_columns`（第 112 行）、`::test_scanner_insert_keeps_type_source_auto`（第 141 行）；`tests/test_cli_resource_write.py::test_cli_writes_survive_scanner_rescan`（第 222 行，第 252 行断言 `type_source == "user"`）。

**③ Query Layer 的类型筛选使用什么字段及条件**
【事实-代码】`core/query/queries.py::_resource_where`（第 273–305 行）：`if resource_type is not None: clauses.append("r.resource_type = ?")`（第 295–297 行）。
【推断】因此**按类型筛选已返回用户修正后的值**，「effective type 进入搜索面」在实现层面已成立；`PHASE3_0_2` §13-G5 所述「Contract 未说明搜索用 effective type」属**契约/文档空白**，不是实现缺失。
【事实-代码】`ResourceFilter`（`core/query/model.py`）的 15 个筛选字段**不含** `type_source` → 目前**无法**筛选「仅用户已修正」或「仅自动识别」。

**④ `display_name` 如何进入 FTS 与 LIKE 回退**
【事实-代码】`core/query/search.py` 第 58–59 行 `_FTS_COLUMNS = ("display_name", "name")`；`fts_match_expression()` 生成 `{display_name name} : "…"` 列限定短语（第 126–132 行）；FTS 路径用 `r.id IN (SELECT rowid FROM resources_fts WHERE resources_fts MATCH ?)`，非 FTS 路径用 `((r.name LIKE ?) OR (r.display_name LIKE ?))`（`queries.py` 第 246–256 行）；检索面另含 `relative_path`（恒走 LIKE，第 259 行）与作者关系（`resource_authors` + `authors`，第 261–266 行）。
【事实-代码】FTS 虚拟表列为 `display_name, name, author, series, description, notes`（`core/database/schema.py` 第 262–268 行），但**检索只用到 `display_name` / `name`** → `notes` / `series` / `description` / `author` 已入索引但**不可搜**（对应 3.3 契约 §2-14 的 Non-Goal）。
【事实-文档】FTS5 trigram 只索引长度 ≥ 3 的子串，1–2 字必须走 LIKE 回退（`docs/ARCHITECTURE.md` §5.3；`tests/test_database_schema.py` 第 128–129 行注释）——**该限制是「路径选择」的依据，不是「路径已被覆盖」的证据**（见 §7.2）。

**⑤ 更新 `display_name` 后索引如何同步**
【事实-代码】`schema.py` 第 280–285 行定义 `resources_fts_au AFTER UPDATE ON resources`（无 `OF` 限定）：先以 **old** 值对 FTS5 外内容表执行 `'delete'` 命令，再插入 **new** 值 → 任意 UPDATE（含 `set_display_name`）都会同步索引。
【事实-代码】`core/database/db.py`：FTS DDL 与触发器仅在**本次执行了迁移**时由 `_try_enable_fts(conn, fts_ddl)` 执行（第 186–196 行）；存量回填 `_backfill_fts` 亦只在 `applied` 非空时运行（第 200–211 行），其时序已由 `tests/test_fts_backfill.py` 覆盖。
【事实-测试】`tests/test_database_schema.py::test_fts_search_works_when_enabled`（第 118 行）覆盖 **INSERT 时**的 FTS 同步；FTS 不可用时按既有惯例 `pytest.skip`（第 120–121 行）。
【未决】**UPDATE 路径无测试** → §3.3 缺口 B。

**⑥ `ResourceFilter` / `BrowserScope.to_filter()` / Tag-Favorite 条件 / CLI 入口的实际实现**
【事实-代码】
- `core/query/model.py::ResourceFilter`：`@dataclass(frozen=True)`；15 字段（13 既有 + `tag_id` + `favorite`）；`__post_init__` 拒绝 `bool` 型 `tag_id`、非 bool 型 `favorite`；`to_params()` 恒返回 15 键；**无** SQL 出口与语法解析。
- `core/query/browse.py::BrowserScope`：14 个筛选字段（不含 `card_marker`）+ `order_by` + `descending`；`FILTER_KEYS: ClassVar[tuple[str, ...]]` 为 14 键；`to_filter()` 为唯一字段值映射；`filters()` = `to_filter().to_params()` 在 `FILTER_KEYS` 上的投影（docstring 明确不得用字典相等断言）。
- Tag 条件：`EXISTS (SELECT 1 FROM resource_tags rt WHERE rt.resource_id = r.id AND rt.tag_id = ?)`；Favorite：`EXISTS` / `NOT EXISTS` + `JOIN tags t ON t.id = rt.tag_id` + `t.name_key = FAVORITE_TAG_KEY`。
- CLI：`cli_query.py::add_query_parser`（第 712–759 行）在现有 `query resources` 上追加 `--tag` / `--favorite` / `--no-favorite`（互斥组、`dest="favorite"`、`store_const`、`default=None`）；`cmd_resources`（第 295–342 行）经 `TagQuery.find_by_name()` 解析 `--tag`，未命中走 `_not_found`（stderr + 退出码 1，且**不执行查询**）；新增条件经 `ResourceFilter(...).to_params()` 过滤出 `tag_id` / `favorite` 两项后与既有参数合并（第 307–328 行）；`_resource_list_scope`（第 265–292 行）只输出实际提供的键。
【事实-测试】`tests/test_query_model.py`（41 个用例）；`tests/test_query_cli.py`；`tests/test_browse.py`；`tests/test_tag_query.py`。

**⑦ 对应行为已有多少测试覆盖，哪些边界尚未定义**
【事实-测试】覆盖清单（r0 轮核对函数名）：`tests/test_resource_write.py`、`tests/test_cli_resource_write.py`、`tests/test_effective_display_name.py`、`tests/test_read_model_exposure.py`、`tests/test_ownership_guard.py`、`tests/test_search_core.py`、`tests/test_gui_filters.py`。
【事实-测试】全仓 `def test_` 计 **790 个测试函数**；`PHASE3_3_LOG.md` §5.2 记录收集数为 **938 passed**（含参数化）。**r0–r7 轮均未复跑测试**（依据各轮执行记录；仓库内无独立测试产物可核）。
【未决】见 §3.3。

**⑧ 架构文档现有章节与需要补充的具体内容**
【事实-文档】`docs/ARCHITECTURE.md` 共 12 节；r0 定位到的事项按 r1 的分类保留如下：

| # | 位置 | 现状 | 分类 |
| :--- | :--- | :--- | :--- |
| D1 | §3 目录结构（第 64–109 行） | **没有 `core/query/` 与 `core/app/`** | 一致性补充 |
| D2 | 全篇 | **无** `ResourceFilter` / `BrowserScope` / Query Model / 只读标签筛选描述；§5.3 只讲 FTS/LIKE 路由 | **必要修正** |
| D3 | §2 第 58 行 | 「把资源加入 `Favorite` **Collection** 或打上标签」 | **必要修正**（与 `PHASE3_0_CONTRACT.md` §4.2 / §13-5 冲突） |
| D4 | 顶部第 3 行 | 「版本：Phase 3.3 基线…2026-10-15」 | 一致性补充 |
| D5 | §10 路线图第 380 行 | 3.3 行已同步；3.4 及以后「未冻结」 | 一致性补充 |
| D6 | §4.4 索引（第 203–210 行） | 未列 `resource_tags` 的 PK 与 `idx_resource_tags_tag` | 一致性补充 |
| D7 | §4.3 ③（第 198–201 行） | 已写 `type_source ∈ {auto, user}` 与「重扫不覆盖」 | **必要修正**（补：用户修正写同一 `resource_type` 列，故该列即 effective type） |

【事实-文档】`PHASE3_3_CLOSURE_REPORT.md` 第 157–159 行已**自认**「`docs/ARCHITECTURE.md` 尚未收录 Query Model / 只读标签筛选的架构描述，属后续文档轮次」→ 本阶段纳入（用户决策 2）与该登记一致。

### 3.2 三类结论汇总

| 结论 | 性质 |
| :--- | :--- |
| effective type = `resources.resource_type` 单列；按类型筛选已反映用户修正 | 【事实-代码】+【推断】 |
| `display_name` 已在 FTS 与 LIKE 两条搜索路径的检索面内；UPDATE 触发器负责同步 | 【事实-代码】 |
| 原始两项目标在实现层面已基本满足；剩余为语义 / 文档 / 证据 | 【推断】← 零功能增量路径的主要理由 |
| 现行搜索匹配语义为：`name` **或** `display_name` 任一命中即命中（FTS `{display_name name}` 列限定短语；LIKE 两个 `OR` 分支） | 【事实-代码】→ 由 T-A2 取证确认 |

### 3.3 已确认的缺口与待确认边界

**(a) 测试缺口（缺口，非实现缺陷）**

| ID | 缺口 | 证据 |
| :--- | :--- | :--- |
| **A** | **`display_name` 覆盖值与文本搜索的联动未被断言**：搜索套件里 `display_name` 恒等于 `name` | `tests/test_search_core.py::_add_resource` 第 62、78 行；r0 轮 `rg display_name tests -g "*.py"` 在搜索类测试文件中**零命中** |
| **B** | **FTS UPDATE 路径（`resources_fts_au`）无测试**：既有用例只覆盖 INSERT 同步 | `tests/test_database_schema.py` 第 118–143 行；r0 轮 `rg resources_fts tests` 未发现 `set_display_name` → `MATCH` 用例 |
| **C** | **用户类型修正后按有效类型筛选未被断言**：类型筛选用例数据均为直接 INSERT，无一处先经 `set_resource_type()` | `tests/test_search_core.py` 第 647–648 行、`tests/test_browse.py` 第 333–334 行、`tests/test_query_model.py` 第 297/316 行、`tests/test_query_cli.py` 第 114/695–700/732 行 |

**(b) 行为边界未定义（仅记录，不视为缺陷、不纳入实现任务）**

【事实-代码】`cli_query.py` 第 723 行 `--type` **无 `choices`**，Query 层只做 `r.resource_type = ?` → 未知类型**静默返回空结果（exit 0）**；而 `--game` / `--category` / `--order` 的非法值经 `ValueError` 被 `cli_query.py` 第 834–843 行转换为**参数错误（exit 2）**，由 `tests/test_query_cli.py::test_query_argument_errors_exit_2`（第 257–264 行）覆盖（`--game XXX` 的 `ValueError` 来自 `core/query/card_format.py::card_marker_for_game` 第 31–39 行）。
【未决】该不对称是否有意设计**无文档或测试说明** → 处置见 §9-Q5（方向固定为「仅记录」）。

### 3.4 尚未核实 / 超出只读范围

- 未复跑全量测试（938 passed 属历史记录）。
- 未启动 GUI，未核验 `ui/**` 运行期行为。
- 未核验真实样本库之外的数据；持久工作库【事实-实测】`resources=0` / `tags=0`（r0 轮 `immutable=1` 只读实测）。
- 未验证 `requirements.txt` / `docs/THIRD_PARTY.md` 与运行环境的一致性。
- `ARCHITECTURE.md` 的审计范围在 r2 已**收紧**（§4.1-IS4），范围外章节**不得**纳入本阶段。

### 3.5 版本间差异（内容层面）

r1 相对 r0 的改动为结构性/流程性（零功能增量条款、测试拆分与路径覆盖、失败处置、`--type` 方向、架构文档二分、三闸门分离）。r2 相对 r1 落实六项修订（测试修改授权边界、T-B 强化、T-A1/T-A2 隔离与断言、架构审计范围收紧、Step 0 记录方式、失败分类统一）。

**修订计数口径（r4 修订，P3）**：r3 相对 r2 落实的是**「五组修订、共 7 个列出的修订项」**。组别与子项对应关系如下（明细见文末「r2 → r3 修订摘要」的「组别」列）：

- **G1** → 第 1–4 项（分类不授予修改权、T-A1 双路径、T-B 索引级、§4.3/§6/§7.6 授权口径）；
- **G2** → 第 5 项（DoD 阻断条件与 IS4 证据）；
- **G3** → 第 6 项中的 Q2；
- **G4** → 第 6 项中的 Q10（与 G3 共用该行，故 5 组对应 7 行）；
- **G5** → 第 7 项（版本与状态）。

**r4 相对 r3 的变更 = 3 项内容修订（P1 / P2 / P3：测试文件授权清单、冻结契约优先级、修订计数一致性）+ 版本元数据更新**（文档头：标题、文档类型、修订自、文件位置、证据时点、标注约定；§0.2；§2.1）。**版本元数据不计入内容修订项**，也不改变任何功能范围或授权清单。

**r5 相对 r4 的变更 = 3 项内容修订（P1 文件限制适用范围、P2 修订记录一致性、P3 冻结契约冲突处理）+ 必要的版本元数据更新**（文档头、§0.2、§2.1）；未改动功能范围、验收标准、文件清单或架构决策。

**r6 相对 r5 的变更 = 2 项文档记录修订（P1 修订记录补齐、P2 历史事实证据状态标注）+ 必要的版本元数据更新**（文档头、§0.2、§2.1）；未改动功能范围、验收标准、文件清单或架构决策。

**r7（冻结）相对 r6 的变更 = 状态与 Freeze Record（无内容范围变更）**：DRAFT → FROZEN、§0.3 G-1 标记、§11 冻结说明、新增 §12；未改动功能范围、验收标准、文件清单或架构决策。

---

## 4. In Scope、Non-Goals 与文件范围

### 4.1 In Scope（候选，[需批准]）

| # | 范围项 | 依据 |
| :-- | :--- | :--- |
| IS1 | **现有行为核验**：§3.1 八项事实的核验结论逐项成文；架构文档**按 §4.1-IS4 限定的审计范围**核对 | 用户决策 1 |
| IS2 | **必要的行为测试**：补 §3.3 缺口 A / B / C 的测试证据（**不改生产代码、不改搜索行为**），并遵守 §7.6 测试修订授权边界 | 用户决策 1 |
| IS3 | **经批准的、有证据支持的最小实现缺陷修复**：仅在测试暴露「与冻结语义不符」的行为、且**经用户针对具体问题与文件范围单独批准**后 | 用户决策 1；`PHASE3_0_CONTRACT.md` §16 |
| IS4 | **架构文档修订**，分两类：<br>**必要修正**：Query Model / `ResourceFilter` / `BrowserScope` 的职责与关系（D2）；GUI/CLI → 统一 Query Model → Query Layer 唯一执行点 → SQLite 的数据流（D2）；Tag/Favorite 只读筛选的实际实现语义（D2）；Favorite 是**保留系统 Tag 而非 Collection**（D3）；`resource_type` / `type_source` / `PropertyCategory` / `name` / `display_name` 的现有职责与关系（D7）；FTS / LIKE 搜索路径的准确描述（D2 相关）。<br>**一致性补充**：目录结构清单（D1）；`resource_tags` 相关索引清单（D6）；版本与阶段状态（D4/D5）；schema 版本与相关表描述。<br>**审计范围限定**：见下方 §4.1.1。 | 用户决策 2；`PHASE3_3_CLOSURE_REPORT.md` 第 157–159 行 |
| IS5 | **字段职责记录**：仅记录现状与关系（**不定义 Taxonomy、不新增分类值/规则/路径推断**）——并入 IS4 的必要修正部分 | 用户决策 3；`PHASE3_0_2` §11 |
| IS6 | **阶段文档产物**：`docs/phase3/PHASE3_4_LOG.md`、`PHASE3_4_CLOSURE_REPORT.md`，按需同步 `PROJECT_STATE.md` / `README.md` / `ARCHITECTURE.md` 状态行 | `WORKFLOW.md` §5.1；3.3 既有惯例 |
| IS7 | **零功能增量收尾**（§1.4） | 用户决策 1 |

#### 4.1.1 `docs/ARCHITECTURE.md` 一致性审计的范围限定（r2）

**必须核对、并在必要时修正的内容（本阶段审计范围）**

1. Query Model 与相关查询入口（`core/query/model.py`、`core/query/__init__.py`、CLI/GUI 入口）。
2. 筛选数据流及 `ResourceFilter` / `BrowserScope` 的职责（`to_filter()` / `FILTER_KEYS` / `filters()` 投影、15 键 vs 14 键）。
3. Tag / Favorite 的实际筛选语义（`resource_tags` EXISTS、`FAVORITE_TAG_KEY` 保留系统 Tag）。
4. 资源类型字段的职责（`resource_type` 与 `type_source` 的关系）。
5. `name` 与 `display_name` 的职责及搜索行为（含现行 `name` **或** `display_name` 匹配语义）。
6. FTS / LIKE 搜索路径（trigram ≥3 字限制、1–2 字回退、FTS 不可用时的 LIKE 回退）。
7. schema 版本、相关表与索引描述（含 `resource_tags` 的 PK 与 `idx_resource_tags_tag`）。

**其他章节**：**只有**在与上述七项范围**或**与冻结契约存在**直接冲突**时才修正；此类修正须逐条记录「冲突点 + 依据」。

**范围外事项**：与 3.4 七项范围及冻结契约均无直接冲突的历史文档债务，**单独登记**（按 §9-Q10 方案 (a) 登记到 `PHASE3_4_LOG.md` 待办区），**不自动纳入** Phase 3.4。

**禁止**：借一致性审计重新设计架构、引入 Resource Taxonomy 定义、或扩展功能范围。

D1–D7 各项按 §3.1-⑧ 表中的**原有分类**逐项处理（必要修正 / 一致性补充），不因范围限定而改变归属。

### 4.2 Non-Goals 与保留边界

| # | 排除项 | 依据 / 更严格来源 |
| :-- | :--- | :--- |
| 1 | Schema 变更、迁移、新表、新列、新索引 | `PHASE3_0_CONTRACT.md` §8、§13-14、§16.5 |
| 2 | 新增 `type_source` 筛选 | §2.3「扩大范围须走变更控制」；3.4 无该授权 |
| 3 | 新增 Resource Taxonomy 值 / 分类规则 / 路径推断 / **正式定义 Taxonomy** | `PHASE3_0_CONTRACT.md` §5、D3；`PHASE3_0_2` §11 末；用户决策 3 |
| 4 | 文本查询语法（`field:` / AND / OR / NOT）、单/多标签组合、新排序能力 | `PHASE3_0_2` §13-G2/G3；3.3 契约 §2-1/2/3/6、§15 |
| 5 | **改变 `display_name` 的搜索匹配语义**（如要求覆盖后旧 `name` 不再命中） | 属新增用户能力 → `PHASE3_0_CONTRACT.md` §16；见 §9-Q4 |
| 6 | 新 DTO 字段（含列表行 `tags` / `is_favorite`） | 3.3 契约 §2-5；`PHASE3_0_CONTRACT.md` §10 |
| 7 | GUI 标签管理与搜索控件（含 `ui/**` 任何改动）；不把 GUI 工作提前到 3.4 | 3.3 契约 §15 |
| 8 | Collection / 持久 review 状态 / relocation / 重复资源能力扩展 | `PHASE3_0_CONTRACT.md` §13-5/§13-6/§13-7/§13-8、§6.3 |
| 9 | 未经证据支持的自动分类 / 默认标签 / 标签粒度扩展 | 同上 §13-3；§16.4；U1 仍 OPEN |
| 10 | 性能优化、新索引、FTS 检索字段扩展、N+1 重构 | 3.3 契约 §2-13/§2-14；`PHASE3_0_2` §9.3 |
| 11 | Phase 3.5 内容（Tag/Favorite GUI 与 UX、最终 UX、startup eager system-tag bootstrap 接线） | 3.3 契约 §15 |
| 12 | 修改任何冻结契约 | `WORKFLOW.md` §5.2、§8 |
| 13 | 为 `--type` 增加 `choices` 或其它取值校验 | 属 CLI 行为变更；本阶段仅记录（§9-Q5） |
| 14 | 任何 Git 写操作、契约冻结、阶段状态变更、tag 创建或移动 | `WORKFLOW.md` §7；§0.3 |
| 15 | 修改共享 fixture / 辅助函数默认值 / 既有断言 / 无关测试用例；以及把架构文档的**范围外历史债务**纳入本阶段 | §7.6；§4.1.1 |

### 4.3 文件范围 [需批准]

**允许修改（候选；最终以实现轮授权为准）**

| 文件 | 变更 |
| :--- | :--- |
| `docs/ARCHITECTURE.md` | IS4 / IS5：必要修正 + 一致性补充，**限于 §4.1.1 的七项审计范围** |
| 测试文件 | IS2：**(r4 修订)** **仅限 §4.3.1 列出的 3 个文件**，且仅限表内对应的测试 ID；未列出的文件一律**不在**授权范围内。不得擅自修改共享 fixture、辅助函数默认值、既有断言或无关用例。 |
| 生产代码 | **仅**在 IS3 被单独批准时，且限于用户针对该问题明确批准的文件清单 |
| `docs/phase3/PHASE3_4_LOG.md`（新增）· `PHASE3_4_CLOSURE_REPORT.md`（新增）· `docs/PROJECT_STATE.md` · `README.md` | IS6（收尾轮）；写入时机见 §6.1 |

**明确禁止修改（除非单独批准）**：`core/database/**` · `core/scanner/**` · `core/parsers/**` · `core/app/**` · `core/models/tags.py` · `core/query/search.py`（文本搜索语义冻结）· `ui/**` · `main.py` · 任何冻结契约文件 · 既有测试断言语义 · 共享 fixture 与辅助函数默认值。

#### 4.3.1 授权测试文件清单（穷尽式，r4）

本阶段**仅**允许在下列 3 个文件中新增用例。路径已由 2026-10-17 只读核验确认存在（`Test-Path` → `True`）。**未列出的文件一律不在授权范围内。**

| # | 文件路径（仓库相对） | 允许承载的测试 ID | 允许的修改范围 | 明确不允许 |
| :-- | :--- | :--- | :--- | :--- |
| 1 | `tests/test_search_core.py` | **T-A1**、**T-A2** | 仅在文件末尾**追加**新的 `test_` 函数；可复用文件内既有 fixture 与 `_add_resource(..., display_name=...)` 参数 | 修改 `_add_resource` 默认值、既有用例、既有断言或 fixture；改动 `name OR display_name` 语义 |
| 2 | `tests/test_database_schema.py` | **T-B** | 仅在文件末尾**追加**新的 `test_` 函数；FTS 不可用时按既有 skip 惯例跳过 | 修改既有 `test_fts_search_works_when_enabled`、`db_file` fixture 或 skip 条件；放宽四项断言 |
| 3 | `tests/test_query_model.py` | **T-C** | 仅在文件末尾**追加**新的 `test_` 函数 | 修改既有用例、`seeded` fixture、`_add_resource` 等辅助函数或既有断言 |

**补充规则**

```text
1. T-D / T-E 仅复用既有覆盖，不新增用例、不新增文件（见 §7.2）。
2. 未列出的测试文件、新增测试文件、或修改上表任一文件的既有结构
   （fixture / 辅助函数 / 既有断言 / 无关用例）→ 必须停止并报告，
   等待用户单独批准（§7.6）。
3. 每个新增用例须在实施日志登记「实际函数名 ↔ 测试 ID」映射；
   函数名的语义不得超出对应 T-ID 的断言范围。
4. 上表是穷尽式清单：不存在「可改用其他测试文件」的默认授权。
```

---

## 5. 架构、数据安全与兼容性约束

### 5.1 架构约束

1. 依赖方向单向 `ui/ → core/`，`core/` 永不 import UI（`ARCHITECTURE.md` §3）。
2. **唯一 Query Model + 唯一执行点**：GUI 与 CLI 必须编译到同一 `ResourceFilter`，SQL 只由 `core/query/queries.py` 构造（`PHASE3_0_2` §10.1/§10.4；3.3 契约 §4/§5）。
3. Query Layer **只读**；不得因本阶段获得 UPDATE / DELETE 能力。
4. 用户写入只经 `ResourceWriteService`（tag 写侧为既有 `TagWriteService`）；GUI 不得直连 SQLite。
5. **不新增第二套搜索系统**；不得在 `ui/**` 或 `cli_query.py` 中新增 SQL。

### 5.2 数据安全约束

1. 不触碰 `data/kks_resource_manager.db` 真实工作库；测试一律在临时库中进行。
2. 不移动 / 重命名 / 删除任何用户文件；不联网。
3. 新增查询必须**参数化绑定**，保持既有只读护栏（`core/query/readonly.py`）。
4. 发现工作区已有修改时**记录并保护**，不覆盖、不清理。

### 5.3 兼容性约束

1. **零 schema 变更**：`SCHEMA_VERSION == 2` / `MIGRATIONS == {1, 2}` / 16 张业务表保持。
2. DTO 字段集不变、构造方式（关键字与位置）向后兼容。
3. `ResourceQuery.count` / `list` 的既有参数语义与默认值不变；新增参数只能以带默认值的 keyword-only 形式追加。
4. CLI 既有输出字段与 `scope` 语义不变。
5. **`display_name` 搜索匹配语义不变**（`name` 或 `display_name` 任一命中即命中）。
6. 既有测试断言不得削弱或改写。

### 5.4 不变量（本阶段必须保持）

`PHASE3_0_CONTRACT.md` §14.1 D1–D5 + S1–S4；`PHASE3_0_2` §12 的 R2/R3/R4/R6；`PHASE3_3_IMPLEMENTATION_CONTRACT.md` §9 兼容性条款与 §12 测试不变式的**精神**。

---

## 6. 实施顺序（[需批准]）

```text
Step 0  核验轮：完成 §3.1 八项事实的逐项核验结论（含 ARCHITECTURE.md 在
        §4.1.1 范围内的逐项核对）。
        记录方式见 §6.1：结果先写入执行报告 / 对话，不修改任何仓库文件。

Step 1  缺口取证（测试）：在 §4.3.1 授权清单内新增 §3.3 缺口 A / B / C
        的测试用例 → 运行 focused 测试。
        ├─ 全部通过 → 进入 Step 3（零功能增量路径）
        └─ 任一失败 → 立即停止，按 §7.3 五类处置流程执行；
             分类本身不授予任何修改权（§7.6）

Step 2  [条件性] 最小缺陷修复：仅针对 Step 1 暴露、且经用户针对
        「具体问题 + 具体文件范围」单独批准的问题，严格限于批准的文件清单；
        修复后重跑 focused 测试（并回到 Step 1 判定）。
        Step 2 仅描述条件性执行顺序，不构成生产代码修复授权。

Step 3  架构文档修订（必要修正）：D2 / D3 / D7 + 数据流 + Tag/Favorite 只读
        筛选语义 + 字段职责记录，限 §4.1.1 七项范围。

Step 4  架构文档一致性补充：D1 / D4 / D5 / D6 + 范围内发现的其他过时描述；
        范围外债务按 §9-Q10 单独登记，不纳入。

Step 5  验证：focused → 全量 pytest（记录真实输出）→ schema 断言 → 只读护栏 →
        文档与实现一致性核对。

Step 6  文档收尾：PHASE3_4_LOG.md → 关闭轮 PHASE3_4_CLOSURE_REPORT.md +
        同步 PROJECT_STATE.md / README.md / ARCHITECTURE.md 状态行。
        若无生产代码变更，Closure Report 必须显式记录该事实及依据（§1.4-3）。

Step 7  Git 收尾：仅在用户另行明确授权（G-3）后执行 commit / tag；默认不授权。
```

### 6.1 Step 0 核验结果的记录方式（正式条款，r2）

```text
1. Step 0 是只读核验阶段：
   - 核验结果先写入「执行报告」或对话中（逐项列出结论 + 证据：文件 / 符号 / 行号）；
   - 不修改或创建任何仓库文件；
   - 不提前更新实施日志（PHASE3_4_LOG.md 属 IS6，仅在 G-2 授权后创建/写入）。
2. 「逐项记录核验结果」不得被理解为 Step 0 可以修改仓库文档。
3. 只有在后续实施获得授权（G-2）后，才把必要的核验证据写入
   获准修改的实施日志（PHASE3_4_LOG.md）。
4. Step 0 若发现与范围外章节相关的过时描述，按 §4.1.1 单独登记，不顺手修改。
```

### 6.2 授权口径的统一（r3）

```text
§4.3（允许修改的文件清单）· §6（实施顺序与 Step 2 的性质）·
§7.6（测试修订授权边界）三者必须一致解释：

1. 「已批准测试文件」= 最终冻结契约 §4.3.1 的穷尽式清单；
2. 新增测试文件、扩大测试文件范围、修改既有测试结构，均须另行批准；
3. Step 2 只是条件性执行顺序，不构成生产代码修复授权；
4. 任何一步的分类、记录或流程确认，都不替代针对具体改动的批准。
```

---

## 7. 测试策略

### 7.1 已有覆盖（**不预设不足**）

任务要求的五类行为**均已有覆盖**，明细见 §3.1-⑦。结论：既有覆盖足以支撑「无回归」声明，但**不足以**作为「用户值可被搜到」与「用户修正后按有效类型可筛」的**正面证据**——这正是缺口 A / B / C 的性质。

### 7.2 待补充测试（候选，[需批准]）

**总体要求**

```text
1. 测试必须能证明「实际覆盖了相应搜索路径」，不得仅凭输入字符串长度
   假定走了 FTS 或 LIKE 路径；须复用既有路由测试手段或等价可靠证据。
2. 不得改变现有搜索行为；不得新增搜索语法或扩展检索字段。
3. 不得削弱既有断言；默认不得改动共享 fixture 与辅助函数默认值（见 §7.6）。
4. 新增用例的数据必须与其他 fixture 明显区分，避免意外命中（见各用例）。
5. FTS 相关跳过只允许在环境确实不支持 FTS 时发生（见 skip 政策）。
```

| ID | 目标 | 唯一位置（§4.3.1；批准后生效） | 断言要点 / 路径与隔离要求 |
| :--- | :--- | :--- | :--- |
| **T-A1** | **(r3 修订)** 搜索语义测试：覆盖后的 `display_name` 能通过现有搜索接口命中，且 **FTS 与 LIKE 两条路径各自独立验证** | `tests/test_search_core.py`（用既有 `display_name=` 参数，不改默认值） | **资源隔离**：使用与其他 fixture 明显区分的机器名 / 展示名 / 查询词（例如含唯一标记的字符串）。**两条路径都必须验证**：经 `ResourceWriteService.set_display_name(rid, "<唯一别名>")` 覆盖后，分别通过 FTS 路径与 LIKE 路径搜索该别名，均能命中目标资源。**实际断言**：每条路径各自的断言均须确认**结果集合恰好包含目标资源**（不得只看「非空」）。**路径证明**：(a) FTS 路径——用 ≥3 字查询并**证明实际走 FTS**（沿用 `tests/test_search_core.py::test_long_query_uses_fts_expression`（第 278 行）/ `::test_real_sample_routing_uses_fts_for_three_chars`（第 843 行）的路由断言方式）；(b) LIKE 路径——**强制关闭 FTS** 后按 `::test_fts_disabled_falls_back_to_like`（第 323 行）/ `::test_plan_falls_back_to_like_when_fts_unavailable`（第 222 行）方式，**确认实际执行了 LIKE 回退**，并在该路径下得出命中。**禁止**：把旧 `name` 命中误当作 `display_name` 搜索成功；不得仅凭输入长度推定路径。 |
| **T-A2** | 旧名称行为记录：**明确记录现有 `name` OR `display_name` 语义**，并**实际断言**目标资源仍可通过旧 `name` 命中 | `tests/test_search_core.py`（同上） | **资源隔离**：同上，使用唯一标记名称与查询词，断言命中集合恰好包含目标资源。**实际断言**：覆盖 `display_name` 后，用旧 `name` 作为查询词仍**命中该资源**（现行语义）。**明确禁止**：把「旧 `name` 必须失效」写入验收要求或断言。若实际结果与现行语义不符，按 §7.3 处置，**不得**顺势把「旧名失效」当作目标 |
| **T-B** | FTS **索引级**更新同步测试（直接检查 FTS 中的 `display_name` 字段，而非只经 Query Layer 观察搜索结果） | `tests/test_database_schema.py`（**唯一位置**；不得新建文件） | 见下方「T-B 详细规格」 |
| **T-C** | 用户类型修正后按有效类型筛选 | `tests/test_query_model.py`（**唯一位置**） | `set_resource_type(rid, "mod")` 后：`list(resource_type="mod")` 含该行；`list(resource_type="character_card")` 不含；并断言 `type_source == "user"` |
| **T-D** | 覆盖后重扫仍保留（回归确认） | **不新增** | 已由 `tests/test_scanner.py::test_rescan_does_not_touch_notes_or_user_type`（第 847 行）、`tests/test_ownership_guard.py`（第 112 / 141 行）、`tests/test_read_model_exposure.py::test_scanner_rescan_does_not_change_exposed_user_fields`（第 109 行）覆盖 → 仅在核验结论中引证 |
| **T-E** | 只读与 schema 非回归 | **复用既有** | `count`/`list` 一致、连接级 `total_changes` 不变、`SCHEMA_VERSION == 2`、DTO 字段集不变、`ui/**` 无新增 SQL 绕过 |

#### T-B 详细规格 **(r3 修订)**

**执行环境与数据**

```text
1. 使用独立的临时数据库（不得触碰 data/kks_resource_manager.db）。
2. 令旧 display_name、新 display_name 与资源的 name 三者彼此「明显不同」。
3. 更新必须通过 ResourceWriteService.set_display_name 实际执行
   （而非直接 UPDATE SQL），以覆盖真实写路径与触发器。
4. 数据与查询词必须与其他 fixture 明显区分，避免其他资源意外匹配。
5. 更新前后均使用列限定的 display_name 条件（如 MATCH 'display_name : "<词>"'）
   直接检查 FTS 索引，并核对目标 rowid。
```

**四项独立断言**

```text
1. 更新前：旧 display_name 可在 FTS 索引中命中（且命中目标 rowid）。
2. 更新前：新 display_name 不命中。
3. 更新后：新 display_name 可命中（且命中目标 rowid）。
4. 更新后：旧 display_name 不再以旧的 display_name 值命中。
```

**必须明确区分的两种情形**

```text
- 旧 name 仍可通过 Query Layer 命中 → 属于现行搜索语义
  （name 或 display_name 任一命中即命中），本阶段只记录、不改，不得判定为缺陷；
- 旧 display_name 仍残留于 FTS 索引（例如列限定 MATCH 旧展示名仍命中）
  → 可能是索引同步问题，按 §7.3 分类处置，不得自行修复。
```

**执行条件与 skip**

```text
1. 仅当运行环境确实不支持 FTS 时才允许 skip；
2. FTS 已启用但断言失败时，必须按 §7.3 处理，不得 skip、不得放宽断言；
3. 沿用既有 skip 写法与措辞（参见 tests/test_database_schema.py 第 120–121 行）；
4. 实施日志必须记录 skip 的 test id、原因与当时的环境判定依据。
```

### 7.3 测试失败处置流程（正式条款 · 五类分类，r2）

Step 1 中 T-A1 / T-A2 / T-B / T-C 或任何新增用例失败时，按下列流程执行。

**前置：保存证据（先于分类）**

```text
必须保留：实际失败命令、完整输出、最小复现步骤，
以及相关代码证据（文件 / 符号 / 行号）。
在证据保存完成前，不得进入分类或修改任何测试。
```

**判断基准（P2，r4 修订）**

```text
1. 冻结契约是范围与行为判断的最高依据；
2. 现有测试只能作为验证证据，不能推翻、修改或覆盖冻结契约；
3. 测试现有预期与冻结契约冲突时，不得为了让测试通过而自动修改实现或契约，
   应报告冲突并按任务授权流程处理；
4. 其他文档、历史说明与测试意图，均不得被解释为高于冻结契约的授权。
```

**分类（五类，必须明确归类，不得省略）**

| 类别 | 含义 |
| :--- | :--- |
| 1. **实现缺陷** | 生产代码行为与冻结契约（最高依据）不一致；契约未规定时，才参考既有语义与既有测试 |
| 2. **测试自身问题** | 测试预期或测试代码错误（写错断言、写错数据、误解契约；含测试预期与冻结契约冲突） |
| 3. **环境问题** | 夹具、临时库、依赖、SQLite 构建等环境因素导致 |
| 4. **契约未定义** | 现行契约与文档均未规定的语义空白（例如 `--type` 未知值行为） |
| 5. **尚不能分类** | 证据不足以判定属于以上任一类 |

**处置步骤**

```text
1. 保存证据（见上）。
2. 依据证据归入上述五类之一。
   - 证据不足时必须归类为「尚不能分类」，保留全部证据、停止相关工作并报告；
     不得强行归类。
3. 分类结果本身不授予任何额外的生产代码或测试代码修改权限。
   - 若分类涉及「测试预期与冻结契约冲突」，必须同时记录「冲突点 + 契约条款出处」；
     冻结契约优先，不得以测试预期为由修改实现或契约（§2.2）。

4. 对「测试自身问题」：
   (a) 归类为测试自身问题，不自动意味着可以修改测试；
   (b) 只有同时满足以下四项条件，才可在现有授权内修正测试：
       i.   修改仅涉及 §4.3.1 已批准的测试文件；
       ii.  仅针对本阶段新增的测试用例；
       iii. 不涉及共享 fixture、辅助函数默认值、既有断言或无关用例；
       iv.  修正是在恢复或表达正确的测试意图，而不是为了通过测试
            而改变预期结果、削弱断言或规避失败；
   (c) 不满足上述任一条件 → 先报告「具体文件 / 修改原因 / 影响范围 /
       替代方案」，等待用户单独批准。

5. 对「实现缺陷」：暂停修复并报告，等待用户针对「具体问题 + 具体文件范围」
   作出单独批准。Step 2 本身不构成该授权。

5a. 若冲突或失败涉及多个冻结契约之间的实质冲突，或无法在现有授权范围内安全解决：
    立即暂停并报告；报告须包含冲突原文（文件 / 条款 / 行号）、已完成检查、
    可行选项、待用户决定事项（`WORKFLOW.md` §3）。不得自行修改任一冻结契约。

6. 对「环境问题」「契约未定义」「尚不能分类」：
   报告证据与影响（含对 §1.4 零功能增量判定的影响），等待用户决定后续处理；
   不得通过修改测试预期来规避失败。

7. 全局禁止：不得把任何测试失败自动解释为生产代码缺陷；不得因测试失败、
   测试意图修正或测试分类而默认获得生产代码修改授权；不得自行扩大实施范围；
   不得削弱既有测试断言或以修改测试预期的方式回避第 1 类问题。
```

### 7.4 回归与护栏

全量 `pytest -q` 必须执行并记录**真实输出**（不得引用历史数字）；补跑 3.3 既有护栏（schema 断言、Query 层连接级 `total_changes`、CLI 层数据库文件 SHA-256 不变）。

### 7.5 验收证据口径

必须区分「实施轮实测」与「收尾轮新取证」，明确声明哪些数字来自哪一轮、哪些**未**在该轮重跑（沿用 `PHASE3_3_CLOSURE_REPORT.md`「Verification」的既有做法）。**禁止**将历史记录或 r0 轮核验描述为本轮新执行的结果。

### 7.6 测试修订授权边界（正式条款，r4 对齐）

```text
1. 默认仅允许：在 §4.3.1 列出的 3 个文件中新增**本阶段**的测试用例。
   「已批准测试文件」= 最终冻结契约 §4.3.1 的穷尽式清单；未列出的文件不在授权范围。
2. 不得擅自修改：
   - 共享 fixture；
   - 辅助函数默认值（例如 tests/test_search_core.py::_add_resource 的 display_name 默认值）；
   - 既有断言；
   - 与本阶段无关的测试用例。
3. 新增测试文件、扩大测试文件范围或修改既有测试结构，都必须取得相应批准；
   未经批准不得以「新建文件」方式绕过 §4.3 的文件清单。
4. 如确有必要修改共享 fixture、辅助函数或既有测试结构，必须先报告：
   - 具体文件；
   - 修改原因；
   - 影响范围（可能受影响的既有用例）；
   - 替代方案（如何在不改动共享结构的前提下完成取证）；
   并等待用户**单独批准**后方可执行。
5. 测试修订必须「恢复或表达正确的测试意图」：
   不得仅为让测试通过而改变预期结果、削弱断言或规避失败。
6. 生产代码疑似存在缺陷时：保留证据并暂停相关修复，等待用户单独批准。
   Step 2 只是条件性执行顺序，不构成生产代码修复授权。
7. 当证据不足以判断属于实现缺陷 / 测试问题 / 环境问题 / 契约未定义时：
   归类为「尚不能分类」（§7.3），停止相关工作并报告，不得强行归类。
8. 环境问题、契约未定义或尚不能分类，不得通过修改测试预期规避失败。
9. 冻结契约优先于任何测试预期（§2.2 / §7.3）：不得以「测试意图」为由修改契约
   或生产行为；测试与契约冲突时，先报告冲突，不得自动修复。
```

---

## 8. Definition of Done

Phase 3.4 视为完成，当且仅当：

1. §1.3 六项目标**逐项**有可核验结论（核验类结论须注明证据来源：源码符号 / 测试名 / 只读实测）。
2. 未批准范围**零改动**；所有变更落在 §4.3 批准清单内，完整 diff 与批准范围一致。
3. **(r3 修订)** 最终验收要求**全量测试成功**，并记录**实际执行命令及结果**；新增测试失败必须按 §7.3 分类处置，但**分类或记录本身不能代替通过验收**。
4. **(r3 修订)** 如果**环境问题**导致全量测试无法成功运行，必须明确标记为**阻断项**，不得宣称满足 DoD。
5. **(r3 修订)** 未解决的测试失败、无法完成的必要验证或证据不足，**不得静默转化为「通过」**。
6. **(r4 修订)** 测试修订未越界：变更仅涉及 §4.3.1 列出的 3 个文件与对应测试 ID；未擅自修改共享 fixture / 辅助函数默认值 / 既有断言 / 无关用例；如确有超出清单的修改，均已取得**单独批准**并有记录（§7.6）。
7. 架构文档审计**限于 §4.1.1 七项范围**：范围外历史债务已**单独登记**，未被纳入本阶段修改。
8. **(r3 修订)** **IS4 架构文档审计证据**：
   - §4.1.1 七项范围中的**每一项**均须记录核验结论及证据来源；
   - **必要修正**和**一致性补充**均须有对应的**可核验证据**；
   - 如果发现与冻结契约冲突的问题但**未获修改授权**，必须记录为**未解决事项**，不能仅因「没有继续修改」就宣称 IS4 完成；
   - 范围外历史债务应单独登记，不得自动纳入本阶段修改。
9. `docs/ARCHITECTURE.md` 与实际实现一致：IS4 的**必要修正**与**一致性补充**全部完成，且不再存在与冻结契约冲突的表述。
10. `PHASE3_4_LOG.md`、`PHASE3_4_CLOSURE_REPORT.md`、`PROJECT_STATE.md`、`README.md` 状态一致；冻结契约未被修改（blob 哈希一致可核）；测试与冻结契约的冲突（若有）均已报告并记录，未按测试预期静默处理（§2.2 / §7.3）。
11. 零 schema 变更、DTO 兼容、Query 只读护栏、既有筛选语义、CLI 输出、**`display_name` 搜索匹配语义**均保持不变。
12. 若本阶段**无生产代码变更**，Closure Report 显式声明「仅核验 + 文档 + 测试」及其依据（§1.4-3）。
13. 零功能增量**不豁免**：验证、验收标准与证据要求逐项照常适用（§1.4-4）。
14. Step 0 的核验结果按 §6.1 记录（先入执行报告/对话，未在授权前写入仓库文档）。
15. 阶段**未**因本契约自动关闭；是否关闭、是否打 tag 由用户在验收后决定（`WORKFLOW.md` §6.2、§7；§0.3 G-3）。

---

## 9. 开放问题与用户决策点

| ID | 问题 | 影响的选项 | 建议（**非结论**） |
| :--- | :--- | :--- | :--- |
| **Q1** | 是否接受 §1.4 的「零功能增量」为合法交付形态 | 决定 Step 2 是否被触发；决定阶段性质 | 接受（与用户决策 1 一致） |
| **Q2** | **(r3 修订)** 若 T-A1 / T-A2 / T-B / T-C 失败的处置 | **正式方向已确定**：以 §7.3 的五类分类和 §7.6 的授权边界作为正式处置流程。**分类结果本身不授予**额外的生产代码或测试代码修改权限；对于不属于既定测试修正授权的改动，必须先报告并等待用户**单独批准**。**「用户确认处置流程」不等于对所有后续修复的预先授权。** | 按 §7.3 + §7.6 执行；流程确认 ≠ 修复授权 |
| **Q3** | 是否批准 §4.3 的文件范围 | 决定允许的 diff 面 | 按 §4.3 批准（生产代码默认不在范围） |
| **Q4** | `display_name` 搜索语义的「细化」具体指什么 | (a) 行为变更（如「覆盖后旧 `name` 不再命中」）→ **属新增能力**，须走 `PHASE3_0_CONTRACT.md` §16；(b) 仅指「记录并验证现行 `name` **或** `display_name` 语义」→ 文档 + 测试工作 | 倾向 (b)：不改搜索行为 |
| **Q5** | `--type` 不做取值校验是否有意 | **方向固定为「仅记录」**：记录行为与证据，**不**增加 `choices` 或其它校验，**不**改退出码 / 错误输出 / 查询结果语义 | 维持「仅记录」；不得扩展为实现任务 |
| **Q6** | 是否正式定义 Resource Taxonomy | 用户决策 3 已定「暂缓」；正式定义须走 §16 | 维持「暂缓」 |
| **Q7** | `ARCHITECTURE.md` 的 Favorite-Collection 过时表述（D3）是否在本阶段修正 | 属 IS4「必要修正」 | 建议修正（与冻结契约冲突） |
| **Q8** | 是否需要先采集真实使用证据（U1/U2） | U1 / U2 仍 **OPEN** | 3.4 **不含**取证扩范围；如需扩展应另立需求验证轮 |
| **Q9** | 关闭轮的 Git 授权范围（G-3） | commit / annotated tag | 收尾前**单独**请求授权 |
| **Q10** | **(r3 修订)** 架构文档**范围外**历史债务的登记位置 | **采用方案 (a)**：范围外历史债务**首先登记到 `PHASE3_4_LOG.md` 的待办区**；记录「发现位置 / 问题描述 / 证据 / 为何超出本阶段范围 / 建议的后续处理方向」；**不得因登记债务而扩大本阶段实施范围**；**只有**事项确实影响项目基线、阶段依赖或正式状态时，才**建议**同步 `PROJECT_STATE.md`，且同步仍须遵守该文件的修改授权 | 方案 (a) |
| **Q11** | 若 T-B 第 4 项（旧 `display_name` 仍在索引中）失败 | 属 §7.3 第 1 或第 5 类，须暂停并等待单独批准；**不得**自行修复索引同步 | 按 §7.3 处置，不预设结论 |

---

## 10. 与 Phase 3.5 的边界

| 归属 | 内容 | 出处 |
| :--- | :--- | :--- |
| **3.5** | Tag / Favorite 的 GUI 入口与管理 UX（浏览、打标、收藏按钮、标签管理界面）、最终 UX、startup eager system-tag bootstrap 接线 | 3.3 契约 §15 |
| **3.5 不得** | 另建并行的 CLI 筛选入口；如需变更，应在既有 `--tag` / `--favorite` / `--no-favorite` 上修改 | 3.3 契约 §15 |
| **3.4 不得** | 触及 `ui/**`；把 GUI 相关测试或控件改动作「顺手」纳入 | 本契约 §4.2-7；3.3 契约 §15 |
| 交接口径 | 3.4 交付的 CLI 只读入口语义（`--tag` 名称精确解析、未命中 exit 1、`scope` 只输出提供的键）在 3.5 必须**保持兼容** | 3.3 契约 §3.3 / §3.5 / §6.5 |

---

## 11. 用户批准条款与冻结状态

以下为冻结时记录的批准条款；未列入 §12 批准清单的事项不得视为已批准。

**冻结状态（2026-10-17）**：下列条款已按 §12 Freeze Record 记录的用户裁决冻结；未列入批准清单的事项不得视为已批准。

**A. 三个独立闸门（§0.3）——G-1 已完成；G-2 / G-3 未授权**

1. **G-1 契约冻结**：**已完成（2026-10-17）**。**冻结不自动授权实施。**
2. **G-2 实施授权**：契约冻结后，是否另行授权 Codex 实施 Phase 3.4。
3. **G-3 Git 收尾授权**：验收通过后，是否另行授权 commit / tag / 其他 Git 写操作。

**B. 范围与内容**

4. **§1.1 / §1.2**：阶段名称与内容性质（核验 + 文档 + 测试）。
5. **§1.4**：零功能增量为合法交付形态，且**不豁免**必要验证与验收。
6. **§4.1**：In Scope 的 IS1–IS7。
7. **§4.1.1**：`ARCHITECTURE.md` 一致性审计的**七项范围**与「范围外债务单独登记」规则。
8. **§4.2**：Non-Goals 第 1–15 项（尤其第 2、4、5、6、7、13、15 项）。
9. **(r4 修订)** **§4.3 / §4.3.1**：文件范围与**穷尽式测试文件清单**（3 个文件 + 对应 T-ID）；生产代码默认不在范围，仅在 IS3 单独批准后开放；未列出的测试文件、新增测试文件、修改既有测试结构均须另行批准。

**C. 流程与测试**

10. **(r4 修订)** **§2.2 / §6 / §6.1 / §6.2**：冻结契约优先级、实施顺序、Step 0 记录方式（只入执行报告/对话）、以及 §4.3 / §6 / §7.6 的授权口径统一。
11. **(r4 修订)** **§7.2**：待补充测试 T-A1（双路径独立证明）/ T-A2 / T-B（独立临时库与索引级四项断言）/ T-C / T-E，含**唯一位置（§4.3.1）**、资源隔离与 skip 政策。
12. **(r4 修订)** **§7.3**：测试失败的五类分类与处置流程（含「尚不能分类」、测试自身问题不自动获得修改权、Step 2 不构成修复授权、冻结契约优先于测试预期）。
13. **§7.6**：测试修订授权边界（含共享 fixture / 辅助函数 / 既有断言 / 新增测试文件的单独批准要求）。
14. **§7.5**：验收证据口径。

**D. 开放问题**

15. **§9** Q1–Q11 的处置方向（**已于 2026-10-17 按 §12 Freeze Record 冻结**：Q1 / Q3 / Q4(b) / Q7 为此前批准；Q2 / Q5 / Q8 / Q10 / Q11 为本轮批准；Q6 沿用用户决策 3；Q9 属后续 G-3）。
16. **§10**：与 3.5 的边界，以及 3.4 不新增 GUI / 语法 / DTO / 排序能力的承诺。

---

## 12. Freeze Record

```text
Design Review（本草案）      → 完成（r0–r6：DRAFT / CANDIDATE）
最终审批草案                 → r6 · DRAFT
批准草案内容 SHA-256          → 6C0A4893CFB5A4E073E6DE3347FE9D0EF871EB80F8BE1ACB745A4E517C28498A
用户冻结授权                 → 【已授权】（2026-10-17）
Freeze Record 创建           → 完成（本记录，r7）
Implementation Contract      → FROZEN
Phase 3.4 implementation     → 未开始（G-2 未授权）
Phase 3.4 CLOSED             → 未达成
```

**本轮（r7）记录的批准事项**

- **本轮批准**：§11-4、§11-6、§11-7、§11-8、§11-10、§11-11、§11-12、§11-13、§11-14、§11-16、Q2、Q5、Q8、Q10、Q11。
- **此前已批准**：Q1、Q3、Q4(b)、Q7、C2、C3。
- **Resource Taxonomy**：维持此前决定，暂缓正式定义（用户决策 3）。
- **G-1 冻结不自动授权 G-2 实施。**
- **G-3 的 tag、push 等操作仍须单独授权。**

**冻结依据与边界**

- 依据：`docs/WORKFLOW.md`（§7 Git 授权、§8 阶段状态）、`docs/PROJECT_STATE.md` §2.2 权威顺序、`docs/phase3/PHASE3_0_CONTRACT.md` §15/§16，以及 Phase 3.3 §19 的冻结记录格式。
- 冻结范围：仅冻结本契约的内容与范围；不修改 Phase 3.0 / Phase 3.3 冻结契约，不改变 §4 授权清单，不授权生产代码修改或 Phase 3.4 实施。
- 按已批准的 C2：`PROJECT_STATE.md` / `README.md` / `ARCHITECTURE.md` 的状态行同步属 IS6 收尾轮，本次不执行。

**自引用说明**：本 Freeze Record 与 FROZEN 状态随同一次提交入库，因此不内嵌该提交自身的 hash；此处记录的是**批准草案内容**的 SHA-256（`6C0A…`）。冻结提交的 hash 由提交后的执行报告承担（本轮不同步 `PROJECT_STATE.md`）。

---

## 附录 A：证据来源（r0 轮只读命令；r1–r7 轮未重跑）

```
git rev-parse HEAD / phase-3.3-closed^{commit} · git status --short · git diff --stat
rg -n "^def test_|^class Test" tests/*.py（覆盖映射）
rg -n "display_name" tests -g "*.py"（缺口 A）
rg -n "resources_fts" tests -g "*.py"（缺口 B）
rg -n "set_resource_type|type_source" tests -g "*.py"（缺口 C）
rg -n "resource_type=" tests -g "*.py"（类型筛选覆盖范围）
rg -n "core/query|Query Model|type_source|Favorite" docs/ARCHITECTURE.md（D1/D2/D3 定位）
Get-Content core/query/{model,browse,queries,search,card_format,property_map}.py ·
            core/app/resource_write.py · core/scanner/store.py ·
            core/database/{schema,db}.py · cli_query.py
python -c "sqlite3 immutable=1 只读打开持久库"（resources=0 / tags=0）
```

## 附录 B：边界合规核对

**r3 轮**

| 禁止项 | 状态 |
| :--- | :--- |
| 创建或修改本文件之外的任何仓库文件 | ✅ 未做 |
| 重新调查仓库 / 重新运行测试 | ✅ 未执行 |
| Git 写操作（add / commit / tag / push / reset / checkout / clean） | ✅ 未执行 |
| 创建 / 移动 / 删除 / 修改 tag | ✅ 未执行 |
| 修改功能代码、测试代码、数据库或其他项目文档 | ✅ 未做 |
| 修改冻结契约 | ✅ 未做 |
| 冻结契约 / 改变阶段状态 / 进入实施阶段 | ✅ 未做 |
| 扩大 Phase 3.4 功能范围 | ✅ 未做 |
| 把建议写成已批准决策 | ✅ 未做（全文 DRAFT / [需批准] / 【推断】/【未决】） |

---

# r1 → r2 修订摘要（历史保留）

| 修订项 | 落实章节 | 具体处理 |
| :--- | :--- | :--- |
| 1. 收紧测试修改授权边界 | §7.6（新增）、§4.3、§7.3、§8、§11 | 默认仅允许在已批准测试文件中新增/修正本阶段用例；禁止擅改共享 fixture、辅助函数默认值、既有断言、无关用例；须先报告并等待单独批准；不得为通过而改预期、削断言或规避失败。 |
| 2. 强化 T-B 的 FTS UPDATE 同步验证 | §7.2「T-B 详细规格」、§9-Q11 | 要求直接检查 FTS 的 `display_name` 字段；四项必证断言；旧/新展示名与 `name` 明显不同；column-specific 条件；区分「旧 `name` 仍命中」与「旧 `display_name` 残留」。 |
| 3. T-A1 / T-A2 资源隔离与断言 | §7.2 表 | T-A1 断言覆盖后可命中；T-A2 记录 `name OR display_name` 语义并断言旧 `name` 仍命中；禁止把「旧名失效」作为验收要求。 |
| 4. 限定 ARCHITECTURE.md 一致性审计范围 | §4.1-IS4、§4.1.1、§4.2-15、§6、§8、§9-Q10 | 七项必核范围；其他章节仅在与范围或冻结契约直接冲突时修正；范围外债务单独登记。 |
| 5. 澄清 Step 0 核验结果记录方式 | §6.1、§6、§8 | 结果先入执行报告/对话；不改仓库文件；不提前更新实施日志。 |
| 6. 统一测试失败分类与停止条件 | §7.3、§7.6、§6、§8 | 五类分类（含「尚不能分类」）；证据不足不得强行归类；疑似生产缺陷须单独批准。 |

# r2 → r3 修订摘要

| 修订项 | 组别 | 落实章节 | 具体处理 |
| :--- | :--- | :--- | :--- |
| 1. 测试失败分类后不自动获得修改授权 | G1 | §7.3（步骤 3–7）、§7.6（第 6–8 条）、§6.2（新增）、§4.3（测试文件行） | 明确「分类结果本身不授予修改权」；「测试自身问题」须同时满足四项条件才可在现有授权内修正；其余情况先报告并等待单独批准；环境/契约未定义/尚不能分类不得靠改测试预期规避；生产修复须针对具体问题与文件范围单独批准，Step 2 不构成授权。 |
| 2. T-A1 独立证明 FTS 与 LIKE 两条路径 | G1 | §7.2 T-A1 | 两条路径都须验证覆盖后的 `display_name` 搜索命中；各自独立断言结果集合恰好包含目标资源；强制关闭 FTS 时须确认实际执行 LIKE 回退；禁止把旧 `name` 命中当作成功；禁止凭长度推定路径。 |
| 3. T-B 直接验证 FTS `display_name` 索引同步 | G1 | §7.2「T-B 详细规格」 | 独立临时库；旧/新展示名与 `name` 明显不同；经 `ResourceWriteService.set_display_name` 实际更新；更新前后均用列限定的 `display_name` 条件直查索引并核对 rowid；保留四项独立断言；旧 `name` 经 Query Layer 命中属现行语义，不得判为缺陷；仅环境确实不支持 FTS 才 skip。 |
| 4. §4.3 / §6 / §7.6 授权口径一致 | G1 | §4.3、§6.2（新增）、§7.6（第 1–3 条） | 「已批准测试文件」以最终冻结契约 §4.3 清单为准（r4 起为 §4.3.1）；新增测试文件、扩大范围、修改既有结构均须批准；Step 2 仅为条件性执行顺序。 |
| 5. §8 全量测试阻断条件与 IS4 证据要求 | G2 | §8 第 3–5、8 项 | 全量测试须成功并记录命令与结果；分类/记录不替代通过；环境导致无法全量运行须标记阻断；未解决失败不得静默转为通过；IS4 七项逐项记录结论与证据，未获授权修改的冲突记为未解决事项。 |
| 6. §9-Q2 / §9-Q10 方向确定 | G3（Q2）· G4（Q10） | §9-Q2、§9-Q10 | Q2：§7.3 + §7.6 为正式流程，分类不授权，确认流程 ≠ 预先授权修复。Q10：采用方案 (a)，范围外债务先入 `PHASE3_4_LOG.md` 待办区，仅在影响基线/依赖/正式状态时建议同步 `PROJECT_STATE.md`。 |
| 7. 版本与状态 | G5 | 标题与元信息 | 标为 `r3 · DRAFT`；保持阶段目标、范围、Non-Goals、3.5 边界、Taxonomy 暂缓与 G-1/G-2/G-3 不变。 |

> **计数核对（r4 修订，P3）**：上表共 **7 行**，对应 **G1–G5 五个组别**。其中 G1 覆盖第 1–4 行，G2 覆盖第 5 行，G3 与 G4 共用第 6 行（分别为 Q2 / Q10），G5 覆盖第 7 行。故「五组修订」与「7 个列出的修订项」并不矛盾，二者按上表一一对应。

# r3 → r4 修订摘要

| 修订项 | 落实章节 | 具体处理 |
| :--- | :--- | :--- |
| P1. 明确测试文件授权范围 | §4.3、§4.3.1（新增）、§7.2、§8 第 6 项、§11 第 9/11 项 | 以穷尽式清单锁定 3 个测试文件与对应 T-ID（`tests/test_search_core.py` → T-A1/T-A2；`tests/test_database_schema.py` → T-B；`tests/test_query_model.py` → T-C）；取消「或新建 focused 文件」「或另一文件」等可选表述；未列出的文件不在授权范围；新增文件或改既有结构须另行批准。 |
| P2. 明确冻结契约优先级 | §2.2、§7.3（判断基准 + 分类 1/2 + 步骤 3）、§7.6 第 9 条、§8 第 10 项、§11 第 10/12 项 | 冻结契约为范围与行为的最高依据；测试仅为验证证据，不得推翻契约；测试预期与契约冲突时不得自动改实现或契约；其他文档 / 历史说明 / 测试意图不得高于契约。未放宽生产代码修改权限。 |
| P3. 修正修订数量不一致 | §3.5、文末「r2 → r3 修订摘要」 | 统一表述为「五组修订、7 个列出的修订项」，并在表中增加「组别」列，给出 G1–G5 与第 1–7 行的对应关系；G3/G4 共用第 6 行的事实已显式说明。 |

# r4 → r5 修订摘要

| 修订项 | 落实章节 | 具体处理 |
| :--- | :--- | :--- |
| P1. 文件限制适用范围 | §2.2 | 记录用户 2026-10-17 的确认：Phase 3.3 §10.2 文件限制只约束 Phase 3.3 自身、不自动延伸；不修改 `PHASE3_0_CONTRACT.md`、不授权超出 §4.3 的修改；§17 第 7 项仅列为同构先例而非通用规则明文；不得扩大解释为其它限制或冻结决策的豁免。 |
| P2. 修订记录一致性 | §0.2、§3.0、§3.1、§3.5、附录 A、版本元数据 | 统一 r4 计数为「3 项内容修订 + 版本元数据」；补齐 r1–r5 测试状态口径（未运行，依据各轮执行记录、未由仓库独立核实）；新增 r5 计数与元数据说明。 |
| P3. 冻结契约冲突处理 | §2.2 第 5 条、§7.3 步骤 5a / 7 | 明确冻结契约实质冲突时暂停并报告（冲突原文、已完成检查、可行选项、待用户决定事项）；不得自行修改任一冻结契约；不得因测试失败 / 测试意图修正 / 测试分类获得隐含的生产代码修改权限；不得削弱既有断言。 |
| 版本元数据 | 文档头、§0.2、§2.1 | 标为 `r5 · DRAFT`；修订自 r4；r5 为 r4 的最小修订版；§0.2 轮次边界与 §2.1 版本行一并更新。版本元数据不计入内容修订项。 |

# r5 → r6 修订摘要

| 修订项 | 落实章节 | 具体处理 |
| :--- | :--- | :--- |
| P1. 修订记录补齐 | §3.5、文末「r4 → r5 修订摘要」 | 在 r4/r5 的版本元数据说明中补充 §0.2、§2.1；在 r4→r5 的 P2 行补充附录 A；只记录实际发生的位置，未新增变更项。 |
| P2. 历史事实证据状态 | §2.1（文件清单表下方陈述） | 保留「r3 创建前由只读核验确认」的历史含义，同时标注该事实目前无法仅凭本文件独立核实；未改写为已证实或已否定。 |
| 版本元数据 | 文档头、§0.2、§2.1 | 标为 `r6 · DRAFT`；修订自 r5；r6 为 r5 的最小修订版。版本元数据不计入内容修订项。 |

# r6 → r7 冻结记录

| 项 | 落实章节 | 具体处理 |
| :--- | :--- | :--- |
| G-1 冻结 | 文档头、§0.2、§0.3、§11、§12（新增） | DRAFT → FROZEN；记录用户批准事项；新增 Freeze Record |
| 测试状态口径 | 文档头、§3.0、§3.1、§3.5、附录 A | 补齐 r1–r7 / r0–r7；冻结轮未运行测试 |
| Freeze Record | §12 | 记录批准草案内容 SHA-256、G-2/G-3 边界、C2 状态同步安排 |
