# Phase 1.2 报告

> 项目：KKS Resource Manager
> 计划：**1.2-A Schema v2** → 1.2-B 只读 Parser → 1.2-C Scanner 入库
> 日期：2026-10-06 · 环境：`.venv` CPython 3.12.10 / SQLite 3.49.1
> 依据：[docs/phase1/SAMPLE_ANALYSIS.md](./SAMPLE_ANALYSIS.md)（真实样本只读分析）

---

## 1.2-A：Schema v2（✅ 已完成）

### 结论

**Schema v2 迁移完成，80 passed。** v1 的 13 张表一张没删、一列没改语义；
v2 只做加法：**1 个新列 + 3 张新表**。真实老库（v1）已实测升级成功，
Library / resources / resource_mods / scan_records 全部原样保留。

### 一、修改了哪些 schema

`core/database/schema.py`：`SCHEMA_VERSION: 1 → 2`

#### 新增列（1 个）

| 表 | 列 | 类型 | 作用 |
| :--- | :--- | :--- | :--- |
| `resources` | `card_marker` | TEXT | 卡片游戏格式（`KoiKatuCharaSun` / `KoiKatuChara`）。**只描述格式，不是身份**，同一角色可有两个 marker |

配套索引：`idx_resources_card_marker`。

#### 新增表（3 张）

```sql
-- ① 插件：KKEx 键（moreAccessories / KSOX / marco.authordata …）
--    与 MOD 严格区分：插件没有 manifest.xml，不是 zipmod
CREATE TABLE resource_plugins (
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    plugin_guid TEXT    NOT NULL,
    detected_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (resource_id, plugin_guid)
);

-- ② 卡片 → MOD 的逐槽位使用关系
CREATE TABLE resource_mod_usages (
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    mod_guid    TEXT    NOT NULL,
    property    TEXT    NOT NULL,   -- 例：outfit6.accessory10.ChaFileAccessory.PartsInfo.id
    slot        INTEGER,
    local_slot  INTEGER,
    category_no INTEGER,
    detected_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (resource_id, mod_guid, property)
);

-- ③ 多作者
CREATE TABLE resource_authors (
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    author_id   INTEGER NOT NULL REFERENCES authors(id)   ON DELETE CASCADE,
    ordinal     INTEGER NOT NULL DEFAULT 0,   -- 卡内出现顺序
    raw_name    TEXT    NOT NULL DEFAULT '',  -- 该卡上的原始写法
    PRIMARY KEY (resource_id, author_id)
);
```

新增索引：`idx_resource_plugins_guid`、`idx_resource_mod_usages_guid`、
`idx_resource_mod_usages_resource`、`idx_resource_mod_usages_property`、
`idx_resource_authors_author`。

#### 关于 `resource_mods`（v1 表）的处理

v1 已有 `resource_mods(resource_id, mod_guid, mod_id, relation, ref_count, detected_at)`，
**保留不动**，继续做「每资源一个 MOD 的汇总行 + 本地已安装回填 `mod_id`」；
`resource_mod_usages`（v2）承载**明细**。两者的不变式：

> 对每个 `(resource_id, mod_guid)`：`resource_mods` 恰有 1 行，
> 且 `ref_count` = 该组合在 `resource_mod_usages` 中的行数。

之所以不把 v1 表改成视图：老库已有数据、Phase 0 测试直接写它，删除是破坏性操作。

#### 各类需求落地位置

| 需求 | 落地 |
| :--- | :--- |
| 1. 游戏格式 `card_marker` | `resources.card_marker` |
| 2. 插件 GUID/键 + 数量 | `resource_plugins`；数量 = `COUNT(*)`（不存冗余列） |
| 3. 逐槽位关系 | `resource_mod_usages`（复数槽位 → 多行，槽位信息不丢） |
| 4. MOD metadata | v1 的 `mods` 表已够（guid/name/author/version/website/description/game），**未改动** |
| 5. 多作者 | `resource_authors` + `authors` 实体；哨兵不建 authors 行，原始值留 `metadata_json.authors_raw` |
| 6. metadata_json 约定键 | `schema.RESOURCE_METADATA_KEYS`：`user_id` / `data_id` / `card_version` / `embedded_texture_count` / `plugin_count` / `authors_raw` / `face_preview_kind` / `block_sizes` |
| 7. dataID 不是身份 | 只进 `metadata_json`，**不建唯一索引**；测试断言两条资源可共享同一 dataID |
| 8. 不自动写 skin/eyes/hair/accessory | `AUTO_DETECTABLE_TYPES` 仍只含 5 项，测试断言排除这四类 |

### 二、migration 如何工作

**设计原则：加列与建表分开，且必须幂等。**

```python
schema.SCHEMA_VERSION = 2
MIGRATIONS = {1: (_V1_SQL, _V1_FTS_SQL), 2: (_V2_SQL, "")}
MIGRATION_ADDED_COLUMNS = {2: (("resources", "card_marker", "TEXT"),)}
```

`db.initialize()` 对每个 `version > current` 的迁移：

1. **先**执行 `MIGRATION_ADDED_COLUMNS[version]` 里的加列 —— 通过 `PRAGMA table_info`
   判断列是否已存在，存在就跳过（`_add_column_if_missing`）。
2. **再**执行 `MIGRATIONS[version]` 的 DDL（全部 `IF NOT EXISTS`）。
3. 写 `app_meta.schema_version`。

**顺序为什么关键**：v2 的 DDL 里有 `CREATE INDEX ... ON resources(card_marker)`，
如果先跑 DDL 而列还没加，就会直接建索引失败。

**加列为什么不能写进 DDL**：SQLite 的 `ALTER TABLE ... ADD COLUMN` 不幂等，
重复执行报 `duplicate column name`。实测验证：把 `schema_version` 手工改回 1
再跑一次 `initialize()`，加列被正确跳过，迁移仍能成功。

| 场景 | 走的路径 |
| :--- | :--- |
| 全新库 | 迁移 1 建 13 张表 → 迁移 2 加列 + 建 3 张表 → v2 |
| v1 老库 | 跳过 1 → 只跑迁移 2 → v2 |
| 已是 v2 | `applied_migrations == []`，什么都不做 |

### 三、旧数据如何兼容

| 项 | 保证 |
| :--- | :--- |
| v1 表结构 | 除新增 `card_marker` 列外**零改动**；`_V1_SQL` 一个字符没动（有测试断言） |
| v1 数据 | 升级后逐项比对：libraries / resources / authors / tags / collections / resource_tags / resource_collections / resource_mods / scan_records 全部原样 |
| 新列取值 | 老数据的 `card_marker` 为 `NULL`，**不编造、不猜测** |
| 幂等 | 重复 `initialize()` 不重复建表、不重复迁移 |

**真实库实测**：

```text
升级前: schema_version=1, card_marker 列=False, 13 张表
applied_migrations: [2]   → 升级后: schema_version=2, card_marker 列=True, 16 张表
```

**带数据 + 走真实 CLI 的端到端升级**（临时库，非项目 data/）：

```text
[老库]  schema=1  libraries=1  resources=3  card_marker 列=False
[CLI]   python main.py --init-db      -> 0   （schema 版本：2，数据表（16））
[CLI]   python main.py library list   -> 0   （老卡库 / D:/KKS / 资源：3）
[升级后] libraries = [(1,'老卡库','D:/KKS')]
[升级后] resources = [('角色0',1,None), ('角色1',1,None), ('角色2',1,None)]
[升级后] resource_mods = [('com.example.x', 1)]
[升级后] v2 新表 = resource_authors / resource_mod_usages / resource_plugins
```

### 四、新增了哪些测试

**新增 `tests/test_migration_v2.py`（27 个用例）**：

| 分组 | 用例 |
| :--- | :--- |
| 版本与结构 | schema 版本 = 2；fresh 库落在 v2 且 16 张表齐全；v1 表未被破坏；`card_marker` 列存在；3 张 v2 表存在；6 个新索引存在 |
| **旧库升级** | v1 库升到 v2 且**只补跑 [2]**；升级后 9 类 v1 数据逐项保留；升级幂等；强制重跑 v2（改回 schema_version=1）加列仍安全 |
| 新增列行为 | `card_marker` 可读写；KK/KKS 两种 marker 共存 |
| 插件隔离 | 插件可多条、重复被拒；**插件不污染 mods / resource_mods**；随资源级联删除 |
| 逐槽位关系 | 同一 MOD 4 个槽位 → 4 行且 `COUNT(DISTINCT mod_guid)=1`；同 MOD 同 property 重复被拒；slot 字段可空；**缺失依赖也能建关系**；跨资源反向查询（naginata 两卡）；级联删除 |
| 多作者 | 一张卡挂两个作者，`ordinal` 与 `raw_name` 正确 |
| 身份约束 | 两条资源可共享同一 `dataID`（证明它不是唯一键） |
| 类型规则 | `AUTO_DETECTABLE_TYPES` 不含 skin/eyes/hair/accessory |
| 作者哨兵 | `partition_authors` 把 `[Unknown]` 与真实作者分开且**保留原始列表**；去重/去空白；仅哨兵的情况 |

**修改的既有测试（1 处）**：`tests/test_fts_backfill.py`

- `test_backfill_runs_on_first_initialize`：原先写死 `applied_migrations == [1]`，
  现在改为 `== sorted(MIGRATIONS)`（不再绑死版本号）。
- `test_backfill_runs_after_new_migration_on_existing_db`：假迁移版本号从 `2` 改成 `99`，
  避免与**真实存在的 v2** 冲突。

**工具升级**：`tools/validate_schema.mjs`（无 Python 备用通道）现在也跑 v2 ——
按与 Python 相同的顺序加列 + 建表，并新增 6 项 v2 冒烟（card_marker 写入、
插件与 MOD 分离、3 记录/1 唯一 MOD、多作者、KK/KKS 共存、v2 级联删除）。

### 五、测试结果

```text
pytest -q                      80 passed in 1.39s     （1.1 时是 53，本次 +27）
node tools/validate_schema.mjs exit=0  业务表数量：16（期望 16）
                                       DDL 重复执行（幂等，v1+v2）：OK
                                       card_marker 可写入：OK
                                       插件与 MOD 分离：OK
                                       逐槽位依赖（3 记录 / 1 唯一 MOD）：OK
                                       多作者关联可写入：OK
                                       KK/KKS 两种 marker 可共存：OK
                                       逐槽位依赖主键（同 MOD 同 property 重复）：OK
                                       级联删除（v2 插件/依赖/作者）：OK
node tools/check_model_sync.mjs  exit=0  schema 与 models 类型清单一致
```

### 六、本轮明确没做的事

- ❌ **没有实现 Parser**（1.2-B）：`core/parsers/`、`core/scanner/` 仍只有占位文档字符串。
- ❌ 没有写任何 Scanner 入库逻辑。
- ❌ 没有解析 zipmod 内部内容。
- ❌ 没有改动 `ui/`。
- ❌ 没有对真实样本目录做任何写入。

---

## 1.2-B：只读 Parser（✅ 已完成）

### 结论

**Parser 实现完成，161 passed；22 张卡 + 13 个 zipmod 全部解析成功（22/22、13/13）。**
真实样本目录在测试前后 **SHA256 完全一致**（见 §1.2-B-8）。

**本轮没有实现 Scanner、没有做数据库入库、没有改 UI、没有修改真实样本。**

### 1. 新增 / 修改了哪些文件

| 文件 | 状态 | 说明 |
| :--- | :--- | :--- |
| `core/parsers/models.py` | 新增 | 结果 dataclass：`CharacterCardParseResult` / `ZipmodParseResult` / `ModDependencyRecord` / `LstInfoEntry` |
| `core/parsers/card.py` | 新增 | 角色卡只读解析器（`parse_card` / `parse_bytes` / `decode_block` / `read_png_chunks`） |
| `core/parsers/zipmod.py` | 新增 | ZIPMOD 只读解析器（`parse_zipmod` / `parse_bytes` / `parse_manifest_xml` / `find_manifest_entry`） |
| `core/parsers/__init__.py` | 修改 | 占位文档 → 导出上述实现 |
| `tests/conftest.py` | 新增 | `sample_root` 夹具（含样本目录 sha256 前后比对护栏）+ `sample_files` |
| `tests/test_parser_card.py` | 新增 | 41 个用例：22 张真实卡参数化验收 + 逐条要求 |
| `tests/test_parser_zipmod.py` | 新增 | 18 个用例：13 个真实 zipmod 参数化验收 + 判定规则 |
| `tests/test_parser_errors.py` | 新增 | 20 个用例：合成损坏样本 |
| `docs/phase1/PHASE1_2_REPORT.md` | 修改 | 本文件 |
| `docs/ARCHITECTURE.md` | 修改 | 目录树标注 parser 已实现；补充 KK/KKS 差异 |
| `docs/phase1/SAMPLE_ANALYSIS.md` | 修改 | 补记「KK 卡片没有 About 块」这一实测差异 |

> 未改动：`core/database/*`、`core/library/*`、`core/models/*`、`ui/*`、`main.py`、
> `tools/*`（`tools/inspect_card.py` 仍保留为分析期探针）。

### 2. Parser result model 设计

不是随意 dict，而是 `core/parsers/models.py` 里的 dataclass：

```text
CharacterCardParseResult
    path / parse_status / error / warnings
    product_no / card_marker / card_marker_raw / card_type / card_version
    face_preview_kind / face_preview_size
    name / lastname / firstname / nickname / personality
    user_id / data_id
    plugin_guids[] / dependencies[ModDependencyRecord] / unique_mod_guids[]
    embedded_texture_count
    lst_info[LstInfoEntry] / lst_info_reordered / file_level_reserved
    block_sizes{} / region_bytes / region_covers_to_eof
    （属性）success / plugin_count / dependency_records / unique_mod_count

ModDependencyRecord（逐槽位，一条记录一个对象，**不去重**）
    mod_id / property / slot / local_slot / category_no / author / website / name

ZipmodParseResult
    path / parse_status / error / warnings
    is_zipmod / manifest_entry / guid / name / author / version / website
    （属性）success
```

设计要点：

- **`parse_status ∈ {ok, partial, failed}`**，与数据库 `resources.parse_status` 的口径一致。
- `card_marker` 是**去掉【】的原文**（`KoiKatuCharaSun` / `KoiKatuChara`），
  另有 `card_marker_raw` 保留精确内容（含【】）；**绝不归一化**。
- `name` = `lastname + firstname`；只有昵称时回落到 `nickname`。
- **模型里没有任何资源类型字段**（没有 eyes/skin/hair/accessory/resource_type）——
  眼睛/皮肤/衣服/配饰语义只存在于 `ModDependencyRecord.property`。
- `data_id` 只是元数据字段，**模型里没有把它当身份键**。

### 3. Character Card Parser 的解析流程

```text
1. 校验 PNG 签名 → 遍历 PNG 块直到 IEND，拿到尾部起点
   （PNG 结构不完整 → failed，不抛异常）
2. 容器头（关键结构，坏了就 failed）
   int32 productNo
   7bit 变长长度 + UTF-8 marker      → card_marker / card_marker_raw
   7bit 变长长度 + UTF-8 card version
   int32 faceLen + 面部图            → face_preview_kind: jpeg | png | unknown
   int32 lstLen + msgpack{"lstInfo"} → lst_info
   int32 regionLen
   int32 file-level reserved         → file_level_reserved
   data region
   （任一步越界/结构异常 → failed，并给出具体原因）
3. 卡片类型：marker ∈ {KoiKatuCharaSun, KoiKatuChara} → character_card
   其他 marker → 记 warning、card_type 留 None（不猜、不归一化）
4. lstInfo 按 pos 排序后再用；另记录 lst_info_reordered 标记原始顺序是否不同
5. 逐块容错解码（decode_block）：
   ① 整块是一个 msgpack？          → 直接返回
   ② [int32 长度][msgpack] 分帧？   → 逐帧取
   ③ 裸 msgpack 对象流 + 逐字节重同步 → 跳过解不动的字节并记 warning
   单块失败只记 warning，不中断整卡
6. 字段抽取（各自 try/except，失败只记 warning）
   Parameter → lastname / firstname / nickname / personality / name
   About     → userID / dataID（块不存在时留 None，不算失败）
   KKEx      → plugin_guids；sideloader 的 info → dependencies（逐条解码）
7. 唯一 MOD：按 ModID 去重（保序）；**dependencies 不去重**
8. 内嵌贴图：数据区里 PNG 签名计数（主图与面部图都在数据区之前，不参与计数）
9. 状态判定：有 warning → partial；无 → ok
   若连角色名都取不到 → failed（这不是 KKS/KK 角色卡）
```

**关键实现点（都来自真实样本的教训）：**

| 点 | 处理 |
| :--- | :--- |
| lstInfo 顺序 | 实测 `KKEx` 排在列表第一位、物理位置在最后 → **必须按 pos 排序** |
| 数据区起点 | lstInfo 之后是 `int32 长度 + int32 保留`，少读 4 字节会导致末尾截断 |
| 数据区覆盖 | 解析后校验 `region_covers_to_eof`，覆盖不到 EOF 会记 warning |
| 面部图格式 | JPEG / PNG 两种都实测存在 → 按魔数判断，不写死 |
| 块内分帧 | 「一个块 = 一个 msgpack」的假设在多数卡上失败 → 三形态容错 |
| 非关键块失败 | 有合成样本专门验证：Parameter 正常 + Coordinate 是垃圾 → 整卡仍成功 |

### 4. ZIPMOD Parser 的解析流程

```text
1. 以 zipfile 打开；BadZipFile / OSError / 其他异常 → failed + 明确 error
2. 遍历条目找 manifest.xml（文件名大小写不敏感，子目录也认，优先根目录）
   找不到 → failed（is_zipmod=False），error 说明「不是 ZIPMOD」
3. 读取 manifest.xml
   加密条目（RuntimeError）→ failed + 「可能被加密」
4. 解析 XML（ElementTree）
   非法 XML → failed + 「不是合法 XML」
   同时支持属性式 <manifest guid=... /> 与子元素式 <guid>...</guid>，兼容 XML 命名空间
5. 只取已确认可靠的字段：guid / name / author / version / website
   「标签存在但为空」保留成 ""（实测 NoHair 的 author 就是空标签），
   「标签不存在」才是 None
6. 缺 guid → partial + warning（可作为文件解析，但不能当 MOD 唯一键）
   有 guid → ok
```

**不根据文件名判断类型**：有测试把 zipmod 复制到临时目录并改名成
`totally_unrelated_name.zipmod`，结论不变。
**不解析 zipmod 内部资源结构**（Phase 2 再做）。

### 5. 真实样本 acceptance test 结果

**22 张卡全部解析成功，状态全部为 `ok`；13 个 zipmod 全部解析成功且都有 guid。**

| 组 | 文件 | 状态 | marker | 插件 | 依赖记录 | 唯一 MOD | 内嵌贴图 | 角色名 |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| A | 碧蓝航线 - 罗德尼.png | ok | KoiKatuCharaSun | 1 | 0 | 0 | 0 | HMSRodney |
| A | 魔法少女小圆 - 鹿目圆.png | ok | KoiKatuCharaSun | 2 | 0 | 0 | 0 | 鹿目まどか |
| B | 魔法少女小圆 - 美树沙耶香.png | ok | KoiKatuCharaSun | 2 | **4** | **1** | 0 | 美樹さやか |
| B | 魔法少女小圆 - 佐仓杏子.png | ok | KoiKatuCharaSun | 2 | **5** | **3** | 0 | 佐倉杏子 |
| C | 没有黄段子的无聊世界 - 华城绫女.png | ok | KoiKatuCharaSun | 2 | 3 | 1 | 0 | KajoAyame |
| C | 天结堡主 - 岚燐结骑.png | ok | KoiKatuCharaSun | 2 | 13 | 1 | 0 | 嵐燐結騎 |
| D | 政宗君的复仇 - 安达垣爱姬.png | ok | KoiKatuCharaSun | 2 | 1 | 1 | 0 | 安達垣愛姫 |
| D | 请问您今天要来点兔子吗 - 保登心爱.png | ok | KoiKatuCharaSun | 4 | 2 | 2 | **7** | 保登心愛 |
| E | 青春猪头少年系列 - 古贺朋绘.png | ok | KoiKatuCharaSun | 2 | 1 | 1 | 0 | 古賀朋絵 |
| E | 不死者之王 - 夏提雅 布拉德弗伦.png | ok | KoiKatuCharaSun | 3 | 2 | 1 | 0 | 夏提雅·布拉德弗伦 |
| F | Koikatu_F_..._Hermione_Evaan.png | ok | KoiKatuCharaSun | 17 | 136 | 20 | 10 | GrangerHermione |
| F | Koikatu_F_..._Tatsumaki_Evaan.png | ok | KoiKatuCharaSun | 19 | 31 | 19 | 10 | Tatsumaki |
| F | Koikatu_F_..._Kugisaki Nobara_Evaan.png | ok | KoiKatuCharaSun | 18 | 30 | 13 | 17 | KugisakiNobara |
| H | 明日方舟 - 红豆.png | ok | KoiKatuCharaSun | 10 | 112 | 26 | 1 | 新倉ようこ |
| H | FATE - 长尾景虎.png | ok | KoiKatuCharaSun | 10 | 301 | 25 | 0 | KagemitsuNagao |
| I | ...140632481...Kobeni.png | ok | KoiKatuCharaSun | 14 | 192 | 42 | 0 | HigashiyamaKobeni |
| I | ...140632862...Kobeni.png | ok | KoiKatuCharaSun | 14 | 192 | 42 | 0 | HigashiyamaKobeni |
| I | 同名不同目录/female/...Kugisaki.png | ok | KoiKatuCharaSun | 18 | 30 | 13 | 17 | KugisakiNobara |
| I | 同名不同目录/old_female/...Kugisaki.png | ok | **KoiKatuChara** | 17 | 30 | 13 | 17 | KugisakiNobara |
| I | [Yeeted] Sora .png | ok | KoiKatuCharaSun | 14 | 30 | 17 | 22 | IkushimaSora |
| I | KK_317794.png | ok | KoiKatuCharaSun | 12 | 192 | 43 | 0 | HigashiyamaKobeni |
| J | 刀剑神域 - 绀野木棉季.png | ok | KoiKatuCharaSun | 21 | **220** | **31** | **120** | ユウキ |

**P1.2 要求的逐条断言（全部通过）：**

| 要求 | 结果 |
| :--- | :--- |
| 22 张卡全部可解析 | ✅ 22/22，全部 `ok` |
| 13 个 zipmod 全部可解析 | ✅ 13/13，且 guid 互不相同 |
| Sayaka = 4 records / 1 unique | ✅ |
| Kyoko = 5 records / 3 unique | ✅（chinadresstop / crossstaff / ymgpt.acc_earrings_top） |
| Ayame 保留眼睛 Property 且**不推断来源** | ✅ `ChaFileFace.eyelineUpId` / `Pupil1` / `Pupil2` 原样保留；模型里无推断字段（有字段白名单断言） |
| Aki 识别 `ChaFileBody.detailId` | ✅ |
| Cocoa = 7 内嵌 PNG / 2 unique MOD | ✅ |
| Ranrin Yuiki 同一 MOD 多个 Property/Slot | ✅ 13 条记录 → 1 个 GUID，Property 去重后 > 1 |
| 共享 MOD 被多卡引用 | ✅ naginata 同时出现在红豆与长尾景虎，且槽位不同 |
| 缺失本地 zipmod 的依赖仍保留 | ✅ `ymgpt.acc_earrings_top` / `NonLightStockings` 先证明本地无对应 zipmod，再断言仍出现在 Parser 结果里 |
| NoHair 的 author/version 异常不失败 | ✅ author=`""`、version=`"0"`，状态 ok |
| 两个 Kobeni 的 dataID 不参与身份 | ✅ dataID 不同、userID 相同、身份来自 path |
| KK / KKS marker 保持区别 | ✅ `KoiKatuChara` vs `KoiKatuCharaSun` 不被归一 |
| Unicode 角色名正常 | ✅ ユウキ / 嵐燐結騎 / 夏提雅·布拉德弗伦 / IkushimaSora |
| Yuuki 大量记录不因去重丢失 | ✅ 220 条记录、31 唯一 MOD |

### 6. malformed fixture test 结果

合成样本（20 个用例全绿），**每个都返回结果对象、绝不抛异常**：

| 场景 | 期望 | 结果 |
| :--- | :--- | :--- |
| 非 PNG 字节 | failed + 明确原因 | ✅ |
| 合法 PNG 但没有卡片尾部 | failed +「没有卡片尾部数据」 | ✅ |
| PNG 被截断（未到 IEND） | failed | ✅ |
| 尾部被截断（数据区长度超出剩余） | failed | ✅ |
| lstInfo 长度被改坏 | failed | ✅ |
| 数据区长度被改坏 | failed | ✅ |
| **非关键块是垃圾字节** | **整卡仍成功**，只记 warning | ✅ Parameter 正常 + Coordinate 垃圾 → ok/partial 且名字正确 |
| 未知 marker（如 KoiKatuCoordinate） | partial，marker 原样保留、card_type 为 None | ✅ |
| 文件不存在 | failed（不抛 FileNotFoundError） | ✅ |
| 一批坏文件连续解析 | 逐个返回结果，整体不崩 | ✅ |
| 损坏 ZIP | failed + is_zipmod=False | ✅ |
| 非 ZIP 内容 | failed | ✅ |
| ZIP 内无 manifest.xml | failed + 「不是 ZIPMOD」 | ✅ |
| manifest XML 非法 | failed + 「不是合法 XML」，is_zipmod 仍为 True | ✅ |
| manifest 缺 guid | partial + warning | ✅ |
| manifest 属性式写法 | ok | ✅ |
| manifest 在子目录 | ok，`manifest_entry` 记录实际路径 | ✅ |
| 加密 manifest（模拟 RuntimeError） | failed + 「可能被加密」 | ✅ |
| 一批坏 zipmod 连续解析 | 全部 failed 且都有 error，不崩 | ✅ |

### 7. 完整 pytest 结果

```text
161 passed in 2.40s

tests/test_database_schema.py         9
tests/test_database_transactions.py   7
tests/test_fts_backfill.py            5
tests/test_library_cli.py            11
tests/test_library_store.py          21
tests/test_migration_v2.py           27
tests/test_parser_card.py            41   （本轮新增）
tests/test_parser_errors.py          20   （本轮新增）
tests/test_parser_zipmod.py          18   （本轮新增）

node tools/validate_schema.mjs        exit=0
node tools/check_model_sync.mjs       exit=0
```

1.2-A 完成时是 80 passed，本轮 +81。

### 8. 是否确认 22 cards + 13 zipmods 全部通过

**确认：22/22 卡片解析成功（全部 `ok`），13/13 zipmod 解析成功（全部有 guid）。**
不是抽样 —— `test_all_cards_are_parsed` 会先断言目录里正好有 22 张卡、
`test_all_zipmods_are_parsed` 断言正好 13 个 zipmod，再逐个解析并汇总失败清单。

### 9. 真实样本目录 SHA256 前后是否完全一致

**完全一致，无新增、无删除、无内容变化。**

```text
文件数: 36
全目录合并 SHA256（测试前）: 2f203ab77c77ae1ccbb69959bad2ab2ab4c3712fc97fb45abeb8b6cdb027f5cf
pytest: 159 passed in 2.34s          （当时尚未加入新增的 2 个用例）
全目录合并 SHA256（测试后）: 2f203ab77c77ae1ccbb69959bad2ab2ab4c3712fc97fb45abeb8b6cdb027f5cf
一致性: 完全一致 ✅   新增: [] 删除: [] 内容变化: []
```

另有一道自动化护栏：`tests/conftest.py` 的 `sample_root` 夹具会在**每个会话开始时**
记录样本目录全部文件的 sha256、**结束时再算一次**并断言一致 ——
也就是说「Parser 只读」这个约束从此每天都被测试守着。

### 10. 本轮发现的新事实（非冲突，供登记）

**KK（原版）卡片没有 `About` 块。**

- 样本：`I_.../同名不同目录/old_female/Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png`
  （marker `【KoiKatuChara】`）
- 实测：它的 lstInfo 只有 **5 个块** —— `Coordinate / Custom / KKEx / Parameter / Status`，
  **没有 `About`**；而 KKS 版本（同目录 `female/`）有 6 个块、含 `About` 与 `userID`/`dataID`。
- 结论：`userID` / `dataID` 在 KK 卡上**不可得**，这是格式差异而不是解析失败。
- 处理：解析器在 About 缺失时把 `user_id` / `data_id` 留 `None`，**不降级为 partial**、
  也不编造值；已有测试 `test_kk_format_has_no_about_block` 固定这一行为。
- 影响面：Phase 1.2-C 入库时，KK 卡片的 `metadata_json.data_id` 会缺省。

> 这条**不与既有分析结论冲突**（原分析只验证了 KKS 卡的 About 块），
> 因此没有自行改动数据模型，仅按上述方式处理并登记。

---

## 1.2-C：Scanner 入库（✅ 已完成）

### 结论

**Scanner 完成，209 passed + 1 xfailed；真实样本首次扫描 35/35 全部入库，第二次全部跳过。**
真实样本目录 SHA256 测试前后**完全一致**。

> ⚠️ **一处必须上报的冲突**：1.2-C §八 要求写入 `resource_authors` / `metadata_json.authors_raw`，
> 但**已确认的 Parser(1.2-B) 并不输出作者信息**（`CharacterCardParseResult` 里没有 `authors` 字段，
> 也不暴露 `marco.authordata` 的原始数据）。按「不偷偷修改 Parser」的要求，本轮**没有动 Parser**：
> Scanner 的作者入库代码已写好并通过 `getattr(parsed, "authors", None)` 接线，等 Parser 补齐字段即可生效；
> 相关验收测试标记为 `xfail(strict=True)`。详见 §14。

### 1. Scanner 新增 / 修改了哪些文件

| 文件 | 状态 | 说明 |
| :--- | :--- | :--- |
| `core/scanner/models.py` | 新增 | `ScanStats` / `ScanIssue` / `ScanResult` + 阶段常量 |
| `core/scanner/store.py` | 新增 | `ResourceStore`：入库层（只写库，不遍历、不解析） |
| `core/scanner/scanner.py` | 新增 | `LibraryScanner`：遍历 + 增量判定 + 调 Parser + 事务 + scan_records |
| `core/scanner/__init__.py` | 修改 | 占位文档 → 导出实现 |
| `main.py` | 修改 | 新增 `scan [<id\|路径>] [--full]` 子命令 |
| `tests/builders.py` | 新增 | 合成样本构造器（卡片 / zipmod / 普通 PNG / 损坏文件） |
| `tests/test_scanner.py` | 新增 | 30 个 synthetic 用例 |
| `tests/test_scanner_samples.py` | 新增 | 19 个真实样本用例（含 1 个 xfail） |
| `docs/phase1/PHASE1_2_REPORT.md` / `docs/ARCHITECTURE.md` / `README.md` | 修改 | 文档同步 |

**未改动**：`core/parsers/*`（Parser 行为保持不变）、`core/database/*`、`core/library/*`、
`core/models/*`、`ui/*`、`tools/*`。**Schema 没有变化**（仍为 v2，无新迁移）。

### 2. Scanner → Parser → DB 的实际调用链

| 步骤 | 代码 |
| :--- | :--- |
| CLI 入口 | `main.py scan [<id\|路径>] [--full]` → `cmd_scan` |
| 读 Library | `LibraryStore.require(library_id)`（含 `enabled` 检查） |
| 递归遍历 | `iter_candidates(root, ('.png', '.zipmod', '.zip'))`，`os.walk` + 排序保证顺序稳定 |
| 增量判定 | `ResourceStore.find_by_path_key()` 比对 `(file_size, modified_time)` |
| 只读解析 | `core.parsers.parse_card(path)` / `parse_zipmod(path)` |
| 入库 | `with db.transaction(conn): ResourceStore.upsert_card_resource()` / `upsert_mod_resource()` |
| 关系重建 | `_replace_plugins` / `_replace_usages` / `_replace_authors` |
| 收尾 | `ResourceStore.mark_missing(library_id, seen_keys)` + 回填 `scan_records` |

**扩展名只决定「是否值得尝试解析」**：`.png` 交给 card parser，`.zipmod` / `.zip` 交给 zipmod parser；
最终是不是资源、是什么类型，完全由 Parser 的结果决定。Scanner 里没有任何
「按文件名 / 目录名 / GUID 外观 / 文件大小判断类型」的代码。

### 3. 增量判定逻辑

```text
existing = SELECT * FROM resources WHERE file_path_key = ?

if mode == 'incremental' and existing is not None
   and existing.file_size == stat.st_size
   and abs(existing.modified_time - stat.st_mtime) < 1e-6:
        skipped += 1          # 不调用 Parser
        touch_present(id)     # 若之前被标记 missing → 恢复 present
        return
else:
        parsed += 1           # 调 Parser
```

- 路径先经 `db.normalize_path_key` 归一化（大小写 / 分隔符 / 尾斜杠无关）。
- **不做全量 SHA256**（本轮完全没有引入哈希计算）。
- `mode='full'` 时忽略上面的捷径，全部重新解析（`scan_records.mode='full'`）。
- **不自动删除**：文件消失只把 `scan_status` 置为 `missing`，资源行与关系行全部保留
  （Phase 1.1 只在 schema 里定义了 `missing` 状态，没有定义删除策略，因此按「不删」执行）。

### 4. 各表的入库规则

| 表 | 规则 |
| :--- | :--- |
| `resources` | 一个文件一行（`file_path_key` 唯一）。卡片写 `name/display_name/file_path/relative_path/file_size/modified_time/extension/parse_status/parse_error/card_marker/metadata_json`；zipmod 写 `resource_type='mod'`。`library_id` 指向当前库。`type_source='user'` 时**不覆盖**用户改过的类型；`display_name` 被用户改写过也不覆盖。 |
| `resource_plugins` | 每张卡的 `plugin_guids[]` 各一行，主键 `(resource_id, plugin_guid)`。**绝不写进 `mods`**。重建式写入（先删后插）→ 重扫不产生重复。 |
| `resource_mod_usages` | `dependencies[]` **逐条**写入（不去重）：`mod_guid / property / slot / local_slot / category_no`。本轮最重要的表。 |
| `resource_mods` | 按 `(resource_id, mod_guid)` 汇总一行，`ref_count` = 该组合的 usage 行数，`relation='uses'`；本地已安装则回填 `mod_id`，缺失则留空。 |
| `mods` | 仅 zipmod 写入，以 `guid` 为身份（`ON CONFLICT(guid) DO UPDATE`），写 `guid/name/author/version/website/file_path/file_path_key/resource_id/library_id`。**空 author / version="0" 照写**，非 dotted GUID（如 `shinyBunny`）正常接受。 |
| `resource_authors` + `authors` | 在 Phase 1.2-D 打通（见 §15）：按 `partition_authors` 规则，哨兵 `[Unknown]` 不建 `authors` 实体，`ordinal` / `raw_name` 保留。 |
| 缺失 MOD | 只建 `resource_mod_usages` / `resource_mods` 关系行，**不凭空创建 `mods` 实体**（除非本地真扫到该 zipmod）。 |

**v2 不变式的保持**：`resource_mods` 每个 `(resource_id, mod_guid)` 恰好 1 行，
`ref_count` == usage 行数 —— 用真实样本验证过（见 §7、§8）。

**一处刻意的合并**：`resource_mod_usages` 的主键是 `(resource_id, mod_guid, property)`，
因此同一 `(mod_guid, property)` 的重复记录会按主键合并（保留第一条）。
真实样本里**没有**这种重复 —— 22 张卡的 usage 行数与 Parser 的 dependency 记录数逐一对上
（如 Yuuki 220 条），测试对此有断言。

### 5. scan_records 统计规则

**没有改动 schema**（仍是 v1 的那些列），采用同义映射：

| 用户命名 | scan_records 列 | 含义 |
| :--- | :--- | :--- |
| discovered | `files_seen` | 候选文件数（按扩展名筛出的） |
| inserted | `files_new` | 新建的资源行 |
| updated | `files_changed` | 内容变化后更新的资源行 |
| skipped | `files_skipped` | size+mtime 未变、未调用 Parser |
| missing | `files_missing` | 上次入库、这次磁盘上找不到 |
| failed | `files_failed` | 失败（含「不是卡片 / 不是 zipmod」） |
| parsed | **无对应列** | 只在 `ScanResult.stats.parsed` 与 CLI 输出里报告 |

`parsed` 没有对应列，本轮**没有为了它新增列**——按「保留现有 scan_records 语义、不擅自改 schema」处理。
如果需要长期留痕，可后续加一个 `files_parsed` 列（v3 迁移）。

`scan_records.status`：开始写 `running`，结束改 `completed`（或 `failed`），
并回填 `duration_ms / finished_at`；前 5 条 issue 摘要写进 `error_message`。

### 6. transaction / failure isolation 方案

**每个文件一个 `db.transaction`**（用户明确允许该方案）：

| 文件 | 结果 |
| :--- | :--- |
| File A | `with transaction:` 写 resources + 全部关系 → 提交 |
| File B | Parser 失败 → 不进事务，记 `failed` 记录 |
| File C | `with transaction:` 写 resources + 全部关系 → 提交 |

- 文件在**入库阶段**抛异常 → 该文件的事务整体回滚（资源行与关系行都不会留半截），
  记 `stage='store'` 的 issue，**批次继续**。
- 实测（synthetic）：A/B/C 三个文件、B 的入库被强制抛错 → 只有 A、C 入库，
  `resource_mod_usages` 为 0 行（B 的回滚没有留下任何关系）。
- 另测「关系写入中途失败」→ 该文件的 `resources` 行也一并回滚。

选「每文件一个事务」而不是「整批一个事务」，是为了让「一个坏文件不毁掉整批」
成为**结构性保证**，而不是靠 savepoint 技巧。

### 7. 真实样本 acceptance test

`tests/test_scanner_samples.py`：直接扫描真实样本目录（只读），18 passed + 1 xfailed。

| 验收点 | 结果 |
| :--- | :--- |
| 首次扫描 35 个候选全部入库 | ✅ 22 卡 + 13 mod，failed=0 |
| 资源类型只有 `character_card` / `mod` | ✅ 没有 eyes/skin/hair/accessory |
| Sayaka | ✅ 4 usages / 1 unique MOD / `resource_mods.ref_count=4` |
| Kyoko | ✅ 5 usages / 3 unique MOD；本地有的回填 `mod_id`，缺失的为空 |
| Ayame | ✅ `ChaFileFace.eyelineUpId` / `Pupil1` / `Pupil2` 原样进 `property`；无任何 eye-source 字段 |
| Cocoa | ✅ metadata `embedded_texture_count=7`；2 个 MOD；`ChaFileBody.detailId` 在 usages |
| E 组服装 | ✅ `outfit6.ChaFileClothes.ClothesTop` / `outfit3,6...ClothesBot` 原样保留 |
| G 组孤立 MOD | ✅ 3 个 zipmod 都入库且 `resource_mods` 里 0 引用；NoHair 的 `author=""`、`version="0"` 正常写入 |
| H 组 naginata | ✅ 反向查询命中 2 个不同 resource，槽位不同，`mod_id` 一致 |
| I 组 Kugisaki | ✅ `KoiKatuCharaSun` 与 `KoiKatuChara` 分开存；**3 个不同路径都保留**（不做静默去重） |
| I 组 Kobeni | ✅ 两张卡都在库、`data_id` 不同、各自保留自己的 usage |
| J 组 Yuuki | ✅ 220 usages / 31 unique / 120 内嵌贴图 / 21 plugins |
| F 组多作者 | ⚠️ **xfail** —— Parser 未暴露作者（见 §14） |

### 8. 首次扫描统计

```text
[1] 真实样本（增量）  G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike
      发现 35 · 解析 35 · 新增 35 · 更新 0 · 跳过 0 · 失败 0 · 缺失 0      耗时 171 ms

resources              35      22 卡 + 13 mod
mods                   13
resource_mods         315      每个 (resource, mod) 一行
resource_mod_usages  1527      逐槽位，与 Parser 的 dependency 记录总数一致
resource_plugins      206      22 张卡的插件键总数
resource_authors        0      被 Parser 能力阻塞（§14）
authors                 0      同上
scan_records            2

MOD 回填：已安装(有 mod_id)=29   缺失(mod_id 为空)=286
共享 MOD naginata 反向命中资源数 = 2
未被任何卡片引用的 MOD（孤立）= 3
```

抽样核对：

```text
美樹さやか   usages=4    resource_mods=1   plugins=2   内嵌贴图=0
佐倉杏子     usages=5    resource_mods=3   plugins=2   内嵌贴图=0
保登心愛     usages=2    resource_mods=2   plugins=4   内嵌贴图=7
ユウキ       usages=220  resource_mods=31  plugins=21  内嵌贴图=120
```

### 9. 第二次扫描统计

```text
[1] 真实样本（增量）  G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike
      发现 35 · 解析 0 · 新增 0 · 更新 0 · 跳过 35 · 失败 0 · 缺失 0      耗时 3 ms
```

第二次扫描后 `resources(35) / mods(13) / resource_mods(315) / resource_mod_usages(1527) /
resource_plugins(206)` 全部保持不变，只有 `scan_records` 按预期 +1。

### 10. changed-file 测试结果

**真实副本上的完整流程**（`test_incremental_with_real_copies`，样本复制到临时目录后操作）：

```text
 复制 Rodney 到临时 Library → scan#1 : inserted=1
 原样再扫一次               → scan#2 : skipped=1, parsed=0
 给副本追加 1 字节           → scan#3 : updated=1, parsed=1, inserted=0
                                        resources 仍为 1 行；file_size 已更新
 删除副本                    → scan#4 : missing=1, resources 仍为 1 行
                                        scan_status='missing'（不删行、不删文件）
```

**关系重建**（`test_changed_card_relations_are_rebuilt`）：Sayaka 的副本被改动后重扫，
`resource_mod_usages` 仍然是 **4 行**（替换而不是累加），`resource_mods` 仍是 1 行。

### 11. 完整 pytest 结果

```text
209 passed, 1 xfailed in 6.59s

tests/test_database_schema.py          9
tests/test_database_transactions.py    7
tests/test_fts_backfill.py             5
tests/test_library_cli.py             11
tests/test_library_store.py           21
tests/test_migration_v2.py            27
tests/test_parser_card.py             43
tests/test_parser_errors.py           20
tests/test_parser_zipmod.py           18
tests/test_scanner.py                 30   （本轮新增）
tests/test_scanner_samples.py         19   （本轮新增，含 1 xfail）
```

1.2-B 结束时是 161 passed，本轮 **+48**。

### 12. `validate_schema.mjs` / `check_model_sync.mjs` 结果

```text
node tools/validate_schema.mjs   exit=0   （16 张业务表、幂等、v2 冒烟全 OK）
node tools/check_model_sync.mjs  exit=0   （schema 与 models 类型清单一致）
```

### 13. 真实样本目录 SHA256 是否变化

**完全一致，无新增 / 删除 / 内容变化。**

```text
样本文件数: 36
测试前合并 SHA256: 2f203ab77c77ae1ccbb69959bad2ab2ab4c3712fc97fb45abeb8b6cdb027f5cf
测试后合并 SHA256: 2f203ab77c77ae1ccbb69959bad2ab2ab4c3712fc97fb45abeb8b6cdb027f5cf
一致性: 完全一致
```

`tests/conftest.py` 的会话级护栏（测试前后自动比对全部文件 sha256）持续生效。

### 14. ~~上报冲突~~ 已解决：Parser 现在提供作者信息（Phase 1.2-D）

> **状态：已解决。** 下方记录的是冲突发生时的原始报告（1.2-C 结束时的状态），
> 保留作为审计线索。修复过程与结果见 **§15 Phase 1.2-D**。

**冲突内容**

- 1.2-C §八 要求：把 Parser 发现的多个作者写入 `resource_authors`（关联 `authors`），
  并在 `metadata_json.authors_raw` 保留原始列表。
- 但已确认的 Parser（1.2-B）**没有输出作者信息**：`CharacterCardParseResult` 里没有
  `authors` / `authors_raw` 字段，它只暴露 `plugin_guids` 与 `dependencies`，
  **不暴露 `marco.authordata` 的原始数据**。
- 而 1.2-C §十五 明确禁止「改变已经确认的 Parser 行为」。

**我没有做的事**：没有偷偷给 Parser 加字段、没有改 Schema、没有让 Scanner 自己解析卡片
（那会违反「Scanner 不允许自己重新解析卡片」）。

**当前处理**

- Scanner 侧的作者入库代码**已实现并接线**：
  `authors_raw = getattr(parsed, "authors", None)` → `ResourceStore._replace_authors()`。
  今天 Parser 没有这个属性 → 取到 `None` → `resource_authors` 为空，
  且 `metadata_json.authors_raw` **不写**（不会伪造成 `[]` 谎称「无作者」）。
- 验收测试 `test_group_f_authors_are_stored` 标记 `xfail(strict=True)`：
  一旦 Parser 补上作者字段它会自动变绿；若届时不生效会立即报错。
- 现有 Parser 行为**一个字节都没改**，1.2-B 的用例继续全绿。

**建议的解法（等你确认，本轮不执行）**

给 `CharacterCardParseResult` 增加两个**纯新增**字段（约 10 行）：

```python
authors: list[str] = field(default_factory=list)      # 已去重的真实作者
authors_raw: list[str] = field(default_factory=list)  # 卡内原始列表（含哨兵）
```

数据来源是 `KKEx["marco.authordata"]` → `[版本, {"Authors": <msgpack 列表>}]`，
哨兵处理直接复用 `core.models.partition_authors`（1.2-A 已实现并有测试）。

这属于**新增能力**而不是修改既有行为（不改任何现有字段语义、不改 `parse_status`），
但要动 `core/parsers/`，所以按你的规则先停下来报告。

---

## 1.2-D：补齐 Parser 作者信息（✅ 已完成）

### 结论

**§14 的能力缺口已修复，作者功能正式打通，234 passed（0 failed / 0 xfailed）。**
真实样本再扫一次：22 卡 + 13 zipmod 全部正常，`resource_authors=14`、`authors=3`、无重复。
真实样本目录 SHA256 前后依旧**完全一致**。

### 1. 修改文件

| 文件 | 状态 | 改动 |
| :--- | :--- | :--- |
| `core/parsers/models.py` | 修改 | `CharacterCardParseResult` 新增 `authors` / `authors_raw`（默认空列表）；新增常量 `AUTHORS_PLUGIN_GUID` |
| `core/parsers/card.py` | 修改 | 新增 `_decode_authors_payload()` / `_extract_authors()`；`_extract_kkex()` 改为返回插件字典；抽取步骤改用具名 `safe()` 包装 |
| `core/parsers/__init__.py` | 修改 | 导出 `AUTHORS_PLUGIN_GUID` |
| `core/scanner/scanner.py` | 修改 | 作者来源从 `getattr(parsed, "authors", None)` 改为 **`parsed.authors_raw`**（原始列表） |
| `tests/builders.py` | 修改 | 合成卡片支持 `authors=` / `broken_authors=` |
| `tests/test_parser_card.py` | 修改 | +10 个作者用例（53 个） |
| `tests/test_scanner_samples.py` | 修改 | 去掉 xfail，+5 个作者用例（24 个） |
| `docs/phase1/PHASE1_2_REPORT.md` / `docs/ARCHITECTURE.md` | 修改 | 文档同步 |

**没有改**：Schema（仍 v2，无 v3）、数据库表结构、`parse_status` 规则、现有字段语义、
MOD dependency 语义、增量策略、UI、zipmod 内部解析。

### 2. 作者解析的实际结构

先对 22 张真实卡逐张实测，确认结构（**不是照文档猜的**）：

```text
KKEx["marco.authordata"] = [1, {"Authors": b"\x92\xa9[Unknown]\xa9Evaan"}]
                                    └── bytes，里面是一段 msgpack 列表

解码后 = ['[Unknown]', 'Evaan']
```

实测统计：**22 张卡里只有 12 张带 `marco.authordata`**，另外 10 张完全没有这个键
（A/B/C/D/E 组）。12 张的 `Authors` 全部是 **bytes** 形态（代码同时容忍直接给列表）。

| 组 | 卡 | `authors` | `authors_raw` |
| :--- | :--- | :--- | :--- |
| F | Hermione / Tatsumaki / Kugisaki | `['Evaan']` | `['[Unknown]', 'Evaan']` |
| I | female / old_female Kugisaki | `['Evaan']` | `['[Unknown]', 'Evaan']` |
| H | 长尾景虎 / 红豆 | `['Anonymous']` | `['[Unknown]', 'Anonymous']` |
| I | 两张 Kobeni | `['Azurou', 'Anonymous']` | 同左 |
| I | KK_317794 | `['Azurou']` | `['Azurou']` |
| I | [Yeeted] Sora | `['Anonymous']` | `['[Unknown]', 'Anonymous']` |
| J | ユウキ | `['Anonymous']` | `['Anonymous']` |
| A–E | 其余 10 张 | `[]` | `[]` |

**处理规则**（全部复用 1.2-A 的 `core.models.partition_authors`）：

- `authors_raw` = 卡内原始字符串列表，**顺序、空白、哨兵全部原样保留**。
- `authors` = 去空白、去重、**剔除 `[Unknown]` 之类的哨兵**后的真实作者。
- 卡片没有该键 → 直接返回（`[]`），**不记 warning、不影响 `parse_status`**。
- 该键结构损坏 → 记一条 warning（`parse_status` 变 `partial`），
  但**其它字段（名字、卡片 marker、MOD 依赖…）照常解析**。
- 绝不根据文件名 / 目录名推断作者。

### 3. Parser / Scanner 测试新增与结果

**Parser（`tests/test_parser_card.py`，新增 10 个）**

| 用例 | 断言 |
| :--- | :--- |
| F 组三张卡（参数化） | `authors == ['Evaan']`、`authors_raw == ['[Unknown]', 'Evaan']` |
| `[Unknown]` 不进真实作者 | 三张卡 `[Unknown] not in authors`，但 `in authors_raw` |
| 没有作者数据的卡 | 4 张代表卡 → `authors == []`、`parse_status == 'ok'`、无 author 相关 warning |
| 全样本作者统计 | 22 张里 12 张有作者；`Evaan` 命中 5 张（F 组 3 + I 组 2） |
| 不按文件名推断 | 合成 `..._Evaan.png`（卡内无作者数据）→ `authors == []` |
| 作者块损坏 | 合成损坏负载 → 整卡 `success`、名字/marker/MOD 依赖全部正常、留 warning |
| 去空白去重保原始 | `('[Unknown]', '  Evaan ', 'Evaan', 'Anonymous', '')` → `authors == ['Evaan','Anonymous']`，`authors_raw` 逐项原样 |

**Scanner（`tests/test_scanner_samples.py`，去掉 xfail + 新增 5 个）**

| 用例 | 断言 |
| :--- | :--- |
| `test_group_f_authors_are_stored`（原 xfail，现正式） | 建立 `resource_authors`；`authors` 里有 `Evaan`；无 `[Unknown]` 实体；`metadata.authors_raw == ['[Unknown]','Evaan']` |
| F 组三张卡逐一 | 各 1 条关联、`name='Evaan'`、**`ordinal=1`**（原始列表下标）、`raw_name='Evaan'` |
| 哨兵不成实体 | `authors` 表恰好 `{Evaan, Anonymous, Azurou}`，无 unknown |
| 重扫不重复 | 第二次扫描后 `resource_authors=14`、`authors=3`，`GROUP BY resource,author HAVING count>1` 为空 |
| 改动后重建 | 复制 Hermione 到临时库 → 改动内容 → 重扫 `updated=1`，作者关系仍为 1 条（替换而非累加） |
| 无作者的卡 | Madoka → `resource_authors=0`、`metadata.authors_raw == []` |

### 4. 完整 pytest 结果

```text
234 passed in 8.95s        （1.2-C 是 209 passed + 1 xfailed；xfail 清零）

tests/test_database_schema.py          9
tests/test_database_transactions.py    7
tests/test_fts_backfill.py             5
tests/test_library_cli.py             11
tests/test_library_store.py           21
tests/test_migration_v2.py            27
tests/test_parser_card.py             53   （+10）
tests/test_parser_errors.py           20
tests/test_parser_zipmod.py           18
tests/test_scanner.py                 36   （+6）
tests/test_scanner_samples.py         27   （+8，去掉 1 xfail）
```

### 4.1 `ordinal` 语义的一处修正（本轮返工点）

1.2-D 第一次实现时，`ordinal` 是**过滤掉哨兵后重新编号**的（Evaan 得到 0）。
按本轮明确要求「`ordinal` 保持原始列表语义」，已改为**原始列表下标**：

```text
authors_raw = ['[Unknown]', 'Evaan', 'Alice']
   ↓
Evaan  ordinal=1        ← 不是 0
Alice  ordinal=2
```

改动只在 `core/scanner/store.py::_replace_authors`：用 `enumerate(raw_list)` 取下标，
哨兵 / 空串 / 重复项仍然跳过（不建实体），但**不再重排后续作者的序号**。
真实样本上的实际效果：

| 卡 | `authors_raw` | 落库 ordinal |
| :--- | :--- | :--- |
| F 组三张 / I 组两张 Kugisaki | `['[Unknown]','Evaan']` | Evaan = **1** |
| H 组两张 / Sora | `['[Unknown]','Anonymous']` | Anonymous = **1** |
| 两张 Kobeni | `['Azurou','Anonymous']` | Azurou = 0、Anonymous = 1 |
| KK_317794 | `['Azurou']` | Azurou = 0 |
| ユウキ | `['Anonymous']` | Anonymous = 0 |

### 5. 22+13 真实样本结果

```text
scan#1  发现 35 · 解析 35 · 新增 35 · 更新 0 · 跳过 0 · 失败 0 · 缺失 0
scan#2  发现 35 · 解析 0  · 新增 0  · 更新 0 · 跳过 35 · 失败 0 · 缺失 0

resources              35      （22 卡 + 13 zipmod）
mods                   13
resource_mod_usages  1527      （与 1.2-C 完全一致，未被作者功能影响）
resource_plugins      206      （同上）
resource_authors       14
authors                 3      ['Anonymous', 'Azurou', 'Evaan']
重复作者关系             0
```

22 张卡的 `parse_status` **全部仍是 `ok`** —— 新增作者解析没有改变任何一张卡的状态。

### 6. 作者数据库结果

```text
authors                = Evaan(1) / Anonymous(2) / Azurou(3)     ← 无 [Unknown]
resource_authors       = 14 条

F 组三张卡：
  GrangerHermione  → Evaan, ordinal=1, raw_name='Evaan'   （raw = ['[Unknown]','Evaan']）
  Tatsumaki        → Evaan, ordinal=1, raw_name='Evaan'
  KugisakiNobara   → Evaan, ordinal=1, raw_name='Evaan'

metadata_json.authors_raw（F 组抽样）= ['[Unknown]', 'Evaan']
```

`resources.author` / `resources.author_id`（v1 的单值列）**保持不写**：多作者由
`resource_authors` 表达，不去维护一个容易失真的冗余单值字段（这是刻意选择，不是遗漏）。

### 7. SHA256 前后结果

```text
样本文件数: 36
测试前合并 SHA256: 2f203ab77c77ae1ccbb69959bad2ab2ab4c3712fc97fb45abeb8b6cdb027f5cf
测试后合并 SHA256: 2f203ab77c77ae1ccbb69959bad2ab2ab4c3712fc97fb45abeb8b6cdb027f5cf
样本目录一致性: 完全一致
```

### 8. 是否还有 xfail / known issue

**没有 xfail 了**（`0 xfailed`）。当前已知项：

| # | 项 | 状态 |
| :--- | :--- | :--- |
| 1 | `scan_records` 没有 `files_parsed` 列 | 设计选择：`parsed` 只在 `ScanResult` / CLI 输出里报告；要长期留痕需 v3 迁移 |
| 2 | `resources.author` / `author_id` 未写入 | 设计选择：多作者以 `resource_authors` 为准 |
| 3 | 重复检测（`duplicate_groups`）未实现 | Phase 4 范围，本阶段只保证相同内容的不同路径都保留 |
| 4 | zipmod 内部资源结构未解析 | Phase 2 范围 |
| 5 | 内嵌贴图只计数、不解释业务类型 | 既定设计 |

---

## Phase 1.3 及以后（未开始）

本轮停在 1.2-D，没有进入 1.3。
