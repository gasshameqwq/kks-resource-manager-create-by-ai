# Phase 1.4-C-2 Report — Search / Filter / Sort / Bounded Loading

> 版本：Phase 1.4-C-2 · schema v2（**未改动**）· 2026-10-06
>
> 目标：把 C-1 的静态资源网格变成真正可用的资源浏览器
> （搜索 / 筛选 / 排序 / 分页加载），**仍不实现 Preview 与完整 Detail**。

---

## 1. 修改文件列表

**新增**

| 文件 | 说明 |
| :-- | :-- |
| `ui/filter_bar.py` | `FilterBar`（Search / Type / Missing MOD / Needs Review / Sort）+ debounce |
| `tests/test_gui_filters.py` | C-2 GUI 测试（28 项，离屏） |
| `docs/phase1/PHASE1_4C2_REPORT.md` | 本报告 |

**修改**

| 文件 | 改动 |
| :-- | :-- |
| `ui/browser_panel.py` | 接入 FilterBar；统一 `reload()`；新增 `load_more()`；三种空状态；状态栏 |
| `ui/resource_model.py` | 新增 `append_items()`（「加载更多」用，**不重构 model**） |
| `core/__init__.py` | `__version__` → 0.10.0；`__phase__` → `Phase 1.4-C-2 (Search / Filter / Bounded Loading)` |
| `README.md` | 状态行 / 路线图 / 文档表同步 |

**未改动**：`schema.py` / migrations、`db.py`、`parsers/*`、`scanner/*`、`models/*`、
`library/store.py`、`thumbnails/*`、`core/query/*`（Search Core / BrowseService /
`has_missing_mods` 全部保持原样）、`cli_query.py`、`main.py`、`ui/main_window.py`、
`ui/library_panel.py`、`ui/detail_panel.py`、真实样本。

---

## 2. FilterBar 结构

```text
FilterBar (QWidget, 一行 QHBoxLayout)
├── QLineEdit       搜索框（placeholder「搜索名称 / 文件名 / 作者」，debounce）
├── QComboBox       资源类型（全部类型 / …）—— 选项来自 core.models.RESOURCE_TYPES
├── QCheckBox       只看缺 MOD
├── QCheckBox       待确认
└── QComboBox       排序（名称 ↑ / 名称 ↓ / 最近修改 ↓ / 最近修改 ↑ / 文件大小 ↓ / 文件大小 ↑）
```

中栏最终结构：

```text
BrowserPanel
├── FilterBar
├── QStackedLayout
│     ├── ResourceListView (QListView, IconMode)
│     └── 状态消息（无库 / 无资源 / 无匹配 / 查询失败）
└── BottomArea
      ├── StatusLabel（共 N 条，已显示 M 条）
      └── LoadMoreButton（按需显示）
```

FilterBar 只发一个信号 `criteria_changed`；**不含任何查询 / 排序 / 类型判定逻辑**。

---

## 3. BrowserScope 状态管理方式

- `BrowserScope` 是 frozen DTO，**未被修改**；也没有往里面塞 loading / selection /
  scroll / epoch 等 UI 状态。
- UI 状态就是 FilterBar 的控件值 + `BrowserPanel._library_id`；
  `BrowserPanel.scope()` 每次按需**新建**一个 `BrowserScope`：

  ```python
  BrowserScope(
      query=self.filter_bar.query(),
      resource_type=self.filter_bar.resource_type(),
      library_id=self._library_id,
      needs_review=self.filter_bar.needs_review(),
      has_missing_mods=self.filter_bar.has_missing_mods(),
      order_by=self.filter_bar.order_by(),
      descending=self.filter_bar.descending(),
  )
  ```

- 「未勾选 = `None`」严格按指令：Missing MOD 勾选 → `True`，取消 → `None`；
  Needs Review 同理（不是 `False`）。
- Library 仍然只由左侧 `LibraryPanel` 控制，经 `MainWindow` 传到 `BrowserPanel.set_library()`。

---

## 4. Search debounce 实现

- `QTimer`（single-shot，`SEARCH_DEBOUNCE_MS = 280`）属于 `FilterBar`；
- `search_box.textChanged` → `timer.start()`（每次 keystroke 重启计时）；
- `timer.timeout` → `criteria_changed` → `BrowserPanel.reload()`；
- 因此**输入过程中不查询数据库**，只有停顿 ≥280ms 才查一次；
- 连续输入只产生一次查询（有测试断言）。
- 空 / 纯空白查询经 core 归一化为「无文本条件」，恢复全部结果。
- 搜索字段（name / display_name / relative_path / author）与 FTS/LIKE 路由**完全由 core 决定**，
  GUI 不感知、不实现。

---

## 5. Sort 映射

排序项与 `ResourceQuery` 的 `order_by` 白名单一一对应（GUI 不做 `sorted()`，有静态测试守护）：

| 下拉项 | `order_by` | `descending` |
| :-- | :-- | :-- |
| 名称 ↑（默认） | `name` | `False` |
| 名称 ↓ | `name` | `True` |
| 最近修改 ↓ | `modified_time` | `True` |
| 最近修改 ↑ | `modified_time` | `False` |
| 文件大小 ↓ | `file_size` | `True` |
| 文件大小 ↑ | `file_size` | `False` |

排序**只通过** `BrowserScope.order_by` / `descending` 交给 core（SQL 排序）。

---

## 6. Load More 实现

- `PAGE_SIZE = 100`（固定）。
- 首屏：`page(scope, limit=100, offset=0)`。
- 按钮显示条件：`total > 0 and model.rowCount() < total`。
- 点击：`offset = model.rowCount()` → `page(scope, limit=100, offset)` →
  `model.append_items(...)`（**追加，不清空**）。
- 追加用 `QAbstractListModel` 的 `beginInsertRows/endInsertRows`，不重建整个 model。
- 状态栏始终来自 `BrowsePage.total` + 当前 model 行数，不自行估算。
- **不是**传统的「上一页 / 下一页 / 第 N 页」。

**筛选变化 vs 加载更多**（严格区分，有测试守护）：

| 场景 | 行为 |
| :-- | :-- |
| 搜索 / 类型 / 缺 MOD / 待确认 / 排序 / 切换 Library | **清空**结果、从 offset 0 重新查询（`reload()`） |
| 点击「加载更多」 | **保留**结果、追加下一页（`load_more()`） |

---

## 7. Empty state

| 场景 | 显示 | 判定方式 |
| :-- | :-- | :-- |
| 没有 Library | 「没有资源库 / 请先使用 CLI 添加资源库」 | `library_id is None` |
| Library 存在但没有资源 | 「该资源库暂无资源」 | `total == 0` 且**无**筛选条件 |
| 有资源但当前筛选无结果 | 「没有匹配的资源」 | `total == 0` 且**有**筛选条件（筛选条件保持不清空） |
| Browse 查询失败 | 「读取资源失败：…」 | 捕获异常后就地展示 |

---

## 8. BrowseService 调用路径

```text
FilterBar.criteria_changed / LibraryPanel.library_selected
        ↓
BrowserPanel.reload()  →  BrowserScope  →  service.page(scope, limit=100, offset=0)
        ↓                                       ↓
ResourceListModel.set_items(page.items)     page.total → 状态栏 / Load More

LoadMoreButton.clicked → BrowserPanel.load_more()
        ↓
service.page(scope, limit=100, offset=model.rowCount()) → model.append_items(...)

QListView.selectionModel().currentChanged
        ↓
resource_selected(id) → MainWindow → service.detail(id) → DetailPanel
```

GUI **只**调用 `BrowseService.libraries / page / detail`；不直接调用
`ResourceQuery.list/count`、`LibraryQuery`，不写 SQL —— 有静态测试守护。
`BrowseService.page()` 内部保证 `count` 与 `list` 使用同一个 scope，GUI 直接使用
`BrowsePage.total` / `items`，不存在「只刷新行不刷新 total」的路径。

---

## 9. 测试数量和结果

新增 `tests/test_gui_filters.py`，共 **28** 项（全部离屏）：

| 组 | 覆盖 |
| :-- | :-- |
| 默认状态 | scope 全为 None、默认排序 名称↑、状态栏文案、Load More 不显示 |
| Search | debounce 生效（输入后未查询）、flush 后生效、连续输入只触发一次、空搜索恢复全部、记忆 `relative_path` 命中、`file_path` 不命中 |
| Resource Type | 全部 / 各类型；下拉选项来自 `core.models.RESOURCE_TYPES` |
| Missing MOD | 未勾选 → None；勾选 → True；取消 → None |
| Needs Review | 未勾选 → None；勾选 → True；取消 → None |
| Sort | 名称/最近修改/文件大小 + 升降序；scope 正确；GUI 内无 `sorted(` |
| Library | 切换后重新查询；切换后 offset 重置（从 150 回到第一页） |
| Load More | 150 条数据：首屏 100、点击后 **追加**到 150（前 100 个 id 保持不变）、total 不变、按钮隐藏、重复点击幂等 |
| 筛选变化 | 清空旧结果并从 offset 0 重查 |
| model | `append_items` 保留已有行、空列表 no-op |
| 组合 | Library+Search+Type、Library+Missing、Search+Missing+Sort 的 scope 与结果 |
| 空状态 | 无 Library / 空 Library / 筛选无结果（三者文案互不相同） |
| 只读 | `total_changes` / `app_meta` / `needs_review` 不变 |
| 架构 | ui/*.py 仍不 import ResourceQuery / LibraryQuery / PreviewService / 线程类 |

```text
547 passed in 23.44s
0 failed / 0 xfailed        （1.4-C-1 基线 519 + 新增 28）
```

C-1 的 19 项测试全部保持通过。

---

## 10. 真实样本验证结果

真实样本扫入**临时库**，离屏驱动 FilterBar：

```text
默认                        total 35 / shown 35 / Load More 不显示
搜索「沙耶香」               total 1, 命中 id 4（经 relative_path，Search Core 未改）
只看缺 MOD                  total 14
搜索「Evaan」               total 5（作者关系命中）
待确认                      total 0 →「没有匹配的资源」
资源类型 = mod              total 13
组合「沙耶」+ 只看缺 MOD     total 0（该卡 MOD 已安装，组合后确实无匹配）
清空筛选后                   total 35 / shown 35 / Load More 不显示
选择资源 / reload / load_more 正常
total_changes               2406 → 2406（不变）
样本 36 文件                sha256 前后一致；size + mtime_ns 前后一致
```

> 分页：真实样本 35 < `PAGE_SIZE=100`，因此**首屏即全部**，不显示「加载更多」——
> 与「有界加载」语义一致（超过 100 条时才出现按钮，已由 150 条合成数据验证）。

---

## 11. 只读不变量

- GUI 测试：反复搜索 / 切类型 / 勾选筛选 / 改排序 / 切换库 / 加载更多 / 选中资源 前后，
  `conn.total_changes` 不变、`app_meta` 不变、`needs_review` 各行不变。
- 真实样本（临时库）：`total_changes` 保持 `2406 → 2406`。
- C-2 未引入任何写语句；查询仍全部经 `BrowseService` → 只读 Query Layer。

---

## 12. schema / version / phase

- **schema 仍为 v2**：`SCHEMA_VERSION == 2`、`MIGRATIONS == [1, 2]`；无新增 migration。
- `__version__ = "0.10.0"`，`__phase__ = "Phase 1.4-C-2 (Search / Filter / Bounded Loading)"`。

---

## 13. P0 / P1 / P2

- **P0：无。P1：无。**
- P2（记录，未做）：
  1. 作者仍是逐行查询（BrowseService 的 N+1），C-2 无感；待实测再优化。
  2. 刷新 / 筛选变化后不保留原选中项（selection 会重置）。
  3. 查询在 GUI 线程执行（样本 35 条无感）；若将来卡顿再单独设计查询异步化。
  4. 没有「上一页」；只有「加载更多」（符合本轮设计）。
  5. 搜索框没有「回车立即搜索」的显式绑定（`flush_search()` 已就绪，仅未接快捷键）。

---

## 14. 本阶段严格未做

Preview / Thumbnail / PreviewWorker / QThreadPool / QRunnable / QThread / QtConcurrent /
完整 DetailPanel / MOD·Plugin·Usage·Metadata 详情 / 收藏 / 删除 / 编辑 / 打开文件 /
AI / fuzzy / alias / 跨语言归一化 / health score / tagging / persistence / settings /
新 Query API / 新 schema / N+1 优化 / 自定义 Delegate / MVC-MVVM。

以上均未实现，也未顺手扩大范围。

---

## 15. C-2 验收结论

**PASS。**

验收标准「GUI 已经能够通过 Search / Filter / Sort / Library 组合控制 BrowserScope，
并且所有资源查询仍然统一经过 `BrowseService.page()`；超过 100 条资源时可以通过
『加载更多』追加结果，而不是替换已有结果」——已由 28 项专项测试 + 真实样本验证双重证明：

- 搜索（debounce）/ 类型 / 缺 MOD / 待确认 / 排序 / Library 六类变化**统一走 `reload()`**，
  每次都重新查询 `total` 与 `items`（不可能只刷行不刷 total）；
- `BrowserScope` 未被修改、未夹带 UI 状态；GUI 未新增任何查询路径；
- 150 条数据下：首屏 100 → 点击后 150（**追加**，前 100 条 id 不变）；
- 三种空状态文案互不相同，筛选条件在「无匹配」时仍然保留；
- 全流程只读，schema 保持 v2，真实样本未被修改。

---

### 附：验收对照

| 指令要求 | 结果 |
| :-- | :-- |
| FilterBar：Search / Type / Missing MOD / Needs Review / Sort | ✅ |
| 中栏：FilterBar + ListView + BottomArea(Status + LoadMore) | ✅ |
| 搜索 250–300ms debounce，不逐字查询 | ✅ 280ms（有测试） |
| Resource Type 用 core 的 RESOURCE_TYPES | ✅（有测试） |
| Missing MOD 勾选 → True，取消 → None | ✅ |
| Needs Review 勾选 → True，取消 → None | ✅ |
| Sort 映射 name / modified_time / file_size + 升降序 | ✅ |
| 排序交给 core，不在 UI `sorted()` | ✅（静态测试） |
| BrowserScope 不被修改、不塞 UI 状态 | ✅ |
| 统一 reload 路径（六类变化） | ✅ |
| 不出现「只刷新 model 不刷新 total」 | ✅（total 来自 BrowsePage） |
| PAGE_SIZE=100；只做「加载更多」，不做页码 | ✅ |
| 加载更多**追加**而非替换 | ✅（150 条测试） |
| 加载更多按钮显示条件 `offset+shown < total` | ✅（等价于 `shown < total`） |
| 三种空状态互不相同 | ✅ |
| Library 联动经 MainWindow → set_library | ✅ |
| 状态栏来自 total + model 数 | ✅ |
| 不引入后台线程 | ✅（静态测试） |
| selection → detail 链路不变 | ✅ |
| 不接入 PreviewService | ✅（静态测试） |
| super C-1 测试保持通过 | ✅ 519 → 547 |
| 真实样本验证（沙耶香=1 / missing=14 / Evaan=5 / needs_review=0 / 分页 35） | ✅ |
| `total_changes` / `app_meta` / `needs_review` 不变 | ✅ |
| schema v2 / 无 migration | ✅ |
| `__version__` / `__phase__` | ✅ 0.10.0 / `Phase 1.4-C-2 (Search / Filter / Bounded Loading)` |
