"""领域模型（与数据库、UI 无关的纯数据结构）。

Phase 0 只定义核心实体骨架，字段与 ``core/database/schema.py`` 中的列一一对应。
Phase 1 起由 database 层负责「行 <-> 模型」转换。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.models.tags import (
    FAVORITE_TAG_KEY,
    RESERVED_SYSTEM_TAG_KEYS,
    SYSTEM_TAGS,
    SystemTagSpec,
    is_system_tag_key,
)

# 资源类型（与 schema 中 resources.resource_type 的 CHECK 约束保持一致）
RESOURCE_TYPES: tuple[str, ...] = (
    "character_card",
    "outfit_card",
    "scene_card",
    "mod",
    "skin",
    "eyes",
    "hair",
    "accessory",
    "other",
    "unknown",
)

# 自动识别能可靠给出的类型（其余一律先落 unknown，交给用户确认）
AUTO_DETECTABLE_TYPES: tuple[str, ...] = (
    "character_card",
    "outfit_card",
    "scene_card",
    "mod",
    "unknown",
)


# 卡片里的「作者未知」哨兵值。真实样本实测 `marco.authordata` 常返回
# `['[Unknown]', 'Anonymous']` 这类列表 —— 哨兵值**不能**成为作者聚合键，
# 否则会把大量互不相关的卡片聚成同一个「作者」。
# 处理原则：不建 authors 行，但原始值必须原样保留（见 schema.RESOURCE_METADATA_KEYS
# 的 `authors_raw`），不静默丢弃。
UNKNOWN_AUTHOR_SENTINEL = "[Unknown]"


def is_placeholder_author(name: str) -> bool:
    """判断一个作者名是否是占位/哨兵值（不区分大小写与首尾空白）。"""
    return (name or "").strip().casefold() == UNKNOWN_AUTHOR_SENTINEL.casefold()


def partition_authors(authors: list[str]) -> tuple[list[str], list[str], list[str]]:
    """把卡内作者列表拆成三份，供入库时分别处理。

    返回 ``(real, placeholders, raw)``：

    - ``real``         —— 可以建 authors 行 / 建立关联的真实作者（已去重、保持原序）
    - ``placeholders`` —— 哨兵值（如 ``[Unknown]``），**不建 authors 行**
    - ``raw``          —— 卡内原始列表（原样保留，写入 ``metadata_json.authors_raw``）

    空字符串与纯空白会被忽略，但同样保留在 ``raw`` 中。
    """
    raw = [a for a in (authors or []) if isinstance(a, str)]
    real: list[str] = []
    placeholders: list[str] = []
    for name in raw:
        if is_placeholder_author(name):
            if name not in placeholders:
                placeholders.append(name)
            continue
        cleaned = name.strip()
        if cleaned and cleaned not in real:
            real.append(cleaned)
    return real, placeholders, raw


@dataclass
class Library:
    """一个扫描根目录。"""

    name: str
    root_path: str
    id: int | None = None
    enabled: bool = True
    notes: str = ""
    last_scan_at: str | None = None


@dataclass
class Resource:
    """一个被管理的资源（文件）。"""

    file_path: str
    resource_type: str = "unknown"
    type_source: str = "auto"          # auto | user
    id: int | None = None
    library_id: int | None = None
    name: str | None = None
    display_name: str | None = None
    relative_path: str | None = None
    file_size: int | None = None
    modified_time: float | None = None
    extension: str | None = None
    sha256: str | None = None
    quick_hash: str | None = None
    content_key: str | None = None
    thumbnail_path: str | None = None
    source: str | None = None
    author: str | None = None
    author_id: int | None = None
    series: str | None = None
    description: str | None = None
    notes: str | None = None
    metadata: dict = field(default_factory=dict)
    scan_status: str = "new"           # new | present | missing | error
    parse_status: str = "unparsed"     # unparsed | ok | partial | failed | skipped
    parse_error: str | None = None
    needs_review: bool = False


@dataclass
class ModEntry:
    """一个本地 MOD（zipmod）的 manifest 信息。"""

    guid: str
    id: int | None = None
    name: str = ""
    author: str = ""
    version: str = ""
    description: str = ""
    website: str = ""
    game: str = ""
    file_path: str = ""
    md5: str = ""


@dataclass
class ModDependency:
    """一张卡对某个 MOD 的依赖（无论该 MOD 是否已安装）。"""

    mod_guid: str
    ref_count: int = 1
    mod_id: int | None = None
    relation: str = "uses"             # uses | embeds


@dataclass
class CardSummary:
    """卡片轻量解析结果（浏览列表用，不加载整文件）。"""

    path: str
    card_type: str = "unknown"         # character_card | outfit_card | scene_card | unknown
    game: str = "?"                    # KK | KKS | ?
    marker: str = ""
    name: str = ""
    thumbnail_png: bytes = b""


__all__ = [
    "RESOURCE_TYPES",
    "AUTO_DETECTABLE_TYPES",
    "UNKNOWN_AUTHOR_SENTINEL",
    "is_placeholder_author",
    "partition_authors",
    # Tag 领域（Phase 3.2）
    "FAVORITE_TAG_KEY",
    "SystemTagSpec",
    "SYSTEM_TAGS",
    "RESERVED_SYSTEM_TAG_KEYS",
    "is_system_tag_key",
    "Library",
    "Resource",
    "ModEntry",
    "ModDependency",
    "CardSummary",
]
