# Phase 1.4-C-3 Report — Async Preview / Thumbnail

> 版本：Phase 1.4-C-3 · schema v2（**未改动**）· 2026-10-07
>
> 目标：把 `PreviewService` 的耗时工作移出 GUI 线程，安全地把结果回传到
> `QListView` 的单个资源项；切换搜索/筛选/Library 时旧任务**绝不串图**。

---

## 1. PreviewService 实际 API（已核对，未修改其核心语义）

```python
PreviewService(cache_dir=None, *, max_size=(256, 256), webp_quality=90)

status(source)          -> PreviewStatus   # 轻量：stat + 校验已有缓存（不生成）
get_or_generate(source) -> PreviewStatus   # 生成/命中：解码 + 缩放 + WebP 编码 + 写缓存

PreviewStatus(state, cache_key, path, reason)
  state ∈ {"unsupported", "missing", "ready", "failed"}；有 .is_ready / .is_supported
```

`source` 接受任何带 `file_path`（可选 `extension` / `resource_type`）的对象
→ `ResourceSummary` 可直接传入。

**本阶段未修改 `core/thumbnails/service.py` 的任何一行。**

---

## 2. PreviewWorker 架构

```text
ui/preview_worker.py
├── PreviewSignals(QObject)         # 信号载体（在 GUI 线程创建）
│     finished = pyqtSignal(resource_id, epoch, PreviewStatus)
│     failed   = pyqtSignal(resource_id, epoch, error_text)
└── PreviewWorker(QRunnable)
      run(): PreviewService.get_or_generate(source) → signals.finished.emit(...)
             异常 → signals.failed.emit(...)（不抛出、不杀线程）
```

- worker **只做**「调用 `get_or_generate` + 转成信号」；
- worker **不**碰 `QWidget` / `QAbstractListModel` / `QPixmap` / `QListView`
  （测试断言其 import 里没有 `QtGui` / `QtWidgets`，也没有 `dataChanged`）；
- `setAutoDelete(True)`，由 `QThreadPool` 管理生命周期；BrowserPanel 额外持有引用
  直到回调到达，避免 Python 侧提前回收。

---

## 3. QThreadPool / QRunnable 使用方式

项目当前 PyQt6 **没有 QtConcurrent**（已实测 `importlib.util.find_spec("PyQt6.QtConcurrent")` 为 `False`），
因此采用 Qt 原生线程池：

```python
self._pool = QThreadPool.globalInstance()
worker = PreviewWorker(preview_service, resource, epoch=..., resource_id=...)
self._pool.start(worker)
```

- 不使用 QtConcurrent、不自建长期 QThread、不为每张图开线程、不用 multiprocessing / asyncio；
- 每页最多 `PAGE_SIZE`(100) 个短任务，由线程池自动限流。

---

## 4. 结果如何回到 GUI 线程

`PreviewSignals` 在 **GUI 线程**创建 → 其线程亲和性为 GUI 线程；worker 在**线程池线程**
中 `emit` → Qt 的 AutoConnection 判定为跨线程 → **队列连接** → 槽函数在 GUI 线程执行。

GUI 线程收到结果后才做：

```python
pixmap = self._load_pixmap(status.path)      # 只在 GUI 线程创建 QPixmap
self.model.set_preview_state(rid, PREVIEW_READY, pixmap)   # → 单行 dataChanged
```

**worker 线程绝不创建 `QPixmap`**（`PreviewService` 返回的是缓存文件路径，不是像素）。
测试 `test_generation_happens_off_gui_thread` 运行时抓取 `QThread.currentThread()`，
断言 `get_or_generate` 从不在 `QApplication.thread()` 上执行；
`test_pixmap_loaded_on_gui_thread` 断言 `_load_pixmap` 只在 GUI 线程执行。

---

## 5. epoch 防串图

`BrowserPanel._preview_epoch`：

- 每次 **`reload()`**（搜索 / 类型 / 缺 MOD / 待确认 / 排序 / 切换 Library / 首次加载）
  `+= 1`；
- `load_more()` **不**递增（旧 items 仍在列表中，其 READY 预览继续有效）；
- 提交任务时记录 `epoch`；回调里：

  ```python
  if epoch != self._preview_epoch:
      return          # 过期结果直接丢弃，绝不写入当前列表
  ```

因此 `搜索 A → 启动 preview A → 切到搜索 B（epoch++）→ A 完成 → 丢弃`。

测试：`test_reload_increments_epoch`、`test_stale_epoch_result_is_discarded`、
`test_stale_failed_result_is_discarded`、`test_stale_result_does_not_leak_into_new_filter_result`。

---

## 6. 重复任务防护

- 键：`(resource_id, epoch)`，存于 `self._pending_previews`；
- 提交前双重检查：
  1. `model.preview_state(rid)` 必须是 `UNREQUESTED`（`LOADING/READY/UNSUPPORTED/MISSING/FAILED`
     一律直接返回，不重复提交）；
  2. `(rid, epoch)` 不在 pending 中；
- 回调（成功或失败）都会 `pop` 该键 → 字典自清理、也充当 worker 的引用保活；
- epoch 变化后同资源可以（也应当）重新提交；
- **不做**硬取消（旧任务自然结束、结果被丢弃），符合「不要复杂 cancellation system」。

---

## 7. ResourceListModel 的 preview state

模型**未重构**，只新增 UI 临时状态（不进 core / schema）：

```text
PREVIEW_UNREQUESTED / PREVIEW_LOADING / PREVIEW_READY /
PREVIEW_UNSUPPORTED / PREVIEW_MISSING / PREVIEW_FAILED

模型内部：
    _preview_state:  dict[resource_id, state]
    _preview_pixmap: dict[resource_id, QPixmap]
```

新增方法：`preview_state()` / `preview_pixmap()` / `row_for_resource()` /
`decoration_for()` / `set_preview_state()`。

模型职责仍然是「保存列表数据 + 保存 UI 状态 + 提供 roles」：
**不调用 `PreviewService`、不创建线程、不读文件、不生成图片**。

---

## 8. DecorationRole

`data(index, DecorationRole)`：

- `READY` → 返回真实的缩略图 `QPixmap`；
- `LOADING` / `UNSUPPORTED` / `MISSING` / `FAILED` / `UNREQUESTED` → 返回对应**占位图**。

不写二进制图片进 SQLite，不新增 preview DB 字段。

---

## 9. 占位图

不引入图片资源系统：用 `QPainter` 在 GUI 线程画 160×160 的简单占位（灰底 + 边框 + 文案），
按状态**记忆化**复用同一 `QPixmap`：

| 状态 | 文案 |
| :-- | :-- |
| LOADING | 加载中… |
| UNSUPPORTED | 不支持预览 |
| MISSING | 无预览 |
| FAILED | 预览不可用 |
| UNREQUESTED | （空） |

---

## 10. reload / load_more 行为

| 事件 | epoch | model | preview 调度 |
| :-- | :-- | :-- | :-- |
| 搜索 / 类型 / 缺 MOD / 待确认 / 排序 / 切换 Library / 首次加载 | **+1** | `set_items()`（清空旧预览状态） | 为新的 items 调度 |
| 加载更多 | 不变 | `append_items()`（**保留**旧的 READY 预览） | **只为新增的 items** 调度 |

`load_more` 的等待结果是「前 100 条的 preview 不被重新生成」——测试
`test_load_more_only_schedules_new_items` 用 `status()` 调用记录验证：
第一页记录 100 个 id，加载更多后新增记录恰为 101–150，且与第一页无交集。

---

## 11. 测试数量与结果

新增 `tests/test_gui_preview.py`，共 **22** 项；并更新了 C-1/C-2 的两条静态守护
（原先禁止 ui/ 出现 `PreviewService` / 线程类，现改为守护「`get_or_generate` 只能出现在
`preview_worker.py`」这一更有意义的约束）。

```text
569 passed in 22.86s （再跑一次 569 passed, 均 exit 0）
0 failed / 0 xfailed        （1.4-C-2 基线 547 + 新增 22）
```

覆盖：status 映射（ready/unsupported/missing/failed）、缓存命中不建 worker、
DecorationRole 各状态、单行 `dataChanged` 且**无 model reset**、worker 成功/异常、
worker 无 GUI 依赖、`get_or_generate` 仅出现在 worker、epoch 递增与丢弃（成功/失败/跨筛选）、
重复任务保护、load_more 只调度新增、GUI 线程约束（生成在后台 / QPixmap 在 GUI 线程）、
数据库只读不变量、源文件未被修改。

---

## 12. 真实样本验证（临时库 + 临时缓存目录，样本只读）

```text
resources                 character_card 22 / mod 13（合计 35）
default                   total 35，Load More 不显示（35 < PAGE_SIZE=100）
wait_for_previews()       True，pending 0
最终状态分布               ready 22 / unsupported 13
实际生成过预览的资源       22 个（全部是卡片）；zipmod 生成次数 0
缓存 .webp 文件            22 个（只有卡片）
搜索「沙耶香」             total 1 → 资源 id 4，状态 ready（缓存命中）
清空搜索                   total 35 / shown 35，Load More 仍不显示
total_changes             2406 → 2406（不变）
真实样本 36 文件           sha256 前后一致；size + mtime_ns 前后一致
```

- zipmod：`status()` 返回 `unsupported` → 稳定占位、不生成、不反复提交；
- 卡片：未生成的后台生成（22 个），完成后单格 `dataChanged`；
- 搜索切换：旧 epoch 结果按 epoch 丢弃，新结果里只出现新集合的资源；
- 真实样本 35 < 100，因此 Load More 未被触发（150 条并发场景由测试 fixture 覆盖）。

---

## 13. 数据库只读不变量

`total_changes` / `app_meta` / `needs_review` 在 preview 生成前后**均不变**
（合成测试 + 真实样本各一组断言）。preview 不改任何数据库状态、不写 DB 字段。

---

## 14. preview cache 文件变化情况

- 允许且**预期**的变化：`<cache_dir>/*.webp` 增加（真实样本：新增 22 个，全部来自卡片）；
- 缓存目录在测试中使用**临时目录**；真实样本验证使用临时缓存目录，未写入项目 `data/`；
- 源资源文件**零修改**：真实样本 36 文件 sha256 + size + mtime_ns 前后一致；
- 失败不落库、不留永久 failure marker（沿用 `PreviewService` 既有语义）。

---

## 15. P0 / P1 / P2

- **P0：无。P1：无。**
- P2（记录，未做）：
  1. `status()` 在缓存命中时会 `Image.open` + `verify`；一页 100 行会有少量磁盘 IO
     （GUI 线程），当前量级无感；若将来放大，再把 status 也挪进后台。
  2. 预览只在当前 model 的 items 上调度；滚动到大量条目时不预取（有意为之）。
  3. 无「取消」机制：epoch 丢弃结果，但已开始的短任务仍会跑完（符合本轮要求）。
  4. 占位图是 `QPainter` 现画的简单方块，非美术资源。

---

## 16. 完成后自检（逐条回答）

| # | 问题 | 结果 |
| :-- | :-- | :-- |
| 1 | worker 直接操作 QWidget？ | **否**（worker 未 import `QtWidgets`，有测试） |
| 2 | worker 直接操作 QAbstractListModel？ | **否**（同上，且无 `dataChanged`） |
| 3 | GUI 线程执行 `get_or_generate()`？ | **否**（静态：只有 `preview_worker.py` 出现该调用；运行时：spy 断言不在 GUI 线程） |
| 4 | 旧 epoch preview 污染新列表？ | **否**（epoch 不匹配即丢弃，4 条测试覆盖） |
| 5 | 同 resource + epoch 重复任务？ | **否**（状态检查 + pending 键，有测试） |
| 6 | 整个 model 被 reset 来刷新单个 preview？ | **否**（单行 `dataChanged`；测试断言无 `modelAboutToBeReset`） |
| 7 | 修改 schema / DB？ | **否**（v2 未变；`total_changes`/`app_meta`/`needs_review` 不变） |
| 8 | 修改真实样本？ | **否**（sha256 + size + mtime_ns 三重一致） |
| 9 | 引入新的业务逻辑到 UI？ | **否**（无查询/排序/判定；只有 UI 临时 preview 状态） |
| 10 | 提前实现 C-4？ | **否**（DetailPanel / MOD / Plugin / Usage / metadata 一律未动） |

---

## 17. 本阶段严格未做

完整 DetailPanel、MOD/Plugin/Usage/Metadata 详情 UI、收藏、删除、编辑、打开文件、
AI / fuzzy / alias / 跨语言、health score、tagging、persistence、settings、
新 schema / migration / Query API、`BrowseService` 与 `PreviewService` 重构、
N+1 优化、复杂 MVC/MVVM、PreviewManager / PreviewStore / EventBus、全局缓存系统、
自定义复杂 Delegate、preload 全库、LRU/memory cache、priority scheduler、cancellation framework。

---

## 18. C-3 验收结论

**PASS。** 本轮唯一目标——「让 `PreviewService` 的耗时工作离开 GUI 线程，并安全地把结果
回传到 `QListView` 对应的单个资源项；切换筛选/搜索时旧任务绝不串图」——已由
22 项专项测试 + 真实样本验证双重证明。

### 附：验收对照

| 指令要求 | 结果 |
| :-- | :-- |
| `status()` 可在 GUI 线程、`get_or_generate()` 必须后台 | ✅（静态 + 运行时断言） |
| 使用 QThreadPool + QRunnable（无 QtConcurrent / 无自建 QThread） | ✅ |
| 信号载体 + 队列连接回 GUI 线程 | ✅ |
| worker 不操作 QWidget / model / QPixmap | ✅（import 检查 + 测试） |
| epoch 代际 + 过期丢弃 | ✅ |
| 重复任务保护（resource + epoch） | ✅ |
| model 保存 preview 状态、DecorationRole、占位图 | ✅ |
| 单行 `dataChanged`，不 reset 整个 model | ✅ |
| reload 递增 epoch 并重查；load_more 只追加且只为新增调度 | ✅（150 条测试） |
| 不预加载全库、不做全局缓存管理 | ✅ |
| 数据库只读不变量（允许写 preview 缓存文件） | ✅ |
| 真实样本 35 / 22 / 13 验证 | ✅ |
| 源文件 sha256 + size + mtime_ns 不变 | ✅ |
| schema 保持 v2 / 无 migration | ✅ |
| `__version__` / `__phase__` | ✅ 0.11.0 / `Phase 1.4-C-3 (Async Preview)` |
| 未提前进入 C-4 | ✅ |
