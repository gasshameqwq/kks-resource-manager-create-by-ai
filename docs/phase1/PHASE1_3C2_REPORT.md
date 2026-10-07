# Phase 1.3-C-2 Report — Review Reason（只读派生）

> 版本：Phase 1.3-C-2 · schema v2（**未改动**）· 2026-10-06
>
> 目标：在 Query Layer 上增加「为什么这个资源需要人工查看」的**只读推导**能力。
> 不改 schema / migration / Parser / Scanner / ResourceStore / models / CLI / GUI；
> 不写库、不新增字段、不修改 `needs_review` 的写入逻辑。

## 1. 数据流（state 与 reason 分离）

```text
resources.needs_review          ← review state（现有布尔；Scanner 写入，本阶段不改）
        │
        ├── parse_status   ┐
        ├── parse_error    │
        ├── name           ├─► ResourceQuery.review_reasons(id)  ← 只读推导（本阶段新增）
        ├── resource_type  │        → tuple[ReviewReason, ...]
        └── resource_mod_usages.property（unknown 类别）
```

- **state** = 既有 `resources.needs_review`（本阶段**不触碰**其写入逻辑）。
- **reason** = 查询期推导，**不落库、不新增字段**。

## 2. 实现文件变更

| 文件 | 变更 |
| :-- | :-- |
| `core/query/dto.py` | 新增只读 DTO `ReviewReason(code, label, detail)` |
| `core/query/queries.py` | 新增 reason 常量 + `ResourceQuery.review_reasons(id)` + 私有 `_unknown_properties` |
| `core/query/__init__.py` | 导出 `ReviewReason` 与 `REVIEW_REASON_*` 常量 |
| `tests/test_review_reasons.py` | 新增 13 个测试 |

**未改动**：`core/database/schema.py`、migration、`core/parsers/*`、`core/scanner/*`、
`core/scanner/store.py`（ResourceStore）、`core/models/*`、`cli_query.py`、`main.py`、
`ui/*`、真实样本。

## 3. API

```python
ResourceQuery.review_reasons(resource_id) -> tuple[ReviewReason, ...]

@dataclass(frozen=True)
class ReviewReason:
    code: str          # 稳定机器标识
    label: str         # 人类可读提示（GUI 可本地化）
    detail: str | None # 可选补充
```

返回规则：资源不存在 → `()`；没有任何理由 → `()`；多个理由按 `REVIEW_REASON_CODES` 稳定顺序返回。

## 4. reason 定义

| code | 触发条件（既有列） | detail |
| :-- | :-- | :-- |
| `parse_failed` | `parse_status = 'failed'` | `parse_error` 文本 |
| `parse_partial` | `parse_status = 'partial'` | `parse_error` 文本（可能为空） |
| `missing_name` | `name` 为空 / NULL | — |
| `unknown_type` | `resource_type = 'unknown'` | — |
| `unknown_property` | 该资源的 usage 中存在无法归类的 property | 无法识别的 property 列表（去重、排序） |

顺序：`parse_failed → parse_partial → missing_name → unknown_type → unknown_property`。

> `unknown_type` / `unknown_property` 仅**只读展示**，**不会**翻转 `needs_review`。

## 5. 只读保证

- `review_reasons` 只执行 `SELECT`（经 `_execute_select` 只读护栏）。
- 调用前后 `conn.total_changes` 不变；`resources.needs_review` 值不变（有测试断言）。
- 无 schema 变更：`SCHEMA_VERSION == 2`、`MIGRATIONS == [1, 2]`。

## 6. 测试

新增 **13** 个（`tests/test_review_reasons.py`）：每个 reason 单独触发、多 reason 顺序、
不存在资源、去重/排序、只读（total_changes 与 needs_review 不变）、schema 未变、
真实样本无任何 reason、真实样本库 sha 不变。

## 7. pytest 全量结果

**330 passed，0 failed，0 xfailed**（C-1 基线 317 + 13）。

## 8. 真实样本结果

- 35 个资源 → **带 reason 的资源 = 0**；
- `needs_review = 1` 计数 = **0**；
- 无法识别的 property = **0**；
- `review_reasons` 调用新增写操作 = **0**；
- 真实样本目录 sha256 前后**一致**。

## 9. 是否发现 P0/P1

**没有。**

## 10. 下一步

Phase 1.3-C 至此结束（Preview + Review Reason 均为只读/派生）。
