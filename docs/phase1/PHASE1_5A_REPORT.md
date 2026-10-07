# Phase 1.5-A 报告 —— Library GUI 管理

> 版本：`0.14.0` · `Phase 1.5-A (Library Admin GUI)` · schema v2（**未改动**）· 2026-10-07
>
> 目标：让用户**不打开终端**也能在 GUI 中管理 Library：
> Add / Enable / Disable / Remove，操作后刷新左栏，Add 后自动选中新库且不自动扫描。
>
> 本阶段**只做 1.5-A**：不实现 1.5-B（Scan Worker）/ 1.5-C（进度 / 取消）/ 1.5-D（文件监控）。

---

## 1. 新增 / 修改的文件

| 文件 | 类型 | 说明 |
| :--- | :--- | :--- |
| `core/app/__init__.py` | 新增 | Application 层入口，导出 `LibraryAdminService` |
| `core/app/admin.py` | 新增 | 极薄写操作服务：转发 `LibraryStore`（无 SQL、无新业务规则） |
| `ui/library_admin_dialog.py` | 新增 | `AddLibraryDialog` + `confirm_remove` / `build_removal_text`（移除确认文案） |
| `ui/library_panel.py` | 修改 | 左栏加管理按钮、写操作方法、`reload(select=...)` 选择策略 |
| `ui/main_window.py` | 修改 | 由同一条连接构造 `LibraryAdminService` 并注入左栏 |
| `tests/test_gui_library_admin.py` | 新增 | 18 个离屏 GUI 用例（Add / Enable / Disable / Remove） |
| `core/__init__.py` | 修改 | 版本 `0.13.0 → 0.14.0`，阶段 `Phase 1.5-A` |
| `docs/phase1/PHASE1_5A_REPORT.md` | 新增 | 本报告 |
| `README.md` / `docs/ARCHITECTURE.md` | 修改 | 状态行与路线图同步到 1.5-A |

**未改动**：`core/database/schema.py`、`core/database/db.py`、`core/parsers/*`、
`core/scanner/*`、`core/library/store.py`、`core/query/*`、`cli_query.py`、`main.py`、
真实样本目录。

`run_scan()` **未实现**（属 1.5-B）。

---

## 2. Application 层（`core/app/admin.py`）

```python
LibraryAdminService(conn)                      # 复用调用方连接
  .add_library(root_path, *, name, notes, enabled, allow_missing) -> Library
  .set_enabled(library_id, enabled) -> Library
  .preview_removal(library_id) -> LibraryRemovalReport
  .remove_library(library_id)  -> LibraryRemovalReport
```

- **只转发** `LibraryStore`：路径归一化、目录校验、重复拒绝、删除级联语义全部以
  `LibraryStore` 为准，本层不写 SQL、不做二次判断；
- **不引入** Manager / Controller / EventBus / 通用 Task Framework；
- 短操作用调用方连接；线程约束（`check_same_thread` 默认 True）已在 docstring 说明。

---

## 3. GUI 行为

### 3.1 Add

- 对话框选择目录 + 可选 `name` / `notes` / `enabled` / `allow_missing`（后两项沿用 CLI 语义）；
- 目录必须存在（`LibraryStore` 语义）；重复 `root_path` 抛 `LibraryAlreadyExists`，
  GUI 用 `QMessageBox.warning` 原样展示其消息，**不复制**归一化 / 去重逻辑；
- Library 名称**允许重复**，GUI 不加唯一性限制；
- Add 成功后 `reload(select=new_id)` → 刷新左栏并**自动选中新库**；
- **不自动扫描**（`resources` / `scan_records` 保持为空，`last_scan_at` 仍为 `None`）。

### 3.2 Enable / Disable

- `set_enabled` → 写库后 `reload(select=SELECT_KEEP)` **重新查询**，不做本地状态模拟；
- disabled 库仍在左栏显示（带 `[disabled]`），**不隐藏、不删除**，并且**仍可浏览**；
- 切换按钮文案（启用 / 暂停）来自查询结果，不来自本地猜测。

### 3.3 Remove

- 先 `preview_removal(library_id)`，再把预览信息放进确认框；
- 确认文案逐字表达真实语义：

```text
将移除资源库「<name>」
  · 只删除数据库中的库记录
  · 已入库的资源会保留（但不再属于任何库）
  · 不会删除或移动你的任何文件
  · 该库的扫描历史记录将被删除
```

- 默认按钮为「取消」；用户确认后才调用 `remove_library(library_id)`；
- 成功后 `reload(select=None)` → 刷新左栏、**清空当前 Library selection** →
  中栏（Browse）与右栏（Detail）回到空状态；
- 不碰文件系统、不删 `resources`、不执行额外清理。

### 3.4 状态一致性

GUI **不维护第二份 Library / resource 状态**：每次操作成功后一律调用
`self._service.libraries()`（Query Layer）重新读取再渲染。测试用「直接改库 → 刷新 → 生效」
证明了这一点。

### 3.5 扫描入口位置

左栏提供「立即扫描」按钮作为 **1.5-B 的入口位置**，本阶段保持 **disabled**
（tooltip 注明「Phase 1.5-B 提供」），**不实现任何扫描 / 进度 / 取消逻辑**，
也不伪造任何「扫描中」状态。

---

## 4. 测试

新增 `tests/test_gui_library_admin.py`（18 个用例，离屏、临时库 / 临时目录 / 临时缓存）：

| 验收点 | 用例 |
| :--- | :--- |
| GUI Add Library | `test_gui_add_library_appears_and_is_selected` / `..._button_adds_via_dialog_values` |
| Add 后出现在左栏 | `test_gui_add_library_appears_and_is_selected` |
| Add 后自动选中新库 | 同上 |
| Add 不自动 Scan | `test_gui_add_does_not_scan` |
| duplicate root_path 正确失败并显示错误 | `test_gui_add_duplicate_raises_existing_error` / `..._shows_warning` |
| name 可重复 / 支持 name·notes·enabled | `test_gui_add_supports_name_notes_and_disabled` |
| Enable / Disable 改数据库状态 | `test_gui_enable_disable_updates_database` / `..._toggle_button_flips_state` |
| disabled 仍可浏览 | `test_gui_disabled_library_is_not_hidden_and_still_browsable` |
| 刷新以数据库为准（非本地模拟） | `test_gui_reload_reads_state_from_database` |
| Remove 前出现确认 | `test_gui_remove_requires_confirmation` |
| Remove preview 语义正确（只读） | `test_gui_remove_preview_semantics` |
| Remove 后 Library 消失 | `test_gui_remove_only_deletes_db_record` |
| Remove 不删除 resources | 同上（资源保留、`library_id` 置空） |
| Remove 不碰文件系统 | 同上（`sample.read_bytes()` 不变） |
| Remove 后 scan_records 级联消失 | 同上 |
| 刷新后无残留 selection / Detail | `test_gui_remove_clears_selection_and_detail` |
| 只读边界 / 入口位置 | `test_gui_without_admin_service_is_read_only` / `..._scan_entry_point_present_but_not_wired` / `test_add_dialog_values_defaults` |

### 测试结果

```text
tests/test_gui_library_admin.py   18 passed
全套 pytest                        648 passed / 0 failed / 0 xfailed
```

（基线 630 passed + 新增 18。）

---

## 5. 回归确认

| 项 | 结果 |
| :--- | :--- |
| Phase 1.4-C 只读浏览未被破坏 | ✅ 全套 648 passed |
| BrowseService 边界未被破坏 | ✅ `ui/*` 仍不 import `sqlite3` / `ResourceQuery` / `LibraryQuery`（静态测试通过） |
| Preview 功能未破坏 | ✅ `test_gui_preview.py` 全绿 |
| LibraryStore 原有测试 | ✅ `test_library_store.py` 全绿 |
| Scanner 原有测试 | ✅ `test_scanner*.py` 全绿 |
| schema 未变化 | ✅ `SCHEMA_VERSION == 2`、`MIGRATIONS == [1, 2]` |
| CLI 未变化 | ✅ `main.py` / `cli_query.py` 未改动 |

---

## 6. 明确未做的事

- ❌ Scan Worker / 后台线程 / `run_scan()`（1.5-B）；
- ❌ progress / cancel（1.5-C）；
- ❌ filesystem watcher / 自动扫描 / 自动刷新（1.5-D）；
- ❌ EventBus / AppController / Manager 层 / MVVM-MVC 重构；
- ❌ 标签 / Collection / 批量文件操作；
- ❌ schema / Parser / Scanner / ResourceStore / Query Layer / LibraryStore 语义改动。

---

## 7. 已知遗留（P2，不阻塞 1.5-B）

1. **Remove 后统一清空 selection**：即使还剩余其它 Library，也按设计清空选中并让中 /
   右栏回到空状态；此时中栏显示的是「没有资源库」文案（沿用既有
   `NO_LIBRARY_TEXT`），语义上更准确的说法应是「未选择资源库」。是否需要区分
   「无库」与「未选中」属于后续 UI 文案优化，不影响本阶段验收。
2. **删除正在扫描的 Library**：`ScanWorker` 尚不存在，1.5-B 引入后台扫描后，
   必须在此补齐「禁止删除正在扫描的 Library」的约束（设计评审 §9-Q6）。
3. `AddLibraryDialog` 的「浏览…」使用 `QFileDialog.getExistingDirectory`，
   自动化测试未覆盖真实文件对话框（核心正确性用 `_prompt_add_library` 注入验证）。

---

## 8. 是否可进入 Phase 1.5-B

**可以。** 1.5-A 的 Add / Enable / Disable / Remove 闭环成立，写操作边界（GUI →
`LibraryAdminService` → `LibraryStore`）已立住，schema 与既有 core 语义零改动，
全套 648 passed。1.5-B 只需新增 `ui/scan_worker.py` 与扫描入口接线，并补上
「扫描进行中禁止删除同一 Library」这一约束。
