# Phase 3.2 — Tag System

## Closure Report

> 文档类型：**Phase 3.2 收尾报告（Closure Report）**。只记录 Phase 3.2 的最终收尾结果，
> 不引入任何新的设计或契约。
> 日期：2026-10-08

---

### Phase

Phase 3.2 — Tag System

### Status

```text
CLOSED / PASS
```

### Contract

- `docs/phase3/PHASE3_2_TAG_SYSTEM_ARCHITECTURE_DESIGN.md`
- `docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md`

（上级权威：`docs/phase3/PHASE3_0_CONTRACT.md`；前置：Phase 3.1 = CLOSED / PASS。）

### Implementation

- **Tag CRUD**：`TagWriteService.create_tag` / `rename_tag` / `delete_tag`（normalization =
  `strip()` + `casefold()`，create/rename 冲突拒绝、不自动 merge）。
- **Resource ↔ Tag assignment**：`assign_tag` / `unassign_tag`（幂等，`origin = 'user'`）。
- **Favorite reserved system Tag**：`name_key = "favorite"` / `name = "Favorite"`；
  `set_favorite(r, True/False)` 只经 `resource_tags`；无 `resources.favorite`、无 `favorites` 表。
- **TagQuery**：只读 read model（`list` / `get` / `find_by_name` / `for_resource` /
  `resource_ids` / `system_tags` / `is_favorite` / `favorite_resource_ids`）；无 `resolve()`。
- **DTO**：`TagSummary`；`ResourceDetail += tags / is_favorite`（additive、带默认值）。
- **`resource_count`**：读取时派生值（一次聚合查询），不落库、不缓存。
- **Ownership boundary**：`TagWriteService` 是 `tags` / `resource_tags` 的唯一 runtime writer；
  Scanner / Parser / ResourceWriteService / Query / GUI / CLI 均不写这两张表。
- **Lazy bootstrap**：system Tag 按需保证存在；`ensure_system_tags()` 为幂等权威 seam；
  `set_favorite()` 在自身事务内确保 Favorite；`database.initialize()` 未被修改；
  startup eager bootstrap 属后续 CLI / GUI integration。

### Verification

| 检查 | 结果 |
| :--- | :--- |
| 全量测试 `pytest -q -p no:cacheprovider` | **883 passed / 0 failed / 0 skipped**（基线 825） |
| Phase 3.2 focused | 62 passed（`test_tag_write` 33 + `test_tag_query` 21 + `test_ownership_guard` 8） |
| schema verification | `SCHEMA_VERSION == 2` / `MIGRATIONS == {1,2}` / **16 business tables** |
| `tools/validate_schema.mjs` | exit 0 |
| `tools/check_model_sync.mjs` | exit 0 |
| Test invariants T-A…T-N | 全部 **PASS** |
| ownership | `OWNERSHIP: PASS` |
| scope | `SCOPE: PASS` |
| Implementation Audit（只读） | `OVERALL: PASS` |

### Git

| 项 | 值 |
| :--- | :--- |
| Implementation commit message | `feat(tag): add tag system` |
| Implementation Commit (full) | `841865d29cc54977874a4223476ab6fa9ee9b4cf` |
| Implementation Commit (short) | `841865d` |
| Final Closure Commit | 由最终 Git 验证结果补录（见下方自引用说明） |
| Final Tag | `phase-3.2-closed` |
| Final Tag type | annotated（`git cat-file -t phase-3.2-closed` → `tag`） |
| Final Tag target | Final Closure Commit（`git rev-parse phase-3.2-closed^{commit}` == `HEAD`） |
| Final working tree | clean |

> **自引用说明**：本报告随 **Final Closure Commit** 一起提交，因此**不内嵌该 commit 自身的 hash**
> （写入 hash 会改变内容、进而改变 hash，无法自洽）；改为只记录 `phase-3.2-closed` 标签。
> 该 annotated tag 解引用后指向的 commit 即 Final Closure Commit；
> 收尾提交后 `HEAD` == `phase-3.2-closed^{commit}`，工作树 clean。

### Scope

Phase 3.2 CLOSED 后，**不包含** Phase 3.3 Search implementation。
本阶段未实现：Search Query Model、`field:value`、AND / OR / NOT、全文搜索、Tag 搜索语法、
Tag / Favorite filtering、BrowserScope tag filtering、GUI Tag 管理、GUI Favorite UI、
CLI Tag UX、自动分类、AI 分类、Tag ↔ Resource Type / Usage Category 自动转换、Collection、
文件移动 / 改名 / 删除 / 下载 / 联网。这些全部属于后续阶段。
