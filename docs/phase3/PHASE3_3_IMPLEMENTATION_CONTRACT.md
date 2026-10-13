# Phase 3.3 — Implementation Contract（Search & Query Foundation）

> 文档类型：**Phase 3.3 Implementation Contract —— FROZEN（已冻结；用户确认见 §19）**
> 日期：2026-10-12
> 权威层级（从高到低）：
> 1. `docs/phase3/PHASE3_0_CONTRACT.md`（Phase 3 首期 Architecture / Scope Contract，最高权威）
> 2. `docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md`（Search & Taxonomy 设计评审）
> 3. `docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md`（Tag System，FROZEN / PASS）
> 4. 本文件 —— Phase 3.3 Implementation Contract（**FROZEN**，2026-10-13），**不得与上级冲突**
>
> 前置：Phase 3.2 = CLOSED / PASS（tag `phase-3.2-closed` → `034a726`；实现 commit `841865d`）
>
> 起草轮次（r0–r3）：**只做契约规划**。未修改任何功能代码 / schema / migration / 测试 / CLI / GUI；
> 当时未冻结本契约、未创建 commit / tag。
>
> 冻结：**已由用户确认（2026-10-13）**；冻结内容由 commit `a73438e`（r3，897 行）固定，
> Freeze Record 见 §19。**冻结 ≠ 实施授权**：Phase 3.3 功能实施需另行授权。

> **修订记录**
> - r0（2026-10-12）：初稿（DRAFT / CANDIDATE），§3 的入口问题标记为待用户裁决。
> - r1（2026-10-12）：用户已裁决采用 **Option B**（最小 CLI 只读入口）。本版据此修订：
>   §3 由「待裁决」改写为「已批准」；`--tag` 统一定义为**标签名称**（不再声称接受 ID）；
>   `BrowserScope.filters()` 改为**委托** `to_filter().to_params()`；
>   `883 passed` 由验收门槛降级为**参考基线**；未冻结条款统一标注为「候选」；
>   同步 §15 的 Phase 3.5 边界与 §6.5 的 CLI 语义。**仍不冻结、不实施。**
>   （注：r1 的"委托"方向已在 r2 第二轮修正为**投影** —— `filters()` 是 `to_params()`
>   在 GUI 键集上的子集，见 §5；该行保留为历史记录，不代表现行条款。）
> - r2（2026-10-12）：**同一版本的两轮连续修订**（尚未冻结、尚未审核通过）：
>   **第一轮（Option B 审计修订）** —— 将 CLI 只读入口确立为 Scope / 步骤 / 测试 / DoD 的
>   **必做项**（§0 / §1.2-6 / §11 Step 5 / §12 T-O·T-P·T-S / §13-9）；按**真实 CLI 实现与既有测试**
>   明确 `--tag` 的退出码、输出与 JSON 行为（§3.5）；补充 `count` / `list` 为 **keyword-only**
>   的签名事实与 `game`/`card_marker` 待核实项（§4.6）；收敛重复不变式（T-D / T-E / T-R）；
>   §15 移除 Phase 3.5 的 CLI 入口责任；§17 / §18 增补"未发现真实冲突"的核对结论。
>   **第二轮（一致性修订）** —— 新增 §6.6 区分「`to_params()` 的 15 键 Query 参数集」与
>   「CLI JSON `scope` 对外输出」（`scope` 仅在实际提供时加入 `tag_id` / `favorite`，
>   不输出 `None` 键、不追加其它键）；消除 `filters() == to_params()` 的键集矛盾
>   （改为 `FILTER_KEYS` 14 键**投影**，见 §5 / §4.3）；§6.5 明确 CLI 新旧参数合并规则
>   （只取新增两项，禁止整表展开）；§12 **T-C** 写明排序依据并改为显式 `order_by`/`descending`；
>   修订 **T-K / T-L** 与 §13-4 的验证方式（运行时行为用自动化测试，结构性约束允许
>   代码审查等可核验证据，不引入脆弱的源码文本匹配测试）；§6.4 补 §4.4 规则与 T-D / T-E / T-F
>   的对应；附录 B 版本标注更正为 **r2**。**上述两轮均未冻结、未审核、未实施。**
> - r3（2026-10-12，冻结前最小文本修订，仅处理终审前只读审查报告的非阻断项）：
>   **N1** §10.1/§10.2 明确实施 / 收尾阶段的文档产物（`PHASE3_3_LOG.md` / Closure Report）
>   及其边界，不开放 `docs/**` 任意权限；**N2** §4.4 与 T-D 明确 `None` 合法、
>   `bool` 必须拒绝；**N3** §1.1/§2/§3.3 的"本轮任务 §一-N"改为可长期追溯的
>   「Option B 批准轮次 §一-N」；**N4** §6.1 精确区分 Favorite 判据（谓词一致）与
>   外层查询形态（correlated EXISTS vs `SELECT 1 … LIMIT 1`）；**N5** §8 明确只读性证据
>   的测量层（Query 层连接级 `total_changes`；CLI 层文件 SHA-256）；
>   **N7** §13-4 明确覆盖 T-A 至 T-S 全部不变式；**N8** §4.6 说明参数列举顺序不代表签名顺序
>   （全部 keyword-only）。**N6（Git 跟踪）不在文本修订范围。仍未冻结、未实施。**
> - r4（2026-10-13，**冻结记录补齐**；**仅状态元数据，未改动任何实质性契约条款**）：
>   头部状态标记改为 **FROZEN**；§19 Freeze Record 补齐（用户确认日期、冻结内容 commit
>   `a73438e`、自引用说明）；术语约定更新为"候选条款自冻结记录完成起成为冻结条款"；
>   附录 B 同步标注（起草/修订轮次的范围限定与"冻结由后续轮次完成"）。
>   历史条目（r0–r3）中的"未冻结 / DRAFT / CANDIDATE"为**当时状态**，不代表现行状态。

> **状态声明**：本文件已 **FROZEN** —— 用户于 2026-10-13 确认冻结，
> 冻结内容为 r3（commit `a73438e`，见 §19）。§3 的入口裁决为 **Option B**（r1，2026-10-12），
> 该处不存在待决项。
> **冻结不构成实施授权**：Phase 3.3 功能实施仍需单独授权；本文档亦不代表任何实施验收结果。

> **术语约定（r3 冻结后更新）**：§19 Freeze Record 已补齐，因此正文中标注「**候选**」的条款
> （§4–§9、§12、§16 及各处「候选定义」）**自冻结记录完成之时起成为【FROZEN】冻结条款**；
> 未标注「候选」的章节（如 §11 步骤、§13 DoD、§14 变更控制、§15 边界）同样随本次冻结生效。
> 其「必须 / 不得」的约束力自此生效，但**不构成实施授权**（实施需另行授权）。
> 正文中的「候选」一词自此为**历史标注**（表示该类条款在冻结前曾是候选），不再表示"尚未冻结"。

> **冻结声明**：本契约**已冻结**（2026-10-13，证据见 §19）。冻结范围为 Phase 3.3 的
> 范围、Query Model 定义、筛选语义、兼容性约束与测试不变式。
> 任何扩大 3.3 范围的行为，必须先走 `PHASE3_0_CONTRACT.md` §16 变更控制
> （新增评审 + 更新 Contract + 用户确认）。

---

## 0. 本阶段唯一目标

```text
在【不新增搜索语法、不改 schema、不改变既有筛选与文本搜索语义】的前提下，
把「现有的参数式资源筛选」正式化为一个不可变的 Query Model，
并把 Phase 3.2 已交付的 Tag / Favorite 只读事实接入同一条查询路径，
使 Query / Browse 具备 additive 的只读标签筛选能力，
并按用户已批准的 Option B 在既有 CLI 命令上交付【最小只读筛选入口】。
```

交付物是 **core 查询基础（Query Model + 只读筛选）+ 既有命令上的最小只读入口**；
不是搜索语言，也不是完整 UX（Tag / Favorite 的 GUI 与标签管理 UX 不属本阶段）。

---

## 1. Scope

### 1.1 范围来源（本草案的依据）

> **引用约定（N3 修订）**：本文件所称「**Option B 批准轮次 §一-N**」，指用户于 2026-10-12
> 裁决采用 Option B 的那一轮任务中 §一 所列的已批准范围（共 6 项）。使用该描述是为了避免
> 依赖「本轮」这类随对话变化的指代；下文每条同时内联批准内容，便于长期追溯。
> 未列入该 §一 的内容（例如讨论中的建议）**不构成已批准决定**。

| # | 范围项 | 依据 |
| :-- | :--- | :--- |
| 1 | 新建不可变 `ResourceFilter` 作为正式 Query Model | 用户已批准（Option B 批准轮次 §一-1）；架构选择依据 `PHASE3_0_2` §10.2 / §13-G1 |
| 2 | Tag / Favorite 只读筛选接入 `ResourceQuery` 与 `BrowseService`，复用现有结构、零 schema 变更 | 用户已批准（Option B 批准轮次 §一-2）；`PHASE3_0_CONTRACT.md` §12-6 |
| 3 | 明确 `BrowserScope` / `ResourceFilter` / `ResourceQuery` 的唯一数据流 | 用户已批准（Option B 批准轮次 §一-3）；`PHASE3_0_2` §13-G1 |
| 4 | 既有 `query resources` 增加最小只读入口：`--tag <name>` / `--favorite` / `--no-favorite` | 用户已批准（Option B 批准轮次 §一-4：按标签名称精确筛选 / 只筛选收藏 / 只筛选非收藏）；`PHASE3_0_CONTRACT.md` §12-7（入口要求） |
| 5 | 保留现有文本搜索语义，不引入 `field:value` / AND / OR / NOT / 多标签组合 | 用户已批准（Option B 批准轮次 §一-5 / §一-6）；`PHASE3_0_2` §13-G2/G3 |
| 6 | 保持 schema v2、Query 只读护栏、DTO 向后兼容、既有筛选行为 | 用户已批准（Option B 批准轮次 §一-5）；`PHASE3_0_CONTRACT.md` §8 / §10 |
| 7 | 不新增 GUI 控件，只实现后续阶段所需的基础能力 | 用户已批准（Option B 批准轮次 §一-6）；`PHASE3_0_CONTRACT.md` §12-7（入口先后见 §3） |

入口要求（§12-6「按标签浏览」与 §12-7「至少一个入口」）的处置见 **§3**；
用户已裁定采用 **Option B**（最小 CLI 只读入口）。

### 1.2 交付能力（能力级）

1. **Query Model**：`ResourceFilter`（不可变、纯值对象、不含 SQL、不含 UI 状态）。
2. **Tag 筛选**：`ResourceQuery` / `BrowseService` 支持按**单个** Tag 只读筛选（`tag_id`）。
3. **Favorite 筛选**：支持 `favorite=True` / `favorite=False` 的只读筛选；
   语义完全由「`name_key == FAVORITE_TAG_KEY` 的保留系统 Tag 关联」定义。
4. **单一转换点扩展**：`BrowserScope` 继续是 GUI 状态的唯一装配点，并转为 `ResourceFilter`。
5. **一致性与护栏**：`count` / `list` / 分页 / 排序在新增筛选下保持一致；
   只读护栏、参数化查询、所有权护栏保持有效。
6. **最小 CLI 只读入口**（Option B，用户已批准）：在既有 `query resources` 命令上增加
   `--tag <name>` / `--favorite` / `--no-favorite`，且必须经 `ResourceFilter` 进入同一筛选路径（§3.5 / §6.5）。

---

## 2. Explicit Non-Goals（Phase 3.3 明确不做）

| # | 排除项 | 依据 |
| :-- | :--- | :--- |
| 1 | `field:value` / `tag:` / `favorite:` / 引号 / 通配符等**文本查询语法** | Option B 批准轮次 §一-5 / §一-6；`PHASE3_0_2` §13-G2/G3（超出冻结 In Scope，需另行变更控制） |
| 2 | `AND` / `OR` / `NOT` 布尔组合（文本或结构化） | 同上 |
| 3 | 多值 / 多标签组合（标签交集、并集、`IN (…)`） | 首期只做单 Tag 筛选；多值属独立评审 |
| 4 | 新增独立 Search Service / Query Parser / 倒排索引 / 外部搜索引擎 | `PHASE3_0_2` §9.2 |
| 5 | 新 DTO 字段（含把 `tags` / `is_favorite` 加入列表行） | 本期无 DTO 变更；列表行填充会产生额外查询成本，未获授权 |
| 6 | 新增 `order_by` 白名单项（按标签数 / 标签名排序等） | 未获授权；排序面保持现状 |
| 7 | 新增 GUI 控件 / 标签浏览器 / 收藏按钮 | Option B 批准轮次 §一-6（不新增 GUI 控件）；GUI 侧入口仍留后续阶段（§3.4 / §15） |
| 8 | Tag / Favorite 的**写**入口（GUI 或 CLI） | `PHASE3_2_IMPLEMENTATION_CONTRACT.md` §2-5/§2-6；写服务已在 3.2 交付 |
| 9 | Collection 相关查询（`collections` / `resource_collections`） | `PHASE3_0_CONTRACT.md` §13-5 |
| 10 | review 状态 / 重复组确认 / relocation 等持久化查询 | `PHASE3_0_CONTRACT.md` §13-6/§13-7/§13-8 |
| 11 | schema v3 / migration / 新表 / 新列 / 新索引 | Option B 批准轮次 §一-5；`PHASE3_0_CONTRACT.md` §8 |
| 12 | 修改 Scanner / Parser / 写服务 / database 层行为 | `PHASE3_0_CONTRACT.md` §2 / §9 |
| 13 | 性能优化（新索引、去 N+1、相关子查询重构） | `PHASE3_0_2` §3.3 / §9.3（未来选项，需真实基准） |
| 14 | 扩展 FTS 检索面到 `notes` / `series` / `description` / `author` 列 | `PHASE3_0_2` §8.3（列为未来选项） |

---

## 3. 契约约束核对：「按标签浏览」与入口要求（**已批准：Option B**）

> 本节如实核对冻结契约，并记录用户对入口问题的裁决结果（r1）。

### 3.1 冻结条文（摘录）

`PHASE3_0_CONTRACT.md` §12（In Scope，**能力级**，且明确"不写死子阶段编号与顺序"）：

```text
6. 按标签浏览：Query / Browse 增加只读标签筛选（additive）。
7. 至少一个入口（CLI 与/或 GUI）：入口先后顺序为未决项（§14-OPEN-EVIDENCE）；
   GUI 必须消费写服务，不得写 SQL。
```

相关既有事实（均已核对）：

- `PHASE3_0_CONTRACT.md` §15：本 Contract **不决定**子阶段编号（3.1 / 3.2 / 3.3）与实施顺序。
- `PHASE3_2_IMPLEMENTATION_CONTRACT.md` §2-6 / §17-6：3.2 **不得**修改 `main.py` /
  `cli_query.py` / `ui/*` 以提供 Tag UX，并声明「入口属 Phase 3.5」。
- `PHASE3_1_IMPLEMENTATION_CONTRACT.md` §5.3：已存在 `resource set-*` 的
  「CLI 只读解析 + 写服务」入口范式（既有先例）。
- `PHASE3_0_2` §11：建议 3.3 引入 Query Model + tag filter；入口建议「先 CLI 验证 API 再 GUI」。

### 3.2 核对结论（事实）

1. §12-6 是**能力要求**（Query / Browse 具备只读标签筛选），由本契约 §1.2 / §6 覆盖。
2. §12-7 是 **Phase 3 首期整体**的入口要求（"至少一个入口"）；3.2 曾把 Tag / Favorite 的
   写入口与最终 UX 留给 3.5。
3. r0 曾据此登记一处**排期归属歧义**：读侧的标签浏览入口没有任何阶段承接
   （3.2 交给 3.5、3.3 未定义），且 §12-7 当时只被 3.1 的 `resource set-*`（写侧）部分满足。
4. **该歧义已由用户于 2026-10-12 裁决：采用 Option B** —— 3.3 在交付 core 能力的同时，
   交付**最小 CLI 只读筛选入口**，使 §12-7 在读侧得到满足；GUI 侧入口仍归后续阶段（§3.4）。
   本版据该裁决改写本节，**不再存在待裁决的入口选项**。
5. 依据链保持可追溯：§12-6 / §12-7 / §16（变更控制），以及 3.2 §1.1 / §4.5 / §7.4 / §10 的约束，
   逐条登记于 §17 与附录 A。

### 3.3 已批准的入口方案：Option B（最小 CLI 只读入口）

**状态：用户已批准（2026-10-12）。本项属于 Phase 3.3 Scope（§1.2-6）。**

在既有 `query resources` 命令上追加**可选、只读**参数；不新增子命令、不新增模块、
不引入 SQL（CLI 仍是薄适配层）：

```text
python main.py query resources [既有参数] --tag <name> [--json]
python main.py query resources [既有参数] --favorite [--json]
python main.py query resources [既有参数] --no-favorite [--json]
```

- `--tag` 接受**标签名称**（见 §3.5 / §6.5），**不接受** tag id；
- `--favorite` / `--no-favorite` 互斥（沿用既有 `--with-mods` / `--without-mods` 使用的
  `add_mutually_exclusive_group` 风格）；
- **不新增 GUI 控件**：`ui/**` 不改（满足 Option B 批准轮次 §一-6）；
- JSON payload 的 `scope` 仅在提供新参数时增加 `tag_id` / `favorite` 键；既有输出字段不变。

### 3.4 保留的边界（不做的事）

```text
3.3 提供 CLI 只读筛选入口；
Tag / Favorite 的 GUI 浏览、管理 UX 与最终用户界面仍属后续阶段（§15）。
```

因此 §2-7（不新增 GUI 控件）与 §2-8（不做 Tag / Favorite 写入口）不受本裁决影响。

### 3.5 CLI 参数语义（候选定义；已按真实实现与既有测试核对）

1. `--tag <name>`：**仅**按标签名称筛选（不接受 id）。
2. 解析经既有 `TagQuery.find_by_name(name)`（源码核对 + 3.2 §7.2 / 设计文档 §13.3）：

```text
name_key = (name or "").strip().casefold()
命中条件 = tags.name_key 精确相等；大小写不敏感
空 / 纯空白 / 非字符串 → 归一化后为空 → 返回 None
非模糊、非前缀、非分词、非 LIKE
```

3. 解析成功 ⇒ `tag_id = TagSummary.id` ⇒ 交给 `ResourceFilter(tag_id=...)`（§6.5）。
4. 解析失败（`None`）⇒ 走**既有 not-found 约定**（源码 `cli_query._not_found`；测试
   `tests/test_query_cli.py::test_query_not_found_is_not_traceback` 锁定了同型行为）：

```text
stderr 输出:  Tag not found: <name>
退出码:       1
stdout:       不输出任何内容（含 --json）
后续:         不执行任何查询
```

   理由：`--tag` 的值是**用户提供的查找键**，与既有 `query resource <target>` /
   `query mod <guid>` 同类；既有约定对"查找键无法解析"用退出码 1，而不是参数错误。
5. `--favorite` ⇒ `favorite=True`；`--no-favorite` ⇒ `favorite=False`；都不给 ⇒ `favorite=None`。
6. 新参数与既有筛选参数为 **AND** 组合（可如 `--tag X --favorite --type character_card` 同用）。
7. 其余退出码约定**保持不变**（源码 + 既有测试核对）：

```text
0  成功；没有匹配结果也算成功
   · 文本模式输出 "(no results)"（既有 test_query_empty_result_is_success）
   · --json 模式仍输出 payload：{"count": 0, "scope": {...}, "resources": []}
     （payload 的 "count" 是【本页返回行数】，不是总数；既有行为不变）
1  查找键无法解析（not found；见第 4 条）
2  参数 / 取值错误：如 --game XXX、--order bogus、--category bogus
   （Query 层抛 ValueError ⇒ dispatch_query 打印 "参数错误：…" 到 stderr 并返回 2；
     既有 test_query_argument_errors_exit_2）
```

8. 与 Query 层的分工不要混淆：Query 层对**未知 tag_id** 返回空集且不抛异常（§4.4）；
   "标签名称无法解析"是 **CLI 层**的 not-found 结果。两者语义不同、互不矛盾：
   CLI 先解析名称，因此用户通常看到的是退出码 1，而不是空结果。
9. **不新增**任何退出码语义、不新增 `--json` 字段、不改变 `(no results)` 文案。

---

## 4. Query Model —— `ResourceFilter`（候选定义）

### 4.1 定位

```text
ResourceFilter = 「一次资源筛选条件」的不可变值对象（Query Model）
```

- **纯值对象**：frozen dataclass；不持有连接、不执行 SQL、不含 UI 状态（选中态 / 视图 / 排序）。
- **唯一条件载体**：core 层表达「筛选什么」的正式类型；`BrowserScope` 与 CLI 参数都编译为它。
- **不是执行器**：SQL 仍**只**由 `core/query/queries.py::_resource_where` 构造
  （**不得**出现第二个 SQL 条件构造点）。

### 4.2 字段（候选）

字段与 `ResourceQuery.count/list` 的筛选参数**一一对应**（含 `card_marker`），默认值全部为 `None`：

| 字段 | 类型 | 默认 | 说明 |
| :--- | :--- | :--- | :--- |
| `query` | `str \| None` | `None` | 文本检索词（既有语义不变） |
| `resource_type` | `str \| None` | `None` | 既有 |
| `game` | `str \| None` | `None` | 既有（→ `card_marker`） |
| `card_marker` | `str \| None` | `None` | 既有（core 层，GUI 未暴露） |
| `library_id` | `int \| None` | `None` | 既有 |
| `scan_status` | `str \| None` | `None` | 既有 |
| `needs_review` | `bool \| None` | `None` | 既有 |
| `has_mods` | `bool \| None` | `None` | 既有 |
| `has_missing_mods` | `bool \| None` | `None` | 既有 |
| `mod_guid` | `str \| None` | `None` | 既有 |
| `plugin_guid` | `str \| None` | `None` | 既有 |
| `author_id` | `int \| None` | `None` | 既有 |
| `property_category` | `str \| None` | `None` | 既有 |
| **`tag_id`** | `int \| None` | `None` | **新增**：单个 Tag 的 surrogate id |
| **`favorite`** | `bool \| None` | `None` | **新增**：`True` 仅收藏 / `False` 仅非收藏 / `None` 不筛选 |

排序（`order_by` / `descending`）与分页（`limit` / `offset`）**不属于** `ResourceFilter`。

> **字段集已与实际签名核对**（见 §4.6）：`ResourceQuery.count` 与 `ResourceQuery.list`
> 当前各接受 13 个筛选参数，与上表前 13 行一致；后 2 行为本阶段新增。

### 4.3 方法与行为（候选）

```python
@dataclass(frozen=True)
class ResourceFilter:
    ...
    def to_params(self) -> dict[str, object]: ...
```

- `to_params()` 返回的键集 == §4.2 全部 15 个字段（13 既有 + 2 新增），值可为 `None`；
  可直接用于 `ResourceQuery.count(**f.to_params())` /
  `list(**f.to_params(), order_by=..., limit=..., offset=...)`。
- 该 15 键集合是**内部 Query 调用接口**，**不是**对外输出契约：
  CLI 的 JSON `scope` 另按 §6.6 的独立规则构造，两者**不得**混为一谈。
- GUI 也只使用该 15 键中的**子集**（`BrowserScope.FILTER_KEYS`，14 键）；
  投影规则与"为什么少一个 `card_marker`"见 §5（职责边界与键集差异表）。
- **不提供** `to_sql()` / `to_where()` 等任何 SQL 出口。
- **不提供**文本语法解析（`parse()` / `compile()` 一律不在本阶段）。

### 4.4 参数验证（候选）

- `tag_id`：`None` **合法**（表示不启用 Tag 筛选）；`int` 合法；
  **`bool` 即使本身是 `int` 的子类，也必须拒绝** ⇒ `TypeError`；其它非 `int` 值 ⇒ `TypeError`。
- `favorite`：`None` **合法**（表示不启用 Favorite 筛选）；`True` / `False` 合法；
  其它任何值 ⇒ `TypeError`。
- 其余字段沿用既有行为：**不新增**校验（保持与 `ResourceQuery` 现状一致，避免行为漂移）。
- **未知 / 不存在的 `tag_id`** ⇒ 空结果，**不抛异常**
  （与 `TagQuery.resource_ids()` 对未知 Tag 返回 `[]` 一致）。
- `favorite=True` 在「系统 Tag 尚未 bootstrap」的库上 ⇒ 空结果，**不抛异常**
  （与 `TagQuery.is_favorite() == False` / `system_tags() == []` 一致；见 3.2 Contract §4.4 lazy bootstrap）。

### 4.5 模块与依赖方向（候选）

```text
新增：core/query/model.py      （ResourceFilter；仅依赖标准库）

依赖方向（单向，禁止反向）：
  core/query/browse.py      →  core/query/model.py        （允许）
  core/query/model.py       ✗→  queries.py / browse.py / tag_queries.py
  core/query/queries.py     →  tag_queries.py             （既有，保持）
  core/query/tag_queries.py ✗→  queries.py                （3.2 已冻结，保持）
```

### 4.6 与既有 `ResourceQuery` 签名的对应关系（已核对）

| 检查 | 事实 | 对本契约的影响 |
| :--- | :--- | :--- |
| `count` / `list` 筛选参数 | 两者**各 13 个**，名称与默认值完全相同（`query`、`resource_type`、`game`、`card_marker`、`library_id`、`scan_status`、`needs_review`、`has_mods`、`has_missing_mods`、`mod_guid`、`plugin_guid`、`author_id`、`property_category`） | `ResourceFilter` 的 13 行既有字段必须与之**逐名一致**，否则 `to_params()` 无法直接展开 |
| 参数位置 / 传递方式 | `count` / `list` 的定义均以 `*` 开头，即**全部筛选参数为 keyword-only** | "参数位置"不构成兼容性面；新增的两个参数也必须是 keyword-only，且**置于末尾** |
| `list` 额外参数 | `order_by` / `descending` / `limit` / `offset` | 排序与分页**不进** `ResourceFilter`（§4.2） |
| `card_marker` 与 `game` | `_resource_where` 中 `game` 经 `card_marker_for_game()`（`KKS`→`KoiKatuCharaSun`、`KK`→`KoiKatuChara`，大小写不敏感）转换为 `card_marker` 条件 | 模型**原样透传**这两个字段，不新增转换层 |
| `game` 与 `card_marker` **同时**提供 | `_resource_where` 会追加**两个** `r.card_marker = ?` 子句（AND 组合） | **既有行为，保持**；模型与契约均**不**定义"优先级"或"互相覆盖"，也不新增校验 |
| 未知 `game` 取值 | `card_marker_for_game()` 抛 `ValueError` | **既有行为，保持**；`ResourceFilter` 不包装、不吞异常 |
| `resource_type` / `scan_status` 取值合法性 | 由 SQLite `CHECK` 约束与既有调用方负责，Query 层不预校验 | 沿用；不新增枚举校验 |

> 说明（N8）：上表**参数列举顺序不代表函数签名的参数顺序**。`count` / `list` 的全部筛选参数
> 均为 **keyword-only**（定义以 `*` 开头），调用方与文档列举顺序都不构成兼容性面；
> **不得**为了对齐文档/列表顺序而改动代码签名。

> 结论：模型与现有查询层**行为一致**，本阶段**只增加** `tag_id` / `favorite` 两个条件，
> 不改变任何既有字段的解释方式。

> **待核实项（不影响本阶段）**：`game` 与 `card_marker` 同时提供时产生两个 AND 子句，
> 这是**已核实的当前行为**，但仓库文档中**没有记录其设计意图**（是有意收紧，还是历史遗留）。
> 本阶段**不改变**该行为、不新增校验，也不替上级文档解释其意图；
> 如需定性，应由后续阶段或文档修订单独决定。

---

## 5. 数据流与职责边界（候选）

```text
GUI 状态  ui/filter_bar.py + ui/browser_panel.py
              │  scope()
              ▼
        BrowserScope（GUI 会话作用域：筛选子集 + 排序）
              │  to_filter()
              ▼
        ResourceFilter（Query Model：不可变条件集）
              │  to_params()
              ▼
        ResourceQuery.count / list（唯一 SQL 执行点）
              │  _resource_where()（唯一条件构造点，参数化）
              ▼
        core/query/readonly._execute_select（仅 SELECT / WITH）
              ▼
            SQLite

GUI 细化：BrowserScope.filters() = to_filter().to_params() 在 GUI 键集上的【投影】
          （先 to_filter() 做唯一字段映射，再按 FILTER_KEYS 取子集；不得另写字段值映射）

CLI  `query resources` 参数（含 --tag / --favorite / --no-favorite）
              │  --tag <name> → TagQuery.find_by_name()（只读、精确 name_key；失败 ⇒ stderr + exit 1）
              ▼
        ResourceFilter（与 GUI 同一个 Query Model）
              │  to_params()
              ▼
        ResourceQuery.count / list（唯一 SQL 执行点；既有筛选参数与新增参数在此汇合）
```

职责边界（候选）：

| 组件 | 职责 | 明确不负责 |
| :--- | :--- | :--- |
| `BrowserScope` | GUI 状态适配层：**12 个既有筛选字段 + 新增 `tag_id` / `favorite` = 14 个筛选键**，外加排序状态；`to_filter()` 为**唯一字段值映射实现**，`filters()` 仅做键投影 | 不持有 SQL；不解析文本语法；不维护第二份字段值映射；**不把模型 15 键直接暴露为 GUI 键集** |
| `ResourceFilter` | 条件的正式载体（core 层完整筛选面，15 项） | 不执行 SQL；不含排序 / 分页 / UI 状态 |
| `ResourceQuery` | 唯一的 SQL 执行与条件构造（`_resource_where`） | 不做名称解析；不写库 |
| `BrowseService` | 只读编排（count + list 共用同一 filters；行补充 Library / 作者） | 无自有 SQL（既有冻结约束，保持） |
| `TagQuery` | Tag / Favorite 只读事实 | **不是** Search Engine（3.2 §7.4） |

**不允许出现两套竞争性抽象**：

1. `ResourceFilter` **不得**内建 SQL；`BrowserScope` **不得**保留一条绕过 `ResourceFilter` 的并行条件路径。
2. **`BrowserScope.to_filter()` 是 GUI 条件转换的唯一实现**：

```python
FILTER_KEYS: ClassVar[tuple[str, ...]] = (     # 既有 12 键 + 新增 2 键
    "query", "resource_type", "game", "library_id", "scan_status", "needs_review",
    "has_mods", "has_missing_mods", "mod_guid", "plugin_guid", "author_id",
    "property_category",                        # ← 既有 12 键（保持逐键一致）
    "tag_id", "favorite",                       # ← 本阶段新增
)

def to_filter(self) -> ResourceFilter: ...      # 唯一字段值映射实现

def filters(self) -> dict[str, object]:         # 仅投影，不得重复字段值映射
    params = self.to_filter().to_params()
    return {key: params[key] for key in self.FILTER_KEYS}
```

- `filters()` 返回值**恰好包含这 14 个键**，且**键恒存在、值可为 `None`**
  （与今日"12 键全在、值可为 None"的行为一致；`count` / `list` 接受 `None`）。
- **不得**要求 `filters() == to_filter().to_params()`：模型参数集为 **15** 键
  （多一个 `card_marker`），二者**必然不等**（r2 已修正该矛盾，见 T-Q）。
- 投影的**键来自模型参数**（`to_params()` 的键），因此不存在第二份"字段 → 值"映射；
  `filters()` **不得**退化为手写 14 项字面量字典。
3. **CLI 的新增参数必须经同一 Query Model 进入**：`--tag` 解析出的 `tag_id` 与
   `--favorite` / `--no-favorite` 映射出的 `favorite` 必须构造为 `ResourceFilter`
   并**只从**其 `to_params()` 取出 `tag_id` / `favorite` **两项**传入
   `ResourceQuery.count/list`（合并规则见 §6.5；**不得**整表展开 15 键）；
   CLI **不得**自行拼装 `tag_id` / `favorite` 条件，也**不得**引入第二套条件语义。
4. CLI 的**既有**筛选参数可以继续以关键字参数传入（本阶段**不要求**全面重构 `cli_query.py`）；
   新增条件则**只**从模型参数中取出 `tag_id` / `favorite` 两项后与之合并（§6.5）。
   **不得**把 `to_params()` 的完整 15 键与既有参数同时展开 —— 会产生重复关键字
   （如 `resource_type` 被传两次），或用模型默认的 `None` 覆盖既有筛选值。
   两条入口最终都汇合到同一个 `_resource_where`，因此**不存在**第二条条件构造路径。
   将 CLI 全部参数统一收敛为 `ResourceFilter` 属 [FUTURE-CANDIDATE]，不在本阶段。

**GUI 键集（14）与模型参数集（15）为什么不同**：

| 类别 | 键 | 说明 |
| :--- | :--- | :--- |
| 既有 GUI 筛选键（12） | `query`、`resource_type`、`game`、`library_id`、`scan_status`、`needs_review`、`has_mods`、`has_missing_mods`、`mod_guid`、`plugin_guid`、`author_id`、`property_category` | 与 `BrowserScope.filters()` 的**现值逐键一致**（已按 `core/query/browse.py:81-94` 核对） |
| 新增 GUI 筛选键（2） | `tag_id`、`favorite` | 本阶段新增 |
| 模型专用、不进 GUI 投影（1） | `card_marker` | `ResourceQuery.count/list` 支持，但 `BrowserScope` 不含；**不得**仅为满足"字典相等"而把它塞进 GUI 键集 |
| 非筛选状态（不属于 Query Model） | `order_by`、`descending`（`BrowserScope` 字段）；`limit`、`offset`（`page()` 参数） | 排序 / 分页语义保持现状（§7） |

> **已核对的现状（不含新增字段）**：`BrowserScope` 的 12 个筛选字段中，当前 GUI 实际装配 **8** 个
> （`query` / `resource_type` / `library_id` / `needs_review` / `has_missing_mods` / `mod_guid` /
> `plugin_guid` / `author_id`；见 `ui/browser_panel.py:127-140`）。`game` / `scan_status` /
> `has_mods` / `property_category` 属**作用域已支持但当前无 GUI 控件绑定**（既有状态，本阶段不改）。
> 本阶段**不新增 GUI 控件**，因此 GUI 实际装配的字段数仍为 8；`tag_id` / `favorite` 由 API /
> 测试调用方设置，GUI 接线属 Phase 3.5。

---

## 6. Tag / Favorite 筛选语义（候选）

### 6.1 SQL 形状（候选，参数化）

```sql
-- 6.1.1 tag_id 条件
EXISTS (SELECT 1 FROM resource_tags rt
        WHERE rt.resource_id = r.id AND rt.tag_id = ?)

-- 6.1.2 favorite = True
EXISTS (SELECT 1 FROM resource_tags rt JOIN tags t ON t.id = rt.tag_id
        WHERE rt.resource_id = r.id AND t.name_key = ?)      -- 参数 = FAVORITE_TAG_KEY

-- 6.1.3 favorite = False
NOT EXISTS ( <同上> )
```

- Favorite **判据（谓词）与既有权威只读路径 `TagQuery.is_favorite()` 保持一致**：
  同为 `JOIN tags t ON t.id = rt.tag_id` + `t.name_key = ?`（`?` = `FAVORITE_TAG_KEY`）。
  两者差别仅在**外层查询形态**：既有实现为 `SELECT 1 … LIMIT 1`，本契约使用
  correlated `EXISTS`。**不得**为追求字面一致而改动现有查询代码
  （`core/query/tag_queries.py` 不改），也不得引入第二套 Favorite 判据（3.2 §4.5）。
- Favorite 条件**不依赖** `tags.name`（展示文本）、不依赖 `system_tags()` 是否已 bootstrap。
- 不使用 `resources.favorite` 列（**不存在**）、不使用 `favorites` 表（**禁止**新建，3.2 §4.5）。
- `origin='user'` / `'auto'` 在本筛选语义中**不作区分**（筛选按事实关联判断；3.2 恒为 `'user'`）。

### 6.2 组合方式（候选）

- 所有条件（既有 + 新增）之间恒为 **AND**，与 `_resource_where` 现状完全一致。
- `tag_id=X` + `favorite=True` ⇒ 同时满足（AND），不是并集。
- 文本 `query` 与 Tag / Favorite 条件同为 AND（既有行为不变）。
- 空条件（`tag_id=None`、`favorite=None`）⇒ **不追加任何子句** ⇒ 行为与今日**逐字一致**（零语义漂移）。

### 6.3 身份与解析（候选）

- `ResourceFilter.tag_id` 是 **surrogate id**（`tags.id`），不是 `name_key`。
- Tag **名称解析不在 Query 层**：需要按名称筛选时，由调用方（如 CLI）先用
  `TagQuery.find_by_name()`（精确 `name_key`，大小写不敏感、**非模糊**）解析为 id；
  `ResourceQuery` / `ResourceFilter` **不得**接受标签名。
- 不做 Tag 的自动创建 / 自动补建（读路径永不写库，保持 3.2 §7.2 / T-I）。

### 6.4 参数验证与边界

见 §4.4。补充：`tag_id` 为 `0` 或负数 ⇒ 视为「不存在的 Tag」⇒ 空结果（不抛异常）。

§4.4 的规则与测试的对应关系：`tag_id` 的类型拒绝 ⇒ **T-D**；
`tag_id` 的 0 / 负数 / 未知 ID ⇒ **T-D**；`favorite=False` 的语义 ⇒ **T-E**；
「未 bootstrap 时不得隐式写库」⇒ **T-F**。（不在此重复同一规则。）

### 6.5 CLI 参数到条件的映射（候选）

**唯一适配路径**：CLI 的新增筛选条件**只**经 `ResourceFilter` 进入 Query 层（§5-3）；
不新增独立命令、不新增查询模块、不在 CLI 内拼 SQL 或直传条件（§3.3 / §5-4）。

```text
--tag <name>    → TagQuery.find_by_name(name) → tag_id → ResourceFilter(tag_id=tag_id)
--favorite      → ResourceFilter(favorite=True)
--no-favorite   → ResourceFilter(favorite=False)
未提供          → 对应字段保持 None（不追加子句，行为与今日一致）
```

- CLI **不向 Query 层传递标签名称**：名称解析只发生在 CLI 层（§3.5），
  Query 层只接受 `tag_id`（§6.3）。
- CLI **不得**创建 Tag、不得写库；解析与筛选全程只读。
- 名称解析失败 ⇒ 按既有约定 stderr + 退出码 1，**不查询**（§3.5-4）。

**参数组合规则（方案 B：最小改动；不得重复展开模型参数）**

1. 既有 CLI 筛选参数（`--type` / `--game` / `--library` / `--status` / `--needs-review` /
   `--mod` / `--plugin` / `--category` / `--with-mods|--without-mods`）**保持现有装配与传递方式**，
   语义、默认值与输出不变。
2. 新增参数经模型表达；但**只**从模型参数中取出新增的两项，再与既有参数合并：

```python
new_params = {
    key: value
    for key, value in ResourceFilter(tag_id=resolved_tag_id, favorite=args.favorite)
        .to_params().items()
    if key in ("tag_id", "favorite")
}
rows = ResourceQuery(conn).list(
    **existing_cli_params,   # 既有 9 个筛选参数，保持现状
    **new_params,            # 仅 tag_id / favorite
    order_by=args.order, descending=args.desc, limit=args.limit, offset=args.offset,
)
```

3. **禁止**把 `to_params()` 的完整 15 键与既有参数同时 `**` 展开：既会产生重复关键字
   （`TypeError: got multiple values for keyword argument`），也会用模型默认的 `None`
   覆盖已有的筛选值。
4. 未提供新参数时 `tag_id` / `favorite` 为 `None`，`_resource_where` **不追加子句**
   （行为与今日一致）。
5. 组合语义为 **AND**（§6.2）：新增条件与既有条件同时生效；`--favorite` 与既有
   `--type` / `--library` 等可任意组合。

### 6.6 Query 参数集 与 CLI JSON `scope` 输出（候选；两者是不同的事）

**已核对的现有实现**（`cli_query.py`）：`cmd_resources` 构造
`payload = {"count": len(rows), "scope": _resource_list_scope(args), "resources": [...]}`；
`_resource_list_scope()` 逐项枚举 9 个键（`resource_type` / `game` / `library_id` /
`scan_status` / `needs_review` / `mod_guid` / `plugin_guid` / `property_category` / `has_mods`），
且**仅在值非 `None` 时**写入。`scope` **不是**由 `ResourceFilter.to_params()` 序列化而来。

| 维度 | `ResourceFilter.to_params()` | CLI `payload["scope"]` |
| :--- | :--- | :--- |
| 用途 | **内部** Query 调用参数（`count` / `list`） | **对外** JSON 输出（既有契约面） |
| 键数 | 恒 **15** 个（值可为 `None`） | 仅**实际提供**的筛选参数（0–11 个） |
| 新增键 | `tag_id` / `favorite` 恒存在 | `tag_id` **仅在 `--tag` 解析成功时**加入；`favorite` **仅在提供 `--favorite` / `--no-favorite` 时**加入（值 `True` / `False`） |
| `card_marker` | 存在于模型中（core 完整筛选面） | **不输出**（CLI 无对应参数，保持现状） |
| `has_missing_mods` | 存在于模型中 | **不输出**（CLI 无对应参数，保持现状） |
| `None` 值 | 允许 | **不得**出现 |

规则（候选）：

1. 既有 9 个 `scope` 键的**键名、类型与语义不变**（`--library`→`library_id`、
   `--status`→`scan_status`、`--category`→`property_category`、`--mod`→`mod_guid`、
   `--plugin`→`plugin_guid` 等映射保持现状）。
2. 新增键的命名与 `ResourceQuery` 参数名一致：`tag_id` / `favorite`。
3. **不得**因引入 Query Model 而向 `scope` 追加其它键，也**不得**输出值为 `None` 的新键。
4. `--without-mods` 会输出 `"has_mods": false`（既有行为）；`--no-favorite` 同理输出
   `"favorite": false`。新增键与既有键遵循**同一条**「非 None 才输出」规则。
5. `scope` 继续由 CLI 侧显式构造（沿用 `_resource_list_scope` 的写法扩展），
   **不得**改为直接 dump `to_params()`（那会引入 15 个键与 `None` 值，破坏对外兼容）。

---

## 7. count / list / 分页 / 排序 一致性（候选）

1. `count` 与 `list` **必须**由同一 `_resource_where` 结果驱动（既有实现，保持）；
   新增条件对两者**同时**生效，不得只作用于其中一条路径。
2. 一致性等式（细则见 §12 T-H / T-Q，本处不重复展开）：
   `page(scope).total` == `ResourceQuery.count(**scope.filters())`，且 `scope.filters()` ==
   「`scope.to_filter().to_params()` 在 `FILTER_KEYS`（14 键）上的投影」（§5-2）；
   **不是**与完整 15 键 `to_params()` 相等；`sum(len(items)) <= total`。
3. 新增筛选下的排序白名单**不变**：`id` / `name` / `display_name` / `file_size` /
   `modified_time` / `created_at` / `updated_at`；非法值仍抛 `ValueError`。
4. 分页语义不变：`limit` / `offset` 作用于 `list`，不影响 `count`；`offset` 无 `limit` 时行为保持现状。
5. 稳定性不变：排序恒附加 `r.id ASC` 作为 tie-breaker。
6. `BrowseService.page()` 的**签名不变**（`scope` / `limit` / `offset` / `with_review_reasons`）；
   新增筛选通过 `BrowserScope` 字段进入，不需要新的服务方法。
7. CLI 的 `--order` / `--desc` / `--limit` / `--offset` 语义不变；新增筛选**不**改变分页与排序行为。

---

## 8. 只读与参数化约束（候选）

- 新增 SQL **只允许** `SELECT` / `WITH`，且必须经 `core/query/readonly._execute_select` 护栏。
- 用户可控值（`tag_id` / `favorite` / `query`）**必须**以绑定参数传入，不得字符串插值。
- 排序字段继续经白名单映射，不得直接拼接调用方字符串。
- 读路径**不得**创建任何行（含系统 Tag）。只读性证据**按测量层区分**（N5）：
  - **Query 层**：在**已打开的连接**上围绕读取调用断言连接级 `total_changes` 不变
    （沿用既有 `tests/test_tag_query.py::test_tag_query_performs_no_writes` 的测量方式）；
  - **CLI 层**：沿用既有 CLI 只读测试惯例，以**数据库文件 SHA-256** 等既有证据
    证明文件未被修改（`tests/test_query_cli.py::test_cli_does_not_modify_database`）。
- CLI 启动会调用 `database.initialize()`（`cli_query._open_conn`），其建库 / 迁移属**既有启动行为**：
  **不得**把它误判为"筛选查询写入"；本阶段**不修改** CLI 初始化或 database 行为，
  也**不得**用 CLI 层的连接级 `total_changes` 作为筛选只读证据。
- 所有权护栏（`tests/test_ownership_guard.py`）覆盖的表与 writer allowlist **不变**：
  本阶段不新增任何 writer。

---

## 9. 兼容性约束（候选）

| 面 | 约束 |
| :--- | :--- |
| `ResourceQuery.count/list` | 既有参数名 / 默认值 / 位置语义**不变**，仅**追加** `tag_id` / `favorite`（带 `None` 默认） |
| 文本搜索 | `core/query/search.py` 的路由（空 / LIKE / FTS）、转义与「整段短语」语义**一字不改**；不新增语法解析 |
| `BrowserScope` | 既有 **12** 个筛选字段与 `filters()` 的既有 **12** 键**逐一不变**；追加 `tag_id` / `favorite`（置于末尾、带默认值），故 `filters()` 返回**恰好 14 键**（键恒存在、值可为 `None`）；`order_by` / `descending` 仍不进 `filters()`；`filters()` 为**投影**而非 `to_params()` 的直接展开（§5 / T-Q） |
| DTO | `ResourceSummary` / `ResourceDetail` / `TagSummary` 及其余 DTO **零变更** |
| `BrowseService` | 公开方法签名不变；转发行为不变 |
| CLI | 既有 `query` 子命令的参数、输出行、JSON 字段与退出码约定不变；`query resources` **仅追加** `--tag` / `--favorite` / `--no-favorite`（§3.3，已批准）；既有筛选参数继续以关键字传入，新增条件只取 `tag_id` / `favorite` 两项合并（§6.5，避免重复关键字与 `None` 覆盖） |
| 既有测试 | 任何既有测试的**断言语义不得因本阶段而需要修改**；允许在**实际负责相应行为的现有测试文件**中新增用例（不限定文件名，见 §10.1） |

> 说明：既有断言 `set(filters) ⊆ set(ResourceQuery.count/list 的参数名)`
> （`tests/test_browse.py::test_scope_filters_are_a_single_conversion_point`）对应 §12 **T-R**，
> 本处不再重复定义。若该断言需要改动，视为**破坏兼容性的信号**，必须停下报告。

---

## 10. 文件范围

### 10.1 允许修改（仅实现阶段；本草案不执行）

| 文件 | 变更 |
| :--- | :--- |
| `core/query/model.py` | **新增**：`ResourceFilter`（Query Model） |
| `core/query/queries.py` | `_resource_where` + `ResourceQuery.count/list` 追加 `tag_id` / `favorite` 与 §6.1 的两个 EXISTS 子句 |
| `core/query/browse.py` | `BrowserScope` 追加两字段与 `FILTER_KEYS` / `to_filter()`；`filters()` 改为在该 14 键上的投影（既有 12 键不变；不做 dict 相等） |
| `core/query/__init__.py` | 导出 `ResourceFilter` |
| `cli_query.py` | `query resources` 追加可选只读参数（`--tag` / `--favorite` / `--no-favorite`）及其名称解析 |
| 测试文件 | **新增** focused 测试文件（如 `tests/test_query_model.py`）；并允许在**实际负责相应行为的现有测试文件**中新增用例（如 `test_browse.py` / `test_query_cli.py` / `test_gui_filters.py` / `test_tag_query.py`） |
| `docs/phase3/PHASE3_3_LOG.md`、`docs/phase3/PHASE3_3_CLOSURE_REPORT.md` | **仅限实施 / 收尾阶段的产物**（文件名沿用仓库既有惯例 `PHASE3_x_LOG.md` / `PHASE3_x_CLOSURE_REPORT.md`），对应 §11 Step 8 |

> 说明（N1）：上表最后一行是 **Phase 3.3 实施与收尾**阶段的文档产物；**本契约修订任务
> 不得创建或修改它们**（`WORKFLOW.md` §5.1）。本节**不开放** `docs/**` 的任意修改权限 ——
> 除上表最后一行明确列出的两个文件外，`docs/**` 仍受 §10.2 约束。

> 说明（r1）：**不限定**新增用例必须落在某个指定文件；测试位置按"谁负责该行为"决定。
> 唯一硬约束是不得修改既有断言语义（§9）。

> 说明（r1）：`cli_query.py` 的改动**限于** `query resources` 的参数注册与
> 其 handler 内的条件装配；不得借机重构其它子命令。

> 路径核对（r2）：`cli_query.py` 位于**仓库根目录**（不是 `core/query/cli_query.py`；
> 后者不存在）；`core/query/model.py` 是本阶段**拟新增**的文件，当前**尚不存在**。

### 10.2 明确禁止修改

```text
core/database/**        （schema / migration / db —— 零 schema 变更）
core/scanner/**         （机器事实写入者）
core/parsers/**         （解析器）
core/app/**             （ResourceWriteService / TagWriteService —— 写服务边界）
core/models/tags.py     （保留系统 Tag 注册表；改动需 PHASE3_0_CONTRACT.md §16）
core/query/search.py    （文本搜索语义冻结；除经授权的缺陷修复外不改）
ui/**                   （本阶段不新增 GUI 控件；不改 ui/**）
main.py                 （parser 注册位于 cli_query.add_query_parser，无需改动）
docs/**                 （除 §10.1 最后一行明确列出的 PHASE3_3_LOG / Closure 记录外，
                          不得修改任何文档；本契约自身除外）
既有测试的断言            （不得削弱或改写既有断言语义；允许追加新用例）
```

---

## 11. Implementation Steps（仅计划，本草案不执行）

```text
Step 1  core/query/model.py：ResourceFilter（15 字段 + to_params() + §4.4 校验）
Step 2  core/query/queries.py：_resource_where 追加 tag_id / favorite 条件（§6.1 形状）；
        ResourceQuery.count / list 追加两个关键字参数（带 None 默认，置于末尾）
Step 3  core/query/browse.py：BrowserScope 追加 tag_id / favorite + to_filter()；
        filters() 改为「to_filter().to_params() 在 FILTER_KEYS（14 键）上的投影」
        （既有 12 键保持不变；无重复字段值映射；不做 dict 相等）
Step 4  core/query/__init__.py：导出 ResourceFilter
Step 5  cli_query.py：query resources 追加 --tag / --favorite / --no-favorite；
        --tag 经 TagQuery.find_by_name() 解析为 tag_id；条件经 ResourceFilter 传入
Step 6  测试：新增 focused 用例（Query Model / 筛选语义 / CLI 入口 / 只读护栏），
        按"谁负责该行为"放入对应测试文件
Step 7  验证：focused → 全量 pytest（记录实际结果）→ schema 断言 → 只读护栏
Step 8  文档（实施 / 收尾阶段产物，按 §10.1 最后一行）：
        docs/phase3/PHASE3_3_LOG.md 与 docs/phase3/PHASE3_3_CLOSURE_REPORT.md
        （文件名沿用仓库惯例；不在本契约修订任务范围内）
```

---

## 12. Test Invariants（候选）

```text
T-A  ResourceFilter 为 frozen；默认构造等价于「无任何条件」；to_params() 键集 == 15 个筛选字段
T-B  空条件等价性：list(**ResourceFilter().to_params()) 与 list() 结果逐行一致（既有语义零漂移）
T-C  tag_id=T（无其它条件、order_by="id"、descending=False、无分页）
     == sorted(TagQuery.resource_ids(T))
     依据（已按源码核对）：ResourceQuery.list 的 SQL 为 "ORDER BY r.id ASC, r.id ASC"
     （默认 order_by="id" / descending=False），TagQuery.resource_ids 为
     "ORDER BY resource_id"（升序）——两侧均为 id 升序，且该顺序有明确实现依据；
     测试必须【显式写出】order_by / descending，不得依赖未写明的隐含默认
T-D  tag_id 校验与边界：None 合法（= 不启用该筛选）；True（bool 即使为 int 子类）与其它
     非 int 值 ⇒ TypeError；未知 / 0 / 负数 ⇒ 空结果且不抛异常
T-E  favorite 仅接受 True / False / None（None = 不启用该筛选；其它任何值 ⇒ TypeError）；
     favorite=True == TagQuery.favorite_resource_ids()；favorite=False == 全集减去该集合
T-F  系统 Tag 尚未 bootstrap 的库：favorite=True ⇒ 空、favorite=False ⇒ 全集，
     均不抛异常，且查询过程【不创建】favorite Tag 行（total_changes 不变）
T-G  tag_id + favorite + 既有条件（如 library_id / resource_type）为 AND 组合
T-H  count(**p) == len(list(**p))（无 limit）；page(scope).total == count(**scope.filters())
T-I  新增筛选下 limit / offset / order_by 行为不变；非法 order_by 仍抛 ValueError
T-J  新 SQL 仅 SELECT / WITH；查询过程不写库（total_changes 不变）；无新增 writer
T-K  新增条件以参数化方式传入：**运行时**证据 = 含 SQL 元字符 / 引号 / 通配符的输入
     不会改变结果集、不报错（行为可测）；"源码中无字符串拼接"属结构性约束，
     允许以**代码审查**等明确可核验的证据满足，不要求脆弱的源码文本匹配测试
T-L  文本搜索语义不变：既有搜索测试全绿（**运行时**验证）；
     "仓库内不存在 field:value / AND·OR·NOT 解析器"属结构性约束，
     以**代码审查 / 公开 API 面核对**作证据；不新增语法解析器
T-M  DTO 零变更：ResourceSummary / ResourceDetail / TagSummary 字段集不变
T-N  schema 冻结：SCHEMA_VERSION == 2 / MIGRATIONS == {1,2} / 16 张业务表
T-O  CLI：既有参数、退出码与输出不变；新参数仅在提供时出现在 payload["scope"]
T-P  CLI --tag：精确 name_key 命中（大小写不敏感、非模糊）；空 / 未知名称 ⇒
     stderr（"Tag not found: <name>"）+ exit 1，不执行查询，stdout 无输出（含 --json）
T-Q  BrowserScope.to_filter() 为唯一字段值映射；filters() 必须等于
     「to_filter().to_params() 在 FILTER_KEYS 上的投影」：
     set(filters()) == set(FILTER_KEYS)（恰好 14 键、键恒存在、值可为 None），
     且每个键的值与 to_params() 中同名键的值相同；
     【不得】断言 filters() == to_filter().to_params()（模型 15 键，二者必然不等）
T-R  filters() 的键集 ⊆ ResourceQuery.count/list 的参数名（既有断言保持有效）
T-S  CLI 空结果：文本模式 "(no results)" 且 exit 0；--json 模式输出 count=0 / resources=[] 且 exit 0
```

---

## 13. Definition of Done（Phase 3.3）

Phase 3.3 视为完成，当且仅当：

1. `ResourceFilter` 作为正式、不可变的 Query Model 落地，且为纯值对象（无 SQL、无 UI 状态）；
2. `ResourceQuery` / `BrowseService` 支持 `tag_id` 与 `favorite` 只读筛选，语义符合 §6；
3. `BrowserScope` → `ResourceFilter` → `ResourceQuery` 的数据流唯一，无第二套 SQL 条件构造点；
4. §12 不变式的验证方式与其性质匹配，且**覆盖 T-A 至 T-S 全部不变式**（不遗漏、不弱化）：
   - 可经**运行时行为**可靠验证的部分（全部筛选语义、只读、DTO、schema、CLI 行为与退出码，
     以及 T-K / T-L 的运行时部分）**必须**有自动化测试并通过；
   - **结构性约束**（T-K 的"无字符串拼接"、T-L 的"不存在语法解析器"）允许以
     代码审查或其它明确、可核验的证据满足；
   - **不得**为满足形式要求引入脆弱的源码文本匹配测试；
     也**不得**因此降低安全约束或搜索语义兼容性要求；
5. `SCHEMA_VERSION == 2`，无 migration / 新表 / 新列 / 新索引；
6. 全量测试已实际运行并记录结果（`883 passed` 仅作**参考基线**，不作为单独门槛）；
   若出现新增失败或环境差异，必须解释原因，不得静默接受；
   且**未修改任何既有断言语义**；
7. 未引入 `field:value` / AND / OR / NOT / 多标签组合 / 新 DTO 字段 / 新 GUI 控件；
8. §2 Non-Goals 无一项被越界实现；
9. CLI 只读入口按 §3.3 / §3.5 交付，且 T-O / T-P / T-S 通过；
10. `BrowserScope.filters()` 为**投影**实现（非 `to_params()` 直接展开、非手写字面量字典），
    且 §12 **T-Q** / **T-R** / **T-C** 通过。

---

## 14. 变更控制

```text
1. 本契约冻结后，任何扩大 Phase 3.3 范围的行为必须走
   PHASE3_0_CONTRACT.md §16（评审 + 更新 Contract + 用户确认）。
2. 本契约的候选条款在冻结后即为【FROZEN】决策，不得在实现阶段被顺带更改。
3. §2 Non-Goals 不得被「顺手一起做」（尤其是文本语法与 GUI 扩展）。
4. 本契约不修改 Phase 3.0 / 3.0.2 / 3.1 / 3.2 的既有契约，不重新打开已关闭阶段。
5. §3 的入口方案（Option B）已由用户批准；实现方不得擅自扩展到 GUI 入口、
   文本语法或其它未批准形态。
```

---

## 15. Explicit Phase 3.4 / 3.5 Boundary

留给后续阶段（不在本契约内）：

```text
3.4  effective type（type_source='user' 优先）进入搜索面；
     display_name 作为用户值的搜索语义细化（PHASE3_0_2 §13-G5）
3.5  Tag / Favorite 的 GUI 入口与管理 UX（浏览、打标、收藏按钮、Tag 管理界面）、
     最终 UX，以及 startup eager system-tag bootstrap 的接线
     —— CLI 只读筛选入口【不属于 3.5 的责任范围】：已由 3.3 交付（§3.3 / §6.5）；
        3.5 不得另建并行的 CLI 筛选入口（如需变更，应在既有
        --tag / --favorite / --no-favorite 上修改）
未来  文本查询语法（field:value / AND / OR / NOT / tag: / favorite:）
     —— 属新增用户能力，必须先走 PHASE3_0_CONTRACT.md §16（PHASE3_0_2 §13-G2/G3）
未来  多标签组合、按标签排序、性能优化与新索引（PHASE3_0_2 §9.3）
```

---

## 16. Schema Decision（候选）

```text
SCHEMA_VERSION = 2
MIGRATIONS = {1, 2}
NO MIGRATION REQUIRED
```

依据（已核对真实 schema）：`resource_tags` 已有 PK `(resource_id, tag_id)` 与
`idx_resource_tags_tag(tag_id)`；`tags.name_key` 已有 UNIQUE。Tag / Favorite 筛选在
**两个方向**上都命中既有索引，无需新表 / 新列 / 新索引。不得新增：

```text
is_system · resource_count · library_id · favorite 列 · favorites 表 · 任何新索引
```

---

## 17. 一致性核对与 Contract Gap 状态

| # | 检查 | 结论 |
| :-- | :--- | :--- |
| 1 | 与 Phase 3.0 §12-6「按标签浏览（additive 只读筛选）」 | ✅ 覆盖（§1.2 / §6） |
| 2 | 与 Phase 3.0 §10「Query 只读 + additive + DTO 向后兼容」 | ✅ 遵守（§8 / §9） |
| 3 | 与 Phase 3.0 §8 / §16「零 schema」 | ✅ 遵守（§16） |
| 4 | 与 Phase 3.0 §11「文件系统只读」 | ✅ 本阶段不触碰文件系统 |
| 5 | 与 Phase 3.2 §7.4（`TagQuery` forbidden surface） | ✅ 不违反；Tag 过滤在 `ResourceQuery` 侧实现，`TagQuery` 保持只读事实层 |
| 6 | 与 Phase 3.2 §10「TagQuery ≠ Search Engine」 | ✅ 遵守；无 `resolve()`、无文本语法 |
| 7 | 与 Phase 3.2 §2-6（3.2 不改 CLI / GUI） | ✅ 该禁令仅约束 3.2 自身；3.3 经用户批准的 Option B 只改 `cli_query.py` 的 `query resources`，仍**不改** `ui/**` |
| 8 | G1（Query Model 未在 Contract 明列） | ✅ **由本契约承接**：Query Model 定义与边界见 §4 / §5（冻结后成为该议题的设计权威） |
| 9 | G2 / G3（文本语法 / 用户可见 `tag:` / `favorite:` 字段） | ⚠️ **仍未关闭**，明确排除于 §2-1 / §2-2；需独立变更控制轮次 |
| 10 | G4（Taxonomy 未在 Contract 定义）/ G5（effective type 搜索语义） | ⏭ 不受影响 / 留 3.4 |
| 11 | U1 / U2 / U3（OPEN-EVIDENCE） | ⚠️ **仍未关闭**（见 §18）；U2 已由用户以 Option B 作出**排期裁决**，但"真实入口偏好"的证据仍缺 |
| 12 | 持久工作库证据 | ⚠️ `resources=0` / `tags=0`（2026-10-12 只读实测）⇒ 无真实使用证据 |

**与上级冻结契约的冲突核对（结论）**：**未发现真实冲突**。
唯一需要说明的是 3.2 §2-6 / §17-6「不得修改 `main.py` / `cli_query.py` / `ui/*`」——
该禁令约束的是 **Phase 3.2 自身**；`PHASE3_0_CONTRACT.md` §15 明确不写死子阶段编号与顺序，
3.2 §15 亦把入口事项留待后续阶段。3.3 修改 `cli_query.py`（`query resources` 单个命令）
属用户本轮批准的 Option B 范围，且**不改 `ui/**`**、不改 `main.py`，
因此不构成对上级契约的违反。本文件不改动任何上级契约；详见附录 A。

---

## 18. 已知证据缺口（如实登记，本阶段不关闭）

| ID | 缺口 | 影响 |
| :--- | :--- | :--- |
| U1 | 真实组织需求与标签粒度（库内 0 资源 / 0 标签） | 无法证明「单 Tag 筛选」足够；多值组合的优先级无证据 |
| U2 | 入口先后（core→CLI vs core→GUI） | 已由用户裁决为 **core→CLI 先行**（§3.3）；GUI 侧偏好仍无证据 |
| U3 | 组织范围是否全局 | 已由 3.2 冻结为 GLOBAL；本阶段沿用，不重新打开 |
| — | 性能证据（LIKE 全扫 / 相关子查询 / N+1） | 新增筛选沿用既有 EXISTS 模式；无真实规模基准，故不做优化（§2-13） |
| — | `game` + `card_marker` 同时提供时的设计意图 | 行为已核实（两个 AND 子句）、文档未记录意图；登记为 §4.6 的待核实项，本阶段不改行为 |

---

## 19. Freeze Record

```text
Design Review（本草案）      → 完成（r0–r3：DRAFT / CANDIDATE）
§3 入口裁决                  → 【已批准：Option B】（2026-10-12）
用户冻结确认                 → 【已确认】（2026-10-13）
契约内容冻结（Git 证据）      → commit a73438eabe8c716ff9b6b5242c90e7b17286e88c
                              "docs(phase3.3): freeze implementation contract"
                              提交时间 2026-10-13T18:11:16+08:00 · 单文件 · 897 行
                              · SHA-256 8670EDE04950DEEC69AF247F193AA906F010ED187ECA35EF2C165D5138DDDB36
Freeze Record 补齐           → 完成（本记录，r4）
Implementation Contract      → FROZEN
Phase 3.3 implementation     → 未开始（需另行授权）
Phase 3.3 CLOSED             → 未达成
```

冻结时点：**2026-10-13**（用户确认于该日；Git 证据为上述 commit，其提交时间为
2026-10-13T18:11:16+08:00）。

**自引用说明**：本 Freeze Record 的补齐随**其自身提交**一起入库，因此**不内嵌该提交自身的
hash**（写入 hash 会改变内容、进而改变 hash，无法自洽）；此处改为记录 r3 冻结内容的 commit
`a73438e`。若需登记本记录提交的 hash，应由 `PROJECT_STATE.md` 或后续 Closure Report 承担。

---

## 附录 A — 与上级契约的一致性

| 上级条款 | 本契约 | 一致性 |
| :--- | :--- | :--- |
| Phase 3.0 §12-6 按标签浏览（additive 只读筛选） | §1.2 / §6 | ✅ 覆盖，未缩小 |
| Phase 3.0 §12-7 至少一个入口 | §3.3 / §3.5 / §6.5 | ✅ 经用户批准的 Option B 以 CLI 只读入口满足（读侧） |
| Phase 3.0 §14.1 D1–D5 / S1–S4 | §8 / §9 / §16 | ✅ 遵守 |
| Phase 3.0 §16 变更控制 | §14 / §3.4 | ✅ 遵守；未擅自扩大 |
| Phase 3.0 §15 不写死子阶段编号 | 本文件仅定义 3.3 自身范围 | ✅ |
| Phase 3.0.2 §10 Query Model 建议 | §4 / §5 | ✅ 采纳「唯一 Query Model + 唯一执行点」方向 |
| Phase 3.0.2 §11（3.3 建议：Query Model + tag filter；语法需变更控制） | §1.2 / §2-1 | ✅ 一致 |
| Phase 3.2 §4.5 / §7.4 / §10（Favorite 唯一事实、TagQuery 边界） | §5 / §6 | ✅ 一致 |
| Phase 3.2 §1.1（Tag scope = GLOBAL） | §6 | ✅ 沿用 |

## 附录 B — 起草/修订轮次（r0–r3）只读合规核对

| 禁止项 | 状态 |
| :--- | :--- |
| 修改功能代码 / schema / migration | ✅ 未做 |
| 修改测试 / UI / CLI / `main.py` | ✅ 未做 |
| 修改数据库（含写操作） | ✅ 未做（仅只读打开） |
| 实现 Query Model / 筛选 / Search | ✅ 未做 |
| 冻结 Contract | ✅ 起草 / 修订轮次内未冻结；用户在后续轮次确认冻结（见 §19，2026-10-13） |
| 创建 commit / tag / push | ✅ 起草 / 修订轮次内未做；冻结提交 `a73438e` 属后续授权轮次（**tag / push 仍未做**） |
| 更新 `PROJECT_STATE.md` | ✅ 未做（按 `WORKFLOW.md` §5.1，状态同步在冻结 / 关闭后） |
| 唯一被修改文件 | 本文件 `docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md`（r3 内容 + r4 冻结记录补齐均只改本文件；无其它文件变更） |
