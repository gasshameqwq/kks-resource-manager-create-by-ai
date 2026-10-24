# Phase 4.0 / 4.1 — Query 重复与哈希筛选契约

> 文档类型：阶段冻结契约（PHASE CONTRACT）
>
> 状态：**FROZEN**
>
> 冻结日期：2026-10-24
>
> 适用阶段：Phase 4.0 契约落盘、Phase 4.1 Query Model 扩展与 CLI 闭环
>
> 依据：用户于 2026-10-24 明确批准并下达 Phase 4.0 / 4.1 实施任务

---

## 1. 目的

本契约冻结 Phase 4.1 的最小只读查询扩展：

1. 在既有 `ResourceFilter` / `BrowserScope` / `ResourceQuery` 数据流中增加
   byte-duplicate 状态与 SHA-256 精确筛选；
2. 在 `query resources` CLI 中暴露重复状态、哈希与作者筛选；
3. 保持 Phase 3.5 结束时的 982 项回归基线零破坏；
4. 不接入 GUI、不修改 schema、不持久化重复关系、不修改任何用户文件。

Phase 4.2 的 GUI 接入不在本契约范围内。

---

## 2. 基线与数据语义

- 实施基线 HEAD 由开始实施时的 `git rev-parse --short HEAD` 现场核验；
  本契约不把历史阶段文档中的 commit 当作当前 HEAD。
- `SCHEMA_VERSION == 2`；业务表总数保持 16；`MIGRATIONS == {1, 2}`。
- 既有 `resources.sha256` 与 `idx_resources_sha256` 是本阶段唯一哈希事实来源。
- `sha256` 相等只表示文件原始字节完全相同（byte-identical），不表示：
  - 同角色或同逻辑资源；
  - 同 MOD 或同依赖；
  - 可安全删除其中任一文件。
- `sha256 IS NULL` 表示没有可用的字节哈希；该资源不参与重复组，并属于
  `has_duplicates=False` 的集合。
- `duplicate_groups` / `duplicate_members` 是预留表，本轮必须保持零读取依赖与
  零写入；重复状态只在查询时由 `resources.sha256` 派生。
- 不读取、不写入、不清理已废弃的 `content_key`。
- 严禁修改、移动、删除磁盘卡片或 MOD 文件。

---

## 3. 允许变更范围

允许新建：

- `docs/phase4/PHASE4_0_CONTRACT.md`
- `docs/phase4/PHASE4_1_LOG.md`
- `tests/test_query_duplicate_filter.py`

允许修改：

- `core/duplicate/__init__.py`
- `core/query/model.py`
- `core/query/browse.py`
- `core/query/queries.py`
- `cli_query.py`
- `tests/test_query_model.py`
- `tests/test_cli_query.py`

严格禁止：

- 修改 `ui/` 下任何文件；
- 修改 `core/database/schema.py`、DDL 或创建 migration；
- 写入 `duplicate_groups` / `duplicate_members`；
- 修改任何卡片、MOD 或真实样本文件；
- 执行 `git add`、`git commit`、`git tag`、`git push`。

---

## 4. 注释与文档契约

`core/duplicate/__init__.py` 的模块说明必须：

1. 删除过时的「Phase 4 实现」描述；
2. 删除对 `content_key` 的引用；
3. 明确重复分组是 **纯只读派生分组**；
4. 明确 `duplicate_groups` / `duplicate_members` 保持**零写入**；
5. 明确永不自动删除用户文件。

---

## 5. Query Model 契约

### 5.1 `ResourceFilter`

`ResourceFilter` 是 frozen 值对象，不持有连接、不执行 SQL、不提供 SQL 出口。
字段总数从 15 扩展为 **17**，在既有字段末尾追加：

- `has_duplicates: bool | None = None`
- `sha256: str | None = None`

校验与归一化：

1. `has_duplicates` 只接受 `None`、`True`、`False`；其他值抛出 `ValueError`。
2. `sha256` 去除首尾空白；结果为空串时归一为 `None`。
3. `sha256` 只做字符串归一化，不验证十六进制格式，不做大小写转换。
4. `to_params()` 恒返回恰好 17 个键；键始终存在，未启用条件值为 `None`。
5. 字段名与 `ResourceQuery.count()` / `list()` 的 keyword-only 筛选参数逐名一致。

排序与分页不属于 Query Model。

### 5.2 `BrowserScope`

在既有 14 个筛选键之后增加：

- `has_duplicates`
- `sha256`

`BrowserScope.FILTER_KEYS` 必须为恰好 **16** 个键，顺序为既有 14 键后追加上述两键。
`to_filter()` 必须映射这两个属性；`filters()` 必须是模型 17 键在
`FILTER_KEYS` 上的 16 键投影，保留 `card_marker` 不在 GUI scope 中的既有边界。

---

## 6. Query Layer 契约

`ResourceQuery.count()` 与 `ResourceQuery.list()` 均增加 keyword-only 参数：

- `has_duplicates: bool | None = None`
- `sha256: str | None = None`

并原样传导至 `_resource_where()`。SQL 只由该函数构造且始终参数化：

1. `sha256 is not None`：
   - 追加 `r.sha256 = ?`；
   - 参数为传入值。
2. `has_duplicates is True`：
   - 追加 `r.sha256 IS NOT NULL`；
   - 追加
     `EXISTS (SELECT 1 FROM resources r2 WHERE r2.sha256 = r.sha256 AND r2.id != r.id)`；
   - 允许 SQLite 使用 `idx_resources_sha256`。
3. `has_duplicates is False`：
   - 等价于「没有同哈希的其他资源」；
   - 使用 `r.sha256 IS NULL OR NOT EXISTS (...)`，其中 EXISTS 子查询与 True 分支相同；
   - 空哈希资源必须包含在结果中。
4. 多个条件以 AND 组合，不改变既有文本检索、Tag、Favorite 等语义。
5. `count()` 与 `list()` 在同一筛选参数下必须得到一致的作用域基数与成员。

---

## 7. CLI 契约

`query resources` 新增：

### 7.1 重复状态

互斥参数：

- `--has-duplicates`：`dest="has_duplicates"`，值 `True`；
- `--no-duplicates`：`dest="has_duplicates"`，值 `False`；
- 未提供时值为 `None`。

两者同时提供时，由 argparse 以退出码 2 拒绝。

### 7.2 SHA-256

- `--sha256 <hash>`：默认 `None`；
- 经 `ResourceFilter` 进行首尾空白清理与空串转 `None`；
- 结果只用精确相等，不做前缀、模糊或十六进制格式扩展。

### 7.3 作者

- `--author <name_or_id>`：默认 `None`；
- 去除首尾空白后，纯数字输入**优先**按作者 id 解析；
- 非纯数字输入使用 `AuthorQuery.find_by_name()` 精确查找；
- 数字 id 未命中时不得回退为同名查找；
- 未命中时向 stderr 输出 `Author not found: <name>`，退出码 1；
- 未命中分支必须在此前不执行资源查询，stdout 不输出 JSON 或文本结果。

### 7.4 JSON scope

`scope` 沿用「仅输出实际提供且非 `None` 的条件」规则。新增可输出键为：

- `author_id`
- `has_duplicates`
- `sha256`

不得把 `ResourceFilter.to_params()` 的 17 个 `None` 键整体写入 `scope`。

---

## 8. 测试与验收

必须新增或扩充测试覆盖：

1. `ResourceFilter` 为 17 字段、`BrowserScope.FILTER_KEYS` 为 16 键；
2. `has_duplicates` 非法值抛出 `ValueError`；
3. `sha256` 去空白、空串转 `None`；
4. `sha256` 精确过滤；
5. `has_duplicates=True` / `False` 的结果、空哈希归属、count/list 一致性；
6. 新增 CLI 参数与 scope；
7. CLI 作者 id / 名称解析与 not-found 退出；
8. 重复互斥参数退出码 2；
9. 查询前后持久数据库不变，`duplicate_groups` / `duplicate_members` 仍为 0。

验收命令：

```text
pytest tests/test_query_duplicate_filter.py tests/test_query_model.py tests/test_cli_query.py -v
pytest -q -k "read_only or do_not_write or duplicate_groups"
pytest -q
```

必须使用项目 `.venv`。最终期望：

- 针对性测试全部通过；
- 只读护栏全部通过；
- 全量结果为 0 failed / 0 skipped，通过数至少为原 982 + 本轮新增测试数。

---

## 9. 交付边界

本阶段完成代码、测试、契约与实施日志落盘，并提供实际 Git 工作区证据。

本阶段**不**执行 commit、tag、push，也不更新 `docs/PROJECT_STATE.md`；阶段关闭与
Git 收尾须另行授权。

本契约冻结后，若实施需要改变上述语义、范围或验收口径，必须先停止受影响工作并取得
用户明确授权。
