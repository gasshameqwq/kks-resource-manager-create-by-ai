# Phase 2.4 Work Log — Baseline / Scope Review

> 性质：**工作日志（过程记录）**，不是冻结契约，也不是正式 Phase 报告。
> 阶段：**Phase 2.4**（契约定义见 §1 = **Phase 2 Final Audit**）。
> 本次记录范围：**Phase 2.4 Baseline / Scope Review（只读审计）**。
> 日期：2026-10-07
> 权威契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`（尤其 §14 / §15 / §16 / §17 / §18）
> 前序基线：`docs/phase2/PHASE2_3_CLOSURE_REPORT.md`（Phase 2.3 = CLOSED / PASS）
> schema：**v2**（未改动）· 实测 CPython 3.12.10 · SQLite 3.49.1
> 状态：**本次 = 只读 Baseline / Scope Review，已完成**；未修改任何功能代码 / schema /
> migration / 数据库 / 依赖 / CLI / GUI / 测试 / 既有文档；未删除或重命名文件；
> 未 commit / tag / push。本文件是本会话**唯一新增文件**。

---

## 0. 本日志的用途

记录进入 Phase 2.4 之前对**契约、仓库实际状态、Phase 2.1/2.2/2.3 基线**的只读核对结论，
供下一步（确认 2.4 读法 → 实施 / 审计 → 收尾）参考。
本文件**不改变**任何 Phase 1 / 2.0 / 2.1 / 2.2 / 2.3 已封存文档的结论，也不构成新的契约。

**维护约定**：本次对话后续的每一步（经用户确认的动作）都追加到本文件，不新建平行日志。
本文件始终是**过程日志**：不构成冻结契约，也不代替将来的正式 Phase Closure Report。

---

## 1. 阶段与权威契约：Phase 2.4 = Phase 2 Final Audit

全仓检索确认：Phase 2.4 的**唯一正式定义**来自 `PHASE2_0_C_ARCHITECTURE_DESIGN.md` §16
的冻结路线图，原文为：

```text
Phase 2.0-C   Architecture & Schema Design      ← CLOSED / PASS
      ↓
Phase 2.1     Content Identity Foundation        ← CLOSED / PASS（sha256 写入）
      ↓
Phase 2.2     Byte-Duplicate Capability          ← CLOSED / PASS（只读派生查询）
      ↓
Phase 2.3     Query / CLI / GUI Surfacing        ← CLOSED / PASS（暴露 sha256 与重复组）
      ↓
Phase 2.4     Phase 2 Final Audit
              （回归 + 只读不变量 + 范围核对 + 收尾报告）
```

§16 对照表进一步写明：`Phase 2 Final Audit | 保留为 2.4 | 与 Phase 1 的验收纪律一致`。
同一定义在 `PHASE2_2_LOG.md` @36 与 `PHASE2_3_LOG.md` @41 被重复引用。

**关键结论**：按仓库正式契约，**Phase 2.4 = Phase 2 Final Audit（最终审计 / 收尾），
不是一个新功能实现阶段**。全仓**不存在**独立的 Phase 2.4 设计 / 契约文档。
这一点与本次任务 §3 / §4 中"Phase 2.4 是否需要 schema change / migration / 新增 Query /
新增 Model / Scanner / CLI / GUI"的提问预设不同，已在 §10 标注为最高优先级歧义。

---

## 2. 本次任务性质（只读）

本次为**只读 Baseline / Scope Review**，全程未执行任何写操作。允许的动作仅限：
`git status/log/tag/remote/rev-parse`、文件读取、`rg` 检索、运行测试与 Node 校验脚本。

**明确未做**：不修改任何功能代码 / schema / migration / 数据库 / 依赖 / CLI / GUI / 测试 /
既有文档；不删除或重命名文件；不创建功能文件；不 commit / tag / push；不创建 remote。

---

## 3. 只读审查范围

**文档**：

- `docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`（全文 1135 行）
- `docs/phase2/PHASE2_1_{LOG,CLOSURE_REPORT}.md`、`PHASE2_2_{LOG,CLOSURE_REPORT}.md`、
  `PHASE2_3_{LOG,CLOSURE_REPORT}.md`
- `docs/PHASE2_0_A_BASELINE_REVIEW.md`、`docs/phase2/PHASE2_0_B_RESEARCH.md`（标题 / 结构核对）
- `docs/phase1/PHASE1_FINAL_REPORT.md`（Phase 1 验收纪律模板）
- `docs/ARCHITECTURE.md`、`README.md`（漂移核对）

**代码**：

- `core/database/{schema,db}.py`
- `core/query/{queries,dto,browse,__init__}.py`
- `core/scanner/{scanner,store,hashing}.py`
- `core/duplicate/__init__.py`、`core/classification/__init__.py`（确认仍为 docstring 空壳）
- `cli_query.py`、`ui/{detail_panel,main_window,browser_panel,library_panel,resource_model}.py`

**测试**：`tests/` 全量（27+ 文件）+ `tools/validate_schema.mjs` / `tools/check_model_sync.mjs`。

核对方法：**以实际代码 / 实测结果为准**，不依据文件名或报告转述猜测设计。

---

## 4. 基线证据（只读，实测）

| 检查 | 命令 / 方式 | 结果 |
| :--- | :--- | :--- |
| branch | `git rev-parse --abbrev-ref HEAD` | `main` |
| HEAD | `git rev-parse HEAD` | `518565aabeaab9cc788df7ea4a17176896a91e42`（short `518565a`） |
| 工作区 | `git status` | **clean**（无改动、无未跟踪文件） |
| 历史 | `git log --oneline --decorate` | 见下方 §4.1 |
| tag | `git tag -n` | `phase-2.0-closed` / `phase-2.1-closed` / `phase-2.2-closed` / `phase-2.3-closed` |
| remote | `git remote -v` | 空（无 remote） |
| 全量回归 | `.venv\Scripts\python.exe -m pytest -q -rs` | **734 passed / 0 failed / 0 skipped**（47.91 s） |
| schema 校验 | `node tools/validate_schema.mjs` | 业务表 **16**（期望 16）/ 全项 OK / **exit 0** |
| model sync | `node tools/check_model_sync.mjs` | schema ↔ models 一致 / **exit 0** |
| schema 版本 | `core/database/schema.py` | `SCHEMA_VERSION == 2`；`MIGRATIONS == {1, 2}`；`MIGRATION_ADDED_COLUMNS == {2: (("resources","card_marker","TEXT"),)}` |

### 4.1 relevant commits

```text
518565a (HEAD, tag: phase-2.3-closed) docs: close phase 2.3 surfacing
0471ea4                               docs: record phase 2.3-c commit hash in log
149a0d9                               feat(gui): show content hash and byte-duplicate info   (2.3-C)
1b595e6                               feat(cli): expose byte-duplicate query                 (2.3-B)
10f2b79                               feat(query): expose sha256 and duplicate read model    (2.3-A)
8f45a46 (tag: phase-2.2-closed)       feat(query): add byte-duplicate capability
e76a1c6 (tag: phase-2.1-closed)       feat: close phase 2.1 content identity foundation
93218bd (tag: phase-2.0-closed)       docs: close phase 2.0 design baseline
5987a0f                               chore: close phase 1 baseline
```

与任务给定基线对照：Phase 2.2 commit `8f45a46…`、Phase 2.3 commit `518565a…` **一致**。

---

## 5. Contract 摘要：Phase 2.4 Contract

以下直接取自 2.0-C §16（唯一正式定义），并按"审计阶段"性质补齐 2.0-C 与 Phase 1 验收纪律。
凡契约未明写者，已在 §10 标注为歧义。

| 维度 | 契约内容 | 依据 |
| :--- | :--- | :--- |
| **Goal** | Phase 2 Final Audit：对 Phase 2（2.0-C / 2.1 / 2.2 / 2.3）做最终审计与收尾 | 2.0-C §16 + 对照表 |
| **Scope** | ① 回归；② 只读不变量；③ 范围核对；④ 收尾报告 | 2.0-C §16 |
| **Inputs** | 2.0-C 契约；2.1 / 2.2 / 2.3 报告 + 日志；仓库实际代码；测试；真实样本；§14 矩阵；§18.2 结束条件 | 2.0-C §14 / §18.2 |
| **Outputs** | Phase 2 收尾 / 审计报告（含日志）+ Phase 2 总阶段结论 | 2.0-C §16；Phase 1 验收纪律 |
| **Allowed Changes** | **仅新增文档**（审计报告 / 工作日志）；不改任何功能文件 | Phase 1 审计先例（只读、未改功能代码） |
| **Forbidden Changes** | 功能代码 / schema / migration / 数据库 / 依赖 / CLI / GUI / 测试 / 既有文档的任何修改；文件删除或改名；任何越界新功能 | 2.0-C §15.2 OUT OF SCOPE 全表 |
| **Required Tests** | 全量 `pytest`（`>= 734`，不得回归）；`validate_schema.mjs` exit 0；`check_model_sync.mjs` exit 0；真实样本只读不变量；`duplicate_*` 零写入；schema 冻结断言 | 2.0-C §14.1 / §14.6 / §18.2 |
| **Acceptance Criteria** | §18.2 结束条件逐项 ✅；§14 验证矩阵通过；无 P0 / P1；各阶段标签完整；范围隔离成立 | 2.0-C §18.2；Phase 1 §10 模式 |

---

## 6. Phase 2 Existing Baseline（实际提供的能力）

### 6.1 Phase 2.1 — Content Identity Foundation（CLOSED / PASS）

- 新增 `core/scanner/hashing.py::sha256_of_file()`（流式 1 MiB，只读，不吞 `OSError`）。
- `core/scanner/scanner.py::_process_file()` 增加 **C7 读取一致性窗口**：
  `stat_before → parse → sha256 → stat_after`；窗口内 `(size, mtime)` 变化 ⇒ 本次解析结果与 hash
  **整体不提交**（沿用既有 changed / 失败语义，无锁 / 无 watcher / 无重试）。
- `core/scanner/store.py` 的 `upsert_card_resource` / `upsert_mod_resource` 增加 `sha256: str`
  （required kw-only），INSERT / UPDATE 均写 `resources.sha256`。
- 增量门 `(file_path_key, file_size, modified_time)` 不变；hash 当且仅当 (re)parse。
- **零 schema 变更**（沿用 v1 已有列 + `idx_resources_sha256`）。

### 6.2 Phase 2.2 — Byte-Duplicate Capability（CLOSED / PASS）

- `core/query/queries.py::ResourceQuery.duplicates() -> list[DuplicateGroup]`，
  核心 SQL 为 `GROUP BY sha256 + HAVING count(*) >= 2`，经 `_execute_select` 只读护栏。
- `core/query/dto.py::DuplicateGroup`（`frozen` 不可变；`sha256` + `tuple[ResourceSummary, ...]`
  + `member_count` 派生属性），并从 `core/query/__init__.py` 导出。
- **不落库**：`duplicate_groups` / `duplicate_members` 保持零写入（有守门测试）。
- 语义边界：`sha256` 相等**只**表示 byte-identical；`sha256 IS NULL` 与单例排除；
  组按 `sha256` 升序、组内按 `resources.id` 升序。

### 6.3 Phase 2.3 — Query / CLI / GUI Surfacing（CLOSED / PASS）

- **2.3-A**：`ResourceSummary.sha256: str | None = None`（末尾、带默认值）；
  `_RESOURCE_SUMMARY_COLUMNS` 增 `r.sha256`；新增 `ResourceQuery.duplicate_group_for(resource_id)`；
  `BrowseService.duplicates()` / `duplicate_group_for()` 只读转发。`duplicates()` SQL **一字未改**。
- **2.3-B**：CLI 新增 `query duplicates [--json]`；`_resource_obj` **只增** `sha256` 键；
  未改 `main.py`。
- **2.3-C**：GUI `DetailPanel` Basic 区只读展示「内容哈希」（前 12 位 + `…`，tooltip 全 64 位）
  与「字节完全相同的资源数」；数据经 `BrowseService.duplicate_group_for()`；
  `ui/*` 无 `sqlite3` / `ResourceQuery` 导入 / SQL / `hashlib`。
- **2.3-D（FilterBar「只看重复项」）明确未实现**（用户裁决的可选项，未授权）。

---

## 7. Phase 2.3 → Phase 2.4 Boundary

**Phase 2.3 已完成什么**：把 Phase 2.1 写入的 `sha256` 与 Phase 2.2 的派生 byte-duplicate 组，
以只读、只增、向后兼容的方式**暴露**到 Query / DTO、CLI、GUI；未新增任何 identity /
equivalence / classification / relationship 语义；未改 `duplicates()` 语义；未落库重复组；
已创建 closure report + `phase-2.3-closed` tag；2.3-D 明确不做；2.3 closure 明写
「**Phase 2.4 Final Audit：未开始**」。

**Phase 2.3 留给 Phase 2.4 的正式接口 / 能力**：2.3 **没有留下待实现的构建接口**
（它本身是 surfacing 的终点）。它留给 Phase 2.4 的是**待审计的验证面**：

```text
resources.sha256（2.1 写入，C7 读取一致性）
ResourceQuery.duplicates() / ResourceQuery.duplicate_group_for()      （2.2 / 2.3-A）
DuplicateGroup DTO                                                     （2.2）
ResourceSummary.sha256（末尾、带默认值）                               （2.3-A）
BrowseService.duplicates() / duplicate_group_for()                     （2.3-A）
CLI: query duplicates [--json]；resource JSON 增 sha256                （2.3-B）
GUI: DetailPanel「内容哈希」「字节完全相同的资源数」                    （2.3-C）
```

**Phase 2.4 从哪里开始**：从 §5 的审计动作开始 —— 以只读方式核对"2.1 + 2.2 + 2.3 实现是否与
2.0-C 契约一致"，跑 §14 验证矩阵与 §18.2 结束条件，判无 P0 / P1，然后**产出 Phase 2 收尾报告**。
不新增功能、不改 schema / migration / Query / Model / Scanner / Store / CLI / GUI。

### 7.1 任务 §3 的 11 个问题（逐项回答）

| # | 问题 | 契约下的回答 |
| :-- | :--- | :--- |
| 1 | Phase 2.3 到底完成了什么？ | 只读 surfacing（Query/DTO + CLI + GUI）；2.3-D 未做；见 §6.3 |
| 2 | Phase 2.3 留给 2.4 的正式接口 / 能力？ | 无"待构建接口"；留下的是 §7 的**待审计验证面**与已登记 non-blocking 残留 |
| 3 | Phase 2.4 建立在哪些现有能力之上？ | 全部 Phase 2 能力（sha256 写入 + 派生重复查询 + surfacing）作为被审计对象 |
| 4 | 是否需要 schema change？ | **否**（Phase 2 全程 `SCHEMA_VERSION == 2`；2.4 = 审计） |
| 5 | 是否需要 migration？ | **否**（`MIGRATIONS == {1, 2}` 冻结） |
| 6 | 是否需要新增 Query？ | **否**（2.4 不新增 Query；仅验证既有 Query） |
| 7 | 是否需要修改现有 Query？ | **否**（`duplicates()` / `ResourceSummary` / `BrowseService` 均冻结） |
| 8 | 是否需要新增 Model / DTO？ | **否**（`DuplicateGroup` / `ResourceSummary.sha256` 已在 2.2 / 2.3 完成） |
| 9 | 是否涉及 Scanner / Parser / ResourceStore？ | **否**（只做只读核对与回归；不改） |
| 10 | 是否涉及 CLI / GUI？ | **否**（只做只读核对与回归；不改） |
| 11 | 明确属于 Phase 2.4 之外？ | 所有新功能与 schema v3 / `quick_hash`·`content_key` 清理 / 语义·感知重复 / 分类层 / Tags·Collections / MOD→MOD 依赖 / 删除·合并 / AI / OCR / 感知哈希 / 作者识别（2.0-C §15.2 + 任务 §4）；以及 2.3-D FilterBar |

---

## 8. Repository vs Contract Audit

| Area | Contract | Current Reality | Status |
| :--- | :--- | :--- | :--- |
| Phase 2 总体目标（身份 & 字节重复） | 2.0-C §15.1 / §16 | 已按 2.1 → 2.2 → 2.3 落地 | MATCH |
| Content Identity 定义 | Content = `resources.sha256`（byte-identical，非实体） | `dto.py` 明确；无 Content 表 / 实体 | MATCH |
| sha256 写入（2.1） | 与解析同频；C7 读取一致性 | `scanner.py` C7 窗口 + `hashing.py` + `store.py` 均实现 | MATCH |
| Byte-duplicate（2.2） | derived `GROUP BY sha256`；不落库 | `ResourceQuery.duplicates()` 实现；无写入者 | MATCH |
| Surfacing（2.3） | Query / CLI / GUI 最小只读暴露 | DTO / CLI / GUI 均已实现且 additive | MATCH |
| 2.3-D FilterBar | 可选、未授权 | 未实现 | MATCH（按设计） |
| schema | Phase 2 保持 v2 | `SCHEMA_VERSION==2`、16 表、`MIGRATIONS=={1,2}` | MATCH |
| duplicate_* 零写入 | D2：保持未写 | 全仓无 INSERT/UPDATE/DELETE；守门测试通过 | MATCH |
| `quick_hash` / `content_key` | C5：deprecated / unused | 代码内无读写；仅存于冻结 DDL、`models` 字段、测试断言、`tools/inspect_card.py`（独立工具，与本列无关） | MATCH（含文档漂移，见 §10-4） |
| Query 只读护栏 | 仅 SELECT / WITH | `_execute_select` 仅放行 `select` / `with` | MATCH |
| GUI 边界 | 不得绕过 Query Layer | `ui/*` 无 `sqlite3` / `ResourceQuery` 导入 / SQL / `hashlib`；守卫测试通过 | MATCH |
| ResourceSummary 兼容性 | 既有字段 / 构造不变 | `sha256` 置末尾带默认值 | MATCH |
| 真实样本只读不变量 | 样本 sha256 前后一致 | `conftest.py::sample_root` 会话夹具生效（0 skipped） | MATCH |
| **Phase 2.4 定义** | 2.0-C §16：Phase 2 Final Audit | 仅路线图一行；**无独立 Phase 2.4 设计 / 契约文档** | **GAP**（见 §10-1） |
| 文档一致性 | 2.0-C 为权威 | `ARCHITECTURE.md` / `README.md` / `core/duplicate` / `core/classification` / `schema.py` 注释 / `PHASE2_0_C` §1.2 快照存在**既有漂移** | **DRIFT（non-blocking，§10-4）** |

**结论**：未发现实现层面的 mismatch（代码与 2.0-C 契约在功能语义上一致）；
存在的两处问题均为"契约覆盖（无 2.4 设计文档）"或"既有文档漂移"，不属功能不一致。

---

## 9. Proposed Implementation Surface

契约明确允许 Phase 2.4 触碰的**仅**为审计产物（文档），**不含任何功能文件 / 模块**：

- 允许（新增，审计阶段）：一份 Phase 2 收尾 / 审计报告 + 对应工作日志
  （沿用命名惯例，例如 `docs/phase2/PHASE2_4_*.md` / `PHASE2_FINAL_*.md`，最终命名待定）。
- **不允许任何功能性改动**：`core/**`、`cli_query.py`、`main.py`、`ui/**`、`tests/**`、
  `core/database/schema.py`、`tools/**`、`requirements.txt`，以及既有文档。

---

## 10. Risks / Ambiguities

1. **【最高优先级】契约把 Phase 2.4 定义为审计，而任务预设它像实现阶段。**
   2.0-C §16 明确 `Phase 2.4 = Phase 2 Final Audit`，**不存在**把 2.4 定义为"新功能实现"的
   仓库契约。若继续按"2.4 = 实现"推进，将缺少权威依据（scope creep 风险）。
   **需在实现前由用户确认 2.4 的读法**：(a) 按契约执行 Final Audit，或
   (b) 另行立项一个"Phase 2.4 实现"并先补设计契约。
2. **"生成日志"与"只读不改"的冲突（本次已裁决）。**
   任务首行要求"记得生成日志"，但同一任务反复强调"只读 / 不修改任何文件 / 不修改工作区状态"。
   两者不可同时满足。**用户随后明确授权生成日志**，故本次仅**新增本文件**
   `docs/phase2/PHASE2_4_LOG.md`，未触碰任何功能代码与既有文件。
3. **2.3-D（FilterBar「只看重复项」）未实现** —— 已由用户明确排除；**不属于** Phase 2.4
   （2.4 = 审计），也不属于 2.0-C §15.2 的任何 IN SCOPE 项。若认为 2.4 应补 2.3-D，
   需要新的授权与契约，当前无依据。
4. **既有文档漂移（non-blocking，只记录、不修改）**：
   - `docs/ARCHITECTURE.md` §5.2 仍写"需要时才算 sha256 / 大库先算 `quick_hash` 预筛"；
     §7 仍把重复检测列为 Phase 4 并描述 `duplicate_groups.status='suggested'`；
   - `README.md` 路线图同上；
   - 2.0-C §1.2 快照仍记 `resources.sha256` 为"零写入"（2.1 起已改变）；
   - `core/duplicate/__init__.py` docstring 仍写"Phase 4 实现"并引用 `content_key`；
     `core/classification/__init__.py` 仍为 docstring 空壳（`__all__=[]`，无调用方）；
   - `core/database/schema.py` v1 注释仍写 `sha256 -- 全量哈希（按需计算，不做首次扫描默认项）`、
     `quick_hash` / `content_key` 注释（**v1 冻结文本，Phase 2 不得改**）；
     `core/models/__init__.py` 仍定义 `quick_hash` / `content_key` 字段。
   这些均为**既有**漂移，权威性低于 2.0-C，属审计应"记录但不修复"的项。
5. **Phase 2.1 已登记的两项测试覆盖缺口**（不阻塞）：同 size 不同 bytes 未显式断言；
   hash / `stat_after` 的 `OSError` 分支无自动化用例。2.4 审计应复核其"仍为已知、未修复"。
6. **契约措辞小差异（非阻塞）**：§15.1 第 3 项把"Query / CLI / GUI 最小暴露"列为**整阶段**
   IN SCOPE，而 §16 把它拆到 2.3；各阶段报告已统一采用 §16 读法（2.3 closure §1 记明）。

---

## 11. Final Recommendation

按仓库正式契约，Phase 2.4 = Phase 2 Final Audit；当前仓库状态健康、与 2.0-C 契约在功能语义上
一致、回归全绿（734 passed）、schema 与 model-sync 校验通过、工作区 clean。

```text
READY FOR PHASE 2.4 IMPLEMENTATION
```

其中"IMPLEMENTATION"的含义**严格按契约**为：执行 Phase 2 最终审计 + 产出收尾报告。
**不包含任何功能实现。**

条件性结论（必须留意）：

```text
若将 Phase 2.4 理解为"新功能实现阶段" → BLOCKED — CONTRACT / BASELINE ISSUE
（原因：仓库中不存在把 2.4 定义为实现阶段的权威契约；需先立项并补设计契约）
```

### 11.1 建议的实施顺序（只读审计版；本次未执行）

1. **Preflight**：确认 HEAD / tags / working tree clean；复核 2.0-C 与 2.1–2.3 报告一致性。
2. **Regression**：全量 `pytest -q`（须 `>= 734`、0 failed）；`validate_schema.mjs`、
   `check_model_sync.mjs` exit 0。
3. **Read-only invariants**：真实样本目录 sha256 前后一致；`duplicate_*` 零写入；
   `quick_hash` / `content_key` 无读写；Query 仅 SELECT/WITH。
4. **Scope verification**：核对 Phase 2 全期 diff 只落在契约允许文件，
   其余目录零改动。
5. **Contract conformance**：逐项对照 §14 验证矩阵与 §18.2 结束条件；列出 drift / P2
   （只记录，不修复）。
6. **Closure**：写 Phase 2 收尾报告 + 工作日志 →（按 2.3 先例）打 `phase-2.4-closed` /
   Phase 2 总标签。

---

## 12. 只读合规声明

| 约束 | 状态 |
| :--- | :--- |
| 未修改任何功能代码 | ✅ |
| 未修改 schema / migration / 数据库 | ✅ |
| 未修改依赖 | ✅ |
| 未修改 CLI / GUI | ✅ |
| 未修改测试 | ✅ |
| 未修改既有文档 | ✅ |
| 未删除或重命名文件 | ✅ |
| 未创建功能文件 | ✅（仅新增本文档） |
| 未 commit / tag / push | ✅ |

---

## 13. Git 状态（记录本文档时）

```text
branch  main
HEAD    518565a  （tag: phase-2.3-closed）
tags    phase-2.0-closed · phase-2.1-closed · phase-2.2-closed · phase-2.3-closed
status  ?? docs/phase2/PHASE2_4_LOG.md   （本会话唯一新增文件；未 commit、未 tag）
```

---

## 14. 后续维护约定

1. 本次对话**后续每一步**都追加到本文件，不新建平行日志。
2. 每条记录固定包含：范围冻结 / 变更清单 / 关键决策 / 验证证据 / Git 状态。
3. 本文件始终是**过程日志**：不构成冻结契约，也不代替将来的正式 Phase Closure Report。
4. 记录只陈述实际执行与实测结果；未执行的检查明确标注"未执行"。

---

## 15. 相关文件

- 契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`
- 前序基线：`docs/phase2/PHASE2_1_CLOSURE_REPORT.md`、`PHASE2_2_CLOSURE_REPORT.md`、
  `PHASE2_3_CLOSURE_REPORT.md`
- 前序日志：`docs/phase2/PHASE2_1_LOG.md`、`PHASE2_2_LOG.md`、`PHASE2_3_LOG.md`
- 相关代码：`core/scanner/{hashing,scanner,store}.py`、`core/query/{queries,dto,browse}.py`、
  `cli_query.py`、`ui/{detail_panel,main_window}.py`
- 相关测试：`tests/{test_content_identity,test_duplicate_query,test_query_surfacing,test_query_cli,test_gui_detail}.py`

---

## 16. Final Audit 实施记录（Phase 2.4 — Phase 2 Final Audit）

> 范围：本次**正式执行 Phase 2.4 = Phase 2 Final Audit**（只读审计 + 收尾报告）。
> 依据：2.0-C §14 / §15 / §16 / §17 / §18 + §1–§15 的 Baseline / Scope Review 结论。
> **本阶段不是新功能开发**；未修改任何功能代码 / schema / migration / 数据库 / 依赖 /
> Scanner / Parser / ResourceStore / Query / DTO / Model / CLI / GUI / 现有测试 / 既有文档；
> 未删除或重命名文件。新增文档：本日志 + `docs/phase2/PHASE2_FINAL_CLOSURE_REPORT.md`。
> Git 收尾（commit / tag）**待用户确认**后执行（见 §16.10）。

### 16.1 Preflight（基线核对）

| 项 | 结果 |
| :--- | :--- |
| branch | `main` |
| HEAD full | `518565aabeaab9cc788df7ea4a17176896a91e42` |
| HEAD short | `518565a` |
| `phase-2.0-closed` | ✅ 存在 → `93218bd`（docs: close phase 2.0 design baseline） |
| `phase-2.1-closed` | ✅ 存在 → `e76a1c6`（feat: close phase 2.1 content identity foundation） |
| `phase-2.2-closed` | ✅ 存在 → `8f45a46`（feat(query): add byte-duplicate capability） |
| `phase-2.3-closed` | ✅ 存在 → `518565a`（docs: close phase 2.3 surfacing）＝ HEAD |
| working tree | 审计开始时 **clean**（仅本会话新增未跟踪 `docs/phase2/PHASE2_4_LOG.md`） |
| remote | **无**（`git remote -v` 为空） |

结论：审计开始基线正确（HEAD == `phase-2.3-closed`）。

### 16.2 Full Regression

```text
.venv\Scripts\python.exe -m pytest -q -rs
→ 734 passed / 0 failed / 0 skipped   （43.15 s）
```

- passed = **734**；failed = **0**；skipped = **0**；耗时 = **43.15 s**。
- 0 skipped 说明真实样本夹具确实生效（而非被跳过）。
- **未修改任何测试**；734 = Phase 2.3 基线数，无回归、无减少。

### 16.3 Schema / Model Sync

```text
node tools/validate_schema.mjs   → 业务表 16（期望 16）/ 全项 OK / exit 0
node tools/check_model_sync.mjs  → schema ↔ models 一致 / exit 0
```

运行时只读核对（临时空库，未触碰项目库）：

```text
schema_version(meta) = 2
SCHEMA_VERSION = 2 ; MIGRATIONS = [1, 2] ; CURRENT_TABLES = 16
idx_resources_sha256 present = True
```

结论：schema 仍为 **v2**、业务表仍为 **16**、migration 集合 `{1,2}` **未变**、
schema ↔ models 一致，两个校验均 exit 0。

### 16.4 Read-only invariants

| 不变量 | 证据 | 结果 |
| :--- | :--- | :--- |
| 真实样本 sha256 前后稳定 | `conftest.py::sample_root` 会话前后比对整棵目录 sha256 树并断言一致；全量 0 skipped 证明其生效 | ✅ |
| `ResourceQuery.duplicates()` 只读 | `test_query_performs_no_db_writes`（`total_changes` 不变）；`test_duplicates_goes_through_read_only_guard`（只发 SELECT/WITH） | ✅ |
| `duplicate_group_for()` 只读 | `test_browse_duplicates_performs_no_db_writes`；`test_duplicate_group_for_goes_through_read_only_guard` | ✅ |
| `duplicate_*` 不落库 | `test_duplicate_tables_remain_unwritten`（两处）；全仓无 `INSERT/UPDATE/DELETE duplicate_*` | ✅ |
| `_execute_select` 只允许 SELECT/WITH | 源码 `queries.py::_execute_select`：非 `select` / `with` 抛 `ReadOnlyViolation`；`test_query_layer_has_no_write_statements` | ✅ |
| `quick_hash` / `content_key` 无实际读写 | `core/query` 完全未引用（`test_query_layer_does_not_reference_deprecated_hash_fields`）；其余仅见于冻结 DDL / `models` 字段 / 独立工具 | ✅ |
| 2.1 C7 读取一致性仍成立 | `test_c7_unstable_read_new_file_not_committed`；`test_c7_unstable_read_keeps_existing_row` | ✅ |
| 无新 identity / equivalence / classification / relationship 语义 | 全期 diff 只落在 scanner/query/cli/ui + tests + docs；无新表；`RESOURCE_TYPES`（10）/ `CURRENT_TABLES`（16）不变；`core/classification` 未被触碰 | ✅ |

### 16.5 Phase 2 全范围核对（Git diff）

```text
2.1  (93218bd → e76a1c6)
  core/scanner/__init__.py · core/scanner/hashing.py · core/scanner/scanner.py · core/scanner/store.py
  tests/test_content_identity.py · docs/phase2/PHASE2_1_*
2.2  (e76a1c6 → 8f45a46)
  core/query/__init__.py · core/query/dto.py · core/query/queries.py
  tests/test_duplicate_query.py · docs/phase2/PHASE2_2_*
2.3  (8f45a46 → 518565a)
  cli_query.py · core/query/browse.py · core/query/dto.py · core/query/queries.py
  ui/detail_panel.py · ui/main_window.py
  tests/test_gui_detail.py · tests/test_query_cli.py · tests/test_query_surfacing.py · docs/phase2/PHASE2_3_*
```

| 核对项 | 结论 |
| :--- | :--- |
| 2.1 = Content Identity Foundation | ✅（scanner/hashing/store + identity 测试） |
| 2.2 = Byte-Duplicate Capability | ✅（query/dto/queries + duplicate 测试） |
| 2.3 = Query / CLI / GUI Surfacing | ✅（query/cli/ui + surfacing 测试） |
| 2.3-D FilterBar 未实现 | ✅ 未实现；**不构成 2.4 阻塞项**（用户明确排除、契约 §15.2 无此项） |
| 未偷偷引入 Phase 2.4 新功能 | ✅ 全期 diff 仅上述文件；scope-creep 关键词扫描无实现（仅"不做相似性推断"的否定陈述） |
| schema 未升级到 v3 | ✅ `SCHEMA_VERSION==2`；`git log 93218bd..518565a -- core/database/schema.py` 为空 |
| 未新增 duplicate 持久化表 | ✅ 业务表仍 16；`duplicate_*` 零写入 |
| 未引入 semantic / perceptual duplicate | ✅ 无 phash/perceptual/embedding/opencv/ocr/tesseract；`requirements.txt` 未变 |
| 禁止目录零改动 | ✅ `core/database`、`core/duplicate`、`core/classification`、`main.py` 全期 diff 为空 |

### 16.6 §14 Verification Matrix

见正式报告 `docs/phase2/PHASE2_FINAL_CLOSURE_REPORT.md` §9（逐项 PASS / FAIL / NOT APPLICABLE）。

### 16.7 §18.2 Closure Conditions

见正式报告 §10。全部满足。

### 16.8 Drift / Known Gaps（只记录，不修复）

见正式报告 §11（README / ARCHITECTURE 漂移、2.0-C §1.2 快照、`core/duplicate` /
`core/classification` docstring、schema.py 历史注释、`quick_hash` / `content_key` 遗留、
Phase 2.1 已知覆盖缺口）。**均不影响 Phase 2 Closure。**

### 16.9 审计结论

```text
Phase 2 — CLOSED / PASS
```

无 P0 / P1；§14 矩阵全部 PASS 或 NOT APPLICABLE；§18.2 结束条件全部满足。
Phase 2.4 审计本身**未产生任何功能性变更**；schema v2 **保持冻结**。

### 16.10 Git 状态（记录本记录时）

```text
branch  main
HEAD    518565a  （tag: phase-2.3-closed）
tags    phase-2.0-closed · phase-2.1-closed · phase-2.2-closed · phase-2.3-closed
status  ?? docs/phase2/PHASE2_4_LOG.md
        ?? docs/phase2/PHASE2_FINAL_CLOSURE_REPORT.md
        （本阶段新增文档；**未 commit、未 tag**）
```

> Git 收尾（commit 审计报告 / 日志 + 创建 `phase-2.4-closed` tag，并按惯例创建
> Phase 2 总阶段 tag）**待用户确认后执行**，本记录写作时尚未执行。
