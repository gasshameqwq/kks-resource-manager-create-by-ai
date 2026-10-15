# Phase 3.3 — Implementation Log（Search & Query Foundation）

> 文档类型：**Implementation Log**（过程与实测记录；不构成契约，不替代验收结论）。
> 依据：`docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md`（**FROZEN**，2026-10-13）
> · `docs/WORKFLOW.md` §2 / §3 / §7 / §8 · `docs/PROJECT_STATE.md` §4。
> 本文件是**实施轮**授权范围内唯一新增的文档产物（契约 §10.1 末行 / §11 Step 8）。
> **不创建** Closure Report；**不执行**任何 Git 写操作；**不关闭**本阶段。

---

## 1. 实施前基线

| 项 | 值 | 证据 |
| :--- | :--- | :--- |
| HEAD（实施前） | `26a73c27cc03833adeeb0fc546e08f778ab57eed` | `git rev-parse HEAD` |
| 分支 | `main` | `git branch --show-current` |
| 工作区（实施前） | 干净（`git status --short` 无输出） | `git status --short` |
| Phase 3.2 | CLOSED / PASS（`phase-3.2-closed` → `034a726`） | `git for-each-ref`（peel 后） |
| `phase-3.3-closed` | **不存在** | `git tag -l 'phase-3.3*'` |
| schema | `SCHEMA_VERSION == 2` / `MIGRATIONS == {1, 2}` / 16 张业务表 | `core/database/schema.py` |
| 历史测试参考基线 | `883 passed`（**参考值，非本轮门槛**） | `PROJECT_STATE.md` §1 |
| 持久工作库 | 实施轮**未打开**（WAL 库，避免触碰 `data/*.db-shm`）；所有验证均在临时库中进行 | 见 §5 |

---

## 2. 实施范围与边界

严格按冻结契约执行，未扩大范围：

```text
允许（契约 §10.1）：core/query/model.py（新增）· core/query/queries.py ·
                    core/query/browse.py · core/query/__init__.py ·
                    cli_query.py（仅 query resources）· 测试文件 ·
                    docs/phase3/PHASE3_3_LOG.md（本文件）
禁止（契约 §10.2）：core/database/** · core/scanner/** · core/parsers/** · core/app/** ·
                    core/models/tags.py · core/query/search.py · ui/** · main.py ·
                    docs/**（本 LOG 除外）· 既有测试断言语义
本轮额外禁止（用户指令）：commit / tag / push / amend / 历史重写 / 工作区清理 /
                    Closure Report / Phase 3.4 及以后内容 / 修改冻结契约
```

---

## 3. 实际变更文件

```
 M cli_query.py                       (58 insertions,  3 deletions)
 M core/query/__init__.py             ( 3 insertions,  0 deletions)
 M core/query/browse.py               (57 insertions, 15 deletions)
 M core/query/queries.py              (30 insertions,  0 deletions)
 M tests/test_browse.py               (90 insertions,  0 deletions)
 M tests/test_query_cli.py            (194 insertions, 1 deletion)
?? core/query/model.py                (新增，113 行；splitlines() 口径)
?? tests/test_query_model.py          (新增，622 行；splitlines() 口径)
?? docs/phase3/PHASE3_3_LOG.md        (新增，获准新增的 Phase 3.3 实施日志；未跟踪)
```

（上表 `M` 行数字来自 `git diff --numstat`。`??` 行为**未跟踪**的新增文件，
**不计入** `git diff --stat` / `git diff --numstat` 的统计（二者只统计 tracked 文件），
只在 `git status --short` 中显示，故此处单独登记。）

> 行数口径说明：`113 行` / `622 行` 均为 `splitlines()` 口径（空行计入），
> 与契约 §19 记录自身行数所用口径一致。其它工具的口径不同 —— 例如
> `Get-Content | Measure-Object -Line` 不统计空行，会分别得到 91 / 492。
> 该差异属**工具统计口径差异**，不是文件内容或行数事实的差异。

**未触碰**（`git diff --stat` 输出为空，已实测）：`core/database`、`core/scanner`、
`core/parsers`、`core/app`、`core/models/tags.py`、`core/query/search.py`、`ui/`、
`main.py`、`docs/`。冻结契约文件本身**未被修改**。

---

## 4. 实施步骤（契约 §11）

| Step | 内容 | 结果 |
| :--- | :--- | :--- |
| 1 | `core/query/model.py`：frozen `ResourceFilter`（15 字段）+ `to_params()` + §4.4 校验 | 完成 |
| 2 | `core/query/queries.py`：`_resource_where` 追加 `tag_id` / `favorite` 两个子句；`count` / `list` 末尾追加两个 keyword-only 参数（默认 `None`） | 完成 |
| 3 | `core/query/browse.py`：`BrowserScope` 追加 `tag_id` / `favorite`（置于筛选字段末尾）+ `FILTER_KEYS`（14）+ `to_filter()`；`filters()` 改为投影 | 完成 |
| 4 | `core/query/__init__.py`：导出 `ResourceFilter` | 完成 |
| 5 | `cli_query.py`：`query resources` 追加 `--tag` / `--favorite` / `--no-favorite` | 完成 |
| 6 | 测试：新增 `tests/test_query_model.py`；在 `test_browse.py` / `test_query_cli.py` 追加用例 | 完成 |
| 7 | 验证：focused → 全量 pytest → schema → 只读护栏 → `git diff --check` | 完成（见 §5） |
| 8 | 文档：仅本文件 `docs/phase3/PHASE3_3_LOG.md` | 完成 |

### 4.1 关键实现事实（供审核核对）

- `ResourceFilter.__post_init__` 校验：`tag_id` 拒绝 `bool`（即使 `bool` 是 `int` 子类）
  与其它非 `int` 值；`favorite` 只接受 `None` / `True` / `False`；其余字段不新增校验。
- 新增条件 SQL（仍只由 `_resource_where` 构造，唯一条件构造点）：

```sql
-- tag_id
EXISTS (SELECT 1 FROM resource_tags rt
        WHERE rt.resource_id = r.id AND rt.tag_id = ?)

-- favorite = True / False
EXISTS / NOT EXISTS (SELECT 1 FROM resource_tags rt
        JOIN tags t ON t.id = rt.tag_id
        WHERE rt.resource_id = r.id AND t.name_key = ?)   -- 参数 = FAVORITE_TAG_KEY
```

  新子句中**唯一**的 f-string 插值是常量关键字 `EXISTS` / `NOT EXISTS`
  （与既有 `has_mods` / `has_missing_mods` 的同一写法）；所有用户可控值
  （`tag_id`、`FAVORITE_TAG_KEY`）均以绑定参数 `?` 传入。
  未新增 `favorites` 表 / 收藏列；未修改 `core/query/tag_queries.py`。
- CLI 只从 `ResourceFilter(...).to_params()` 中取 `tag_id` / `favorite` **两项**再与既有
  参数合并（未整表展开 15 键）；`--tag` 名称解析只发生在 CLI 层（`TagQuery.find_by_name`）。
- `BrowserScope.filters()` 为 `{key: params[key] for key in FILTER_KEYS}` 投影，
  **不是** `to_params()` 展开、也不是手写 14 项字典；`FILTER_KEYS` 为 `ClassVar`（非 dataclass 字段）。

---

## 5. 实际执行的命令与真实输出

### 5.1 focused → 相关模块回归

```
> .venv\Scripts\python.exe -m pytest tests/test_query_model.py -q
42 passed in 1.31s

> .venv\Scripts\python.exe -m pytest tests/test_query_cli.py -q
37 passed in 4.53s

> .venv\Scripts\python.exe -m pytest tests/test_browse.py -q
54 passed in 4.52s

> .venv\Scripts\python.exe -m pytest tests/test_query_model.py tests/test_query_cli.py
  tests/test_browse.py tests/test_tag_query.py tests/test_tag_write.py
  tests/test_ownership_guard.py tests/test_query_surfacing.py tests/test_query_layer.py
  tests/test_gui_filters.py tests/test_read_model_exposure.py -q
277 passed in 14.91s
```

### 5.2 全量测试（真实输出）

```
> .venv\Scripts\python.exe -m pytest -q
........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
........................................................................ [ 30%]
........................................................................ [ 38%]
........................................................................ [ 46%]
........................................................................ [ 53%]
........................................................................ [ 61%]
........................................................................ [ 69%]
........................................................................ [ 76%]
........................................................................ [ 84%]
........................................................................ [ 92%]
........................................................................ [ 99%]
..                                                                       [100%]
938 passed in 46.84s
```

- 环境：Python 3.12.10 · pytest 9.1.1（`.venv`）。
- **0 failed / 0 error / 0 skipped。**
- 复核：在完成全部改动（含最后的 import 顺序整理）后**再次**运行同一命令，
  结果为 `938 passed in 44.30s`（两次独立运行、同一用例数、0 failed）。
- 与历史参考基线（`883 passed`）的差异 = **+55 个新增用例**
  （`tests/test_query_model.py` 42 + `test_query_cli.py` 9 + `test_browse.py` 4），
  无既有用例被删除或语义改写。`883 passed` **未**被当作本轮门槛。

### 5.3 schema 不变性 / Query 层只读 / CLI 层只读（临时库实测）

```
[schema] SCHEMA_VERSION = 2
[schema] MIGRATIONS = [1, 2]
[schema] business tables = 16
[schema] MIGRATION_ADDED_COLUMNS = {2: (('resources', 'card_marker', 'TEXT'),)}
[query] ids tagged = [1, 2]
[query] ids favorite = [2, 3] count = 2
[query] ids non-favorite = [1, 4] count = 2
[query] count(tag_id) = 2 count(tag_id, favorite) = 1
[query] page.total = 2 == count: True
[query] tagged == TagQuery.resource_ids: True
[query] favorite True == TagQuery.favorite_resource_ids: True
[query] total_changes before/after: 34 34 unchanged: True
[query] to_params keys = 15
[query] filters() keys = 14
[cli] exit codes = [0, 0, 0, 0, 0, 1]
[cli] empty-result text contains (no results): True
[cli] tag not found on stderr: True
[cli] stdout empty for not-found case: True
[cli] db sha256 unchanged: True | 79b69a79563c2a1f0b4556196cafdbf0fe1504ccd9f98186be5e256653866c42
[cli] tags still: [('Alpha', 'alpha'), ('Favorite', 'favorite')]
[cli] favorite rows: [2, 3]
```

CLI 用例序列：
`--tag Alpha` · `--tag alpha --json` · `--favorite` · `--no-favorite --json` ·
`--tag Alpha --type mod`（空结果）· `--tag Nope`（not found）。

> 只读性证据**按测量层区分**（契约 §8 / N5）：
> **Query 层**用**已打开连接**的连接级 `total_changes` 不变（34 → 34）；
> **CLI 层**用**数据库文件 SHA-256** 不变。
> CLI 启动时的 `database.initialize()` 属**既有启动行为**，不作为筛选写入的证据。
> 验证全程在 `tempfile.mkdtemp()` 临时目录内进行（`KKS_RM_DATA_DIR` 重定向），
> 结束后已删除；**未打开**仓库内持久工作库 `data/kks_resource_manager.db`。

### 5.4 `git diff --check`

```
> git diff --check
warning: in the working copy of 'cli_query.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/query/__init__.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/query/browse.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/query/queries.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_browse.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_query_cli.py', LF will be replaced by CRLF the next time Git touches it
(exit code 0 —— 无空白错误 / 无冲突标记)
```

> 说明：上述 LF/CRLF 提示是仓库既有环境行为（`core.autocrlf=true`，且工作副本中
> **包括未被修改的** tracked 文件同样是 LF 结尾），**不是**本轮引入的行尾变更；
> `git diff --numstat` 显示改动为行级小范围，不存在整文件重写。

### 5.5 结构性护栏（契约 T-K / T-L 的静态部分）

```
> git diff --stat -- core/database core/scanner core/parsers core/app core/models/tags.py core/query/search.py ui main.py docs
(空输出)                        ⇒ 禁止修改清单与 docs/** 均未被触碰

> rg -n 'resource_tags' core/query/queries.py
366:            "EXISTS (SELECT 1 FROM resource_tags rt"
377:            f"{exists} (SELECT 1 FROM resource_tags rt"
（完整输出，共 2 行）

> rg -n 'name_key' core/query/queries.py
372:        # ``TagQuery.is_favorite()`` 保持一致（同为 JOIN ``tags t`` + ``name_key``），
379:            " WHERE rt.resource_id = r.id AND t.name_key = ?)"     ⇒ 本阶段新增子句的绑定参数
658:            is_favorite=any(tag.name_key == FAVORITE_TAG_KEY for tag in tags),
1076:        key = database.normalize_name_key(name)
1080:            self.conn, "SELECT id FROM authors WHERE name_key = ?", [key]
（完整输出，共 5 行：372 / 379 / 658 / 1076 / 1080。其中仅第 379 行属本阶段新增，
658 / 1076 / 1080 为既有代码，与本阶段无关。）

> rg -c 'sqlite3' cli_query.py     → 无匹配（退出码 1）
> rg -n 'resource_tags' cli_query.py → 无匹配（退出码 1）

> rg -n '\b(AND|OR|NOT|field:value)\b' core/query/model.py core/query/browse.py
（无匹配，退出码 1）
（修订说明：原记录使用的无词边界模式 `'field:value|AND|OR|NOT'` 实际会命中
 `core/query/model.py:68` 一处**假阳性**（`OR` 命中 `FAVORITE` 的子串），
 故本条改用词边界模式，并如实记录无匹配与退出码 1。
 本检查**仅**说明这两个指定文件中不存在匹配的**独立词项**，
 **不构成**完整的 SQL 语法分析，也不扩大任何结论；「不存在 field:value / 布尔语法
 解析器」的实质结论另由「无 parser API」「`core/query/search.py` 零改动」与
 T-L 的运行时用例共同支撑。）
```

由测试套件自动化的结构断言（本轮全部通过）：
`tests/test_query_surfacing.py::test_query_layer_has_no_write_statements`（逐文件扫描
`core/query/*.py`）、`::test_browse_has_no_own_sql`、`tests/test_query_cli.py::test_cli_has_no_sql_and_no_sqlite_access`、
`tests/test_browse.py::test_browse_module_has_no_sql_and_no_preview`、
`tests/test_ownership_guard.py`（writer allowlist 不变、UI/CLI 不连库）。

---

## 6. T-A … T-S 逐项证据映射

| 不变式 | 证据位置 | 结论 |
| :--- | :--- | :--- |
| T-A | `test_query_model.py::test_resource_filter_is_frozen_and_has_fifteen_params` / `::test_resource_filter_fields_match_query_signatures`（frozen 赋值抛 `FrozenInstanceError`；`to_params()` 键集 = 15 字段 = `count` 参数面） | ✅ |
| T-B | `::test_empty_filter_is_equivalent_to_no_conditions`（`list(**ResourceFilter().to_params())` 与 `list()` 逐行同 id）、`::test_to_params_expands_into_list_call` | ✅ |
| T-C | `::test_tag_id_filter_matches_tag_query_resource_ids`（显式 `order_by="id"`, `descending=False`）；实测 `tagged == TagQuery.resource_ids` | ✅ |
| T-D | `::test_tag_id_rejects_non_int_values`（含 `True`/`False`）、`::test_tag_id_accepts_none_and_int`、`::test_unknown_or_non_positive_tag_id_yields_empty_result`（0 / -1 / 999999） | ✅ |
| T-E | `::test_favorite_rejects_non_bool`、`::test_favorite_accepts_none_true_false`、`::test_favorite_true_and_false_match_tag_query`（`favorite=True` == `favorite_resource_ids()`；`True` + `False` == 全集） | ✅ |
| T-F | `::test_favorite_filter_without_system_tag_bootstrap`（空 `tags` 表：`True` ⇒ 空、`False` ⇒ 全集、`total_changes` 不变、`tags` 计数仍 0） | ✅ |
| T-G | `::test_new_conditions_combine_with_existing_ones_as_and`；CLI 侧 `test_query_cli.py::test_query_resources_new_filters_combine_with_existing_ones_as_and` | ✅ |
| T-H | `::test_count_matches_list_under_new_filters`、`::test_browse_page_total_matches_scope_filters`（`page.total == count(**scope.filters())`，`sum(len(items)) <= total`） | ✅ |
| T-I | `::test_pagination_and_sorting_unchanged_under_new_filters`、`::test_illegal_order_by_still_raises_under_new_filters`（`ValueError`） | ✅ |
| T-J | `::test_new_filters_do_not_write` / `::test_new_filters_leave_all_tables_untouched`（连接级 `total_changes`）、`::test_new_filters_go_through_read_only_guard_and_bind_parameters`（spy `_execute_select`：仅 `SELECT`/`WITH`、含 `resource_tags` + `name_key`、语句文本不含 `favorite` 字面量）、`test_browse.py::test_page_with_new_filters_does_not_write`、`test_query_cli.py::test_query_resources_new_filters_do_not_modify_database`（SHA-256 + Tag 集合不变） | ✅ |
| T-K | 运行时部分：`::test_sql_metacharacter_input_is_inert`（标签名 `a'b%_" OR 1=1 --`、检索词 `%'` 均不改变结果集、不报错）；结构部分：§5.5 的代码审查证据（唯一条件构造点、绑定参数） | ✅ |
| T-L | 运行时部分：既有搜索/FTS 全量用例全绿（含 `test_search_core.py` / `test_gui_filters.py`，`search.py` **零改动**）；结构部分：§5.5（`core/query` 内无语法解析器、无 `field:value`/AND/OR/NOT） | ✅ |
| T-M | `::test_dto_field_sets_are_unchanged`（`ResourceSummary` / `ResourceDetail` / `TagSummary` 字段名逐项不变）、`::test_list_rows_gain_no_tag_columns` | ✅ |
| T-N | `::test_schema_stays_v2` + §5.3 实测（`2` / `{1,2}` / 16 表 / `MIGRATION_ADDED_COLUMNS` 不变） | ✅ |
| T-O | 既有 CLI 用例（`test_query_resources_and_filters` 等）全绿未改；`test_query_cli.py::test_query_resources_scope_only_lists_provided_filters`（未提供新参数时 `scope` 不含新键；提供时 `scope == {"tag_id":…, "favorite":True}`） | ✅ |
| T-P | `::test_query_resources_tag_matches_query_layer`（精确 `name_key`、与 Query 层同结果）、`::test_query_resources_tag_accepts_casing_and_exact_name_only`（大小写不敏感；`Alph` / `Alpha%` 不命中）、`::test_query_resources_tag_not_found_is_not_traceback`（`Tag not found: <name>` 到 stderr、exit 1、stdout 空含 `--json`、空/纯空白同名处理） | ✅ |
| T-Q | `test_query_model.py::test_scope_filters_are_a_projection_of_model_params` / `::test_empty_scope_filters_have_all_fourteen_keys` / `::test_filter_keys_is_a_class_constant_not_a_field`；`test_browse.py::test_scope_filters_project_model_params_exactly`（恰 14 键、逐键值等于 `to_params()` 同名键、**且** `filters() != to_params()`） | ✅ |
| T-R | `::test_filters_keys_and_model_keys_are_valid_query_params`；`test_browse.py::test_scope_model_keys_are_accepted_by_query_layer`；既有 `test_browse.py::test_scope_filters_are_a_single_conversion_point` **未修改**且通过 | ✅ |
| T-S | `test_query_cli.py::test_query_resources_empty_result_with_new_filters_is_success`（文本模式 `(no results)` + exit 0；`--json` 输出 `count=0` / `resources=[]` + exit 0）；§5.3 实测 `(no results)` 为 `True` | ✅ |

---

## 7. DoD 逐项核对（契约 §13）

| # | 要求 | 结论 |
| :-- | :--- | :--- |
| 1 | `ResourceFilter` 为正式、不可变的纯值对象（无 SQL、无 UI 状态） | ✅ `core/query/model.py`；frozen；无 SQL 出口（`test_resource_filter_has_no_sql_or_parsing_surface`） |
| 2 | `ResourceQuery` / `BrowseService` 支持 `tag_id` / `favorite` 只读筛选且语义符合 §6 | ✅ T-C / T-E / T-F / T-G；`BrowseService.page()` 经 `BrowserScope` 进入，签名未变 |
| 3 | 数据流唯一（`BrowserScope` → `ResourceFilter` → `ResourceQuery`），无第二条件构造点 | ✅ `to_filter()` 为唯一字段值映射；`filters()` 仅投影；SQL 仍只在 `_resource_where` |
| 4 | §12 覆盖 T-A 至 T-S 全部不变式，验证方式与性质匹配 | ✅ §6 逐项映射；结构约束用代码审查证据，未引入源码文本匹配测试 |
| 5 | `SCHEMA_VERSION == 2`，无 migration / 新表 / 新列 / 新索引 | ✅ §5.3 实测 |
| 6 | 全量测试实际运行并记录；未修改既有断言语义 | ✅ `938 passed`；既有测试文件仅**追加**新用例（`test_browse.py` +4、`test_query_cli.py` +9，均为新增函数；`test_query_cli.py` 的既有函数体未改动，import 行仅新增符号） |
| 7 | 未引入文本语法 / 布尔组合 / 多标签 / 新 DTO 字段 / 新 GUI 控件 | ✅ `ui/**` 零改动；DTO 字段集不变；`--tag` 只接受单个名称 |
| 8 | §2 Non-Goals 无一项越界 | ✅ 见 §2 边界核对 |
| 9 | CLI 只读入口按 §3.3 / §3.5 交付，T-O / T-P / T-S 通过 | ✅ 互斥组、`--tag` 名称语义、not-found exit 1、`scope` 只增提供的键 |
| 10 | `filters()` 为投影实现；T-Q / T-R / T-C 通过 | ✅ |

---

## 8. 偏差、未解决问题与风险

**偏差**：无功能性偏差；实施严格落在契约 §10.1 的文件清单内。

**未解决 / 未验证事项（如实登记）**：

1. 契约 §18 的 U1–U5 证据缺口**仍然开放**（持久库 `resources=0`）；本轮的
   `tag_id` / `favorite` 筛选**仅在合成库与真实样本库上验证**，
   **不构成**「单 Tag 筛选足以覆盖真实组织需求」的证据。
2. §4.6 登记的待核实项「`game` + `card_marker` 同时提供产生两个 AND 子句的设计意图」
   **未处理**（本阶段按契约保持既有行为）。
3. 性能：新增筛选沿用既有 EXISTS 模式，**未做**基准测试（契约 §2-13 明确排除）。
4. `docs/PROJECT_STATE.md` §6 第 6 行「README / ARCHITECTURE 的 3.3 未冻结陈述」
   登记状态已过期（该两文件已由 `26a73c2` 同步）—— 属**文档治理**事项，
   不在本轮授权范围，**未修改**。
5. 本 LOG 未记录任何 commit / tag / Closure 证据：本轮**无** Git 写操作，阶段**未关闭**。

**风险**：无数据安全风险（新增语句均为只读 `SELECT`，无 schema 变更，无写路径新增）。
兼容性风险已由 T-B / T-Q / T-R / T-O 与全量回归覆盖。

---

## 9. 实施轮边界合规核对

| 禁止项 | 状态 |
| :--- | :--- |
| 修改冻结契约 / 上游契约 / 其它未授权文档 | ✅ 未做（`git diff --stat -- docs` 空） |
| 修改既有测试断言语义 | ✅ 未做（仅追加新用例；既有断言原样通过） |
| 修改 `ui/**` / `main.py` / `core/database` / `core/scanner` / `core/parsers` / `core/app` / `core/models/tags.py` / `core/query/search.py` | ✅ 未做（§5.5 实测空 diff） |
| 引入 Non-Goals 或 Phase 3.4+ 内容 | ✅ 未做 |
| 创建 `PHASE3_3_CLOSURE_REPORT.md` | ✅ 未创建 |
| Git 写操作（add / commit / tag / push / amend / 历史重写 / 清理工作区） | ✅ 未执行 |
| 覆盖实施前已存在的无关修改 | ✅ 实施前工作区干净，无无关修改可覆盖 |
| 关闭 Phase 3.3 | ✅ 未关闭（无验收结论、无 Git 证据、无 Closure） |

**当前状态**：`Implementation Contract → FROZEN` ·
`Phase 3.3 implementation → 已完成（待审核）` · `验收 → 未进行` · `CLOSED → 未达成`。
