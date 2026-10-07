# Phase 1.4-C-1 Report — GUI Skeleton

> 版本：Phase 1.4-C-1 · schema v2（**未改动**）· 2026-10-06
>
> 目标：把 GUI 骨架跑起来，并证明
> `BrowseService → ResourceListModel → QListView → Detail selection` 这条链路成立。

---

## 1. 修改文件列表

**新增**

| 文件 | 说明 |
| :-- | :-- |
| `ui/resource_model.py` | `ResourceListModel`（`QAbstractListModel`）+ `display_title()` |
| `ui/library_panel.py` | 左栏 `LibraryPanel` |
| `ui/browser_panel.py` | 中栏 `BrowserPanel`（`QListView` IconMode + model + 状态栏） |
| `ui/detail_panel.py` | 右栏 `DetailPanel`（空/已选中/错误 三种最小状态） |
| `tests/test_gui_smoke.py` | GUI 冒烟测试（19 项，离屏） |
| `docs/phase1/PHASE1_4C1_REPORT.md` | 本报告 |

**修改**

| 文件 | 改动 |
| :-- | :-- |
| `ui/main_window.py` | 由占位改为真实 `MainWindow` + `create_main_window()` + `run_gui()` |
| `ui/__init__.py` | 导出 `MainWindow` / `create_main_window` / `run_gui`，写明分层原则 |
| `main.py` | 新增 `gui` 子命令（不改动任何既有 CLI 行为） |
| `core/__init__.py` | `__version__` → 0.9.0；`__phase__` → `Phase 1.4-C-1 (GUI Skeleton)` |
| `README.md` | 状态行、路线图、文档表同步 |

**未改动**：`schema.py` / migrations、`db.py`、`parsers/*`、`scanner/*`、`models/*`、
`library/store.py`、`thumbnails/*`、`core/query/*`、`cli_query.py`、真实样本。

---

## 2. MainWindow / Panel 架构

```text
MainWindow (QMainWindow)
└── QSplitter(Horizontal)
    ├── LibraryPanel   左：资源库列表（QListWidget）
    ├── BrowserPanel   中：QListView(IconMode) + ResourceListModel + 底部状态
    └── DetailPanel    右：详情骨架（空 / 已选中 / 错误）
```

职责边界（严格遵守）：

- **MainWindow**：创建 service、创建三个 panel、连接信号、处理启动级错误、关闭自有连接。
  不写 SQL、不做筛选、不碰 preview。
- **LibraryPanel**：只调 `BrowseService.libraries()`；发射 `library_selected(int|None)`；
  不持有 `BrowserScope`。
- **BrowserPanel**：只调 `BrowseService.page(scope, limit=100, offset=0)`；
  发射 `resource_selected(int|None)`；不获取 `ResourceDetail`。
- **DetailPanel**：纯展示，无 service；由 MainWindow 传入 `ResourceDetail`。

没有 Controller / Presenter / ViewModel / Store / Event Bus；没有 MVC/MVVM。

---

## 3. ResourceListModel 实现摘要

`ResourceListModel(QAbstractListModel)`：

- 内部持有 `list[ResourceListItem]`；
- 实现 `rowCount()` / `data()` / `roleNames()` / `set_items()` / `clear()` /
  `item_at()` / `item_at_row()` / `resource_id_at()` / `items()`；
- 角色：`DisplayRole` → `display_title()`；`UserRole` → `resource.id`；
  `ToolTipRole` → `file_path`；`DecorationRole` 留空（C-3 才接缩略图）。
- `display_title()` 回退链：`display_name` → `name` → `relative_path` 的文件名 → 完整 `file_path`。

不含业务逻辑：不查询、不筛选、不读文件。

---

## 4. BrowseService 调用路径

```text
MainWindow
  ├─ 启动：  service.libraries()              （经 LibraryPanel.reload）
  ├─ 选库：  service.page(BrowserScope(library_id=...), limit=100, offset=0)
  └─ 选中：  service.detail(resource_id)
```

- GUI **只**调用 `BrowseService`；不调用 `ResourceQuery.list/count`、不调用 `LibraryQuery`。
- 数据库由 `MainWindow` 通过项目既有机制获取：`core.database.db.initialize()` +
  `db.connect()`，再包成 `BrowseService`；**UI 不出现 `sqlite3.connect`**（静态测试断言）。
- 外部注入：`MainWindow(browse_service=...)` 可注入现成 service（测试/未来复用），
  此时不打开任何连接、也不负责关闭。
- 连接归属：`MainWindow` 自己打开连接时，`closeEvent` 会关闭它；注入时不接管。

---

## 5. main.py GUI 入口

```
python main.py gui
```

- `main.py` 只新增一个 argparse 子命令 `gui` 和一个 `cmd_gui()`：

  ```python
  def cmd_gui() -> int:
      from ui.main_window import run_gui
      return run_gui()
  ```

- `ui/main_window.py::run_gui()` 负责：创建/复用 `QApplication` → `create_main_window()`
  → `window.show()` → `app.exec()`。
- **GUI 逻辑没有塞进 main.py**；既有 CLI 命令行为完全不变（有测试断言
  `build_parser().parse_args([])`、`["library","list"]` 仍正常）。

---

## 6. 测试数量和结果

新增 `tests/test_gui_smoke.py`，共 **19** 项（全部离屏 `QT_QPA_PLATFORM=offscreen`）：

| 组 | 覆盖 |
| :-- | :-- |
| QApplication | 可创建 |
| MainWindow | 可构造；三个 panel 存在且都是 `QWidget`；`create_main_window()` 工厂 |
| 空库 | 不崩；LibraryPanel 空状态；BrowserPanel 显示「没有资源库」；DetailPanel 空状态 |
| 空库有资源 | LibraryPanel 显示条目与 `resource_count`；disabled 标记；默认选中第一个 enabled；全 disabled 时回退第一个且**不改状态** |
| 查询失败 | LibraryPanel 就地显示错误文本 |
| model | `display_title` 回退链；`rowCount` / `DisplayRole` / `UserRole` / 状态栏文案；`QListView` 为 IconMode |
| 链路 | 选中行 → `resource_selected` → `BrowseService.detail()` → DetailPanel；切换 Library 重新加载；detail 不存在时兜底 |
| 只读 | 构造/刷新/选择前后 `total_changes`、`app_meta`、`needs_review` 不变 |
| 架构静态约束 | ui/*.py 不 import `sqlite3` / `ResourceQuery` / `LibraryQuery` / `PreviewService` / 线程类 |
| 入口 | `main.py gui` 可解析，既有命令不受影响 |
| schema | 仍 v2 / `[1, 2]` |

```text
519 passed in 25.88s
0 failed / 0 xfailed        （1.4-B.3 基线 500 + 新增 19）
```

---

## 7. 真实样本启动 / 链路验证

### 7.1 入口级（`python main.py gui`）

用**临时数据目录**（`KKS_RM_DATA_DIR` 指向系统临时目录，不触碰项目 `data/`）执行：

```text
python main.py library add <真实样本>     -> Library [1] 已添加
python main.py scan                      -> 发现 35 · 解析 35 · 新增 35 · 失败 0 · 缺失 0
python main.py gui  (QT_QPA_PLATFORM=offscreen)
    -> GUI RUNNING（事件循环存活，未崩溃）
```

### 7.2 离屏链路（真实样本扫描进临时库）

```text
startup_error                None
libraries                    1  ->  "s (35)"
model_rows / total           35 / 35
status                       "共 35 条，已显示 35 条"
select_row(0)                selected = 1   -> detail: "Resource ID: 1"
select_row(20)               selected = 21  -> detail: "Resource ID: 21"
reload                       model_rows 仍为 35
total_changes                2406 -> 2406（不变）
schema                       2 / [1, 2]
真实样本 36 文件              sha256 前后一致；size + mtime_ns 前后一致
```

> 「无 preview 资源不会崩」在本轮天然成立：C-1 **完全不读取图片**、不调用
> `PreviewService`，所有行都只显示文本（zipmod / 无缩略图资源同样正常显示）。

---

## 8. schema / version / phase

- **schema 仍为 v2**：`SCHEMA_VERSION == 2`、`MIGRATIONS == [1, 2]`；无新增 migration。
- `__version__ = "0.9.0"`，`__phase__ = "Phase 1.4-C-1 (GUI Skeleton)"`。

---

## 9. 只读不变量

- GUI 冒烟测试：构造 / reload / 多次选择前后，`conn.total_changes` 不变，
  `app_meta` 不变，`needs_review` 各行不变。
- 真实样本（临时库）：`total_changes` 保持 `2406 → 2406`。
- GUI C-1 不执行任何 INSERT / UPDATE / DELETE，不修改 `needs_review` / `app_meta`，
  不修改任何资源文件。

---

## 10. P0 / P1 / P2

- **P0：无。P1：无。**
- P2（记录，未做）：
  1. 作者是逐行查询（`BrowseService` 的 N+1），C-1 无感；待有实测再优化。
  2. 中栏只加载第一页（`PAGE_SIZE=100`），无「加载更多」——按指令属 C-2。
  3. 刷新后 selection 会重置（不保持原选中项）。
  4. `MainWindow` 没有菜单栏 / 快捷键 / 状态栏（非 C-1 范围）。

---

## 11. 本阶段严格未做

Search / FilterBar / Missing MOD UI / Needs Review UI / Sort UI / Load More /
Thumbnail / PreviewWorker / 完整 Detail（MOD/Plugin/Usage/metadata）/ 收藏 / 删除 /
编辑 / 打开文件 / AI / alias / fuzzy / health score / tagging / persistence / settings /
复杂 MVC-MVVM / Controller / Presenter / ViewModel / 新 core Query API / schema 修改。

线程相关（`QThread` / `QRunnable` / `QThreadPool` / `QtConcurrent`）在本轮**完全未使用**，
并有静态测试守护。

---

## 12. C-1 是否可以验收

**可以验收。** 本轮唯一目标——「GUI 骨架跑起来，并证明
`BrowseService → ResourceListModel → QListView → Detail selection` 链路成立」——
已通过测试与真实样本双重验证：

- `python main.py gui` 可启动并进入事件循环；
- 三栏结构就位，LibraryPanel 显示真实库与资源数；
- `BrowseService.page()` 的 35 条资源进入 model 并显示名称；
- 选择资源后 DetailPanel 收到 id 并显示；
- 空库 / 空资源 / 无 Library / 查询失败 / detail 缺失均有就地状态；
- 全流程只读，样本与数据库均未被修改。

---

### 附：验收对照

| 指令要求 | 结果 |
| :-- | :-- |
| `python main.py gui` 子命令，且不破坏既有 CLI | ✅（有测试） |
| MainWindow 三栏 + QSplitter | ✅ |
| MainWindow 只创建 service / panels / 信号 / 启动错误 | ✅ |
| service 用项目既有 DB 机制创建，UI 不 `sqlite3.connect` | ✅（静态测试） |
| LibraryPanel 用 `BrowseService.libraries()`，显示 name + count + disabled | ✅ |
| 默认选中第一个 enabled；全 disabled 不改状态 | ✅ |
| `library_selected(int\|None)` 信号 | ✅ |
| BrowserPanel 用 `BrowseService.page(scope, limit=100, offset=0)` | ✅ |
| GUI 不调用 `ResourceQuery.list/count` | ✅（静态测试） |
| `ResourceListModel`（rowCount/data/set_items/item_at/DisplayRole/UserRole） | ✅ |
| `QListView` IconMode，可选，`resource_selected` | ✅ |
| 本轮不加载 thumbnail、不调用 `get_or_generate` | ✅（静态测试） |
| DetailPanel 空/选中骨架 | ✅ |
| 空状态（无 Library / 无资源 / 查询失败） | ✅ |
| 不引入 worker / 线程 | ✅（静态测试） |
| GUI smoke tests（离屏） | ✅ 19 项 |
| 真实样本启动 + 链路验证 | ✅ |
| 只读不变量 | ✅ |
| schema v2 / 无 migration | ✅ |
| `__version__` / `__phase__` | ✅ 0.9.0 / `Phase 1.4-C-1 (GUI Skeleton)` |
