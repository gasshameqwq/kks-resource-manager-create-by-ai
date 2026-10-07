# Phase 2.1 Work Log — Content Identity Foundation

> 性质：**工作日志（过程记录）**，不是冻结契约，也不是正式 Phase 报告。
> 日期：2026-10-07
> 权威契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`（§5 / §13.3 / §14 / §16 / §18.1）
> 范围：Phase 2.1 = **Content Identity Foundation**（Path A 裁定）
> 状态：**实现完成，未提交、未打 tag**；未进入 Phase 2.2。

---

## 0. 本日志的用途

记录 Phase 2.1 这一次工作的**时间线、裁定、变更、证据与状态**，供阶段收尾与后续
（2.2 / 正式报告 / 提交 / 打 tag）参考。本文件**不改变**任何 Phase 1 / Phase 2.0
已封存文档的结论，也不构成新的契约。

---

## 1. 时间线（本次会话）

| 步骤 | 内容 | 产物 |
| :--- | :--- | :--- |
| 1 | 只读 Preflight 审计 + Contract 对齐 | `Phase 2.1 Preflight Review`（对话） |
| 2 | 范围裁定：Path A（Content Identity），非 Resource Management | 用户裁定 |
| 3 | 活基线验证 | pytest 671 passed；两个 node 脚本通过 |
| 4 | Implementation Design（10 节） | `Phase 2.1 Implementation Design`（对话） |
| 5 | 最终决策裁定：`sha256: str` required；独立 `hashing.py` | 用户裁定 |
| 6 | 代码实现 | 见 §3 |
| 7 | 全量验证 | pytest 685 passed；两个 node 脚本通过 |
| 8 | Implementation Report | 见对话（未落盘） |

---

## 2. 冻结的裁定与决策

| # | 决策 | 值 | 来源 |
| :-- | :--- | :--- | :--- |
| 1 | Phase 2.1 的范围 | **Path A**：Content Identity Foundation | 用户裁定 |
| 2 | C7 语义 | **解释 ii**：读取窗口内不稳定 ⇒ 本次解析结果与 sha256 整体不提交，下次扫描重来 | 用户裁定 |
| 3 | `ResourceStore` 参数 | `sha256: str`（required keyword-only；不用 `None` 默认） | 用户裁定 |
| 4 | 哈希工具位置 | 独立文件 `core/scanner/hashing.py` | 用户裁定 |
| 5 | SHA-256 定义 | 文件**原始字节**的 SHA-256，64 位小写十六进制；只表示 byte-identical | 2.0-C §5 |
| 6 | 计算时机 | 与解析同频：新增 / `(size, mtime)` 变化 / `mode='full'`；增量未变不算 | 2.0-C §5.2 |
| 7 | Schema | `SCHEMA_VERSION == 2`，无 v3、无 migration、无新表 | 2.0-C §11.1 |

---

## 3. 变更清单

| 文件 | 类型 | 统计 | 说明 |
| :--- | :--- | :--- | :--- |
| `core/scanner/hashing.py` | 新增 | 新文件 | `sha256_of_file(path, *, chunk_size=1<<20) -> str` |
| `core/scanner/scanner.py` | 修改 | +38 / -1 | C7 读取窗口 + 调用哈希 + 传 `sha256`；docstring |
| `core/scanner/store.py` | 修改 | +16 / -4 | 两个 upsert 增加 `sha256: str` 并写入列 |
| `core/scanner/__init__.py` | 修改 | +5 / -1 | 导出 `sha256_of_file`；docstring |
| `tests/test_content_identity.py` | 新增 | 新文件，14 例 | Phase 2.1 验收测试 |

未改动：`core/database/*`（schema / migration）、`core/parsers/*`、`core/query/*`、
`ui/*`、`main.py`、`cli_query.py`、`core/duplicate/*`、Phase 1 报告、Phase 2.0-C 文档。

---

## 4. 实现要点

- **读取窗口（C7）**：`stat_before`（Scanner 已捕获的 `size`/`modified_time`）→ `parse`
  → `sha256_of_file` → `stat_after`。
  - 触发条件：`size_after != size_before` 或 `|mtime_after - mtime_before| >= 1e-6`。
  - 触发时：不调用 Store、不开事务、不写库、不改 `failed`、不加 `ScanIssue`、
    不调用 `mark_parse_failed`；库中保持既有状态；下次扫描重新处理。
- **IO / OSError**：哈希读取或 re-stat 失败 ⇒ 走**既有 IO 失败语义**
  （`failed += 1` + `STAGE_IO` issue），与 C7 区分。
- **接口扩展**：`upsert_card_resource(..., *, sha256: str, ...)`、
  `upsert_mod_resource(..., *, sha256: str, ...)` —— required keyword-only。
- **Parser 未改**：hash 与 parse 同处一个 stat 前后夹逼的窗口，但各自独立读文件，
  未强制共享 file handle。

---

## 5. 证据（命令与结果）

| 命令 | 结果 |
| :--- | :--- |
| `.venv\Scripts\python.exe -m pytest -q` | **685 passed**（基线 671 + 新增 14），0 failed |
| `node tools/validate_schema.mjs` | 全 OK（16 表 / FTS trigram / 约束 / 级联） |
| `node tools/check_model_sync.mjs` | ✅ schema ↔ models 一致 |
| `git diff --stat` | 3 个已跟踪文件（+59 / -6）+ 2 个新文件 |

环境：CPython 3.12.10（`.venv`）· SQLite 3.49.1 · pytest 9.1.1。

---

## 6. Schema 不变证明

- `SCHEMA_VERSION == 2`（未变）；`MIGRATIONS == {1, 2}`（未变）；
  `MIGRATION_ADDED_COLUMNS == {2: (("resources", "card_marker", "TEXT"),)}`（未变）。
- `git diff --name-only -- core/database core/parsers core/query ui main.py cli_query.py`
  → **空**。
- `validate_schema.mjs` 业务表数量 = **16**（与 Phase 1 一致）。
- 沿用既有 `resources.sha256` 列与 `idx_resources_sha256` 索引；未新增表 / 列 / 索引。

---

## 7. 已知限制 / 风险

1. **同 size + 同 mtime 被替换**的盲区：Phase 1 既有，Phase 2.1 明示不消除。
2. **C7 不进入扫描计数**：只体现在 `discovered` / `parsed`，不落入
   `inserted/updated/skipped/failed`（按「统计口径不变」裁定）。
3. **`upsert_*` 签名变更**：对 Phase 1 Store 接口的必要扩展（已批准）；
   仓库内生产调用点仅 Scanner。
4. **性能**：仅在 (re)parse 时多读一次字节；真实样本 93.7 MB 全量哈希约 0.25 s。
5. `git diff` 的 `LF will be replaced by CRLF` 为 autocrlf 换行提示，非内容改动。

---

## 8. 状态与未做事项

```text
Phase 2.1 实现：完成
Git：未提交、未打 tag（用户未要求）
Phase 2.2 / 2.3 / 2.4：未开始
sha256 surfacing（Query / CLI / GUI）：未做
duplicate 查询 / groups：未做
Tags / Collections / user-managed metadata：未做
```

---

## 9. 相关文件

- 契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`
- 实现：`core/scanner/hashing.py`、`core/scanner/scanner.py`、`core/scanner/store.py`、
  `core/scanner/__init__.py`
- 测试：`tests/test_content_identity.py`
