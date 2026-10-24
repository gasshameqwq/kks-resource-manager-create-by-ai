# Phase 3.5.2 — PyQt6 GUI 集成实施日志

> 日期：2026-10-24  
> 状态：实施与测试完成；等待 Git 收尾授权  
> 契约：`docs/phase3/PHASE3_5_2_IMPLEMENTATION_CONTRACT.md`（FROZEN）

## 1. 执行环境

```text
OS: Windows / PowerShell
Python: 3.12.10
pytest: 9.1.1
解释器: .venv\Scripts\python.exe
GUI: PyQt6 / offscreen
```

所有正式测试均使用项目 `.venv`，不使用缺少 `msgpack` / `PyQt6` 的全局解释器。

## 2. 实施内容

### 2.1 FilterBar

在 `ui/filter_bar.py` 新增：

- `tag_combo`：全部 + 各 Tag（显示 resource_count）；
- `favorite_combo`：全部 / 仅收藏 / 非收藏；
- `set_tag_options()`：重建 Tag 选项并保留仍存在的当前 id；
- `tag_id()` / `favorite_filter()` 及测试驱动 setter。

`ui/browser_panel.py` 的 `scope()` 将两值传给既有：

```text
BrowserScope.tag_id
BrowserScope.favorite
  → BrowserScope.to_filter()
  → ResourceFilter.tag_id / favorite
```

没有新增筛选语法或 GUI 端 SQL。

### 2.2 Tag 目录刷新

`BrowserPanel.reload_tag_options()` 只经 `BrowseService.tags()` 读取。
构造时加载；Tag/Favorite/用户字段写入后由 MainWindow 再次刷新，使 resource_count
与当前 Tag 目录保持同步。

### 2.3 DetailPanel

在 `ui/detail_panel.py` 新增：

- 「标签与收藏」区：Tag 列表、已有 Tag 下拉、新 Tag 输入、移除按钮、Favorite 开关；
- 「用户编辑」区：display_name、notes、resource_type；
- 写意图 pyqtSignal，不持有写服务；
- 写入反馈标签与错误样式属性；
- 系统 Tag 不允许通过普通移除按钮取消；
- Favorite 系统 Tag 只由专用收藏开关操作。

详情展示完全消费 MainWindow 传入的 `ResourceDetail`：

```text
tags
is_favorite
resource.display_name
resource.notes
resource.resource_type
resource.type_source
```

### 2.4 MainWindow

在 `ui/main_window.py` 注入或从同一 `BrowseService.conn` 构造：

- `TagWriteService`
- `ResourceWriteService`

信号槽统一执行：

```text
DetailPanel signal
  → MainWindow slot
  → WriteService
  → BrowseService.tags() / page() / detail()
  → Filter options + list + detail 重建
```

构造函数继续兼容既有位置参数，并新增可选：

```python
tag_write_service=None
resource_write_service=None
```

写入成功后刷新全局筛选结果；资源仍匹配时恢复选择，不匹配时清空详情。

### 2.5 resource_type 清除的冻结冲突

Phase 3.1 冻结语义明确：

```text
set_resource_type(resource_id, value)
→ resource_type=value, type_source='user'

NO user → auto fallback API
```

本子阶段禁止修改 `core/`，因此 GUI：

- 提供 `resource_type` 修正保存；
- 不提供伪“清除”；
- 在字段 tooltip 中说明冻结契约不提供恢复自动类型的 API；
- 不直接写 `resources` 表，不猜测 machine type。

这是唯一的任务与上游冻结契约冲突，已显式保留，没有通过危险写入规避。

## 3. 自动化测试

新增 `tests/test_ui_tags.py`，共 21 项，覆盖：

- Favorite 三态和 Tag 下拉；
- Tag / Favorite 单独及 AND 组合筛选；
- `BrowserScope → ResourceFilter` 映射；
- 详情显示 Tag / Favorite；
- 添加已有 Tag、新建并添加、冲突拒绝；
- 移除 Tag 及系统 Tag 保护；
- Favorite 收藏 / 取消收藏；
- 当前 Tag / Favorite 筛选下的结果与详情同步；
- display_name / notes 保存与清除；
- resource_type 修正保存及筛选刷新；
- 服务实例自动构造与外部注入；
- UI 零直接 SQL、core 零 PyQt6 import；
- schema v2 / migration `{1,2}` / 16 表冻结。

### 3.1 针对性测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_tags.py -v
```

结果：

```text
collected 21 items
21 passed in 3.24s
```

外层进程计时 4.66 秒，退出码 0。

### 3.2 GUI 交叉回归

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_tags.py tests/test_gui_filters.py tests/test_gui_detail.py tests/test_gui_smoke.py -q
```

结果：

```text
110 passed in 9.76s
```

### 3.3 只读护栏

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_query_layer.py tests/test_query_model.py tests/test_search_core.py -q -k "read_only or do_not_write or untouch"
```

结果：

```text
8 passed, 149 deselected in 3.57s
```

外层进程计时 5 秒，退出码 0。

### 3.4 全量回归

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

结果：

```text
982 passed in 125.38s (0:02:05)
```

外层进程计时 127.19 秒，退出码 0。

982 = Phase 3.5.1 基线 961 + Phase 3.5.2 新增 21。  
全部 passed，0 failed / 0 skipped。

## 4. 架构合规证据

```text
SCHEMA_VERSION = 2
MIGRATIONS = [1, 2]
BUSINESS_TABLES = 16
```

静态检查：

```text
core 中实际 PyQt6 import：none
ui 中 sqlite3 import / .execute()：none
```

结构测试同时确认：

- UI 数据读取经 `BrowseService`；
- UI 写入经 `TagWriteService` / `ResourceWriteService`；
- core 保持对 GUI 的独立性；
- 没有新增字段、表、DDL、索引或 migration。

## 5. 代码改动统计（文档落笔前）

跟踪文件：

| 文件 | 变更（`git diff --numstat`） | 当前行数 |
| :--- | :--- | ---: |
| `ui/filter_bar.py` | `+52 / -3` | 339 |
| `ui/browser_panel.py` | `+22 / -0` | 446 |
| `ui/detail_panel.py` | `+387 / -2` | 1184 |
| `ui/main_window.py` | `+195 / -3` | 610 |

普通 `git diff --stat`：

```text
4 files changed, 656 insertions(+), 8 deletions(-)
```

新建文件：

| 文件 | 当前行数 |
| :--- | ---: |
| `tests/test_ui_tags.py` | 452 |
| `docs/phase3/PHASE3_5_2_IMPLEMENTATION_CONTRACT.md` | 208 |
| `docs/phase3/PHASE3_5_2_LOG.md` | 251 |

## 6. 未决与边界

除 `resource_type` 清除受 Phase 3.1 冻结契约限制外，无其它功能未决项。

未修改：

- `main.py`
- `core/`
- `core/database/schema.py`
- 任何 DDL / migration / 索引
- 任何图片、角色卡或 MOD 文件

未执行 commit / push / tag。工作区保持未提交状态，等待审核。

