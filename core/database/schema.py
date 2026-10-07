"""SQLite schema 定义（版本化迁移）。

设计原则
--------
1. **DDL 内嵌在 Python 里**（不是外部 .sql 文件）——PyInstaller 打包后不会因
   忘记 ``--add-data`` 而在运行时找不到文件。
2. **版本化**：``SCHEMA_VERSION`` + ``MIGRATIONS``。以后每个 Phase 只追加新的
   迁移项，不改动历史迁移，保证老用户数据库能平滑升级。
3. **外键约束**：连接时开启 ``PRAGMA foreign_keys=ON``。
4. **只存索引与用户信息**：资源路径、大小、修改时间、哈希、解析摘要、
   标签、集合、关系；绝不存文件内容。
5. **路径大小写无关**：Windows 上路径不区分大小写，因此所有路径都额外保存
   一个归一化列（``*_path_key``）并对其建唯一索引，避免同一文件被重复入库。

归一化路径 key 的生成见 ``core.database.db.normalize_path_key``。
"""

from __future__ import annotations

# 当前 schema 版本。任何 DDL 变更都必须 +1 并新增 MIGRATIONS 条目。
# v1 = Phase 0 基础结构；v2 = Phase 1.2（真实样本分析后的模型补强）。
SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# v1 —— Phase 0 基础结构
# ---------------------------------------------------------------------------

_V1_SQL = """
-- ===================== 元信息 =====================
CREATE TABLE IF NOT EXISTS app_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ===================== 资源库（扫描根目录）=====================
-- 用户可以添加多个 Library（D:/KKS/Cards、E:/Downloads/KKS、F:/Archive …）。
CREATE TABLE IF NOT EXISTS libraries (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    root_path     TEXT    NOT NULL,
    root_path_key TEXT    NOT NULL UNIQUE,
    enabled       INTEGER NOT NULL DEFAULT 1,   -- 0=暂停扫描
    notes         TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    last_scan_at  TEXT
);

-- ===================== 作者 =====================
-- 作者是独立概念，不依附于文件名；可由用户手动修改。
CREATE TABLE IF NOT EXISTS authors (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    name_key    TEXT NOT NULL UNIQUE,     -- 归一化（trim + casefold）用于去重
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ===================== 资源（核心实体）=====================
-- 一个文件 = 一个资源（Phase 1 建立；未来可由关系表表达“一文件多资源”）。
CREATE TABLE IF NOT EXISTS resources (
    id              INTEGER PRIMARY KEY,
    resource_type   TEXT    NOT NULL DEFAULT 'unknown'
        CHECK (resource_type IN (
            'character_card','outfit_card','scene_card','mod',
            'skin','eyes','hair','accessory','other','unknown'
        )),
    -- 类型来源：auto=自动识别，user=用户人工确认/修正（人工结果优先，重扫不覆盖）
    type_source     TEXT    NOT NULL DEFAULT 'auto'
        CHECK (type_source IN ('auto','user')),
    library_id      INTEGER REFERENCES libraries(id) ON DELETE SET NULL,

    name            TEXT,             -- 解析出的原始名（如角色名）
    display_name    TEXT,             -- 界面展示名（可被用户改写）

    file_path       TEXT    NOT NULL, -- 绝对路径（展示用原样保留）
    file_path_key   TEXT    NOT NULL UNIQUE,  -- 归一化路径，防重复入库
    relative_path   TEXT,             -- 相对 Library 根目录的路径
    file_size       INTEGER,          -- 字节
    modified_time   REAL,             -- 文件 mtime（epoch 秒，含小数）
    extension       TEXT,             -- 小写扩展名，如 '.png' '.zipmod'

    sha256          TEXT,             -- 全量哈希（按需计算，不做首次扫描默认项）
    quick_hash      TEXT,             -- 快速指纹（大小+首尾块），用于去重预筛
    content_key     TEXT,             -- 资源级重复键（卡片内容摘要，见 Phase 4）

    thumbnail_path  TEXT,             -- 缩略图缓存相对路径（thumbnail_cache/）
    source          TEXT,             -- 来源（下载站/群/作者包 …）
    author          TEXT,             -- 原始作者文本（可能来自 Level 3 推断）
    author_id       INTEGER REFERENCES authors(id) ON DELETE SET NULL,
    series          TEXT,             -- 系列/作品名
    description     TEXT,
    notes           TEXT,             -- 用户备注
    metadata_json   TEXT,             -- 解析出的其余元数据（JSON，宽松存储）

    scan_status     TEXT    NOT NULL DEFAULT 'new'
        CHECK (scan_status IN ('new','present','missing','error')),
    parse_status    TEXT    NOT NULL DEFAULT 'unparsed'
        CHECK (parse_status IN ('unparsed','ok','partial','failed','skipped')),
    parse_error     TEXT,
    needs_review    INTEGER NOT NULL DEFAULT 0,  -- 1=进入“待确认”

    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    last_scanned_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_resources_type         ON resources(resource_type);
CREATE INDEX IF NOT EXISTS idx_resources_library      ON resources(library_id);
CREATE INDEX IF NOT EXISTS idx_resources_author_id    ON resources(author_id);
CREATE INDEX IF NOT EXISTS idx_resources_sha256       ON resources(sha256);
CREATE INDEX IF NOT EXISTS idx_resources_quick_hash   ON resources(quick_hash);
CREATE INDEX IF NOT EXISTS idx_resources_content_key  ON resources(content_key);
CREATE INDEX IF NOT EXISTS idx_resources_needs_review ON resources(needs_review)
    WHERE needs_review = 1;
CREATE INDEX IF NOT EXISTS idx_resources_relative     ON resources(relative_path);

-- ===================== 标签（多对多）=====================
CREATE TABLE IF NOT EXISTS tags (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    name_key    TEXT NOT NULL UNIQUE,     -- 归一化，避免 "Favorite"/"favorite" 重复
    color       TEXT,                     -- 可选展示色，如 '#8ab4f8'
    category    TEXT,                     -- 可选分组（如 '状态' / '风格'）
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS resource_tags (
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id)      ON DELETE CASCADE,
    origin      TEXT    NOT NULL DEFAULT 'user'
        CHECK (origin IN ('user','auto')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (resource_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_resource_tags_tag ON resource_tags(tag_id);

-- ===================== Collection（多对多）=====================
-- Collection 与文件目录结构完全分离：加入 Collection 不移动文件。
CREATE TABLE IF NOT EXISTS collections (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    name_key    TEXT NOT NULL UNIQUE,
    description TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS resource_collections (
    resource_id   INTEGER NOT NULL REFERENCES resources(id)   ON DELETE CASCADE,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    added_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    sort_order    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (resource_id, collection_id)
);

CREATE INDEX IF NOT EXISTS idx_resource_collections_col ON resource_collections(collection_id);

-- ===================== MOD 索引 =====================
-- 一个 zipmod 一个 GUID；GUID 来自 manifest.xml。
CREATE TABLE IF NOT EXISTS mods (
    id            INTEGER PRIMARY KEY,
    guid          TEXT NOT NULL UNIQUE,
    name          TEXT,
    author        TEXT,
    version       TEXT,
    description   TEXT,
    website       TEXT,
    game          TEXT,                   -- manifest 里的 game（如 'koikatu'）
    file_path     TEXT,                   -- zipmod/zip 所在路径
    file_path_key TEXT UNIQUE,            -- 归一化路径；非文件型 mod 允许为空
    resource_id   INTEGER REFERENCES resources(id) ON DELETE SET NULL,
    library_id    INTEGER REFERENCES libraries(id) ON DELETE SET NULL,
    md5           TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_mods_guid ON mods(guid);
CREATE INDEX IF NOT EXISTS idx_mods_file_path_key ON mods(file_path_key);
CREATE INDEX IF NOT EXISTS idx_mods_resource ON mods(resource_id);

-- ===================== 角色卡 → MOD 依赖 =====================
-- 关键设计：**即使该 MOD 未安装也允许存在依赖记录**，因此
-- 主键用 mod_guid（而不是 mod_id）；mod_id 仅在本地已安装时回填。
CREATE TABLE IF NOT EXISTS resource_mods (
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    mod_guid    TEXT    NOT NULL,
    mod_id      INTEGER REFERENCES mods(id) ON DELETE SET NULL,
    relation    TEXT    NOT NULL DEFAULT 'uses'
        CHECK (relation IN ('uses','embeds')),
    ref_count   INTEGER NOT NULL DEFAULT 1,   -- 卡内引用次数
    detected_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (resource_id, mod_guid)
);

CREATE INDEX IF NOT EXISTS idx_resource_mods_guid     ON resource_mods(mod_guid);
CREATE INDEX IF NOT EXISTS idx_resource_mods_resource ON resource_mods(resource_id);

-- ===================== 重复检测 =====================
CREATE TABLE IF NOT EXISTS duplicate_groups (
    id          INTEGER PRIMARY KEY,
    group_type  TEXT NOT NULL DEFAULT 'file'
        CHECK (group_type IN ('file','content')),
    hash_key    TEXT NOT NULL,            -- sha256 或 content_key
    confidence  REAL NOT NULL DEFAULT 1.0,
    status      TEXT NOT NULL DEFAULT 'suggested'
        CHECK (status IN ('suggested','confirmed','dismissed')),
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_duplicate_groups_hash ON duplicate_groups(hash_key);

CREATE TABLE IF NOT EXISTS duplicate_members (
    group_id     INTEGER NOT NULL REFERENCES duplicate_groups(id) ON DELETE CASCADE,
    resource_id  INTEGER NOT NULL REFERENCES resources(id)        ON DELETE CASCADE,
    similarity   REAL NOT NULL DEFAULT 1.0,
    is_canonical INTEGER NOT NULL DEFAULT 0,   -- 用户指定的保留项
    PRIMARY KEY (group_id, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_duplicate_members_resource ON duplicate_members(resource_id);

-- ===================== 扫描记录 =====================
CREATE TABLE IF NOT EXISTS scan_records (
    id            INTEGER PRIMARY KEY,
    library_id    INTEGER REFERENCES libraries(id) ON DELETE CASCADE,
    mode          TEXT NOT NULL DEFAULT 'incremental'
        CHECK (mode IN ('full','incremental')),
    status        TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running','completed','cancelled','failed')),
    started_at    TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at   TEXT,
    duration_ms   INTEGER,
    files_seen    INTEGER NOT NULL DEFAULT 0,
    files_new     INTEGER NOT NULL DEFAULT 0,
    files_changed INTEGER NOT NULL DEFAULT 0,
    files_skipped INTEGER NOT NULL DEFAULT 0,
    files_missing INTEGER NOT NULL DEFAULT 0,
    files_failed  INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_records_library ON scan_records(library_id, started_at);
"""


# ---------------------------------------------------------------------------
# 可选：FTS5 全文检索表
# ---------------------------------------------------------------------------
# 名称可能是中日文，用 trigram 分词器才能做子串匹配（unicode61 对 CJK 无效）。
# 部分 SQLite 构建不含 FTS5 或版本过旧 → 由 db.initialize() 做“尽力启用”，
# 失败时回退到 LIKE 查询，不影响主流程。

_V1_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS resources_fts USING fts5(
    display_name, name, author, series, description, notes,
    content='resources',
    content_rowid='id',
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS resources_fts_ai AFTER INSERT ON resources BEGIN
    INSERT INTO resources_fts(rowid, display_name, name, author, series, description, notes)
    VALUES (new.id, new.display_name, new.name, new.author, new.series, new.description, new.notes);
END;

CREATE TRIGGER IF NOT EXISTS resources_fts_ad AFTER DELETE ON resources BEGIN
    INSERT INTO resources_fts(resources_fts, rowid, display_name, name, author, series, description, notes)
    VALUES ('delete', old.id, old.display_name, old.name, old.author, old.series, old.description, old.notes);
END;

CREATE TRIGGER IF NOT EXISTS resources_fts_au AFTER UPDATE ON resources BEGIN
    INSERT INTO resources_fts(resources_fts, rowid, display_name, name, author, series, description, notes)
    VALUES ('delete', old.id, old.display_name, old.name, old.author, old.series, old.description, old.notes);
    INSERT INTO resources_fts(rowid, display_name, name, author, series, description, notes)
    VALUES (new.id, new.display_name, new.name, new.author, new.series, new.description, new.notes);
END;
"""


# ---------------------------------------------------------------------------
# v2 —— Phase 1.2：真实样本分析暴露出的模型缺口
# ---------------------------------------------------------------------------
#
# 背景见 docs/phase1/SAMPLE_ANALYSIS.md。四类信息在 v1 里无处安放：
#
# ① 卡片格式（KKS / KK）：样本里同一角色同时存在 【KoiKatuCharaSun】 与
#    【KoiKatuChara】 两个版本，必须能区分，但又不能当成身份键。
# ② 插件（KKEx）：每张卡 1–21 个插件，它们**不是** zipmod（没有 manifest），
#    绝不能写进 mods 表，否则「MOD 依赖」会被污染。
# ③ 逐槽位依赖：sideloader 的 info 是**每槽位一条记录**，形如
#    `outfit6.accessory10.ChaFileAccessory.PartsInfo.id`。只存
#    `(resource_id, mod_guid)` 会丢掉「用在哪」，也就丢失了眼睛/皮肤/衣服/配饰
#    这些**关系语义**。
# ④ 多作者：`marco.authordata` 返回的是列表（如 `['[Unknown]', 'Evaan']`）。
#
# 约定（Phase 1.2 起必须遵守）：
# - `skin` / `eyes` / `hair` / `accessory` **不允许**作为 PNG 文件类型自动写入；
#   这些语义只存在于 `resource_mod_usages.property` 里。
# - `dataID` **不得**作为资源身份或唯一键（同一角色每次保存都可能变化）。

_V2_SQL = """
-- ===================== 资源：卡片游戏格式 =====================
-- 实测取值：'KoiKatuCharaSun'（KKS）/ 'KoiKatuChara'（KK）。
-- 只描述格式，不是身份：同一角色可以有两个 marker。
CREATE INDEX IF NOT EXISTS idx_resources_card_marker ON resources(card_marker);

-- ===================== 插件（KKEx，与 MOD 严格区分）=====================
-- 插件 = 卡片 ExtensibleSaveFormat 里的键（moreAccessories / KSOX / marco.authordata …）。
-- 它们没有 manifest.xml、不是 zipmod，因此只在这里登记，不进 mods / resource_mods。
-- 插件数量 = 本表按 resource_id 的计数，不额外存冗余计数列。
CREATE TABLE IF NOT EXISTS resource_plugins (
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    plugin_guid TEXT    NOT NULL,
    detected_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (resource_id, plugin_guid)
);

CREATE INDEX IF NOT EXISTS idx_resource_plugins_guid ON resource_plugins(plugin_guid);

-- ===================== 卡片 → MOD 的逐槽位使用关系 =====================
-- 一个 MOD 被 N 个槽位使用 → N 行；唯一 MOD 数 = COUNT(DISTINCT mod_guid)。
-- property 例：outfit6.accessory10.ChaFileAccessory.PartsInfo.id
-- slot 例：10（配饰槽位号，可为 NULL）；category_no 来自卡内记录。
-- 未安装的 MOD 同样要建关系（本地没有 mods 行 → mod_id 为空，见 resource_mods）。
CREATE TABLE IF NOT EXISTS resource_mod_usages (
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    mod_guid    TEXT    NOT NULL,
    property    TEXT    NOT NULL,
    slot        INTEGER,
    local_slot  INTEGER,
    category_no INTEGER,
    detected_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (resource_id, mod_guid, property)
);

CREATE INDEX IF NOT EXISTS idx_resource_mod_usages_guid
    ON resource_mod_usages(mod_guid);
CREATE INDEX IF NOT EXISTS idx_resource_mod_usages_resource
    ON resource_mod_usages(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_mod_usages_property
    ON resource_mod_usages(property);

-- ===================== 多作者 =====================
-- 一张卡可以有多个作者；`authors` 表仍是去重后的作者实体。
-- `[Unknown]` 之类的哨兵值**不建** authors 行（避免污染作者聚合），
-- 但其原始值必须保留在 `resources.metadata_json.authors_raw` 里。
-- `raw_name` 保存该卡上的原始写法，避免归一化后丢失大小写/空白信息。
CREATE TABLE IF NOT EXISTS resource_authors (
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    author_id   INTEGER NOT NULL REFERENCES authors(id)   ON DELETE CASCADE,
    ordinal     INTEGER NOT NULL DEFAULT 0,   -- 卡内出现顺序
    raw_name    TEXT    NOT NULL DEFAULT '',  -- 该卡上的原始写法
    PRIMARY KEY (resource_id, author_id)
);

CREATE INDEX IF NOT EXISTS idx_resource_authors_author ON resource_authors(author_id);
"""


# 每个迁移额外需要的「幂等加列」：(表名, 列名, 列定义)。
# 单独列出而不是写进 DDL，是因为 SQLite 的 ADD COLUMN 不是幂等的
# （重复执行会报 duplicate column name）；db.initialize() 会先查 PRAGMA 再决定加不加。
MIGRATION_ADDED_COLUMNS: dict[int, tuple[tuple[str, str, str], ...]] = {
    2: (("resources", "card_marker", "TEXT"),),
}


# 版本号 -> (迁移 DDL, 可选 FTS DDL)。FTS 允许启用失败。
MIGRATIONS: dict[int, tuple[str, str]] = {
    1: (_V1_SQL, _V1_FTS_SQL),
    2: (_V2_SQL, ""),
}


# resources.metadata_json 中约定写入的键（Phase 1.2 起）。
# 原则：只放「已确认有价值、但不值得单独建表」的卡片元数据。
RESOURCE_METADATA_KEYS: tuple[str, ...] = (
    "user_id",                 # About.userID（制作者 id，不是资源身份）
    "data_id",                 # About.dataID（**不得**作为身份或唯一键）
    "card_version",            # 容器头的卡片版本字符串
    "embedded_texture_count",  # 数据区内嵌 PNG 数量（不解释业务类型）
    "plugin_count",            # 插件数；权威值仍是 resource_plugins 的行数
    "authors_raw",             # 卡内作者原始列表（含 [Unknown] 等哨兵）
    "face_preview_kind",       # 面部预览图格式：'jpeg' | 'png'
    "block_sizes",             # lstInfo 各块字节数
)


# 自检用：v1 之后应当存在的业务表（不含 FTS 影子表与 sqlite 内部表）。
V1_TABLES: tuple[str, ...] = (
    "app_meta",
    "libraries",
    "authors",
    "resources",
    "tags",
    "resource_tags",
    "collections",
    "resource_collections",
    "mods",
    "resource_mods",
    "duplicate_groups",
    "duplicate_members",
    "scan_records",
)


# v2 新增的业务表（v1 的表全部保留，不删不改）。
V2_TABLES: tuple[str, ...] = (
    "resource_plugins",
    "resource_mod_usages",
    "resource_authors",
)


# 最新版本下应当存在的全部业务表 —— 自检 / 验证脚本用。
CURRENT_TABLES: tuple[str, ...] = V1_TABLES + V2_TABLES
