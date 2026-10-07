# Phase 0 验收报告

> 项目：KKS Resource Manager（Koikatsu Sunshine 本地资源管理器）
> 阶段：**Phase 0 — 架构与项目初始化**
> 日期：2026-10-06 · schema `v1`
> 验收执行环境：Windows 11 + **CPython 3.12.10（内置 SQLite 3.49.1）** + Node.js 24.21.0

> 验证状态：**Python 环境已就绪，两条官方验收路径（pytest / main.py）均已实跑通过。**

---

## 1. 结论摘要

**Phase 0 通过验收（全部验收项闭环，无条件通过）。**

| 维度 | 结论 |
| :--- | :--- |
| 架构文档 | 通过 —— `docs/ARCHITECTURE.md` 完整，12 节覆盖分层 / 数据模型 / 决策 / 迁移 / 打包 |
| 项目骨架 | 通过 —— `core/` 8 个子包 + `ui/` + `tests/` + `tools/` + `docs/` 齐全，依赖方向单向 |
| SQLite schema | 通过 —— v1 建成 13/13 业务表，约束 / 索引 / FTS 全部实测生效 |
| 数据模型一致性 | 通过 —— SQL CHECK 清单与 `models.RESOURCE_TYPES` 逐项一致（10/10） |
| 测试 | 通过 —— `pytest -q` **9 passed**（含 FTS 用例，实跑非跳过） |
| 官方 CLI 自检 | 通过 —— `main.py --version / --init-db / --info` 全部 exit 0 |
| License 合规 | 通过 —— `docs/THIRD_PARTY.md` 已建立，三项来源分级处理明确 |

**原唯一阻塞已解除**：本机此前没有可用的 Python 解释器（只有 Microsoft Store 的 0 字节占位符），
现已安装 CPython 3.12.10。`python -m pytest -q` 与 `python main.py` 两条官方验收路径均已实际执行并通过，
证据见 §3.3 / §3.4。Phase 0 全部验收项闭环。

---

## 2. 交付物清单

| 交付物 | 路径 | 状态 | 说明 |
| :--- | :--- | :--- | :--- |
| 架构文档 | `docs/ARCHITECTURE.md` | 完成 | 13.2 KB，Phase 0 核心交付 |
| 第三方许可 | `docs/THIRD_PARTY.md` | 完成（本次补齐） | KKTools / koikatu.js / KKCardModCheck 分级 |
| 项目说明 | `README.md` | 完成（本次补齐） | 快速开始、结构、测试、路线图 |
| 本报告 | `docs/PHASE0_REPORT.md` | 完成（本次补齐） | 验收证据 + Phase 1 进入条件 |
| 版本化 DDL | `core/database/schema.py` | 完成 | 14.3 KB，DDL 内嵌，`SCHEMA_VERSION = 1` |
| 连接 / 迁移 | `core/database/db.py` | 完成 | connect / initialize / 归一化 / FTS 回退 |
| 路径解析 | `core/app_paths.py` | 完成 | 便携式数据目录 + `KKS_RM_DATA_DIR` 覆盖 |
| 领域模型 | `core/models/__init__.py` | 完成 | 5 个 dataclass + 类型常量 |
| 占位包 | `core/{scanner,parsers,mod,thumbnails,duplicate,classification}/` | 完成 | 仅文档字符串，Phase 1+ 填充 |
| GUI 占位 | `ui/main_window.py` | 完成 | 明确 `NotImplementedError`，Phase 1 实现 |
| 验收测试 | `tests/test_database_schema.py` | 通过 | 9 个用例，`pytest -q` → 9 passed |
| 无 Python 校验 | `tools/validate_schema.mjs` | 完成（本次加强） | 新增幂等重跑检查 |
| 模型同步校验 | `tools/check_model_sync.mjs` | 完成（本次新增） | 防 SQL / models 类型清单漂移 |
| 入口 | `main.py` | 通过 | `--init-db` / `--info` / `--version` 三命令实跑 exit 0 |
| 运行时目录 | `data/.gitkeep` | 完成 | DB / 缩略图 / 日志由 `ensure_dirs()` 自动创建 |

---

## 3. 验收证据（实测输出）

### 3.1 schema 结构与约束 —— `node tools/validate_schema.mjs`

```text
DDL 执行：OK
业务表数量：13（期望 13）
FTS5/trigram：已启用
DDL 重复执行（幂等）：OK
未安装 MOD 依赖可记录：OK
外键约束（孤儿 resource_tags）：OK
CHECK 约束（非法 resource_type）：OK
路径唯一约束（大小写归一后重复）：OK
PRAGMA 可设置：OK
FTS 中文子串（3 字 "白峰一"）：OK
FTS 中文子串（2 字 "一乃"）：不命中（符合预期，需 LIKE 回退）
LIKE 回退（2 字 "一乃"）：OK
级联删除（resource_mods）：OK
exit=0
```

该脚本直接从 `core/database/schema.py` 抽取字符串（不是复制 DDL）在真实 SQLite 引擎中执行，
因此「文档里的 DDL」与「实际能跑的 DDL」不会漂移。

关键验证点：

1. **未安装 MOD 依赖可记录** —— `resource_mods` 主键是 `(resource_id, mod_guid)`，
   `mod_id` 可为 NULL。这是「缺失 MOD 提示」功能的根基，实测通过。
2. **路径大小写归一唯一约束** —— `d:/c.png` 与 `D:/C.PNG` 归一后冲突被拒。
3. **FTS5 trigram 的 1–2 字限制** —— 与架构文档 §5.3 的实测结论一致，LIKE 回退确为必需品。

### 3.2 schema 与 models 类型同步 —— `node tools/check_model_sync.mjs`

```text
SQL CHECK 类型（10）：character_card, outfit_card, scene_card, mod, skin, eyes, hair, accessory, other, unknown
RESOURCE_TYPES（10）：character_card, outfit_card, scene_card, mod, skin, eyes, hair, accessory, other, unknown
✅ schema 与 models 类型清单一致
exit=0
```

额外确认了自动识别清单不含 `skin` / `eyes` / `hair` / `accessory`，
即架构文档 §6 的「不确定就不猜」在代码层面没有被悄悄违反。

### 3.3 官方 pytest 验收 —— `python -m pytest -q`

```text
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: <PROJECT_ROOT>
collected 9 items

tests/test_database_schema.py::test_initialize_creates_all_tables PASSED          [ 11%]
tests/test_database_schema.py::test_initialize_is_idempotent PASSED               [ 22%]
tests/test_database_schema.py::test_foreign_keys_enforced PASSED                  [ 33%]
tests/test_database_schema.py::test_resource_type_check_constraint PASSED         [ 44%]
tests/test_database_schema.py::test_file_path_key_is_unique PASSED                [ 55%]
tests/test_database_schema.py::test_mod_dependency_allows_missing_mod PASSED      [ 66%]
tests/test_database_schema.py::test_normalize_path_key_windows_case_insensitive PASSED [ 77%]
tests/test_database_schema.py::test_normalize_name_key PASSED                     [ 88%]
tests/test_database_schema.py::test_fts_search_works_when_enabled PASSED          [100%]

9 passed in 0.13s
```

注意 `test_fts_search_works_when_enabled` 状态是 **PASSED 而不是 SKIPPED** ——
说明 Python 内置 SQLite 3.49.1 确实带 FTS5 + trigram，中日文子串检索在 Python 侧同样成立。

### 3.4 官方 CLI 自检 —— `python main.py`（经解释器完整路径 / venv 执行）

```text
> python main.py --version
0.1.0 (Phase 0 (架构与项目初始化))
exit=0

> python main.py --init-db
数据库已就绪：...\data\kks_resource_manager.db
schema 版本：1
FTS 搜索表：已启用
数据表（13）：app_meta, authors, collections, duplicate_groups, duplicate_members,
              libraries, mods, resource_collections, resource_mods, resource_tags,
              resources, scan_records, tags
exit=0

> python main.py --info
应用版本：0.1.0  |  Phase 0 (架构与项目初始化)
项目根目录：<PROJECT_ROOT>
数据目录：  <DATA_DIR>
数据库：    <DATABASE_FILE>（schema v1）
缩略图缓存：<THUMBNAIL_CACHE_DIR>
日志目录：  <LOG_DIR>
数据表（13）：...（同上）
exit=0
```

**幂等性实测（真实库，非内存库）**：对已存在的 `data/kks_resource_manager.db` 连续执行两次
`--init-db`，两次都 exit 0、schema 仍为 v1、13 张表不变，无重复建表、无报错。

### 3.5 真实数据库内部状态（Python 侧直接读取）

```text
journal_mode = wal              foreign_keys = 1
schema_version = '1'            fts_enabled = '1'      fts_error = ''（无错误）
fts 影子表 = resources_fts, resources_fts_data, resources_fts_idx,
             resources_fts_docsize, resources_fts_config,
             resources_fts_ai, resources_fts_ad, resources_fts_au（3 个触发器齐备）
idx_ 索引数 = 18
归一化示例 = d:/kks/cards/a.png == d:/kks/cards/a.png
```

产物：`data/kks_resource_manager.db`（208 KB）、`data/thumbnail_cache/`、`data/logs/`。
均在 `.gitignore` 覆盖范围内，不会进入版本管理。

### 3.6 双环境复验（系统解释器 与 项目 venv）

同一套验收集在两处执行，结论一致：

| 环境 | 命令 | 结果 |
| :--- | :--- | :--- |
| 系统解释器 | `python -m pytest -q` | 9 passed in 0.13s，exit 0 |
| 项目 venv | `.venv\Scripts\python.exe -m pytest -q` | 9 passed in 0.13s，exit 0 |
| 系统解释器 | `python main.py --info` | 13 张表、schema v1、FTS 已启用，exit 0 |
| 项目 venv | `.venv\Scripts\python.exe main.py --info` | 同上，exit 0 |

venv 关键版本（实测）：

```text
python 3.12.10 | sqlite 3.49.1 | Qt 6.11.0 | msgpack (1, 2, 3) | Pillow 12.3.0
```

### 3.7 无 Python 备用通道（仍然有效，保留作为交叉验证）

```text
node tools/validate_schema.mjs   → exit=0（13/13 表、约束、FTS、幂等全部 OK）
node tools/check_model_sync.mjs  → exit=0（schema 与 models 类型清单一致）
```

两个通道（Python 与 Node）结论完全一致，互为佐证。

---

## 4. 环境说明（原阻塞项，已解除）

### 4.1 现状：就绪（系统解释器 + 项目 venv 双通道）

| 环境 | 路径 | 内容 |
| :--- | :--- | :--- |
| 解释器 | `<SYSTEM_PYTHON_EXECUTABLE>` | Python 3.12.10，内置 SQLite 3.49.1（含 FTS5 + trigram），pip 25.0.1 |
| 项目 venv | `.venv\Scripts\python.exe` | Python 3.12.10（基于同一解释器），已装 `requirements.txt` 全部依赖 + pytest |

venv 内已安装（`pip list` 实测）：

```text
pytest 9.1.1   msgpack 1.2.3   pillow 12.3.0   PyQt6 6.11.0 (Qt 6.11.2, sip 13.13.0)
```

Phase 0 运行时只用标准库 `sqlite3`，本不需要第三方依赖；venv 里的 PyQt6 / msgpack / Pillow
属于 Phase 1 的准备，本次**未使用**（Phase 0 未越界实现 Phase 1 内容）。
顺带确认 `PyQt6` 可正常 import（`Qt 6.11.0`），Phase 1 的 UI 选型在环境层面无风险。

### 4.2 PATH 注意事项（唯一的遗留操作项）

安装后**旧终端不会自动刷新 PATH**：`python` / `python3` 仍然优先解析到
`<WINDOWS_STORE_PYTHON_ALIAS>`（0 字节的 Store 别名存根），
且 `py` 启动器来自 `...\Python\Launcher`。

- 已验证的可用调用方式（推荐用 venv，最短且依赖齐全）：

  ```powershell
  .venv\Scripts\python.exe main.py --info
  .venv\Scripts\python.exe -m pytest -q
  ```

  或使用系统解释器完整路径：
  `& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" ...`
- 新开的终端应当能直接 `python --version`；若不能，到
  「设置 → 应用 → 高级应用设置 → 应用执行别名」关闭 `python.exe` / `python3.exe` 的别名即可。

这不影响 Phase 0 验收结论（已在完整路径下全部跑通），但会影响 Phase 1 的日常开发体验。

### 4.3 环境问题记录（供追溯）

```text
<WINDOWS_STORE_PYTHON_ALIAS>   -> 0 字节，应用执行别名未安装
```

首次验收时 `python` / `python3` 只解析到该 Store 存根，`py` 启动器不存在，
因此当时只能改用项目自带的 Node 通道（§3.7）完成等价验收。
安装 CPython 3.12.10 后，官方路径已补跑通过（§3.3 / §3.4 / §3.5）。

---

## 5. 发现的问题与风险

### P1 —— ✅ 已在 Phase 1.1 修复（详见 docs/phase1/PHASE1_REPORT.md）

**① `initialize()` 每次启动都全量跑 FTS 回填** —— ✅ 已修复
`core/database/db.py:142` 在 `fts_enabled` 为真时无条件调用 `_backfill_fts`
（定义在 `core/database/db.py:168`，SQL 见 `:172-176`）。
该 SQL 是 `WHERE r.id NOT IN (SELECT rowid FROM resources_fts)`，开销随资源量线性增长，
数万行时每次启动都要多扫一遍。
→ 已改为 `if fts_enabled and applied:`，仅当本次真的执行了迁移才回填。
回归测试：`tests/test_fts_backfill.py`（5 个用例）。

**② 连接层是自动提交模式，批量写入会非常慢** —— ✅ 已修复
`core/database/db.py:61` 使用 `isolation_level=None`（autocommit）。
Phase 1 扫描一次可能插入数千行，autocommit 意味着逐行落盘。
→ 已新增 `db.transaction(conn)` 上下文管理器（嵌套安全、异常回滚），
并在 `LibraryStore.add_many` / `remove` 中实际使用；单条操作保持 autocommit。
实测 800 行插入约 4.7× 加速。回归测试：`tests/test_database_transactions.py`（7 个用例）。
**Phase 1.2 的扫描器必须使用该事务批量写入**（约定已写入 ARCHITECTURE.md §5.4）。

### P2 —— Phase 2+ 再处理，但需登记

**③ `table_names()` 的过滤规则过于具体**
`core/database/db.py:78` 用 `"resources_fts" not in n` 排除 FTS 影子表。
Phase 2 若新增 `mods_fts`，该表会被当成业务表返回，直接打破测试里的表数量断言。
→ 建议：改为按 FTS 影子表后缀（`_data` / `_idx` / `_docsize` / `_config`）或显式白名单过滤。

**④ 文档提到但代码中不存在的 `core/search`**
`tests/test_database_schema.py:129` 注释写「见 core/search 的检索策略」，
但项目里没有 `core/search/` 包，检索策略目前只存在于架构文档 §5.3。
→ 建议：Phase 1 建立 `core/search/`（FTS + LIKE 回退的封装），或先修正注释。

**⑤ `duplicate_groups.hash_key` 没有唯一约束**
`core/database/schema.py:210-218` 只建了普通索引，重复检测重跑会累积重复分组。
→ Phase 4 再定：是加唯一约束，还是按 `status` 复用已有分组。

**⑥ `author` 自由文本与 `authors` 表之间没有同步规则**
`resources.author`（原始文本）与 `resources.author_id` 并存，目前无归一 / 回填逻辑。
→ Phase 3 需要明确「先建 authors 行、再回填 author_id」的时机与冲突规则。

### P3 —— 可选改进

- 项目尚未 `git init`。Phase 0 名为「项目初始化」，建议尽快纳入版本管理（`.gitignore` 已就绪）。
- `ARCHITECTURE.md` §3 列出的 `ui/pages/`、`ui/dialogs/`、`ui/widgets/` 目录尚未创建
  （Phase 1 会创建，非缺陷）。
- 缺 `pyproject.toml` / lint 配置；Phase 1 引入依赖时一并补齐更省事。
- `_backfill_fts` 的 `except sqlite3.Error: pass` 会静默吞掉问题，建议写日志。

---

## 6. Phase 1 进入条件（Definition of Ready）

1. 已满足 —— 架构文档、schema v1、数据模型决策已冻结（本报告确认）。
2. 已满足 —— 本机 CPython 3.12.10，`python -m pytest -q` → **9 passed**。
3. 已满足 —— `python main.py --info` 打印出 13 张业务表，FTS 已启用，exit 0。
4. 待决定 —— P1 问题 ① ② 是否在 Phase 1 一并修掉（建议顺手修，成本很低）。
5. 未准备 —— 一个真实的小型测试样本目录（建议 20–50 个文件，含中日文名，
   含至少 1 张角色卡、1 张服装卡、1 个 zipmod），作为 Phase 1 的回归基线。

**Phase 0 的验收条件已全部满足，可以进入 Phase 1**（进入后即可按 §7 的 4 个小步推进）。

---

## 7. Phase 1 建议范围

架构文档 §10 定义 Phase 1 = 「扫描 + KKS/KK 卡片识别 + SQLite + 基础浏览器」。
为避免一次吞下太多，建议拆成 4 个可独立验收的小步：

| 步骤 | 内容 | 验收方式 |
| :--- | :--- | :--- |
| 1.1 Library 管理 | 添加 / 删除扫描根目录，写入 `libraries` 表 | CLI 能列出已添加的 Library |
| 1.2 扫描器 | 递归遍历 + 增量判定（path / size / mtime）写 `resources` | 对样本目录跑一次统计正确；再跑一次应全部 skip |
| 1.3 卡片解析 | PNG 尾部 MessagePack 还原类型 + 名称 + 缩略图 | 断言角色卡 / 服装卡类型与名称；无法判断的落 `needs_review=1` |
| 1.4 基础浏览器 | PyQt6：缩略图网格 + 名称 / 类型 / 路径筛选 + 搜索（FTS + LIKE 回退） | 人工验收；搜索「一乃」「白峰一」都能命中 |

**明确不在 Phase 1 做的事**（防止范围蔓延）：
MOD 索引与依赖（Phase 2）、标签 / Collection / 作者管理（Phase 3）、
重复检测（Phase 4）、任何文件移动 / 删除（Phase 5）。

---

## 8. 供下一步规划直接引用的一段话

> KKS Resource Manager 的 Phase 0 已完成并通过验收：架构文档、项目骨架、SQLite schema v1（13 张业务表）
> 全部就位。CPython 3.12.10 装好后，官方验收路径已实跑通过 —— `pytest -q` 9 passed（含 FTS 用例，
> 实跑非跳过），`main.py --version / --init-db / --info` 全部 exit 0，真实库连续两次 `--init-db`
> 幂等无副作用；WAL、外键、18 个索引、8 个 FTS 对象齐备。SQL 与 Python 模型类型清单一致，
> 自动识别清单未越界（不含 skin/eyes/hair/accessory）。无阻塞项，可以进入 Phase 1。
> 请按 Phase 1 的 4 个小步（Library 管理 -> 扫描器 -> 卡片解析 -> 基础浏览器）逐级推进，
> 并顺手修掉两个 P1 性能点（每次启动全量 FTS 回填、autocommit 导致批量写入慢）。
> 另需注意：旧终端 PATH 仍指向 Microsoft Store 的 python 别名存根，写命令时要用完整路径
> 或先关闭应用执行别名。

