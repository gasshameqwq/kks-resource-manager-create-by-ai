# Phase 2.1 Final Closure Report — CLOSED / PASS

> 阶段：**Phase 2.1 — Content Identity Foundation**
> 权威契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`（§5 / §13.3 / §14 / §16 / §18.1）
> 日期：2026-10-07
> schema：**v2**（未改动）· Python 3.11+ / 实测 CPython 3.12.10

## 结论

```text
PHASE 2.1 = CLOSED / PASS
```

无 P0 / P1。`pytest` 685 passed / 0 failed；schema 与 model-sync 校验通过；
范围隔离干净（无 schema / Parser / Query / CLI / GUI 改动）。

---

## 1. 范围与权威契约

Phase 2.1 的范围严格限定为 **Content Identity Foundation**（Phase 2.0-C §16）：
让既有 `resources.sha256` 从「已存在但全仓零写入」变为「扫描重解析时写入文件字节
SHA-256」。**不**引入 Content 实体 / 表，**不**改变 File ≡ Resource 的 1:1 身份模型。

权威契约：`docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`，特别是：

- §5（Content Identity：唯一内容身份 = `resources.sha256`，byte-identical）
- §13.3（C1–C8 不变式）
- §14.2 / §14.3（identity / scanner 验证矩阵）
- §16（Phase 2.1 = Content Identity Foundation）
- §18.1（冻结决定）

---

## 2. 冻结的裁定与决策

| # | 决策 | 值 |
| :-- | :--- | :--- |
| 1 | Phase 2.1 范围 | **Path A**：Content Identity Foundation（非 Resource Management / user-managed metadata） |
| 2 | C7 语义 | **解释 ii**：读取窗口内不稳定 ⇒ 本次解析结果与 sha256 整体不提交，下次扫描重来 |
| 3 | `ResourceStore` 参数 | `sha256: str`（required keyword-only；不用 `None` 默认） |
| 4 | 哈希工具 | 独立文件 `core/scanner/hashing.py` |
| 5 | SHA-256 定义 | 文件**原始字节**的 SHA-256，**64 位小写十六进制**；只表示 byte-identical |
| 6 | 计算时机 | 与解析同频：新增 / `(size, mtime)` 变化 / `mode='full'` |
| 7 | Schema | `SCHEMA_VERSION == 2`，无 v3、无 migration、无新表 |

---

## 3. 实现内容

- **`core/scanner/hashing.py`（新增）**：`sha256_of_file(path, *, chunk_size=1 << 20) -> str`。
  只对文件原始字节做 SHA-256；流式分块（1 MiB）读取；只读；不吞 `OSError`。
- **`core/scanner/scanner.py`**：`_process_file()` 增加 C7 读取窗口；仅 `parsed.success`
  时计算 sha256；把 `sha256` 传入 Store；模块 docstring 同步。
- **`core/scanner/store.py`**：`upsert_card_resource` / `upsert_mod_resource` 增加
  `sha256: str`（required keyword-only），INSERT 与 UPDATE 均写入 `resources.sha256`。
- **`core/scanner/__init__.py`**：导出 `sha256_of_file`；docstring 同步。

写入路径保持 `Scanner → ResourceStore → Database`；GUI / Query / CLI 未涉及。

---

## 4. C7 语义（读取一致性）

读取窗口（`core/scanner/scanner.py`）：

```text
stat_before（size / mtime，函数开头已捕获）
    → parse（parse_card / parse_zipmod，只读）
    → sha256（仅 parsed.success）
    → stat_after
    → 若 size 或 mtime 变化（容差 _MTIME_EPSILON = 1e-6）⇒ 本次整体不提交
```

不稳定窗口触发时：

- 不调用 Store、不开启 / 提交 DB 事务、不写任何 resource 状态；
- 不调用 `mark_parse_failed`；**不增加** `failed`；**不产生** `ScanIssue`；
- 数据库保持本次扫描前状态；下一次扫描因 `(size, mtime)` 仍不一致而重新处理；
- **不加锁 / 无 watcher / 无自动 retry**。

与之区分：哈希读取或 re-stat 抛 `OSError` ⇒ 走**既有 IO failure 语义**
（`failed += 1` + `STAGE_IO` issue），不与 C7 混淆。

---

## 5. 不变式（Phase 2.0-C §13.3）

- **C1** Content 是派生值，无表、无 ID。
- **C2** `resources.sha256` = 文件精确字节的 SHA-256，64 位小写十六进制。
- **C3** sha256 只与同一次读取的 `file_size` / `modified_time` 一起写。
- **C4** sha256 相等仅表示 byte-identical。
- **C5** `quick_hash` / `content_key` 不写、不读、不删。
- **C6** 哈希只来自文件字节（不掺 path / name / metadata / dataID）。
- **C7 / C8** 读取窗口内 `(size, mtime)` 变化 ⇒ 本次 hash 与解析结果整体不提交。
- **S1 / S2 / S3** 增量门不变；hash 当且仅当 (re)parse；全程只读。

---

## 6. 测试与验证

| 验证 | 命令 | 结果 |
| :--- | :--- | :--- |
| 全量回归 | `.venv\Scripts\python.exe -m pytest -q` | **685 passed**（基线 671 + 新增 14），0 failed |
| Schema | `node tools/validate_schema.mjs` | 全 OK（16 表 / FTS / 约束 / 级联） |
| Model sync | `node tools/check_model_sync.mjs` | ✅ schema ↔ models 一致 |

新增测试 `tests/test_content_identity.py`（14 例）覆盖：

- **Identity**：新卡 / 新 zipmod sha256 正确；64 位小写 hex；同 bytes 同 hash；异 bytes 异 hash；
  `sha256_of_file` 对齐 `hashlib`。
- **Scanner**：新增计算；`(size, mtime)` 变化重算；`mode='full'` 重算；
  未变化增量**不读不算**（monkeypatch 断言未被调用）。
- **C7**：新资源不稳定 ⇒ 无行、`failed==0`、无 issue、下次可处理；
  既有资源不稳定 ⇒ size / mtime / sha256 保持旧值。
- **Schema**：`SCHEMA_VERSION==2`、`MIGRATIONS=={1,2}`、`MIGRATION_ADDED_COLUMNS` 不变、16 表。
- **真实样本**：样本每行 sha256 == 现场 `hashlib.sha256`（只读）。

---

## 7. 两项非阻塞测试覆盖缺口

以下两项为**测试表达力 / 覆盖**缺口，**不构成实现缺陷**，按 Final Closure 决定不修复：

1. **同 size / 不同 bytes 未显式隔离**：`test_different_bytes_yield_different_sha256`
   使用 `Alpha`(618B) vs `Beta`(616B)，属「不同 bytes 且 size 不同」。同 size 反例
   （`Alpha` vs `Bravo`，均 618B）尚未断言。SHA-256 实现已与 `hashlib` 对齐，正确性不受影响。
2. **无 `OSError` / IO failure 测试**：Phase 2.1 的 IO failure 分支（hash 读取失败 /
   `stat_after` 失败）行为正确但无自动化用例；属 Phase 1 起既有的覆盖缺口。

---

## 8. Phase 2.1 的实际文件变更

| 文件 | 类型 |
| :--- | :--- |
| `core/scanner/hashing.py` | 新增 |
| `core/scanner/scanner.py` | 修改 |
| `core/scanner/store.py` | 修改 |
| `core/scanner/__init__.py` | 修改 |
| `tests/test_content_identity.py` | 新增（14 例） |
| `docs/phase2/PHASE2_1_LOG.md` | 新增（工作日志） |
| `docs/phase2/PHASE2_1_CLOSURE_REPORT.md` | 新增（本报告） |

---

## 9. Schema 与范围隔离

- `SCHEMA_VERSION == 2`；`MIGRATIONS == {1, 2}`；`MIGRATION_ADDED_COLUMNS == {2: card_marker}`。
- **无** schema.py 修改；业务表仍为 **16**；沿用既有 `resources.sha256` + `idx_resources_sha256`。
- **未修改** Parser / Query / CLI / GUI；**未**实现 sha256 surfacing；
  **未**实现 duplicate 查询 / groups；**未**实现 Tags / Collections；
  **未**进入 Phase 2.2 / 2.3 / 2.4。
- **未**引入 `quick_hash` / `content_key` 的读写；**未**新增 content / file / duplicate 实体或表。

---

## 10. Phase 1 行为保持

- 原 671 项测试全部通过（685 = 671 + 14）。
- 增量门 `(file_path_key, file_size, modified_time)` 不变；skip 路径不读文件、不算 hash。
- 失败隔离 / 单文件事务 / `mark_missing` / 关系先删后插 / 作者规则均保持。
- user-owned 字段（`display_name` / `notes` / `type_source`）逻辑未被触碰。
- 真实样本 `sample_root` 会话前后 sha256 一致的只读不变量继续成立。

---

## 11. Git 状态

- 分支：`main`
- 起点 HEAD：`93218bd`（`docs: close phase 2.0 design baseline`，tag `phase-2.0-closed`）
- Phase 2.1 closure commit 与 annotated tag `phase-2.1-closed`：见本提交（tag 指向它）。
- working tree：closure 提交后为 clean。

---

## 12. Non-Scope（本阶段未做）

duplicate 查询 / `GROUP BY sha256` / duplicate groups、Query / CLI / GUI 的 sha256 surfacing、
Tags / Collections / 备注 / 收藏 / user-managed metadata、Resource Management API / GUI、
schema v3 / migration、Phase 2.2 / 2.3 / 2.4、remote / push。

---

## 13. 结束条件核对

| 结束条件 | 状态 |
| :--- | :--- |
| Phase 2.1 范围（Content Identity Foundation）实现 | ✅ |
| C7（解释 ii）在代码中成立 | ✅ |
| 685 passed / 0 failed | ✅ |
| `validate_schema.mjs` / `check_model_sync.mjs` 通过 | ✅ |
| 16 表 / `SCHEMA_VERSION == 2` / 无 migration | ✅ |
| 范围隔离（无 Parser / Query / CLI / GUI / duplicate / tags 改动） | ✅ |
| Phase 1 行为未回归 | ✅ |
| closure commit + annotated tag `phase-2.1-closed` | ✅ |
| working tree clean | ✅ |
