# Phase 3.5.1 — CLI 写入口与 System-Tag Bootstrap 实施契约

> 文档类型：Implementation Contract  
> 状态：**FROZEN**  
> 冻结日期：2026-10-24  
> 实施授权：用户已明确授权本子阶段实施与验证（G-2）  
> Git 收尾：**未授权**（G-3）；不得 commit / push / 创建或移动 tag

---

## 1. 目标

Phase 3.5.1 为既有 Tag 领域补齐可用的 CLI 用户入口，并接入 System-Tag
Eager Bootstrap：

1. 暴露 Tag CRUD 与 Resource ↔ Tag / Favorite 写命令；
2. 所有写操作严格经过 `TagWriteService`；
3. 在应用 / CLI 启动时幂等保证保留系统 Tag `favorite` 已就绪；
4. 以自动化测试证明命令语义、错误码、幂等性、只读护栏与全量回归。

本子阶段只接入口和启动引导，不新增 Tag 领域能力。

## 2. 权威与不变式

本契约服从 `PHASE3_0_CONTRACT.md`、Phase 3.2 Tag Contract 与已关闭阶段契约。

实施必须保持：

```text
SCHEMA_VERSION == 2
MIGRATIONS == {1, 2}
业务表 == 16
```

以及：

- `TagWriteService` 是 `tags` / `resource_tags` 的唯一运行期 writer；
- CLI 不 import `sqlite3`、不拼写 `tags` / `resource_tags` 的写 SQL；
- Favorite 的唯一持久化事实是 `resource_tags`，不新增列或表；
- 系统 Tag 身份由保留 `name_key == "favorite"` 派生，不新增 `is_system` 列；
- Query Layer 只读，CLI 只使用 `ResourceQuery` / `TagQuery` 做身份解析与展示；
- 文件系统只读；不修改图片、角色卡或 MOD 文件。

## 3. 允许修改范围

允许修改：

```text
main.py
core/app/**                    （仅在必要时）
```

允许新建：

```text
tests/test_cli_tags.py
docs/phase3/PHASE3_5_1_IMPLEMENTATION_CONTRACT.md
docs/phase3/PHASE3_5_1_LOG.md
```

实际实施选择仅修改 `main.py`，没有修改 `core/app/**`。

## 4. CLI 命令清单

| 命令 | 服务调用 | 成功语义 |
| :--- | :--- | :--- |
| `tag create <name> [--color <c>] [--category <cat>]` | `create_tag` | 创建用户 Tag；返回 id |
| `tag list` | `TagQuery.list` | 列出 id / name / color / category / system |
| `tag rename <old_name_or_id> <new_name>` | `rename_tag` | 重命名用户 Tag，不自动合并 |
| `tag delete <name_or_id>` | `delete_tag` | 删除用户 Tag 并清理关联 |
| `resource add-tag <resource_id> <tag_name>` | `assign_tag` | 为资源添加 Tag，幂等 |
| `resource remove-tag <resource_id> <tag_name>` | `unassign_tag` | 从资源移除 Tag，幂等 |
| `resource favorite <resource_id>` | `set_favorite(..., True)` | 收藏，幂等 |
| `resource unfavorite <resource_id>` | `set_favorite(..., False)` | 取消收藏，幂等 |

Tag 名称解析使用 `TagQuery.find_by_name()`：先 `strip() + casefold()`，再做精确
`name_key` 匹配。不提供模糊搜索、前缀搜索或结构化查询语法。

`tag rename` / `tag delete` 的 target 支持 id 或名称。若 target 是数字，先按 id
解析；id 不存在时再按名称精确解析。

Resource 命令的目标入口沿用既有 `ResourceQuery.resolve()`，因此接受既有资源 id /
路径身份形式；命令契约中的主形式仍是 `resource_id`。

## 5. 启动引导语义

有效 CLI 启动（版本查询 `--version` 除外）在命令分发前执行：

```text
database.initialize()
  → database.connect()
  → TagWriteService.ensure_system_tags()
  → close()
```

该流程：

- 幂等；重复启动不产生重复 Favorite；
- 是数据 seed，不是 migration / DDL；
- 失败时向 stderr 输出 `系统标签初始化失败：...`，返回退出码 1；
- 使后续 `tag list` 与 Favorite 写命令在 fresh DB 上立即可用。

`set_favorite()` 内部仍有既有的按需保证，保留 Phase 3.2 的服务级幂等语义。

## 6. 错误与退出码

成功：stdout 输出确认信息，退出码 `0`。  
领域失败：stderr 输出明确原因，退出码 `1`。

| 条件 | 最低错误内容 |
| :--- | :--- |
| 资源不存在 | `找不到资源` |
| Tag 不存在 | `找不到标签` |
| create / rename 名称冲突 | `标签名已存在`，并声明不自动合并 |
| 创建 / 改名为保留 key | `系统保留名` |
| 重命名 / 删除系统 Tag | `系统标签不可重命名或删除` |
| 启动 bootstrap 失败 | `系统标签初始化失败` |

ArgumentParser 自身的语法错误保持常规退出码 `2`。

## 7. 测试要求

新增测试必须覆盖：

1. 八个命令的成功路径；
2. `tag create` / `list` 的字段与系统标记；
3. `rename` 冲突拒绝且不合并；
4. 删除 / 重命名 `favorite` 被拒绝；
5. resource 打标 / 去标与收藏 / 取消收藏；
6. 资源不存在、Tag 不存在时 stderr 与退出码 1；
7. 重复打标、重复收藏和取消收藏的幂等性；
8. Eager Bootstrap 幂等与 schema 冻结；
9. CLI 写路径静态护栏：无直接 Tag 写 SQL。

必须执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_tags.py -v
.\.venv\Scripts\python.exe -m pytest tests/test_query_layer.py tests/test_query_model.py tests/test_search_core.py -q -k "read_only or do_not_write or untouch"
.\.venv\Scripts\python.exe -m pytest -q
```

使用 `.venv` 是执行口径的一部分：系统 Python 缺 `msgpack` / `PyQt6`，不能代表
项目依赖环境。

## 8. Definition of Done

本子阶段完成需同时满足：

1. 八个命令已注册，成功/失败输出符合 §4–§6；
2. 所有 CLI 写操作只经 `TagWriteService`，无直接 Tag 写 SQL；
3. Eager Bootstrap 幂等，fresh DB 启动后 Favorite 就绪；
4. `SCHEMA_VERSION == 2`、迁移集合与 16 张业务表不变；
5. 新增测试全部通过；
6. 既有 943 项测试全部回归通过；
7. 只读护栏通过；
8. 实施日志记录命令、环境、耗时、结果和 diff 统计；
9. 工作区保持未提交的 modified / untracked 状态，等待 G-3 审核授权。

## 9. 排除项

本子阶段明确不做：

- 不修改 `ui/` 任何文件；
- 不修改 `core/database/schema.py`、DDL、索引或创建 migration；
- 不修改图片、角色卡、MOD 或任何扫描根目录文件；
- 不新增字段、表、Favorite 第二事实来源或计数器；
- 不扩展 `field:value`、`AND` / `OR` / `NOT` 等查询语法；
- 不新增 GUI Tag UX；
- 不修改既有只读 Query Model / Search API；
- 不执行 `git commit`、`git push`、tag 创建或移动。

