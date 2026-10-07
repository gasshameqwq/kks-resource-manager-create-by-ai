# Phase 1.4-C-5 Report — Relation Browse

> 版本：Phase 1.4-C-5 · schema v2（**未改动**）· 2026-10-07
>
> 目标：把 Query Layer **已经具备**的关系反查能力接进 GUI，完成
> `Resource → Relation → Resource` 的查询闭环。**不新增资源管理模型、不写库。**

---

## 1. Scope

- **C-5-a**：`BrowseService` 增加 4 个只读关系转发（authors / plugins / missing_mods / orphan_mods）。
- **C-5-b**：`FilterBar` 增加 作者 / 插件 / 缺失 MOD 三个筛选（映射到已有的
  `BrowserScope.author_id` / `plugin_guid` / `mod_guid`），并修正「有筛选但 0 结果」的空态判定。
- **C-5-c**：`DetailPanel` 的 MOD 依赖表增加「按此 MOD 筛选」→ `MainWindow` → `BrowserPanel`，
  形成 `资源 → MOD → 资源` 闭环。

**不做**：写操作、schema/migration、Parser/Scanner/ResourceStore/PreviewService/Thumbnail 改动、
EventBus / PreviewManager / NavigationManager / FilterManager / MVC-MVVM / 导航栈 / 新页面、
N+1 与规模优化、fuzzy / alias / 跨语言、标签 / 收藏 / 删除 / 编辑 / 文件操作。

> 与指令的一处差异（已按「以实际代码为准」处理）：`core/query/resource.py` / `mod.py` /
> `author.py` / `plugin.py` **不存在**；`ResourceQuery / ModQuery / AuthorQuery / PluginQuery`
> 全部定义在 `core/query/queries.py`。

---

## 2. Files changed

| 文件 | 改动 |
| :-- | :-- |
| `core/query/browse.py` | 新增 4 个只读转发方法 + 3 个 Query 实例 |
| `ui/filter_bar.py` | 新增作者/插件/缺失MOD 三个下拉（第二行）+ 选项填充 + 清除 + 信号抑制 |
| `ui/browser_panel.py` | scope 接入三个关系筛选；`_has_active_filters` 扩展；`reload_relation_options()`；`apply_relation_filter()` |
| `ui/detail_panel.py` | MOD 表可选中 + 「按此 MOD 筛选」按钮 + `mod_filter_requested` 信号 |
| `ui/main_window.py` | 连接 `mod_filter_requested` → `apply_relation_filter`；**closeEvent 等待后台 worker**（P1 修复，见 §8） |
| `core/__init__.py` | `__version__` → 0.13.0；`__phase__` → `Phase 1.4-C-5 (Relation Browse)` |
| `tests/test_gui_filters.py` | 修正一条静态断言口径（见 §7 备注） |
| `README.md` | 状态行 / 路线图 / 文档表同步 |

**新增**：`tests/test_relation_browse.py`（28 项）、本报告。

**未改动**：`core/query/queries.py`、`core/query/dto.py`、`core/query/search.py`、
`core/thumbnails/service.py`、`core/database/*`、`core/parsers/*`、`core/scanner/*`、
`core/models/*`、`cli_query.py`、`main.py`、`ui/library_panel.py`、`ui/resource_model.py`、
`ui/preview_worker.py`、真实样本。

---

## 3. BrowseService 新增 API（C-5-a）

```python
BrowseService.authors(*, with_resources: bool = False) -> list[AuthorSummary]
BrowseService.plugins() -> list[PluginSummary]
BrowseService.missing_mods() -> list[ModSummary]
BrowseService.orphan_mods() -> list[ModSummary]
```

- 全部为**只读转发**：分别调用 `AuthorQuery.list()` / `PluginQuery.list()` /
  `ModQuery.missing()` / `ModQuery.orphan()`；
- **不新增 SQL、不新增 DTO、不复制 Query 逻辑**（静态测试断言 `browse.py` 无 `.execute(` / 无 `SELECT `）；
- `with_resources=True` 用 `AuthorSummary.resource_count > 0` 过滤掉没有任何资源的作者
  （供 GUI 下拉使用；不查关系明细）；
- 缺失 MOD 的 `ModSummary` 带 `used_by_count` / `usage_count`（由 core 提供，未重算 usage）。

---

## 4. FilterBar 新增筛选（C-5-b）

新增第二行（第一行保持原样）：

```
作者 [全部作者/Evaan(5)/…]   插件 [全部插件/moreAccessories(22)/…]   MOD [全部缺失 MOD/moderchan…(12)/…]
```

| 控件 | 显示 | 内部值 → BrowserScope |
| :-- | :-- | :-- |
| 作者 | `名称（资源数）` | `author_id` |
| 插件 | `GUID（资源数）` | `plugin_guid` |
| 缺失 MOD | `GUID（被引用资源数）`，**按 used_by 倒序** | `mod_guid` |

- MOD 下拉 **可输入**（`setEditable(True)` + `NoInsert` + `MatchContains` completer），
  134 项不必手动滚动；
- 「全部」= `None`（三个下拉都有）；
- `clear_relation_filters()` 一键复位；
- 填充选项时用 `_populating` 抑制信号，避免逐项触发查询；
- **`BrowserScope` 未修改**（`author_id` / `plugin_guid` / `mod_guid` 本就存在），
  只是把 FilterBar 的值传进去；
- 缺失 MOD 下拉只列缺失 MOD（按指令）；若详情面板传入**已安装** MOD 的 guid，
  `set_missing_mod(..., add_if_missing=True)` 会临时补一个条目，避免「点了没反应」。

**空态修正**：`BrowserPanel._has_active_filters()` 已把 `mod_guid` / `plugin_guid` /
`author_id` 计入，因此「选了关系筛选但 0 结果」显示 **「没有匹配的资源」**，
而不会误显示成「该资源库暂无资源」（三个筛选各有测试）。

---

## 5. DetailPanel → MOD → Resource 闭环（C-5-c）

```text
DetailPanel（MOD 表可选中行 + 「按此 MOD 筛选」按钮）
    → mod_filter_requested(mod_guid)
    → MainWindow._on_mod_filter_requested
    → BrowserPanel.apply_relation_filter(mod_guid=…)
    → FilterBar 状态同步 → criteria_changed → reload()
    → BrowseService.page(BrowserScope(mod_guid=…)) → 资源列表刷新
```

- **不新建页面 / 导航栈 / EventBus**；DetailPanel 不持有 `BrowseService`、不改 `BrowserScope`；
- 按钮默认禁用，选中 MOD 行后才可用；`_render_mods()` 每次重渲染都会清空选择并禁用按钮；
- 对 **missing MOD**：显示所有也缺该 MOD 的资源；对 **installed MOD**：显示使用该 MOD 的资源
  （两者都走同一个 `mod_guid` 筛选，语义由 core 定义）；
- 闭环后列表被替换 → 详情按 C-4 的 selection lifecycle 清空（有测试，C-4 行为不回归）。

---

## 6. 测试数量与结果

新增 `tests/test_relation_browse.py`，共 **28** 项：

| 组 | 覆盖 |
| :-- | :-- |
| BrowseService | authors / authors(with_resources) / plugins / missing_mods / orphan_mods；与底层 Query 结果一致；只读；无 SQL |
| FilterBar | 默认 None；选项来自 service（作者过滤 0 资源作者）；MOD 按 used_by 排序；可编辑；作者/插件/MOD 选择；已安装 guid 兼容；清除 |
| 组合 | search+关系、type+关系、missing+具体 MOD、review+关系、sort+关系 |
| 空态 | 作者/插件/MOD 三种关系筛选各自 0 结果 → 「没有匹配的资源」（≠「该资源库暂无资源」） |
| DetailPanel | 按钮需先选中；无 MOD 时禁用；installed / missing 分别发出正确 GUID |
| MainWindow | 闭环应用 `mod_guid`；reload 后详情清空（C-4 不回归） |
| 架构 | `ui/*.py` 不得 import `ModQuery/AuthorQuery/PluginQuery/ResourceQuery/UsageQuery/sqlite3` |
| 只读 | `total_changes` / `app_meta` / `needs_review` / 六张关系表行数不变 |

```text
630 passed in 28.36s
0 failed / 0 xfailed        （1.4-C-4 基线 602 + 新增 28）
```

> 备注：C-2 时期的一条静态断言（`filter_bar.py` 内不得出现 `sorted(`）被本轮改动触发——
> FilterBar 现在会对**自己的下拉选项**排序（展示顺序，不是资源排序）。
> 已把该断言改为更准确的口径：**资源列表**（`browser_panel.py`）不得出现 `sorted(`，
> 且 FilterBar 不接触 `ResourceListItem`。资源排序仍 100% 交给 core。

---

## 7. 真实样本结果

真实样本扫入**临时库**、preview 使用**临时缓存目录**：

```text
Evaan → 5 resources                 （Query Layer 也是 5）
moreAccessories → 22 resources      （Query Layer 也是 22）
moderchan.CharamakerSupportMOD → 12 （Query Layer 也是 12）
missing_mods() → 134 distinct missing MODs
orphan_mods()  → 3
plugins()      → 29
authors()      → 3
缺 MOD + moderchan.CharamakerSupportMOD → 12（与 Query Layer 一致）

DetailPanel（id=19，20 条 MOD 依赖，含目标 MOD）
  → 选中该行 → 点「按此 MOD 筛选」
  → 中栏 12 条，scope.mod_guid == moderchan.CharamakerSupportMOD（与 Query Layer 一致）
```

---

## 8. 只读不变量 + 本轮发现并修复的 P1

**只读不变量（全部通过）**

```text
total_changes        2406 → 2406（不变）
needs_review = 1     0（不变）
schema               v2 / MIGRATIONS [1, 2]
真实样本 36 文件      sha256 / size / mtime_ns 前后一致
preview 缓存         仅写临时缓存目录（22 个 .webp）
```

合成测试另外断言 `app_meta` 与 `resources / mods / resource_mods / resource_mod_usages /
resource_plugins / resource_authors` 六表行数不变。

**P1（本轮发现并修复，非 C-5 功能）**

真实验证时发现：**关闭窗口时若仍有预览 worker 在跑，进程会在退出阶段崩溃（exit 0xC0000409）**。
复现对比：

| 场景 | 退出码 |
| :-- | :-- |
| 关窗前 `wait_for_previews()` | 0 |
| **不等待直接关窗退出** | **0xC0000409（崩溃）** |

根因：C-3 引入的后台 `QRunnable` 在解释器退出时仍存活（PyQt 已知问题）。
最小修复：`MainWindow.closeEvent()` 里 `QThreadPool.globalInstance().waitForDone(5000)`
（`_wait_for_background_workers`），不做任何架构改动。修复后复现脚本退出码为 0。

> 这是用户可感知的崩溃（生成缩略图中途关窗即触发），属 P1，因此在本轮一并修复并记录；
> 除此之外未扩大 C-5 范围。

---

## 9. P0 / P1 / P2

- **P0：无。**
- **P1：1 个（已修复）** —— 退出期后台 worker 崩溃，见 §8。
- **P2（记录，未做）**：
  1. 关系筛选是 **Library 内**生效（中栏始终受左侧 Library 约束）；跨库的全局反查未做。
  2. 缺失 MOD 无名称（本地没有 manifest，数据不存在），下拉只显示 GUID + 使用数。
  3. 作者/插件下拉在几百项规模时可能偏长（当前 3 / 29 项无感）。
  4. 详情面板与网格各有一份 status→UI 状态映射（C-4 已记录，未抽象）。
  5. 作者仍是逐行查询（BrowseService 的 N+1），本轮按要求不做优化。

---

## 10. Explicit non-goals

写操作（增删改、文件操作、打开文件/文件夹）、schema / migration 变更、
Parser / Scanner / ResourceStore / PreviewService / Thumbnail 改动、
标签 / 收藏 / 删除 / 编辑、AI / fuzzy / alias / 跨语言、
health score / settings / 持久化 UI 状态、EventBus / PreviewManager / PreviewStore /
NavigationManager / FilterManager / QueryController、复杂 MVC-MVVM / 导航栈 / 新页面 /
MOD·作者·插件独立管理页、N+1 与规模优化、Usage 虚拟化。

---

## 11. Final PASS / NEEDS REVISION

```text
Phase 1.4-C-5 PASS
```

### 特别报告

```text
schema version         v2（SCHEMA_VERSION=2，MIGRATIONS=[1,2]，无新 migration）
__version__            0.13.0
__phase__              Phase 1.4-C-5 (Relation Browse)
pytest result          630 passed / 0 failed / 0 xfailed
real sample result     Evaan=5 / moreAccessories=22 / moderchan…=12 / missing_mods=134 /
                       orphan_mods=3 / 闭环 12（全部与 Query Layer 一致）
database total_changes 2406 → 2406（不变）
sample file integrity  sha256 / size / mtime_ns 前后一致（36 文件）
```

### 附：验收对照

| 指令要求 | 结果 |
| :-- | :-- |
| MOD / Author / Plugin → Resource 查询可用 | ✅ |
| Resource → MOD → Resource 闭环可用 | ✅ |
| Search / Type / Missing / Review / Sort 与关系筛选可组合 | ✅（有测试） |
| 空结果状态正确 | ✅（三种关系筛选各自测试） |
| BrowseService 是 GUI 唯一查询入口 | ✅（静态测试） |
| 无 schema migration / 无写操作 | ✅ |
| 无新增复杂架构 | ✅（无 EventBus/Manager/导航栈/新页面） |
| 全部测试通过 | ✅ 630 passed |
| 真实样本验证通过 | ✅ |
| 数据库 read-only invariant | ✅ |
| 真实样本文件 integrity | ✅ |
| C-4 原有测试全部保持通过 | ✅（仅按新口径修正 1 条静态断言，见 §6 备注） |
