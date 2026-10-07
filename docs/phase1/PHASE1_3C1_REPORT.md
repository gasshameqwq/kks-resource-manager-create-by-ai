# Phase 1.3-C-1 Implementation Report — PreviewService

> 版本：Phase 1.3-C-1 · schema v2（**未改动**）· 2026-10-06
>
> 目标：只实现 Preview。不实现 Review Reason，不改 schema/Parser/Scanner/models/CLI/main，
> 不做 GUI、不做 zipmod 内部图片提取、不提取 embedded face preview、不改真实样本。

## 1. 文件变更

**新增**

| 文件 | 说明 |
| :-- | :-- |
| `core/thumbnails/service.py` | `PreviewService` / `PreviewStatus`（派生缩略图缓存） |
| `tests/test_thumbnails.py` | 16 个测试（cache key → GC → 只读不变量） |

**修改**

| 文件 | 改动 |
| :-- | :-- |
| `core/thumbnails/__init__.py` | 导出 `PreviewService` / `PreviewStatus` / 状态常量 / 默认参数 |

**未改动**：`core/database/schema.py`、`core/parsers/*`、`core/scanner/*`、
`core/models/*`、`cli_query.py`、`main.py`、`ui/*`、真实样本。

## 2. PreviewService API

```python
PreviewService(cache_dir=None, *, max_size=(256, 256), webp_quality=90)

preview_cache_key(file_path_key, size, mtime) -> str      # 模块级纯函数

service.cache_key(source) -> str | None           # 按当前 stat 计算
service.cache_path(source) -> Path | None
service.path_for_key(cache_key) -> Path
service.is_supported(source) -> bool
service.status(source) -> PreviewStatus            # 不生成
service.get_or_generate(source) -> PreviewStatus   # 命中即返回，否则生成
service.generate(source) -> PreviewStatus    # 强制（重新）生成
service.invalidate(source) -> bool
service.gc(valid_keys) -> int
service.known_keys() -> set[str]
```

`source` = 路径（`str`/`Path`）或任意带 `file_path`（可选 `extension`）的对象，
例如 Query Layer 的 `ResourceSummary`（带 `resource_type` 时按类型判断）。
**本类不接收数据库连接**，结构上不写 SQLite。

## 3. cache key 实现

```python
sha256(f"{file_path_key}\n{size}\n{mtime!r}")[:32]
```

- `file_path_key` 用项目现有 `core.database.db.normalize_path_key`；
- `size` / `mtime` 取**当前实际文件 stat 值**（`os.stat`）；
- **不使用** `resource.id`，**不读取文件内容**做 content hash；
- 注释与文档已写明：**这是 filesystem-state cache key，不是 content identity**。

## 4. preview 状态语义

| 状态 | 含义 |
| :-- | :-- |
| `unsupported` | 本阶段无 preview 来源（`.zipmod`/非图片/非 `character_card`；即使 zipmod 内部有图片也不提取） |
| `missing` | 支持该类型，但当前没有可用 preview：**源文件不存在/不是普通文件，或 cache 尚未生成** |
| `ready` | cache 文件存在且可正常读取 |
| `failed` | 支持，但**读取/解码/生成过程中失败**（**不落库、不写永久 failure marker**） |

`PreviewStatus(state, cache_key, path, reason)`；`is_ready` / `is_supported` 便捷属性。

## 5. cache 写入策略

- 输出 `data/thumbnail_cache/<cache_key>.webp`（沿用 `app_paths.thumbnail_dir()`）。
- 统一缩略图：保留 alpha（`RGBA`/`RGB` 安全转换）、保持纵横比、**最长边 ≤ 256（不放大）**。
- **不新增/不使用** `resources.thumbnail_path`，**不写数据库**。
- **安全写入**：写入同目录临时文件（`.<name>.tmp-<pid>-<rand>`）→ `os.replace` 原子替换 →
  异常时清理临时文件，避免半截 webp。写入后再用 Pillow 重新打开验证，杜绝 0 字节/损坏缓存。

## 6. corruption / failure handling

- cache 读取：`Image.open(...).verify()` + `load()` 验证；失败 → **删除损坏文件** → 回到生成流程。
- 源文件不存在 / 非普通文件 → `missing`；读取/解码/生成出错（IO、损坏、截断、解码炸弹）→ `failed`
  （带 `reason`，供测试与日志定位，不向调用方抛底层异常）。
  只把「坏文件」类错误转成 `failed`；真正的编程错误（如 `TypeError`）照常抛出。
- 失败**不写任何 cache 文件**，不写 DB，下次仍可重试。

## 7. GC

`gc(valid_keys)`：删除 `thumbnail_cache/*.webp` 中 stem 不在 `valid_keys` 的文件，返回删除数。
只删 **cache 派生文件**；绝不触碰资源文件 / 数据库 / 样本。

## 8. 测试数量

新增 **21** 个（`tests/test_thumbnails.py`）。

## 9. pytest 总结果

**317 passed，0 failed，0 xfailed**（1.3-A/B 基线 296 + 21）。

## 10. 22 张真实角色卡生成结果

- **22 / 22** 生成成功，状态全部 `ready`，输出全部为合法 **WebP**，尺寸全部 **(183, 256)**。
- 不放大：小图（32×48）保持原尺寸。
- 源 PNG 逐文件 sha256 **不变**。

## 11. 真实样本 sha256 前后对比

生成 22 张缩略图前后，样本目录整树 sha256 **完全一致**（`sample_root` 会话夹具也会独立断言）。

## 12. DB sha256 前后对比

扫描样本入库 → 关闭连接 → 记录 `.db` sha256 → 对全部资源跑 `PreviewService.get()` →
再次 sha256：**完全一致**。PreviewService 无数据库连接，未写 SQLite。

## 13. 是否发现 P0/P1

**没有。**

## 14. 未修改 schema / Parser / Scanner

已确认：

- `SCHEMA_VERSION == 2`、`MIGRATIONS == [1, 2]`（无迁移）；
- `PreviewService` 源码不引用 `core.parsers` / `core.scanner`，不含 `.execute(`，不含 `thumbnail_path`；
- 未编辑 `core/database/*`、`core/parsers/*`、`core/scanner/*`、`core/models/*`、
  `cli_query.py`、`main.py`、`ui/*`；真实样本未改动。
- `resources.thumbnail_path` **未使用、未写入**（操作后全表仍为 NULL，实测非空行 = 0）。

## 15. 下一步

Phase 1.3-C-2 Review Reason
