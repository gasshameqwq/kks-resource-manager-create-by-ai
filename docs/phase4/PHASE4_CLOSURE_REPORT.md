# Phase 4 — Duplicate Detection & Resource Relations

## Final Closure Report

> 文档类型：Phase 4 **最终关闭报告（Closure Report）**
>
> 日期：2026-10-24
>
> 状态：**CLOSED / CONDITIONAL PASS**

---

## Phase

Phase 4 — Duplicate Detection & Resource Relations

## Status

```text
CLOSED / CONDITIONAL PASS
```

Phase 4.1 已完成 byte-duplicate / SHA-256 Query Model 与 CLI 闭环；
Phase 4.2 已完成 PyQt6 重复状态筛选、同组副本展示、SHA-256 反查，以及作者 /
插件关系反查信号闭环。

“CONDITIONAL”来自仍未取得真实工作库的人工使用与目标平台视觉验收证据。实现、
自动测试、只读边界、schema 与 Git 收尾均已满足本阶段验收要求；上述证据缺口不构成
阻断，但不得被描述为已经关闭或取得使用证明。

## Contracts

- 冻结契约：[PHASE4_0_CONTRACT.md](./PHASE4_0_CONTRACT.md)（FROZEN）
- Phase 4.1 实施日志：[PHASE4_1_LOG.md](./PHASE4_1_LOG.md)
- Phase 4.2 实施日志：[PHASE4_2_LOG.md](./PHASE4_2_LOG.md)

Phase 4.0 / 4.1 冻结契约只定义只读 byte-duplicate、SHA-256 与 Query/CLI 扩展；
Phase 4.2 的用户批准任务另行覆盖 GUI 接入。本报告不扩展两者的冻结语义。

---

## Delivered

### Phase 4.1 — Query Model 与 CLI

- `ResourceFilter` 从 15 字段扩展为 17 字段：
  - `has_duplicates: bool | None`
  - `sha256: str | None`
- `BrowserScope.FILTER_KEYS` 从 14 键扩展为 16 键。
- `has_duplicates` 仅接受 `None` / `bool`；其他值抛 `ValueError`。
- `sha256` 去首尾空白，空串归一为 `None`。
- `ResourceQuery.count()` / `list()` 支持重复状态与 SHA-256 只读筛选。
- 重复状态通过既有 `resources.sha256` 在查询时派生：
  - `True`：非空哈希且存在同哈希其他资源；
  - `False`：空哈希，或不存在同哈希其他资源。
- SQL 使用 `idx_resources_sha256`；查询计划实测使用覆盖索引。
- CLI `query resources` 新增：
  - `--has-duplicates`
  - `--no-duplicates`
  - `--sha256`
  - `--author`
- 作者纯数字输入优先按 id 解析，否则精确名称匹配；未命中返回退出码 1，
  且不执行资源查询。
- `core/duplicate/__init__.py` 已移除过期 `content_key` / “Phase 4 实现”描述，
  明确纯只读派生与预留表零写入。

### Phase 4.2 — PyQt6 GUI

- FilterBar 新增重复三态：
  - 全部 → `None`
  - 仅重复 → `True`
  - 无重复 → `False`
- FilterBar 同步外部 SHA-256 过滤状态，展示短值 / 完整 tooltip，并提供清除入口。
- BrowserPanel 将 `has_duplicates` / `sha256` 写入 `BrowserScope`。
- `apply_relation_filter()` 支持 MOD、author、plugin、SHA-256，并统一从 `offset=0`
  重新加载。
- DetailPanel 消费 `duplicate_group_for()` 的 `DuplicateGroup`：
  - 成员数 > 1 时展示全部成员的 ID、名称与相对路径；
  - 提供“筛选同组副本”按钮，发出 `sha256_filter_requested(group.sha256)`。
- DetailPanel 作者按钮发出 `author_filter_requested(author_id)`。
- DetailPanel 插件项发出 `plugin_filter_requested(plugin_guid)`。
- MainWindow 将三个详情信号统一接入 BrowserPanel 关系过滤通道。

---

## Architecture Verification

```text
SCHEMA_VERSION == 2
MIGRATIONS == {1, 2}
BUSINESS_TABLES == 16
```

边界核验：

- Phase 4 未修改 schema、DDL、索引、migration 或数据库版本。
- `duplicate_groups` / `duplicate_members` 保持预留、零写入、零读取依赖。
- duplicate 结果完全由 `resources.sha256` 只读派生。
- `sha256` 相等只表示文件原始字节完全相同，不表示同角色、同 MOD 或可安全删除。
- `core/` 无 PyQt6 import，Query / CLI 不依赖 UI。
- `ui/` 无 `import sqlite3`、`sqlite3.connect(` 或 `.execute(`。
- UI 数据读取统一经 `BrowseService`，写入不在本阶段扩展。
- 未移动、改名或删除任何磁盘卡片 / MOD 文件。
- 未读取、写入或清理废弃的 `content_key`。

持久库只读核验：

```text
schema_version=2
business_tables=16
duplicate_groups=0
duplicate_members=0
```

---

## Verification

Phase 4.1 聚焦测试：

```text
147 passed in 17.63s
exit code 0
```

Phase 4.2 聚焦测试：

```text
5 passed in 0.38s
exit code 0
```

GUI 全套交叉回归：

```text
180 passed in 9.31s
exit code 0
```

只读护栏：

```text
22 passed, 978 deselected in 5.24s
exit code 0
```

最终关闭复验：

```text
pytest -q
1000 passed in 61.70s (0:01:01)
0 failed / 0 skipped
exit code 0
```

`1000 = Phase 3.5 基线 982 + Phase 4.1 新增 13 + Phase 4.2 新增 5`。

完整分项证据见：

- [PHASE4_1_LOG.md](./PHASE4_1_LOG.md)
- [PHASE4_2_LOG.md](./PHASE4_2_LOG.md)

---

## Git Evidence

| 节点 | Commit | Message | 文件 / 统计 |
| :--- | :--- | :--- | :--- |
| Phase 4.1 实施 | `21ad0c2` | `feat(phase4.1): expand query model and cli for duplicate and sha256 filtering` | 10 files, +810 / −42 |
| Phase 4.2 实施 | `37f6cab` | `feat(phase4.2): integrate duplicate filter, copy list and relation lookup into pyqt6 gui` | 6 files, +697 / −9 |
| Phase 4 最终关闭 | 本报告所在提交（自引用，不内嵌） | `docs(phase4): close phase 4 and update project state` | Closure + PROJECT_STATE + README |

阶段关闭 tag：

```text
phase-4-closed
Phase 4 — Duplicate Detection & Resource Relations: CLOSED (CONDITIONAL PASS)
```

tag 类型为 annotated，目标为 Phase 4 最终关闭提交。创建 tag 不等同于 push；
推送须由用户另行授权。

---

## Definition of Done

| # | 条件 | 结果 |
| :--- | :--- | :--- |
| 1 | `ResourceFilter` 17 字段 / `BrowserScope` 16 键 | ✅ |
| 2 | 重复三态、空哈希归属、SHA-256 精确筛选 | ✅ |
| 3 | CLI 重复 / SHA / 作者筛选与错误退出 | ✅ |
| 4 | GUI 重复三态、同组副本列表与 SHA 反查 | ✅ |
| 5 | GUI 作者 / 插件关系反查闭环 | ✅ |
| 6 | UI 零直接 SQL、core 零 PyQt6 依赖 | ✅ |
| 7 | schema v2 / 16 表 / 零 migration | ✅ |
| 8 | duplicate 预留表零写入 | ✅ |
| 9 | 全量测试 1000 passed、0 failed / 0 skipped | ✅ |
| 10 | 关闭文档、状态同步与 annotated tag | ✅ |

---

## Conditional Items

以下事项不阻断阶段关闭，但在本报告中如实保留：

1. **缺少真实工作库使用证据**：持久工作库仍为空；自动化验证使用临时合成库与真实
   样本只读查询，不能替代用户实际重复处理流程。
2. **缺少人工 GUI 验收**：Phase 4.2 使用离屏 Qt 自动化测试；尚未取得 Windows
   目标环境下的人工视觉、DPI、键盘操作与可用性验收记录。
3. **Phase 4.1 范围偏差已披露**：为同步既有 14/15 键过期断言，实际最小修改了
   允许清单之外的 `tests/test_browse.py`；变更只涉及 16/17 键断言与 docstring，
   不改变产品行为，详见 Phase 4.1 日志 §3.5。

## Open Items

- 未执行重复视图性能 benchmark；冻结契约未要求。
- 未提供语义重复、相似图片或 perceptual duplicate 判定；本阶段只支持 byte-identical。
- `duplicate_groups` / `duplicate_members` 仍为预留表，未建立确认、忽略或 canonical
  持久化工作流。
- 未实现自动删除、移动或重命名重复文件；该能力不在本阶段范围。

## Exclusions

Phase 4 未新增：

- schema 字段、业务表、DDL、索引或 migration；
- duplicate 结果持久化；
- 语义 / 感知相似度推断；
- 文件移动、改名、删除或内容修改；
- UI 直接 SQL 或数据库连接；
- Git push。

---

## Closure Boundary

- 本文件与 `docs/PROJECT_STATE.md`、`README.md` 同步 Phase 4 为
  **CLOSED / CONDITIONAL PASS**，测试基线为 **1000 passed**。
- 本次收尾仅修改 3 个文档文件。
- 未修改 `core/`、`ui/`、`tests/`、schema、DDL 或 migration。
- 未移动、改名或删除任何卡片 / MOD 文件。
- 创建 annotated tag `phase-4-closed`。
- 未执行 `git push`。
