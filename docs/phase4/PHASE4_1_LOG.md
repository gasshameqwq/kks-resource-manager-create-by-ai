# Phase 4.1 — Query Model 扩展与 CLI 闭环实施日志

> 状态：实施完成（待独立审核与用户验收）
>
> 日期：2026-10-24
>
> 契约：[PHASE4_0_CONTRACT.md](./PHASE4_0_CONTRACT.md)（FROZEN）

---

## 1. 实施依据与基线

- 长期协作规范：`docs/WORKFLOW.md`
- 当前状态：`docs/PROJECT_STATE.md`
- 冻结契约：`docs/phase4/PHASE4_0_CONTRACT.md`
- 实施开始 HEAD：`97f3b28`
- Phase 3.5 既有测试基线：982 passed
- schema：v2 / 16 张业务表 / migrations `{1, 2}`
- 环境：`.venv` / Python 3.12.10

---

## 2. 计划变更

| 文件 | 目的 |
| :--- | :--- |
| `docs/phase4/PHASE4_0_CONTRACT.md` | 冻结本阶段目标、边界与验收标准 |
| `docs/phase4/PHASE4_1_LOG.md` | 记录实施过程与实际验证证据 |
| `core/duplicate/__init__.py` | 移除过期 `content_key` / Phase 4 描述，声明纯只读与零写入 |
| `core/query/model.py` | `ResourceFilter` 扩展至 17 字段并归一化新条件 |
| `core/query/browse.py` | `BrowserScope` 增加两键，`FILTER_KEYS` 扩展至 16 |
| `core/query/queries.py` | 增加哈希与重复状态只读 SQL 条件 |
| `cli_query.py` | 增加重复、哈希、作者筛选及 not-found 行为 |
| `tests/test_query_duplicate_filter.py` | 聚焦测试 Query / CLI / 只读不变量 |
| `tests/test_query_model.py` | 更新 17/16 字段与键集断言 |

---

## 3. 实施记录

### 3.1 Query Model / Browse

- `ResourceFilter` 从 15 字段扩展为 17 字段。
- `has_duplicates` 仅接受 `None` / `bool`，非法值抛 `ValueError`。
- `sha256` 去除首尾空白，空串归一为 `None`。
- `BrowserScope` 增加对应字段，`FILTER_KEYS` 从 14 键扩展为 16 键。

### 3.2 Query Layer

- `ResourceQuery.count()` / `list()` 增加 keyword-only 的
  `has_duplicates` / `sha256` 参数并传导至 `_resource_where()`。
- `sha256` 使用参数化精确匹配。
- `has_duplicates=True` 使用 `r.sha256 IS NOT NULL` 与相关 `EXISTS`。
- `has_duplicates=False` 使用 `r.sha256 IS NULL OR NOT EXISTS (...)`，
  因此空哈希资源归入非重复集合。
- 只读查询计划实测：

  ```text
  SEARCH r USING COVERING INDEX idx_resources_sha256 (sha256>?)
  CORRELATED SCALAR SUBQUERY 1
  SEARCH r2 USING COVERING INDEX idx_resources_sha256 (sha256=?)
  ```

### 3.3 CLI

- `query resources` 增加互斥的 `--has-duplicates` / `--no-duplicates`。
- 增加 `--sha256` 与 `--author`。
- 作者纯数字输入按 id 解析，其他输入使用 `find_by_name()` 精确查找；
  数字 id 未命中时不回退为同名搜索。
- 作者未命中输出 `Author not found: <name>` 到 stderr，退出码 1，
  且测试确认未调用 `ResourceQuery.list()`。
- JSON `scope` 只输出实际提供且归一后非 `None` 的新条件。

### 3.4 文档与注释

- 冻结契约已落盘，状态为 **FROZEN**。
- `core/duplicate/__init__.py` 已移除过期 `content_key` / Phase 4 实现描述，
  明确纯只读派生与两张重复表零写入。

### 3.5 范围偏差记录

`tests/test_browse.py` 的既有断言仍硬编码 `14` 键 scope / `15` 键模型；该文件不在
用户列出的允许修改清单中。为满足同一任务要求的“既有 982 项全部通过”，实际只同步了
该测试中的 14→16、15→17 计数及对应 docstring，没有改变产品行为或新增测试要求。
此偏差应由独立审核确认。

---

## 4. 测试证据

环境：`.venv` / Python 3.12.10 / pytest 9.1.1。

### 4.1 聚焦测试

实际 CLI 测试文件名为仓库既有的 `tests/test_query_cli.py`；任务指令中的
`tests/test_cli_query.py` 在仓库中不存在。实际运行：

```text
python -m pytest tests/test_query_duplicate_filter.py tests/test_query_model.py tests/test_query_cli.py tests/test_browse.py -v
```

结果：

```text
147 passed in 17.63s
exit code 0
```

### 4.2 只读护栏

```text
python -m pytest -q -k "read_only or do_not_write or duplicate_groups"
```

结果：

```text
22 passed, 973 deselected in 11.84s
exit code 0
```

### 4.3 全量回归

```text
python -m pytest -q
```

结果：

```text
995 passed in 91.18s (0:01:31)
exit code 0
```

`995 = 既有 982 + 新增 13`，0 failed / 0 skipped。

### 4.4 持久库只读核验

- `app_meta.schema_version = '2'`
- `duplicate_groups = 0`
- `duplicate_members = 0`
- 业务表定义仍为 16 张（测试 `test_schema_stays_v2` 通过）

---

## 5. 数据安全与 Git 边界

- 未修改任何卡片或 MOD 文件。
- 未修改 schema / DDL / migration。
- 聚焦测试与持久库只读核验均确认
  `duplicate_groups` / `duplicate_members` 保持零写入。
- 未修改 `ui/`。
- 未执行 commit、tag 或 push。

最终状态以测试完成后的工作区检查为准。
