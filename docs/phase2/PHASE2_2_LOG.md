# Phase 2.2 Work Log — Byte-Duplicate Capability

> 性质：**工作日志（过程记录）**，不是冻结契约，也不是正式 Phase 报告。
> 日期：2026-10-07
> 权威契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`（§5 / §8 / §13.7 / §14 / §16 / §18.1）
> 前序基线：`docs/phase2/PHASE2_1_CLOSURE_REPORT.md`（Phase 2.1 = CLOSED / PASS）
> 范围：Phase 2.2 = **Byte-Duplicate Capability**（只读派生查询；不落库）
> 状态：**只读审计 + Scope & Architecture Assessment 完成，等待用户确认**；
> 用户已确认冻结决策并授权实施 ⇒ **实现完成，等待 closure audit**；
> 已改 `core/query/{queries,dto,__init__}.py` + 新增 focused tests；
> 未改 schema / migration / 依赖 / GUI；未进入 Phase 2.3。

---

## 0. 本日志的用途

记录 Phase 2.2 这一次工作的**时间线、只读审计证据、评估结论与开放决策**，
供阶段推进（确认范围 → 实现 → 验证 → 收尾）参考。本文件**不改变**任何 Phase 1 /
Phase 2.0 / Phase 2.1 已封存文档的结论，也不构成新的契约。

---

## 1. 阶段与权威契约

Phase 2.2 的范围来自 Phase 2.0-C §16 的修订路线图：

```text
Phase 2.0-C   Architecture & Schema Design      ← 已 CLOSED / PASS
      ↓
Phase 2.1     Content Identity Foundation       ← 已 CLOSED / PASS（sha256 写入）
      ↓
Phase 2.2     Byte-Duplicate Capability          ← 本次（只读派生查询；不落库）
      ↓
Phase 2.3     Query / CLI / GUI Surfacing        （后续，不提前做）
      ↓
Phase 2.4     Phase 2 Final Audit                （后续，不提前做）
```

关键契约（Phase 2.0-C）：

- §5.4 / §13.3 C4：`sha256` 相等**仅**表示 byte-identical，不代表同角色 / 同 MOD。
- §8.2 / §8.4：Phase 2 的「重复」= **byte duplicate**；采用 **derived query**，
  `duplicate_groups` / `duplicate_members` **保持预留、不写入**。
- §13.7 D1–D4：byte duplicate = 相同 `sha256` 的派生关系；不落库、不删除、
  不计算同角色 / 同逻辑资源。
- §16：本阶段 = Byte-Duplicate Capability；**surfacing（Query / CLI / GUI）属 Phase 2.3**。
- §18.1：Phase 2 不需要 schema v3；`quick_hash` / `content_key` = deprecated / unused。

---

## 2. 时间线（本次会话）

| 步骤 | 内容 | 产物 |
| :--- | :--- | :--- |
| 1 | 只读审计：通读 Phase 2.0-C / 2.1 契约、代码、schema、测试 | 审计记录（对话） |
| 2 | 活基线复核：pytest / 两个 node 脚本 / git / 真实样本只读哈希 | 证据（本文件 §4） |
| 3 | Phase 2.2 Scope & Architecture Assessment（A–G） | 评估（对话） |
| 4 | 记录工作日志 | **本文件** |

下一步（**等待用户确认后**才执行）：确认范围与开放决策 → 实现只读派生查询 → 验证 → 收尾。

---

## 3. 本次只读审计范围

**文档**：`PHASE2_0_C_ARCHITECTURE_DESIGN.md`（全文，1135 行）、
`PHASE2_1_CLOSURE_REPORT.md`、`PHASE2_1_LOG.md`、`PHASE2_0_A_BASELINE_REVIEW.md`、
以及 `ARCHITECTURE.md` / `README.md` 中与 Phase 2 相关的段落。

**代码**：`core/database/{schema,db}.py`、`core/scanner/{scanner,store,hashing,models,__init__}.py`、
`core/query/{queries,dto,browse,property_map,card_format,search,__init__}.py`、
`core/models/__init__.py`、`core/duplicate/__init__.py`、`core/classification/__init__.py`、
`core/app/admin.py`、`cli_query.py`、`ui/*`（import 层）、`tests/{conftest,builders,test_content_identity,test_query_layer,test_query_cli}.py`。

核对方法：**以实际代码为准**，不根据文件名 / 报告转述猜测设计。

---

## 4. 基线证据（只读）

| 检查 | 命令 / 方式 | 结果 |
| :--- | :--- | :--- |
| 工作区 | `git status` | clean；HEAD `e76a1c6` 在 `main` |
| 历史 | `git log --oneline` | `e76a1c6` → `93218bd` → `5987a0f` |
| tag | `git show-ref --tags` | `phase-2.0-closed` → `93218bd`；`phase-2.1-closed`（annotated）→ `e76a1c6` |
| 回归 | `.venv\Scripts\python.exe -m pytest -q` | **685 passed**（41.62 s，0 failed） |
| Schema | `node tools/validate_schema.mjs` | 16 表 / 全项 OK / exit 0 |
| Model sync | `node tools/check_model_sync.mjs` | 类型 10 == 10 / exit 0 |
| 真实样本 | `G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike` | 存在，36 个文件 |
| 样本只读哈希 | 逐文件 sha256（只读） | 35 个候选；**1 组字节重复** = `Kugisaki Nobara` ×2（`7671306 B`，`ee44ba20…`）；`Higashiyama Kobeni` ×2 同为 `481250 B` 但 **sha256 不同** |
| 环境 | `.venv` | CPython 3.12.10 / SQLite 3.49.1 |

上述样本事实独立复现了 Phase 2.0-C §1.3 / §5.4 所依赖的判据（1 组字节重复；
同大小不同内容不得成组）。

---

## 5. 审计结论摘要（落盘 A–G）

### 5.1 当前已具备（Phase 2.1 实际完成的能力）

1. `resources.sha256` 在**与解析同频**时写入（新增 / `(size, mtime)` 变化 / `mode='full'`）；
   未变化的增量扫描不读文件、不算哈希。
2. **C7 读取一致性**成立：读取窗口内 `(size, mtime)` 变化 ⇒ 本次解析结果与 sha256
   整体不提交，下次扫描重来（不加锁 / 无 watcher / 无重试）。
3. `ResourceStore.upsert_card_resource` / `upsert_mod_resource` 增加
   `sha256: str`（required keyword-only），INSERT / UPDATE 均写入。
4. `core/scanner/hashing.py::sha256_of_file` 已提供并从 `core.scanner` 导出。
5. Schema 冻结 v2（16 表）；`resources.sha256` + `idx_resources_sha256` 自 v1 起存在。
6. `tests/test_content_identity.py`（14 例）覆盖哈希正确性、重算时机、C7、schema 冻结与真实样本。

**Phase 2.1 明确未做**：sha256 的 Query / CLI / GUI 暴露、duplicate 查询、`ResourceSummary.sha256`、DTO 变更、重复组、schema / migration 变更。

### 5.2 Phase 2.2 的目标（工程定义）

```text
Phase 2.2 = Byte-Duplicate Capability
          = 一个只读派生查询，回答「哪些 Resource 行字节完全相同（sha256 相同）」
```

只**计算**关系，不**持久化**、不**确认**、不**删除**。五个概念严格区分：

| 概念 | 是什么 | 归属 | 2.2 的动作 |
| :--- | :--- | :--- | :--- |
| Content Identity | `resources.sha256`（派生值，无表 / 无 ID） | Phase 2.1 已写入 | **只读**按它分组 |
| Resource | 一行 `resources`；身份 = `file_path_key`（全局唯一） | Phase 1 | **不变** |
| Content Relationship | 「A.sha256 == B.sha256」的**派生等价关系**（仅 byte-identical） | 不落库、按需计算 | **仅以只读查询引入** |
| Classification | `resource_type` / `card_marker`（parser-driven） | Parser + store | **不碰** |
| Human Review | `needs_review` / `review_reasons` / confirm-dismiss-canonical | Query（只读推导） | **不碰**、不引入状态 |

### 5.3 输入 / 输出

```text
Phase 2.1 已提供：resources.sha256（与 file_size / modified_time 同一次读取，C3；受 C7 约束）
        ↓
Phase 2.2 消费：sha256 IS NOT NULL 的既有 resources 行，按 sha256 分组，仅保留成员 > 1 的组
        ↓
Phase 2.2 新增：Query Layer 一个只读派生查询（例：ResourceQuery.duplicates(...)）+ 一个稳定 DTO + 测试
        （不落库、无 CLI、无 GUI、无 schema 变更）
        ↓
Phase 2.3 才处理：Query / CLI / GUI surfacing（把 sha256 与重复组暴露给用户；最小改动）
```

### 5.4 Schema 结论

**不需要 migration。** 理由（非默认）：

- 字节重复的真相**已经**存在于 `resources.sha256`，`GROUP BY sha256` 是纯派生结果，不产生第二真相来源。
- `idx_resources_sha256` 已存在，分组有索引支撑。
- 契约明确 `duplicate_groups` / `duplicate_members` 在 Phase 2 **保持预留、不写入**
  （§13.7 D2、§18.1 #11）；提升为持久组属 **OQ-5**，仅在出现真实需求时触发。
- `quick_hash` / `content_key` 不写、不读、不删（C5）；`SCHEMA_VERSION` 保持 **2**。

⇒ 最小修改 = **仅代码**：新增一个只读方法 + 一个小 DTO。

### 5.5 代码边界

| 类别 | 模块 |
| :--- | :--- |
| **应改（只增）** | `core/query/queries.py`（新增派生查询）、`core/query/dto.py`（新增不可变 DTO）、`core/query/__init__.py`（导出）、`tests/`（新增测试模块） |
| **不得改** | `core/database/*`（schema / migration / db）、`core/scanner/*`、`core/parsers/*`、`core/duplicate/__init__.py`、`core/classification/__init__.py`、`ui/*`、`cli_query.py`、`main.py`、既有 Phase 1 / 2.1 测试 |

派生查询必须经 `_execute_select`，从而继承 `ReadOnlyViolation`。

### 5.6 测试策略（最低）

1. 两个字节相同文件 ⇒ 恰好 1 组、成员 2；2. 单例不成组；
3. 同大小不同内容（合成 `Alpha`/`Bravo`；真实 `Higashiyama Kobeni`）⇒ **不成组**；
4. 跨格式同角色（KKS vs KK）⇒ **不成组**；5. `sha256 IS NULL` 行被排除且不崩；
6. 分组内容 / 顺序稳定可复现；7. 只读（不写 `resources` / `duplicate_*`，护栏生效）；
8. schema 冻结断言；9. 全量回归仍绿（≥ 685，只增）；
10. 真实样本只读：恰好 1 组（`Kugisaki Nobara` 对），`Higashiyama Kobeni` 排除，会话 sha256 不变量成立。

### 5.7 风险审查

| 风险 | 评估 | 缓解 |
| :--- | :--- | :--- |
| 破坏 Phase 2.1 | 低（只读，无新写入者） | 不动 scanner / store；保留 14 例 identity 测试 |
| 提前引入 classification | 可避免 | 仅按 sha256 分组，无类型 / marker 逻辑 |
| 把 inference 当 fact | **真实风险** | 强制「字节完全相同」措辞；测试覆盖同大小 / 跨格式反例 |
| Resource / Content 混层 | 需警惕 | 保持纯派生查询，无 content 实体 / 无第二张表 |
| schema 过早锁死 | 避免 | 2.2 无 migration；`duplicate_*` 继续预留 |
| 引入不必要 GUI | **易漂移** | 2.2 = 仅 core；不碰 `ui/`、`cli_query.py` |
| 影响 Phase 1 行为 | 低 | 全量回归必须保持绿 |

---

## 6. 发现的文档差异（仅报告，未修正）

**未发现「Phase 2.0-C / 2.1 契约」与当前代码相矛盾之处**；逐项复核的代码事实均成立。
以下为**文档漂移 / 措辞**问题，不是代码缺陷：

1. **Phase 2.0-C 自身**：§15.1 第 3 项把「Query / CLI / GUI 最小暴露」列在 Phase 2
   「IN SCOPE」，而 §16 把 "Query / CLI / GUI Surfacing" 归到 **Phase 2.3**（整阶段范围 vs 分步拆分）。
   本次采用 §16 的读法（2.2 = 仅 core）。
2. **Phase 0 / 1 旧文档与 Phase 2 契约冲突**：
   - `docs/ARCHITECTURE.md` §5.2 仍写「需要高可靠性时才计算 sha256」「大库先算 `quick_hash` 预筛」，
     与 Phase 2.0-C §5.1.1 / §5.2 及 Phase 2.1 实现相反。
   - `docs/ARCHITECTURE.md` §7 与 `README.md` 路线图仍把重复检测列为 Phase 4、并写
     `duplicate_groups.status='suggested'`，与 Phase 2.0-C §8.4（派生查询、不写入）相反。
   二者权威性低于已封存的 Phase 2 契约，本次**只记录、不修改**。
3. **Phase 2.0-C §1.2 快照**把 `resources.sha256` 记为「零写入」——在 2.0-C 当时成立，
   Phase 2.1 之后已改变；若当作当前状态阅读会显得过期（非矛盾）。

---

## 7. 待用户确认的开放决策

1. **范围读法**：采用 §16 —— Phase 2.2 = **仅 core Query 层只读派生查询**；
   sha256 / 重复组的 CLI + GUI 暴露归 Phase 2.3。（解决 §6-1 差异）
2. **查询落点**：`ResourceQuery.duplicates(...)`（§8.4 的表述）还是新建 `DuplicateQuery` 类。
3. **结果形态**：新增专用 DTO（组 = sha256 + 成员 `ResourceSummary`）还是给 `ResourceSummary` 加 `sha256`。
4. **范围开关**：是否在 2.2 就提供 `min_group_size` / `library_id` / `scan_status` 过滤。

---

## 8. 状态与未做事项

```text
Phase 2.2 只读审计 + Scope & Architecture Assessment：完成
用户确认冻结决策（scope / API / DTO / knobs / semantics / persistence / boundary）：完成
派生 duplicate 查询（ResourceQuery.duplicates + DuplicateGroup DTO）：**已实现**
focused tests（tests/test_duplicate_query.py，13 例）：**已通过**
全量回归：**698 passed**（基线 685 + 13），0 failed
schema / migration / 依赖 / GUI：未改动
sha256 / duplicate 的 CLI / GUI surfacing：未做（属 Phase 2.3）
Git：未提交、未打 tag（本次改动未提交）
Phase 2.2 closure audit：**待用户决定**；Phase 2.3 / 2.4：未开始
```

---

## 9. 相关文件

- 契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`
- 前序基线：`docs/phase2/PHASE2_1_CLOSURE_REPORT.md`、`docs/phase2/PHASE2_1_LOG.md`
- 相关代码：`core/query/{queries,dto,__init__}.py`、`core/scanner/{scanner,store,hashing}.py`、`core/database/schema.py`
- 相关测试：`tests/test_content_identity.py`、`tests/test_query_layer.py`、`tests/conftest.py`

---

## 10. 实施记录（Phase 2.2 实现）

### 10.1 变更清单

| 文件 | 类型 | 统计 | 说明 |
| :--- | :--- | :--- | :--- |
| `core/query/dto.py` | 修改 | +28 | 新增不可变 `DuplicateGroup` DTO（`sha256` + `resources` + `member_count` 只读属性） |
| `core/query/queries.py` | 修改 | +40 | `ResourceQuery.duplicates()` 只读派生查询（经 `_execute_select`） |
| `core/query/__init__.py` | 修改 | +2 | 导出 `DuplicateGroup` |
| `tests/test_duplicate_query.py` | 新增 | 新文件，13 例 | Phase 2.2 focused tests |

未改动：`core/database/*`、`core/scanner/*`、`core/parsers/*`、`core/duplicate/*`、
`core/classification/*`、`ui/*`、`cli_query.py`、`main.py`、既有 Phase 1 / 2.1 测试。

### 10.2 API / DTO

```python
@dataclass(frozen=True)
class DuplicateGroup:
    sha256: str
    resources: tuple[ResourceSummary, ...] = ()
    @property
    def member_count(self) -> int: ...

# core.query.ResourceQuery
def duplicates(self) -> list[DuplicateGroup]: ...
```

`ResourceSummary` **未修改**（未加入 `sha256`）；未新建 `DuplicateQuery` domain。

### 10.3 Query semantics

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

- 仅 byte-identical 分组；最低成员数固定 2；`sha256 IS NULL` 排除；
  组按 `sha256` 升序、组内成员按 `id` 升序 ⇒ 确定性。

### 10.4 验证证据

| 检查 | 命令 | 结果 |
| :--- | :--- | :--- |
| focused | `.venv\Scripts\python.exe -m pytest tests/test_duplicate_query.py -q` | **13 passed** |
| 全量回归 | `.venv\Scripts\python.exe -m pytest -q` | **698 passed**（685 + 13），0 failed |
| Schema | `node tools/validate_schema.mjs` | 16 表 / 全 OK / exit 0 |
| Model sync | `node tools/check_model_sync.mjs` | exit 0 |
| 真实样本 | `test_real_sample_byte_duplicate_query` | **PASSED**（恰好 1 组，Kugisaki Nobara ×2） |

Schema 冻结：`SCHEMA_VERSION == 2`、`MIGRATIONS == {1,2}`、无 migration；
`duplicate_groups` / `duplicate_members` 零写入；`quick_hash` / `content_key` untouched。
