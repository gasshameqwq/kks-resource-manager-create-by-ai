# Phase 1.4-C-4 Report — Detail Panel

> 版本：Phase 1.4-C-4 · schema v2（**未改动**）· 2026-10-07
>
> 目标：把 C-1 的 DetailPanel 骨架升级为真正可用的**只读**资源详情面板，
> 并复用 C-3 已完成的异步 Preview 能力。

---

## 1. Scope

实现 DetailPanel 的完整只读展示：
Preview / Identity / Basic Information / Authors / MOD Dependencies / Usage /
Plugins / Metadata / Parse-Scan-Review。

**不做**：任何写操作、导航跳转、收藏、编辑、删除、打开文件、AI/fuzzy/alias、
health score、tagging、settings、持久化 UI 状态、EventBus/PreviewManager/PreviewStore、
复杂 MVC/MVVM、自定义 delegate、Usage 分页或虚拟化。

**core 未改动**（`schema` / migration / database / models / Parser / Scanner /
ResourceStore / ResourceQuery / BrowseService / PreviewService 全部原样）。

---

## 2. Files changed

**修改**

| 文件 | 改动 |
| :-- | :-- |
| `ui/detail_panel.py` | 由 C-1 骨架重写为完整详情面板（`QScrollArea` + 9 个 section） |
| `ui/main_window.py` | 把 `PreviewService` 注入 DetailPanel；选中时同时取 `detail()` + `review_reasons()`，并传入当前 Library 名 |
| `ui/browser_panel.py` | `reload()` 末尾显式发 `resource_selected(None)`（见 §6，测试证明需要） |
| `ui/preview_worker.py` | 新增**按源文件路径的互斥锁**（见 §5，并发修正） |
| `core/__init__.py` | `__version__` → 0.12.0；`__phase__` → `Phase 1.4-C-4 (Detail Panel)` |
| `README.md` | 状态行 / 路线图 / 文档表同步 |

**新增**

| 文件 | 说明 |
| :-- | :-- |
| `tests/test_gui_detail.py` | Detail Panel 测试（33 项，离屏） |
| `docs/phase1/PHASE1_4C4_REPORT.md` | 本报告 |

**未改动**：`core/query/*`、`core/thumbnails/service.py`、`core/database/*`、
`core/parsers/*`、`core/scanner/*`、`core/models/*`、`cli_query.py`、`main.py`、
`ui/library_panel.py`、`ui/filter_bar.py`、`ui/resource_model.py`、真实样本。

---

## 3. DetailPanel architecture

```text
DetailPanel(QWidget)
└── QStackedLayout
    ├── [0] 状态标签（无选择 / 找不到资源 #id / 读取详情失败：…）
    └── [1] QScrollArea
        └── content (QVBoxLayout)
            ├── 预览            QLabel（占位图 / 缩略图）
            ├── 标识            QFormLayout：标题 / 类型 / 游戏 / 资源库 / 相对路径
            ├── 基本信息        QFormLayout：文件类型 / 大小 / 修改时间 / 扫描 / 解析
            ├── 作者            QLabel（多作者按 ordinal 顺序；空→「无作者信息」）
            ├── MOD 依赖        QTableWidget(状态|MOD GUID|引用数|类别) + 空态标签
            ├── Usage 使用情况  QLabel(按 category 计数) + 可折叠「明细」QListWidget
            ├── 插件            _Section(默认折叠) + QListWidget + 空态标签
            ├── 元数据          人可读键 QFormLayout + 可折叠「原始 Metadata」QPlainTextEdit(只读)
            └── 解析/扫描/待确认 QFormLayout + reason 文本（无 reason → 「状态正常」）
```

- 折叠用 `_Section(QGroupBox)`（`setCheckable` + `toggled → content.setVisible`），**没有自研折叠框架**。
- 默认展开：预览 / 标识 / 基本信息 / 作者 / MOD 依赖 / Usage / 元数据 / Review；
  默认折叠：Usage 明细 / 插件 / 原始 Metadata。（Usage 的**摘要**默认可见、**明细**默认收起，
  这是对 C-4 设计评审 §12 与 §16 冲突之处的取舍，以 §12 为准。）
- 长路径：Identity 显示 `relative_path`，完整 `file_path` 放在 section 的 tooltip。
- 无 Toast / 无通知中心：所有空态与错误都是面板内局部标签。

---

## 4. ResourceDetail integration

数据流保持「UI → BrowseService → Query Layer」：

```text
QListView.selectionModel().currentChanged
    → BrowserPanel.resource_selected(id)
    → MainWindow._on_resource_selected(id)
        detail  = BrowseService.detail(id)            # → ResourceQuery.get()
        reasons = BrowseService.review_reasons(id)    # → ResourceQuery.review_reasons()
        name    = MainWindow._current_library_name()  # 复用已加载的 Library 列表
    → DetailPanel.show_detail(detail, id, reasons, name)
```

DetailPanel **不持有** `BrowseService`，**不写 SQL**，**不 import** Query Layer
（有静态测试断言：源码无 `.execute(`、无 `SELECT `、import 里无
`sqlite3 / ResourceQuery / ModQuery / AuthorQuery / PluginQuery / UsageQuery`）。

字段用途（全部来自 DTO，未重新计算）：

| 区域 | 来源 |
| :-- | :-- |
| 标题 | `ui.resource_model.display_title()`（与列表行**同一套** fallback） |
| 类型 / 游戏 / 相对路径 | `ResourceSummary.resource_type` / `.game` / `.relative_path` |
| 文件类型 / 大小 / 修改时间 / 扫描 / 解析 | `ResourceSummary.extension / file_size / modified_time / scan_status / parse_status` |
| 作者 | `ResourceDetail.authors`（`ResourceAuthor.name`，按 core 给出的 `ordinal` 顺序） |
| MOD 状态 | `ResourceModRef.installed`（**core 判定**，UI 只做文案映射） |
| MOD 类别 | `ResourceModRef.categories`（core 用 `property_map` 算好） |
| Usage 类别 | `ModUsage.category`（**core 算好，UI 不重新映射**） |
| 插件 | `ResourceDetail.plugins`（GUID） |
| 元数据 | `ResourceDetail.metadata`（dict） |
| Review | `ResourceSummary` 三态 + `ResourceQuery.review_reasons()` |

---

## 5. Preview integration

复用 C-3，未新增 PreviewManager / PreviewStore / 全局缓存：

- `PreviewService.status(resource)` 在 **GUI 线程**执行（轻量）；
- 未生成时走 **`PreviewWorker` + `QThreadPool`** 后台生成；
- 结果经 `PreviewSignals.finished/failed` 队列连接回到 GUI 线程后，
  才由 `_load_pixmap()` 创建 `QPixmap` 并写入 `QLabel`（**QPixmap 只在 GUI 线程创建**）；
- **selection epoch**：`show_detail()` 每次 `+= 1`；回调 `epoch != self._preview_epoch`
  或 `resource_id != 当前资源` → 直接丢弃（切换资源不会串图）；
- 占位图复用 `ui/resource_model.placeholder_pixmap()`（**没有复制第二份实现**）；
  `unsupported / missing / failed` 语义与网格一致。

### 并发修正（本轮实际发现的问题）

网格与详情可能**同时**为同一资源请求预览（例如刚加载完页面就立刻选中），
而 `PreviewService` 的缓存写入不是互斥的：两个线程对同一 cache key 做
`os.replace` 时，Windows 上抛出 `PermissionError` → 会被报成 `failed`（偶发）。

最小修正（未改 core）：

1. `ui/preview_worker.py` 增加**按源文件路径**的互斥锁（`_lock_for(source)`）——
   它只是并发原语，不是缓存/管理器；第二个任务随后自然命中缓存；
2. `DetailPanel._on_preview_failed` 在标记失败前**复查一次** `status()`，
   若另一组件已写好缓存则直接显示 READY。

修正后，C-4 的预览用例（含并发场景）稳定通过。

---

## 6. Selection lifecycle

```text
无选择 ──（点击资源）──▶ 显示 A ──（点另一个）──▶ 显示 B
                          │
                          └─（搜索/筛选/排序/切换 Library → reload）──▶ 无选择（清空）
```

| 场景 | 行为 |
| :-- | :-- |
| 无选择 | `show_empty()` → 「请选择一个资源」 |
| 选中资源 | `detail()` + `review_reasons()` → 完整详情 |
| `detail()` 为 None | `show_missing(id)` → 「找不到资源 #id」 |
| 查询异常 | `show_error(text)` → 「读取详情失败：…」 |
| load_more | 只追加行、不动选择 → **详情保持不变**（正确） |
| reload / 切换 Library | 列表被替换 → 详情清空，不残留旧资源 |

### 本轮发现并修复的 UI 问题

**测试证明**：`QListView` 在模型 reset 后**并不保证**发出 `currentChanged`，
因此「列表已变、详情仍显示旧资源」确实会发生（`test_reload_clears_detail` 先失败）。

最小修复（2 行，仅 UI）：`BrowserPanel.reload()` 在三个分支（无 Library / 查询失败 / 正常）
结束后显式 `self.resource_selected.emit(None)`（`_emit_selection_cleared()`），
由 MainWindow 转发给 DetailPanel → 清空。修复后该测试通过。

---

## 7. Test results

新增 `tests/test_gui_detail.py`，共 **33** 项（离屏、临时库、临时缓存）：

基础（创建 / no selection / show_detail / show_missing / show_error / 格式化函数）、
Identity 与 Basic（标题 / 类型 / 游戏 / 资源库 / 相对路径 / 扩展名 / 大小 / 时间 / 扫描 / 解析）、
Authors（DTO 顺序 / 空）、MOD（installed / missing / ref_count / categories / 空表）、
Usage（category 摘要 / 明细 / 默认折叠 / 空）、Plugins（GUID / 空）、
Metadata（人可读键 / 原始 JSON / 只读 / 空）、Review（无 reason / 有 reason）、
Selection（A→B / A→None / 不存在的 id / reload 清空 / 切换 Library 不残留 / 查询异常）、
Preview（ready / unsupported / missing / failed / cache hit / epoch 递增 / 过期丢弃 /
跨资源结果丢弃 / QPixmap 只在 GUI 线程）、
只读不变量（数据库 6 张表行数 + `app_meta` + `needs_review`）、源文件未被修改、
架构静态约束（无 SQL / 无 Query Layer import / missing 只来自 `mod.installed`）。

```text
602 passed in 23.37s
0 failed / 0 xfailed        （1.4-C-3 基线 569 + 新增 33）
```

---

## 8. Real sample verification

真实样本扫入**临时库**、preview 使用**临时缓存目录**（样本只读），逐类选取验证：

```text
types                     character_card 22 / mod 13（合计 35）
normal card (id 4)        美樹さやか   KKS  mods=1(缺 0) plugins=2 authors=0 preview=ready
missing-MOD res (id 19)   GrangerHermione  mods=20(缺 20) plugins=17 authors=1 preview=ready
many-usage res (id 26)    KagemitsuNagao   mods=25(缺 23) plugins=10 authors=1
                          usage={body:1, face:5, hair:1, …} preview=ready
zipmod (id 5)             Cross_staff  type=mod  preview=unsupported（0 mods / 0 plugins）

total_changes             2406 → 2406（不变）
needs_review = 1 计数      0
schema                    v2 / MIGRATIONS [1, 2]
临时缓存 .webp             22 个（只有卡片会生成）
真实样本 36 文件           sha256 前后一致；size + mtime_ns 前后一致
```

结论：详情能完整显示；MOD installed/missing 与 core 判定一致；
Usage category 来自 core；卡片预览正常；**zipmod 显示 unsupported**；
数据库与样本文件均未被改动。

---

## 9. Read-only invariants

- 合成测试：反复切换 5 个资源 + 等待预览 + 取消选择后，
  `conn.total_changes` 不变、`app_meta` 不变、`needs_review` 各行不变、
  `resources / mods / resource_mods / resource_mod_usages / resource_plugins /
  resource_authors` 六张表行数不变。
- 真实样本：`total_changes` 保持 `2406 → 2406`；`needs_review = 1` 计数保持 0。
- preview 缓存文件写入**临时缓存目录**（预期行为，非数据库）；源资源文件零修改。

---

## 10. P0 / P1 / P2

- **P0：无。P1：无。**
- P2（记录，未做）：
  1. MOD 名称 / 作者仍未显示（`ResourceModRef` 不含；`BrowseService` 未暴露 `ModQuery`）
     —— 未来可按设计评审 §11 的最小方案加只读 `mod_labels(guids)`。
  2. 插件只有 GUID（数据模型无插件名）。
  3. `parse_error` 经 `review_reasons().detail` 间接展示（`ResourceSummary` 无该字段）。
  4. DetailPanel 与 BrowserPanel 各自维护一份「status → UI 状态」的映射（约 20 行重复）；
     未抽象成共享 helper，避免引入 PreviewManager。
  5. Usage 明细未做分页/虚拟化（301 条可接受，默认折叠）。

---

## 11. Explicit non-goals

本轮**未实现**：收藏、删除、编辑、打开文件 / 文件夹、作者/MOD/Plugin 导航、
AI、fuzzy search、alias、跨语言归一化、health score、tagging、settings、
持久化 UI 状态、全局缓存、EventBus、PreviewManager / PreviewStore、
复杂 MVC/MVVM、自定义 Delegate、Usage 分页 / 虚拟化、后台 SQLite 查询。

---

## 12. Final PASS / NEEDS REVISION

```text
Phase 1.4-C-4 PASS
```

### 特别报告

```text
schema version        v2（SCHEMA_VERSION=2，MIGRATIONS=[1,2]，无新增 migration）
__version__           0.12.0
__phase__             Phase 1.4-C-4 (Detail Panel)
pytest result         602 passed / 0 failed / 0 xfailed
real sample result    35 资源（22 卡 + 13 zipmod）逐类验证通过；zipmod=unsupported
database total_changes 2406 → 2406（不变）
sample file integrity sha256 / size / mtime_ns 前后一致（36 个文件）
```

### 附：验收对照

| 指令要求 | 结果 |
| :-- | :-- |
| DetailPanel 9 个区域 | ✅ |
| 复用 PreviewService / PreviewWorker / QThreadPool | ✅（未新增 PreviewManager） |
| `QPixmap` 只在 GUI 线程、生成在后台 | ✅（有测试） |
| selection epoch 防串图 | ✅（含跨资源丢弃） |
| 无选择 / 找不到 / 查询异常 三种状态 | ✅ |
| Identity / Basic / Authors / MOD / Usage / Plugins / Metadata / Review | ✅ |
| missing MOD 明显可辨（文字「缺失」+ 颜色） | ✅ |
| Usage 摘要默认可见、明细默认折叠、可滚动 | ✅ |
| 插件 / 原始 Metadata 默认折叠 | ✅ |
| 空态文案（无作者/MOD/插件/元数据/状态正常） | ✅ |
| 不 Toast / 不通知中心 | ✅ |
| 不改 core / schema / Query Layer / BrowseService / PreviewService | ✅ |
| 数据库只读不变量 | ✅ |
| 真实样本 sha256 / size / mtime_ns 不变 | ✅ |
| `__version__` / `__phase__` | ✅ 0.12.0 / `Phase 1.4-C-4 (Detail Panel)` |
| 测试 0 failed / 0 xfailed | ✅ 602 passed |
