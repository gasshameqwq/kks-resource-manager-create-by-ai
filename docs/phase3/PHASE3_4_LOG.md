# Phase 3.4 — Implementation Log（User Classification & Search）

> 文档类型：**Implementation Log**（过程与实测记录；不构成契约，不替代验收结论）
> 依据：`docs/phase3/PHASE3_4_IMPLEMENTATION_CONTRACT.md`（**FROZEN**，2026-10-17，
> H2 前冻结提交 `632eb4c`；清洗后对应提交 `7704a98`）
> 日期：2026-10-17
> 范围：IS1 / IS2 / IS4 / IS5；IS6 收尾与 G-3 提交记录见 §9 与 Closure Report。

---

## 1. 实施前基线

| 项 | 值 |
| :--- | :--- |
| 分支（H2 前实施基线） | `main` |
| HEAD（H2 前实施基线） | `632eb4c7dcaa593208c2a52911273896cbb2cef7` |
| 工作区（实施前，H2 前历史记录） | clean |
| 冻结契约 | `FROZEN`（r6 · FROZEN） |
| schema | `SCHEMA_VERSION == 2` / `MIGRATIONS == {1, 2}` / 16 张业务表 |
| 历史测试基线 | `938 passed`（Phase 3.3 日志；**非本轮结果**） |

---

## 2. Step 0 — 八项事实核验（只读）

| # | 核验结论 | 证据 |
| :-- | :--- | :--- |
| 1 | `set_resource_type` 在同一事务写 `resource_type` + `type_source='user'` | `core/app/resource_write.py` 118–130 |
| 2 | Scanner 在 `type_source='user'` 时保留既有类型 | `core/scanner/store.py` 159–160、243–247 |
| 3 | 类型筛选使用 `r.resource_type = ?` | `core/query/queries.py` 295–297 |
| 4 | `display_name` 同时进入 FTS 与 LIKE 检索面 | `core/query/search.py` 58–59、126–132；`core/query/queries.py` 246–256 |
| 5 | `display_name` 更新后由 `resources_fts_au` 同步索引 | `core/database/schema.py` 280–285 |
| 6 | `ResourceFilter` / `BrowserScope` / Tag / Favorite / CLI 均为既有实现 | `core/query/model.py` 26–70；`core/query/browse.py` 54–99；`core/query/queries.py` EXISTS 子句；`cli_query.py` 295–328、712–759 |
| 7 | 三个测试文件此前无 `set_display_name` / `set_resource_type` 用例 | 本轮 `rg` 无命中；缺口 A/B/C 成立 |
| 8 | `ARCHITECTURE.md` 的 D1–D7 与七项审计范围存在待补内容 | 见 §3 |

**结论**：契约 §3.1 的八项事实与当前实现一致；未发现生产缺陷证据。

---

## 3. 七项架构审计（§4.1.1）

| # | 审计项 | 结论与处理 |
| :-- | :--- | :--- |
| 1 | Query Model 与入口 | 已补充 §3 目录树（`core/query/`、`core/app/`）与 §5.4 数据流 |
| 2 | 筛选数据流 / `ResourceFilter` / `BrowserScope` | 已补充 §5.4：BrowserScope → ResourceFilter → ResourceQuery（唯一执行点）；14/15 键区别 |
| 3 | Tag / Favorite 语义 | 已补充 §5.4：`resource_tags` EXISTS；Favorite = 保留系统 Tag，不是 Collection |
| 4 | `resource_type` / `type_source` | 已补充 §4.3③：单列即 effective type；用户修正覆盖该列 |
| 5 | `name` / `display_name` 职责与搜索 | 已补充 §5.3：两者任一命中即命中（OR）；覆盖后旧 `name` 仍可搜到 |
| 6 | FTS / LIKE 路径 | 已补充 §5.3 / §5.4：trigram ≥3 字、1–2 字回退、FTS 不可用回退 |
| 7 | schema / 表 / 索引 | 已补充 §4.4：`resource_tags` PK `(resource_id, tag_id)` 与 `idx_resource_tags_tag` |

**其他章节**：未发现与七项范围或冻结契约直接冲突的内容；范围外历史债务见 §7-6。

---

## 4. 实际变更

### 4.1 测试（仅追加）

| 文件 | 函数 | T-ID |
| :--- | :--- | :--- |
| `tests/test_search_core.py` | `test_display_name_override_searchable_via_fts` | T-A1（FTS 路径） |
| `tests/test_search_core.py` | `test_display_name_override_searchable_via_like_fallback` | T-A1（LIKE 路径） |
| `tests/test_search_core.py` | `test_old_name_still_matches_after_display_name_override` | T-A2 |
| `tests/test_database_schema.py` | `test_fts_index_updates_display_name_on_write` | T-B |
| `tests/test_query_model.py` | `test_user_type_override_filters_by_effective_type` | T-C |

### 4.2 文档

- `docs/ARCHITECTURE.md`：Phase 3.4 基线状态；§2 Favorite 表述；§3 目录树；§4.3③ effective type；§4.4 索引；§5.3 检索面；新增 §5.4 Query Model 数据流；原 §5.4 写入事务顺延为 §5.5；§10 路线图与说明。
- `docs/phase3/PHASE3_4_LOG.md`：本文件。

### 4.3 生产代码

**无变更**（零功能增量路径）。未修改 `core/**`、`cli_query.py`、`main.py`、`ui/**`、schema 或迁移。

---

## 5. 测试执行与真实结果

### 5.1 focused（5 个新用例）

```text
.venv\Scripts\python.exe -m pytest tests/test_search_core.py tests/test_database_schema.py tests/test_query_model.py -q -k "display_name_override or old_name_still_matches or fts_index_updates or user_type_override_filters"
5 passed, 134 deselected in 1.31s
```

### 5.2 全量

```text
.venv\Scripts\python.exe -m pytest -q
943 passed in 52.07s
```

（`943 = 938 历史基线 + 5 新增`；本轮实际执行，非引用历史数字。）

### 5.3 只读护栏

```text
.venv\Scripts\python.exe -m pytest tests/test_query_layer.py tests/test_query_model.py tests/test_search_core.py -q -k "read_only or do_not_write or untouch"
8 passed, 149 deselected in 2.04s
```

### 5.4 schema 断言

```text
SCHEMA_VERSION 2
MIGRATIONS [1, 2]
CURRENT_TABLES 16
```

### 5.5 G-3 提交前复跑（2026-10-17）

```text
.venv\Scripts\python.exe -m pytest tests/test_search_core.py tests/test_database_schema.py tests/test_query_model.py -q -k "display_name_override or old_name_still_matches or fts_index_updates or user_type_override_filters"
5 passed, 134 deselected in 0.19s

.venv\Scripts\python.exe -m pytest -q
943 passed in 43.07s
```

---

## 6. 契约不变量核对

| 不变量 | 结果 |
| :--- | :--- |
| 零 schema 变更 | ✅ `SCHEMA_VERSION == 2`、`{1, 2}`、16 表 |
| DTO 字段集不变 | ✅ 未改 DTO；全量回归通过 |
| Query 只读 | ✅ 只读护栏 8 项通过 |
| 既有筛选 / CLI 输出 | ✅ 全量回归通过 |
| `display_name` 搜索语义不变 | ✅ T-A2 验证旧 `name` 仍命中；未改搜索代码 |
| `--type` 行为不变 | ✅ 未改 CLI |
| Taxonomy 暂缓 | ✅ 未新增定义 |
| 冻结契约未修改 | ✅ 工作区 blob `b7b4ab7…` 与 `HEAD:` 一致 |

---

## 7. 遗留与未验证事项

1. **r6 → 冻结版差异未独立验证**：冻结前契约未跟踪、无 r6 副本；该历史限制继续保留，未因本轮实施而改变。
2. **U1 / U2** 仍为 OPEN（真实组织需求 / GUI 入口偏好），不属本阶段阻断项。
3. **`--type` 未知值静默空结果**：按冻结决定仅记录，未改行为。
4. **性能 benchmark**：Non-Goal，未做。
5. 本轮未修改 `PROJECT_STATE` / `README` 之外的状态内容；IS6 状态同步见 Closure Report。
6. **既有文档漂移（关闭后已处置）**：`docs/PROJECT_STATE.md` §4「Phase 3.3 冻结记录」段
   原先直接以当前状态口吻写「3.3 功能实施尚未开始、阶段未关闭」；实施轮未越界修改，
   登记为范围外待办。2026-10-18 的关闭后文档维护已将该表述限定为冻结时点的历史状态，
   并明确后续 Phase 3.3 已 `CLOSED / CONDITIONAL PASS`；不改变历史记录或 Phase 3.3 结论。
7. **T-A2 未直接断言 `display_name` 最终写入值**：该用例只验证覆盖后旧 `name` 仍命中；
   写服务生效由 T-A1 覆盖，属非阻断的测试独立性改进点。

---

## 8. 边界合规

| 禁止项 | 状态 |
| :--- | :--- |
| 修改生产代码 | ✅ 未做 |
| 修改冻结契约 | ✅ 未做 |
| 修改共享 fixture / 辅助函数 / 既有断言 | ✅ 未做 |
| 新增测试文件 | ✅ 未做 |
| 改变搜索语义 / `--type` / API | ✅ 未做 |
| 新增 schema / 索引 / DTO / Taxonomy | ✅ 未做 |
| 创建 implementation commit | ✅ 已完成（`ef362fd`） |
| 创建 tag（实施轮 / G-3 当时） | ❌ 当时未执行（阶段关闭后已完成，见 §10） |
| push（实施轮 / G-3 当时） | ❌ 当时未执行（阶段关闭后已完成，见 §10） |

---

## 9. G-3 执行记录（H2 前历史记录，2026-10-17）

- 执行前 HEAD：`632eb4c7dcaa593208c2a52911273896cbb2cef7`；工作区 clean；
  冻结契约 blob `b7b4ab7bb311c280b95472b2fa55950cab29aace` 未变。
- focused：`5 passed, 134 deselected in 0.19s`（exit 0）。
- 全量：`943 passed in 43.07s`（exit 0）。
- Implementation commit：`ef362fd19e79a67dd496ef5751393244844131a2`；
  父提交 `632eb4c7dcaa593208c2a52911273896cbb2cef7`；
  message `test(phase3.4): verify display name and effective type behavior`；
  8 files changed，459 insertions(+)，21 deletions(-)。
- 文档状态修正 commit：`9e694cf1573ba744ec26f896fe36413a6ac483ff`
  （`docs(phase3.4): correct finalization status`，3 files，+54/−6）。
- 最终关闭提交：即本报告所在提交（自引用，不内嵌自身 hash）。
- 提交后 `git status --short` 为空；冻结契约 blob 未变。
- Phase 3.4 tag：**阶段关闭时未创建**；push：**阶段关闭时未执行**（后续见 §10）。
- 阶段状态：**CLOSED / CONDITIONAL PASS**（2026-10-18）；非阻断事项见 Closure Report。

---

## 10. Post-Closure Publication（H2 前发布记录，2026-10-18）

阶段关闭后完成的 tag/push 操作，不改变 `CLOSED / CONDITIONAL PASS` 结论：

> 本节保留 H2 前的已执行记录，不替换其中任何 commit/tag 值。H2 之后远端同名
> tag 已重写；当前远端 refs 的对照见 §11 和 Closure Report 的 H2 小节。

- Tag：`phase-3.4-closed`（annotated）
- Tag object：`0cae547c7c21cc1a754b147726f022a3396d38c3`
- Peeled commit：`6553333f832de03468af7945294002ba37d040ef`
- Remote：`origin` → `https://github.com/gasshameqwq/kks-resource-manager-create-by-ai.git`
- Push：已完成（仅推送 `refs/tags/phase-3.4-closed`）
- Remote verification（H2 前，2026-10-18）：当时 `git ls-remote` 返回相同 tag
  object 与 peeled commit

---

## 11. H2 清洗前后对象对照（2026-10-21）

本节补充 H2 重写后的对应关系，**不改写 §1、§9、§10 的历史值**：

| 节点 | H2 前对象（保留） | 清洗后对象（当前谱系） |
| :--- | :--- | :--- |
| Contract 冻结 | `632eb4c7dcaa593208c2a52911273896cbb2cef7` | `7704a98a4569f8148494a0618bb11019ef1e1189` |
| Implementation | `ef362fd19e79a67dd496ef5751393244844131a2` | `efffae65c2d66256b5522704a77f50cf38917687` |
| 文档状态修正 | `9e694cf1573ba744ec26f896fe36413a6ac483ff` | `0c1ea2ceff2a2c9e01470ad4a4ecdd592ee113e5` |
| 正式关闭 | `6553333f832de03468af7945294002ba37d040ef` | `11d2a1498ab63d3b3518e6723337185a5321c347` |
| 关闭后状态协调 | `442a980a994614623405ecf3243f90e461991ea0` | `198908c299472672be6ed5590c9a3ddfaeca234a` |
| tag object | `0cae547c7c21cc1a754b147726f022a3396d38c3` | 远端 `294336feeac2a9813f21d11a8a147fa522c71fd5` |
| tag peeled commit | `6553333f832de03468af7945294002ba37d040ef` | 远端 `11d2a1498ab63d3b3518e6723337185a5321c347` |

**证据强度**：五组提交的提交说明、作者时间和父链位置对应，且
`git patch-id --stable` 完全相同；远端 tag object 与 peeled target 已由 2026-10-21
只读 `git ls-remote` 核验。完整 patch-id 与限制以
`docs/PROJECT_STATE.md` §3.2 为准。

**限制**：仓库内没有 H2 正式发布的完整映射表，A4/A5 原始证据本次未直接复核；
patch-id 相同支持差异等价，但不等于证明整棵树在所有历史上下文中逐字节相同。
新旧 tag 注释正文都仍引用旧 closure commit `6553333...`，不能把注释正文当作当前
peeled target 的证明。
