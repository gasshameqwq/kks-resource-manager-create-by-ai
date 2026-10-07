# Phase 1.4-A.1 Report — Path Search（相对路径纳入检索）

> 版本：Phase 1.4-A.1 · schema v2（**未改动**）· 2026-10-06
>
> 目标：把 `resources.relative_path`（文件名 + 用户目录）纳入只读 Search Core 的检索面，
> 使用户能用**实际看到的文件名**找到资源（例：搜索「沙耶香」命中
> `… - 美树沙耶香.png`，即使卡片解析名是日文 `美樹さやか`）。
>
> 严格边界（全部遵守）：不改 `schema.py`/迁移、不改 Parser/Scanner/ResourceStore/models、
> **不改 `resources_fts` 表结构**、不改 `review_reasons`/`needs_review`、不进 GUI、
> 不扩 CLI 命令族、不碰真实样本、不实现跨语言/异体字/别名归一化。

---

## 1. 实际修改文件

**新增**

| 文件 | 说明 |
| :-- | :-- |
| `docs/phase1/PHASE1_4A1_REPORT.md` | 本报告 |

**修改**

| 文件 | 改动 |
| :-- | :-- |
| `core/query/queries.py` | `_text_search_clause` 在 name / author 之外增加 **path 条件** `r.relative_path LIKE ? ESCAPE '\'`，恒定走 LIKE；更新 docstring |
| `core/query/search.py` | 模块文档补充「相对路径」检索字段与「不进 FTS / 不搜 file_path」的说明（**无逻辑变更**） |
| `tests/test_search_core.py` | 合成构造器支持 `relative_path`；新增 `path_seeded` 夹具与 18 项路径检索测试；更新真实样本用例 |
| `core/__init__.py` | `__version__` 0.6.0 → 0.6.1；`__phase__` → `Phase 1.4-A.1 (Path Search)` |
| `README.md` | 状态行与路线图同步 |

**未改动**：`core/database/schema.py`、`core/database/db.py`、`core/parsers/*`、
`core/scanner/*`（含 `store.py`）、`core/models/*`、`core/thumbnails/*`、`cli_query.py`、
`main.py`、`ui/*`、真实样本目录。

---

## 2. 最终搜索子句

`_text_search_clause` 现在用 `OR` 合并**三类事实来源**：

```sql
(
    <name / display_name 条件>                       -- >=3 字走 FTS；否则（或 FTS 不可用）LIKE
    OR r.relative_path LIKE ? ESCAPE '\'             -- Phase 1.4-A.1：恒定 LIKE，从不进 FTS
    OR EXISTS (SELECT 1 FROM resource_authors ra     -- 作者：只经关系表
               JOIN authors a ON a.id = ra.author_id
               WHERE ra.resource_id = r.id
                 AND (a.name LIKE ? ESCAPE '\' OR ra.raw_name LIKE ? ESCAPE '\'))
)
```

参数顺序：`name 条件 → path → author(name) → author(raw_name)`，全部经 `_execute_select` 只读护栏。

**明确不做**：不搜 `file_path`（绝对路径噪声 / 跨机器不稳定），不搜 `file_path_key`（身份键，
非展示字符串）；不把 path 放进 FTS。

---

## 3. 路由规则（更新后）

| 查询 | name / display_name | relative_path | author |
| :-- | :-- | :-- | :-- |
| 空 / 纯空白 | — | — | — |
| 1–2 字 | LIKE | **LIKE** | LIKE |
| ≥ 3 字（FTS 可用） | FTS `MATCH` | **LIKE** | LIKE |
| 任意长度（FTS 不可用） | LIKE | **LIKE** | LIKE |

关键点：**path 恒走 LIKE**，因此 FTS 只是 name/display 的加速器，不改变整体结果集
（`FTS(name) ≡ LIKE(name)`，path/author 两路与 FTS 无关）。

---

## 4. 为什么只搜 `relative_path`

| 候选 | 结论 |
| :-- | :-- |
| basename | 可用，但 `relative_path` 已包含它（根目录资源两者相同），不必单独存 |
| **relative_path** | **采纳**：文件名 + 用户目录；相对 Library 根，跨机器稳定；无盘符噪声 |
| 完整 file_path | **不采纳**：含盘符 / 父目录 / 用户名路径，跨机器不稳定，且同一 Library 资源共享前缀 → 噪声大 |

精确按绝对路径定位的需求由既有的 `ResourceQuery.resolve(id/path/key)` 覆盖，不需要搜索承担。

---

## 5. 测试数量与结果

`tests/test_search_core.py` 由 **65 → 83** 项（净增 18）。新增覆盖：

| 组 | 覆盖 |
| :-- | :-- |
| 文件名命中 | 解析名日文、文件名中文时，按文件名词命中（`沙耶香`→#1、`佐仓杏子`→#2） |
| 目录/Mod 名 | 按子目录名（`hair`）与文件名（`ExtraHair`）命中 |
| 不搜绝对路径 | `d:/lib`、`/lib/1.png` 均不命中（`file_path`/`file_path_key` 非搜索字段） |
| 路由 | ≥3 字：name 走 FTS + path 走 LIKE，仍命中 path-only 资源；2 字不调用 FTS |
| FTS 一致性 | 8 个查询在 FTS 开/关下结果完全一致 |
| 组合筛选 | `query` + type / library / has_mods / property_category / needs_review |
| 排序分页 | path 命中集 + `order_by` + `limit/offset` |
| 输入安全 | `%` / `_` 是**字面量**（`_` 只命中含下划线的路径，不当「任意单字符」）；`沙%耶`、`沙_耶`、`___`、`美"树` 等不命中；`* () NEAR( col:val {q}` 不抛异常 |
| 只读不变量 | `total_changes` / `needs_review` / `app_meta` 前后不变 |

**全量 pytest 结果：**

```text
413 passed in 18.84s
0 failed / 0 xfailed        （1.4-A 基线 395 + 新增 18）
```

---

## 6. 真实样本验证结果（只读）

样本：`G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike`（22 卡 + 13 zipmod）。

```text
fts_enabled True    resources 35

「沙耶香」   (3 字) → FTS  → [4]      <- 解析名是 美樹さやか，命中来自 relative_path
「沙耶」     (2 字) → LIKE → [4]
「佐仓杏子」(4 字) → FTS  → [3]      <- 解析名是 佐倉杏子，命中来自 relative_path
「サヤカ」   (3 字) → FTS  → []       <- 片假名不在文件名/解析名里；属跨语言(B)，本阶段不做
作者「Evaan」       → [19, 20, 21, 31, 32] = 5 个资源

FTS 关闭后结果与 FTS 路径完全一致：True
检索前后 total_changes 2406 → 2406：True
样本 36 个文件 sha256 前后一致：True；size + mtime_ns 前后一致：True
```

> 只读保证：真实样本仅被 `read`（Scanner 只 `os.walk` + `stat` + 只读打开解析，输出写入**临时库**）。
> 未重建索引、未 touch 文件、未向样本目录写入任何临时文件；已用 **sha256 + size + mtime_ns** 三重比对确认。

---

## 7. 只读不变量验证

- 合成库（`path_seeded`）：批量检索前后 `total_changes` 不变；`needs_review` 各行不变；`app_meta` 全表不变。
- 真实样本（临时库）：检索前后 `total_changes` 保持 `2406 → 2406`；`needs_review=1` 计数保持 0。
- 所有 SQL 仍经 `_execute_select`（只允许 `SELECT` / `WITH`）；本阶段未新增任何写语句，
  `search.py` 仍是纯函数、不接连接、不执行 SQL。

---

## 8. schema 是否保持 v2

**保持 v2。** `SCHEMA_VERSION == 2`、`MIGRATIONS == [1, 2]`，无新增迁移/列/表，
`resources_fts` 结构未改（仅被查询，未被重建）。

---

## 9. 是否修改真实样本

**未修改。** sha256（36 文件）、文件大小、`mtime_ns` 前后均一致。

---

## 10. 是否发现 P0/P1/P2

- **P0：无。**
- **P1：无。**
- **P2（记录，未修）：**
  1. 跨语言/异体字/别名（`沙耶香` ↔ `さやか`、`仓` ↔ `倉`、罗马音）仍未支持 ——
     这是**独立问题（B 层）**，需要别名/正名数据，可能涉及 schema，明确留待后续单独评估。
  2. `relative_path` 以 Windows 反斜杠存储，用户输入正斜杠路径串（如 `作者A/角色卡`）不命中；
     当前只搜原始 `relative_path`（目标是搜名字/片段），属已知边界。
  3. `relative_path` 为 NULL 的行不会 path 命中（Scanner 总会写入，手工/导入行可能为空）；
     刻意不加 `COALESCE(..., file_path)` 回退，避免引入绝对路径噪声。
  4. 早期 P2（`resources_fts.author` 对应死列、`metadata_json.plugin_count` 冗余等）维持不变。

---

## 11. 本阶段没有做的事情

- 没有改 schema / 迁移 / FTS 表结构。
- 没有改 Parser / Scanner / ResourceStore / models。
- 没有改 `review_reasons` / `needs_review` 写入逻辑。
- 没有进入 GUI（未改 `ui/*`、`main.py`）。
- 没有新增 CLI 命令或命令族（`cli_query.py` 未改）。
- 没有把 `file_path` / `file_path_key` 纳入搜索。
- 没有实现跨语言 / 异体字 / 别名 / 罗马音 / 模糊 / 语义搜索。
- 没有进入 Phase 1.4-B（libraries 只读查询、缺 MOD 视图等均未动）。

---

## 12. 对 Phase 1.4-B 的建议

1. **libraries 只读查询**：导航需要「库列表 + 资源/缺失/待确认计数」，建议在 Query Layer 增加只读查询，
   避免 UI 依赖写层 `LibraryStore`。
2. **「缺 MOD 的资源」筛选**：真实样本 `missing=134`，建议加 `has_missing_mods` 类只读过滤（纯 EXISTS，零 schema）。
3. **搜索范围保持稳定**：1.4-B 起 GUI 搜索框可直接对接 `query=`（已含 name/display/relative_path/author）。
4. **CLI 薄适配（待确认）**：是否给 `query resources` 加可选 `--search`，仍由你决定。
5. **B 层（跨语言/别名）单独评估**：若要做，优先考虑「用户可编辑别名表」，不要硬编码假名/汉字映射。

---

### 附：验收对照

| 指令要求 | 结果 |
| :-- | :-- |
| path 条件恒定走 LIKE、不进 FTS | ✅ |
| 不搜 `file_path` / `file_path_key` | ✅（有测试断言） |
| 不改 name/display 的 FTS/LIKE 路由与作者 EXISTS | ✅ |
| 空查询行为不变；`relative_path` NULL 不命中（无 COALESCE） | ✅ |
| `search.py` 保持纯函数、不执行 SQL | ✅（仅文档改动） |
| 合成测试（命中 / 组合 / 路由 / 注入 / list-count / 只读） | ✅ 新增 18 项 |
| 真实样本 `沙耶香` / `沙耶` / `佐仓杏子` 命中 | ✅ |
| FTS 开 / 关结果一致 | ✅ |
| 样本 sha256 前后一致（且未 touch） | ✅ sha256 + size + mtime_ns |
| 原有 395 项保持通过 | ✅ 413 passed / 0 failed / 0 xfailed |
| schema 保持 v2 | ✅ |
| `__phase__` 更新 | ✅ `Phase 1.4-A.1 (Path Search)` |
