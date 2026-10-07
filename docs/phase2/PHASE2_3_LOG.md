# Phase 2.3 Work Log — Query / CLI / GUI Surfacing

> 性质：**工作日志（过程记录）**，不是冻结契约，也不是正式 Phase 报告。
> 日期：2026-10-07
> 权威契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`（§5.4 / §5.5 / §8 / §13.7 / §14 / §15 / §16 / §18.1）
> 前序基线：`docs/phase2/PHASE2_2_CLOSURE_REPORT.md`（Phase 2.2 = CLOSED / PASS）
> 阶段定义（2.0-C §16）：**Phase 2.3 = Query / CLI / GUI Surfacing**
> 状态：**只读审查完成 → 用户确认范围 → Phase 2.3-A 实施完成并通过验证**；
> 已实现 Query / DTO Surfacing 与 BrowseService 只读转发；未进入 2.3-B（CLI）/ 2.3-C（GUI）/
> 2.3-D（FilterBar）；未创建 Phase 2.3 Closure Report。

---

## 0. 本日志的用途

记录进入 Phase 2.3 之前的**只读架构审查与实施规划**结论，供下一步
（确认范围 → 冻结决策 → 实现 → 验证 → 收尾）参考。
本文件**不改变**任何 Phase 1 / 2.0 / 2.1 / 2.2 已封存文档的结论，也不构成新的契约。

---

## 1. 阶段与权威契约

Phase 2.3 的**唯一权威定义**来自 Phase 2.0-C §16 的修订路线图：

```text
Phase 2.0-C   Architecture & Schema Design      ← CLOSED / PASS
      ↓
Phase 2.1     Content Identity Foundation       ← CLOSED / PASS（sha256 写入）
      ↓
Phase 2.2     Byte-Duplicate Capability          ← CLOSED / PASS（只读派生查询）
      ↓
Phase 2.3     Query / CLI / GUI Surfacing        ← 本次规划（把 sha256 与重复组暴露给用户）
      ↓
Phase 2.4     Phase 2 Final Audit                （后续，不提前做）
```

与 §15.1 第 3 项（「Query / CLI / GUI 的最小暴露」列为 Phase 2 IN SCOPE）**本质一致**：
整阶段把 surfacing 列为范围，§16 把它拆到 2.3。Phase 2.2 的 closure / log 同样记录
「surfacing 属 Phase 2.3」。**仓库内不存在独立的 Phase 2.3 设计文档。**

---

## 2. 关键结论：Phase 2.3 是「暴露」，不是「新建语义」

进入本阶段前的任务叙述曾提出「在 Content Identity / Byte Duplicate 之上建立更高层的
Resource-level identity / equivalence / duplicate semantics」。**该叙述与权威契约不一致**，
且被 2.0-C 明确排除在 Phase 2 之外：

| 契约条款 | 内容 |
| :--- | :--- |
| §8.1 / §8.2 | 三类重复中，**same character / logical resource = NOT DETECTABLE WITH CURRENT EVIDENCE**，明确排除 |
| §13.7 **D4** | 「Same character / same logical resource is **not computed in Phase 2**」 |
| §15.2 OUT OF SCOPE | `perceptual / semantic duplicate` = 不做 |
| §18.1 #1 / #3 | File ≡ Resource（1:1）；Content 是派生值、**不是实体** |
| §17.3 **OQ-4** | 「同角色重导出 / 跨格式相似提示」仅在出现真实需求时重开 |
| §5.5 | `ResourceSummary` 暴露 `sha256` 属**可选**，留给后续阶段实现 |

因此本次冻结读法为：

```text
Phase 2.3 = 把「已存在的 sha256」与「已存在的派生 byte-duplicate 组」
            以最小改动暴露到 Query / CLI / GUI；
            不新增任何 identity / equivalence / classification / relationship 语义。
```

**未经用户确认，不实现语义级 Resource 等价**（那需要一次新的设计评审，触发条件见
2.0-C §4.2 / §4.3 / §17.3，不属于 Phase 2.3）。

---

## 3. 本次只读审查范围

**文档**：

- `docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`（全文 1135 行）
- `docs/phase2/PHASE2_1_CLOSURE_REPORT.md`、`docs/phase2/PHASE2_1_LOG.md`
- `docs/phase2/PHASE2_2_CLOSURE_REPORT.md`、`docs/phase2/PHASE2_2_LOG.md`
- `docs/ARCHITECTURE.md`、`README.md`（路线图 / 重复检测 / quick_hash 段落）

**代码**：

- `core/database/{schema,db}.py`
- `core/query/{queries,dto,browse,property_map,card_format,search,__init__}.py`
- `core/scanner/{scanner,store,hashing}.py`、`core/parsers/*`、`core/models/__init__.py`
- `core/duplicate/__init__.py`、`core/classification/__init__.py`（确认仍为 docstring 空壳）
- `cli_query.py`、`main.py`、`ui/*`（main_window / browser_panel / filter_bar / detail_panel / resource_model / library_panel）

**测试**：`tests/{conftest,builders,test_duplicate_query,test_content_identity,test_query_cli,test_query_layer,test_gui_smoke}.py`

核对方法：**以实际代码为准**，不根据文件名 / 报告转述猜测设计。

---

## 4. 基线证据（只读）

| 检查 | 命令 / 方式 | 结果 |
| :--- | :--- | :--- |
| 工作区 | `git status --short` | clean（无改动，无未跟踪文件） |
| HEAD | `git rev-parse HEAD` | `8f45a4693674c6a507fac6de6c8f42468044de08`（short `8f45a46`） |
| 历史 | `git log --oneline --decorate` | `8f45a46`（feat(query): add byte-duplicate capability）→ `e76a1c6` → `93218bd` → `5987a0f` |
| tag | `git tag -n` | `phase-2.0-closed`→`93218bd`；`phase-2.1-closed`→`e76a1c6`；`phase-2.2-closed`→`8f45a46` |
| 回归 | `.venv\Scripts\python.exe -m pytest -q` | **698 passed** / 0 failed（≈47 s；与 Phase 2.2 closure 记录一致） |
| Schema | `core/database/schema.py` | `SCHEMA_VERSION == 2`；`MIGRATIONS == {1, 2}`；业务表 16 张 |
| Node 校验 | `node tools/validate_schema.mjs` / `check_model_sync.mjs` | **本轮未执行**（留待 Phase 2.3 closure 复核） |

---

## 5. 审计结论摘要

### 5.1 当前已具备（可直接复用的能力）

1. `ResourceQuery.duplicates() -> list[DuplicateGroup]`（`core/query/queries.py`），
   按 `sha256` 分组的只读派生查询；经 `_execute_select` 只读护栏。
2. `DuplicateGroup` DTO（`core/query/dto.py`）：`sha256` + `tuple[ResourceSummary, ...]` +
   `member_count`；已从 `core/query/__init__.py` 导出。
3. `resources.sha256` 已由 Phase 2.1 写入；`idx_resources_sha256` 自 v1 起存在。
4. `BrowseService`（`core/query/browse.py`）为**无自有 SQL** 的只读编排层，是 GUI 的唯一入口。
5. `cli_query.py` 的 `_resource_obj` / `_emit` / `_HANDLERS` 薄适配模式。
6. `DetailPanel._set_form_rows` + `basic_rows()` 等测试钩子（`ui/detail_panel.py`）。

### 5.2 Phase 2.3 缺失的暴露

| 缺口 | 位置 | 状态 |
| :--- | :--- | :--- |
| `ResourceSummary` 未含 `sha256` | `core/query/dto.py` | 2.2 冻结决定明确留给后续（§5.5 授权） |
| `BrowseService` 无 duplicate / sha256 转发 | `core/query/browse.py` | 缺失 |
| CLI 无 `query duplicates`；resource 输出无 `sha256` | `cli_query.py` | 缺失 |
| GUI 无 sha256 / 重复提示 | `ui/detail_panel.py` 等 | 缺失 |
| surfacing 测试 | `tests/` | 缺失 |

### 5.3 Identity / Classification / Relationship 边界

| 概念 | 当前定义 | 2.3 是否触及 |
| :--- | :--- | :--- |
| File identity | 无独立实体，File ≡ Resource | 否 |
| Byte identity | `resources.sha256`（派生值，无表 / 无 ID） | **只读展示** |
| Content identity | 本项目 = byte identity 的同义语（唯一内容身份 = sha256） | **只读展示** |
| Resource identity | `file_path_key`（全局唯一） | 否（不变） |
| Resource classification | parser-driven（`resource_type` / `card_marker`） | **否**（不为 Character Card / Outfit / Skin / Eyes / Hair 提前建体系） |
| Resource relationship | `resource_mods` / `resource_mod_usages` / `resource_plugins` / `resource_authors` | 否 |
| Resource provenance | `resources.source` / `series`（从未写入） | 否（属清理阶段） |

⇒ 2.3 **只**处理「Byte/Content identity 的展示」与「byte-duplicate 关系的展示」，
不引入任何分类或关系模型；唯一合法等价判据 = `sha256` 相等（byte-identical）。
面向用户文案必须限定为「**字节完全相同**」。

---

## 6. Gap Analysis（Contract vs 实际代码）

| 维度 | Contract（2.0-C / 2.1 / 2.2） | 实际代码 | 结论 |
| :--- | :--- | :--- | :--- |
| 内容身份写入 | 与解析同频写 `sha256`（C7） | 已实现（`core/scanner/*`） | 可复用 |
| 派生重复查询 | `GROUP BY sha256`，只读，不落库 | `ResourceQuery.duplicates()` 已实现 | 可复用 |
| 重复 DTO | 组 = sha256 + 成员 | `DuplicateGroup` 已实现 | 可复用 |
| 资源概要暴露 sha256 | 可选（§5.5） | 未暴露 | **需新增（只增字段）** |
| Browse 编排暴露 | GUI 不得绕过 Query Layer | `BrowseService` 无重复转发 | **需新增（只增方法）** |
| CLI 暴露 | Phase 2.3 范围 | 无 duplicate 命令 / 无 sha256 | **需新增** |
| GUI 暴露 | Phase 2.3 范围 | 无 | **需新增** |
| schema | Phase 2 不需要 v3 | v2 / 16 表 | 不变 |
| 持久化重复组 | 预留、零写入 | `duplicate_*` 零写入 | 保持 |

**明确禁止修改**：`core/database/*`、`core/scanner/*`、`core/parsers/*`、`core/library/*`、
`core/duplicate/*`、`core/classification/*`，以及既有 Phase 1 / 2.1 / 2.2 测试与报告。

**潜在架构冲突（必须遵守）**：`tests/test_gui_smoke.py::test_ui_does_not_bypass_query_layer`
静态禁止 `ui/*` import `ResourceQuery` / `LibraryQuery` / `sqlite3` ⇒ GUI 新增能力
**必须经 `BrowseService`**。

**文档漂移（只记录，不修）**：`docs/ARCHITECTURE.md` §5.2 / §7 与 `README.md` 路线图
仍写「需要时才算 sha256 / `quick_hash` 预筛 / 重复检测属 Phase 4 /
`duplicate_groups.status='suggested'`」，与 2.0-C 相反。权威性低于已封存的 Phase 2 契约，
本次**只记录、不修改**，属 Phase 2.2 已登记的同批 non-blocking drift。

---

## 7. Phase 2.3 Implementation Plan 摘要

> 完整 A–J 见进入实现前的对话规划；此处只落盘要点。

### 7.1 Scope（IN）

1. Query/DTO：`ResourceSummary.sha256`（可选字段）+ `BrowseService` 只读重复转发。
2. CLI：新增 `query duplicates [--json]`；`query resource` / `query resources` **新增** `sha256` 键。
3. GUI：DetailPanel 展示 `sha256`（截断 + tooltip 全文）与「字节完全相同的资源数」提示。
4. 测试：surfacing 单元 / 集成 / 只读 / 兼容性用例。
5. 可选（待裁决）：FilterBar「只看重复项」+ `ResourceQuery` 只增的 `duplicated` 过滤参数。

### 7.2 Scope（OUT）

任何新 identity/equivalence 语义、schema 变更、持久化重复组、dismiss/canonical、
同角色/跨格式推断、分类层、Tags/Collections、MOD→MOD 依赖、删除/合并、
CLI 现有字段删改、GUI 直接访问 Query Layer。

### 7.3 数据模型影响

**无。** 不新增表 / 列 / 索引 / migration；`SCHEMA_VERSION` 保持 2；业务表保持 16；
`duplicate_*` 继续零写入；`quick_hash` / `content_key` 不写不读不删。

### 7.4 API / Query 影响（全部为「只增」）

| 层 | 变更 |
| :--- | :--- |
| `core/query/dto.py` | `ResourceSummary` 增 `sha256: str | None = None` |
| `core/query/queries.py` | `_RESOURCE_SUMMARY_COLUMNS` 增 `r.sha256`；`_row_to_resource_summary` 填充 |
| `core/query/browse.py` | `BrowseService.duplicates()` + `duplicate_group_for(resource_id)` |
| `cli_query.py` | `cmd_duplicates` + parser 注册；`_resource_obj` 增 `sha256` 键 |
| `ui/detail_panel.py` | Basic 区增「内容哈希」「重复」两行 |
| `ui/main_window.py` | 把 duplicate 信息传入 `show_detail`（默认值保持兼容） |

不新建 repository / store / service 领域；不新增写入路径。

### 7.5 建议 commit 边界

1. `feat(query): expose sha256 on resource summary + duplicate read model`
2. `feat(cli): add byte-duplicate query command`
3. `feat(gui): show content hash and byte-duplicate info`
4. （可选）`feat(gui): add duplicate-only filter`
5. `docs: close phase 2.3 surfacing`（closure report + tag `phase-2.3-closed`）

### 7.6 建议执行顺序（小步、可独立验证、可回滚）

```text
确认 Contract 落差（先决）→ 2.3-A（Query/DTO）→ 2.3-B（CLI）
    → 2.3-C（GUI DetailPanel）→（可选）2.3-D（列表视图）→ 2.3-E（收尾 / audit）
```

### 7.7 Test Plan 要点

- **单元**：`ResourceSummary.sha256` 默认 `None` / 有值映射；`duplicate_group_for` 命中 / 未命中 / 单例。
- **CLI**：`query duplicates --json` 与 DTO 一致；现有命令 JSON 只增键；CLI 不改数据库。
- **GUI**：DetailPanel 显示 sha256 与重复提示；`test_ui_does_not_bypass_query_layer` 仍通过。
- **边界**：`sha256 IS NULL` 排除；同大小不同 bytes / 跨格式不得显示为重复。
- **不变量**：`duplicate_*` 零写入；schema 冻结断言；真实样本只读（1 组 Kugisaki Nobara）。

### 7.8 Closure / Audit 应检查

全量 `pytest` 只增不减；`validate_schema.mjs` / `check_model_sync.mjs` exit 0；
`SCHEMA_VERSION == 2` / 16 表断言；`duplicate_*` 零写入；`quick_hash` / `content_key` 未被引用；
GUI 未绕过 `BrowseService`；CLI JSON 向后兼容；真实样本只读不变量；用户文案只用「字节完全相同」。

---

## 8. 13 个问题的答案索引

| # | 问题 | 结论 |
| :-- | :--- | :--- |
| 1 | Phase 2.3 解决什么 | 暴露已存在的 sha256 与派生 byte-duplicate 组（不做新语义） |
| 2 | 与 Phase 2.1 边界 | 2.1 写入 sha256；2.3 只读展示，不重算、不改写入时机 |
| 3 | 与 Phase 2.2 边界 | 2.2 计算派生重复组；2.3 只消费展示，不改分组语义、不落库 |
| 4 | Resource-level equivalence 定义 | **Phase 2 内不存在**；唯一合法等价 = `sha256` 相等（byte-identical） |
| 5 | 两 File 何时属于同一 Resource | **永不**；File ≡ Resource（1:1），两文件 = 两个 Resource |
| 6 | 何时只能算 Byte Duplicate | **始终**；任何 sha256 相同都只能表述为「字节完全相同」 |
| 7 | 允许一 Resource 多 File | **不允许**（1:1 冻结，不建 `files` 表） |
| 8 | 需要新表 / 字段 / index / migration | **不需要**；`sha256` + 索引已存在 |
| 9 | 需要新 Query / DTO / repo / service | 仅「只增」暴露层；无新 repository / 写层 |
| 10 | 禁止修改的模块 | `core/database/*`、`core/scanner/*`、`core/parsers/*`、`core/library/*`、`core/duplicate/*`、`core/classification/*`、既有阶段测试 |
| 11 | 必须保持 backward compatible 的 API | 全部现有 Query 方法 / `duplicates()` / `DuplicateGroup` / `BrowseService` / `ResourceSummary` 现有字段 / CLI 现有命令与 JSON 字段 / `DetailPanel` 现有访问器 |
| 12 | 最小可交付范围 | 见 §7.1 IN（Query/DTO + CLI + GUI DetailPanel；列表视图可选） |
| 13 | 后续 Phase 能力（不可提前做） | 同角色/语义/感知重复、持久化重复组、分类层、Tags/Collections、MOD→MOD 依赖、schema v3 清理、删除/合并 |

---

## 9. 待用户裁决的开放决策

（以下为进入实现前的开放决策，现已由用户裁决，保留存档。）

| # | 决策 | 裁决结果 |
| :-- | :--- | :--- |
| 1 | Contract 认定：2.3 = surfacing 还是另立「语义级 Resource 等价」评审 | **确认为 surfacing**；2.3 只做暴露，不新建 identity / equivalence 语义 |
| 2 | 是否新增 `ResourceSummary.sha256` 可选字段（§5.5 授权） | **同意新增**（带默认值，向后兼容） |
| 3 | GUI 深度：只做 DetailPanel 展示，还是额外做 FilterBar「只看重复项」列表视图 | **本阶段不做 GUI**（2.3-D 列为可选，未授权实现） |

用户在执行前进一步冻结：本次**只执行 Phase 2.3-A（Query / DTO Surfacing）**，
不提前实现 2.3-B / 2.3-C / 2.3-D。

---

## 10. 状态与未做事项

```text
Phase 2.3 只读审查 + 架构评审 + 实施规划：完成
Phase 2.3-A（Query / DTO Surfacing + BrowseService 只读转发）：**实施完成，验证通过**
Phase 2.3-B（CLI Surfacing）：未开始（本次明确排除）
Phase 2.3-C（GUI Surfacing）：未开始（本次明确排除）
Phase 2.3-D（FilterBar duplicate filter，可选）：未开始（本次明确排除）
Phase 2.3 Closure Report：未创建（按要求不创建）
schema / migration / 数据库 / CLI / GUI：未修改
scanner / parser / hashing / store：未修改
Git：未提交、未打 tag
Phase 2.4 Final Audit：未开始
```

---

## 11. 相关文件

- 契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`
- 前序基线：`docs/phase2/PHASE2_1_CLOSURE_REPORT.md`、`docs/phase2/PHASE2_2_CLOSURE_REPORT.md`
- 过程日志：`docs/phase2/PHASE2_1_LOG.md`、`docs/phase2/PHASE2_2_LOG.md`
- 相关代码：`core/query/{queries,dto,browse,__init__}.py`、`cli_query.py`、`ui/{detail_panel,main_window,browser_panel,filter_bar}.py`
- 相关测试：`tests/{test_query_surfacing,test_duplicate_query,test_content_identity,test_query_cli,test_query_layer,test_gui_smoke}.py`

---

## 12. 实施记录（Phase 2.3-A — Query / DTO Surfacing）

> 范围：本次**只执行 Phase 2.3-A**。2.3-B（CLI）/ 2.3-C（GUI）/ 2.3-D（FilterBar）未实现，
> 也未创建 Phase 2.3 Closure Report。

### 12.1 用户冻结的执行边界（本次）

- 不做新 Resource-level identity；不做新 equivalence 语义；不做 semantic / perceptual /
  same-character duplicate；
- 不改 File ≡ Resource（1:1）；不改 `file_path_key` Resource identity；
- 不改 `ResourceQuery.duplicates()` 分组语义；不新增 duplicate 持久化；
- 不改 schema、不加 migration、不改 scanner / parser / hashing / store、不改 CLI、不改 GUI、
  不实现 FilterBar duplicate filter。

### 12.2 变更清单

| 文件 | 类型 | 统计 | 说明 |
| :--- | :--- | :--- | :--- |
| `core/query/dto.py` | 修改 | +9 / -1 | `ResourceSummary` 新增只读派生字段 `sha256: str | None = None`（带默认值、置于末尾） |
| `core/query/queries.py` | 修改 | +31 / -1 | `_RESOURCE_SUMMARY_COLUMNS` 增 `r.sha256`；`_row_to_resource_summary` 映射；新增 `ResourceQuery.duplicate_group_for()` |
| `core/query/browse.py` | 修改 | +21 | 新增 `BrowseService.duplicates()` / `duplicate_group_for()` 只读转发；导入 `DuplicateGroup` |
| `tests/test_query_surfacing.py` | 新增 | 17 例 | Phase 2.3-A focused tests |

`git diff --stat`：`3 files changed, 61 insertions(+), 2 deletions(-)`。

**明确未修改**：`core/database/*`、`core/scanner/*`、`core/parsers/*`、`core/library/*`、
`core/duplicate/*`、`core/classification/*`、`cli_query.py`、`main.py`、`ui/*`、
以及既有 Phase 1 / 2.1 / 2.2 测试与报告。

### 12.3 API / DTO（全部为「只增」）

```python
@dataclass(frozen=True)
class ResourceSummary:
    ...
    sha256: str | None = None          # 只读派生值；DTO 内不计算哈希

# core.query.ResourceQuery
def duplicate_group_for(self, resource_id: int) -> DuplicateGroup | None: ...

# core.query.BrowseService（无自有 SQL，仅转发）
def duplicates(self) -> list[DuplicateGroup]: ...
def duplicate_group_for(self, resource_id: int) -> DuplicateGroup | None: ...
```

- `ResourceQuery.duplicates()` 与 `DuplicateGroup` **源码 / 语义完全未变**。
- `duplicate_group_for()` 语义与 `duplicates()` **严格一致**（同一 `sha256` 分组键、同组成员、
  组内按 `resources.id` 升序）；单例 / `sha256 IS NULL` / 资源不存在均返回 `None`；
  经 `_execute_select` 只读护栏，不落库。
- 词表约束遵守：新增代码只使用 `sha256` / 「字节完全相同」/ byte-identical 表述，
  未引入「同一个资源 / 同一个角色 / 可删除副本 / 语义重复」等暗示语义等价的术语。

### 12.4 关键实现决定（含一处需记录的权衡）

1. **`sha256` 字段置于 `ResourceSummary` 末尾且带默认值**：既有 14 个必填字段与前 4 个可选
   计数位置不变，全部既有调用方（关键词构造）继续有效。
2. **只 SELECT 已有列**：`_RESOURCE_SUMMARY_COLUMNS` 增加 `r.sha256`；不重算、不新增哈希逻辑。
3. **`duplicates()` 的 SQL 文本保持一字不改**（严格遵守「保持完全不变」）。由于它与新方法
   共用 `_RESOURCE_SUMMARY_COLUMNS`，该常量新增 `r.sha256` 后，`duplicates()` 结果集中
   `sha256` 列出现两次；已实测 `sqlite3.Row` 按名取首列、值相同，13 例既有 duplicate 测试与
   全量回归均通过，**行为无变化**。
4. **`duplicate_group_for()` 落在 Query Layer**（而非让上层遍历 `duplicates()`）：沿用任务要求
   「若 Query Layer 缺少必要底层能力，则实现最小只读 Query 方法，而不是绕过架构」。
5. **BrowseService 只转发**：无自有 SQL、无 `connect(`、不持第二份状态，保持
   `GUI → BrowseService → Query` 为唯一入口。

### 12.5 测试（新增 `tests/test_query_surfacing.py`，17 例）

- **DTO**：未传 `sha256` 默认 `None`；传入时正确保存；既有构造方式不变。
- **Query 映射**：`summary()` / `list()` 携带真实文件哈希；`sha256 IS NULL` ⇒ `None`；非空 ⇒ 正确字符串。
- **BrowseService**：`duplicates()` 与 `ResourceQuery.duplicates()` 结果一致；
  `duplicate_group_for()` 命中正确组（成员数 / 哈希 / 成员 id / 组内 id 升序），另一成员视角同组；
  单例与 `sha256=NULL` 返回 `None`；不存在 id 返回 `None`；两方法不产生任何写入。
- **只读护栏**：`duplicate_group_for()` 经 `_execute_select`，仅发 SELECT / WITH。
- **架构护栏（静态）**：`browse.py` 无 SQL、无 `connect(`；`core/query/*` 无写语句关键字；
  `core/query/*` 不引用 `quick_hash` / `content_key`。
- **不变量**：`SCHEMA_VERSION==2` / `MIGRATIONS=={1,2}` / 16 表 / `MIGRATION_ADDED_COLUMNS` 不变；
  `duplicate_groups` / `duplicate_members` 零写入。

既有 `tests/test_duplicate_query.py`（13 例）**未修改**，全部继续通过。

### 12.6 验证证据

| 检查 | 命令 | 结果 |
| :--- | :--- | :--- |
| focused | `.venv\Scripts\python.exe -m pytest tests/test_query_surfacing.py -q` | **17 passed** |
| 全量回归 | `.venv\Scripts\python.exe -m pytest -q` | **715 passed / 0 failed**（698 + 17，≈43 s） |
| Schema | `node tools/validate_schema.mjs` | 16 表 / 期望 16 / **exit 0** |
| Model sync | `node tools/check_model_sync.mjs` | schema ↔ models 一致 / **exit 0** |
| 改动范围 | `git diff --name-only -- core/database core/scanner core/parsers core/library core/duplicate core/classification cli_query.py main.py ui docs` | **空**（禁止目录零改动） |
| schema 冻结 | `SCHEMA_VERSION == 2`、`MIGRATIONS == {1,2}`、16 表、无 migration | 成立 |
| duplicate 零写入 | 查询前后 `duplicate_groups` / `duplicate_members` 计数 | 均为 **0** |

### 12.7 Git 状态（本次结束时）

```text
$ git status --short
 M core/query/browse.py
 M core/query/dto.py
 M core/query/queries.py
?? docs/phase2/PHASE2_3_LOG.md
?? tests/test_query_surfacing.py

HEAD : 8f45a46（未提交、未打 tag）
```

### 12.8 当前状态

```text
Phase 2.3-A（Query / DTO Surfacing）：CLOSED 候选 —— 实施完成 + 全部验证通过
Phase 2.3-B（CLI）/ 2.3-C（GUI）/ 2.3-D（FilterBar）：未开始
Phase 2.3 Closure Report：未创建
```

> 本日志不构成 Phase 2.3 的正式 closure；2.3 整体收尾属后续阶段。
