# Phase 1.5 Design Review — GUI Setup & Scan

> 版本：设计评审（**不实施**）· schema v2（未改动）· 2026-10-07
>
> 目标问题：**让用户不打开终端，也能在 GUI 中管理 Library、执行 Scan，
> 并在文件变化后刷新资源状态。**
>
> 本轮只做设计分析：未改 schema / migration / Parser / Scanner / ResourceStore /
> Query Layer / GUI / 版本号，未新增 worker 或按钮。

---

## 1. 现状核对（以真实代码为准）

### 1.1 `LibraryStore`（`core/library/store.py`）

```python
LibraryStore(conn)
  .add(root_path, *, name=None, notes="", enabled=True, allow_missing=False) -> Library
  .add_many(root_paths, *, notes="", enabled=True, allow_missing=False) -> list[Library]
  .list_all(include_disabled=True) / .require(id) / .resolve(target) / .find_by_path(path)
  .stats(id) -> LibraryStats(resources, missing, needs_review)
  .update(id, *, name, notes, enabled) / .set_enabled(id, enabled)
  .preview_removal(id) -> LibraryRemovalReport(library, resources_orphaned, scan_records_deleted)
  .remove(id) -> LibraryRemovalReport
```

事实：

- **Add**：`root_path` 默认必须存在且是目录（`allow_missing=True` 才跳过检查）；
  路径经 `_display_path()`（展开 `~`、绝对化）+ `db.normalize_path_key()` 归一化；
  **重复 root_path 会被拒**（`LibraryAlreadyExists`，`root_path_key` UNIQUE）；
  **Library 名称不要求唯一**（`name` 无 UNIQUE 约束）。
- **Enable / Disable**：只改 `libraries.enabled`。
- **Remove**：**只删除 `libraries` 行**——
  `resources.library_id` 因 `ON DELETE SET NULL` 被置空（**资源保留**），
  `scan_records` 级联删除；**完全不接触文件系统**（不删文件、不删资源、不删关系）。

### 1.2 `LibraryScanner`（`core/scanner/scanner.py`）

```python
LibraryScanner(conn).scan(library_id, *, mode="incremental" | "full", root=None) -> ScanResult
```

事实：

- `mode="incremental"`：`(file_path_key, file_size, modified_time)` 未变则**跳过解析**；
  `mode="full"`：忽略增量捷径，全部重新解析。
- **disabled 语义**：`root is None`（即走库自身的 root_path）且 `enabled=0` → 直接返回
  `status="skipped"`、`skip_reason="Library 已暂停（enabled=0），未执行扫描"`；
  传入显式 `root=` 时**不检查 enabled**。
- 写库边界：**每个文件一个事务**（失败隔离）+ `mark_missing()` 自带小事务 +
  `scan_records` 一条运行记录（开始/结束各写一次）。
- 结果对象：`ScanResult(status, skip_reason, stats, issues, scan_record_id, duration_ms)`；
  `ScanStats(discovered, parsed, inserted, updated, skipped, failed, missing, not_a_resource)`。
- **没有 progress 回调、没有 cancel 支持**（`scan()` 是同步阻塞调用）。
- `scan_records.status` 的 CHECK 约束**已经包含 `'cancelled'`**
  （`running / completed / cancelled / failed`）——设计上是为取消预留的。

### 1.3 连接与线程

- `db.connect()` = `sqlite3.connect(path, isolation_level=None)` + `PRAGMA journal_mode=WAL`；
  **未设置 `check_same_thread=False`**，因此**连接绑定创建它的线程**——
  后台 worker **必须自己开一条连接**，不能复用 GUI 线程的连接。
- WAL 模式下**读写可并发**：扫描写入时，GUI 的读连接仍可查询（可能看到扫描中途的快照）。

### 1.4 现有后台任务模式（C-3 / C-5）

- `ui/preview_worker.py`：`PreviewWorker(QRunnable)` + `PreviewSignals(QObject)` +
  `QThreadPool.globalInstance()`；结果经队列连接回 GUI 线程；
- `MainWindow.closeEvent()` 已会 `QThreadPool.globalInstance().waitForDone(5000)`
  （C-5 修复的退出期崩溃）；
- C-3 另有「按源文件路径」的互斥锁（避免同一资源被两处并发生成）。

### 1.5 CLI 现状

```text
python main.py library {add,list,remove,enable,disable} ...
python main.py scan [<id|路径>] [--full]
```

GUI 目前**没有**以上任何写操作入口；`scan` / `library add` 只能走 CLI。

---

## 2. 设计目标（Phase 1.5 只解决这些）

```text
Library GUI 管理   Add / Enable / Disable / Remove
Scan GUI           Incremental Scan / Full Scan / Refresh
长任务              Start / Running / (Progress) / (Cancel) / Success / Failed
状态一致性          扫描完成后全部重新从 Query Layer 读，GUI 不维护第二份状态
```

---

## 3. 架构分析

### A. GUI 与写入层的边界

Phase 1.4-C 是纯只读：`GUI → BrowseService → Query Layer`。
Phase 1.5 首次引入写：`GUI → 写操作 → Store/Scanner → SQLite`。

**推荐边界**：新增一个**极薄的 application 层**（不叫 Manager、不是框架）：

```text
core/app/__init__.py
core/app/admin.py
    class LibraryAdminService:            # 短操作，复用调用方的连接
        add_library(root_path, *, name, notes, enabled, allow_missing) -> Library
        set_enabled(library_id, enabled) -> Library
        preview_removal(library_id) -> LibraryRemovalReport
        remove_library(library_id) -> LibraryRemovalReport

    def run_scan(db_path, library_id, *, mode="incremental") -> ScanResult
        # 内部：database.connect(db_path) → LibraryScanner(conn).scan(...) → conn.close()
```

- `LibraryAdminService` 只**转发** `LibraryStore`，不写 SQL、不新增业务规则；
- `run_scan` 解决「后台线程必须自开连接」这一硬约束（见 §1.3），
  让 `ui/` 侧只需要 import 一个函数，**不接触 Store / Scanner / SQL**；
- 备选（更省一个模块）：GUI 直接 `from core.library import LibraryStore`
  —— 与「UI 只经 Service」的既定边界冲突，**不推荐**；
- **不引入**：EventBus / AppController / 通用 Task Framework / MVVM。

### B. Worker / 线程生命周期

```text
ui/scan_worker.py（新）
    ScanSignals(QObject):  started() / finished(result) / failed(message)
    ScanWorker(QRunnable): run() → admin.run_scan(db_path, library_id, mode=…)
                                     → signals.finished / failed
```

- **复用** C-3 已验证的模式（`QRunnable` + `QObject` 信号载体 + `QThreadPool.globalInstance()`），
  但**不把 `PreviewWorker` 与 `ScanWorker` 抽象成同一个东西**——两者 payload、生命周期、
  错误语义都不同；
- 不使用 QtConcurrent（本环境没有）、不新建长期 `QThread`、不做通用任务框架；
- **进度**：core 无回调 → 本版**只做不确定进度**（「扫描中…」），不做百分比；
- **取消**：core 不支持 → 本版**不提供取消按钮**；窗口关闭策略见 §9-Q10；
- worker 结束时**必须关闭自己开的连接**（`finally`），避免 Windows 上残留 `-wal/-shm`。

---

## 4. Library 操作语义（以现有 core 为准，不发明新规则）

| 操作 | 输入 | 语义（沿用现有实现） | GUI 行为 |
| :-- | :-- | :-- | :-- |
| **Add** | 目录（+可选 name / notes / enabled） | 目录须存在（否则报错，可给 `allow_missing` 逃生口）；重复 root_path 拒绝；重名允许 | 文件选择对话框选目录 → 调 `add_library` → 刷新左栏 → **自动选中新库**；**不自动扫描**（与 CLI 一致），但提供「立即扫描」按钮 |
| **Enable / Disable** | library_id | 只改 `enabled` | 左栏右键/按钮切换；**disabled 仍可浏览**（浏览不看 enabled），只是 `scan` 会跳过 |
| **Remove** | library_id | **只删库记录**：资源保留（`library_id` → NULL）、`scan_records` 级联删除、**不碰文件** | 必须**二次确认**，确认框逐字写明影响（见下）；扫描进行中的库**禁止删除**；删除后刷新左栏并清空中/右栏 |

Remove 确认文案（必须写清楚）：

```text
将移除资源库「<name>」
  · 只删除数据库中的库记录
  · 已入库的资源会保留（但不再属于任何库）
  · 不会删除或移动你的任何文件
  · 该库的扫描历史记录将被删除
```

---

## 5. Scan 语义（复用现有 Scanner，不写第二套扫描逻辑）

| GUI 动作 | 调用 | 说明 |
| :-- | :-- | :-- |
| **增量扫描** | `run_scan(db_path, library_id, mode="incremental")` | 与 `python main.py scan` 完全等价 |
| **全量扫描** | `run_scan(db_path, library_id, mode="full")` | 与 `python main.py scan --full` 完全等价 |
| **刷新** | 不加 `--full` 的增量扫描（或仅重读 Query） | 「刷新」= 增量扫描 + 重读 |

- GUI **只是 Scanner 的另一个入口**；不新增扫描规则、不改 Parser；
- 扫描期间的写入行为沿用 core：**每文件一事务**，中途失败不影响已完成文件，
  数据库保持一致（不会出现「一半写入」）；
- `mode` 用「扫描」按钮 + 「全量重扫」次级项（或按住 Shift 等修饰）区分，
  不新造语义；
- **是否需要给 Scanner 加 progress/cancel：本阶段不需要**（见 §9-Q3）。

---

## 6. Non-goals（明确保持）

EventBus、全局 AppController、Manager 层大抽象、MVC/MVVM 重构、通用 Task Framework、
persistent UI state、AI、semantic search、automatic classification / tagging、
fuzzy / alias 归一化、云端功能、文件监控（filesystem watcher）、
批量文件操作（移动/删除/重命名）、标签 / Collection。

---

## 7. 真实样本验证计划（implementation 阶段执行；本文件不执行）

当前真实样本：1 Library / 35 Resources（22 卡 + 13 zipmod）/ 14 个含缺失 MOD /
134 个缺失 MOD guid / 13 个已安装 MOD / 3 个孤立 MOD。

验证链（**全部在临时数据目录 + 临时数据库 + 临时真实样本副本上做**）：

```text
GUI Add（指向真实样本目录）
   → 左栏出现该 Library（resource_count = 0）
   → 点击扫描
   → resource_count == 35；Browse 35 条；Detail 正确
   → 再次增量扫描 → 无重复资源（仍是 35，且无新增行）
   → 在**临时副本**上改一个文件 → 再扫描 → updated/missing 状态正确
```

同时必须保持：

- **不修改真实样本目录**（sha256 + size + mtime_ns 前后一致）；
- 不依赖手工 GUI 操作：核心正确性必须能用 `QT_QPA_PLATFORM=offscreen` 的 pytest 驱动；
- 数据库只读不变量在**仅浏览**时继续成立；写操作只在**显式触发**时发生；
- 测试结束清理临时库 / 临时缓存（不污染 `data/`）。

---

## 8. 结论与子阶段顺序

```text
A. 可以直接进入 1.5-A
```

理由：**core 无需预先修改**——`LibraryStore`（Add/Enable/Disable/Remove）与
`LibraryScanner`（incremental / full）都已存在并经 CLI + 测试验证；
缺的只是 GUI 入口、后台执行与刷新。schema 不需要变更。

推荐的子阶段顺序：

| 子阶段 | 内容 | 依赖 |
| :-- | :-- | :-- |
| **1.5-A** | `core/app/admin.py`（薄写操作服务）+ **Library GUI 管理**：Add / Enable / Disable / Remove（含确认与影响预览）+ 左栏刷新 | 无（纯短操作，不需要线程） |
| **1.5-B** | `ui/scan_worker.py` + Scan GUI：增量 / 全量 + 扫描中状态 + 完成后刷新 Browse/Detail/库计数 | 1.5-A |
| **1.5-C**（可选，按需） | Scanner 增加 **progress / cancel** 回调（`scan_records.status` 已支持 `'cancelled'`）→ GUI 进度条 + 取消按钮 | 1.5-B + **core 小扩展** |
| **1.5-D**（可选，按需） | 文件变化检测 / 自动刷新提示（不做文件监控） | 1.5-B |

原则：**1.5-A 与 1.5-B 是必须的；1.5-C / 1.5-D 只有在真实证据（大库、扫描耗时）出现时才做。**

---

## 9. 重点问答

**Q1. Library GUI 管理和 Scan 谁先做？**
**Library 管理先（1.5-A）。** 三个操作都是毫秒级短事务、不需要线程、不改变只读边界
之外的东西；Scan 需要后台线程与刷新协调（1.5-B），复杂度更高，放在其后可以把
「写操作的边界」先立住。

**Q2. 是否需要新的 Application Service？**
**需要一个极薄的**（`core/app/admin.py`，见 §3-A）：短操作用 `LibraryAdminService`
转发 `LibraryStore`；后台扫描用 `run_scan(db_path, …)`（内部自开/自关连接）。
**不要** Manager 层、EventBus、通用 Task Framework。

**Q3. Scanner 是否需要增加 progress/cancel API？**
**本阶段不需要。** 依据：真实样本 35 个文件扫描耗时 **184 ms**（实测），
没有真实大库能证明需要进度百分比；给 Scanner 加钩子是 core 改动，应由证据驱动。
本版只做**不确定进度**（「扫描中…」）+ **无取消按钮**。
若将来出现大库，最小扩展是给 `scan()` 加可选 `progress` / `should_cancel` 回调
（`scan_records.status` 已预留 `'cancelled'`），属 1.5-C。

**Q4. ScanWorker 应该如何设计？**
`ScanWorker(QRunnable)` + `ScanSignals(QObject)`（`started / finished(result) / failed(msg)`），
`run()` 里只调用 `admin.run_scan(db_path, library_id, mode)`；**自开自关连接**（线程约束）；
异常一律转成 `failed`；**worker 不接触任何 QWidget / model**。

**Q5. GUI 是否允许 scan 时继续浏览？**
**允许。** WAL 下读写可并发，扫描期间浏览会看到「部分的」结果，可接受；
顶部显示「正在扫描…」提示，扫描完成后自动刷新。

**Q6. GUI 是否允许 scan 时切换 library？**
**允许切换浏览**（只读操作）；但
① 禁止对**同一** library 重复启动扫描；
② 禁止删除**正在扫描**的 library；
③ 扫描期间再次点扫描 → 按钮禁用（而不是排队）。

**Q7. Remove 的真实语义是什么？**
**只删除 `libraries` 行**：资源保留（`resources.library_id` → NULL），
`scan_records` 级联删除，**不删除文件、不删除已入库资源与关系**。
GUI 必须原样呈现（确认框逐字说明），**不得**自定义成「删除资源」或「删除文件」。

**Q8. Add 后是否自动 Scan？**
**不自动**（与 CLI 行为一致）；Add 成功后**自动选中新 Library**，
并在界面提供「立即扫描」按钮由用户显式触发。

**Q9. Scan 完成后如何刷新 Browse / Detail / Library count？**
**全部重新从 Query Layer 读，不维护第二份状态**：

```text
ScanWorker.finished
  → LibraryPanel.reload()                 # 库名 / resource_count / disabled
  → BrowserPanel.reload_relation_options()  # 缺失 MOD / 作者 / 插件下拉
  → BrowserPanel.reload()                 # 资源列表 + total + 空态
  → DetailPanel                            # 由 reload 的 selection 清空自动回到空状态
```

**Q10. 窗口关闭时正在运行的 scan 如何处理？**
策略（推荐）：关窗时若扫描进行中 → 弹**确认框**「扫描仍在进行，是否等待完成后退出？」
→ 确认则等待（有超时，超时后再问一次）；取消则继续运行。
**不采用的方案**：静默杀掉线程（SQLite 连接与 scan_records 状态会不干净）、
或禁止关闭窗口（对用户过于强硬）。
注意：core 的「每文件一事务」保证即使等待超时退出，数据库也不会处于半写状态。

**Q11. 哪些部分必须改 core，哪些只改 GUI？**

| 部分 | 结论 |
| :-- | :-- |
| schema / migration | **不改** |
| Parser / ResourceStore / Query Layer / BrowseService / PreviewService | **不改** |
| `LibraryStore` / `LibraryScanner` | **不改**（现有 API 已满足） |
| **新增** `core/app/admin.py`（薄服务 + `run_scan`） | **新文件**，不修改既有 core 语义 |
| GUI：`ui/scan_worker.py`（新）、`ui/library_admin_dialog.py`（新，Add/Remove 对话框）、`ui/library_panel.py`（+入口）、`ui/main_window.py`（协调 + 工具栏） | **只改 GUI** |
| CLI（`main.py` / `cli_query.py`） | **不改**（GUI 复用同一 core 能力） |

**Q12. 最小实现范围是什么？**
**1.5-A + 1.5-B**：

```text
1.5-A  Library GUI 管理（Add / Enable / Disable / Remove + 确认 + 左栏刷新）
1.5-B  Scan GUI（增量 / 全量 + 后台线程 + 扫描中状态 + 完成后统一刷新）
```

不含：进度百分比、取消按钮、文件监控、自动扫描、批量文件操作、标签/Collection。

---

## 10. 风险与 P0/P1/P2（预判）

- **P0**：无（core 能力齐备）。
- **P1（实现时需要重点保证）**：
  1. **线程与连接**：worker 必须自开自关连接（`check_same_thread` 默认 True）；
  2. **关窗竞态**：扫描中关窗必须走确认 + 等待，避免 C-5 那类退出期崩溃；
  3. **Remove 语义误读**：确认框必须写明「不删文件、不删资源」。
- **P2（记录）**：进度百分比 / 取消（1.5-C）；跨库全局关系视图；
  `scan_status` GUI 筛选；orphan MOD GUI 列表；文件监控。

---

## 11. 最终结论

```text
A. 可以直接进入 1.5-A
```

理由：`LibraryStore`（Add/Enable/Disable/Remove）与 `LibraryScanner`（incremental/full）
已经存在且经 CLI 与测试验证；`db.connect()` 的线程约束与 C-5 已建立的
`closeEvent`/线程池等待机制足以支撑后台扫描；**无需修改 schema 或既有 core**，
只需新增一个极薄的 application 文件与 GUI 侧入口。

Phase 1.5 应严格拆为 **1.5-A（Library 管理）→ 1.5-B（Scan）→ 1.5-C/D（可选）**，
并保持 1.4-C 已确立的只读边界不被破坏（浏览路径仍然只经 `BrowseService`）。
