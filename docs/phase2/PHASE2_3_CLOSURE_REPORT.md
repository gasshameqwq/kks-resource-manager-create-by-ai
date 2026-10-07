# Phase 2.3 Final Closure Report — CLOSED / PASS

> 阶段：**Phase 2.3 — Query / CLI / GUI Surfacing**
> 权威契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`（§5.4 / §5.5 / §8 / §13.7 / §14 / §15 / §16 / §18.1）
> 前序基线：`docs/phase2/PHASE2_2_CLOSURE_REPORT.md`（Phase 2.2 = CLOSED / PASS）
> 过程记录：`docs/phase2/PHASE2_3_LOG.md`
> 日期：2026-10-07
> schema：**v2**（未改动）· Python 3.11+ / 实测 CPython 3.12.10 · SQLite 3.49.1
> 本报告基于 **Phase 2.3 Final Closure / Audit 的实际执行结果**编写，未依据旧报告猜测。

## 结论

```text
PHASE 2.3 = CLOSED / PASS
```

无 P0 / P1。全量 `pytest` **734 passed / 0 failed / 0 skipped**；
schema 与 model-sync 校验通过；范围隔离干净（未改 schema / migration / scanner / parser /
hashing / store / database / GUI 之外的任何功能，CLI / Query 改动均为只增只读）。

---

## 1. Scope / Contract

Phase 2.3 的权威定义来自 Phase 2.0-C §16（并与 §15.1 第 3 项一致）：

```text
Phase 2.3 = Query / CLI / GUI Surfacing
          = 把已经存在的 resources.sha256 与派生 byte-duplicate 组
            以最小、只读、向后兼容的方式暴露给上层
```

**明确不做**（本阶段全程冻结）：

- 不创建 Resource-level identity / equivalence 新语义；
- 不做 same-character / semantic / perceptual duplicate；
- 不改变 File ≡ Resource（1:1）与 `file_path_key` Resource identity；
- 不修改 `ResourceQuery.duplicates()` 的分组语义；不新增 duplicate 持久化；
- 不改 schema / migration / database 结构；不改 scanner / parser / hashing / store；
- 不创建 canonical / primary / dismiss / status 等概念；
- 不实现 2.3-D（FilterBar「只看重复项」）——明确不做。

面向用户的文案统一限定为「**字节完全相同**」（byte-identical），不暗示语义等价。

### 1.1 子阶段拆分（用户冻结）

| 子阶段 | 内容 | 状态 |
| :--- | :--- | :--- |
| 2.3-A | Query / DTO Surfacing（`ResourceSummary.sha256` + `BrowseService` 只读转发） | 完成 |
| 2.3-B | CLI Surfacing（`query duplicates` + resource JSON 增 `sha256`） | 完成 |
| 2.3-C | GUI Surfacing（DetailPanel 只读展示内容哈希 + byte-duplicate） | 完成 |
| 2.3-D | FilterBar duplicate filter | **未实现（明确不做）** |

---

## 2. A / B / C 实施摘要

### 2.3-A — Query / DTO Surfacing

- `ResourceSummary` 新增只读派生字段 `sha256: str | None = None`（**带默认值、置于末尾**，既有构造方式不变）；
- `_RESOURCE_SUMMARY_COLUMNS` 增加已有列 `r.sha256`；`_row_to_resource_summary` 同步映射；
- 新增 `ResourceQuery.duplicate_group_for(resource_id) -> DuplicateGroup | None`（只读、经 `_execute_select`，
  语义与 `duplicates()` 严格一致；单例 / `sha256 IS NULL` / 不存在均返回 `None`）；
- `BrowseService` 新增 `duplicates()` / `duplicate_group_for()` 只读转发（无自有 SQL、无自建连接）。
- **`ResourceQuery.duplicates()` 源码与语义未变**（SQL 文本一字未改）。

### 2.3-B — CLI Surfacing

- 新增 `query duplicates`（人类可读 + `--json`）；数据唯一来源 `ResourceQuery.duplicates()`；
- `_resource_obj()` 增 `sha256` 键（**additive only**，`cli_query.py` 该提交 56 行全为新增、0 删除）；
- 新增 `_duplicate_group_obj()` / `_duplicate_group_lines()`；注册到既有 `add_query_parser`（**未修改 `main.py`**）；
- JSON 形态沿用现有 `{count, <list>}` 风格：`{"count": N, "groups": [{"sha256", "member_count", "resources"}]}`；
- 无重复时默认输出沿用既有 `(no results)` 约定，退出码 0。

### 2.3-C — GUI Surfacing

- `ui/detail_panel.py` Basic 区新增「内容哈希」「字节完全相同的资源数」两行；
- 新增 `format_sha256()`（仅显示截断：前 12 位 + `…`）与两个标签常量；
- `_set_form_rows()` 增可选 `tooltips`（默认不启用）；`show_detail()` 增可选
  `duplicate_group` 参数（末尾、带默认值，既有 4 参调用不变）；
- `ui/main_window.py` 在 `_on_resource_selected()` 经**既有 `BrowseService`** 取
  `duplicate_group_for(rid)` 后传入；GUI 数据路径保持 `GUI → BrowseService → Query → DTO`。

---

## 3. Git commits

```text
8f45a46  feat(query): add byte-duplicate capability            （Phase 2.2；tag phase-2.2-closed）
10f2b79  feat(query): expose sha256 and duplicate read model   （Phase 2.3-A）
1b595e6  feat(cli): expose byte-duplicate query                （Phase 2.3-B）
149a0d9  feat(gui): show content hash and byte-duplicate info   （Phase 2.3-C）
0471ea4  docs: record phase 2.3-c commit hash in log           （文档收尾）
<本提交>  docs: close phase 2.3 surfacing                       （Phase 2.3 收尾 + 本报告）
```

- tag `phase-2.3-closed` 指向 **本提交**（Phase 2.3 最终认可的提交）。
- 本阶段全程未创建 remote、未 push。

### 3.1 各提交改动规模（实测）

| commit | 文件 | 规模 |
| :--- | :--- | :--- |
| `10f2b79` | `core/query/{browse,dto,queries}.py`、`tests/test_query_surfacing.py`、`docs/phase2/PHASE2_3_LOG.md` | 5 files, +817 / -2 |
| `1b595e6` | `cli_query.py`、`tests/test_query_cli.py` | 2 files, +236 / 0 |
| `149a0d9` | `ui/detail_panel.py`、`ui/main_window.py`、`tests/test_gui_detail.py`、`docs/phase2/PHASE2_3_LOG.md` | 4 files, +452 / -17 |
| `0471ea4` | `docs/phase2/PHASE2_3_LOG.md` | 1 file, +9 / -3 |

### 3.2 阶段总改动（`git diff 8f45a46 HEAD`）

```text
 cli_query.py                  |  56 ++++
 core/query/browse.py          |  21 ++
 core/query/dto.py             |  10 +-
 core/query/queries.py         |  32 ++-
 docs/phase2/PHASE2_3_LOG.md   | 637 ++++++
 tests/test_gui_detail.py      | 138 ++++-
 tests/test_query_cli.py       | 180 ++++
 tests/test_query_surfacing.py | 335 ++++
 ui/detail_panel.py            |  93 +++-
 ui/main_window.py             |  12 +-
 10 files changed, 1503 insertions(+), 11 deletions(-)
```

范围**严格限定**在这 10 个文件：`core/database`、`core/scanner`、`core/parsers`、
`core/library`、`core/duplicate`、`core/classification` 在 Phase 2.3 期间**零改动**
（`git diff --name-only 8f45a46 HEAD -- <上述路径>` 为空）。

---

## 4. 测试与验证证据

### 4.1 测试数量演进（实测）

| 节点 | 全量通过数 | 增量 |
| :--- | :--- | :--- |
| Phase 2.2 基线 | 698 | — |
| + 2.3-A | 715 | +17（`tests/test_query_surfacing.py`） |
| + 2.3-B | 725 | +10（`tests/test_query_cli.py`） |
| + 2.3-C | **734** | +9（`tests/test_gui_detail.py`） |

### 4.2 最终验证命令与结果

| 验证 | 命令 | 结果 |
| :--- | :--- | :--- |
| 全量回归 | `.venv\Scripts\python.exe -m pytest -q -rs` | **734 passed / 0 failed / 0 skipped**（≈38 s） |
| Query/DTO focused | `pytest tests/test_query_surfacing.py -q` | **17 passed** |
| CLI focused | `pytest tests/test_query_cli.py -q` | **28 passed** |
| GUI focused | `pytest tests/test_gui_detail.py -q` | **42 passed** |
| GUI smoke | `pytest tests/test_gui_smoke.py -q` | **19 passed**（含 `test_ui_does_not_bypass_query_layer`） |
| 2.1 / 2.2 回归 | `pytest tests/test_duplicate_query.py tests/test_content_identity.py -q` | **27 passed**（13 + 14，未修改） |
| Schema | `node tools/validate_schema.mjs` | 16 表 / 全项 OK / **exit 0** |
| Model sync | `node tools/check_model_sync.mjs` | schema ↔ models 一致 / **exit 0** |

### 4.3 真实样本只读不变量

样本目录：`G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike`（**只读使用**，目录存在）。

- 全量套件中 `tests/conftest.py::sample_root` 会话夹具在测试前后比对**整棵目录的 sha256 树**并断言完全一致；
  本次全量运行 **0 skipped**，说明样本夹具确实生效而非被跳过 → **样本未被修改**。
- 定向复核：`test_real_sample_byte_duplicate_query`、`test_real_sample_sha256_matches_bytes`、
  `test_sample_cli_does_not_modify_database` → **3 passed**（含「CLI 查询前后数据库字节一致」）。

---

## 5. schema / migration / model sync

| 检查 | 结果 |
| :--- | :--- |
| `SCHEMA_VERSION` | **2**（未变） |
| `MIGRATIONS` | **{1, 2}**（未变） |
| 业务表数量 | **16**（未变） |
| `MIGRATION_ADDED_COLUMNS` | `{2: (("resources", "card_marker", "TEXT"),)}`（未变） |
| 新增 migration | **无** |
| `core/database/*` 改动 | **无**（Phase 2.3 零改动） |
| `validate_schema.mjs` | exit 0 |
| `check_model_sync.mjs` | exit 0 |

Phase 2.3 只**读取**已有列 `resources.sha256` 与既有索引 `idx_resources_sha256`，不产生任何 DDL。

---

## 6. duplicate 零写入

- 全仓检索：**不存在** `INSERT INTO duplicate_*` / `UPDATE duplicate_*` / `DELETE FROM duplicate_*`；
- `duplicate_groups` / `duplicate_members` 仍为纯预留表（零写入者）；
- 守门测试（本阶段实测通过）：`tests/test_duplicate_query.py::test_duplicate_tables_remain_unwritten`、
  `tests/test_query_surfacing.py::test_duplicate_tables_remain_unwritten`；
- duplicate 能力仍为**只读派生查询**（`GROUP BY sha256`），不落库、无第二真相来源。

---

## 7. GUI architecture guard

| 检查（静态 + 测试） | 结果 |
| :--- | :--- |
| `ui/*` import 行含 `sqlite3` | **无** |
| `ui/*` import 行含 `ResourceQuery` / `LibraryQuery` | **无**（仅既有 docstring 文字提及） |
| `ui/*` 出现 SQL 关键字 / `GROUP BY` | **无** |
| `ui/*` 出现 `hashlib` | **无** |
| `ui/*` 出现 `quick_hash` / `content_key` | **无** |
| `tests/test_gui_smoke.py::test_ui_does_not_bypass_query_layer` | **通过** |
| `tests/test_gui_detail.py::test_gui_has_no_sql_and_no_query_layer_access` | **通过** |
| 数据路径 | `GUI → BrowseService → Query → DTO`（未新增直连路径） |
| 面板行为 | sha256 仅展示已有值；tooltip 为完整 64 位；duplicate 只用「字节完全相同」表述 |

---

## 8. backward compatibility

| 对象 | 结论 |
| :--- | :--- |
| `ResourceSummary` 既有字段 / 构造方式 | 不变（新字段带默认值、置于末尾） |
| `ResourceQuery.duplicates()` 与 `DuplicateGroup` | 源码 / 语义 **未改** |
| 其余 Query 方法签名与返回语义 | 未改 |
| `BrowseService` 既有方法 | 未改（仅新增两个只读转发） |
| CLI 既有命令与 JSON 字段 | **未删除 / 未重命名**；`_resource_obj` 仅新增 `sha256` 键 |
| `DetailPanel` 既有字段 / 访问器 / `basic_rows()` / `show_detail()` 既有参数 | 不变（新参数带默认值） |
| `_set_form_rows()` | 新增可选 `tooltips`，默认行为不变 |
| schema / migration / 数据库结构 | 不变 |

---

## 9. OUT OF SCOPE / 未实现事项

| 项 | 结论 |
| :--- | :--- |
| Resource-level identity / equivalence 新语义 | **未实现**（Phase 2 明确排除） |
| same-character / semantic / perceptual duplicate | **未实现**（NOT DETECTABLE WITH CURRENT EVIDENCE） |
| canonical / primary / dismiss / status | **未实现**（无需求证据；OQ-5） |
| duplicate 持久化（`duplicate_groups` / `duplicate_members` 写入） | **未实现**（继续预留） |
| schema v3 / migration / `quick_hash` / `content_key` 清理 | **未实现**（属未来独立 schema cleanup） |
| **2.3-D FilterBar「只看重复项」** | **未实现（明确不做）** |
| `ui/filter_bar.py` 改动 | **无** |
| Phase 2.4 Final Audit | **未开始** |

---

## 10. 风险与 non-blocking drift

### 10.1 已评估风险

| 风险 | 评估 | 结论 |
| :--- | :--- | :--- |
| `duplicates()` 与新方法共用 `_RESOURCE_SUMMARY_COLUMNS`（新增 `r.sha256` 后其结果集含重复列名） | 实测 `sqlite3.Row` 按名取首列、值相同；13 例既有 duplicate 测试 + 全量回归均通过 | **低 / 已消解**，`duplicates()` SQL 保持一字未改 |
| GUI 每次选中资源多一次 `duplicate_group_for()` 只读查询 | 走 `idx_resources_sha256`，样本规模下开销可忽略 | **低** |
| 把 sha256 误解为语义身份 | 全部用户可见文案限定「字节完全相同」；测试断言该措辞 | **低** |

### 10.2 文档漂移（non-blocking，本阶段只记录、不修改）

以下为**既有**漂移，权威性低于已封存的 Phase 2 契约，**不属于 Phase 2.3 范围**：

| # | 漂移 | 位置 |
| :-- | :--- | :--- |
| 1 | 仍写「需要时才算 sha256」「大库先算 `quick_hash` 预筛」 | `docs/ARCHITECTURE.md` §5.2 |
| 2 | 仍把重复检测列为 Phase 4、描述 `duplicate_groups.status='suggested'` | `docs/ARCHITECTURE.md` §7、`README.md` 路线图 |
| 3 | Phase 2.0-C §1.2 快照仍记 `resources.sha256` 为「零写入」（2.1 起已改变） | `docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md` §1.2 |
| 4 | `core/duplicate/__init__.py` docstring 仍写「Phase 4 实现」并提 `content_key`（空壳模块，未改） | `core/duplicate/__init__.py` |

---

## 11. 结束条件核对

| 结束条件 | 状态 |
| :--- | :--- |
| 2.3-A / 2.3-B / 2.3-C 实施 + 验证 + 独立提交 | ✅ |
| 全量 `pytest` 734 passed / 0 failed / 0 skipped | ✅ |
| `validate_schema.mjs` / `check_model_sync.mjs` exit 0 | ✅ |
| `SCHEMA_VERSION == 2` / `MIGRATIONS == {1,2}` / 16 表 / 无 migration | ✅ |
| `duplicate_*` 零写入 | ✅ |
| 无 schema / migration / scanner / parser / hashing / store 改动 | ✅ |
| 无 Resource-level identity / equivalence 新语义 | ✅ |
| 无 canonical / primary / dismiss / status | ✅ |
| `ResourceSummary.sha256` additive 且默认值兼容 | ✅ |
| `query duplicates` 只读；既有 CLI JSON 字段未删改 | ✅ |
| GUI 不绕过 Query Layer（无 sqlite3 / SQL / hashlib / ResourceQuery） | ✅ |
| 真实样本只读不变量成立 | ✅ |
| 未实现 2.3-D（FilterBar） | ✅ |
| 创建 Closure Report | ✅（本文件） |
| 创建 `phase-2.3-closed` tag | ✅（指向本收尾提交） |

---

## 12. 最终结论

```text
PHASE 2.3 = CLOSED / PASS
```

Phase 2.3 在严格只读、只增、向后兼容的前提下，把既有的 `sha256` 与 byte-duplicate 能力
完整暴露到 Query / CLI / GUI，范围未越界、语义未膨胀、schema 未变动；
测试、schema 校验、模型同步与真实样本只读不变量全部通过。

（本阶段到此结束：不进入 Phase 2.4；不实现 2.3-D。）
