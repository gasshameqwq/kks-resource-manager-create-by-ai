# PROJECT_STATE — 项目当前状态与权威文档入口

> 文档类型：**当前状态登记（CURRENT STATE）**。不是冻结契约，不是阶段报告。
> 最后更新：2026-10-15（§1 更新基线快照与关闭 tag；§3 新增 Phase 3.3 关闭行；§4 同步
> Phase 3.3 实施完成 / 有条件验收 / 收尾事实与 Git 证据；§6 更新第 6 行处置状态；
> §7 转记关闭时仍开放的事项；§9 新增 Phase 3.3 Closure Report 入口）
>
> 维护规则：
> - 本文件只描述**当前**状态；历史结论仍以对应阶段报告为准，**不以本文件改写历史**。
> - 与冻结 Contract 冲突时，**一律以冻结 Contract 为准**。
> - 每次阶段收尾（Closure）后更新本文件；历史漂移只在 §6 登记。

---

## 1. 基线快照

**时点与语义说明**：本表记录的是**上一次核验时点**的基线，**不会随每次提交自动更新**。
其中「HEAD（本次核验的仓库起点）」记录的是**本次文档修订提交之前**核验到的 HEAD ——
提交本次修订后，它**预期不再等于当前 HEAD**，这属正常情况，不代表本文件失效、也不需要立即改写。
需要"当前 HEAD"时应现场执行 `git rev-parse HEAD`，不要直接引用本表。

| 项 | 值 | 证据 |
| :--- | :--- | :--- |
| HEAD（本次核验的仓库起点；**本次文档修订提交之前**） | `950645c`（feat(phase3.3): add query model and read-only tag filtering，Phase 3.3 实施提交） | `git rev-parse HEAD`（2026-10-15 核验） |
| 阶段关闭 tag（独立记录，与上行 HEAD 无对应关系） | `phase-3.3-closed` → 收尾提交（**即本文件所在提交**；收尾提交 hash 见 `git rev-parse phase-3.3-closed^{commit}`，不在本表内嵌以避免自引用） | `git rev-parse phase-3.3-closed^{commit}` |
| 历史 tag | `phase-2.0-closed` … `phase-2.4-closed`（`phase-2.4-closed` → `202c285`）· `phase-3.0-closed` → `c2fd527` · `phase-3.1-closed` → `99aa0d1` · `phase-3.2-closed` → `034a726` | `git tag -l` |
| schema | `SCHEMA_VERSION == 2` · 16 张业务表 · `MIGRATIONS == {1, 2}` | `core/database/schema.py` |
| 测试基线 | `pytest -q` → **883 passed / 0 failed / 0 skipped**（两次独立运行：治理前只读基线复跑 52.2 s，2026-10-10；文档改动后复核 44.55 s，2026-10-10。两者不是同一次测试，且都不是 2026-10-11 的测量） | 分两次实测 |
| 测试基线（Phase 3.3） | `pytest -q` → **938 passed / 0 failed / 0 skipped**（两次独立运行：`46.84 s` 与 `44.30 s`，**均为 2026-10-15 实施轮实测**）。**该结果未经后续收尾轮重新执行**，来源为实施日志 | `docs/phase3/PHASE3_3_LOG.md` §5.2 |
| 测试基线（Phase 3.4） | `pytest -q` → **943 passed / 0 failed / 0 skipped**（2026-10-17 实施轮实测，`52.07 s`；`943 = 938 + 5` 新增用例） | `docs/phase3/PHASE3_4_LOG.md` §5.2 |
| 持久工作库 | `data/kks_resource_manager.db`：`libraries=0` / `resources=0` / `mods=0` / `tags=0` / `resource_tags=0` / `collections=0` / `duplicate_groups=0`；`schema_version='2'` | 只读打开实测 |
| 运行环境 | Python 3.11+（实测 3.12.10）· PyQt6 / msgpack / Pillow | `requirements.txt` |

---

## 2. 文档职责与权威顺序

### 2.1 职责划分

| 文档 | 职责 |
| :--- | :--- |
| `docs/WORKFLOW.md` | 长期协作规则：角色职责、标准流程与任务指令要求、暂停条件、文档分层与权限边界、审核与阶段状态、Git 授权规则 |
| `docs/PROJECT_STATE.md`（本文件） | 当前状态、已完成阶段、当前基线、下一步方向、**文档职责登记**、权威文档入口 |
| 阶段 Contract | 冻结的目标、范围、架构约束、验收标准 |
| Decision Report | 重要设计决策、备选方案、理由、状态及相关契约 |
| 大阶段总工作文档 | 大阶段的总体目标、简要计划、进度、成果摘要、遗留问题与索引（不承担小阶段详细实施说明） |
| 小阶段工作文档 | 具体小阶段的目标与范围、实施边界、测试与验收标准、实际结果 |
| Implementation Log | 同一阶段内按子阶段记录实施过程、测试结果、问题与处理结论（原则上持续更新同一份） |
| Closure Report | 最终验收结论、测试证据、Git commit / tag |
| `README.md` | 项目简介、当前状态、高层路线图 |
| `docs/ARCHITECTURE.md` | 当前有效的架构（不得把已废弃设计描述成当前实现） |
| 项目对话使用说明（非仓库文档） | ChatGPT 会话内的协作约定与沟通要求；**不取代**上述仓库文档 |

**本表是文档职责的唯一登记入口**；`docs/WORKFLOW.md` 只保留协作所需的职责摘要与指向。

**现状说明（避免误读为"文件已存在"）**：本表登记的是**职责 / 文档类型**，不是"仓库现有文件清单"。

- 「大阶段总工作文档」「小阶段工作文档」为**文档类型定义**，目前**尚未创建**对应文件；是否创建属当前项目决策，不在本表决定（`docs/WORKFLOW.md` §5.1 只规定分层原则）。
- 「项目对话使用说明」**不是仓库文件**，仅用于说明 ChatGPT 会话内的协作约定，不取代仓库文档。
- 上表其余各项在仓库中均有对应产出：`docs/WORKFLOW.md`（已于提交 `41e0939` 纳入版本控制）、`docs/PROJECT_STATE.md`、各阶段 Contract、Decision Report、Implementation Log、Closure Report、`README.md`、`docs/ARCHITECTURE.md`。

以上为职责定义，不代表每个阶段必须产出全部类型。

### 2.2 权威顺序

**设计决策权威**与**阶段验收权威**是两类不同的权威，**不得互相替代**：

| 权威类型 | 决定什么 | 载体 |
| :--- | :--- | :--- |
| **设计决策权威** | 适用范围、架构约束、契约规则（能做什么 / 不能做什么 / 边界与不变量） | **冻结 Contract**（如 `docs/phase3/PHASE3_0_CONTRACT.md`）；其修改必须走该 Contract 自身的变更控制条款（Phase 3 首期见 Contract §16） |
| **阶段验收权威** | 该阶段是否完成、最终验收结论与 Git 证据（commit / tag） | **对应阶段的 Closure Report** |

顺序规则（同一议题出现多个文档时）：

1. **冻结 Contract** —— 设计决策的最高权威；
2. **阶段 Decision Report / 设计评审** —— 决策依据；被 Contract 显式取代时以 Contract 为准；
3. **Implementation Log** —— 过程记录，不构成契约；
4. **Closure Report** —— 阶段最终验收结论及 Git 证据；
5. **`README.md` / `docs/ARCHITECTURE.md` / 本文件** —— 描述性；不得与冻结 Contract 冲突。

明确禁止：

- **Decision Report 与 Implementation Log 不得覆盖最终验收结论**；阶段是否完成、结论与 Git 证据
  一律以对应 Closure Report 为准。
- 不允许两个文档在没有解释的情况下对同一决策给出相互矛盾的当前结论。发生冲突时，
  不得猜测哪个版本正确，必须核对冻结记录、授权记录、实施证据与当前代码，并在本文件登记现行权威。

---

## 3. 已完成阶段（事实）

| 阶段 | 结论 | 权威报告 | tag |
| :--- | :--- | :--- | :--- |
| Phase 0 | 完成（架构 + 骨架 + schema） | [PHASE0_REPORT.md](./PHASE0_REPORT.md) | — |
| Phase 1 | CLOSED | [phase1/PHASE1_FINAL_REPORT.md](./phase1/PHASE1_FINAL_REPORT.md) | — |
| Phase 2 | CLOSED（Content Identity / Byte-duplicate / 查询暴露） | [phase2/PHASE2_FINAL_CLOSURE_REPORT.md](./phase2/PHASE2_FINAL_CLOSURE_REPORT.md) · [phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md](./phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md) | `phase-2.4-closed` |
| Phase 3.0 | CLOSED / PASS（首期 Architecture / Scope Contract 冻结） | [phase3/PHASE3_0_CONTRACT.md](./phase3/PHASE3_0_CONTRACT.md) | `phase-3.0-closed` |
| Phase 3.0.2 | 设计评审已入库（非实现、无独立 tag） | [phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md](./phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md) | — |
| Phase 3.1 | CLOSED / PASS（User Write Foundation） | [phase3/PHASE3_1_CLOSURE_REPORT.md](./phase3/PHASE3_1_CLOSURE_REPORT.md) | `phase-3.1-closed` |
| Phase 3.2 | CLOSED / PASS（Tag System） | [phase3/PHASE3_2_CLOSURE_REPORT.md](./phase3/PHASE3_2_CLOSURE_REPORT.md) | `phase-3.2-closed` |
| Phase 3.3 | **CLOSED / CONDITIONAL PASS**（Search & Query Foundation） | [phase3/PHASE3_3_CLOSURE_REPORT.md](./phase3/PHASE3_3_CLOSURE_REPORT.md) | `phase-3.3-closed` |
| Phase 3.4 | **CLOSED / CONDITIONAL PASS**（User Classification & Search） | [phase3/PHASE3_4_CLOSURE_REPORT.md](./phase3/PHASE3_4_CLOSURE_REPORT.md) | —（tag 未创建） |

Phase 2 内部划分（2.0 设计基线 / 2.1 Content Identity / 2.2 Byte-duplicate / 2.3 查询暴露 /
2.4 收尾审计）见 `docs/phase2/` 下的各阶段报告；Phase 1 内部划分见 `docs/phase1/`。

---

## 4. 当前工作路线图（**未冻结**）

**性质声明**：本节是**工作方向记录**，**不是冻结路线图、不是承诺**。
`PHASE3_0_CONTRACT.md` §15 明确声明 Contract **不固定** Phase 3 子阶段的编号与顺序，
因此当前**不存在冻结级 Phase 3 路线图**。

| 阶段 | 内容 | 状态 |
| :--- | :--- | :--- |
| 3.0 | Architecture / Scope Contract | ✅ 已完成（CLOSED / PASS） |
| 3.0.2 | Search & Taxonomy Design Review | ✅ 已完成（设计评审已入库） |
| 3.1 | User Write Foundation | ✅ 已完成（CLOSED / PASS） |
| 3.2 | Tag System | ✅ 已完成（CLOSED / PASS） |
| 3.3 | Search & Query Foundation | ✅ 已完成（**CLOSED / CONDITIONAL PASS**，2026-10-15；tag `phase-3.3-closed`；Closure Report：[phase3/PHASE3_3_CLOSURE_REPORT.md](./phase3/PHASE3_3_CLOSURE_REPORT.md)） |
| 3.4 | User Classification & Search | ✅ **CLOSED / CONDITIONAL PASS**（2026-10-18；契约 FROZEN；Closure Report：[phase3/PHASE3_4_CLOSURE_REPORT.md](./phase3/PHASE3_4_CLOSURE_REPORT.md)） |
| 3.5 | CLI / GUI Integration | ⏳ **待规划方向**（未开始、未冻结） |
| 3.6 | （无定义） | ⚠️ **定义缺失**：仅出现在路线图记录中，全仓无任何内容定义；**不视为已批准阶段**，本文件不代为定义，也不删除该条目 |

**来源与权威级别**：3.0.2 / 3.1 / 3.2–3.5 顺序来自
`docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md` §11 与该文件头部记录的
「P3.0.1 路线图」，并由 `docs/phase3/PHASE3_2_LOG.md` §1 沿用。
该来源属**审查级记录**（非 Contract、非冻结）；3.1 / 3.2 已是**事实**，3.3 与 3.4 均已有**冻结契约**
（3.3 的能力范围来自 `PHASE3_0_CONTRACT.md` §12-6 与用户批准的 Option B；3.4 见下方冻结与实施记录），
3.5 及以后仅为方向。

**Phase 3.3 冻结记录（事实）**：权威契约为
[phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md](./phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md)，
状态 **FROZEN**（用户冻结确认 2026-10-13）。Git 证据：冻结内容提交 `a73438e`
（`docs(phase3.3): freeze implementation contract`，单文件、897 行）·
Freeze Record 补齐提交 `fe0cbcb`（`docs(phase3.3): record contract freeze`）。
该契约**只冻结 Phase 3.3 自身**的范围、Query Model 定义、筛选语义、兼容性约束与测试不变式，
**不冻结**本节路线图；3.3 的**功能实施尚未开始、尚未获得授权**，阶段**未关闭**（无 Closure、无 tag）。

**边界**：登记本路线图**不扩大** Phase 3 首期 Contract 的能力范围；
任何 3.3 及以后的范围决策都必须另行评审（Contract §16 变更控制）——
3.3 已按此流程评审并由用户确认冻结（见上方冻结记录）。

**Phase 3.3 实施与关闭记录（事实，2026-10-15）**：实施（严格落在契约 §10.1 允许范围内）已完成，
实施提交为 `950645c`（`feat(phase3.3): add query model and read-only tag filtering`，
9 files changed / 1506 insertions(+) / 19 deletions(-)）；用户已接受验收结论
**`CONDITIONAL PASS`**（**非**无条件 PASS，条件/非阻断事项见下与 §7）。
收尾提交（`docs(phase3.3): close phase 3.3`）包含 Phase 3.3 Closure Report 与本次状态同步，
annotated tag `phase-3.3-closed` 指向该收尾提交；完成时核验 `HEAD == phase-3.3-closed^{commit}`、
工作树 clean。收尾提交自身的 hash **不在本文件内嵌**（自引用），
以 `git rev-parse phase-3.3-closed^{commit}` 与 Closure Report 为准。
本阶段 §18 登记的证据缺口与 §2 Non-Goals 排除项在 §7 如实转记，**未关闭、未豁免**。

**Phase 3.4 冻结、实施与关闭记录（事实，2026-10-18）**：权威契约为
[phase3/PHASE3_4_IMPLEMENTATION_CONTRACT.md](./phase3/PHASE3_4_IMPLEMENTATION_CONTRACT.md)，
状态 **FROZEN**（2026-10-17，冻结提交 `632eb4c`，`docs(phase3.4): freeze implementation contract`）。
G-2 实施已完成（零功能增量：仅核验 + 文档 + 测试），**无生产代码变更**；全量测试
`943 passed`（实施轮 52.07 s；G-3 提交前复跑 43.07 s，来源 `PHASE3_4_LOG.md` §5.2 / §9）。
Implementation commit：`ef362fd19e79a67dd496ef5751393244844131a2`
（`test(phase3.4): verify display name and effective type behavior`，8 files，+459/−21）。
文档状态修正 commit：`9e694cf1573ba744ec26f896fe36413a6ac483ff`
（`docs(phase3.4): correct finalization status`，3 files，+54/−6）。
G-3 的提交前核验、focused/全量测试、implementation commit 与提交后核验已完成；
**Phase 3.4 tag 尚未创建，push 尚未执行**。实施/关闭报告见
[phase3/PHASE3_4_CLOSURE_REPORT.md](./phase3/PHASE3_4_CLOSURE_REPORT.md)。
**阶段已于 2026-10-18 CLOSED / CONDITIONAL PASS**；非阻断事项（T-A2 断言独立性、
3.3 历史段落漂移、r6→冻结差异未独立验证、ARCHITECTURE 3.4 状态行）见 Closure Report。

**Phase 4 及以后**：`README.md` / `docs/ARCHITECTURE.md` 中的 Phase 4–6 条目来自早期路线图，
尚未重新论证（Phase 4 的 byte-duplicate 部分已在 Phase 2 以只读派生形式完成）。
不得把这些条目当作契约。

---

## 5. 关键决策的现行权威（冲突登记）

| 议题 | 冲突现状 | 现行权威 | 依据 |
| :--- | :--- | :--- | :--- |
| `display_name` 语义 | `PHASE3_0_DECISION_REPORT.md` §3.1 把它列为「共享字段」（值 ≠ 旧 `name` 时保留的启发式）；`PHASE3_0_CONTRACT.md` §3.1（r1，解法 B）把它定为**纯用户数据**（`NULL` = 未覆盖，`effective_display_name = display_name or name`，Scanner / Parser 不得写，禁止用相等性判断 override） | **`PHASE3_0_CONTRACT.md` §3.1** | Contract §16.5 记录为经用户确认的授权修正；实施证据一致：`core/scanner/store.py` 不写该列、`core/app/resource_write.py` 为唯一写入口、`core/query/dto.py` 按 NULL 语义实现，`tests/test_scanner.py` / `tests/test_effective_display_name.py` / `tests/test_resource_write.py` 断言解法 B。Decision Report §3.1 为历史表述（其正文按治理边界未改写） |

> 证据局限（如实登记）：「经用户确认的授权修正」这一批准记录**目前只存在于
> `PHASE3_0_CONTRACT.md` 的自身文字（§2.2 / §16.5 与附录 A）中**，仓库内没有独立的批准文件。
> 本文件不补造任何批准记录；如需补齐，应由用户提供或另立记录。

---

## 6. 已登记的文档漂移与治理状态

| # | 漂移 | 处理状态 |
| :--- | :--- | :--- |
| 1 | `README.md` 状态行停在 Phase 1.5-B、快速开始称「还没有 GUI」、路线图为早期版本、文档表缺 Phase 2/3 链接 | 已于 2026-10-10 定点修正（本文件 §1 / §3 / §4 为权威来源） |
| 2 | `docs/ARCHITECTURE.md` 标题与 §4 写 `schema v1`；§5.2 的 SHA-256 / `quick_hash` 策略、§7 的重复检测描述、§10 路线图、§3 目录树与实际不符 | 已于 2026-10-10 定点修正 |
| 3 | `docs/phase3/PHASE3_2_LOG.md` 顶部状态与后文（§17 / §18）及 Closure Report 互相取代但缺终态说明 | 已于 2026-10-10 在顶部追加「最终状态索引」，历史章节未删改 |
| 4 | `PHASE3_0_DECISION_REPORT.md` 与 Contract 的 `display_name` 描述不一致 | 已于 2026-10-10 在顶部追加权威指针；原文未改写 |
| 5 | Phase 1 / Phase 2 历史报告中的早期路线图表述（如「重复检测属 Phase 4」） | **不处理**（历史报告不改写；现行描述已在本文件与 ARCHITECTURE 修正） |
| 6 | `README.md` 状态行「下一步：Phase 3.3 及以后为**待规划方向（未冻结）**」与其路线图行、`docs/ARCHITECTURE.md` §10 路线图行的「3.3 及以后**未冻结**」—— 与 Phase 3.3 契约已于 2026-10-13 冻结（见 §4）不符 | **已处置**：该两文件已由 `26a73c2`（2026-10-15）同步为「3.3 契约已冻结、实施未开始」；本轮 Phase 3.3 关闭时又经授权同步为「3.3 CLOSED / CONDITIONAL PASS」。本行登记关闭（历史记录保留） |

---

## 7. 未决事项 / 证据缺口（**未解决**）

Phase 3.0 Contract §14.3 的 U1–U5 属 `[OPEN-EVIDENCE]`；本轮**只登记缺口、取证方式与关闭条件，
不执行取证、不标记为已解决**。清单见
[phase3/PHASE3_0_OPEN_EVIDENCE.md](./phase3/PHASE3_0_OPEN_EVIDENCE.md)。

截至本文件更新时（持久工作库 `resources=0`、`tags=0`、`resource_tags=0`），
U1 / U3 / U4 / U5 **均无真实使用证据**；U2 仅有实现进度（Phase 3.1 已落 CLI 写入口），
**不构成证据**。补充（2026-10-14）：U2 的**排期**已由用户以 Option B 裁决
（core→CLI 先行，见 §4 Phase 3.3 冻结记录），但该裁决**不构成证据**，
**真实入口偏好**仍无数据，U2 **不因此关闭**。

**Phase 3.3 关闭时的转记（2026-10-15，事实）**：Phase 3.3 以
**`CONDITIONAL PASS`** 结束，其冻结契约 §18 登记的各项**在关闭时仍未关闭**，如实转记、**不作豁免**：

| 项 | 关闭时状态 |
| :--- | :--- |
| U1 真实组织需求与标签粒度 | **开放**：真实使用证据仍不足；真实持久库记录为 `resources=0` / `tags=0`；本阶段筛选仅在合成库与真实样本库上验证，不构成真实使用证据 |
| U2 GUI 侧入口偏好 | **开放**：core → CLI 的**排期**已由用户以 Option B 裁决；**GUI 偏好证据**仍无数据 |
| U3 组织范围是否全局 | **已由 Phase 3.2 冻结为 GLOBAL**；本阶段沿用、不重新打开 |
| 性能 benchmark | **未要求实施**（属冻结契约 §2-13 Non-Goal）；未做基准 |
| `game` + `card_marker` 设计意图 | **待核实**：两者同时提供时产生两个 `r.card_marker = ?` AND 子句（已核实）；文档未记录意图，本阶段保留既有行为 |

上游 `PHASE3_0_CONTRACT.md` §14.3 的 U4 / U5 属**上游登记项**，不属 Phase 3.3 范围（其关联能力已被
Phase 3.3 契约 §2-10 排除），**不得**扩展为本阶段的实施内容或验收条件。

---

## 8. 已知代码内过期字符串（登记，本次不处理）

以下属**功能代码**范畴，不在文档治理范围内，本次**不修改**，仅登记以免被误当作状态依据：

| 位置 | 内容 |
| :--- | :--- |
| `core/__init__.py` | `__phase__ = "Phase 1.5-B (Scan GUI)"`（版本字符串未随阶段更新） |
| `core/duplicate/__init__.py` | docstring 写「Phase 4 实现」并引用 `content_key` |
| `core/mod/__init__.py` | docstring 写「Phase 2 实现」（实际 manifest 解析在 `core/parsers/zipmod.py`） |

---

## 9. 相关入口

- 长期协作规范：[WORKFLOW.md](./WORKFLOW.md)
- 架构：[ARCHITECTURE.md](./ARCHITECTURE.md)
- Phase 3 首期冻结 Contract：[phase3/PHASE3_0_CONTRACT.md](./phase3/PHASE3_0_CONTRACT.md)
- Phase 3.3 冻结 Contract（FROZEN，2026-10-13）：[phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md](./phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md)
- Phase 3.3 Closure Report（**CLOSED / CONDITIONAL PASS**，2026-10-15）：[phase3/PHASE3_3_CLOSURE_REPORT.md](./phase3/PHASE3_3_CLOSURE_REPORT.md)
- Phase 3.3 实施日志（含证据修订说明）：[phase3/PHASE3_3_LOG.md](./phase3/PHASE3_3_LOG.md)
- Phase 3.2 实施日志（含最终状态索引）：[phase3/PHASE3_2_LOG.md](./phase3/PHASE3_2_LOG.md)
- 证据缺口登记：[phase3/PHASE3_0_OPEN_EVIDENCE.md](./phase3/PHASE3_0_OPEN_EVIDENCE.md)
- 项目简介：[../README.md](../README.md)
