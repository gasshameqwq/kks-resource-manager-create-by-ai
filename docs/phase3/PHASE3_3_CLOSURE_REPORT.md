# Phase 3.3 — Search & Query Foundation

## Closure Report

> 文档类型：**Phase 3.3 收尾报告（Closure Report）**。只记录 Phase 3.3 的最终收尾结果，
> 不引入任何新的设计或契约；不改写下位历史阶段的验收结论。
> 日期：2026-10-15

---

### Phase

Phase 3.3 — Search & Query Foundation

### Status

```text
CLOSED / CONDITIONAL PASS
```

**验收结论来源（不得改写为无条件 PASS）**：用户已正式接受 Phase 3.3 的验收结论
**`CONDITIONAL PASS`**。本阶段的"有条件"性质来自 `PHASE3_3_IMPLEMENTATION_CONTRACT.md` §18
登记的证据缺口与 §2 Non-Goals 明确排除项（本报告 "Open Items" 节逐项转记），
它们**未被**解决、**未被**豁免、**未被**标记为已验证通过。

### Contract

- 权威实施契约：`docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md`（**FROZEN**，用户冻结确认 2026-10-13）
- 上级权威：`docs/phase3/PHASE3_0_CONTRACT.md`（Phase 3 首期 Architecture / Scope Contract）
- 前置：Phase 3.2 = CLOSED / PASS（tag `phase-3.2-closed` → `034a726`）

**契约未被修改的证据**（执行前核验，只读）：

| 检查 | 结果 |
| :--- | :--- |
| `git rev-parse HEAD:docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md` | `21a80df6fcc1f8c85c500c04d0388c9e65241e59` |
| `git hash-object docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md`（工作副本） | `21a80df6fcc1f8c85c500c04d0388c9e65241e59`（与 HEAD blob **相同**） |
| 实施提交的文件清单 | 9 个文件，**不含**该契约 |
| 收尾提交的文件清单 | 4 个文档，**不含**该契约（本报告 + 3 份状态同步文档） |

### Implementation

契约 §1.2 六项交付能力的落地（细节见 `docs/phase3/PHASE3_3_LOG.md` §4.1）：

- **Query Model**：`core/query/model.py` 新增不可变 `ResourceFilter`（15 字段、`to_params()` 15 键、
  §4.4 校验：`tag_id` 拒绝 `bool` 与非 `int`，`favorite` 仅接受 `None` / `True` / `False`）；
  无 SQL 出口、无文本语法解析。
- **Tag 筛选**：`core/query/queries.py::_resource_where` 追加
  `EXISTS (SELECT 1 FROM resource_tags rt WHERE rt.resource_id = r.id AND rt.tag_id = ?)`；
  `ResourceQuery.count` / `list` 末尾追加两个 keyword-only 参数（默认 `None`）。
- **Favorite 筛选**：同处以 `EXISTS` / `NOT EXISTS` + `JOIN tags t ON t.id = rt.tag_id`
  + `t.name_key = ?`（参数 = `FAVORITE_TAG_KEY`）实现，与 `TagQuery.is_favorite()` 同谓词；
  未新增 `favorites` 表或收藏列，未修改 `core/query/tag_queries.py`。
- **单一数据流**：`BrowserScope.to_filter()` 为唯一字段值映射；`BrowserScope.FILTER_KEYS`
  （`ClassVar`，14 键）；`filters()` 改为投影实现（旧 12 键字面量字典已移除）。
- **CLI 只读入口**：`cli_query.py` 的 `query resources` 追加 `--tag <name>` /
  `--favorite` / `--no-favorite`（互斥组、`dest="favorite"`、`store_const`、`default=None`）；
  `--tag` 经 `TagQuery.find_by_name()` 精确解析，失败时 stderr `Tag not found: <name>` + 退出码 1 且不查询；
  `scope` 仅输出实际提供的筛选键。
- **Schema**：零变更（`SCHEMA_VERSION == 2` / `MIGRATIONS == {1, 2}` / 16 张业务表）。

### Verification

**证据来源区分（重要）**：

| 类别 | 内容 |
| :--- | :--- |
| **历史证据**（来自实施日志 `PHASE3_3_LOG.md` §5，实施轮实测） | 全量 `pytest -q` 两次通过：`938 passed in 46.84s`、`938 passed in 44.30s`；focused：`42 / 37 / 54 / 277 passed`；schema 断言、Query 层连接级 `total_changes` 不变（34 → 34）、CLI 层数据库文件 SHA-256 不变（`79b69a79…c42`）；T-A…T-S 映射见 LOG §6；DoD 1–10 见 LOG §7 |
| **本次收尾轮新取得的证据**（本报告编写前的只读核验） | `git diff --check` exit 0（未暂存与暂存状态均核验）；禁止路径 `git diff --stat` 为空；冻结契约 blob 哈希一致（见上）；未跟踪文件行数/SHA-256 实测；现有 8 个 tag 的名称/类型/对象 ID/目标 commit 快照；`phase-3.3-closed` 执行前不存在；无 remote；工作区在实施提交后 clean |

**⚠️ 明确声明**：上述测试数字与耗时**全部来自实施日志记录**。
**本次收尾核验没有重新运行全量测试**，因此不得将这些数字描述为本次收尾轮重新执行所得。
按 `WORKFLOW.md` §6，"测试通过"本身也不构成阶段验收或 Git 操作授权。

### Git

| 项 | 值 |
| :--- | :--- |
| 实施提交消息 | `feat(phase3.3): add query model and read-only tag filtering` |
| 实施提交（完整 hash） | `950645c5e935de5c985ab361c457a693419178ca` |
| 实施提交（短 hash） | `950645c` |
| 实施提交范围 | 9 files changed, 1506 insertions(+), 19 deletions(-) |
| Final Closure Commit | **即本报告所在的提交**（见下方自引用说明） |
| Final Tag | `phase-3.3-closed` |
| Final Tag type | annotated（`git cat-file -t phase-3.3-closed` → `tag`） |
| Final Tag target | Final Closure Commit（`git rev-parse phase-3.3-closed^{commit}` == `HEAD`） |
| Final working tree | clean（`git status --short` 无输出） |

**关闭过程与提交顺序（实际执行）**：

1. 执行前只读核验（分支 `main`、HEAD `26a73c27cc03833adeeb0fc546e08f778ab57eed`、
   工作区 9 项、`git diff --check` exit 0、禁止路径零 diff、tag 快照）—— 全部通过，无差异。
2. **实施提交**：以显式路径暂存 9 个文件（5 个生产文件 + 3 个测试文件 + 实施日志），
   `git diff --cached --check` exit 0 后提交（上表 hash）。
3. **收尾提交**：新建本报告 + 同步 `docs/PROJECT_STATE.md` / `README.md` /
   `docs/ARCHITECTURE.md`，以显式路径暂存 4 个文档后提交（消息：`docs(phase3.3): close phase 3.3`）。
4. **创建 annotated tag**：`phase-3.3-closed`，message 精确为
   `Phase 3.3 — Search & Query Foundation: CLOSED (CONDITIONAL PASS)`，
   指向上述收尾提交。
5. 最终只读核验（`HEAD == phase-3.3-closed^{commit}`、tag 类型、文件清单、既有 tag 未变、
   工作区 clean）—— 结果由收尾轮执行报告单独提供（不在本报告内声明）。

> **自引用说明**：本报告随 **Final Closure Commit** 一起提交，因此**不内嵌该提交自身的 hash**
> （写入 hash 会改变内容、进而改变 hash，无法自洽）。同理，本报告**不内嵌**
> `phase-3.3-closed` 的 tag 对象 ID。该 annotated tag 解引用后指向的 commit 即 Final Closure Commit；
> 收尾提交与 tag 创建后，`HEAD` == `phase-3.3-closed^{commit}`，工作树 clean。
> 实际的收尾提交 hash / tag 对象 ID / 最终核验输出由本轮执行报告与 `docs/PROJECT_STATE.md` §1
> 的 tag 记录承担（后者记录 tag 名与"指向收尾提交"的关系，同样避免内嵌自引用 hash）。

### Open Items（**未关闭**；不得标记为已解决、已豁免或已验证通过）

| 项 | 状态 | 说明 |
| :--- | :--- | :--- |
| **U1** 真实组织需求与标签粒度 | **开放** | 真实使用场景下的组织需求与标签粒度证据仍不足；此前真实持久库记录为 `resources=0` / `tags=0`。本阶段筛选仅在合成库与真实样本库上验证，**不构成**真实使用证据（契约 §18 第 1 行 / §17-12）。 |
| **U2** GUI 侧入口偏好 | **开放（排期已裁决）** | core → CLI 先行的**排期**已由用户以 Option B 裁决（契约 §3.3 / §19）；GUI 偏好相关的**证据**仍缺（契约 §18 第 2 行 / §17-11）。 |
| **U3** 组织范围是否全局 | **已由 Phase 3.2 冻结** | Tag scope = GLOBAL 已由 Phase 3.2 冻结；本阶段**沿用、不重新打开**（契约 §18 第 3 行）。 |
| **性能 benchmark** | **未要求实施（Non-Goal）** | 属冻结契约 §2-13 明确排除项，本阶段未要求实施、未做基准（契约 §18 第 4 行）。 |
| **`game` + `card_marker` 设计意图** | **待核实（行为保留）** | 两者同时提供时会产生两个 `r.card_marker = ?` AND 子句（已核实）；文档未记录设计意图，本阶段**保留既有行为、未改变**（契约 §18 第 5 行 / §4.6）。 |
| **上游 U4 / U5** | **上游登记项，不属本阶段范围** | 3.3 §18 未列 U4/U5；其关联能力已被 §2-10 排除。**不得**把契约排除项扩展成 Phase 3.3 的实施范围。 |

### Evidence Revision Note（实施日志的证据修订历史）

`docs/phase3/PHASE3_3_LOG.md` 的**证据记录**在实施提交之前经过一次**最小修订**，
已于实施提交中一并入库；**本收尾轮未再修改该日志**（`git show --name-only` 显示收尾提交不含该文件）。
修订内容与范围（仅证据表述与完整性，**未改动任何结论**）：

1. §3 变更清单补入 `docs/phase3/PHASE3_3_LOG.md` 自身（获准新增的实施日志），
   并明确未跟踪文件不计入 `git diff --stat` / `--numstat`；
2. §3 标注行数统计口径为 `splitlines()`（空行计入）；
3. §5.5 把 `rg -n 'name_key' core/query/queries.py` 的记录补为**完整 5 行输出**（372 / 379 / 658 / 1076 / 1080）；
4. §5.5 把语法关键词检索改用词边界模式 `\b(AND|OR|NOT|field:value)\b`，
   如实记录"无匹配、退出码 1"，并注明原无词边界模式曾因 `OR` 命中 `FAVORITE` 子串产生假阳性。

**实施日志最终状态（实施提交入库时）**：

```text
docs/phase3/PHASE3_3_LOG.md
  行数      : 339（splitlines() 口径，空行计入）
  SHA-256   : b362f67227878ef9b63a4da81d693b14a76107b6343084804b47a5d18bc8c3d6
  字节数    : 22611
```

### Scope

Phase 3.3 CLOSED 后，本阶段**不包含**：

- Phase 3.4 内容：effective type（`type_source='user'` 优先）进入搜索面、`display_name` 作为用户值的搜索语义细化；
- Phase 3.5 内容：Tag / Favorite 的 GUI 入口与管理 UX、最终用户界面、startup eager system-tag bootstrap 接线；
- 文本查询语法（`field:value` / `tag:` / `favorite:` / AND / OR / NOT）、多标签组合、按标签排序；
- 新 DTO 字段、新 GUI 控件、新排序白名单项、Collection 查询；
- 性能优化与新索引；FTS 检索面扩展到 `notes` / `series` / `description` / `author`；
- schema v3 / 任何 migration / 新表 / 新列 / 新索引；
- Tag / Favorite 的**写**入口（写侧仍属既有 `TagWriteService` 边界）。

以上均属**后续阶段或未来候选**，不在本次关闭范围。

**文档准确性说明**：本收尾轮对 `README.md` / `docs/ARCHITECTURE.md` 仅做**状态描述与文档导航**同步
（不重写架构、不做功能规划）；因此 `docs/ARCHITECTURE.md` 尚未收录 Query Model / 只读标签筛选的架构描述，
该文档补写属后续文档轮次（已如实登记，不在本阶段关闭条件内）。
