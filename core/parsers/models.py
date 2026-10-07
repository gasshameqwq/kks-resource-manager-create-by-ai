"""Parser 结果模型（结构化输出，替代随意 dict）。

命名与字段依据 `docs/phase1/PHASE1_2_REPORT.md` / `docs/phase1/SAMPLE_ANALYSIS.md`。

设计约定
--------
- **只读**：模型只描述「从文件里读到了什么」，不含任何入库/写入语义。
- ``parse_status`` 复用数据库里的取值口径：``ok`` / ``partial`` / ``failed``。

  * ``ok``      —— 关键字段全部解析成功；
  * ``partial`` —— 拿到了核心信息，但有非关键部分失败（细节见 ``warnings``）；
  * ``failed``  —— 不是可识别的卡片/zipmod，或关键结构损坏。

- **不做类型推断**：本模型里**没有** eyes / skin / hair / accessory 这类资源类型字段。
  这些语义只存在于 ``ModDependencyRecord.property`` 里，由调用方自行解释。
- 所有列表字段使用 ``field(default_factory=list)``，避免可变默认值共享。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# parse_status 取值
PARSE_OK = "ok"
PARSE_PARTIAL = "partial"
PARSE_FAILED = "failed"

# 目前确认可识别为「角色卡」的 marker（**必须保持区别，不做归一化**）
CHARACTER_CARD_MARKERS: tuple[str, ...] = (
    "KoiKatuCharaSun",  # Koikatsu Sunshine
    "KoiKatuChara",     # Koikatsu（原版）
)

# sideloader 插件键：其数据的 info 列表才是「卡片 → MOD」的依赖来源
MODLIST_PLUGIN_GUID = "com.bepis.sideloader.universalautoresolver"

# 作者插件键：实测结构 ``[版本, {"Authors": <msgpack 列表的 bytes>}]``。
# 注意：不是所有卡片都有这个键（真实样本里 22 张只有 12 张有）。
AUTHORS_PLUGIN_GUID = "marco.authordata"


@dataclass(frozen=True)
class LstInfoEntry:
    """卡片 lstInfo 里的一个数据块声明。

    注意：**列表顺序不是物理顺序**，读取时必须按 ``pos`` 排序。
    """

    name: str
    version: str = ""
    pos: int = 0
    size: int = 0


@dataclass(frozen=True)
class ModDependencyRecord:
    """卡片对某个 MOD 的**一条**使用记录（逐槽位，不去重）。

    字段与卡内实际记录一一对应，全部原样保留：
    ``ModID / Slot / LocalSlot / Property / CategoryNo / Author / Website / Name``。

    ``property`` 形如 ``outfit6.accessory10.ChaFileAccessory.PartsInfo.id`` ——
    眼睛/皮肤/衣服/配饰这类语义就在这里，但**解析器不做解释**。
    """

    mod_id: str
    property: str = ""
    slot: int | None = None
    local_slot: int | None = None
    category_no: int | None = None
    author: str | None = None
    website: str | None = None
    name: str | None = None


@dataclass
class CharacterCardParseResult:
    """一张 KKS/KK 角色卡的只读解析结果。"""

    path: str
    parse_status: str = PARSE_FAILED
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    # --- 容器头 ---
    product_no: int | None = None
    card_marker: str | None = None        # 去掉【】后的 marker，如 'KoiKatuCharaSun'
    card_marker_raw: str | None = None    # 原样（含【】），保留精确内容
    card_type: str | None = None          # 'character_card' | None（未知 marker）
    card_version: str | None = None
    face_preview_kind: str | None = None  # 'jpeg' | 'png' | 'unknown'
    face_preview_size: int = 0

    # --- Parameter ---
    name: str | None = None
    lastname: str | None = None
    firstname: str | None = None
    nickname: str | None = None
    personality: int | None = None

    # --- About ---
    user_id: str | None = None
    data_id: str | None = None            # 只作元数据，**不是**身份键

    # --- KKEx ---
    plugin_guids: list[str] = field(default_factory=list)
    dependencies: list[ModDependencyRecord] = field(default_factory=list)
    unique_mod_guids: list[str] = field(default_factory=list)
    # 作者：``authors`` 是去重后的真实作者；``authors_raw`` 是卡内原始列表
    # （`[Unknown]` 之类的哨兵只出现在 raw 里，不会进 authors）
    authors: list[str] = field(default_factory=list)
    authors_raw: list[str] = field(default_factory=list)

    # --- 内嵌贴图（只计数，不解释业务类型）---
    embedded_texture_count: int = 0

    # --- 结构信息（诊断用）---
    lst_info: list[LstInfoEntry] = field(default_factory=list)
    lst_info_reordered: bool = False
    file_level_reserved: int | None = None
    block_sizes: dict[str, int] = field(default_factory=dict)
    region_bytes: int = 0
    region_covers_to_eof: bool = False

    # ---- 便捷视图（不引入任何推断）----

    @property
    def success(self) -> bool:
        """是否可用于后续处理（ok 或 partial）。"""
        return self.parse_status in (PARSE_OK, PARSE_PARTIAL)

    @property
    def plugin_count(self) -> int:
        """插件数量（KKEx 键数）。"""
        return len(self.plugin_guids)

    @property
    def dependency_records(self) -> int:
        """依赖记录条数（**未去重**，一个槽位一条）。"""
        return len(self.dependencies)

    @property
    def unique_mod_count(self) -> int:
        """唯一 MOD 数量（按 ModID 去重）。"""
        return len(self.unique_mod_guids)


@dataclass
class ZipmodParseResult:
    """一个 zipmod 的只读解析结果。"""

    path: str
    parse_status: str = PARSE_FAILED
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    is_zipmod: bool = False               # ZIP 内是否真的存在 manifest.xml
    manifest_entry: str | None = None     # manifest.xml 在压缩包内的路径
    guid: str | None = None
    name: str | None = None
    author: str | None = None
    version: str | None = None
    website: str | None = None

    @property
    def success(self) -> bool:
        return self.parse_status in (PARSE_OK, PARSE_PARTIAL)


__all__ = [
    "PARSE_OK",
    "PARSE_PARTIAL",
    "PARSE_FAILED",
    "CHARACTER_CARD_MARKERS",
    "MODLIST_PLUGIN_GUID",
    "AUTHORS_PLUGIN_GUID",
    "LstInfoEntry",
    "ModDependencyRecord",
    "CharacterCardParseResult",
    "ZipmodParseResult",
]
