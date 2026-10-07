# Phase 3.1 — Implementation Contract（User Write Foundation）

> 文档类型：**Phase 3.1 实施前冻结的 Implementation Contract（FROZEN）**
> 日期：2026-10-07
> 权威层级（从高到低）：
> 1. `docs/phase3/PHASE3_0_CONTRACT.md` —— **Phase 3.0 冻结 Architecture / Scope Contract（最高权威）**
> 2. `docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md` —— Search & Taxonomy Design Review
> 3. 本文件 —— Phase 3.1 实施契约，**不得与上级冲突**
> 前置：
> - Phase 3.0 = CLOSED / PASS（tag `phase-3.0-closed` → commit `c2fd527`，未改动）
> - Phase 3.0.2 Design Review 已正式入库（commit `ae3529a`）
> - Phase 3.1 Read-Only Baseline & Implementation Plan 已完成（审计结论见本文件 §3 / §7）
> 本文件：**只做实施前冻结。未修改任何功能代码 / schema / migration / 测试 / CLI / GUI。**

> **冻结声明**：本文件冻结 Phase 3.1（User Write Foundation）的**范围、所有权、写边界、
> 语义与测试不变式**。任何扩大 3.1 范围的行为，必须先走 `PHASE3_0_CONTRACT.md` §16 变更控制
> （新增评审 + 更新 Contract + 用户确认）。

---

## 0. 本阶段唯一目标

```text
建立统一、安全、可审计的「用户数据写入边界」：
用户可以明确修改「属于用户的数据」，
而程序不会因此获得随意修改机器事实的能力。
```

Phase 1～2 的结论是「程序可以读取与分析资源」；Phase 3.1 起：
**用户数据可被用户明确修改，且机器写入者永不覆盖用户数据。**

---

## 1. Scope（Phase 3.1 只负责这些）

1. **ResourceWriteService**：唯一用户数据 runtime 写入口（对称于既有 `LibraryAdminService`）。
2. **`display_name` user ownership** 落地：Scanner 停止写入；语义见 §4。
3. **`notes` user ownership** 落地：仅由写服务写入。
4. **`resource_type` user override**：提供 `set_resource_type()` 基础写能力。
5. **`type_source` ownership**：`'user'` 由写服务写入；Scanner 尊重该开关。
6. **effective display name 统一定义**：单一权威实现（core），UI 委托。
7. **必要的 read-model additive exposure**：把用户字段（至少 `type_source`）以**追加字段**方式暴露给只读消费方。
8. **CLI 最小编辑入口**：`resource set-display-name` / `resource set-notes` / `resource set-type`（含 display name clear）。
9. **ownership / regression tests**：静态写路径守卫 + §8 全部不变式。

交付顺序按 §7；**Step 2 与 Step 3 必须同一批落地**。

---

## 2. Explicit Non-Goals（Phase 3.1 明确不做）

| # | 排除项 |
| :-- | :--- |
| 1 | Tag 体系（创建 / 列表 / 重命名 / 删除 / 加标签） |
| 2 | Favorite / 收藏 |
| 3 | Collection |
| 4 | GUI 大规模改造（含 GUI 编辑资源字段） |
| 5 | 文件移动 / 改名 / 删除 / 下载 |
| 6 | 自动重新分类 / 自动整理 |
| 7 | 自动迁移用户数据（含对既有 `display_name` 的回填或清理） |
| 8 | AI / Semantic Classification / 语义相似 / 感知哈希 |
| 9 | relocation / 移动检测 / 资源连续性 |
| 10 | 新身份键（Family / Variant / logical resource） |
| 11 | Query Layer 获得任何写能力（`_execute_select` 只读护栏保持） |
| 12 | Query Layer 文本布尔语法（`field:` + AND / OR / NOT；属 Contract §16 变更控制） |
| 13 | schema v3 / migration / 新表 / 新列 / 新索引 |
| 14 | Parser 行为修改 |
| 15 | `type_source` 由 `'user'` 回退为 `'auto'`（用户类型修正的「清除」能力，本阶段不做） |

> 说明：第 15 项为**有意收窄**：3.1 只提供「设置用户类型」，不提供「撤销用户类型」。

---

## 3. Ownership Table（冻结）

| Data | Owner | Writer |
| :--- | :--- | :--- |
| `name` | Machine | ResourceStore |
| scanner-derived fields | Machine | ResourceStore |
| `display_name` | User | ResourceWriteService |
| `notes` | User | ResourceWriteService |
| `resource_type` when auto | Machine | ResourceStore |
| `resource_type` when user | User | ResourceWriteService |
| `type_source` | ownership marker | ResourceWriteService / Machine logic according to contract |

补充冻结（落点澄清，不扩大范围）：

| 类别 | 具体列 | 写入者 |
| :--- | :--- | :--- |
| Machine facts | `file_path`、`file_path_key`、`relative_path`、`file_size`、`modified_time`、`extension`、`sha256`、`card_marker`、`metadata_json`、`name`、`parse_status`、`parse_error`、`scan_status`、`last_scanned_at` | `ResourceStore` |
| Machine（系统） | `id`、`created_at`、`updated_at` | DB / `ResourceStore` |
| User data | `display_name`、`notes` | `ResourceWriteService` |
| User override | `resource_type`（当 `type_source='user'`）+ `type_source='user'` | `ResourceWriteService` |
| 预留 / 未启用 | `source`、`series`、`description`、`authors.notes`、`tags`、`resource_tags`、`collections` | 首期无写入者（沿用 Phase 3.0 §2.2 / §2.3） |

`type_source` 的写入归属澄清（消除歧义）：

```text
'auto'（初始值）  → ResourceStore 在 INSERT 时写入（既有行为，保持）
'user'            → 仅 ResourceWriteService 写入（与 resource_type 同事务）
'user' → 'auto'   → Phase 3.1 不提供（见 §2-15）
```

> `type_source` 不是自由文本：它是「机器 / 用户」的 ownership marker，
> 两个写入者各自只能把行置于自己负责的状态。

---

## 4. display_name Contract（冻结）

```text
NULL          = no user override
non-NULL      = user override exists
equal-to-name = still user override（not a "no override" signal）

clear         = NULL
effective     = display_name if display_name is not None else name
                （对历史遗留的 ''/纯空白，读取侧按「无 override」处理，见 §4.4）
```

### 4.1 写入归一化（ResourceWriteService 必须实现）

输入 `value: str | None`：

```text
None                      → display_name = NULL   （no override）
value.strip() == ""       → display_name = NULL   （no override；含纯空白）
否则                       → display_name = value.strip()   （非空字符串，strip 后保存）
```

### 4.2 不得使用的判定

**禁止**用 `display_name == name` 判断 override 是否存在。

```text
name = "Alice" 且 display_name = "Alice"
    ⇒ display_name IS NOT NULL
    ⇒ user override 存在
```

### 4.3 重扫语义

- `display_name IS NOT NULL` 时，Scanner 重扫**不得**修改它（即使 Parser 改变了 `name`）。
- `display_name IS NULL` 时，effective display name 回退到**当前** `name`。
- 写服务保证 `''`/纯空白不会成为持久状态，因此 **非 NULL ⇒ 非空用户值**。

### 4.4 读取侧归一化（历史遗留空白）

写服务保证不会产生 `''`/纯空白（§4.1）。为兼容历史库中可能存在的空白值，**读取侧**统一按
「空白 = 无 override」处理：

```text
effective_display_name =
    display_name   if (display_name is not None and display_name.strip() != "")
    name           otherwise
```

对所有由 `ResourceWriteService` 写入的数据（非 NULL ⇒ 非空），本式与 §4 的
`display_name if display_name is not None else name` **完全等价**；它只额外把历史遗留的
`''`/纯空白按「无 override」处理（与本次裁定「blank ⇒ no override」一致，并保持既有 UI 行为
与既有测试 `test_display_title_fallbacks`）。

本阶段**不做**任何自动迁移或清理（§2-7）。当前持久工作库为 0 resources，此边界无实际影响。

---

## 5. Write Boundary（冻结）

```text
ResourceWriteService 是 Phase 3.1 用户数据写入的唯一 runtime boundary。
```

### 5.1 写服务必须定义

| 维度 | 冻结语义 |
| :--- | :--- |
| 事务边界 | 单个写方法 = 一个 `db.transaction`；失败整体回滚并原样抛出 |
| 幂等 | 同值重复写入无副作用（可 no-op 或幂等 UPDATE） |
| 冲突语义 | 首期无乐观锁；直接覆盖「自己这一行」的对应列，不做并发写合并 |
| 错误语义 | 资源不存在 → `ResourceNotFound`；非法类型 → `InvalidResourceValue`；不吞异常 |

### 5.2 Scanner / Parser 不得写

```text
- display_name
- notes
- user-owned resource_type（type_source='user' 时的 resource_type）
- type_source = 'user'
```

机器写入（`ResourceStore`）**只能**写 §3 的 Machine facts 列。
Parser 为纯只读，不接触 DB。

### 5.2.1 系统簿记列（冻结豁免）

```text
updated_at 是「行被修改」的系统簿记列，不是业务事实。
ResourceWriteService 的每次写入都必须同时更新 updated_at = datetime('now')。
因此 Invariant F 的「用户 writer 不得写 machine-owned columns」护栏
对 updated_at 显式豁免；其余 Machine facts 列一律不得出现在用户 writer 的 SQL 中。
```

### 5.3 入口分层（CLI）

```text
CLI
 ↓
ResourceQuery.resolve()     # 仅用于只读解析目标（id / 路径 / path_key / relative_path）
 ↓
ResourceWriteService        # 唯一用户写入口
 ↓
DB
```

CLI **不得**：

- `import sqlite3`
- 自己执行 SQL
- 绕过 `ResourceWriteService` 修改 `resources`

---

## 6. Schema（冻结）

```text
SCHEMA_VERSION = 2
No schema change
No migration
No new table
No new column
No new index
```

依据：`display_name` / `notes` / `resource_type` / `type_source` 列在 v1 即存在；
本阶段只改**写入归属与读取语义**，不改 DDL。

---

## 7. Implementation Steps

> 全程零 schema / 零 migration。每步可独立审计、独立测试。
> **Step 2 与 Step 3 必须作为同一 implementation batch**（避免中间状态）。

### Step 1 — ResourceWriteService

- **新增**：`core/app/resource_write.py`（`ResourceWriteService` + 异常类型）；`core/app/__init__.py` 导出。
- **方法**：
  - `set_display_name(resource_id, value: str | None)`（§4.1 归一化；`None`/空白 ⇒ NULL）
  - `set_notes(resource_id, value: str | None)`（`None`/空白 ⇒ NULL；否则 `strip()` 保存）
  - `set_resource_type(resource_id, value: str)` ⇒ `resource_type = value, type_source = 'user'`
- **为什么**：Phase 3.0 §2.4 / §9；3.0.2 §5.2 指定落点。
- **依赖**：`core.database.db.transaction`。
- **测试**：set / clear / 等于 name / 类型校验 / 不存在 id / 幂等。
- **schema / migration**：否 / 否。**Scanner / Parser**：否。**Query Layer**：否（写入不经 Query Layer）。
- **docstring 必须写入 §4 全套语义（含「禁止 `display_name == name` 判定」与「非 NULL ⇒ override」）。**

### Step 2 — Scanner 移除 `display_name` 写入

- **修改**：`core/scanner/store.py`：`upsert_card_resource` 与 `upsert_mod_resource` 的
  INSERT 去掉 `display_name` 列；UPDATE 的 `SET` 去掉 `display_name`，并删除旧启发式
  （`display_name = parsed.name` 及「等于旧 name 才跟随」的判定）。
- **为什么**：Phase 3.0 §3.1 规则 5/6/7/8/9（解法 B 授权修正）。
- **依赖**：Step 3（读取侧 effective 定义）——同批落地。
- **测试**：§8 Invariant A / B / C。
- **schema / migration**：否 / 否。**Scanner**：是（仅去列）。**Parser**：否。**Query Layer**：否。

### Step 3 — Effective display name 统一

- **修改**：`core/query/dto.py`（在此**唯一**定义 `ResourceSummary.effective_display_name` 与 `title`），
  `ui/resource_model.py` 的 `display_title` 委托 core；删除 UI 内的重复实现。
- **冻结定义（两层，不得混用）**：

  ```text
  业务定义（= §4.4，权威）
      effective_display_name =
          display_name if (display_name is not None and display_name.strip() != "") else name

  展示回退链（仅当业务结果为空时使用；在 core 定义一次）
      effective_display_name → relative_path 的文件名 → file_path
  ```

- **为什么**：单一权威定义；UI 不重复业务语义；保留既有「name 为空时显示文件名」的行为，避免 UX 回归。
- **依赖**：Step 1 的归一化（保证非 NULL ⇒ 非空）。
- **测试**：`display_name` 非空 → display；`==name` → display（仍为 override）；
  `display_name = NULL` → name；`name` 也为空 → relative_path 文件名；`relative_path` 也为空 → `file_path`。
- **schema / migration / Scanner / Parser**：否。**Query Layer**：只读、无 SQL 变更。
  （注意：本步保留既有 `test_display_title_fallbacks` 的全部断言。）

### Step 4 — Read model additive exposure

- **修改**：`core/query/dto.py`（`ResourceSummary` 末尾**追加** `type_source: str = "auto"`，`notes: str | None = None`）；
  `core/query/queries.py`（`_RESOURCE_SUMMARY_COLUMNS` 增列 + 行映射）。
- **为什么**：CLI 与测试需要观察 `type_source` / `notes`。
- **约束**：**仅 additive SELECT**；字段带默认值、置末尾（Phase 2.3 惯例）；不改既有字段语义与筛选语义。
- **测试**：旧构造方式仍可用（向后兼容）+ 映射正确。
- **schema / migration / Scanner / Parser**：否。

### Step 5 — CLI 入口

- **修改**：`main.py`（新增 `resource` 子命令）；薄适配，不含 SQL。
- **命令**：
  ```text
  python main.py resource set-display-name <id|路径> <value>
  python main.py resource set-display-name <id|路径> --clear
  python main.py resource set-notes <id|路径> <value>
  python main.py resource set-notes <id|路径> --clear
  python main.py resource set-type <id|路径> <type>
  ```
- **为什么**：Phase 3.0 §12-7（至少一个入口）；3.0.2 §11 建议 CLI 先行（U2 未决）。
- **测试**：dispatch 级别 + 端到端（写后只读查询立即可见）。
- **schema / migration / Scanner / Parser**：否。**Query Layer**：仅只读 `ResourceQuery.resolve()`。

### Step 6 — Ownership / regression tests

- **新增**：`tests/test_resource_write.py`、`tests/test_ownership_guard.py`；扩展 `tests/test_scanner.py`。
- **测试**：§8 Invariant A–F。
- **schema / migration**：否。

---

## 8. Test Invariants（冻结）

### Invariant A

```text
user display_name
+
scanner changes name
=
display_name unchanged
```

### Invariant B

```text
clear display_name
=
NULL
=
effective display name falls back to name
```

### Invariant C

```text
display_name == name
=
still user override
```

### Invariant D

```text
type_source = user
+
scanner rescan
=
resource_type unchanged
```

### Invariant E

```text
notes
+
scanner rescan
=
notes unchanged
```

### Invariant F

```text
机器 writer 的 SQL 不得包含 user-owned columns。
用户 writer 的 SQL 不得写 machine-owned columns。
```

补充断言（Invariant F 落地形式）：

- 扫描 `core/**`、`ui/**`、`main.py`、`cli_query.py` 中所有 `INSERT INTO resources` / `UPDATE resources`：
  只允许出现在 `core/scanner/store.py` 与 `core/app/resource_write.py`。
- `core/scanner/store.py` 的 `resources` 写语句**不含** `display_name` / `notes` / `type_source`。
- `core/app/resource_write.py` 的 SQL **不含** machine 列
  （denylist：`file_path` / `file_path_key` / `relative_path` / `file_size` / `modified_time` /
  `extension` / `sha256` / `card_marker` / `metadata_json` / `name` / `parse_status` /
  `parse_error` / `scan_status` / `last_scanned_at` / `id` / `created_at`）；
  **唯一豁免**：`updated_at`（系统簿记，见 §5.2.1）。
- `ui/**` 不 import `sqlite3`，不直接持 `ResourceQuery` / `LibraryQuery`（沿用既有静态守卫）。

---

## 9. Definition of Done（Phase 3.1）

Phase 3.1 视为完成，当且仅当：

1. `ResourceWriteService` 存在且是**唯一**用户数据 runtime 写入口；
2. `core/scanner/store.py` 不再写 `display_name`（INSERT 与 UPDATE 均无）；
3. effective display name 只有**一份**权威实现，UI 委托 core；
4. read model 以 additive 方式暴露 `type_source`（及 `notes`）；
5. CLI 三个命令 + display name clear 可用，且为薄适配层；
6. §8 Invariant A–F 全部有自动化测试并通过；
7. `SCHEMA_VERSION == 2`，无 migration / 无新表 / 无新列 / 无新索引；
8. 既有测试全绿（基线：734 passed）；
9. 未越界实现 §2 任何 Non-Goal。

---

## 10. 变更控制

```text
1. 本 Contract 冻结后，任何扩大 Phase 3.1 范围的行为必须走
   PHASE3_0_CONTRACT.md §16（评审 + 更新 Contract + 用户确认）。
2. 【FROZEN】决策不得在实现阶段被顺带更改。
3. §2 Non-Goals 不得被「顺手一起做」。
4. 本 Contract 不修改 Phase 3.0 Contract、不修改 Phase 1 / Phase 2 既有契约，
   不重新打开 Phase 3.0，不改动 `phase-3.0-closed` tag。
```

---

## 附录 A — 与上级契约的一致性声明

| 上级条款 | 本 Contract | 一致性 |
| :--- | :--- | :--- |
| Phase 3.0 §2 机器事实 / 用户数据 | §3 Ownership Table | ✅ 未扩大 |
| Phase 3.0 §3.1 display_name 解法 B | §4 | ✅ 逐条落地（含 `==name` 仍为 override） |
| Phase 3.0 §3.2 `resource_type` / `type_source` | §3 / §7 Step 1 | ✅ 沿用既有优先级，不改语义 |
| Phase 3.0 §8 零 schema 变更 | §6 | ✅ 一致 |
| Phase 3.0 §9 单一写服务 | §1 / §5 | ✅ 一致 |
| Phase 3.0 §10 Query Layer 只读 | §2-11 / §5.3 | ✅ 一致 |
| Phase 3.0 §12 In Scope | §1 | ✅ 3.1 为其子集（Tag / Favorite / 查询筛选留给 3.2+） |
| Phase 3.0 §13 Out of Scope | §2 | ✅ 一致，未缩小 |
| 3.0.2 §5.2 写服务落点 `core/app/` | §7 Step 1 | ✅ 一致 |
| 3.0.2 §11（3.1 建议：先解决 display_name 归属、不引入搜索/语法） | §7 / §2-12 | ✅ 一致 |
