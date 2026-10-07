# Phase 1.4-C-4 — Detail Panel Design Review

> 版本：设计评审（**不实施**）· schema v2（未改动）· 2026-10-07
>
> 本轮只做代码核对 + 架构评估，产出本文档。**未修改任何业务代码、未改版本号 / `__phase__`。**

---

## 1. Scope

**目标**：基于当前仓库真实代码，确定第一版资源详情面板（DetailPanel）如何消费
`BrowseService` / `PreviewService`，以及现有 core 是否已足够支撑 C-4。

**本轮允许**：阅读代码 / 测试 / 文档；核对真实 DTO / API / SQL；新增本文档。

**本轮禁止（均未做）**：修改 `core/`、`ui/` 实现、`main.py`、schema、migration、
database、Parser / Scanner / ResourceStore、`BrowseService` / `ResourceQuery` /
`PreviewService`；新增 Query API；新增 DB 字段；实现 DetailPanel 或 MOD/Plugin/Usage/
Metadata 详情 UI；改版本号 / `__phase__`；进入收藏 / 编辑 / 删除 / 打开文件。

**核对过的文件**：`core/query/browse.py`、`core/query/queries.py`、`core/query/dto.py`、
`core/query/property_map.py`、`core/models/__init__.py`、`core/thumbnails/service.py`、
`ui/main_window.py`、`ui/detail_panel.py`、`ui/browser_panel.py`、`ui/resource_model.py`、
`ui/filter_bar.py`、`ui/preview_worker.py`、`ui/library_panel.py`，
以及 `tests/test_browse.py`、`tests/test_gui_smoke.py`、`tests/test_gui_filters.py`、
`tests/test_gui_preview.py`。

---

## 2. Current API verification

### 2.1 `BrowseService`（`core/query/browse.py`，实际公共方法）

```python
BrowseService(conn)
  .libraries(include_disabled=True) -> list[LibrarySummary]
  .page(scope, *, limit=None, offset=0, with_review_reasons=False) -> BrowsePage
  .detail(resource_id) -> ResourceDetail | None      # 直接转发 ResourceQuery.get()
  .review_reasons(resource_id) -> tuple[ReviewReason, ...]   # 直接转发
```

**核对结论**：`BrowseService` **只暴露这 4 个方法**，**没有**暴露 `ModQuery` /
`AuthorQuery` / `PluginQuery` / `UsageQuery`。因此 DetailPanel 能拿到的就是
`ResourceDetail` 的内容 + `review_reasons()`。

### 2.2 `PreviewService`（`core/thumbnails/service.py`，未修改）

```python
status(source) -> PreviewStatus            # 轻量；不生成
get_or_generate(source) -> PreviewStatus   # 生成/命中；可能写缓存
PreviewStatus(state, cache_key, path, reason)
  state ∈ {"unsupported","missing","ready","failed"}
```

`source` 接受任何带 `file_path`（可选 `extension` / `resource_type`）的对象
→ `ResourceSummary` 可直接传入。

### 2.3 UI 现状

- `ui/browser_panel.py`：C-2 的筛选/分页 + C-3 的 preview 调度（epoch、`QThreadPool`、单行 `dataChanged`）。
- `ui/preview_worker.py`：`PreviewWorker(QRunnable)` + `PreviewSignals(QObject)`。
- `ui/detail_panel.py`：**仍是 C-1 最小骨架**（空 / 已选中 id+名称+类型 / 错误三种文本状态），无 service。
- `ui/main_window.py`：`MainWindow(browse_service=None, preview_service=None)`；选中的资源经
  `_on_resource_selected` → `service.detail()` → `detail_panel.show_detail()`。

---

## 3. ResourceDetail structure

### 3.1 `ResourceSummary`（实际字段，逐项核对）

| 字段 | 类型 | 备注 |
| :-- | :-- | :-- |
| `id` | int | |
| `resource_type` | str | 取值见 `core.models.RESOURCE_TYPES` |
| `name` | str \| None | 解析名 |
| `display_name` | str \| None | 展示名（可与 name 不同） |
| `file_path` | str | 绝对路径 |
| `relative_path` | str \| None | 相对 Library 根（含目录） |
| `extension` | str \| None | 小写 |
| `card_marker` | str \| None | `KoiKatuCharaSun` / `KoiKatuChara` / None |
| `file_size` | int \| None | 字节 |
| `modified_time` | float \| None | epoch 秒 |
| `library_id` | int \| None | 只有 id，**没有 Library 名** |
| `scan_status` | str | new/present/missing/error |
| `parse_status` | str | unparsed/ok/partial/failed/skipped |
| `needs_review` | bool | |
| `mod_count` / `usage_count` / `plugin_count` / `author_count` | int | 权威计数（来自关系表） |
| `game` | property → str \| None | 由 `card_marker` 映射（KKS/KK） |
| `title` | property → str | `display_name or name or file_path` |

**注意**：`ResourceSummary` **没有** `parse_error` 字段（见 §11 缺口 3）；
也**没有** Library 名、作者名、`has_missing_mods` 标记。

### 3.2 `ResourceDetail`（`ResourceQuery.get()` 的真实返回）

```python
ResourceDetail(
    resource: ResourceSummary,
    usages:  tuple[ModUsage, ...],        # 逐槽位使用事实
    mods:    tuple[ResourceModRef, ...],  # 资源↔MOD 汇总（含 installed）
    plugins: tuple[str, ...],             # 仅 GUID
    authors: tuple[ResourceAuthor, ...],
    metadata: dict,                        # json.loads(metadata_json)，失败→{}
)
```

`get()` 的实现是「1 次 summary + usages + mods + plugins + authors + metadata」共 7 条只读小查询；
**资源不存在返回 `None`**。

### 3.3 各子 DTO 真实字段

**Authors** — `ResourceAuthor(author_id: int, name: str, ordinal: int, raw_name: str)`：
包含 id / name / raw_name，另有 `ordinal`（卡内原始列表下标，哨兵也占位）。

**MODs** — `ResourceModRef(mod_guid, mod_id, installed: bool, ref_count, relation, categories: tuple[str,...])`：

✅ **已能直接区分 installed / missing**（`installed` 由 core 的 `LEFT JOIN mods` 得出，
UI **不需要也不允许**自己判断）。

❌ **不含** MOD 的 `name` / `author` / `version` / `website`（那些在 `ModSummary` 里，
而 `ModSummary` 只能经 `ModQuery` 拿到，`BrowseService` 未暴露）。

**Usages** — `ModUsage(resource_id, mod_guid, property, category, slot, local_slot, category_no)`：

✅ `property` 与 `category` 都已有；`category` 是 **Query Layer 用
`core/query/property_map.py` 算好的**（face/body/clothes/accessory/hair/makeup/unknown），
UI 不得重新分类。

**Plugins** — `tuple[str, ...]`，**只有 GUID，没有名称**（数据模型里就不存在插件名）。

**Metadata** — Python **dict**（`json.loads` 的结果，非 dict 或解析失败时返回 `{}`）。
真实样本里 8 个键：`user_id`、`data_id`、`card_version`、`embedded_texture_count`、
`plugin_count`、`face_preview_kind`、`block_sizes`(dict)、`authors_raw`(list)。

### 3.4 Parse / Scan / Review 可用的信息

| 信息 | 是否可直接用于详情页 | 来源 |
| :-- | :-- | :-- |
| `scan_status` | ✅ | `ResourceSummary` |
| `parse_status` | ✅ | `ResourceSummary` |
| `needs_review` | ✅ | `ResourceSummary` |
| `parse_error` | ⚠️ 间接 | **不在 `ResourceSummary`**；经 `review_reasons()[i].detail` 拿到（仅 parse_* 理由携带） |
| `review_reasons()` | ✅ | `BrowseService.review_reasons(id)`（只读派生，不改 `needs_review`） |

---

## 4. DetailPanel information architecture

### 4.1 分级结论（基于真实数据，不照抄建议结构）

**第一版必须显示（核心价值，数据齐全）**

1. **Preview**（复用 C-3；见 §5）
2. **Identity**：标题（`display_title`）、`resource_type`、`game`、`relative_path`
3. **Basic Info**：`extension`、`file_size`、`modified_time`、`scan_status`、`parse_status`
4. **MOD Dependencies**：逐条 `mod_guid` + **installed / missing** + `ref_count` + `categories`
   —— 这是本项目最核心的管理信息（真实样本 14/35 资源存在缺失 MOD）
5. **Authors**：`name`（多个按 `ordinal` 排序）；无作者时显示 `authors_raw` 提示

**第一版建议显示（成本低、信息量合理）**

6. **Usage 摘要 + 明细（默认折叠）**：先给「按 category 的计数摘要」，明细列表默认折叠
   —— 真实样本单资源最多 **301** 条 usage，展开前不应撑爆面板
7. **Plugins**：GUID 列表（默认折叠；真实样本最多 21 条）
8. **Parse / Scan / Review 状态**：一行状态 + `review_reasons()`（仅有 reason 时展开）

**第一版暂时隐藏（有理由）**

9. **Metadata 原始 JSON** → 默认折叠，只显示少量「人可读」键
   （`card_version` / `user_id` / `data_id` / `embedded_texture_count` / `face_preview_kind`）；
   `block_sizes`、`authors_raw` 等原始结构放折叠的只读文本框，不做美化
10. **Library 名** → `ResourceDetail` 里没有；但浏览是按 Library 进行的，
    MainWindow 可以把自己当前选中的 Library 名传给 DetailPanel（**无需 core 改动**）
11. **MOD 名称 / 作者** → 数据不在 `ResourceDetail` 里（见 §3.3 / §11），v1 只显示 GUID
12. **Usage 全量 + 分页 / 懒加载** → 301 条在可滚动列表里足够，v1 不做分页

---

## 5. Preview reuse design

1. **DetailPanel 是否应直接使用 `PreviewService`？**
   **不应直接持有**。C-3 已确立「生成只能经 `PreviewWorker` + `QThreadPool`」。
   DetailPanel 应复用同一套：`PreviewService`（注入）+ `PreviewWorker`（复用，不新增类）。

2. **能否复用 BrowserPanel 已生成的缓存？**
   **能，而且是默认路径**：`PreviewService` 的 cache key 是
   `sha256(file_path_key + size + mtime)`，与「谁请求」无关；BrowserPanel 生成的同一资源
   缓存文件，DetailPanel 再次请求会 **cache hit**（`status()` → `ready`），不会重复生成。

3. **如何避免同一资源重复生成？**
   - 跨组件：靠上面同一条 cache key（无需共享状态）；
   - 组件内：DetailPanel 自己维护 `self._preview_epoch`（选择代际）+
     `(resource_id, epoch)` 记账，沿用 C-3 的重复保护写法。

4. **unsupported / missing / failed 如何显示？**
   与网格一致：`unsupported` → 「不支持预览」（zipmod）；`missing`（源文件不在）→「无预览」；
   `failed` →「预览不可用」。占位图复用 `ui/resource_model.placeholder_pixmap(state)`。

5. **切换资源时旧 preview 是否可能串到新资源？**
   与 C-3 相同的风险，解决办法相同：**selection epoch**——每次 `show_detail()` 递增；
   worker 携带 epoch 返回，不匹配即丢弃。

6. **是否需要新的 `PreviewManager` / `PreviewStore` / `EventBus`？**
   **不需要。** 理由：`PreviewService` 自带文件缓存（跨组件复用）；跨线程/代际问题
   C-3 已经用 `PreviewWorker` + epoch 解决；再引入管理器只会重复这两件事。

---

## 6. Selection lifecycle

现状（C-1/C-2 已实现）：

```text
LibraryPanel.library_selected -> MainWindow._on_library_selected -> BrowserPanel.set_library -> reload
QListView.selectionModel().currentChanged -> BrowserPanel.resource_selected(id)
    -> MainWindow._on_resource_selected -> BrowseService.detail(id) -> DetailPanel.show_detail()
```

逐问回答：

1. **没有 selection** → `DetailPanel.show_empty()`（“请选择一个资源”）。
2. **选中资源** → MainWindow 调 `service.detail(id)` → `show_detail(detail)`；
   `detail is None` 时 `show_missing(id)`。
3. **reload 后原 resource 不再在列表里** → 必须回到空状态。C-2/C-3 的 `reload()`
   会 `set_items()`（模型 reset），Qt 会清空 selection 并触发
   `currentChanged(invalid)`，BrowserPanel 因而发出 `resource_selected(None)`
   → MainWindow 调 `detail_panel.show_empty()`。
   **C-4 必须补一条测试确认这一点**；若某平台不触发该信号，最稳妥的 2 行修法是
   在 `BrowserPanel.reload()` 末尾显式 `self.resource_selected.emit(None)`
   （属 UI 改动，本轮不做）。
4. **load_more** → 只是追加行，不改当前 selection → **详情保持不变**（正确行为）。
5. **详情加载失败** → `MainWindow` 已有 `try/except` → `detail_panel.show_error(...)`
   （C-1 已实现）。
6. **resource_id 不存在** → `detail()` 返回 `None` → `show_missing(id)`。
7. **Library 切换** → `set_library()` → `reload()` → 同第 3 点 → 详情回到空状态，
   不会残留旧 Library 的资源。

**核心原则**：DetailPanel 只显示「MainWindow 当前告诉它的资源」，
自己不持有列表、不记忆上一次选择。

---

## 7. Threading decision

**结论：`BrowseService.detail()` 直接在 GUI 线程执行即可，不需要异步。**

实测（真实样本，临时库）：

```text
35 个资源的 detail() 全部调用合计 12.4 ms   → 约 0.35 ms / 个
usages 每条最多 301；mods 最多 43；plugins 最多 21；authors 最多 2
metadata_json 最大 366 字节（中位数 336）
```

单次详情 = 7 条带索引的 SQLite 小查询 + 一次 `json.loads`（≤366 字节），
毫秒级以内；GUI 线程执行完全可接受。**不要为了「看起来更高级」引入线程。**

如果将来出现超大资源（例如 usages 上万条），再单独评估「分页 / 懒加载 / 异步」，
本轮不设计、不实现。

---

## 8. UI widget design

整体：`DetailPanel(QWidget)` = `QScrollArea` + 垂直排列的若干 section（普通 `QWidget`/`QGroupBox`），
**不做 MVC/MVVM、不做自定义 delegate、不做复杂 controller**。

| 区域 | 建议控件 | 理由 |
| :-- | :-- | :-- |
| Preview | `QLabel`（居中，固定高度） | 单张图 + 文字占位 |
| Identity | `QLabel`（标题，可选中文本）+ `QFormLayout` | 键值对，天然适合表单 |
| Basic Info | `QFormLayout` | 同上 |
| Authors | `QLabel`（逗号分隔）或 `QListWidget` | 真实样本最多 2 个 → 用 `QLabel` 即可 |
| MOD Dependencies | `QTableWidget`（列：状态 / MOD GUID / 引用数 / 类别） | **missing 需明显区分**：缺失行整行标红/前缀「缺失」 |
| Usage | `QLabel`(按 category 的计数摘要) + `QListWidget`（明细，默认折叠） | 最多 301 条 → 必须可滚动、默认收起 |
| Plugins | `QListWidget`（默认折叠） | GUID 列表 |
| Metadata | `QFormLayout`（人可读键）+ 折叠的 `QPlainTextEdit`（只读，原始 JSON） | 避免把大 dict 直接堆到界面 |
| Parse/Scan/Review | `QFormLayout`（状态）+ `QLabel`（reasons，只有非空才显示） | Review 不做视觉中心 |

细节规则：

- **滚动**：整个面板放 `QScrollArea`；Usage/Plugins 用固定最大高度的内嵌滚动列表（避免面板无限拉长）。
- **折叠**：用 `QGroupBox.setCheckable(True)` 实现即可（无需自研折叠控件）。
- **长路径**：显示 `relative_path`（短、可读）为主；完整 `file_path` 放 `tooltip` +
  可选中文本；必要时用 `QFontMetrics.elidedText` 中间省略。
- **长 metadata**：只把「人可读键」放进表单；原始 JSON 放折叠只读文本框，不默认展开。
- **空列表**：显示一行灰字（如「无 MOD 依赖」「无插件」），不显示空表格。
- **missing MOD**：整行用醒目前景色 + 「缺失」前缀；installed 行用普通色 + 「已安装」。
- **review reason**：`needs_review=False` 时只显示一行「状态正常」；有 reason 时列出
  `label`（+`detail`），不占据面板主体。

---

## 9. Empty / error states

| 情况 | 显示 | 由谁判定 |
| :-- | :-- | :-- |
| No selection | 「请选择一个资源」 | DetailPanel 默认态 |
| Resource not found（`detail()` 为 None） | 「找不到资源 #id」 | MainWindow / DetailPanel |
| Detail query failed（异常） | 「读取详情失败：<错误>」 | MainWindow `try/except` |
| Preview unsupported | 占位图「不支持预览」 | `PreviewService.status()` |
| Preview missing | 占位图「无预览」 | status = missing |
| Preview failed | 占位图「预览不可用」 | status = failed / worker failed |
| No authors | 「无作者信息」（可附 `authors_raw`） | `detail.authors == ()` |
| No MOD dependencies | 「无 MOD 依赖」 | `detail.mods == ()` |
| No missing MOD | 列表中全部显示「已安装」 | 由 `installed` 聚合展示 |
| No plugins | 「无插件」 | `detail.plugins == ()` |
| No metadata | 「无元数据」 | `detail.metadata == {}` |
| No review reasons | 一行「状态正常」 | `review_reasons()` 为空 |

全部使用**面板内局部状态**（标签 / 灰色文字 / 占位图），
**不引入 toast / notification center / 复杂 dialog**。

---

## 10. Performance assessment

真实样本（只读实测）：

```text
resources 35（character_card 22 / mod 13）
usages / resource   max 301, median 2, mean 43.6（top5: 301,220,192,192,192）
mods / resource     max 43,  median 1（top5: 43,42,42,31,26）
plugins / resource  max 21,  median 2
authors / resource  max 2
metadata_json       max 366 B, median 336 B
全部 35 次 detail()  12.4 ms（约 0.35 ms/次）
最大资源（id 26）    usages 301 / mods 25（2 已安装、23 缺失）/ plugins 10 / authors 1
```

结论：

- **单资源 detail 成本**：毫秒级以内，GUI 线程同步执行即可；
- **usages 多时 UI 成本**：301 行放进 `QListWidget` 可行，但**必须默认折叠 + 可滚动**；
- **metadata 很大时**：不适用（真实样本最大仅 366 B），直接做「人可读键 + 折叠原始文本」；
- **N+1**：`detail()` 一次返回全部内容 → **无 N+1**；唯一可能的 N+1 是「显示 MOD 名称」，
  本设计明确不做（见 §11）；
- **是否需要分页**：不需要；
- **是否需要 lazy section**：不需要懒加载，只需要**折叠**（纯 UI 行为）。

---

## 11. Core gaps

| # | 缺口 | 是否阻塞 C-4 | 说明 / 最小后续方案 |
| :-- | :-- | :-- | :-- |
| 1 | `ResourceModRef` 没有 MOD 名称 / 作者（只有 guid / installed / ref_count / relation / categories） | **非阻塞** | v1 只显示 GUID + 已安装/缺失 + 引用数 + 类别；若将来要名称，最小方案是给 `BrowseService` 加只读 `mod_labels(guids)`（内部复用 `ModQuery`，一次批量查询），**不改 schema** |
| 2 | 插件只有 GUID、没有名称 | **非阻塞** | 数据模型里不存在插件名（`resource_plugins` 只有 `plugin_guid`），无法补 |
| 3 | `parse_error` 不在 `ResourceSummary` | **非阻塞** | 经 `review_reasons()[].detail` 间接可得 |
| 4 | `ResourceDetail` 不含 Library 名 | **非阻塞** | 浏览按 Library 进行，MainWindow 可把当前 Library 名传入 DetailPanel |
| 5 | `ResourceSummary.title` 与 `ui/resource_model.display_title` 的回退链略有差异 | **非阻塞** | DetailPanel 直接复用 `ui.resource_model.display_title()`，列表与详情显示一致 |

**没有任何一项阻塞 C-4 实施**；全部可用「现有 DTO + UI 组合」绕过，且都不需要改 schema。

---

## 12. Explicit non-goals

本轮**未设计为已有**，且 C-4 第一版**不做**：收藏、删除、编辑、打开文件 / 文件夹定位、
AI、fuzzy search、alias、跨语言归一化、health score、tagging、持久化 UI 状态、settings、
全局缓存、EventBus、`PreviewManager` / `PreviewStore`、自定义复杂 Delegate、
作者导航、MOD 导航、Plugin 导航、Usage 分页 / 虚拟化。

（未来方向一句话记录：以上属「浏览之上的操作与导航」，应在只读读模型稳定、
出现真实需求后单独评估。）

---

## 13. C-4 implementation boundary

```text
DetailPanel（QScrollArea + 若干 section）
├── Preview          （复用 PreviewService + PreviewWorker + selection epoch）
├── Identity         （display_title / resource_type / game / relative_path）
├── Basic Info       （extension / file_size / modified_time / scan_status / parse_status）
├── Authors          （name，多作者按 ordinal；空则 authors_raw 提示）
├── MOD Dependencies （guid + installed/missing 高亮 + ref_count + categories）
├── Usage            （category 计数摘要 + 明细列表，默认折叠，可滚动）
├── Plugins          （GUID 列表，默认折叠）
├── Metadata         （人可读键表单 + 折叠的原始 JSON 只读文本）
└── Parse/Scan/Review（状态行 + review reasons，非视觉中心）
```

**C-4 第一版明确不做**：MOD 名称/作者、插件名称、作者/MOD/插件导航跳转、
Usage 分页或虚拟化、Metadata 美化渲染、任何写操作与持久化。

**允许的最小 UI 改动（属 C-4，不在本轮）**：

1. `ui/detail_panel.py`：从骨架扩展为上述结构（渲染 + preview 调度 + selection epoch）；
2. `ui/main_window.py`：把「当前 Library 名」与 `PreviewService` 传给 DetailPanel（若采用）；
3. **可选**：`ui/browser_panel.py` 在 `reload()` 末尾显式 `resource_selected.emit(None)`，
   以确保「列表变了 → 详情清空」在所有平台都成立（若测试证明 Qt 已自动触发则不需要）。

---

## 14. Final PASS / NEEDS REVISION

### A. 当前 core 是否已经足够支撑 C-4？

```text
PASS
```

理由：`BrowseService.detail()` 已提供 Identity / Basic / Authors / MOD（含 `installed` 标记）/
Usage（含 core 计算好的 `category`）/ Plugins / Metadata 的全部所需数据；
`review_reasons()` 提供 review 信息；C-3 的 `PreviewService` + `PreviewWorker` + epoch
机制可直接复用；实测 detail 成本约 0.35 ms/资源。§11 的 5 个缺口全部非阻塞且都不需要改 schema。

### B. DetailPanel 最小实现边界

见 §13：Preview / Identity / Basic Info / Authors / MOD Dependencies /
Usage（折叠）/ Plugins（折叠）/ Metadata（折叠）/ Parse-Scan-Review。
第一版不做 MOD 名称作者、插件名称、导航跳转、Usage 分页、任何写操作与持久化。

### C. Core 修改需求

```text
Core changes required: NO
```

（若将来要显示 MOD 名称/作者，可单独提出「给 `BrowseService` 增加只读 `mod_labels(guids)`」
的最小扩展 —— 本轮不实施、不改 schema。）
