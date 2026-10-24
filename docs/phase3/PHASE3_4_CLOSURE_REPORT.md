# Phase 3.4 — User Classification & Search

## Final Closure Report

> 文档类型：Phase 3.4 **最终关闭报告（Closure Report）**
> 日期：2026-10-18
> 状态：**CLOSED / CONDITIONAL PASS**
> H2 历史对照更新：2026-10-21（旧 Git 值原样保留；清洗后对象与证据限制见
> “H2 Sanitized-History Correlation”）

---

### Phase

Phase 3.4 — User Classification & Search

### Status

```text
CLOSED / CONDITIONAL PASS
```

**有条件通过的来源**：核心实施与测试已完成，但仍有已记录的非阻断事项与历史证据限制
（见 Open Items）；它们未被解决、未被豁免、未被标记为已验证。
**阶段关闭时** tag/push 尚未执行；其后已完成（见 Post-Closure Publication）。

### Contract

- 权威实施契约：`docs/phase3/PHASE3_4_IMPLEMENTATION_CONTRACT.md`（**FROZEN**，2026-10-17，冻结提交 `632eb4c`）。
- 契约 blob 未修改：`b7b4ab7bb311c280b95472b2fa55950cab29aace` == `HEAD:`。
- 前置：Phase 3.3 = CLOSED / CONDITIONAL PASS（tag `phase-3.3-closed`）。
- Implementation commit：`ef362fd19e79a67dd496ef5751393244844131a2`。
- 文档状态修正 commit：`9e694cf1573ba744ec26f896fe36413a6ac483ff`。
- 最终关闭提交：即本报告所在提交（自引用，不内嵌自身 hash）。

> **历史口径**：以上是 H2 前的阶段关闭证据，必须原样保留。H2 重写历史后，
> 当前远端谱系中的对应对象见下方“H2 Sanitized-History Correlation”。旧提交号
> 不再直接指向当前远端谱系，但其历史记录不能被静默替换。

### Implementation

零功能增量路径：**无生产代码变更**。

- **T-A1**：`tests/test_search_core.py` 新增 2 个用例，分别验证 FTS 与 LIKE 路径均可命中覆盖后的 `display_name`。
- **T-A2**：同文件新增 1 个用例，验证覆盖后旧 `name` 仍命中（现行语义）。
- **T-B**：`tests/test_database_schema.py` 新增 1 个用例，直接验证 FTS `display_name` 列的更新同步（四项断言 + rowid）。
- **T-C**：`tests/test_query_model.py` 新增 1 个用例，验证用户类型修正后的有效类型筛选与 `type_source='user'`。
- `docs/ARCHITECTURE.md`：完成 D1–D7 与 §4.1.1 七项范围修订（Query Model 数据流、Tag/Favorite 语义、effective type、FTS/LIKE、目录树、索引、路线图）。
- `docs/phase3/PHASE3_4_LOG.md`：记录 Step 0、架构审计、测试命令与结果。

### Verification

| 项 | 实际结果 |
| :--- | :--- |
| focused（5 个新用例） | `5 passed, 134 deselected in 1.31s` |
| 全量 `pytest -q` | `943 passed in 52.07s` |
| G-3 提交前复跑 | focused `5 passed`（0.19s，exit 0）；full `943 passed`（43.07s，exit 0） |
| 只读护栏 | `8 passed, 149 deselected in 2.04s` |
| schema | `SCHEMA_VERSION == 2` / `MIGRATIONS == {1, 2}` / 16 表 |
| 生产代码 diff | 空 |
| 契约 blob | 与 `HEAD:` 一致 |

### Git

| 项 | 值 |
| :--- | :--- |
| Implementation commit | `ef362fd19e79a67dd496ef5751393244844131a2` |
| 父提交 | `632eb4c7dcaa593208c2a52911273896cbb2cef7` |
| Message | `test(phase3.4): verify display name and effective type behavior` |
| 文件 / 统计 | 8 files changed, 459 insertions(+), 21 deletions(-) |
| 文档修正 commit | `9e694cf1573ba744ec26f896fe36413a6ac483ff`（3 files，+54/−6） |
| 最终关闭提交 | 本报告所在提交（自引用，不内嵌） |
| Phase 3.4 tag | 阶段关闭时未创建；后续已创建 `phase-3.4-closed`（见 Post-Closure Publication） |
| Push | 阶段关闭时未执行；后续已推送至 `origin` |

### Post-Closure Publication（H2 前发布记录，2026-10-18）

下表保留 H2 前的发布记录，不改变 `CLOSED / CONDITIONAL PASS` 结论。H2 之后
远端同名 tag 已重写；当前远端对象不得从本历史表推定。

| 项 | 值 |
| :--- | :--- |
| Tag | `phase-3.4-closed`（annotated） |
| Tag object | `0cae547c7c21cc1a754b147726f022a3396d38c3` |
| Peeled commit | `6553333f832de03468af7945294002ba37d040ef` |
| Remote | `origin` → `https://github.com/gasshameqwq/kks-resource-manager-create-by-ai.git` |
| Push | 已完成（仅推送 `refs/tags/phase-3.4-closed`） |
| Remote verification（H2 前，2026-10-18） | 当时 `git ls-remote` 返回上表相同 tag object 与 peeled commit |

### H2 Sanitized-History Correlation（2026-10-21）

以下只增加对照，不替换本报告上方保留的 H2 前历史值：

| 节点 | H2 前对象（保留） | 清洗后对象（当前谱系） | 证据 |
| :--- | :--- | :--- | :--- |
| Contract 冻结 | `632eb4c7dcaa593208c2a52911273896cbb2cef7` | `7704a98a4569f8148494a0618bb11019ef1e1189` | patch-id `4caba32e90bd9d13eeb4c53162ef876a1b9177cb` 相同 |
| Implementation | `ef362fd19e79a67dd496ef5751393244844131a2` | `efffae65c2d66256b5522704a77f50cf38917687` | patch-id `c77848125b32ae263297b36f52aa77861fbc5fa9` 相同 |
| 文档状态修正 | `9e694cf1573ba744ec26f896fe36413a6ac483ff` | `0c1ea2ceff2a2c9e01470ad4a4ecdd592ee113e5` | patch-id `270c4ce46b341600c2a3fe0ff3ce77b5f41ed158` 相同 |
| 正式关闭 | `6553333f832de03468af7945294002ba37d040ef` | `11d2a1498ab63d3b3518e6723337185a5321c347` | patch-id `24da1c0132a74a70c68b13ecefc5f78aacc6f539` 相同 |
| 关闭后状态协调 | `442a980a994614623405ecf3243f90e461991ea0` | `198908c299472672be6ed5590c9a3ddfaeca234a` | patch-id `c7afb8d051075bcd2b8ad3ff767b2389ea5404f8` 相同 |
| tag `phase-3.4-closed` | object `0cae547c7c21cc1a754b147726f022a3396d38c3` → `6553333...` | 远端 object `294336feeac2a9813f21d11a8a147fa522c71fd5` → `11d2a149...` | 2026-10-21 只读 `git ls-remote` |

**证据强度**：五组提交除 patch-id 相同外，提交说明、作者时间与父链位置也对应；
这是仓库内可以重复复核的强关联。它不是 H2 报告中已正式发布的完整映射表，也不
证明新旧提交的整棵树在所有上下文中逐字节相同。A4/A5 原始证据本次未直接复核。

**tag 特别限制**：新旧 tag 注释正文都仍写着旧 closure commit `6553333...`；
远端 tag 的实际 peeled target 由 `git ls-remote` 核验为 `11d2a149...`。因此不能仅凭
tag 注释正文判断当前目标。

### Definition of Done 核对

| # | 条件 | 结果 |
| :-- | :--- | :--- |
| 1 | §1.3 六项目标逐项有证据 | ✅（LOG §2–§3 + 测试） |
| 2 | 未批准范围零改动；diff 与批准范围一致 | ✅（仅 3 个测试文件 + ARCHITECTURE + LOG/Closure/状态行） |
| 3 | 全量测试成功并记录命令/结果 | ✅ `943 passed in 52.07s` |
| 4 | 环境问题导致无法全量运行 → 阻断 | ✅ 未发生 |
| 5 | 未解决失败/证据不足不得转通过 | ✅ 无未解决失败 |
| 6 | 测试修订仅限 §4.3.1 三文件与对应 T-ID | ✅ 5 个新增函数 |
| 7 | 架构审计限 §4.1.1 七项 | ✅ LOG §3 |
| 8 | IS4 七项逐项证据；未授权冲突记未解决 | ✅ 无未授权冲突；七项均有处理 |
| 9 | ARCHITECTURE 与实际实现一致 | ✅ |
| 10 | LOG/Closure/状态文件一致；冻结契约未改 | ✅ |
| 11 | 零 schema、DTO、只读、筛选、CLI、搜索语义不变 | ✅ 全量回归 + 护栏 |
| 12 | 无生产代码变更时显式声明 | ✅ 见上 |
| 13 | 零增量不豁免验证 | ✅ 全量测试已跑 |
| 14 | Step 0 按 §6.1 记录 | ✅ LOG §2 |
| 15 | 阶段未自动关闭 | ✅ 用户已接受 `CLOSED / CONDITIONAL PASS`（2026-10-18） |

### Scope

- 本阶段只做核验 + 文档 + 测试；未修改 `core/**`、`cli_query.py`、`main.py`、`ui/**`、schema、迁移或 DTO。
- 未改变 `display_name` 搜索语义；未给 `--type` 增加校验；Resource Taxonomy 继续暂缓。
- G-3 的提交前核验、focused/全量测试、implementation commit `ef362fd`、文档修正 commit
  `9e694cf` 与提交后核验已完成；**阶段关闭时 tag/push 尚未执行；其后已完成**（见 Post-Closure Publication）。
- `PROJECT_STATE.md` / `README.md` / 本报告 / `PHASE3_4_LOG.md` 已同步为
  `CLOSED / CONDITIONAL PASS`；`docs/ARCHITECTURE.md` 的 3.4 状态行已在后续文档一致性修复中
  同步。关闭时曾记录为“工作区修改，未提交”；该时点状态后由 `198908c`
  纳入版本控制，当前历史对照见上面 H2 小节。

### Open Items

1. **用户已接受 `CLOSED / CONDITIONAL PASS`（2026-10-18）**；非阻断事项保留。
2. **r6 → 冻结版差异未独立验证**：历史证据限制继续保留，未因本轮实施而改变。
3. **U1 / U2** 仍为 OPEN（真实组织需求 / GUI 入口偏好），不属本阶段阻断项。
4. **`--type` 未知值静默空结果**：按冻结决定仅记录，未改行为。
5. **性能 benchmark**：Non-Goal，未做。
6. **T-A2 未直接断言 `display_name` 最终写入值**：T-A1 已覆盖写服务生效，属非阻断。

### Resolved After Closure

- **Tag / push**：阶段关闭时未执行；2026-10-18 已创建 annotated tag `phase-3.4-closed`
  并推送至 `origin`（见 Post-Closure Publication）。
- **ARCHITECTURE 3.4 状态行**：已在后续文档一致性修复中同步（工作区修改，未提交）；
  不再作为未解决事项。
- **Phase 3.3 冻结段落状态漂移**：`PROJECT_STATE.md` 中“尚未实施 / 未关闭”的旧当前状态
  描述已于 2026-10-18 的关闭后文档维护中改为“契约冻结时点的历史状态 + 后续关闭事实”，
  不再作为未解决事项；不改变 Phase 3.3 的 `CLOSED / CONDITIONAL PASS` 结论或
  `phase-3.3-closed` tag。

### Evidence

- 实施日志：`docs/phase3/PHASE3_4_LOG.md`
- 测试：`tests/test_search_core.py`、`tests/test_database_schema.py`、`tests/test_query_model.py`
- 架构：`docs/ARCHITECTURE.md`
- Commit 证据：`ef362fd19e79a67dd496ef5751393244844131a2`（implementation）、
  `9e694cf1573ba744ec26f896fe36413a6ac483ff`（文档修正）。清洗后对应提交分别为
  `efffae65c2d66256b5522704a77f50cf38917687` 和
  `0c1ea2ceff2a2c9e01470ad4a4ecdd592ee113e5`。
