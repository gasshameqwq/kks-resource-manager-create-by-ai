# Phase 2.2 Final Closure Report — CLOSED / PASS

> 阶段：**Phase 2.2 — Byte-Duplicate Capability**（Query Layer 只读派生能力）
> 权威契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`（§5 / §8 / §13.7 / §14 / §16 / §18.1）
> 前序基线：`docs/phase2/PHASE2_1_CLOSURE_REPORT.md`（Phase 2.1 = CLOSED / PASS）
> 日期：2026-10-07
> schema：**v2**（未改动）· Python 3.11+ / 实测 CPython 3.12.10 · SQLite 3.49.1
> 本报告基于 **Phase 2.2 Closure Audit** 的实际执行结果编写，未添加未经验证的结论。

## 结论

```text
PHASE 2.2 = CLOSED / PASS
```

无 P0 / P1。focused tests 13 passed；全量 `pytest` **698 passed / 0 failed**；
schema 与 model-sync 校验通过；范围隔离干净（未改 schema / scanner / parser /
store / CLI / GUI）。**未提交、未打 tag。**

---

## 1. 阶段名称与目标

- **名称**：Phase 2.2 — Byte-Duplicate Capability。
- **目标**（Phase 2.0-C §16）：在既有 `resources.sha256` 之上，提供一个**只读派生查询**，
  回答「哪些 Resource 的文件**字节完全相同**（sha256 相等）」。
- 本阶段**只计算**该派生关系，**不持久化**、**不确认**、**不删除**，也不暴露到 CLI / GUI
  （surfacing 属 Phase 2.3）。

---

## 2. 权威契约来源

Phase 2.2 的全部约束来自 `docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`：

| 契约位置 | 内容 | 与本阶段的关系 |
| :--- | :--- | :--- |
| §5.4 / §13.3 **C4** | sha256 相等**仅**表示 byte-identical，不代表同角色 / 同 MOD / 同逻辑资源 | 本查询的语义边界 |
| §8.1 / §8.2 | 三类重复分开；Phase 2 的「重复」= **byte duplicate** | 本阶段范围 |
| §8.4 / §13.7 **D1–D4** | duplicate = **derived** 关系；`duplicate_*` 预留不写入；不删除；不计算同角色 | 本阶段设计 |
| §13.3 **C5** / §18.1 #4 | `quick_hash` / `content_key` = deprecated / unused | 本阶段保持 untouched |
| §14.4 | Query Layer 只允许 SELECT / WITH | 只读护栏 |
| §16 | Phase 2.2 = Byte-Duplicate Capability（只读派生查询；不落库） | 阶段定义 |
| §11.1 / §18.1 #14 | Phase 2 不需要 schema v3 | schema 冻结 |

用户在本阶段开始前冻结的决策（scope / API / DTO / knobs / semantics / persistence / boundary）
与本契约一致。

---

## 3. 明确范围 / 非范围

### 3.1 IN SCOPE（已实现）

- 在**现有 `ResourceQuery`** 上新增一个**只读派生查询** `duplicates()`。
- 新增一个 **immutable** `DuplicateGroup` DTO（`sha256` + 组成员）。
- focused tests 覆盖分组、反例、NULL、ordering、只读、schema 冻结与真实样本。

### 3.2 OUT OF SCOPE（未做）

| 项 | 结论 |
| :--- | :--- |
| CLI surfacing | **未做**（Phase 2.3） |
| GUI surfacing | **未做**（Phase 2.3） |
| `ResourceSummary` 暴露 `sha256` | **未做**（契约中为「可选」；本阶段冻结决定不加） |
| 新建 `DuplicateQuery` domain | **未做**（复用 `ResourceQuery`） |
| 持久化 duplicate 关系 | **未做**（不写 `duplicate_groups` / `duplicate_members`） |
| user 确认 / dismiss / canonical | **未做**（无证据；OQ-5） |
| `min_group_size` / `library_id` / `scan_status` 参数 | **未做**（冻结决定不增加） |
| same-character / same-MOD / logical duplicate 推断 | **未做** |
| schema / migration 变更 | **未做** |

---

## 4. 交付物：API 与 DTO

### 4.1 `ResourceQuery.duplicates()`

位置：`core/query/queries.py`（`ResourceQuery` 的新方法）。

```python
def duplicates(self) -> list[DuplicateGroup]: ...
```

- 返回按 `sha256` 分组的 **byte-identical** 组列表；每个组至少 2 个成员。
- 无参数（最低成员数固定为 2；无过滤开关）。
- 只读：经 `_execute_select` 执行，继承只读护栏。

### 4.2 `DuplicateGroup` DTO

位置：`core/query/dto.py`（并从 `core/query/__init__.py` 导出）。

```python
@dataclass(frozen=True)
class DuplicateGroup:
    sha256: str
    resources: tuple[ResourceSummary, ...] = ()

    @property
    def member_count(self) -> int:
        return len(self.resources)
```

- `frozen=True`（immutable / read-only）；`member_count` 为纯派生属性。
- `sha256` 是**分组键**，**不是**新的 Content ID / Content 实体。
- 成员为 `ResourceSummary`（资源自身事实），未修改 `ResourceSummary` 本体。

---

## 5. 语义与设计

### 5.1 byte-identical / sha256 语义

- `sha256` = 文件**原始字节**的 SHA-256（64 位小写十六进制），由 Phase 2.1 在与解析同频时写入。
- `sha256` 相等**只**表示**文件字节完全相同**（byte-identical）。
- 本阶段**不**把 `sha256` 解释为角色身份、MOD 身份或逻辑资源身份；
  **不**做任何逻辑相似性推断。

### 5.2 derived query 设计

- duplicate 关系是**派生结果**，由查询时 `GROUP BY sha256` 计算得到；
- **不落库**：不创建 content 实体、不写 `duplicate_groups` / `duplicate_members`；
- 唯一事实来源仍是 `resources.sha256`（不存在第二真相来源）。

### 5.3 SQL 核心语义

```sql
SELECT <_RESOURCE_SUMMARY_COLUMNS>, r.sha256
FROM resources r
WHERE r.sha256 IS NOT NULL
  AND r.sha256 IN (
      SELECT s.sha256 FROM resources s
      WHERE s.sha256 IS NOT NULL
      GROUP BY s.sha256
      HAVING count(*) >= 2
  )
ORDER BY r.sha256 ASC, r.id ASC
```

索引兼容（`EXPLAIN QUERY PLAN` 实测）：

```text
SEARCH r USING INDEX idx_resources_sha256 (sha256=?)
SEARCH s USING COVERING INDEX idx_resources_sha256 (sha256>?)
```

说明：§13.7 D1 表述为「identical sha256 over identical-size files」；由于 C3
（sha256 与同一次读取的 `file_size` 一起写入），sha256 相等 ⇒ 字节相同 ⇒ `file_size` 相同，
因此按 `sha256` 分组与「同 sha256 且同大小」等价。真实样本中成组成员大小一致，已实测验证。

### 5.4 NULL / singleton / ordering 行为

| 行为 | 规则 |
| :--- | :--- |
| `sha256 IS NULL` | **排除**，不参与分组、不报错（从未解析 / 未计算哈希的资源） |
| singleton | **排除**，不返回（`HAVING count(*) >= 2`，最低成员数固定为 2） |
| group ordering | 按 `sha256` **升序**（稳定） |
| member ordering | 组内按 `resources.id` **升序**（稳定） |
| determinism | 相同数据库状态下重复调用结果一致 |

---

## 6. Read-only invariant

实际验证（非仅代码阅读）：

- `duplicates()` 的所有语句经 `_execute_select` 执行；捕获到的语句关键字仅 `select`。
- 调用后 `conn.total_changes` **不变**（delta = 0）；`resources` 行数不变。
- `core/query/*` 内**不存在** `INSERT / UPDATE / DELETE / DROP / ALTER`；
  唯一的 `conn.execute` 位于 `_execute_select`（只读护栏）内部。
- 真实样本目录在验证前后 sha256 树一致（无文件系统写入）。

---

## 7. 未写入 / 未使用

### 7.1 `duplicate_groups` / `duplicate_members`

- 本阶段**没有**把 duplicate 关系持久化；这两张表**保持预留、零写入**。
- 验证：查询前后两表计数均为 **0**；全仓无写入者。
- **不是**本阶段实现的一部分（本阶段实现是派生查询）。

### 7.2 `quick_hash` / `content_key`

- 二者保持 **deprecated / unused**：本阶段不写、不读、不删除。
- `core/query` 内**完全未引用**这两个字段。

---

## 8. Schema

- `SCHEMA_VERSION == 2`；`MIGRATIONS == {1, 2}`；`MIGRATION_ADDED_COLUMNS` 不变。
- 业务表 **16**；`validate_schema.mjs` 实测 16/16。
- **无** schema v3、**无** migration、**无**新表 / 新列 / 新索引。
- 沿用既有 `resources.sha256` + `idx_resources_sha256`。

---

## 9. Phase 2.1 compatibility

- `core/scanner/*`、`core/database/*`、`core/parsers/*` 均**未修改**（`git diff` 对上述路径为空）。
- Phase 2.1 的 sha256 writer 行为与 **C7 读取一致性**未被改变。
- `tests/test_content_identity.py` 仍**完整通过（14 passed）**，未修改。
- Resource Identity（`file_path_key` 全局唯一）未被重新定义。
- **`ResourceSummary` 未被修改**（`dto.py` 的改动为纯新增：`DuplicateGroup` 块 + 一处 `__all__` 条目）。

---

## 10. Phase 2.3 surfacing 状态

- 本阶段**未**实施任何 CLI / GUI / Query surfacing。
- `sha256` 与 duplicate 组**尚未**暴露给用户界面或 CLI（属 Phase 2.3）。
- 未进入 Phase 2.3。

---

## 11. 文件修改范围

| 文件 | 类型 | 统计 | 说明 |
| :--- | :--- | :--- | :--- |
| `core/query/dto.py` | 修改 | +28 | 新增不可变 `DuplicateGroup` DTO |
| `core/query/queries.py` | 修改 | +40 | 新增 `ResourceQuery.duplicates()` |
| `core/query/__init__.py` | 修改 | +2 | 导出 `DuplicateGroup` |
| `tests/test_duplicate_query.py` | 新增 | 13 例 | Phase 2.2 focused tests |
| `docs/phase2/PHASE2_2_LOG.md` | 新增 | 过程记录 | Phase 2.2 工作日志（审计 + 实施） |
| `docs/phase2/PHASE2_2_CLOSURE_REPORT.md` | 新增 | 本报告 | Phase 2.2 收尾报告 |

**明确未修改**：`core/database/*`、`core/scanner/*`、`core/parsers/*`、`core/duplicate/*`、
`core/classification/*`、`ui/*`、`cli_query.py`、`main.py`；未修改既有 Phase 1 / 2.1 测试与报告。

---

## 12. 测试与验证结果

| 验证 | 命令 | 结果 |
| :--- | :--- | :--- |
| duplicate query（focused） | `.venv\Scripts\python.exe -m pytest tests/test_duplicate_query.py -q` | **13 passed** |
| content identity | `.venv\Scripts\python.exe -m pytest tests/test_content_identity.py -q` | **14 passed** |
| 全量回归 | `.venv\Scripts\python.exe -m pytest -q` | **698 passed / 0 failed**（≈42 s） |
| Schema | `node tools/validate_schema.mjs` | 16 表 / 全 OK / **exit 0** |
| Model sync | `node tools/check_model_sync.mjs` | **exit 0** |

基线对照：698 = 685（Phase 2.1 基线）+ 13（Phase 2.2 新增）；既有测试无减少、无削弱。

---

## 13. 真实样本验证（只读）

样本目录：`G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike`（只读使用）。

| 检查 | 结果 |
| :--- | :--- |
| Kugisaki Nobara ×2 | **形成 1 个 byte-duplicate group**（sha256 `ee44ba20…`，两文件均 `7671306 B`） |
| Higashiyama Kobeni ×2（同为 `481250 B`） | **不分组**（字节不同） |
| 跨格式（KKS vs KK）同角色 | **不分组**（字节不同） |
| 数据库写入 | 无（查询前后 `duplicate_*` 计数为 0；样本目录前后一致） |

---

## 14. Git 状态

```text
branch : main
HEAD   : e76a1c6  （未变）
tags   : phase-2.0-closed, phase-2.1-closed（未变）
状态   : 未 commit、未 tag
```

- **尚未 commit**：Phase 2.2 的改动与本文档仍处于工作区。
- **尚未 tag**：**没有**创建 `phase-2.2-closed` 或任何 Phase 2.2 tag。
- 已跟踪文件改动：`core/query/{dto,queries,__init__}.py`（+2 / +28 / +40）。
- 未跟踪文件：`tests/test_duplicate_query.py`、`docs/phase2/PHASE2_2_LOG.md`、
  `docs/phase2/PHASE2_2_CLOSURE_REPORT.md`（本报告）。

---

## 15. Non-blocking documentation drift

以下为**既有**文档漂移，**不影响** Phase 2.2 的正确性与结论；按要求**未修改**（不属于本阶段范围）：

| # | 漂移 | 位置 | 状态 |
| :-- | :--- | :--- | :--- |
| 1 | 仍把重复检测列为 Phase 4、并描述 `duplicate_groups.status` 语义 | `docs/ARCHITECTURE.md` §7 / `README.md` 路线图 | **non-blocking**（被 Phase 2.0-C 取代） |
| 2 | 仍写「需要时才计算 sha256」「大库先算 `quick_hash` 预筛」 | `docs/ARCHITECTURE.md` §5.2 | **non-blocking**（与 Phase 2.0-C §5 相反） |
| 3 | 整阶段范围 vs 分步拆分措辞 | `PHASE2_0_C` §15.1 第 3 项 vs §16 | **non-blocking**（本阶段采用 §16 读法） |
| 4 | `sha256` 记为「零写入」 | `PHASE2_0_C` §1.2 快照 | **non-blocking**（Phase 2.1 起已改变） |

---

## 16. 结束条件核对

| 结束条件 | 状态 |
| :--- | :--- |
| Phase 2.2 范围（Byte-Duplicate Capability）实现 | ✅ |
| byte-identical = sha256 equality；duplicate = derived query | ✅ |
| `duplicate_groups` / `duplicate_members` 零写入 | ✅ |
| 无 same-character / same-MOD / logical duplicate 推断 | ✅ |
| 无 schema 变更、无 migration、无 v3（保持 v2 / 16 表） | ✅ |
| `quick_hash` / `content_key` 保持 unused | ✅ |
| 只读不变量成立（经 `_execute_select`） | ✅ |
| Phase 2.1 不变量保持（14 identity tests 通过；scanner/store 未改） | ✅ |
| `ResourceSummary` 未修改 | ✅ |
| Phase 2.3 surfacing 未实施 | ✅ |
| focused 13 + content identity 14 + 全量 698 passed / 0 failed | ✅ |
| `validate_schema.mjs` / `check_model_sync.mjs` exit 0 | ✅ |
| 真实样本：1 组（Kugisaki Nobara）；Higashiyama / 跨格式不分组 | ✅ |
| 未 commit、未 tag | ✅（如预期） |

```text
PHASE 2.2 = CLOSED / PASS
```

（本阶段到此结束：不进入 Phase 2.3；不修改任何功能代码、schema、migration 或既有报告。）
