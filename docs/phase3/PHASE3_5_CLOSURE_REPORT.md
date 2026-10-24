# Phase 3.5 — CLI / GUI Integration

## Final Closure Report

> 文档类型：Phase 3.5 **最终关闭报告（Closure Report）**  
> 日期：2026-10-24  
> 状态：**CLOSED / CONDITIONAL PASS**

---

## Phase

Phase 3.5 — CLI / GUI Integration

## Status

```text
CLOSED / CONDITIONAL PASS
```

本阶段已完成 Phase 3.5.1 CLI 写入口与 System-Tag Eager Bootstrap，并完成
Phase 3.5.2 PyQt6 筛选、Tag / Favorite 交互和用户字段编辑接线。

有条件通过的来源是已登记的 U1 / U2 证据缺口，以及 Phase 3.1 冻结契约未提供
`resource_type` 从用户修正恢复自动值的接口。上述事项没有被标记为已解决或已豁免。

## Contracts

- Phase 3 首期冻结 Contract：`docs/phase3/PHASE3_0_CONTRACT.md`
- Phase 3.5.1：`docs/phase3/PHASE3_5_1_IMPLEMENTATION_CONTRACT.md`（FROZEN）
- Phase 3.5.2：`docs/phase3/PHASE3_5_2_IMPLEMENTATION_CONTRACT.md`（FROZEN）
- 既有上游依赖：Phase 3.1、3.2、3.3 的冻结 Contracts

## Delivered

### Phase 3.5.1 — CLI 写入口与 Bootstrap

新交付 8 个 CLI 命令：

```text
tag create
tag list
tag rename
tag delete
resource add-tag
resource remove-tag
resource favorite
resource unfavorite
```

实现事实：

- 所有 `tags` / `resource_tags` 写入经 `TagWriteService`；
- Tag 冲突、保留系统 Tag 保护与幂等全部由服务层负责；
- CLI 不 import `sqlite3`，不包含 Tag 表直接写 SQL；
- 有效 CLI 启动通过 `TagWriteService.ensure_system_tags()` 幂等保证 Favorite 就绪；
- `main.py` 仅在启动 / 分发路径执行 bootstrap，不新增 schema 或 migration；
- 新增 `tests/test_cli_tags.py` 18 项测试；
- CLI focused 测试 `18 passed in 4.81s`；
- 本子阶段全量回归为 `961 passed in 89.34s`（943 基线 + 18 新增）。

### Phase 3.5.2 — PyQt6 GUI 集成

新交付：

- FilterBar Favorite 三态：全部 / 仅收藏 / 非收藏；
- FilterBar Tag 下拉，显示 Tag 名称与 resource_count；
- Tag / Favorite 经 `BrowserScope` → `ResourceFilter` 进入既有 Query Model；
- DetailPanel 展示已关联 Tag 与 Favorite 状态；
- 添加已有 Tag、新建并添加 Tag、移除 Tag；
- Favorite 收藏 / 取消收藏；
- `display_name` / `notes` 保存与清除；
- `resource_type` 用户修正保存；
- MainWindow 通过信号槽调用 `TagWriteService` / `ResourceWriteService`；
- 写入后重新读取 Tag 目录、当前筛选列表与详情；
- 当前资源因写入后不再匹配筛选时清空详情；
- 新增 `tests/test_ui_tags.py` 21 项测试；
- GUI focused + 既有 GUI 交叉回归 `110 passed in 9.76s`。

## Architecture Verification

```text
SCHEMA_VERSION == 2
MIGRATIONS == {1, 2}
BUSINESS_TABLES == 16
```

边界核验：

- `ui/` 无 `sqlite3` import、无 `.execute()`；
- UI 读取经 `BrowseService` / Query Layer；
- UI 写入经 `TagWriteService` / `ResourceWriteService`；
- `core/` 无实际 PyQt6 import；
- 未修改任何 DDL、索引、migration 或 schema；
- 未修改图片、角色卡或 MOD 文件；
- 未新增结构化文本查询语法。

## Verification

最终全量测试证据：

```text
pytest -q
982 passed in 125.38s (0:02:05)
0 failed / 0 skipped
exit code 0
```

982 = Phase 3.5.1 基线 961 + Phase 3.5.2 新增 21。

只读护栏：

```text
8 passed, 149 deselected in 3.57s
exit code 0
```

针对性 GUI 测试：

```text
21 passed in 3.24s
exit code 0
```

完整证据与命令见：

- `docs/phase3/PHASE3_5_1_LOG.md`
- `docs/phase3/PHASE3_5_2_LOG.md`

## Git Evidence

| 节点 | Commit | Message | 文件 / 统计 |
| :--- | :--- | :--- | :--- |
| Phase 3.5.1 | `96c7fab` | `feat(phase3.5.1): add cli tag commands and eager bootstrap` | 4 files, +951 / −1 |
| Phase 3.5.2 | `9bc1938` | `feat(phase3.5.2): integrate tag and favorite controls into pyqt6 gui` | 7 files, +1567 / −8 |
| Phase 3.5 最终关闭 | 本报告所在提交（自引用，不内嵌） | `docs(phase3.5): close phase 3.5 and update project state` | Closure + PROJECT_STATE + README |

Phase 3.5.1 文件：

```text
main.py
tests/test_cli_tags.py
docs/phase3/PHASE3_5_1_IMPLEMENTATION_CONTRACT.md
docs/phase3/PHASE3_5_1_LOG.md
```

Phase 3.5.2 文件：

```text
ui/browser_panel.py
ui/detail_panel.py
ui/filter_bar.py
ui/main_window.py
tests/test_ui_tags.py
docs/phase3/PHASE3_5_2_IMPLEMENTATION_CONTRACT.md
docs/phase3/PHASE3_5_2_LOG.md
```

## Definition of Done

| # | 条件 | 结果 |
| :--- | :--- | :--- |
| 1 | CLI 8 个命令可用并全部经 `TagWriteService` | ✅ |
| 2 | System-Tag Eager Bootstrap 幂等 | ✅ |
| 3 | GUI Tag / Favorite 筛选进入 Query Model | ✅ |
| 4 | GUI Tag / Favorite 写操作全部经 `TagWriteService` | ✅ |
| 5 | GUI 标量编辑全部经 `ResourceWriteService` | ✅ display_name / notes 保存与清除；resource_type 保存 |
| 6 | 写入后 UI 状态与列表刷新 | ✅ |
| 7 | 无直接 SQL / schema 变更 | ✅ |
| 8 | Phase 3.5 全量测试 | ✅ `982 passed`，0 failed / 0 skipped |
| 9 | 只读护栏 | ✅ `8 passed` |
| 10 | 文档与当前测试基线一致 | ✅ |

## Open Items

### U1 — 真实组织需求与标签粒度

`OPEN`。本阶段提供了 CLI 与 GUI 使用入口，但没有取得真实工作库的标签使用分布、
打标会话或用户粒度的明确陈述。实现完成不等于使用证据成立。

### U2 — CLI / GUI 入口偏好

`OPEN`。两个入口现均已存在，但尚无“首个真实入口、使用者与选择理由”的记录。
入口实现进度不构成 U2 的使用证据。

### resource_type 清除接口

Phase 3.1 冻结 Contract 的 Non-Goal 明确不提供：

```text
type_source: 'user' → 'auto'
```

因此当前 GUI 支持 `resource_type` 用户修正保存，但不提供“恢复自动类型”的清除操作。
禁止通过直接 SQL、错误类型值或猜测 machine fact 伪造该能力。若未来需要，应经新的
契约 / 服务 API 授权处理。

## Exclusions

本阶段未新增：

- schema 字段、业务表、DDL、索引或 migration；
- Favorite 第二持久化机制；
- 结构化搜索语法；
- 超出既有 Query Model 的筛选能力；
- 文件移动或文件内容修改。

## Closure Boundary

- 本文件与 `PROJECT_STATE.md`、`README.md` 同步 Phase 3.5 为
  **CLOSED / CONDITIONAL PASS**；
- 最终提交由用户在本轮明确授权的 G-3 收尾命令创建；
- 本阶段**未创建、移动或删除 tag**；
- 本阶段**未执行 push**。

