# PROJECT_STATE — 项目当前状态与权威文档入口

> 文档类型：**当前状态登记（CURRENT STATE）**。不是冻结契约，不是阶段报告。
> 最后更新：2026-10-24（登记 Phase 3.5 CLI / GUI Integration 关闭结论与
> `982 passed` 测试基线；保留 U1 / U2 开放缺口和 `resource_type` 清除接口限制）
>
> 维护规则：
> - 本文件只描述**当前**状态；历史结论仍以对应阶段报告为准，**不以本文件改写历史**。
> - 与冻结 Contract 冲突时，**一律以冻结 Contract 为准**。
> - 每次阶段收尾（Closure）后更新本文件；历史漂移只在 §6 登记。

---

## 1. 基线快照

**时点与语义说明**：本表保留历史核验时点，并单独登记旧本地历史与已清洗远端
`main`；这些值属于不同对象，不能互相替代。需要“当前 HEAD”时应现场执行
`git rev-parse HEAD`，不要直接引用历史行。

| 项 | 值 | 证据 |
| :--- | :--- | :--- |
| 历史核验基线（**旧本地 Phase 3.3 收尾文档修订前**；非当前 HEAD） | `950645c`（feat(phase3.3): add query model and read-only tag filtering，Phase 3.3 实施提交） | 旧本地历史记录（2026-10-15） |
| 旧本地 `main` HEAD（H2 关闭文档提交；**不是**远端清洗后历史） | `880f26a86d91015192a3ce3085e187711d4772f8` | `git rev-parse main`（2026-10-19 核验） |
| 已清洗远端 `main`（H2 发布基线） | `ca694778a21e01a849c735342a589397f101cc75` | `git rev-parse origin/main`；A4/A5 证据 |
| H2 文档迁移工作分支基线 | `ca694778a21e01a849c735342a589397f101cc75`（`origin/main`） | 本文件迁移时现场核验 |
| H2 文档迁移最新已提交基线（**历史证据治理前**） | 分支 `codex/phase-h2-docs-migration-20261019` · HEAD `9dd217f4691b4077d1c5bb53bdef214974ed035f` · 工作区 clean | `git rev-parse HEAD` / `git status`（2026-10-21 核验） |
| 阶段关闭 tag（**旧本地 H2 前历史记录**） | `phase-3.3-closed` → 旧本地收尾提交；具体 tag object / peeled 对照见 §3.1 | 旧本地 tag refs（不与远端同名 tag 混用） |
| 历史 tags（**旧本地历史基线记录；不是远端完整权威清单**） | `phase-2.0-closed` … `phase-2.4-closed`（`phase-2.4-closed` → `202c285`）· `phase-3.0-closed` → `c2fd527` · `phase-3.1-closed` → `99aa0d1` · `phase-3.2-closed` → `034a726` | 旧本地 `git tag -l`；远端同名 tags 见 §3.1 |
| schema | `SCHEMA_VERSION == 2` · 16 张业务表 · `MIGRATIONS == {1, 2}` | `core/database/schema.py` |
| 测试基线 | `pytest -q` → **883 passed / 0 failed / 0 skipped**（两次独立运行：治理前只读基线复跑 52.2 s，2026-10-10；文档改动后复核 44.55 s，2026-10-10。两者不是同一次测试，且都不是 2026-10-11 的测量） | 分两次实测 |
| 测试基线（Phase 3.3） | `pytest -q` → **938 passed / 0 failed / 0 skipped**（两次独立运行：`46.84 s` 与 `44.30 s`，**均为 2026-10-15 实施轮实测**）。**该结果未经后续收尾轮重新执行**，来源为实施日志 | `docs/phase3/PHASE3_3_LOG.md` §5.2 |
| 测试基线（Phase 3.4） | `pytest -q` → **943 passed / 0 failed / 0 skipped**（2026-10-17 实施轮实测，`52.07 s`；`943 = 938 + 5` 新增用例） | `docs/phase3/PHASE3_4_LOG.md` §5.2 |
| 测试基线（Phase 3.5） | `pytest -q` → **982 passed / 0 failed / 0 skipped**（`125.38 s`，2026-10-24 Phase 3.5.2 实施轮实测；`982 = 961 + 21` 新增用例） | `docs/phase3/PHASE3_5_2_LOG.md` §3.4 |
| 持久工作库 | `data/kks_resource_manager.db`：`libraries=0` / `resources=0` / `mods=0` / `tags=0` / `resource_tags=0` / `collections=0` / `duplicate_groups=0`；`schema_version='2'` | 只读打开实测 |
| 运行环境 | Python 3.11+（实测 3.12.10）· PyQt6 / msgpack / Pillow | `requirements.txt` |

---

## 2. 文档职责与权威顺序

### 2.1 职责划分

| 文档 | 职责 |
| :--- | :--- |
| `docs/WORKFLOW.md` | 长期协作规则：用户 / Gemini / Codex 的职责、标准流程与任务指令要求、暂停条件、文档分层与权限边界、审核与阶段状态、Git 授权规则 |
| `docs/PROJECT_STATE.md`（本文件） | 当前状态、已完成阶段、当前基线、下一步方向、**文档职责登记**、权威文档入口 |
| 阶段 Contract | 冻结的目标、范围、架构约束、验收标准 |
| Decision Report | 重要设计决策、备选方案、理由、状态及相关契约 |
| 大阶段总工作文档 | 大阶段的总体目标、简要计划、进度、成果摘要、遗留问题与索引（不承担小阶段详细实施说明） |
| 小阶段工作文档 | 具体小阶段的目标与范围、实施边界、测试与验收标准、实际结果 |
| Implementation Log | 同一阶段内按子阶段记录实施过程、测试结果、问题与处理结论（原则上持续更新同一份） |
| Closure Report | 最终验收结论、测试证据、Git commit / tag |
| `README.md` | 项目简介、当前状态、高层路线图 |
| `docs/ARCHITECTURE.md` | 当前有效的架构（不得把已废弃设计描述成当前实现） |
| Gemini / Codex 对话说明（非仓库文档） | 对话内的协作上下文与沟通要求；**不取代**上述仓库文档 |

**本表是文档职责的唯一登记入口**；`docs/WORKFLOW.md` 只保留协作所需的职责摘要与指向。

**现状说明（避免误读为"文件已存在"）**：本表登记的是**职责 / 文档类型**，不是"仓库现有文件清单"。

- 「大阶段总工作文档」「小阶段工作文档」为**文档类型定义**，目前**尚未创建**对应文件；是否创建属当前项目决策，不在本表决定（`docs/WORKFLOW.md` §5.1 只规定分层原则）。
- 「Gemini / Codex 对话说明」**不是仓库文件**，仅补充会话内的协作上下文，不取代仓库文档。
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

### 2.3 当前协作职责模型

本节登记当前确认的职责模型；具体流程、暂停条件与审核方法以
[`docs/WORKFLOW.md`](./WORKFLOW.md) §1–§9 为长期协作规范。

| 角色 | 当前职责 |
| :--- | :--- |
| **用户** | 决定项目方向和功能优先级；批准阶段计划、适用契约与实施范围；保留最终验收权，并决定审核发现应触发修复、有条件接受还是拒绝；授权具体 Git 操作。 |
| **Gemini** | 制定阶段计划与架构提案；起草供用户审批的阶段契约；准备 Codex 实施任务指令；独立审核代码、测试、文档、范围合规性和 Git 证据；区分已验证事实、推断、未验证事项、风险与遗留问题。 |
| **Codex** | 只实施明确获准的任务与契约；运行适当测试和检查；更新获准修改的文档与实施记录；汇报实际变更、已执行检查、结果、遗留问题和相关 Git 证据；遇到阻断条件时停止受影响工作并报告。 |

协作边界：

- 规划或起草契约不构成实施授权；实施只在用户批准适用范围与契约后开始。
- Gemini 的独立技术审核不代替用户的最终验收，也不得代替用户授权实施。
- commit、创建或移动 tag、push、重写历史或清理无关修改必须获得匹配具体任务的
  明确授权，不得从其他工作状态推定。
- 遇到契约冲突、重大风险、未经授权的范围扩大、未解决的测试失败或数据安全问题，
  Codex 必须停止受影响的工作并报告。
- 既有冻结契约、已关闭阶段的结论和当前阶段状态不因本职责模型迁移而改变。
- 尚未冻结的后续方向仍只是方向，不得描述为已批准或进行中。

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
| Phase 3.4 | **CLOSED / CONDITIONAL PASS**（User Classification & Search） | [phase3/PHASE3_4_CLOSURE_REPORT.md](./phase3/PHASE3_4_CLOSURE_REPORT.md) | `phase-3.4-closed` |
| Phase 3.5 | **CLOSED / CONDITIONAL PASS**（CLI / GUI Integration） | [phase3/PHASE3_5_CLOSURE_REPORT.md](./phase3/PHASE3_5_CLOSURE_REPORT.md) | —（未授权创建） |
| Phase H2 | **CLOSED / CONDITIONAL PASS**（Git History Privacy Remediation） | [PHASE_H2_CLOSURE_REPORT.md](./PHASE_H2_CLOSURE_REPORT.md) | —（H2 未创建专用 tag） |

Phase 2 内部划分（2.0 设计基线 / 2.1 Content Identity / 2.2 Byte-duplicate / 2.3 查询暴露 /
2.4 收尾审计）见 `docs/phase2/` 下的各阶段报告；Phase 1 内部划分见 `docs/phase1/`。

### 3.1 Phase H2 — Git History Privacy Remediation

**CLOSED / CONDITIONAL PASS**（用户批准，2026-10-18）。H2 处理 Phase 1 至
Phase 3.4 完整历史的隐私整改、候选验证与现有 GitHub 仓库发布，不是 Phase 3.5
功能开发。

- 已清洗远端 `main`：`ca694778a21e01a849c735342a589397f101cc75`。
- 远端保留 10 个阶段 tags；名称、类型、对象和 peeled 关系以 A4/A5 证据为准。
- 旧本地 `main` 和同名 tags 仍属于 H2 前的分离历史，不得把其 commit/tag object
  当作远端清洗后对象，也不得将旧本地谱系合并或强制推送到远端。
- H2 文档迁移分支以 `origin/main` 的 `ca694778...` 为基线；迁移提交
  `9dd217f4691b4077d1c5bb53bdef214974ed035f` 已将 H2 关闭报告和本次状态同步
  纳入版本控制，远端同名工作分支指向该提交。该历史事实不表示 H2 前本地 tags
  已被更新。
- 关闭结论保持 **CONDITIONAL PASS**；五项未解决限制见 §7 和
  [PHASE_H2_CLOSURE_REPORT.md](./PHASE_H2_CLOSURE_REPORT.md)。

### 3.2 Phase 3.4 — H2 前后 Git 对象对照

本节保留 H2 前对象作为历史证据，同时登记清洗后当前谱系中的对应对象。以下对照
**不替换**原阶段报告、实施日志或 tag 注释中的历史值。

| 节点 | H2 前对象（**保留，历史值**） | 清洗后对象（当前谱系） | 本次可复核证据 |
| :--- | :--- | :--- | :--- |
| Phase 3.4 契约冻结 | `632eb4c7dcaa593208c2a52911273896cbb2cef7` | `7704a98a4569f8148494a0618bb11019ef1e1189` | 提交说明与作者时间一致；父链位置对应；`git patch-id --stable` 同为 `4caba32e90bd9d13eeb4c53162ef876a1b9177cb` |
| Phase 3.4 实施 | `ef362fd19e79a67dd496ef5751393244844131a2` | `efffae65c2d66256b5522704a77f50cf38917687` | 提交说明与作者时间一致；父链位置对应；patch-id 同为 `c77848125b32ae263297b36f52aa77861fbc5fa9` |
| 关闭前文档状态修正 | `9e694cf1573ba744ec26f896fe36413a6ac483ff` | `0c1ea2ceff2a2c9e01470ad4a4ecdd592ee113e5` | 提交说明与作者时间一致；父链位置对应；patch-id 同为 `270c4ce46b341600c2a3fe0ff3ce77b5f41ed158` |
| Phase 3.4 正式关闭 | `6553333f832de03468af7945294002ba37d040ef` | `11d2a1498ab63d3b3518e6723337185a5321c347` | 提交说明与作者时间一致；父链位置对应；patch-id 同为 `24da1c0132a74a70c68b13ecefc5f78aacc6f539` |
| 关闭后状态协调 | `442a980a994614623405ecf3243f90e461991ea0` | `198908c299472672be6ed5590c9a3ddfaeca234a` | 提交说明与作者时间一致；父链位置对应；patch-id 同为 `c7afb8d051075bcd2b8ad3ff767b2389ea5404f8` |
| tag `phase-3.4-closed` | object `0cae547c7c21cc1a754b147726f022a3396d38c3` → commit `6553333...` | 远端 object `294336feeac2a9813f21d11a8a147fa522c71fd5` → commit `11d2a149...` | 2026-10-21 只读 `git ls-remote` 直接核验远端 object 与 peeled target |

**证据强度**：五组提交均有相同的提交说明、作者时间和对应父链位置，且实际差异的
`git patch-id --stable` 完全一致。这足以支持“清洗后对应提交”的文档对照与审计导航，
但不能表述为已经取得正式 A4/A5 映射表，也不能据此证明新旧提交的整棵树在所有历史
上下文中逐字节相同。

**限制**：

- H2 报告未在仓库内发布完整的“旧 SHA → 清洗后 SHA”正式映射；原始 A4/A5 证据只以
  受控逻辑位置登记，本次未直接复核其原始产物。
- 新旧 tag 注释的正文都仍写着旧关闭提交 `6553333...`；远端 tag 的实际 peeled target
  由 `git ls-remote` 核验为 `11d2a14...`。因此 tag 注释正文不能单独作为当前目标依据。
- 本地 tag 仍是 H2 前对象，不得与远端同名 tag 混用。

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
| 3.4 | User Classification & Search | ✅ **CLOSED / CONDITIONAL PASS**（2026-10-18；契约 FROZEN；tag `phase-3.4-closed`；Closure Report：[phase3/PHASE3_4_CLOSURE_REPORT.md](./phase3/PHASE3_4_CLOSURE_REPORT.md)） |
| 3.5 | CLI / GUI Integration | ✅ **CLOSED / CONDITIONAL PASS**（2026-10-24；Closure Report：[phase3/PHASE3_5_CLOSURE_REPORT.md](./phase3/PHASE3_5_CLOSURE_REPORT.md)；未授权 tag） |
| 3.6 | （无定义） | ⚠️ **定义缺失**：仅出现在路线图记录中，全仓无任何内容定义；**不视为已批准阶段**，本文件不代为定义，也不删除该条目 |

**来源与权威级别**：3.0.2 / 3.1 / 3.2–3.5 顺序来自
`docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md` §11 与该文件头部记录的
「P3.0.1 路线图」，并由 `docs/phase3/PHASE3_2_LOG.md` §1 沿用。
该来源属**审查级记录**（非 Contract、非冻结）；3.1 / 3.2 已是**事实**，3.3 与 3.4 均已有**冻结契约**
（3.3 的能力范围来自 `PHASE3_0_CONTRACT.md` §12-6 与用户批准的 Option B；3.4 见下方冻结与实施记录），
3.5 已完成收尾；3.6 及以后仍未定义，不构成本轮新增规划。

**Phase 3.3 冻结记录（事实）**：权威契约为
[phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md](./phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md)，
状态 **FROZEN**（用户冻结确认 2026-10-13）。Git 证据：冻结内容提交 `a73438e`
（`docs(phase3.3): freeze implementation contract`，单文件、897 行）·
Freeze Record 补齐提交 `fe0cbcb`（`docs(phase3.3): record contract freeze`）。
该契约**只冻结 Phase 3.3 自身**的范围、Query Model 定义、筛选语义、兼容性约束与测试不变式，
**不冻结**本节路线图。上述契约冻结时，3.3 的功能实施尚未开始、尚未获得授权，阶段尚未关闭
（无 Closure、无 tag）；这是冻结时点的历史状态。后续事实见下方“Phase 3.3 实施与关闭记录
（事实，2026-10-15）”：Phase 3.3 已完成实施和验收，当前为 **CLOSED / CONDITIONAL PASS**，
并有 annotated tag `phase-3.3-closed`。该后续关闭不改变本段记录的冻结时点状态。

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
状态 **FROZEN**（2026-10-17，H2 前冻结提交 `632eb4c`；清洗后对应冻结提交
`7704a98`，证据与限制见 §3.2）。
G-2 实施已完成（零功能增量：仅核验 + 文档 + 测试），**无生产代码变更**；全量测试
`943 passed`（实施轮 52.07 s；G-3 提交前复跑 43.07 s，来源 `PHASE3_4_LOG.md` §5.2 / §9）。
Implementation commit：H2 前 `ef362fd19e79a67dd496ef5751393244844131a2`；清洗后
`efffae65c2d66256b5522704a77f50cf38917687`
（`test(phase3.4): verify display name and effective type behavior`，8 files，+459/−21）。
文档状态修正 commit：H2 前 `9e694cf1573ba744ec26f896fe36413a6ac483ff`；清洗后
`0c1ea2ceff2a2c9e01470ad4a4ecdd592ee113e5`
（`docs(phase3.4): correct finalization status`，3 files，+54/−6）。
G-3 的提交前核验、focused/全量测试、implementation commit、文档修正 commit 与提交后核验已完成；
**Phase 3.4 tag `phase-3.4-closed` 的 H2 前 annotated 对象为
`0cae547c7c21cc1a754b147726f022a3396d38c3` → `6553333f832de03468af7945294002ba37d040ef`；
清洗后远端 annotated 对象为 `294336feeac2a9813f21d11a8a147fa522c71fd5` →
`11d2a1498ab63d3b3518e6723337185a5321c347`**
（`https://github.com/gasshameqwq/kks-resource-manager-create-by-ai.git`）。实施/关闭报告见
[phase3/PHASE3_4_CLOSURE_REPORT.md](./phase3/PHASE3_4_CLOSURE_REPORT.md)。
**阶段已于 2026-10-18 CLOSED / CONDITIONAL PASS**；非阻断事项（T-A2 断言独立性、
r6→冻结差异未独立验证）见 Closure Report。Phase 3.3 冻结段落中的过时当前状态描述
已在 2026-10-18 的关闭后文档维护中修正；该项不再作为未解决漂移。

**Phase 3.5 实施与关闭记录（事实，2026-10-24）**：Phase 3.5.1 实施提交
`96c7fab`（`feat(phase3.5.1): add cli tag commands and eager bootstrap`，
4 files / +951 / −1）交付 8 个 CLI 命令与 System-Tag Eager Bootstrap；
Phase 3.5.2 实施提交 `9bc1938`
（`feat(phase3.5.2): integrate tag and favorite controls into pyqt6 gui`，
7 files / +1567 / −8）交付 Tag / Favorite 筛选、详情交互与用户字段编辑。
最终全量测试为 **`982 passed / 0 failed / 0 skipped`**（`125.38 s`），只读护栏
`8 passed`。阶段结论为 **CLOSED / CONDITIONAL PASS**；非阻断事项为 U1 / U2
仍无真实使用证据，以及 Phase 3.1 冻结契约未提供 `resource_type` 从用户修正
恢复自动值的接口。Phase 3.5 关闭时**未创建 tag、未执行 push**。

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

**Phase 3.5 关闭时的转记（2026-10-24，事实）**：

| 项 | 关闭时状态 |
| :--- | :--- |
| U1 真实组织需求与标签粒度 | **仍为 OPEN**：CLI / GUI 入口已交付不等于取得真实打标会话与粒度证据 |
| U2 CLI / GUI 入口偏好 | **仍为 OPEN**：两个入口已存在，但没有首个真实入口的使用记录 |
| `resource_type` 清除 | **受限**：Phase 3.1 冻结 Non-Goal 不提供 `type_source: user → auto`；GUI 不伪造该能力 |

**Phase H2 关闭时保留的证据限制（2026-10-18，仍未解决）**：

1. A5 缺少 `fsck.log` 与 `fsck-unreachable.log` 原始输出；summary 中的退出码 0
   不能替代原始日志，该部分无法由独立审核直接复核。
2. A4 `push.log` 与 `prepush-dry-run.log` 的 SHA-256 相同
   （`2BA4313A8087177AEC805E86B5859CA8E6885B56FD0D5405FAA61DC55645AEEC`），
   降低了独立证明力；push 退出状态与推送后 refs 核验不能消除该缺陷。
3. 公开 refs 和 fresh clone 已核验，但不能证明 GitHub 服务端所有缓存、不可达
   对象、PR refs、fork 及协作者本地副本均已清除。
4. 没有清理任何备份、旧对象、staging/演练目录或测试临时文件；不得声称已完成
   历史材料清理。
5. 独立审核没有重新运行项目测试；A2 测试记录及候选内容与 A2 测试 tree 的
   一致性是既有依据，不得表述为独立复测通过。

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
- Phase 3.5 Closure Report（**CLOSED / CONDITIONAL PASS**，2026-10-24）：[phase3/PHASE3_5_CLOSURE_REPORT.md](./phase3/PHASE3_5_CLOSURE_REPORT.md)
- Phase H2 Closure Report（**CLOSED / CONDITIONAL PASS**，2026-10-18）：[PHASE_H2_CLOSURE_REPORT.md](./PHASE_H2_CLOSURE_REPORT.md)
- Phase 3.3 实施日志（含证据修订说明）：[phase3/PHASE3_3_LOG.md](./phase3/PHASE3_3_LOG.md)
- Phase 3.2 实施日志（含最终状态索引）：[phase3/PHASE3_2_LOG.md](./phase3/PHASE3_2_LOG.md)
- 证据缺口登记：[phase3/PHASE3_0_OPEN_EVIDENCE.md](./phase3/PHASE3_0_OPEN_EVIDENCE.md)
- 项目简介：[../README.md](../README.md)
