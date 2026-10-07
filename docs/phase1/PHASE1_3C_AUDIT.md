# Phase 1.3-C 设计审计：Preview / Thumbnail 与 Review / 待确认

> 版本：Phase 1.3-C（Design / Audit，**本轮不实现**）· schema v2（**未改动**）· 2026-10-06
>
> 前置基线：resources=35 / cards=22 / mods=13 / usages=1527 / resource_mods=315 /
> plugins=206 / resource_authors=14 / authors=3 / missing=134 / orphan=3 /
> pytest 296 passed / 真实样本 sha256 不变。
>
> 本轮只做设计审计，不改 schema / Parser / Scanner，不扩 CLI，不实现 GUI，
> 不碰真实样本。文中所有数字都来自对 22 卡 + 13 zipmod 的**只读**实测。

---

## 1. 当前 Preview 数据流

```text
PNG 卡片文件
   │  (只读)
   ▼
core.parsers.card.parse_card()                ← 已存在
   │  产出 CharacterCardParseResult：
   │    face_preview_kind / face_preview_size   (仅“格式/大小”，不含字节)
   │    embedded_texture_count                  (数据区内嵌 PNG 计数)
   │    block_sizes / name / authors / deps …
   ▼
core.scanner.store.build_card_metadata()      ← 已存在
   ▼
resources.metadata_json { face_preview_kind, embedded_texture_count, … }
```

现状要点：

- **Parser 只报告 preview 的“元信息”，不保留 preview 字节**：`parse_bytes` 里
  `face = trailing[pos:pos+face_len]` 读进局部变量后即丢弃，结果对象只留
  `face_preview_kind`（`jpeg`/`png`/`unknown`）与 `face_preview_size`。
- **主 PNG 图像本身**就是一张可直接解码的图片（PNG 数据流到 `IEND` 结束，
  其后的卡片尾部字节被 Pillow 忽略）。
- `resources.thumbnail_path` 列**存在但从未被写入**（v1 遗留，全库非空计数 = 0）；
  `core/models.CardSummary.thumbnail_png` 字段定义了但**无人使用**。
- `core/thumbnails/` 目前**只有 docstring 占位**，没有任何生成代码；
  `app_paths.thumbnail_dir()`（`data/thumbnail_cache/`）已存在且已 `ensure_dirs`。
- `ui/main_window.py` 的 `create_main_window()` 仍 `raise NotImplementedError`。
- **Pillow 已声明并可用**（实测 Pillow 12.3.0）。

> 结论：preview 的“生成/缓存”是**全新代码**，但所有需要的输入（文件、Pillow、
> 缓存目录、metadata）都已就绪，**不需要改 Parser / Scanner**。

## 2. 当前 Review 数据流

```text
Parser.parse_status (ok/partial/failed) + name
        │
        ▼
ResourceStore.upsert_card_resource():
   needs_review = 1 当 (parse_status != 'ok' 或 name 为空)，否则 0     ← 唯一写入点
        │
        ▼
resources.needs_review (INTEGER, 默认 0；部分索引 idx_resources_needs_review WHERE =1)
        │
        ├── LibraryStore.stats().needs_review   (library list 显示“待确认 N”)
        └── Query Layer: ResourceQuery.list(needs_review=True)  (Phase 1.3-A/B 已有)
```

现状要点：

- `needs_review` 是**布尔状态**；**没有 review reason**、没有“已确认/已忽略”状态、
  没有时间戳。
- 唯一写入点是**卡片**入库：`parse_status != 'ok' or not name`。
  **zipmod 入库路径完全不设置它**（保持默认 0，即使 `parse_status='partial'`）。
- 相关但独立的既有字段：`parse_status`、`parse_error`(文本)、`scan_status`
  (new/present/missing/error)、`type_source`(auto/user)。
- 每次重扫会**重算并覆盖** `needs_review`（无法承载“用户已确认”的持久状态）。
- Phase 1.3-A 的 property 分类里，未识别块 → `unknown`；真实样本 **unknown = 0**。

## 3. 真实样本 Preview 审计结果

对 22 张卡 + 13 zipmod 的**只读**实测：

### 3.1 角色卡（22/22 全部有可用 preview，且有两个来源）

| 来源 | 尺寸 | 格式 | 覆盖率 | 是否需改 Parser | 说明 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| **主 PNG 图像**（IEND 之前） | 全部 252×352 | 全部 PNG | **22/22** | **不需要**（直接 `Image.open(file)`） | 头+上半身卡片图 |
| **内嵌面部预览**（容器头里） | 全部 240×320 | 19 PNG + 3 JPEG | **22/22** | 需要（Parser 未暴露字节） | 面部特写裁切 |

证据：

- 22/22 主 PNG 都能被 Pillow 打开并 `load()` 成功，尺寸全为 252×352（格式 PNG）。
- 22/22 容器头都含面部预览字节（无一张缺失），`face_preview_kind` 分布
  `png=19 / jpeg=3`，解码尺寸全为 240×320。
- 两个来源是**不同图片**：主 PNG 是头+上半身，面部预览是更紧的面部裁切
  （已抽取 `ayame` 两图人工确认）。
- `embedded_texture_count`：22 张里 13 张为 0，其余为 1/7/10/10/17/17/17/22/120。
  这些是**数据区里的依赖贴图**（属于被引用的 MOD），**不是卡片自身预览**，不作为 preview 来源。

**逐题回答：**

1. 22 张卡是否都有可用 preview？→ **是**，两种来源都 100% 覆盖。
2. preview 来源？→ 主 PNG（通用、无需解析）+ 内嵌面部预览（更贴脸、需提取）。
3. 是否存在没有 preview 的卡？→ **否**（0 张）。
4. 能否稳定从原始资源重新生成？→ **能**。主 PNG 解码是确定性的；同一文件重复生成结果一致。
5. 是否需要解码/提取？→ 主 PNG 只需**解码**；面部预览需**提取+解码**。
6. 是否可能因原文件变化而失效？→ **会**。文件内容变化 → preview 应重生成
   （用 size/mtime 失效，见 §6）。
7. zipmod 是否有合理 preview？→ **不可靠**：13 个里 **11 个内部无任何图片**；
   仅 2 个含内部缩略图（`[Blanketman] Additional Skin Pack` 的
   `abdata/chara/thumb/...`、`[ryo2003] VanillaEx Stiletto` 的
   `abdata/chara/thumb/ryo2003/01_thumb.png`），路径/命名/数量都不统一。
   **本阶段 zipmod 一律“无 preview”**，不做内部解析。
8. 非角色卡资源以后是否可能需要 preview？→ **会**。服装卡 / 场景卡同样是
   “PNG + 卡片尾部”容器，主 PNG 方案天然适用；zipmod/其它归档类资源另议。

> **推荐 preview 来源：主 PNG 图像。** 它 100% 可用、无需改 Parser、覆盖所有 PNG 类资源。
> 内嵌面部预览（更贴脸）作为**可选增强**，需要 Parser 暴露字节（见 §10），本轮不做。

## 4. 当前 needs_review 实际使用情况

真实样本实测：

| 指标 | 值 |
| :-- | --: |
| `needs_review = 1` 的资源 | **0** |
| `parse_status` 分布 | ok = 35 |
| `scan_status` 分布 | present = 35 |
| `type_source` 分布 | auto = 35 |
| `thumbnail_path` 非空 | 0 |

**结论**：真实样本是“干净”的——没有任何资源需要人工确认，也**没有任何 review reason
数据**可供验证。这意味着 1.3-C 的 Review 设计只能建立在**推导规则**上，而非既有数据分布上。

## 5. Preview Cache 推荐架构

保持「派生数据」定位，**不写数据库**：

```text
GUI / Service 调用方
        │
        ▼
core.thumbnails.PreviewService      ← 新代码（纯文件缓存，只读源文件）
        │  path_for(resource) / get(resource) / status(resource)
        ├──────────────► data/thumbnail_cache/<cache_key>.webp   (文件缓存)
        └──────────────► core.query.ResourceQuery                (只读拿资源元数据)
```

- **不新增 schema**；`resources.thumbnail_path` 继续**留空不用**（或仅作为将来可选的
  快捷缓存，本轮不使用）。
- Preview 状态（有/无）**由缓存目录 + 资源元数据推导**，不落库。
- 删除整个 `thumbnail_cache/` 不影响数据库、不影响原始资源，可随时重建。
- 源文件始终只读：只用 `Image.open(path)`，绝不写回。

## 6. Cache key / invalidation 方案

**Cache key（推荐）**

```text
cache_key = sha256( file_path_key + "\n" + file_size + "\n" + modified_time ).hexdigest()[:32]
cache_path = data/thumbnail_cache/<cache_key>.webp
```

- 输入全部来自已入库列（`file_path_key` / `file_size` / `modified_time`），
  **不需要读取文件内容做 hash**，也不依赖数据库 id。
- 确定性：同一文件状态 → 同一 key。

**原文件变化如何失效**

- size 或 mtime 变化 → key 变化 → 自然 cache miss → 重新生成。
- 旧文件成为孤儿 → 由 **GC**（删除“当前无任何资源映射到该 key”的文件）清理。
- 与增量扫描保持一致的风险（内容变了但 size+mtime 没变）**已知**且可接受；
  如将来要求强一致，再引入内容 hash（届时只是换 key 计算，架构不变）。

**健壮性**

| 情况 | 处理 |
| :-- | :-- |
| cache 文件损坏 | 读取时 `Image.open` + `verify()`，失败 → 删除并重生成 |
| 生成失败（解码异常等） | **不写任何文件**，返回“无 preview”（不缓存失败，避免负数缓存） |
| 没有 preview（如 zipmod） | 用“无文件”表示；`status()` 返回 `unsupported` / `missing` |
| 缓存被删 | 下次访问自动重建 |
| 多个 resource 是否共享 preview | 用上面的 key **不共享**（按路径状态）。真实样本里 3 个 sha256 相同的 Kugisaki 会各自生成一份（可接受）。如需共享，未来可改为**内容寻址**（key = 源图像内容 hash）——架构不变，仅换 key |

**数据库 / 备份边界**

- Cache **不进数据库**，**不进项目备份**（纯派生，可重建）。

## 7. Review 推荐架构

区分两个概念，且**只用现有字段**：

| 概念 | 载体 | 说明 |
| :-- | :-- | :-- |
| **review state** | 现有 `resources.needs_review`（布尔，已建索引） | “流水线标了它需要人看” |
| **review reason(s)** | **查询期推导**（不进库） | 为什么需要看，从既有列推出 |

**推导出的 reason（基于现有列，不新增字段）**

| reason | 判定（全部来自既有列） | 真实样本 |
| :-- | :-- | --: |
| `parse_failed` / `parse_partial` | `parse_status IN ('failed','partial')` | 0 |
| `missing_name` | `name` 为空/NULL | 0 |
| `unknown_type` | `resource_type = 'unknown'` | 0 |
| `unknown_property` | 该资源的 usage 里存在 `unknown` 类别 property（由 Query Layer 提供） | 0 |

> 这些 reason 只是**候选**；当前只有 `parse_*` / `missing_name` 会真的触发
> `needs_review=1`（由 Scanner 写入），`unknown_type` / `unknown_property` 仅作为
> **只读展示**，不改变布尔值。

**明确不做**（本阶段）：

- 不建 review/workflow 表；
- 不引入“已确认/已忽略/审批人/时间线”；
- 不让 `needs_review` 影响资源可搜索 / 可显示（它只是筛选维度之一）。

## 8. 是否需要 schema 修改

**不需要（本阶段）。**

- Preview：纯文件缓存，零 schema。
- Review state：复用既有 `needs_review`。
- Review reason：查询期推导。

因此 A（完全复用 `needs_review`）在**功能与数据完整性上都成立**，无需 B/C。

## 9. 如果将来需要 schema 修改：最小方案（仅备选，不实施）

唯一可能的触发点是「**需要持久化“用户已确认/已忽略”**」——现有布尔值每次重扫会被覆盖，
无法承载这类人工结论。届时**最小 B**：

```sql
-- 迁移 v3（仅示意，本轮不实施）
ALTER TABLE resources ADD COLUMN review_state TEXT NOT NULL DEFAULT 'none'
    CHECK (review_state IN ('none','pending','confirmed','dismissed'));
-- 或更保守：只加 reviewed_at TEXT（NULL=未确认）
```

- **不选 C**：没有多步审批、没有多审核人、没有状态机的需求。
- 在真正出现可确认的 review 数据之前，**不迁移**。

## 10. 需要修改哪些代码文件

**实现阶段预计新增/修改（本轮不动）**

| 文件 | 变更 | 类型 |
| :-- | :-- | :-- |
| `core/thumbnails/service.py`（新） | `PreviewService`：key / path / get / status / generate / gc | 新增 |
| `core/thumbnails/__init__.py` | 导出 `PreviewService` 与 `PreviewStatus` | 修改（当前是占位） |
| `core/query/queries.py` | 新增只读的 review reason 推导（如 `ResourceQuery.review_reasons(id)` / `review_summary()`） | 修改（查询层职责） |
| `tests/test_preview_service.py`（新） | preview 生成 / 失效 / 损坏 / 失败 / 删除重建 | 新增 |
| `tests/test_review_reasons.py`（新） | reason 推导 / needs_review 筛选 | 新增 |

**明确不改**：`core/database/schema.py`、`core/parsers/*`、`core/scanner/*`、
`core/models/*`、`cli_query.py`、`main.py`、`ui/*`、真实样本。

> 唯一“可能”要动 Parser 的场景是**想用内嵌面部预览**（更贴脸的缩略图）。
> 由于主 PNG 已 100% 覆盖，**不构成必要性**，本轮不改 Parser。

## 11. 测试计划（实现阶段）

**Preview**

1. key 确定性：同 (path_key,size,mtime) → 同 key。
2. 生成：真实样本 22 卡 → 22 张可被 Pillow 打开的 `.webp`（只读源文件）。
3. 失效：改副本 size/mtime → key 变化 → 重新生成（在**临时副本**上做，不碰真实样本）。
4. 损坏缓存：写入垃圾字节 → 读取时判定损坏并重生成。
5. 生成失败：损坏源图 → 返回“无 preview”，**不写缓存文件**。
6. 不支持类型：zipmod → `status == 'unsupported'`，不生成。
7. 可删除重建：删 `thumbnail_cache/` 后仍能全部重建；DB 行数/内容不变。
8. **只读保证**：生成前后真实样本目录 sha256 不变；DB 文件 sha256 不变。

**Review**

9. reason 推导：parse_partial → `parse_partial`；空 name → `missing_name`。
10. `needs_review=True` 过滤与 `review_summary` 一致。
11. 真实样本：`needs_review=1` 计数为 0、review reasons 全空。

## 12. 对 Phase 1.3-C 实现阶段的建议

拆成两个可独立验收的小步，均**不动 schema / Parser / Scanner**：

1. **1.3-C-1（PreviewService，优先）**：`core/thumbnails/service.py` + 测试。
   验收 = 真实样本 22/22 生成缩略图、失效/损坏/失败/删除重建路径正确、源文件与 DB 均不被修改。
2. **1.3-C-2（Review reasons，只读推导）**：查询层新增 reason 推导 + 测试。
   验收 = 用合成样本覆盖 `parse_partial` / `missing_name` / `unknown_type`；真实样本全空。

CLI **不再扩充**；GUI（1.4）只经 `Service / Query Layer` 访问。

## 13. 明确留到后续阶段的事项

| 事项 | 阶段 |
| :-- | :-- |
| duplicate detection（含内容寻址共享 preview） | Phase 4 |
| zipmod 内部图片提取（缩略图来源） | 后续（样本不足、格式不一） |
| 内嵌面部预览提取（更贴脸的缩略图） | 后续（需 Parser 暴露字节，非必需） |
| 缩略图 GC 调度 / 后台线程 / 进度 | 1.4（GUI） |
| GUI 网格、筛选、搜索、待确认页面 | 1.4 |
| 自动标签 / AI 分类 | 明确不做（本项目原则） |
| per-usage 代理键、作者→MOD 归属 | 未定 |

---

### 附：本轮顺带记录的 P2 backlog（仅记录，不修）

- `resources.thumbnail_path` 列自 v1 起**从未使用**（死列）。
- `core/models.CardSummary` / `thumbnail_png` **定义但未使用**。
- zipmod 入库路径不设置 `needs_review`（即使 `parse_status='partial'`）——当前无实际影响，留待 Review 真正落地时评估。
