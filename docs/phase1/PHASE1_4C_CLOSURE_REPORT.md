# Phase 1.4-C Closure Report — GUI 只读浏览阶段收尾

> 版本：Phase 1.4（C-1 ～ C-5）· schema v2（**未改动**）· 2026-10-07
>
> 结论：**Phase 1.4-C = CLOSED / PASS**
>
> 依据：C-1 ～ C-5 的实现与测试 + `docs/phase1/PHASE1_4C-6` 收尾评估（Closure Review）
> + 真实样本（35 资源）验证。本文件只做收尾记录，**不新增任何产品功能**。

---

## 1. C-1 ～ C-5 最终能力清单

| 子阶段 | 交付 | 报告 |
| :-- | :-- | :-- |
| **C-1** | GUI 骨架：`QApplication` + `MainWindow` 三栏（LibraryPanel / BrowserPanel / DetailPanel）、`ResourceListModel`、`python main.py gui` | `PHASE1_4C1_REPORT.md` |
| **C-2** | Search（debounce 280ms）/ Filter（类型、只看缺 MOD、待确认）/ Sort / 有界加载（`PAGE_SIZE=100`，加载更多**追加**） | `PHASE1_4C2_REPORT.md` |
| **C-3** | 异步缩略图：`PreviewService` + `PreviewWorker`(QThreadPool/QRunnable) + epoch 防串图 + 单行 `dataChanged` | `PHASE1_4C3_REPORT.md` |
| **C-4** | 完整只读 DetailPanel（9 区域）+ selection lifecycle | `PHASE1_4C4_REPORT.md` |
| **C-5** | 关系反查：作者 / 插件 / 缺失 MOD → 资源；`资源 → MOD → 资源` 闭环 | `PHASE1_4C5_REPORT.md` |

底层（C 之前已完成，本阶段只读复用，未改动）：Library 管理（CLI）、Scanner/Parser、
Query Layer（Resource/Mod/Author/Plugin/Usage）、Search Core（FTS+LIKE）、
`has_missing_mods`、`review_reasons`、Browse Read Model、`PreviewService`。

---

## 2. GUI 最小只读闭环

```text
python main.py gui
 └─ MainWindow
     ├─ LibraryPanel     库列表（名称 + 资源数 + [disabled]；默认选第一个 enabled）
     ├─ BrowserPanel
     │    ├── FilterBar  第 1 行：搜索 / 类型 / 只看缺 MOD / 待确认 / 排序
     │    │              第 2 行：作者 / 插件 / 缺失 MOD（+ 每个「全部」）
     │    ├── ResourceListView (QListView IconMode + ResourceListModel)
     │    │              └ 缩略图（异步、epoch 防串图、占位图）
     │    └── 底部状态 + 加载更多（共 N 条，已显示 M 条）
     └─ DetailPanel      预览 / 标识 / 基本信息 / 作者 / MOD 依赖 /
                          Usage / 插件 / 元数据 / 解析-扫描-待确认
                         └── 「按此 MOD 筛选」→ 中栏刷新（闭环）
```

闭环验证（真实样本）：`Library → Search/Filter/Sort → Browse → Detail → Relation → Resource`。
13 项能力（Library / Search / Filter / Sort / Missing MOD / Review Reason / Browse /
Detail / Preview / Author 反查 / Plugin 反查 / MOD 反查 / 闭环）**全部可用**。

---

## 3. 测试与真实样本验证

```text
pytest                630 passed / 0 failed / 0 xfailed（24 个测试文件）
GUI 测试              119 项（smoke 19 + filters 28 + preview 22 + detail 33 + relation 28 - 含少量跨文件）
schema                v2（SCHEMA_VERSION=2，MIGRATIONS=[1,2]）
真实样本              35 资源（22 character_card + 13 zipmod）
```

真实样本关键结果（全部与 Query Layer 一致）：

```text
Search「沙耶香」             → 1（id 4，经 relative_path）
只看缺 MOD                  → 14
作者 Evaan                  → 5
插件 moreAccessories        → 22
缺失 MOD moderchan.CharamakerSupportMOD → 12
missing_mods() / orphan_mods() / plugins() / authors() → 134 / 3 / 29 / 3
Detail → 按此 MOD 筛选       → 12（闭环成立）
Preview                      → 22 ready / 13 unsupported（zipmod）
```

---

## 4. 只读不变量验证

```text
conn.total_changes     2406 → 2406（全部 C 阶段验证前后不变）
app_meta               不变
needs_review           各行不变（计数 0）
六张关系表行数          resources / mods / resource_mods / resource_mod_usages /
                       resource_plugins / resource_authors 全部不变
真实样本 36 文件        sha256 / size / mtime_ns 前后一致
preview 缓存           只写缓存目录（验证时用临时目录），源文件零修改
```

> 架构保证：GUI 只经 `BrowseService`（读）与 `PreviewService`（缩略图）；
> `ui/*.py` 不得 import `sqlite3` / `ResourceQuery` / `ModQuery` / `AuthorQuery` /
> `PluginQuery` / `UsageQuery`（有静态测试守护）。

---

## 5. 已知 P2 / Future 项

以下三项**已登记，本轮不实现**：

1. **跨库全局关系视图** —— 当前关系筛选（作者/插件/MOD）在**所选 Library 内**生效；
   跨库聚合未做。样本只有 1 个 Library，**无法用真实数据验证**其价值。
2. **`scan_status` GUI 筛选** —— CLI 有 `query resources --status`，GUI 无对应控件；
   真实样本 `missing = 0`，**无法验证**。
3. **orphan MOD GUI 列表** —— 3 条孤立 MOD 目前只能在 CLI 看到。

其它 P2（来自各阶段报告）：

- 缺失 MOD 无名称（本地无 manifest，**数据不存在**，无法补）；
- 作者为逐行查询（N+1）、`LIKE` 全表扫描（无规模证据，不优化）；
- 详情面板与网格各有一份 `status → UI 状态` 映射（未抽象，避免引入 PreviewManager）；
- `order_by` 白名单不含作者/缺失状态；
- 关系筛选不改变左侧 Library 选择。

### 关于 `BrowseService.orphan_mods()` 的准确描述

`BrowseService.orphan_mods()` **已经存在、已经测试通过**（`tests/test_relation_browse.py`），
因此**不得**把它描述成「Query Layer 能力缺失」。它的现状是：

> **CLI / API 可用，GUI 尚未接线**（C-5 只把「缺失 MOD」放进了 FilterBar 下拉）。

未来若接入 GUI，属于「一行接线 + 一个小视图」，不是新能力开发。

---

## 6. 明确 non-goals（永久保持）

- AI / 云端 / 语义搜索；fuzzy / alias / 跨语言**自动**归一化；
- health score；自动分类；自动标签；
- EventBus / 全局 AppController / Manager 大抽象 / MVC-MVVM 重构；
- 持久化 UI 状态；
- 为了「架构看起来完整」而增加的抽象层。

（标签 / Collection / 重复检测 / 批量文件操作属于**路线图后续 Phase**，不是 non-goal，
但需要真实需求驱动才启动。）

---

## 7. 为什么不继续 C-6

按「必须有真实、重要、样本可验证的问题」这一判据逐条对照：

| 判据 | 结论 |
| :-- | :-- |
| 是否存在真实、重要、已被样本验证的浏览/查询问题？ | **否**。剩余候选（跨库视图、`scan_status` 筛选、orphan 列表）在当前样本上**都无法验证**（1 个库 / missing=0 / orphan=3） |
| 是否只是「还能加一个按钮」？ | **是** |
| 是否重复已有能力？ | **会**：关系反查、缺 MOD、作者/插件反查在 C-5 已完成 |
| 是否有超出「已闭环」的明确用户价值？ | **没有** |

→ **C-6 不成立**：不为了保持编号连续而强行设计 C-6。

---

## 8. 下一阶段方向：Phase 1.5 — GUI Setup & Scan

只读浏览已闭环，但 **GUI 仍不自足**：要看到任何资源，用户必须先用终端执行
`library add` 与 `scan`。GUI 空状态本身也这样提示：

```text
没有资源库
请先使用 CLI 添加资源库
```

因此下一阶段的核心问题是：

> **让用户不打开终端，也能在 GUI 中管理 Library、执行 Scan，并在文件变化后刷新资源状态。**

这会**首次引入写操作与长任务（后台扫描）**，必须作为**独立阶段显式立项**，
不能塞进只读浏览阶段。详细设计见 `docs/phase1/PHASE1_5_DESIGN_REVIEW.md`。

---

## 9. 三条需要准确记录的备注

1. **「路径筛选」由 Search 覆盖**：搜索范围包含 `relative_path`（Phase 1.4-A.1），
   GUI 没有独立的「路径」控件——语义已满足，入口是搜索框。
2. **原始验收样本名称与当前真实样本不同**：Phase 0 的验收语是
   「搜索『一乃』『白峰一』都能命中」，但当前 35 资源样本中不存在这两个串
   （该卡的解析名是 `美樹さやか`，文件名才是中文「美树沙耶香」）。
   已完成**机制等价验证**：3 字走 FTS、1–2 字走 LIKE、文件名经 `relative_path`
   命中（「沙耶香」→ id 4）。细节见 `PHASE1_4A1_REPORT.md`。
3. **GUI 当前不是自足的**：Library 的增 / 删 / 启停与 Scan 只能在 CLI 完成，
   这是下一阶段（Phase 1.5）要解决的问题，而不是本阶段的缺陷。

---

## 10. Phase 1.4-C 最终验收标准

```text
1. python main.py gui 可启动并进入事件循环
2. 13 项能力全部可用（见 §1 / §2）
3. 关系筛选与 Search / Type / Missing / Review / Sort 可任意组合
4. 空态三态正确：无资源库 / 该资源库暂无资源 / 没有匹配的资源
5. GUI 只经 BrowseService + PreviewService；静态约束测试通过
6. pytest 全绿（630 passed / 0 failed / 0 xfailed）
7. 真实样本验证通过（35 资源；Evaan=5 / moreAccessories=22 / moderchan=12 /
   missing=134 / orphan=3 / 闭环=12）
8. schema 仍 v2，无新增 migration
9. 只读不变量成立（total_changes / app_meta / needs_review / 六表不变）
10. 真实样本 sha256 + size + mtime_ns 不变
```

以上 10 条**全部满足** → **Phase 1.4-C CLOSED / PASS**。
