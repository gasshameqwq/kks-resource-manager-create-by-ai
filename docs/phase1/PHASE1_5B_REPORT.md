# Phase 1.5-B 报告 —— GUI 扫描（后台执行 + 统一刷新）

> 版本：`0.15.0` · `Phase 1.5-B (Scan GUI)` · schema v2（**未改动**）· 2026-10-07
>
> 目标：在 GUI 中执行 Incremental Scan / Full Scan，后台 worker 执行，扫描期间显示运行
> 状态，扫描完成后统一重新从 Query Layer 刷新 GUI。
>
> 本阶段**只做 1.5-B**：不实现 1.5-C（progress / cancel）、1.5-D（文件监控 / 自动刷新）。

最终目标（本阶段的验收标准）：

```text
GUI 只是 Scanner 的另一个入口；Scanner 仍然是唯一扫描逻辑；
数据库仍然是事实来源；Query Layer 仍然是 GUI 浏览状态的来源；
worker 只负责后台执行和传递结果。
```

---

## 1. 实际修改 / 新增的文件

| 文件 | 类型 | 说明 |
| :--- | :--- | :--- |
| `ui/scan_worker.py` | 新增 | `ScanSignals` + `ScanWorker(QRunnable)`（后台扫描） |
| `core/app/admin.py` | 修改 | 新增模块级 `run_scan(...)`；`LibraryAdminService` 增 `database_path()` |
| `core/app/__init__.py` | 修改 | 导出 `run_scan` |
| `ui/library_panel.py` | 修改 | 扫描按钮（增量 / 全量）、扫描任务状态、Remove 竞态防护 |
| `ui/main_window.py` | 修改 | 扫描编排、完成后统一刷新、`closeEvent` 生命周期 |
| `tests/test_gui_scan.py` | 新增 | 23 个用例（worker + GUI + 真实扫描行为） |
| `tests/test_gui_library_admin.py` | 修改 | 1 个用例（1.5-A 的「入口未接线」断言 → 1.5-B「入口已接线」） |
| `core/__init__.py` | 修改 | 版本 `0.14.0 → 0.15.0`，阶段 `Phase 1.5-B` |
| `README.md` / `docs/ARCHITECTURE.md` | 修改 | 状态与路线图同步 |
| `docs/phase1/PHASE1_5B_REPORT.md` | 新增 | 本报告 |

**未改动**：`core/database/*`、`core/parsers/*`、`core/scanner/*`、`core/query/*`、
`core/library/store.py`、`cli_query.py`、`main.py`、`ui/browser_panel.py`、
`ui/filter_bar.py`、`ui/preview_worker.py`、`ui/detail_panel.py`、真实样本目录。

---

## 2. ScanWorker 架构

```text
MainWindow.start_scan(mode)
    ↓  ScanWorker(db_path, library_id, mode)          # 只在 GUI 线程构造
    ↓  QThreadPool.globalInstance().start(worker)
worker thread
    ↓  ScanWorker.run()
    ↓  core.app.run_scan(db_path, library_id, mode)    # 自开自关连接
    ↓  LibraryScanner(conn).scan(...)                  # 唯一扫描逻辑
    ↓  emit started() / finished(result) / failed(library_id, message)
GUI thread（队列连接）
    ↓  MainWindow._on_scan_finished / _on_scan_failed
```

`ScanSignals(QObject)`：

```python
started  = pyqtSignal()
finished = pyqtSignal(object)      # ScanResult
failed   = pyqtSignal(object, str) # library_id, message
```

> 说明：`failed` 在「至少提供 failed(message)」的基础上额外带上 `library_id`，
> 目的只有一个 —— GUI 需要知道是哪一次扫描失败，才能清除对应的「扫描中」状态。
> 消息本体仍是 `message`。

约束（全部满足）：

- 与 `PreviewWorker` **同构但独立**（`QRunnable` + `QObject` 信号 + `QThreadPool`），
  不做通用 Worker 抽象；
- **不接触任何 QWidget / Qt Model / QMessageBox**；
- **不刷新 Query、不缓存结果、不做进度 / 取消**；
- 不接收 GUI 线程的 SQLite 连接，只拿 `db_path`。

---

## 3. `run_scan()` 的 connection 生命周期

```python
def run_scan(db_path, library_id, *, mode="incremental") -> ScanResult:
    conn = database.connect(db_path)      # 在**调用线程**里新建连接
    try:
        return LibraryScanner(conn).scan(library_id, mode=mode)
    finally:
        conn.close()                      # 成功 / 异常都必须关闭
```

- 为什么不接收连接：`db.connect()` 默认 `check_same_thread=True`，连接绑定创建它的线程
  —— GUI 线程的连接**不能**在 worker 线程里用；
- **没有**修改 `db.connect()` 的线程策略，**没有**使用 `check_same_thread=False`；
- `finally` 保证无论成功、`scan_records` 写入失败、还是 Library 不存在，连接都关闭；
- `run_scan` 内**没有**任何扫描规则：模式、解析、入库、missing 判定全部由
  `LibraryScanner` 决定。

---

## 4. Incremental / Full 行为

| GUI 动作 | 调用 | 等价于 |
| :-- | :-- | :-- |
| 「扫描」（主操作，`scan_button`） | `start_scan("incremental")` | `python main.py scan` |
| 「全量重扫」（次级，`full_scan_button`） | `start_scan("full")` | `python main.py scan --full` |

GUI **不实现任何扫描规则**（不比对 path / size / mtime，不解析，不判 missing，
不插入 / 更新资源）。增量与全量的差异完全由现有 `LibraryScanner.scan(mode=...)` 决定。

Add Library 后仍然：自动选中新库、**不自动扫描**，需用户显式点扫描（1.5-A 行为保持）。

---

## 5. GUI 状态管理

`MainWindow` 维护唯一的**任务运行状态** `_scanning: dict[library_id, ScanWorker]`
（不是 Library / resource 的第二份数据库状态）：

- worker 启动 → 加入；`finished` / `failed` → 移除；
- `LibraryPanel.set_scanning_library_ids(ids)` 同步这份集合用于渲染与禁用。

扫描期间的 UI：

- 左栏该项显示 `[扫描中…]`；当前选中项的状态标签显示「扫描中…」；
- 扫描按钮 / 全量扫描按钮禁用；被扫描 Library 的移除 / 启停按钮禁用；
- **同一 Library 不重复启动、不排队**：`start_scan` 检测到已在扫描直接返回 `None`，
  再次点击不会创建第二个 worker；
- 允许浏览 / 切换其它 Library（只读），`_on_library_selected` 不受扫描影响。

**单扫描策略（有意为之）**：同一时刻最多一个扫描 worker（不同 Library 也不并发）。
原因：`db.connect()` 未设置 `busy_timeout`，两个扫描并发写会争用 SQLite 写锁，可能出现
`database is locked`。单扫描既满足「同一 Library 不重复启动」，又避免这一风险；
本阶段需求未要求并发扫描。

---

## 6. scanning Library 的 Remove 防护

**不只依赖按钮禁用**：`LibraryPanel._on_remove_clicked()` 在弹确认框之前显式检查

```python
if library.id in self._scanning_ids:
    QMessageBox.information(self, "无法移除", "该资源库正在扫描，请等待扫描完成。")
    return          # 不调用 preview_removal / remove_library
```

- 即使按钮被程序化点击（直接调用槽），也**不会**执行移除；
- 非扫描中的 Library 仍可正常移除（扫描 A 时移除 B 有专门用例验证）；
- 扫描状态在 `finished` / `failed` 后移除，按钮随之恢复。

---

## 7. Scan 完成后的 Query 刷新链

```text
ScanWorker.finished(result)          # 只在 GUI 线程处理
    ↓ MainWindow._on_scan_finished
    ├─ 从 _scanning 移除 library_id（清扫描状态）
    ├─ LibraryPanel.reload(select=SELECT_KEEP)      # 名称 / enabled / resource_count
    ├─ BrowserPanel.reload_relation_options()       # 作者 / 插件 / 缺失 MOD 下拉
    ├─ BrowserPanel.reload()                        # 资源列表 + total + 空态
    └─ DetailPanel 由 reload 清空 selection → 回到空状态（现有链路）
```

原则：

- **不从 `ScanResult` 推导资源变化**、**不把 ScanResult 存成 GUI 状态**；
  `ScanResult` 只用于「是否成功 / 一句完成提示 / 是否刷新」；
- 只有 `status == completed` 才刷新；`skipped` / `failed` **不假装成功**；
- 保持用户当前 selection：扫的是 A 而用户在浏览 B 时，不强制切回 A；
- GUI 仍然只经 `BrowseService`（不 import `sqlite3`、不碰 `ResourceQuery` /
  `LibraryQuery`、不写 SQL）。

完成提示示例：`扫描完成：发现 22，新增 22，更新 0，跳过 0，缺失 0，失败 0`。

---

## 8. closeEvent / worker 生命周期

```text
closeEvent
    ↓ _prepare_to_close()
    ├─ 有扫描在跑：confirm_close_during_scan()「扫描仍在进行，是否等待完成后退出？」
    │     ├─ 取消 → event.ignore()（窗口不关，扫描继续）
    │     └─ 等待 → QThreadPool.waitForDone(CLOSE_WAIT_MS=15s)
    │            ├─ 完成 → 正常关闭
    │            └─ 超时 → confirm_keep_waiting()「继续等待 / 现在退出」
    │                   ├─ 继续等待 → 循环再等
    │                   └─ 现在退出 → 走退出流程（仍给 5s 兜底等待）
    └─ 无扫描 → 沿用 C-5 的 waitForDone(5s)
```

保证：

- **不主动杀线程**：QRunnable 无法安全中断，本阶段不引入 `cancel`；
- **不从 GUI 线程关闭 worker 的连接**：连接由 `run_scan()` 的 `finally` 关闭；
- widget 不会被 worker 触碰（worker 不持有任何 QWidget），因此不会出现
  「QWidget 已销毁而 worker 还在操作」；
- `-wal` / `-shm`：worker 连接正常关闭，扫描写入是逐文件事务，不会留下半写状态。

---

## 9. 测试

新增 `tests/test_gui_scan.py`（23 个用例，全部离屏、临时库 / 临时目录 / 临时缓存）：

**Worker（6）**：incremental 成功、full 成功、第二次 incremental 跳过且无重复、
`failed` 正确 emit、`finished` 正确 emit、连接被关闭（`ProgrammingError` 证明）、
连接在 **worker 线程**创建（线程 id 与主线程不同）。

**GUI 扫描（11）**：点击增量 / 全量启动 worker、扫描期间按钮禁用、同一 Library 不能
重复启动、扫描期间可浏览 / 切换其它 Library、finished 清状态、failed 清状态并恢复按钮、
skipped 不当作完成、Add 后不自动 scan、扫描完成后 Library count 刷新、Browse 刷新、
relation options 刷新、当前 selection 保持。

**Remove 竞态（2）**：扫描中的 Library 不能移除（直接调用槽也被拦下 + 明确提示）、
非扫描 Library 仍可移除。

**closeEvent（2）**：取消等待时窗口不关闭且扫描继续、选择等待后扫描完成才关闭。

**真实 Scanner 行为**（含在上述用例中）：Add → Incremental Scan → `resource_count`
正确 → Browse 正确 → 再次 Incremental Scan 无重复；Full 重新解析（`updated`）。
全部在**临时样本副本**上执行，真实样本未参与。

### 测试结果

```text
tests/test_gui_scan.py    23 passed
全套 pytest               671 passed / 0 failed / 0 xfailed
```

（1.5-A 基线 648 + 新增 23。）

---

## 10. 完整 pytest 结果

```text
671 passed in 31.66s
```

重点回归全部通过：`test_gui_library_admin.py`、`test_gui_preview.py`、
`test_gui_detail.py`、`test_gui_filters.py`、`test_relation_browse.py`、
`test_library_store.py`、`test_scanner*.py`、`test_query_layer.py`、`test_browse.py`、
`test_gui_smoke.py`（含 UI 静态边界测试：`ui/*` 不 import `sqlite3` /
`ResourceQuery` / `LibraryQuery`）。

---

## 11. schema 是否变化

**没有。** `SCHEMA_VERSION == 2`、`MIGRATIONS == [1, 2]`、无新增列 / 表 / 索引。

---

## 12. core scanner 语义是否变化

**没有。** `core/scanner/*` 一个字符未改：`LibraryScanner.scan()`、增量判定、
missing 标记、`scan_records` 写入、disabled → `skipped` 语义全部原样。
本阶段只是**新增了一个调用入口**（`core.app.run_scan`）。

「GUI 不得重新实现 disabled 判断」也已满足：暂停的 Library 仍会调用 Scanner，
由 Scanner 返回 `status="skipped"` + `skip_reason`，GUI 只负责展示。

---

## 13. 1.5-C / 1.5-D 是否保持未实现

**保持未实现。** 没有 progress callback / percentage / progress bar / cancel 按钮 /
`should_cancel` / filesystem watcher / 自动扫描 / 文件变化提示 / EventBus /
AppController / TaskManager / 通用 Worker 基类 / MVVM 重构。

---

## 14. 遗留问题

1. **单扫描策略**（P3）：同一时刻只允许一个扫描。若将来要支持「并发扫描不同 Library」，
   需要先解决 SQLite 写锁争用（例如给连接设置合理的 `busy_timeout`），属于 core 改动，
   需由真实需求驱动。
2. **relation 筛选会被重置**（P2）：`reload_relation_options()` 会重建三个下拉，
   把用户当前的作者 / 插件 / 缺失 MOD 筛选恢复成「全部」。这在既有实现里就是这样
   （1.4-C 的 `set_relation_options`）；本阶段未改 `browser_panel.py` / `filter_bar.py`，
   因此保留该行为。若要保留筛选，需要改这两个文件（超出本阶段允许范围）。
3. **超时后「现在退出」**（P3）：用户可在超时后选择立即退出。此时不杀线程、不关
   worker 连接，只给 5s 兜底等待；扫描耗时通常远小于此（真实样本 35 文件约 184ms）。
4. `-wal` / `-shm` 由 SQLite 在连接全部关闭后自行清理；测试用临时库，未观察到残留。

---

## 15. 结论：能否进入 1.5-C / 1.5-D，或直接结束 Phase 1

**1.5-B 完成，可以进入 1.5-C / 1.5-D，也可以直接结束 Phase 1。**

依据：

- GUI 现在自足：不打开终端即可 Add / Enable / Disable / Remove + Incremental / Full Scan；
- worker 只负责后台执行与传结果，Scanner 仍是唯一扫描逻辑，数据库仍是事实来源，
  Query Layer 仍是 GUI 浏览状态的来源；
- schema / migration / Parser / Scanner / ResourceStore / Query Layer / BrowseService /
  CLI 全部未改；1.4-C 只读边界保持（`ui/*` 仍只经 `BrowseService`）；
- 全套 671 passed / 0 failed。

**建议**：1.5-C（progress / cancel）与 1.5-D（文件监控）都应由**真实证据**驱动 ——
当前真实样本 35 文件扫描仅约 184ms，没有可验证的「需要进度 / 需要取消 / 需要自动刷新」
场景。在没有大库证据前，**建议直接结束 Phase 1**，把精力放到 Phase 2（MOD 索引 + GUID）。
