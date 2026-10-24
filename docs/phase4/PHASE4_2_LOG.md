# Phase 4.2 — PyQt6 重复视图与关系反查闭环实施日志

> 状态：实施完成（待独立审核与用户验收）
>
> 日期：2026-10-24
>
> 依据：[PHASE4_0_CONTRACT.md](./PHASE4_0_CONTRACT.md)（FROZEN）

---

## 1. 基线

- 实施开始 HEAD：`21ad0c2`
- 既有测试基线：`995 passed`
- schema：v2 / 16 张业务表
- 环境：项目 `.venv` / Python 3.12.10 / PyQt6 / 离屏 Qt 平台
- `duplicate_groups` / `duplicate_members`：只读边界，保持零写入

---

## 2. 实施步骤

### 2.1 FilterBar

- 新增“重复”三态下拉：
  - 全部 → `None`
  - 仅重复 → `True`
  - 无重复 → `False`
- 新增 SHA-256 筛选状态标签与“清除 SHA”入口。
- 外部传入 SHA-256 时同步显示值（短值展示、完整值 tooltip），并可清除。
- `has_duplicates` / `sha256` 通过既有 `criteria_changed` 信号驱动刷新。

### 2.2 BrowserPanel

- `scope()` 将 `has_duplicates` / `sha256` 写入 `BrowserScope`。
- `apply_relation_filter()` 支持 MOD、author、plugin、SHA-256。
- 关系筛选统一进入既有 `reload()` 路径，分页从 `offset=0` 开始。
- 空结果判定将重复状态与 SHA-256 也视为 active filter。

### 2.3 DetailPanel

- 消费 `BrowseService.duplicate_group_for()` 传入的 `_current_duplicate_group`。
- 当组内成员数大于 1 时：
  - 展示全部成员的 ID、名称、相对路径；
  - 启用“筛选同组副本”按钮；
  - 点击发出 `sha256_filter_requested(group.sha256)`。
- 作者由可点击按钮展示，点击发出 `author_filter_requested(author_id)`。
- 插件列表项可点击，点击发出 `plugin_filter_requested(plugin_guid)`。

### 2.4 MainWindow

- 统一接通：
  - `sha256_filter_requested`
  - `author_filter_requested`
  - `plugin_filter_requested`
- 三个信号均转入 `BrowserPanel.apply_relation_filter()`，不复制查询逻辑。

### 2.5 测试

- 新增 `tests/test_ui_duplicate_relation.py`。
- 覆盖：
  - 重复三态与 `BrowserScope` / 结果联动；
  - 外部 SHA-256 状态同步、清除与 offset=0；
  - 重复组全部成员渲染与 SHA 信号；
  - 作者、插件信号及 BrowserPanel 反查闭环；
  - 关系筛选重置分页。

---

## 3. 测试证据

### 3.1 针对性测试

```text
python -m pytest tests/test_ui_duplicate_relation.py -v
```

结果：

```text
5 passed in 0.38s
exit code 0
```

### 3.2 UI 文件交叉测试

PowerShell 不会展开传给 pytest 的 `tests/test_ui_*.py` 通配符；实际显式运行同一范围：

```text
python -m pytest tests/test_ui_duplicate_relation.py tests/test_ui_tags.py -q
```

结果：

```text
26 passed in 3.14s
exit code 0
```

### 3.3 GUI 全套交叉回归

仓库其余 GUI 测试使用 `test_gui_*.py` 命名，实际运行：

```text
python -m pytest tests/test_gui_smoke.py tests/test_gui_scan.py
  tests/test_gui_preview.py tests/test_gui_library_admin.py
  tests/test_gui_filters.py tests/test_gui_detail.py
  tests/test_relation_browse.py -q
```

结果：

```text
180 passed in 9.31s
exit code 0
```

### 3.4 只读护栏

```text
python -m pytest -q -k "read_only or do_not_write or duplicate_groups"
```

结果：

```text
22 passed, 978 deselected in 5.24s
exit code 0
```

### 3.5 全量回归

```text
python -m pytest -q
```

结果：

```text
1000 passed in 53.64s
exit code 0
```

`1000 = 既有 995 + 新增 5`，0 failed / 0 skipped。

---

## 4. 架构合规

### 4.1 core 零 PyQt6 导入

```text
git grep -n -E -e "^(from|import) PyQt6" -- core/
```

无匹配（退出码 1）。

注：宽泛命令 `git grep "PyQt6" core/` 会命中 `core/__init__.py` 中说明
“不 import PyQt6”的 docstring，但不是 Python 导入。

### 4.2 UI 零直接数据库 / SQL

```text
git grep -n -E -e "import sqlite3|sqlite3\.connect\(|\.execute\(" -- ui/
```

无匹配（退出码 1）。

任务给出的宽泛谓词 `connect\(` 会同时匹配 Qt 的
`signal.connect(slot)`，不能作为“无数据库连接”的判据；因此使用上述精确数据库谓词。

---

## 5. 边界确认

- 未修改 `core/`、schema、DDL 或 migration。
- 未修改任何卡片或 MOD 文件。
- GUI 只消费 `BrowseService` DTO，不直接查询数据库。
- duplicate 视图完全复用既有只读派生查询。
- 未执行 `git add`、commit、tag 或 push。
