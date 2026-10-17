# Phase 3.4 — User Classification & Search

## Implementation Closure Report

> 文档类型：Phase 3.4 **实施完成报告**（不是最终 CLOSED 结论）
> 日期：2026-10-17
> 状态：**IMPLEMENTATION COMPLETE / PENDING USER ACCEPTANCE**

---

### Phase

Phase 3.4 — User Classification & Search

### Status

```text
IMPLEMENTATION COMPLETE / PENDING USER ACCEPTANCE
```

**不是 CLOSED，也不是 PASS。** 本报告只记录实施完成与 DoD 证据；最终验收与 G-3
Git 收尾仍由用户决定。

### Contract

- 权威实施契约：`docs/phase3/PHASE3_4_IMPLEMENTATION_CONTRACT.md`（**FROZEN**，2026-10-17，冻结提交 `632eb4c`）。
- 契约 blob 未修改：`b7b4ab7bb311c280b95472b2fa55950cab29aace` == `HEAD:`。
- 前置：Phase 3.3 = CLOSED / CONDITIONAL PASS（tag `phase-3.3-closed`）。

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
| 只读护栏 | `8 passed, 149 deselected in 2.04s` |
| schema | `SCHEMA_VERSION == 2` / `MIGRATIONS == {1, 2}` / 16 表 |
| 生产代码 diff | 空 |
| 契约 blob | 与 `HEAD:` 一致 |

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
| 15 | 阶段未自动关闭 | ✅ 待用户验收 |

### Scope

- 本阶段只做核验 + 文档 + 测试；未修改 `core/**`、`cli_query.py`、`main.py`、`ui/**`、schema、迁移或 DTO。
- 未改变 `display_name` 搜索语义；未给 `--type` 增加校验；Resource Taxonomy 继续暂缓。
- 未执行 G-3：无 commit、tag、push。
- 状态行已同步为「实施完成，待用户验收」，**不是**「CLOSED」。

### Open Items

1. **用户验收尚未作出**：阶段未 CLOSED。
2. **G-3 未授权**：提交、tag、push 均未执行。
3. **r6 → 冻结版差异未独立验证**：历史证据限制继续保留，未因本轮实施而改变。
4. **U1 / U2** 仍为 OPEN（真实组织需求 / GUI 入口偏好），不属本阶段阻断项。
5. **`--type` 未知值静默空结果**：按冻结决定仅记录，未改行为。
6. **性能 benchmark**：Non-Goal，未做。

### Evidence

- 实施日志：`docs/phase3/PHASE3_4_LOG.md`
- 测试：`tests/test_search_core.py`、`tests/test_database_schema.py`、`tests/test_query_model.py`
- 架构：`docs/ARCHITECTURE.md`
