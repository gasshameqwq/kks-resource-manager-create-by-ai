# Phase 3.5.2 — PyQt6 GUI 交互与视图集成实施契约

> 文档类型：Implementation Contract  
> 状态：**FROZEN**  
> 冻结日期：2026-10-24  
> 实施授权：用户已明确授权本子阶段实施与验证  
> Git 收尾：**未授权**；不得 commit / push / 创建或移动 tag

---

## 1. 目标

将既有用户数据写服务与查询模型接入 PyQt6 GUI：

1. FilterBar 支持 Favorite 与 Tag 筛选；
2. DetailPanel 展示 Tag，并支持添加/删除 Tag 与 Favorite 切换；
3. DetailPanel 支持 `display_name`、`notes`、`resource_type` 用户编辑；
4. 写入后从 Query / Browse 层重建 UI 状态与资源列表；
5. 保持 Phase 3.1 / 3.2 / 3.3 的冻结语义和 Phase 3.5.1 CLI 基线。

## 2. 权威与架构边界

本契约服从：

```text
docs/phase3/PHASE3_0_CONTRACT.md
docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md
docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md
docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md
docs/phase3/PHASE3_5_1_IMPLEMENTATION_CONTRACT.md
```

冻结的数据流：

```text
筛选：
FilterBar
  → BrowserScope(tag_id, favorite)
  → ResourceFilter
  → BrowseService / Query Layer

读取：
MainWindow
  → BrowseService.detail() / tags()
  → DetailPanel 展示

写入：
DetailPanel signals
  → MainWindow slot
  → TagWriteService / ResourceWriteService
  → BrowseService / Query Layer
  → 重建 Filter options + 当前列表 + 当前详情
```

UI 不直接执行 SQL、不连接 SQLite、不调用 Query 类构造器。  
`core/` 不 import PyQt6。

## 3. 文件范围

允许修改：

```text
ui/filter_bar.py
ui/browser_panel.py
ui/detail_panel.py
ui/main_window.py
main.py（仅在需要注入时）
```

允许新建：

```text
tests/test_ui_tags.py
docs/phase3/PHASE3_5_2_IMPLEMENTATION_CONTRACT.md
docs/phase3/PHASE3_5_2_LOG.md
```

实际实施未修改 `main.py`；CLI 到 GUI 的启动已经由 Phase 3.5.1 的 Eager
Bootstrap 覆盖。

## 4. FilterBar / BrowserScope

### 4.1 Favorite

`FilterBar.favorite_combo` 提供：

| UI 文本 | `favorite` |
| :--- | :--- |
| 全部 | `None` |
| 仅收藏 | `True` |
| 非收藏 | `False` |

`BrowserPanel.scope()` 必须把该值原样放入 `BrowserScope.favorite`，再经现有
`BrowserScope.to_filter()` 映射到 `ResourceFilter.favorite`。

### 4.2 Tag

`FilterBar.tag_combo`：

- 第一项为「全部标签」→ `None`；
- 其余项数据为 Tag id；
- 显示 `name（resource_count）`；
- 列表来源为 `BrowseService.tags()`，UI 不直接构造 `TagQuery`；
- 写操作后重建选项并保留仍存在的当前 Tag id。

`BrowserPanel.scope().tag_id` 必须进入 `ResourceFilter.tag_id`。

### 4.3 组合

Tag / Favorite 与已有筛选按既有 Query Model 语义组合，不新增解析器、不改变
`AND` 组合关系。

## 5. DetailPanel

### 5.1 展示

详情面板展示 `ResourceDetail.tags`：

- 用户 Tag 显示名称；
- 系统 Tag 显示 `[系统]` 标记；
- Favorite 状态与 `ResourceDetail.is_favorite` 一致；
- 可添加已有 Tag 时，不重复列出当前资源已关联的 Tag；
- Favorite 系统 Tag 不进入“已有标签”下拉，由专用收藏开关管理。

### 5.2 Tag 写入

| 交互 | 服务 API |
| :--- | :--- |
| 添加已有 Tag | `assign_tag(resource_id, tag_id)` |
| 新建并添加 Tag | `create_tag(name)`，成功后 `assign_tag(...)` |
| 删除 Tag 关联 | `unassign_tag(resource_id, tag_id)` |
| Favorite 开关 | `set_favorite(resource_id, bool)` |

系统 Tag 行不能被普通“移除所选标签”按钮删除。新建冲突由
`TagWriteService` 原样拒绝，不自动合并。

### 5.3 用户字段

| 字段 | 保存 | 清除 |
| :--- | :--- | :--- |
| `display_name` | `set_display_name` | `set_display_name(..., None)` |
| `notes` | `set_notes` | `set_notes(..., None)` |
| `resource_type` | `set_resource_type` | 无服务 API |

**冻结冲突说明**：Phase 3.1 明确不提供用户修正恢复自动类型的 API，且该子阶段
禁止修改 `core/`。因此 UI 只提供类型修正保存，并明确提示该限制；不得伪造
“清除”，不得直接 SQL 写 `resource_type` / `type_source`。

### 5.4 信号槽

DetailPanel 只发出意图信号：

```text
tag_assign_requested
tag_unassign_requested
tag_create_requested
favorite_change_requested
display_name_save_requested
notes_save_requested
resource_type_save_requested
```

MainWindow 连接这些信号，调用服务并处理错误/刷新。DetailPanel 不持有写服务。

## 6. 写入后的 UI 同步

任一成功写入后：

1. 重新读取 `BrowseService.tags()` 并重建 Tag 选项；
2. 重新执行当前 `BrowserScope` 的列表查询；
3. 若资源仍匹配当前筛选，恢复该资源并重建详情；
4. 若资源因筛选条件不再匹配，显示空详情；
5. 刷新 Tag resource_count 和当前结果总数；
6. 失败时同样从 Query / Browse 层恢复 UI，避免保留被拒绝的乐观状态。

不维护第二份 Tag / Favorite / 用户字段状态。

## 7. 错误处理

写失败在 DetailPanel 内以可读错误反馈呈现，不弹阻塞对话框：

- 服务异常原样显示，至少包含 `写入失败`；
- 名称冲突保留 `标签名已存在`；
- UI 不吞异常后假装成功；
- 写失败后重新读取真实持久状态。

## 8. DoD

1. Favorite 三态与 Tag 筛选进入 `BrowserScope` / `ResourceFilter`；
2. 详情展示 Tag / Favorite；
3. 添加已有、新建、移除 Tag 与 Favorite 切换均经 `TagWriteService`；
4. `display_name` / `notes` 保存与清除、`resource_type` 保存均经
   `ResourceWriteService`；
5. 写入后筛选选项、列表、详情同步；
6. UI 无直接 SQL / SQLite；`core/` 无 PyQt6；
7. `SCHEMA_VERSION == 2`、迁移集合与 16 张业务表不变；
8. 新增 GUI 测试通过；
9. 既有 961 项测试全部回归通过，0 failed / 0 skipped。

## 9. 排除项

- 不新增 Tag 领域功能、字段、表、migration 或 Favorite 第二状态；
- 不修改 `core/database/schema.py`；
- 不修改任何图片、卡片、MOD 文件；
- 不扩展结构化搜索语法；
- 不提供冻结契约外的 `resource_type` 清除/自动值恢复；
- 不执行 commit / push / tag。

