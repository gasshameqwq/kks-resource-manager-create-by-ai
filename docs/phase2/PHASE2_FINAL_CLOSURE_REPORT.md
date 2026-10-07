# Phase 2 Final Closure Report — CLOSED / PASS

> 阶段：**Phase 2.4 — Phase 2 Final Audit**
> 权威契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`（§14 / §15 / §16 / §17 / §18）
> 前序基线：`docs/phase2/PHASE2_1_CLOSURE_REPORT.md`、`PHASE2_2_CLOSURE_REPORT.md`、
> `PHASE2_3_CLOSURE_REPORT.md`（均 = CLOSED / PASS）
> 过程记录：`docs/phase2/PHASE2_4_LOG.md`
> 日期：2026-10-07
> schema：**v2**（保持冻结）· 实测 CPython 3.12.10 · SQLite 3.49.1
> 本报告基于 **Phase 2.4 Final Audit 的实际执行结果**编写，未依据旧报告猜测。

## 结论

```text
Phase 2 — CLOSED / PASS
```

无 P0 / P1。全量 `pytest` **734 passed / 0 failed / 0 skipped**；schema v2 与 model-sync 校验
通过；只读不变量成立；Phase 2 全期 diff 全部落在契约允许范围内（禁止目录零改动）；
Phase 2.4 审计本身**未产生任何功能性变更**。

---

## 1. Phase 2 总体目标

Phase 2 的目标（2.0-C §15.1 / §16）：在 Phase 1 已冻结的 schema v2 与身份模型之上，
为「本地只读资源索引」补齐**内容身份**与**字节重复**两项能力，并**最小、只读、向后兼容**地
暴露给上层；全程不引入无数据源 / 无样本 / 无需求的复杂模型，不做任何文件系统写操作。

Phase 2 的 IN SCOPE（2.0-C §15.1）：

1. **Content Identity（byte）**：扫描重解析时写入 `resources.sha256`（含 C7 读取一致性）。
2. **Byte-Duplicate 能力（派生）**：只读查询「哪些资源字节完全相同」。
3. **Query / CLI / GUI 的最小暴露**（只读、只增）。
4. **回归与验证**（§14 矩阵 + 真实样本只读不变量）。

Phase 2 的 OUT OF SCOPE（2.0-C §15.2，全程冻结）：schema v3、`quick_hash` / `content_key` 清理、
MOD Version 实体 / 多版本共存、MOD→MOD 依赖图、版本约束求解、classification layer、
Tags / Collections、perceptual / semantic duplicate、网络元数据 / 自动下载、游戏安装 / VFS、
AI 分类、自动删除 / 批量文件操作、云同步、File 实体 / 1:N 拆分、通用 Entity/Relation 抽象。

---

## 2. 阶段完成情况（2.0-C → 2.1 → 2.2 → 2.3）

```text
Phase 2.0-C   Architecture & Schema Design      → CLOSED / PASS（tag phase-2.0-closed，93218bd）
Phase 2.1     Content Identity Foundation        → CLOSED / PASS（tag phase-2.1-closed，e76a1c6）
Phase 2.2     Byte-Duplicate Capability          → CLOSED / PASS（tag phase-2.2-closed，8f45a46）
Phase 2.3     Query / CLI / GUI Surfacing        → CLOSED / PASS（tag phase-2.3-closed，518565a）
Phase 2.4     Phase 2 Final Audit                → 本报告（CLOSED / PASS）
```

| 阶段 | 实际交付 | 文件（全期 diff） |
| :--- | :--- | :--- |
| 2.0-C | 架构 / schema 设计契约（只读 + 设计，无功能代码） | `docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`（及 2.0-B 研究） |
| 2.1 | `sha256_of_file()`；Scanner C7 读取窗口；Store 写入 `resources.sha256` | `core/scanner/hashing.py`、`core/scanner/scanner.py`、`core/scanner/store.py`、`core/scanner/__init__.py`、`tests/test_content_identity.py` |
| 2.2 | `ResourceQuery.duplicates()`（派生 `GROUP BY sha256`）；`DuplicateGroup` DTO | `core/query/queries.py`、`core/query/dto.py`、`core/query/__init__.py`、`tests/test_duplicate_query.py` |
| 2.3 | `ResourceSummary.sha256`；`duplicate_group_for()`；`BrowseService` 转发；CLI `query duplicates` + resource JSON `sha256`；GUI 只读展示内容哈希与 byte-duplicate 数 | `core/query/{queries,dto,browse}.py`、`cli_query.py`、`ui/detail_panel.py`、`ui/main_window.py`、`tests/{test_query_surfacing,test_query_cli,test_gui_detail}.py` |

**2.3-D（FilterBar「只看重复项」）明确未实现**，且**不构成 Phase 2.4 的阻塞项**
（用户裁决排除；2.0-C §15.2 无此项）。

---

## 3. Phase 2.4 Final Audit 方法与范围

审计手段（全部只读；仅新增 / 更新 Phase 2.4 审计文档与工作日志）：

1. Preflight（branch / HEAD / tags / working tree / remote）；
2. 全量 `pytest`；
3. `node tools/validate_schema.mjs` + `check_model_sync.mjs` + 运行时 schema 常量核对；
4. 只读不变量核对（样本 sha256 稳定、Query 只读、`duplicate_*` 零写入、
   `_execute_select` 白名单、`quick_hash` / `content_key` 无读写、C7）；
5. Phase 2 全期 Git diff 范围核对；
6. §14 验证矩阵逐项执行；
7. §18.2 结束条件逐项核对；
8. Drift / Known Gap 记录（不修复）。

**未修改**：功能代码 / schema / migration / 数据库 / 依赖 / Scanner / Parser / ResourceStore /
Query / DTO / Model / CLI / GUI / 现有测试 / 既有文档；未删除或重命名文件。

---

## 4. Preflight（基线）

| 项 | 结果 |
| :--- | :--- |
| branch | `main` |
| HEAD full | `518565aabeaab9cc788df7ea4a17176896a91e42` |
| HEAD short | `518565a` |
| `phase-2.0-closed` | ✅ `93218bd` |
| `phase-2.1-closed` | ✅ `e76a1c6` |
| `phase-2.2-closed` | ✅ `8f45a46` |
| `phase-2.3-closed` | ✅ `518565a`（＝ HEAD） |
| working tree | 审计开始时 clean（仅本会话新增未跟踪 `PHASE2_4_LOG.md`） |
| remote | 无 |

结论：审计开始基线正确（HEAD == `phase-2.3-closed`）。

---

## 5. Full Regression

```text
.venv\Scripts\python.exe -m pytest -q -rs
→ 734 passed / 0 failed / 0 skipped   （43.15 s）
```

- passed = **734**；failed = **0**；skipped = **0**；耗时 = **43.15 s**。
- 与 Phase 2.3 基线（734）一致：**无回归、无减少、无削弱**；0 skipped 证明真实样本夹具生效。
- **未修改任何测试。**

补充 focused 证据（合计 133 passed）：

```text
tests/test_content_identity.py   14
tests/test_duplicate_query.py    13
tests/test_query_surfacing.py    17
tests/test_query_cli.py          28
tests/test_gui_detail.py         42
tests/test_gui_smoke.py          19
                                 ── 133 passed
```

---

## 6. Schema / Model Sync

```text
node tools/validate_schema.mjs   → 业务表 16（期望 16）/ 全项 OK / exit 0
node tools/check_model_sync.mjs  → schema ↔ models 一致 / exit 0
```

运行时只读核对（临时空库；未触碰项目库 `data/kks_resource_manager.db`）：

```text
schema_version(meta) = 2
SCHEMA_VERSION = 2 ; MIGRATIONS = [1, 2] ; CURRENT_TABLES = 16
idx_resources_sha256 present = True
RESOURCE_TYPES = 10（character_card, outfit_card, scene_card, mod, skin, eyes, hair, accessory, other, unknown）
```

结论：schema 仍为 **v2**、业务表 **16**、migration 集合 `{1,2}` **未变**、schema ↔ models 一致。

---

## 7. Read-only Invariants（2.0-C §14 / §18.2）

| 不变量 | 证据 | 结果 |
| :--- | :--- | :--- |
| 真实样本 sha256 前后稳定 | `tests/conftest.py::sample_root` 会话前后比对整棵目录 sha256 树；全量 0 skipped 证明生效 | ✅ |
| `ResourceQuery.duplicates()` 只读 | `test_query_performs_no_db_writes`（`conn.total_changes` 不变）；`test_duplicates_goes_through_read_only_guard` | ✅ |
| `duplicate_group_for()` 只读 | `test_browse_duplicates_performs_no_db_writes`；`test_duplicate_group_for_goes_through_read_only_guard` | ✅ |
| `duplicate_*` 不落库 | `test_duplicate_tables_remain_unwritten`（2 处）；全仓无 `INSERT/UPDATE/DELETE duplicate_*` | ✅ |
| `_execute_select` 只允许 SELECT / WITH | 源码护栏（非 `select` / `with` 抛 `ReadOnlyViolation`）；`test_query_layer_has_no_write_statements` | ✅ |
| `quick_hash` / `content_key` 无实际读写 | `core/query` 完全未引用；`test_query_layer_does_not_reference_deprecated_hash_fields` | ✅ |
| 2.1 C7 读取一致性仍成立 | `test_c7_unstable_read_new_file_not_committed`；`test_c7_unstable_read_keeps_existing_row` | ✅ |
| 无新 identity / equivalence / classification / relationship 语义 | 无新表；`current_tables=16`、`RESOURCE_TYPES=10` 不变；`core/classification` 未被触碰 | ✅ |

---

## 8. Phase 2 全范围核对

Phase 2 全期 diff（`93218bd..518565a`）共 **21 个文件**，全部落在契约允许范围：

```text
cli_query.py
core/query/__init__.py · core/query/browse.py · core/query/dto.py · core/query/queries.py
core/scanner/__init__.py · core/scanner/hashing.py · core/scanner/scanner.py · core/scanner/store.py
ui/detail_panel.py · ui/main_window.py
tests/test_content_identity.py · test_duplicate_query.py · test_gui_detail.py ·
      test_query_cli.py · test_query_surfacing.py
docs/phase2/PHASE2_1_* · PHASE2_2_* · PHASE2_3_*
```

| 核对项 | 结论 |
| :--- | :--- |
| 2.1 = Content Identity Foundation | ✅ |
| 2.2 = Byte-Duplicate Capability | ✅ |
| 2.3 = Query / CLI / GUI Surfacing | ✅ |
| 2.3-D FilterBar 未实现且不阻塞 2.4 | ✅ |
| 未偷偷引入 Phase 2.4 新功能 | ✅ |
| schema 未升级到 v3 | ✅（`git log 93218bd..518565a -- core/database/schema.py` 为空） |
| 未新增 duplicate 持久化表 | ✅（业务表仍 16） |
| 未引入 semantic / perceptual duplicate | ✅（无 phash/perceptual/embedding/opencv/ocr/tesseract） |
| 禁止目录零改动（`core/database` / `core/duplicate` / `core/classification` / `main.py`） | ✅ |
| `requirements.txt` 未变 | ✅ |

---

## 9. §14 Verification Matrix

> 逐项执行；每项标记 PASS / FAIL / NOT APPLICABLE。已有 non-blocking 项只记录、不修复。

### 9.1 §14.1 Existing regression

| 检查 | 期望 | 实测 | Status |
| :--- | :--- | :--- | :--- |
| `pytest -q` | 不得回归（≥ 734） | **734 passed / 0 failed / 0 skipped**（43.15 s） | **PASS** |
| `node tools/validate_schema.mjs` | 16 表 / 全项 OK / exit 0 | 16 / 全 OK / exit 0 | **PASS** |
| `node tools/check_model_sync.mjs` | exit 0 | 一致 / exit 0 | **PASS** |
| 真实样本只读不变量 | 前后一致 | 会话夹具生效（0 skipped） | **PASS** |

### 9.2 §14.2 Identity

| 用例 | 期望 | 证据 | Status |
| :--- | :--- | :--- | :--- |
| path change（改名 / 移动） | 新 path key ⇒ 新行；旧行转 missing | 由未改动的 Phase 1 scanner 路径保证（`test_deleted_file_is_marked_missing_not_deleted`、`test_identical_bytes_at_two_paths_are_both_kept`）；无 Phase 2 专用改名用例 | **PASS**（Phase 1 行为，Phase 2 未改） |
| content unchanged（重扫同文件） | 增量跳过；不重算 | `test_unchanged_incremental_does_not_read_or_hash` | **PASS** |
| content changed（同路径改内容） | size/mtime 变 ⇒ 重解析 ⇒ 更新 sha256 | `test_changed_content_recomputes_sha256` | **PASS** |
| same content, different path | 两行、相同 sha256、成组 | `test_two_identical_files_form_one_group` | **PASS** |
| same GUID, different version | 仍 1 个 `mods` 行；version 覆盖为最新 | MOD 侧 Phase 2 未改动（无 schema / store 变更） | **PASS**（不变）/ 无 Phase 2 新用例 |
| same version, different path | 仍 1 个 `mods` 行 | 同上 | **PASS**（不变） |
| duplicate file（真样本） | 派生查询返回该组 | `test_real_sample_byte_duplicate_query` | **PASS** |
| 同大小不同内容 | 不得判为重复 | `test_same_size_different_bytes_not_grouped`（同 size，不同 bytes） | **PASS** |
| 跨格式同角色 | 不得判为重复 | `test_cross_format_same_character_not_grouped` | **PASS** |
| hash 读取一致性（C7） | 窗口内改写 ⇒ 不写库 | `test_c7_unstable_read_new_file_not_committed`、`test_c7_unstable_read_keeps_existing_row` | **PASS** |

### 9.3 §14.3 Scanner

| 用例 | 期望 | 证据 | Status |
| :--- | :--- | :--- | :--- |
| incremental scan | 未变文件跳过、不重算哈希 | `test_unchanged_incremental_does_not_read_or_hash` | **PASS** |
| full scan | 全部重解析并重算；无重复行 | `test_full_scan_recomputes_sha256`、`test_full_mode_reparses_unchanged_files` | **PASS** |
| unchanged file | `files_skipped` 增长 | Phase 1 scan_records 语义（未改） | **PASS**（未改） |
| modified file | `files_changed` 增长；关系重建无残留 | `test_changed_card_relations_are_rebuilt`、`test_author_relations_are_rebuilt_after_change` | **PASS** |
| moved file | 新行 inserted；旧行 missing | 由未改动 Phase 1 路径保证；无 Phase 2 专用用例 | **PASS**（未改） |
| deleted file | 仅标记 missing，不删行 | `test_deleted_file_is_marked_missing_not_deleted` | **PASS** |
| 读取期间文件变化（C7） | 本次不写 hash；扫描继续；无锁 / watcher / retry | C7 两项用例 + 源码核对 | **PASS** |
| 读取一致性不改变增量门 | 未变文件仍按 `(path_key,size,mtime)` 跳过 | C7 实现复用既有增量门 | **PASS** |

### 9.4 §14.4 Read-only

| 用例 | 期望 | 证据 | Status |
| :--- | :--- | :--- | :--- |
| 扫描 / 哈希不修改用户文件 | 样本 sha256 + size + mtime 前后一致 | `conftest.py::sample_root` 会话夹具 | **PASS** |
| 预览缓存写入范围 | 仅 `data/thumbnail_cache/` | `tests/test_thumbnails.py` | **PASS** |
| Query Layer 非 SELECT/WITH | 抛 `ReadOnlyViolation` | `test_query_layer_is_read_only`、`test_sample_query_layer_is_read_only` | **PASS** |

### 9.5 §14.5 Database

| 用例 | 期望 | 实测 | Status |
| :--- | :--- | :--- | :--- |
| v2 → v3 migration | 只应用 v3；数据零丢失 | Phase 2 无 v3 | **NOT APPLICABLE** |
| fresh v3 database | v1→v2→v3；净结构不含被删列 | Phase 2 无 v3 | **NOT APPLICABLE** |
| migration idempotency | 重复运行不报错 | `tests/test_migration_v2.py`（27 passed） | **PASS** |
| constraints | `file_path_key` / `mods.guid` / `authors.name_key` 唯一性生效 | `tools/validate_schema.mjs` + `test_database_schema.py` | **PASS** |
| indexes | `idx_resources_sha256` 存在；被删列索引不存在 | 运行时核对：`idx_resources_sha256` present = True；被删列索引仍存在（无清理） | **PASS**（Phase 2 无清理） |
| Phase 2 期间 schema 冻结 | `SCHEMA_VERSION==2` 且 `MIGRATIONS=={1,2}` 不得变 | 运行时 + 三个 Phase 2 测试文件断言 | **PASS** |

### 9.6 §14.6 Q-V2（验证基线是否足够）

| 项 | 结果 | Status |
| :--- | :--- | :--- |
| 现有套件对内容身份 / 字节重复的缺口已按 2.1 / 2.2 / 2.3 补齐 | ✅ 新增 `test_content_identity.py`(14) / `test_duplicate_query.py`(13) / `test_query_surfacing.py`(17) / `test_query_cli.py`(+10) / `test_gui_detail.py`(+9) | **PASS** |
| 真实样本只读证据 | ✅ 会话夹具 + focused 用例 | **PASS** |
| 残留已知覆盖缺口（非阻塞） | 见 §11（OSError 分支无自动化用例等） | **PASS（带已知缺口）** |

---

## 10. §18.2 Closure Conditions

| 结束条件 | 证据 | 状态 |
| :--- | :--- | :--- |
| 全量回归通过 | 734 passed / 0 failed / 0 skipped（43.15 s） | ✅ |
| schema 校验通过 | `validate_schema.mjs` exit 0（16 表 / 全项 OK） | ✅ |
| model sync 通过 | `check_model_sync.mjs` exit 0（类型清单一致） | ✅ |
| read-only invariants 通过 | §7 全部 ✅（样本稳定 / Query 只读 / `duplicate_*` 零写入 / 白名单 / deprecated 字段无读写 / C7） | ✅ |
| scope conformance 通过 | §8 全期 diff 落在允许范围；禁止目录零改动；无 v3；无新 persists 表 | ✅ |
| 无 P0 / P1 | 审计未发现 | ✅ |
| Phase 2.0 / 2.1 / 2.2 / 2.3 closure 状态完整 | 四个 tag 齐备、四份报告齐备、均 CLOSED / PASS | ✅ |
| Phase 2.4 审计本身没有产生功能性变更 | 新增仅 2 份文档；功能代码 / schema / DB / 依赖 / 测试 / 既有文档零改动 | ✅ |
| schema v2 保持冻结 | `SCHEMA_VERSION==2` / `MIGRATIONS=={1,2}` / 16 表；`schema.py` 全期未改 | ✅ |
| 未补做 2.3-D / 未加 Phase 2.4 新功能 | 无 FilterBar 改动；无新功能 | ✅ |

---

## 11. Drift / Known Gaps（只记录，不修复）

以下为**既有**漂移 / 已知缺口，**不属于 Phase 2.4 修复范围**；经审计判定**均不影响 Phase 2 Closure**。

| # | 项 | 位置 | 是否影响 Closure |
| :-- | :--- | :--- | :--- |
| 1 | 仍写「需要时才计算 sha256 / 大库先算 `quick_hash` 预筛」 | `docs/ARCHITECTURE.md` §5.2 | 否（文档漂移，权威性低于 2.0-C） |
| 2 | 仍把重复检测列为 Phase 4、描述 `duplicate_groups.status='suggested'` | `docs/ARCHITECTURE.md` §7、`README.md` 路线图 | 否 |
| 3 | 快照仍记 `resources.sha256` 为「零写入」 | `PHASE2_0_C_ARCHITECTURE_DESIGN.md` §1.2（历史快照） | 否（2.1 起已改变；历史快照不回溯） |
| 4 | docstring 仍写「Phase 4 实现」并提 `content_key` | `core/duplicate/__init__.py`（空壳，未被调用） | 否 |
| 5 | docstring 仍写「Phase 1 起实现，Phase 3 扩展」 | `core/classification/__init__.py`（空壳 `__all__=[]`，无调用方） | 否 |
| 6 | 历史注释（`sha256 -- 按需计算` / `quick_hash` / `content_key` / `hash_key`） | `core/database/schema.py`（v1/v2 冻结文本） | 否（冻结文本，Phase 2 不得改） |
| 7 | `quick_hash` / `content_key` 字段仍存在于 DDL / `models` | `schema.py`、`core/models/__init__.py` | 否（deprecated / unused；清理属未来独立 schema cleanup 阶段，2.0-C §11.3 / OQ-6） |
| 8 | hash / `stat_after` 的 `OSError` 分支无自动化用例 | `tests/test_content_identity.py`（Phase 2.1 已登记缺口） | 否（实现正确，属覆盖缺口） |

> 说明：Phase 2.1 曾登记的「同 size 不同 bytes 未显式断言」缺口，已在 Phase 2.2 由
> `test_same_size_different_bytes_not_grouped`（同 size、不同 bytes ⇒ 不成组）实际覆盖。

---

## 12. 最终声明

```text
Phase 2.4 = Phase 2 Final Audit：未新增任何功能。
```

- Phase 2.4 只做只读审计与收尾报告 / 日志，**未新增功能**、未改任何功能代码 / schema /
  migration / 数据库 / 依赖 / 测试 / 既有文档；未删除或重命名文件。
- **schema v2 保持冻结**：`SCHEMA_VERSION == 2`、`MIGRATIONS == {1, 2}`、业务表 **16**、
  `MIGRATION_ADDED_COLUMNS` 未变、`core/database/schema.py` 全期未改。
- `duplicate_*` 保持零写入；`quick_hash` / `content_key` 保持 deprecated / unused。
- 唯一合法等价判据仍为 `sha256` 相等（byte-identical）；未引入 semantic / perceptual /
  same-character duplicate，未引入 MOD→MOD 依赖，未引入 classification layer 或 Tags / Collections。

---

## 13. Git / Tag（待用户确认后执行）

```text
branch  main
HEAD    518565a  （tag: phase-2.3-closed）
新增    docs/phase2/PHASE2_4_LOG.md
        docs/phase2/PHASE2_FINAL_CLOSURE_REPORT.md
状态    未 commit、未 tag（等待用户确认）
```

按项目惯例，确认后执行：commit 审计报告 / 日志 → 创建 `phase-2.4-closed` tag →
（如惯例要求）创建 Phase 2 总阶段 tag。**在用户确认前不执行任何 commit / tag。**

---

## 14. 结束条件核对

| 结束条件 | 状态 |
| :--- | :--- |
| Preflight 基线正确 | ✅ |
| 全量回归 734 passed / 0 failed / 0 skipped | ✅ |
| schema / model sync exit 0；v2 / 16 表 / migration 未变 | ✅ |
| read-only invariants 全部成立 | ✅ |
| Phase 2 全范围核对（2.1 / 2.2 / 2.3 + 禁止目录零改动） | ✅ |
| §14 验证矩阵逐项 PASS / NOT APPLICABLE | ✅ |
| §18.2 结束条件全部满足 | ✅ |
| Drift / Known Gap 已记录（不修复） | ✅ |
| Phase 2.4 审计未产生功能性变更 | ✅ |
| 本报告 + `PHASE2_4_LOG.md` 已创建 | ✅ |
| commit / tag | ⏸ 待用户确认 |

```text
Phase 2 — CLOSED / PASS
```

（本阶段到此结束：不进入下一 Phase；commit / tag 待用户确认后再执行。）
