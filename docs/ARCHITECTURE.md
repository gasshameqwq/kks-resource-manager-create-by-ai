# KKS Resource Manager — 架构文档

> 版本：Phase 3.2 基线（Tag System 已 CLOSED / PASS） · schema v2 · 2026-10-10
> 本文件只描述**当前有效**的架构；各阶段状态与权威文档入口见 `docs/PROJECT_STATE.md`。

本文档描述系统的分层、数据模型与关键技术决策。Phase 0 交付了本文档、
项目骨架与 SQLite schema；Phase 1 起按 §10 的路线图逐个小步实现功能。

---

## 1. 项目定位

这不是「角色卡分类器」，而是一个 **Koikatsu Sunshine 本地资源管理器**：

> 建立一个本地、可搜索、可分类、可关联的 KKS 资源数据库。
> 角色卡只是其中一种资源。

三条硬性约束贯穿所有阶段：

| 约束 | 说明 |
| :--- | :--- |
| **本地优先** | 所有数据在本地处理；运行时不依赖云端 AI / API，零网络请求 |
| **默认只读** | 扫描、解析绝不移动/删除/修改用户原始文件；文件操作必须用户明确触发 |
| **可人工修正** | 自动识别只给「可可靠识别的结论」，其余标 `unknown` 交给用户确认 |

---

## 2. 核心架构原则

不要设计成 `文件 → 文件夹`，而应该是：

```
文件
 ↓
资源 (Resource)
 ↓
资源类型 (resource_type)
 ↓
元数据 (metadata)
 ↓
标签 (tags) ── Collection ── Author
 ↓
关系 (relationships)
 ↓
用户分类 (user classification)
```

对应到查询方向，任意一端都能出发：

```
角色 → 使用了什么 MOD？
MOD  → 被谁使用？
作者 → 发布了什么？
Collection → 包含什么？
标签 → 对应什么？
```

**最关键的一条**：文件位置与分类完全分离。把资源加入 `Favorite` Collection
或打上标签，**不移动文件、不改文件名**。数据库里的 `category / tag /
collection` 与 `file_path` 是两套互不影响的维度。

---

## 3. 目录结构

```
kks-resource-manager/
├── core/                      # 核心逻辑：与 UI 完全解耦，不 import PyQt6
│   ├── __init__.py            # 版本号 / 当前 Phase
│   ├── app_paths.py           # 数据目录、数据库、缩略图缓存、日志路径
│   ├── models/                # 领域模型（dataclass，与 DB 列一一对应）
│   ├── database/              # SQLite schema + 迁移 + 连接
│   │   ├── schema.py          # ★ 版本化 DDL（内嵌，打包安全）
│   │   └── db.py              # connect / transaction / initialize / 归一化
│   ├── library/               # Library 管理（Phase 1.1 ✅）
│   │   └── store.py           # libraries 表 CRUD + 统计（只碰数据库，不扫目录）
│   ├── scanner/               # 目录遍历 + 增量扫描（Phase 1.2-C ✅）
│   │   ├── models.py          # ScanStats / ScanIssue / ScanResult
│   │   ├── store.py           # 入库层：resources / mods / 关系表
│   │   └── scanner.py         # LibraryScanner：遍历 + 增量判定 + 每文件事务
│   ├── parsers/               # 只读解析器（Phase 1.2-B/D ✅）
│   │   ├── models.py          # CharacterCardParseResult / ZipmodParseResult
│   │   ├── card.py            # KKS/KK 卡片：PNG + msgpack 尾部
│   │   └── zipmod.py          # ZIPMOD：manifest.xml → guid/name/author/version
│   ├── mod/                   # 空壳模块（MOD manifest / GUID 实际在 parsers/zipmod.py）
│   ├── thumbnails/            # 缩略图缓存（只写 data/thumbnail_cache/）
│   ├── duplicate/             # 空壳模块（byte-duplicate 为 Query 层只读派生）
│   └── classification/        # 识别优先级 Level 1–4
├── ui/                        # 界面层：只调用 core/，不含业务逻辑
│   ├── main_window.py         # 主窗口（三栏；Phase 1.4 起）
│   ├── browser_panel.py       # 资源浏览（网格 + 有界加载更多）
│   ├── filter_bar.py          # 搜索 / 筛选 / 排序
│   ├── detail_panel.py        # 只读资源详情
│   ├── library_panel.py       # Library 管理（Phase 1.5-A）
│   ├── library_admin_dialog.py
│   ├── resource_model.py      # 行模型（展示名委托 core DTO）
│   ├── preview_worker.py      # 异步缩略图 worker
│   └── scan_worker.py         # 后台扫描 worker（Phase 1.5-B）
├── tests/                     # pytest；核心逻辑必须可无 UI 测试
├── tools/                     # 开发辅助脚本（validate_schema.mjs 等）
├── docs/                      # 架构文档 / Phase 报告 / 第三方许可
├── data/                      # 运行时数据（已被 .gitignore 忽略）
│   ├── kks_resource_manager.db
│   ├── thumbnail_cache/
│   └── logs/
├── main.py                    # 入口（自检 + library / scan / resource / gui 子命令）
├── requirements.txt
└── README.md
```

**依赖方向严格单向**：`ui/ → core/`，`core/` 永不反向依赖 UI。
这样核心逻辑可以脱离界面单独测试、单独跑脚本、单独打包成 CLI 工具。

---

## 4. 数据模型（schema v2）

### 4.1 表清单（16 张业务表）

> v1（Phase 0）13 张；**v2（Phase 1.2）新增 3 张**：`resource_plugins`、
> `resource_mod_usages`、`resource_authors`，并给 `resources` 增加 `card_marker` 列。

| 表 | 作用 | 关键点 |
| :--- | :--- | :--- |
| `app_meta` | 应用级键值元数据 | 存 `schema_version`、`fts_enabled` 等 |
| `libraries` | 扫描根目录 | 一个用户可添加多个；`root_path_key` 唯一 |
| `resources` | **核心资源实体** | 一个文件 = 一行；`file_path_key` 唯一 |
| `authors` | 作者 | 独立概念，不依附文件名；`name_key` 唯一 |
| `tags` | 标签 | 多对多；`name_key` 去重 |
| `resource_tags` | 资源 ↔ 标签 | `origin` 区分人工/自动 |
| `collections` | 集合 / 系列 | 与目录结构完全分离 |
| `resource_collections` | 资源 ↔ 集合 | 一个资源属于多个 Collection |
| `mods` | 本地 MOD 索引 | `guid` 唯一，来自 `manifest.xml` |
| `resource_mods` | 卡片 → MOD 依赖 | **主键用 `mod_guid`**，见下 |
| `duplicate_groups` | 重复组 | 只建议，不删除 |
| `duplicate_members` | 重复组成员 | `is_canonical` 标记用户保留项 |
| `scan_records` | 扫描历史 | 增量扫描统计 |
| `resource_plugins` | **卡片插件（v2）** | KKEx 键；与 MOD 严格区分，不是 zipmod |
| `resource_mod_usages` | **卡片 → MOD 逐槽位使用（v2）** | 主键 `(resource_id, mod_guid, property)`；眼睛/皮肤/衣服/配饰语义在这里 |
| `resource_authors` | **多作者关联（v2）** | 一张卡可多作者；`[Unknown]` 哨兵不建 authors 行 |

#### v2 的三条硬约定

1. **插件 ≠ MOD**：插件（`moreAccessories` / `KSOX` / `marco.authordata` …）没有
   `manifest.xml`，只进 `resource_plugins`，绝不进 `mods` / `resource_mods`。
2. **`skin` / `eyes` / `hair` / `accessory` 不允许作为 PNG 文件类型自动写入**：
   这些语义来自 `resource_mod_usages.property`（如 `ChaFileFace.Pupil1`、
   `outfit6.ChaFileClothes.ClothesTop`），是**关系标签**而不是文件类型。
3. **`dataID` 不是身份键**：同一角色每次保存都可能变化，只能存进 `metadata_json`。

### 4.2 关系图

```
libraries ──1:N──► resources ◄──N:M── tags
                       │  ▲            (resource_tags)
                       │  └──N:M── collections
                       │            (resource_collections)
                       │
                  author_id (N:1)
                       ▼
                    authors

resources ──1:N──► resource_mods ──N:0..1──► mods
   (卡片)          (mod_guid 主键)          (本地已安装)

resources ──1:N──► resource_mod_usages ──(按 mod_guid)──► mods
   (卡片)       (逐槽位：property / slot)      (未安装时为 NULL)

resources ──1:N──► resource_plugins          (KKEx 插件，与 MOD 无关)
resources ──N:M──► authors                   (resource_authors，多作者)

resources ──N:M──► duplicate_groups
            (duplicate_members)
```

### 4.3 三个关键设计决策

**① 依赖记录用 `mod_guid` 做主键，而不是 `mod_id`**

一张角色卡可能依赖本机没安装的 MOD。如果 `resource_mods` 只能引用 `mods.id`，
这些「缺失依赖」就无处存放，「缺失 MOD」功能会直接失效。

```sql
PRIMARY KEY (resource_id, mod_guid)   -- 未安装的 MOD 也能记录
mod_id INTEGER REFERENCES mods(id)    -- 已安装时回填，否则为 NULL
```

**② 路径额外存归一化列 `file_path_key`**

Windows 路径不区分大小写，`D:/KKS/A.png` 与 `d:\kks\a.png` 是同一文件。
归一化规则（`core/database/db.py:normalize_path_key`）：
展开 `~` → 绝对化 → 统一分隔符 → 去尾斜杠 → `casefold()`。
对其建 UNIQUE 索引，可从根上杜绝同一文件重复入库。

注意：**不做 `Path.resolve()`** —— 那会把符号链接/短路径解析掉，反而可能
让同一个文件产生两个不同 key。

**③ 人工修正优先于自动识别**

`resources.type_source ∈ {auto, user}`。用户手动改过的类型，重扫时**不覆盖**。
这是需求「自动识别 + 人工修正」在数据层的落点。

### 4.4 索引

除主键/唯一约束外，为高频筛选建了索引：`resource_type`、`library_id`、
`author_id`、`sha256`、`quick_hash`、`content_key`、`relative_path`、
`needs_review`（部分索引，只索引 `=1` 的行）、`resource_mods.mod_guid`。

> 注：`quick_hash` / `content_key` 两列及其索引自 Phase 2.0-C §18.1 起定为
> **deprecated / unused**（不写、不读、不删除），保留仅为兼容既有数据库。

---

## 5. 核心流程

### 5.1 扫描 → 解析 → 入库 → 浏览

```
用户添加 Library 根目录
        ↓
递归遍历，收集候选文件（扩展名 / 大小 / mtime）
        ↓
  增量判断：path + size + modified_time 未变？
     ├── 是 → 跳过解析（skip parsing）
     └── 否 → 进入解析
        ↓
分类判定（Level 1 → 4，见 §6）
        ↓
解析元数据（角色名 / 缩略图 / MOD 依赖 …）
        ↓
写入 SQLite（resources / resource_mods / mods …）
        ↓
生成缩略图缓存 thumbnail_cache/<id>.webp
        ↓
浏览器展示：缩略图 + 名称 + 类型 + 路径
```

### 5.2 增量扫描

**不做**「每次启动重新解析全部文件」。判定顺序：

1. 比对 `(path, size, modified_time)` —— 三者一致即 skip。
2. 需要解析时（新增文件 / `(size, mtime)` 变化 / `mode='full'`），在**同一次稳定读取窗口**内
   计算 `resources.sha256`：窗口 = `stat_before` → parse → `sha256` → `stat_after`；
   窗口内 `(size, mtime)` 变化则本次结果**整体不提交**（Phase 2.1 的 C7 一致性规则）。
3. 增量命中（跳过解析）**不重算哈希**；`sha256` 是全部已解析文件的字节身份，
   而不是「按需才计算」。旧设计中的轻量指纹 `quick_hash`（大小 + 首尾块）自
   Phase 2.0-C 起定为 deprecated / unused，不再参与预筛。

### 5.3 搜索策略（已实测）

名称搜索采用 **FTS5(trigram) + LIKE 回退** 的混合方案：

| 查询长度 | 走哪条路 | 原因 |
| :--- | :--- | :--- |
| ≥ 3 字 | FTS5 trigram | 快速子串匹配，支持中日文 |
| 1–2 字 | `LIKE '%q%'` | **FTS5 trigram 只索引长度 ≥ 3 的子串** |

这一限制是实测确认的，不是推测：

```
FTS 中文子串（3 字 "白峰一"）：OK
FTS 中文子串（2 字 "一乃"）：不命中（符合预期，需 LIKE 回退）
LIKE 回退（2 字 "一乃"）：OK
```

日文名如「一乃」「雪」这类 1–2 字查询非常常见，所以 **LIKE 回退不是可选项
而是必需品**。在数万行规模上 `LIKE '%x%'` 全表扫描只需毫秒级，完全可接受；
FTS 只是长查询的加速器。

FTS 表是**尽力启用**：若某台机器的 SQLite 构建不含 FTS5 或版本过旧，
`initialize()` 会捕获异常、写入 `app_meta.fts_enabled=0` 并继续运行，
搜索自动全程回退 LIKE。应用不会因此启动失败。

### 5.4 写入事务

连接默认是 **autocommit**（`isolation_level=None`）：单条 DDL、单条 UI 编辑最省心。
但 autocommit 下每一行都要单独落一次盘，数万行的批量导入会慢到不可接受。

因此约定：

> **批量写入必须包在 `core.database.db.transaction(conn)` 里。**

```python
with db.transaction(conn):
    for row in rows:
        conn.execute("INSERT INTO resources ...", row)
```

- 已在事务中时复用外层事务，不提前提交（可安全嵌套）。
- 块内抛异常 → 整体回滚并原样抛出，不会留下「导入了一半」的脏数据。
- 单条操作保持 autocommit，不必包事务。

实测（800 行写入 + FTS 触发器）：autocommit ≈ 98 ms，事务内 ≈ 21 ms（约 4.7×）。
扫描器（Phase 1.2）**必须**遵循这一约定；误退回逐行提交会被
`tests/test_database_transactions.py` 的性能冒烟用例拦住。

FTS 存量回填只在**真正执行了迁移**时进行（`applied` 非空）。绝大多数启动没有迁移，
因此不会每次都白扫一遍 `resources`；新行由 FTS 触发器维护。

---

## 6. 识别优先级（规范 §22 的落地）

| Level | 依据 | 可信度 | 处理 |
| :--- | :--- | :--- | :--- |
| **L1** | 卡片格式 header marker | 可靠 | 直接判定 `character_card` / `outfit_card` / `scene_card` |
| **L2** | MOD `manifest.xml` 的 GUID / name / author | 可靠 | 建立 MOD 索引与依赖 |
| **L3** | 路径 / 文件名推断 | **仅候选** | 只写入候选字段，**绝不当作事实** |
| **L4** | 无法判断 | — | `unknown` + `needs_review=1`，进「待确认」 |

**不要假设所有 MOD 都能自动识别为 skin / eyes / hair / outfit。**
绝大多数资源只能可靠判断为 `mod`。只有 L1/L2 级证据才允许写更细的类型；
其余一律先落 `unknown`，由用户在「待确认」页批量确认。

同一原则适用于类型：识别流程是
`PNG → 检查 card header → character card? → outfit card? → scene card? → unknown`，
**不确定就不猜**。

---

## 7. 安全原则

程序第一次运行时：

```
不会移动文件
不会删除文件
不会修改角色卡
不会覆盖 MOD
不会修改游戏目录
```

具体保障：

- 解析层全程只读（`open(path, "rb")`）。
- 重复检测是**只读派生查询**（`GROUP BY sha256`，不落库、永不自动删除）；
  预留表 `duplicate_groups` / `duplicate_members` 至今零写入，用户确认层（confirm /
  dismiss / canonical）属后续阶段。
- 「文件位置」与「分类」分离，打标签/加 Collection 不碰文件系统。
- 未来（Phase 5）任何文件操作都必须：**Preview → Confirm → Undo/Backup**。
- `core/` 层不 import 任何网络库。

---

## 8. 技术选型

| 层 | 选型 | 理由 |
| :--- | :--- | :--- |
| 语言 | Python 3.11+ | 与主要参考项目 KKTools 一致，可最大化复用其卡片解析内核 |
| UI | PyQt6 | 同上；Windows 桌面表现成熟 |
| 数据库 | SQLite（标准库 `sqlite3`） | 零部署、单文件、可承载数万行；无需外部服务 |
| 二进制解析 | `msgpack` | KKS/KK 卡片尾部数据块就是 MessagePack |
| 图片 | Pillow | 缩略图生成与 PNG 校验 |

**不建议为了「现代技术栈」改用完全不同的架构。** 现有成熟实现（尤其卡片
解析）优先复用，而不是重写。

---

## 9. 复用策略与 License

| 来源 | License | 用法 |
| :--- | :--- | :--- |
| KKTools | MIT | ✅ 可复用代码，需保留版权声明 |
| koikatu.js | MIT（仅 package.json/README 声明，仓库无 LICENSE 文件） | ✅ 可参考/依赖；用于交叉验证 |
| KKCardModCheck | **无 License** | ⚠️ 仅参考设计，**不复制代码** |

详见 [THIRD_PARTY.md](./THIRD_PARTY.md)。

---

## 10. 阶段路线图

| Phase | 内容 | 状态 |
| :--- | :--- | :--- |
| **0** | 架构与项目初始化（本文档 + 骨架 + schema） | ✅ 完成 |
| 1 | 扫描 + KKS/KK 卡片识别 + SQLite + 只读 GUI 浏览器 | ✅ 完成并收尾（PHASE 1 = CLOSED） |
| 2 | MOD / 卡片解析 + Content Identity（sha256）+ Byte-duplicate 只读派生 + 查询暴露 | ✅ 完成并收尾（tag `phase-2.4-closed`） |
| 3 | 用户数据 / 机器事实分离 + Tag 体系（Phase 3 首期） | 🚧 3.0 · 3.0.2 · 3.1 · 3.2 已完成（tag `phase-3.2-closed`）；3.3 及以后**未冻结** |
| 4 | 重复检测 + 资源关系 | ⏳ 早期路线图占位（byte-duplicate 已在 Phase 2 完成），未重新论证 |
| 5 | 批量文件操作（Preview/Confirm/Undo） | ⏳ 早期路线图占位，未论证 |
| 6 | 性能优化 + 测试 + Windows 打包 | ⏳ 早期路线图占位，未论证 |

> Phase 3 的子阶段编号与顺序**未被 Contract 冻结**（`PHASE3_0_CONTRACT.md` §15）；
> 当前工作方向与权威级别见 `docs/PROJECT_STATE.md` §4。

Phase 1 拆成 4 个可独立验收的小步（一次只做一步，做完即验收）：

| 步骤 | 内容 | 状态 |
| :--- | :--- | :--- |
| **1.1** | Library 管理（添加 / 删除 / 列出扫描根目录） | ✅ 完成 |
| **1.2** | 扫描器：递归遍历 + 增量判定（path/size/mtime）→ `resources` | ✅ 完成（1.2-A/B/C/D） |
| **1.3** | 卡片解析：PNG 尾部 MessagePack → 类型 / 名称 / 缩略图 | ✅ 完成（含只读查询层与检索） |
| **1.4** | PyQt6 基础浏览器：缩略图网格 + 筛选 + 搜索 | ✅ 完成（1.4-A/A.1/B.1–B.3/C-1～C-5，详见下方） |

Phase 1.4 的实际推进（收尾报告见 `docs/phase1/PHASE1_4C_CLOSURE_REPORT.md`）：

| 步骤 | 内容 | 状态 |
| :--- | :--- | :--- |
| **1.4-A / A.1** | 只读 Search Core（FTS5 trigram + LIKE 回退；检索面含 `relative_path`） | ✅ 完成 |
| **1.4-B.1 / B.2 / B.3** | Library 只读查询 / `has_missing_mods` / Browse Read Model | ✅ 完成 |
| **1.4-C-1 ～ C-5** | GUI 骨架 / 搜索筛选排序 / 异步缩略图 / 详情面板 / 关系反查与闭环 | ✅ 完成 |
| 1.4-C-6 | 收尾评估：结论为「不继续 C-6」（无可验证的剩余浏览缺口） | ✅ 完成 |
| **1.5** | GUI Setup & Scan（Library 管理 + 扫描 + 刷新） | 🚧 **1.5-A（GUI Library 管理）✅ · 1.5-B（GUI 扫描）✅**；1.5-C/D 需真实证据驱动 |

**1.1 明确不含目录遍历**：`core/library/` 只写 `libraries` 表；遍历属于 1.2。

Phase 1.2 的实际推进（比原计划拆得更细）：

| 步骤 | 内容 | 状态 |
| :--- | :--- | :--- |
| **1.2-A** | Schema v2（`card_marker` / `resource_plugins` / `resource_mod_usages` / `resource_authors`） | ✅ 完成 |
| **1.2-B** | 只读 Parser（角色卡 + ZIPMOD） | ✅ 完成 |
| **1.2-C** | Scanner：目录遍历 + 增量判定 + 按 v2 入库 | ✅ 完成 |
| **1.2-D** | Parser 补齐作者信息（`marco.authordata`）并打通 `resource_authors` | ✅ 完成 |
| 1.3 | 缩略图缓存 + 「待确认」流程 | 待开始 |

每完成一个 Phase 必须：跑测试 → 修错误 → 确认旧功能未被破坏 → 更新 README
→ 才进入下一阶段。**不要跨阶段提前实现大量功能。**

---

## 11. 数据库迁移约定

`core/database/schema.py`：

```python
SCHEMA_VERSION = 2
MIGRATIONS = {1: (_V1_SQL, _V1_FTS_SQL), 2: (_V2_SQL, "")}
MIGRATION_ADDED_COLUMNS = {2: (("resources", "card_marker", "TEXT"),)}
```

新增变更时（示例：要加 v3）：

1. 追加 `_V3_SQL`，**不要改动 `_V1_SQL` / `_V2_SQL`**（老用户数据库已按 v1/v2 建好）。
2. `MIGRATIONS[3] = (_V3_SQL, "")`，`SCHEMA_VERSION = 3`。
3. 若需要加列，写进 `MIGRATION_ADDED_COLUMNS[3]`，不要写进 DDL。
4. `initialize()` 会自动只跑 `version > current` 的迁移，天然幂等。

**加列（ALTER TABLE）必须走 `MIGRATION_ADDED_COLUMNS`，不要写进 DDL 字符串**：
SQLite 的 `ADD COLUMN` 不幂等，重复执行会报 `duplicate column name`。
`db.initialize()` 会先查 `PRAGMA table_info` 再决定加不加，并且**加列排在 DDL 之前**
（v2 的 DDL 里有依赖新列的索引）。

**旧库升级实测**（v1 → v2，带数据）：只补跑 `[2]`，13 → 16 张表，
已有 Library / resources / resource_mods / scan_records 全部原样保留，
新列 `card_marker` 对老数据为 `NULL`（不编造值）。

---

## 12. 打包计划（Phase 6）

参考 KKTools 的 GitHub Actions 流程（`windows-latest` + `actions/setup-python`
+ PyInstaller `--onefile --windowed`）。本项目额外注意：

- DDL 内嵌在 Python 中 → **不需要**为数据库脚本添加 `--add-data`。
- 主题、图标等资源才需要 `--add-data`。
- 发布前必须跑 `python -m pytest -q`。
- 数据目录在 exe 同级（便携式），保证用户换机即用。
