# Phase 3.5.1 — 实施日志

> 日期：2026-10-24  
> 状态：实施与测试完成；等待 G-3 Git 收尾授权  
> 契约：`docs/phase3/PHASE3_5_1_IMPLEMENTATION_CONTRACT.md`（FROZEN）

## 1. 执行环境

```text
OS: Windows / PowerShell
Python: 3.12.10
pytest: 9.1.1
解释器: .venv\Scripts\python.exe
```

系统 Python 缺少项目依赖 `msgpack` 与 `PyQt6`；首次用全局 `pytest` 收集时出现
31 个 import errors。随后确认 `.venv` 含 `msgpack 1.2.3`、`PyQt6` 与
`pytest 9.1.1`，本阶段全部有效测试均使用 `.venv` 执行。

## 2. 实施内容

### 2.1 Tag CLI

在 `main.py` 新增：

- `tag create`
- `tag list`
- `tag rename`
- `tag delete`

实现要点：

- `tag list` 只经 `TagQuery.list()`，显示 id / name / color / category / system；
- rename / delete 先按 id、再按精确 `name_key` 解析 target；
- create / rename 的冲突与保留名完全交给 `TagWriteService` 判定；
- delete / rename 系统 Favorite 时由服务异常映射为 stderr + exit 1；
- CLI 不复制归一化、冲突或事务逻辑。

### 2.2 Resource Tag / Favorite 写入口

在既有 `resource` 命令族新增：

- `resource add-tag`
- `resource remove-tag`
- `resource favorite`
- `resource unfavorite`

实现要点：

- resource 目标使用既有 `ResourceQuery.resolve()` 只读解析；
- tag 名称使用 `TagQuery.find_by_name()` 精确解析；
- assign / unassign 与 favorite 全部经 `TagWriteService`；
- 不新增 Favorite 持久化字段，不写 `resources` 表；
- `add-tag` / `remove-tag` / `favorite` / `unfavorite` 均保持服务层幂等。

### 2.3 Eager Bootstrap

`main.py::_bootstrap_system_tags()` 在有效 CLI 启动、命令分发之前执行：

```text
database.initialize()
→ database.connect()
→ TagWriteService(conn).ensure_system_tags()
→ conn.close()
```

异常在 CLI 边界转为：

```text
系统标签初始化失败：<原因>
exit 1
```

该引导不新增 DDL，不修改 schema，只通过 Phase 3.2 的权威服务 seam 幂等 seed
Favorite。

### 2.4 新增测试

新增 `tests/test_cli_tags.py`，共收集 18 项，覆盖：

- 启动时 Favorite 引导及幂等；
- 八个命令成功路径；
- 重命名冲突、保留名、系统标签保护；
- 资源 / Tag 不存在时的 stderr 与 exit 1；
- 重复打标、去标、收藏、取消收藏；
- CLI 无直接 Tag 写 SQL；
- schema v2、迁移集合与 16 表冻结。

## 3. 测试结果

### 3.1 基线收集

```powershell
.\.venv\Scripts\python.exe -m pytest --collect-only -q
```

结果：

```text
943 tests collected in 1.78s
```

### 3.2 针对性测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_tags.py -v
```

结果：

```text
collected 18 items
18 passed in 4.81s
```

### 3.3 既有 CLI / ownership 交叉回归

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_library_cli.py tests/test_cli_resource_write.py tests/test_query_cli.py tests/test_ownership_guard.py -q
```

结果：

```text
70 passed in 13.42s
```

### 3.4 只读护栏

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_query_layer.py tests/test_query_model.py tests/test_search_core.py -q -k "read_only or do_not_write or untouch"
```

结果：

```text
........                                                                 [100%]
8 passed, 149 deselected in 1.84s
```

进程外层计时为 2.29 秒。

### 3.5 全量回归

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

结果：

```text
961 passed in 89.34s (0:01:29)
```

外层进程计时为 89.91 秒，退出码 0。

961 = 既有基线 943 + 新增 18；全部 passed，无 failed / skipped。

## 4. 代码改动统计（文档落笔前）

已修改文件：

| 文件 | 变更 | 当前行数（PowerShell 行记录） |
| :--- | :--- | ---: |
| `main.py` | `+292 / -1`（`git diff --numstat`） | 804 |

已新建文件：

| 文件 | 当前行数（PowerShell 行记录） |
| :--- | ---: |
| `tests/test_cli_tags.py` | 283 |
| `docs/phase3/PHASE3_5_1_IMPLEMENTATION_CONTRACT.md` | 172 |
| `docs/phase3/PHASE3_5_1_LOG.md` | 204 |

`git diff --stat`（仅跟踪文件）：

```text
 main.py | 293 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 292 insertions(+), 1 deletion(-)
```

新建文件尚未被 Git 跟踪，因此不计入普通 `git diff --stat`；这正是未 staging 的
预期状态。

## 5. 边界核验

- `core/database/schema.py` 未修改：`SCHEMA_VERSION = 2`；
- `MIGRATIONS == {1, 2}`，业务表 16 张；
- `ui/` 未修改；
- 未新增 migration、DDL 或索引；
- `main.py` 未 import `sqlite3`，未包含 `tags` / `resource_tags` 写 SQL；
- 未修改任何图片、角色卡或 MOD；
- 未扩展结构化文本查询语法；
- 未执行 commit / push / tag 操作。

## 6. 异常与未决

仅有一个环境异常：全局 Python 缺 `msgpack` / `PyQt6`，首次收集产生 31 个 import
errors。项目 `.venv` 依赖完整，所有正式验证在该环境通过，因此不构成代码回归或
未决功能问题。

当前无功能未决项。按用户要求，Git 工作区保持未提交状态，等待审核与 G-3
收尾授权。

