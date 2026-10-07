# Phase 1 报告（1.1 已完成）

> 项目：KKS Resource Manager
> 本次范围：**Phase 1 步骤 1.1 —— Library 管理** + Phase 0 遗留的两个 P1 修复
> 版本：`0.2.0` · `Phase 1.1 (Library 管理)` · schema 仍为 `v1`（无需迁移）
> 日期：2026-10-06 · 环境：CPython 3.12.10（`.venv`）/ SQLite 3.49.1

---

## 1. 结论

**1.1 完成并通过验收：53 passed（Phase 0 的 9 个用例全部未受影响）。**

| 项 | 结果 |
| :--- | :--- |
| Library 增 / 删 / 改 / 查 | ✅ `core/library/store.py` |
| CLI 子命令 | ✅ `library list/add/remove/enable/disable`，退出码语义明确 |
| P1 ①：FTS 回填不再无条件执行 | ✅ 仅在真正执行迁移时回填 |
| P1 ②：批量写入事务能力 | ✅ `db.transaction()`，实测 4.7× 加速 |
| 测试 | ✅ 53 passed（新增 44 个） |
| 旧功能回归 | ✅ Phase 0 的 9 个 schema 用例全绿 |
| **Scanner** | ❌ **按要求未实现**，`core/scanner/` 仍是占位 |

schema **没有改动**（`SCHEMA_VERSION` 仍为 1）：`libraries` 表在 Phase 0 就已建好，
1.1 只是开始使用它。因此本次不涉及数据库迁移。

---

## 2. 交付物

| 文件 | 类型 | 说明 |
| :--- | :--- | :--- |
| `core/library/__init__.py` | 新增 | 包入口，导出 store 与异常 |
| `core/library/store.py` | 新增 | `LibraryStore` + 4 个异常 + 2 个报告 dataclass |
| `core/database/db.py` | 修改 | 新增 `transaction()`；FTS 回填加 `applied` 门控 |
| `main.py` | 修改 | 新增 `library` 子命令；`--info` 显示 Library 数量 |
| `core/__init__.py` | 修改 | 版本 `0.1.0 → 0.2.0`，阶段改为 `Phase 1.1` |
| `tests/test_library_store.py` | 新增 | 20 个用例（含「绝不删文件」护栏） |
| `tests/test_library_cli.py` | 新增 | 10 个用例（CLI 端到端） |
| `tests/test_database_transactions.py` | 新增 | 7 个用例（P1 ②） |
| `tests/test_fts_backfill.py` | 新增 | 5 个用例（P1 ①） |
| `docs/ARCHITECTURE.md` | 修改 | 目录树、§5.4 写入事务、§10 路线图 1.1 |
| `README.md` | 修改 | 快速开始加 library 用法、结构、状态 |
| `docs/PHASE0_REPORT.md` | 修改 | 两个 P1 标记为已修复 |

---

## 3. 两个 P1 修复

### ① FTS 存量回填不再每次启动都跑

**问题**：`initialize()` 只要 `fts_enabled` 为真就无条件调用 `_backfill_fts`，
而它要跑 `WHERE r.id NOT IN (SELECT rowid FROM resources_fts)` 的全量比对。
绝大多数启动不执行任何迁移，于是每次都白扫一遍 `resources`。

**修复**（`core/database/db.py`）：

```python
if fts_enabled and applied:      # applied = 本次实际应用的迁移列表
    _backfill_fts(conn)
```

新库首建、老库升级到启用 FTS 的版本时 `applied` 都非空 → 该回填的时机一个没少；
之后的增量由 FTS 触发器负责。

**回归测试**：`tests/test_fts_backfill.py`

- 首建 → 回填 1 次
- 再启动（无迁移）→ 不再回填
- FTS 被标记为不可用 → 不尝试回填
- 老库执行新迁移 → 重新回填
- 触发器路径：新插入的行无需回填即可被 FTS 搜到（中日文实测）

### ② 批量写入事务能力

**问题**：连接是 autocommit（`isolation_level=None`），批量写入逐行落盘。

**修复**（`core/database/db.py`）：

```python
with db.transaction(conn):
    for row in rows:
        conn.execute("INSERT ...", row)
```

语义已测死：正常结束提交、抛异常整体回滚、嵌套复用外层不提前提交、
未提交数据对其他连接不可见、事务外仍是 autocommit。

**实测加速**（800 行写入 + FTS 触发器）：

```text
autocommit 800 行 :     98.3 ms
事务内     800 行 :     21.1 ms
加速比            :      4.7 x
```

**在 1.1 中已实际使用**：`LibraryStore.add_many()`（多目录整批原子写入，失败全回滚）、
`LibraryStore.remove()`。**Phase 1.2 的扫描器必须沿用这一约定**
（已写入 ARCHITECTURE.md §5.4，性能冒烟测试会拦住退回逐行提交的改动）。

---

## 4. Library 功能设计要点

`LibraryStore` 只写 `libraries` 表，**完全不遍历目录**（那是 1.2）。

| 方法 | 行为 |
| :--- | :--- |
| `add()` | 归一化路径 → 校验目录存在 → 拒绝重复 → 默认用文件夹名 |
| `add_many()` | 一条事务内批量添加，任一条失败整批回滚 |
| `find_by_path()` / `resolve()` | 大小写与分隔符无关地按路径查找；`resolve` 同时接受 id |
| `list_all(include_disabled=)` | 按名称排序，可只看启用的 |
| `update()` / `set_enabled()` | 局部更新，只改传入字段 |
| `stats()` | 该 Library 下的资源数 / 待确认 / 缺失（只读查询，不扫盘） |
| `preview_removal()` / `remove()` | 删除前先给出影响预览 |

**安全设计**（对应「文件位置与分类分离」「默认只读」两条硬性约束）：

- 添加 Library 只往数据库写一行，目录内容与文件**完全不读不写**。
- 删除 Library 只删数据库记录：资源行保留、`library_id` 置空，扫描记录级联删除，
  **用户的目录与文件毫发无损**。
- 有专门的护栏测试 `test_store_never_deletes_files`：走完增删改流程后，
  用 `sample.read_bytes()` 断言文件内容一字不变。
- CLI 的 `library remove` **必须加 `--yes`**，否则只打印影响预览并以退出码 1 结束。

---

## 5. CLI 实测

```text
> python main.py --version
0.2.0 (Phase 1.1 (Library 管理))

> python main.py library add <TEMP>\kks_demo_cards <TEMP>\kks_demo_mods
已添加 Library [1]（启用）：kks_demo_cards
  根目录：C:\Users\...\Temp\kks_demo_cards
已添加 Library [2]（启用）：kks_demo_mods
  根目录：C:\Users\...\Temp\kks_demo_mods

> python main.py library add <同一个目录>            # 重复添加
添加失败：该目录已添加过（已存在 id=1）：C:\Users\...\kks_demo_cards   [exit=1]

> python main.py library list
已添加 Library（2）：
  [1] kks_demo_cards  （启用）
        根目录：C:\Users\...\Temp\kks_demo_cards
        资源：0（待确认 0，缺失 0）    上次扫描：从未
  [2] kks_demo_mods  （暂停）
        ...

> python main.py library remove 1                    # 无 --yes → 只预览
将要删除 Library [1]：kks_demo_cards
  根目录：C:\Users\...\Temp\kks_demo_cards
  影响：0 条资源解除关联（资源与文件都保留），0 条扫描记录被删除
  目录和文件不会被删除。确认请加 --yes 重新执行。      [exit=1]

> python main.py library remove 1 --yes
已删除 Library [1]：kks_demo_cards
  已解除关联资源：0（文件未改动）
  已删除扫描记录：0

> python main.py --info
应用版本：0.2.0  |  Phase 1.1 (Library 管理)
...（13 张业务表）
已添加 Library（0）：用 `python main.py library add <目录>` 添加
```

演示结束后用 `Test-Path` 确认两个演示目录**依然存在** —— 整个增删流程没有触碰文件系统。
（演示目录位于 `%TEMP%`，清理时被策略拦下未删除，是空文件夹，无影响。）

---

## 6. 测试结果

```text
53 passed in 1.19s
```

| 测试文件 | 数量 | 覆盖 |
| :--- | :--- | :--- |
| `test_database_schema.py` | 9 | Phase 0 回归（未改动，全绿） |
| `test_library_store.py` | 20 | 增删改查、路径归一化、去重、原子批量、统计、删除不删文件 |
| `test_library_cli.py` | 10 | 子命令退出码与输出、重定向数据目录、失败回滚 |
| `test_database_transactions.py` | 7 | P1 ② 事务语义 + 性能冒烟 |
| `test_fts_backfill.py` | 5 | P1 ① 回填门控 + 触发器路径 |

CLI 测试通过 `KKS_RM_DATA_DIR` 把数据目录重定向到临时目录，不会污染项目 `data/`。

---

## 7. 明确未做的事（防止范围蔓延）

- ❌ **Scanner（1.2）**：没有任何目录遍历、文件枚举、增量判定代码。
  `core/scanner/` 仍只有文档字符串。
- ❌ **卡片解析 / 缩略图（1.3）**：`core/parsers/`、`core/thumbnails/` 未动。
- ❌ **UI（1.4）**：`ui/main_window.py` 仍是占位。
- ❌ **schema 变更**：`SCHEMA_VERSION` 仍为 1，没有新增迁移。
- ❌ **未安装 / 未使用 PyQt6 等 Phase 1.3+ 依赖**（venv 里已装但本次代码未 import）。

---

## 8. 已知问题 / 下一步建议

### 遗留（不阻塞 1.2）

| 级别 | 问题 | 位置 |
| :--- | :--- | :--- |
| P2 | `table_names()` 用 `"resources_fts" not in n` 过滤影子表，Phase 2 加 `mods_fts` 会漏 | `core/database/db.py:78` |
| P2 | 测试注释引用的 `core/search` 包仍不存在 | `tests/test_database_schema.py:129` |
| P3 | 未 `git init`；`ui/pages|dialogs|widgets` 未建；无 `pyproject.toml` | — |

### Phase 1.2（扫描器）进入条件

1. ✅ 1.1 完成、53 passed。
2. ⬜ 准备一个**真实样本目录**（20–50 个文件，含中日文名，至少 1 张角色卡、
   1 张服装卡、1 个 zipmod），作为扫描的回归基线。
3. ⬜ 确定增量判定的口径：`(file_path_key, file_size, modified_time)` 三者一致即 skip。
4. ⬜ 明确扫描范围规则：收录哪些扩展名（`.png` / `.zipmod` / `.zip` …），
   是否忽略隐藏目录与 `_reference/`。

### Phase 1.2 必须遵守的既有约定

- **批量写入包在 `db.transaction(conn)` 里**（§5.4 + 性能冒烟测试护栏）。
- 扫描**只读**：不改名、不移动、不删除用户文件。
- 无法可靠判定的类型一律落 `unknown` + `needs_review=1`，不要猜。
- 增量扫描要写 `scan_records`（`files_seen/new/changed/skipped/missing/failed`）。
- 首次扫描**不要**默认计算全量 SHA256；需要时先算 `quick_hash` 预筛。

---

## 9. 供下一步规划直接引用的一段话

> KKS Resource Manager 的 Phase 1.1（Library 管理）已完成并通过验收，`pytest` 53 passed，
> Phase 0 的 9 个 schema 用例未受影响。新增 `core/library/store.py`（libraries 表 CRUD，
> 只碰数据库、绝不遍历目录或改动文件）与 `main.py library list/add/remove/enable/disable` 子命令；
> 删除 Library 只解绑资源、不删文件，且 CLI 必须 `--yes` 确认。同时修掉了 Phase 0 的两个 P1：
> FTS 存量回填改为只在真正执行迁移时运行，新增 `db.transaction()` 批量写入事务
> （实测 800 行 4.7× 加速，已成为扫描器必须遵守的约定）。schema 未变，仍是 v1。
> Scanner 按要求未实现。下一步是 Phase 1.2：递归遍历 + 增量判定（path/size/mtime）
> 写入 `resources`，必须使用 `db.transaction` 批量写入、只读、无法判定落 unknown + needs_review。
> 开工前建议先准备 20–50 个文件的真实样本目录（含中日文名、角色卡、服装卡、zipmod）作为回归基线。
