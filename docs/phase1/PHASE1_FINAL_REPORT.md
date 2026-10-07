# Phase 1 Final Closure Report — CLOSED / PASS

> 版本：`0.15.0` · `Phase 1.5-B (Scan GUI)` · schema `v2`（未改动）· 2026-10-07
>
> 本文件是 **Phase 1 的最终审计与收尾报告**。审计过程**只读**，未修改任何功能代码
> （唯一新增文件就是本报告）。

## 结论

```text
PHASE 1 = CLOSED / PASS
```

无 P0 / P1 问题。pytest `671 passed / 0 failed / 0 xfailed`。

---

## 0. 审计范围与方法

审计手段（全部只读）：

1. 逐阶段阅读 Phase 1 各报告；
2. 静态核对关键源文件（schema / migration / Parser / Scanner / ResourceStore /
   Query Layer / BrowseService / CLI / GUI）；
3. 代码搜索禁项（progress / cancel / watcher / EventBus / Manager / Task Framework …）；
4. 文件修改时间核对（确认 core 未被 1.5 阶段误改）；
5. 运行完整 `pytest`；
6. 运行 `node tools/validate_schema.mjs` 与 `node tools/check_model_sync.mjs`。

### 检查清单与结果

| # | 检查项 | 结果 | 证据 |
| :-- | :-- | :-- | :-- |
| 1 | schema v2 稳定 | ✅ | `SCHEMA_VERSION == 2`，16 张业务表，`validate_schema.mjs` 全 OK |
| 2 | migration 未被意外修改 | ✅ | `MIGRATIONS == {1,2}`；`test_migration_v2.py` 27 passed |
| 3 | Parser / Scanner 核心语义保持 | ✅ | `core/parsers/*`、`core/scanner/*` mtime 仍为 2026-10-06 |
| 4 | ResourceStore 保持 | ✅ | `core/scanner/store.py` 未修改 |
| 5 | Query Layer 保持 | ✅ | `_execute_select` 只放行 SELECT/WITH |
| 6 | BrowseService 保持 | ✅ | `core/query/browse.py` 本阶段未修改 |
| 7 | CLI 保持 | ✅ | `main.py` / `cli_query.py` 未改；library/scan/query/gui 齐全 |
| 8 | GUI 仍遵守 BrowseService 边界 | ✅ | `ui/*` 无 sqlite3 / Query 类导入 |
| 9 | GUI 未维护第二份资源状态 | ✅ | 读经 BrowseService；写/扫描后 reload 重查 |
| 10 | SQLite 连接无跨线程使用 | ✅ | 全库无 `check_same_thread=False` |
| 11 | ScanWorker 正确关闭 connection | ✅ | `run_scan()` finally close；测试证明 |
| 12 | worker 生命周期 / closeEvent 无明显风险 | ✅ | 确认 + 超时再询问；不杀线程 |
| 13 | Library Remove 严格不删文件 / resources | ✅ | 只 DELETE libraries；资源 library_id→NULL |
| 14 | disabled Library 仍可浏览 | ✅ | `set_library` 不读 enabled |
| 15 | Incremental / Full 完全由 LibraryScanner 决定 | ✅ | GUI 无 os.walk / 解析 / upsert |
| 16 | 1.5-C progress/cancel 未实现 | ✅ | 搜索无 progress / should_cancel / cancel( |
| 17 | 1.5-D watcher / 自动刷新未实现 | ✅ | 搜索无 QFileSystemWatcher / watchdog |

---

## 1. Phase 1 总目标

把项目从「架构骨架」推进到「可自足的本地只读浏览器 + 可写资源库管理 + 可后台扫描」：

```text
不打开终端，用户就能：
  Add / Enable / Disable / Remove Library
  Incremental Scan / Full Scan（后台执行）
  Search / Filter / Sort / Browse / Detail / Relation 反查
```

三条贯穿全程的硬性约束：

| 约束 | 落地 |
| :-- | :-- |
| **本地优先** | 运行时零网络、零云 AI；全部数据本地 SQLite |
| **默认只读** | 扫描 / 解析 / 浏览绝不移动、删除、修改用户文件 |
| **位置与分类分离** | 库管理只动数据库记录，不碰文件系统 |

---

## 2. 1.1 → 1.5-B 阶段总结

| 子阶段 | 交付 | 报告 |
| :-- | :-- | :-- |
| **1.1** | `LibraryStore`（libraries CRUD）+ CLI `library`；删除只解绑资源、不删文件 | `PHASE1_REPORT.md` |
| **1.2-A** | Schema v2：`card_marker` + `resource_plugins`/`resource_mod_usages`/`resource_authors` | `PHASE1_2_REPORT.md` |
| **1.2-B** | 只读 Parser：PNG 尾部 MessagePack 角色卡 + zipmod manifest | 同上 |
| **1.2-C/D** | Scanner：递归遍历 + 增量判定 `(path,size,mtime)` + v2 入库 + 作者 | 同上 |
| **1.3-A/B** | 只读 Query Layer + property 分类 + CLI `query` | `PHASE1_3_REPORT.md` |
| **1.4-A/A.1** | Search Core（FTS5 trigram + LIKE 回退；含 `relative_path`） | `PHASE1_4A*.md` |
| **1.4-B.1/2/3** | Library 只读查询 / `has_missing_mods` / Browse Read Model | `PHASE1_4B*.md` |
| **1.4-C-1～C-5** | GUI：三栏骨架 / 搜索筛选排序 / 异步缩略图 / 详情 / 关系反查闭环 | `PHASE1_4C*.md` |
| **1.4-C-6** | 收尾评估：结论「不继续 C-6」 | `PHASE1_4C_CLOSURE_REPORT.md` |
| **1.5-A** | `core/app/admin.py` 薄服务 + Library GUI 管理 | `PHASE1_5A_REPORT.md` |
| **1.5-B** | `ui/scan_worker.py` + Scan GUI（后台执行、统一刷新、Remove 竞态防护） | `PHASE1_5B_REPORT.md` |

---

## 3. 当前架构图

```text
[ GUI  ui/ ]
  MainWindow
    ├── LibraryPanel   左：库列表 + 添加/启停/移除 + 扫描（增量/全量）
    ├── BrowserPanel   中：FilterBar + 资源网格 + 加载更多
    └── DetailPanel    右：资源详情 + 「按此 MOD 筛选」
  任务运行状态（唯一非 DB 状态）：MainWindow._scanning {library_id: ScanWorker}
  QThreadPool.globalInstance() ← PreviewWorker / ScanWorker(QRunnable)
        │
        ├── 读（只读） ─────────────► core/query/ BrowseService
        │                              (Resource/Mod/Author/Plugin/Usage Query, 只读护栏)
        │
        └── 写 / 扫描 ──────────────► core/app/
                                        LibraryAdminService → core/library/ LibraryStore
                                        run_scan(db_path,…)（自开自关连接）
                                          → core/scanner/ LibraryScanner（唯一扫描逻辑）
                                              ├─ core/parsers/（PNG 卡 / zipmod，纯只读）
                                              └─ core/scanner/ ResourceStore（入库）
        │
        ▼
  SQLite  schema v2 / WAL / check_same_thread=True（连接绑定线程）
    libraries, resources, authors, mods, resource_mods, resource_mod_usages,
    resource_plugins, resource_authors, scan_records, tags, collections, …, resources_fts

依赖方向严格单向：ui/ → core/，core/ 永不反向依赖 UI。
GUI 不 import sqlite3、不直接调用 Query 类、不写 SQL。
```

---

## 4. schema 状态

| 项 | 值 |
| :-- | :-- |
| `SCHEMA_VERSION` | `2` |
| `MIGRATIONS` | `{1: (_V1_SQL, _V1_FTS_SQL), 2: (_V2_SQL, "")}` |
| `MIGRATION_ADDED_COLUMNS` | `{2: (("resources", "card_marker", "TEXT"),)}` |
| 业务表 | 16（V1 13 张 + V2 3 张：resource_plugins / resource_mod_usages / resource_authors） |
| FTS | `resources_fts`（FTS5 trigram）+ 触发器，不可用时自动回退 LIKE |

1.5 阶段完全没有触碰 schema / migration（`core/database/*` 修改时间仍为 2026-10-06）。
`validate_schema.mjs`：DDL 幂等 OK、16 张表、FTS/trigram 启用、外键与级联 OK。

---

## 5. core 状态

| 模块 | 状态 | 说明 |
| :-- | :-- | :-- |
| `core/library/store.py` | 未改 | `remove()` 只 `DELETE FROM libraries` |
| `core/parsers/*` | 未改 | 卡片 / zipmod 只读解析 |
| `core/scanner/scanner.py` | 未改 | `scan(mode=…)`；disabled → `status="skipped"` |
| `core/scanner/store.py` | 未改 | `ResourceStore` 入库 / `mark_missing` |
| `core/query/*` | 未改 | 只读护栏（SELECT/WITH）+ Browse Read Model |
| `core/database/*` | 未改 | `connect` 保持 `check_same_thread=True` |
| `core/app/admin.py` | 1.5 新增/扩展 | `LibraryAdminService` + `run_scan`（自开自关连接） |
| `cli_query.py` / `main.py` | 未改 | `library` / `scan` / `query` / `gui` |

---

## 6. GUI 状态

三栏主窗口，`python main.py gui` 启动。

| 区域 | 能力 |
| :-- | :-- |
| 左栏 LibraryPanel | 库列表（名称 + 资源数 + `[disabled]` + `[扫描中…]`）；添加 / 启用暂停 / 移除；扫描（增量）/ 全量重扫 |
| 中栏 BrowserPanel | 搜索（debounce）/ 类型 / 只看缺 MOD / 待确认 / 排序 / 作者 / 插件 / 缺失 MOD；缩略图网格；有界加载更多 |
| 右栏 DetailPanel | 预览 / 标识 / 基本信息 / 作者 / MOD 依赖 / Usage / 插件 / 元数据 / 解析-扫描-待确认；「按此 MOD 筛选」闭环 |

边界与状态：

- **读**只经 `BrowseService`；**写**只经 `core.app.LibraryAdminService`；**扫描**只经
  `core.app.run_scan`（由 `ScanWorker` 在后台调用）；
- `ui/*` 不 import `sqlite3`、不 import `ResourceQuery` / `LibraryQuery`（静态测试守护）；
- GUI **不维护第二份 Library / resource 状态**：任何写 / 扫描成功后一律重新查询；
- 唯一额外状态是**任务运行状态** `MainWindow._scanning` 与面板镜像 `_scanning_ids`，
  只表示「当前 GUI 生命周期内哪些扫描在跑」，用于按钮禁用、重复启动防护、Remove 竞态
  防护与关窗等待；`ScanResult` 不缓存，只用于判断成功与显示一句提示。
- 连接绑定创建线程（`check_same_thread=True`）；后台 worker 一律自开自关连接；
  关窗时若有扫描：确认「是否等待完成后退出」→ 取消则继续扫描；等待 15s 超时后再询问；
  不主动杀线程、不从 GUI 线程关闭 worker 连接。

---

## 7. 测试总数与结果

```text
27 个测试文件 · 671 个用例 · 671 passed / 0 failed / 0 xfailed
```

| 文件 | 用例 | 覆盖 |
| :-- | --: | :-- |
| test_database_schema.py | 9 | Phase 0 schema 回归 |
| test_migration_v2.py | 27 | v1→v2 迁移 / 幂等 / 新表新列 |
| test_database_transactions.py | 7 | 事务语义 + 性能冒烟 |
| test_fts_backfill.py | 5 | FTS 回填门控 |
| test_library_store.py | 21 | LibraryStore CRUD + 不删文件护栏 |
| test_library_cli.py | 11 | CLI library 端到端 |
| test_library_query.py | 14 | Library 只读查询 |
| test_parser_card.py | 53 | 角色卡解析（真实样本参数化） |
| test_parser_zipmod.py | 18 | zipmod 解析 |
| test_parser_errors.py | 20 | 损坏样本容错 |
| test_scanner.py | 36 | 扫描 / 增量 / 入库 |
| test_scanner_samples.py | 27 | 真实样本扫描验收 |
| test_property_map.py | 16 | property → 语义类别 |
| test_query_layer.py | 28 | 查询层 |
| test_query_cli.py | 18 | CLI query |
| test_review_reasons.py | 13 | review reason |
| test_search_core.py | 83 | FTS + LIKE 检索 |
| test_missing_mods.py | 23 | 缺失 / 孤立 MOD |
| test_browse.py | 50 | Browse Read Model |
| test_thumbnails.py | 21 | 缩略图缓存 |
| test_gui_smoke.py | 19 | GUI 骨架 + 只读不变量 + 静态边界 |
| test_gui_filters.py | 28 | 搜索 / 筛选 / 排序 / 加载更多 |
| test_gui_preview.py | 22 | 异步缩略图 |
| test_gui_detail.py | 33 | 详情面板 |
| test_relation_browse.py | 28 | 关系反查闭环 |
| test_gui_library_admin.py | 18 | 1.5-A Library GUI 管理 |
| test_gui_scan.py | 23 | 1.5-B 后台扫描 |

补充验证通道：`node tools/validate_schema.mjs`（DDL 幂等 / 约束 / FTS）与
`node tools/check_model_sync.mjs`（schema ↔ models 类型清单一致）均通过。

---

## 8. 已知 P2 / P3 遗留（不阻塞 CLOSED）

**P2**

1. 跨库全局关系视图：作者 / 插件 / MOD 关系筛选目前只在所选 Library 内生效
   （样本只有 1 个库，无法用真实数据验证价值）。
2. `scan_status` 的 GUI 筛选项：CLI 有 `query resources --status`，GUI 无对应控件
   （真实样本 `missing = 0`，无法验证）。
3. orphan MOD 的 GUI 列表：`BrowseService.orphan_mods()` 已存在且已测试，但 GUI 未接线
   （属「一行接线 + 一个小视图」，不是新能力）。
4. 缺失 MOD 没有名称：本地没有 manifest，数据不存在，无法补。
5. 扫描完成后 `reload_relation_options()` 会重建关系下拉，从而把用户当前的关系筛选
   重置为「全部」（既有 `set_relation_options` 行为；保留筛选需改 `browser_panel.py` /
   `filter_bar.py`）。
6. 作者逐行查询（N+1）与 LIKE 全表扫描：无规模证据，暂不优化。
7. 详情面板与网格各有一份 status → UI 状态映射（未抽象，避免引入 PreviewManager）。
8. `metadata_json.plugin_count` 冗余（权威值 = `COUNT(resource_plugins)`）；死字段
   `resources.author/author_id`、`mods.description/game/md5`；`resource_mods.relation` 恒为 uses。
9. `_replace_usages` 静默合并重复 `(mod_guid, property)`（真实样本 0 触发）。

**P3**

1. 单扫描策略（有意为之）：同一时刻只允许一个扫描 worker，避免并发写争用 SQLite 写锁；
   若要并发扫描不同 Library，需先给连接设置合理的 `busy_timeout`（属 core 改动，
   需真实需求驱动）。
2. 关窗超时后用户可选择「现在退出」：不杀线程、不关 worker 连接，仅给 5s 兜底等待
   （真实样本 35 文件约 184ms，远小于超时）。
3. `db.connect()` 未设置 `busy_timeout`；单扫描策略使其在当前范围内不构成问题。
4. 项目未 `git init`；无版本回退保护。

---

## 9. 明确没有实现的内容（1.5-C / 1.5-D 及其它）

Phase 1 **没有**实现下列内容：

| 类别 | 未实现项 |
| :-- | :-- |
| **1.5-C** | progress callback、百分比、progress bar、cancel 按钮、should_cancel、cancel()；未改动 `LibraryScanner.scan()` 的 API |
| **1.5-D** | filesystem watcher（`QFileSystemWatcher` / watchdog）、文件变化自动检测、自动刷新提示、自动扫描 |
| 架构 | EventBus、AppController、Manager 层、通用 Task Framework、通用 Worker 基类、MVVM / MVC 重构 |
| 后续 Phase | Tag、Collection、MOD Index、GUID Index、重复检测、批量文件操作、语义搜索、AI |

搜索证据：`core/`、`ui/`、`main.py`、`cli_query.py` 内没有上述禁项的实现代码，
只有「刻意不引入」的说明性文字。

---

## 10. Phase 1 是否 CLOSED

```text
PHASE 1 = CLOSED / PASS
```

依据（全部满足）：

1. 1.1 到 1.5-B 六个子阶段全部完成，各有报告；
2. schema 仍为 v2，migration 未被改动，16 张业务表结构稳定；
3. Parser / Scanner / ResourceStore / Query Layer / BrowseService / CLI 语义零改动；
4. GUI 只经 BrowseService 读、只经 LibraryAdminService 写、只经 run_scan 扫描，
   不 import sqlite3、不直接调用 Query 类；
5. 无跨线程复用 SQLite 连接；worker 自开自关连接；
6. Library Remove 仍严格「不删文件、不删 resources」；disabled Library 仍可浏览；
7. Incremental / Full 完全由 LibraryScanner 决定；
8. 1.5-C / 1.5-D 明确未实现；
9. 无 P0 / P1；
10. 全套 pytest 671 passed / 0 failed / 0 xfailed。

---

## 11. 进入 Phase 2 前建议保留的技术基线

以下基线作为 Phase 2 的起点，**不要**在 Phase 2 顺手改动：

1. **schema v2 冻结**：`SCHEMA_VERSION = 2`、`MIGRATIONS = {1,2}`、
   `MIGRATION_ADDED_COLUMNS = {2: card_marker}`；Phase 2 若需变更，必须追加 v3，
   不得改动 `_V1_SQL` / `_V2_SQL`，加列走 `MIGRATION_ADDED_COLUMNS`。
2. **分层单向依赖**：ui → core；GUI 不直接连库、不写 SQL；查询只经 Query Layer /
   BrowseService；写操作经 `core/app`。
3. **只读护栏**：`core/query/queries.py::_execute_select` 只放行 SELECT / WITH；
   Scanner / Parser 全程只读，不移动 / 删除 / 修改用户文件。
4. **线程模型**：`db.connect()` 保持 `check_same_thread=True`；后台 worker 一律自开自关
   连接；后台任务使用 QThreadPool 与 QRunnable，配 QObject 信号载体，结果回 GUI 线程处理。
5. **唯一事实来源**：SQLite 是数据事实来源，Query Layer 是 GUI 浏览状态的来源；
   GUI 不维护第二份 Library / resource 状态（只允许任务运行状态）。
6. **写操作确认**：删除 Library 必须二次确认，且文案明确「只删库记录、资源保留、不动文件」；
   未来任何文件操作都必须 Preview / Confirm / Undo-Backup（Phase 5）。
7. **验证基线**：pytest 671 passed；`tools/validate_schema.mjs`、`tools/check_model_sync.mjs`
   作为无 Python 环境的备用验收通道；真实样本目录 sha256 前后一致作为只读证据。
8. **命名与数据纪律**：卡片 dataID 不是身份（只进 metadata）；MOD guid 是 MOD 唯一身份；
   作者按 `name_key` 归一化，哨兵 `[Unknown]` 不建作者行。

---

## 12. 不提前设计 Phase 2

本报告**不**给出 Phase 2（MOD 索引、GUID、依赖关系）的任何具体设计、表结构、API 或
实施计划。Phase 2 的范围、schema 变更（如需 v3）与实现方案，应在 Phase 2 正式立项时
单独评审，并以「有真实、重要、样本可验证的问题」为启动判据。

本次审计到此结束，**不再继续修改项目**。
