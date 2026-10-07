"""查询层返回的数据对象（DTO）—— Phase 1.3-A。

设计约定
--------
- **不可变**：全部 ``frozen=True``；列表字段用 ``tuple``，避免上层误改。
- **稳定**：字段只增不改语义，方便 UI / CLI 长期依赖。
- **不暴露 cursor / Row**：查询层对外只返回这里定义的对象。

``ResourceSummary`` 里的 ``mod_count / usage_count / plugin_count / author_count``
都是**权威来源**的计数（``resource_mods`` / ``resource_mod_usages`` /
``resource_plugins`` / ``resource_authors``），**不读** ``metadata_json.plugin_count``。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.query.card_format import game_for_card_marker


@dataclass(frozen=True)
class PropertyCategoryCount:
    """某个语义类别下的 usage 行数。"""

    category: str
    count: int


@dataclass(frozen=True)
class PropertyCategoryStats:
    """某个语义类别的完整统计：使用次数 + 涉及的资源数 / MOD 数。"""

    category: str
    usage_count: int
    resource_count: int
    mod_count: int


@dataclass(frozen=True)
class ReviewReason:
    """一个**只读推导**出的「为什么这个资源需要人工查看」的理由。

    - ``code``   —— 稳定的机器标识（见 ``REVIEW_REASON_*`` 常量）。
    - ``label``  —— 人类可读提示（GUI 可自行本地化，不要依赖它做逻辑）。
    - ``detail`` —— 可选补充（如 ``parse_error`` 文本、无法识别的 property 列表）。

    该对象**不改变** ``resources.needs_review``，也不写入数据库。
    """

    code: str
    label: str
    detail: str | None = None


@dataclass(frozen=True)
class LibrarySummary:
    """一个 Library（扫描根目录）的只读概要。

    字段全部来自既有 ``libraries`` 列（Phase 1.1 schema）：
    ``id`` / ``name`` / ``root_path`` / ``enabled`` / ``notes`` / ``last_scan_at``；
    ``resource_count`` 由 ``resources.library_id`` **只读聚合**得到（不落库、不新增列）。

    刻意**不含**任何 UI 专用字段（颜色 / 图标 / 选中态 / 展开态）。
    """

    id: int
    name: str
    root_path: str
    enabled: bool
    notes: str
    last_scan_at: str | None
    resource_count: int = 0


@dataclass(frozen=True)
class ResourceSummary:
    """资源列表行 / 概要（不含明细关系）。"""

    id: int
    resource_type: str
    name: str | None
    display_name: str | None
    file_path: str
    relative_path: str | None
    extension: str | None
    card_marker: str | None
    file_size: int | None
    modified_time: float | None
    library_id: int | None
    scan_status: str
    parse_status: str
    needs_review: bool
    mod_count: int = 0
    usage_count: int = 0
    plugin_count: int = 0
    author_count: int = 0

    @property
    def game(self) -> str | None:
        """卡片游戏格式（KKS / KK）；非卡片返回 ``None``。"""
        return game_for_card_marker(self.card_marker)

    @property
    def title(self) -> str:
        """展示用标题：优先 display_name，其次 name，最后文件名。"""
        return self.display_name or self.name or self.file_path


@dataclass(frozen=True)
class ModUsage:
    """一条逐槽位使用事实（``resource_mod_usages`` 的一行）。"""

    resource_id: int
    mod_guid: str
    property: str
    category: str
    slot: int | None = None
    local_slot: int | None = None
    category_no: int | None = None


@dataclass(frozen=True)
class ResourceModRef:
    """一个资源对某个 MOD 的汇总关系（来自 ``resource_mods``，含便利计数）。"""

    mod_guid: str
    mod_id: int | None
    installed: bool
    ref_count: int
    relation: str
    categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResourceAuthor:
    """资源 ↔ 作者关联（含卡上原始写法与列表下标）。"""

    author_id: int
    name: str
    ordinal: int
    raw_name: str


@dataclass(frozen=True)
class ResourceDetail:
    """单个资源的完整详情。"""

    resource: ResourceSummary
    usages: tuple[ModUsage, ...] = ()
    mods: tuple[ResourceModRef, ...] = ()
    plugins: tuple[str, ...] = ()
    authors: tuple[ResourceAuthor, ...] = ()
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ModSummary:
    """一个 MOD 的概要。

    ``installed=False`` 表示「被资源引用但本地未安装」（``id`` / manifest 字段为空）。
    """

    guid: str
    installed: bool = False
    id: int | None = None
    name: str | None = None
    author: str | None = None
    version: str | None = None
    website: str | None = None
    file_path: str | None = None
    resource_id: int | None = None
    library_id: int | None = None
    used_by_count: int = 0
    usage_count: int = 0


@dataclass(frozen=True)
class ModDetail:
    """单个 MOD 的详情：概要 + 逐语义类别的使用统计。"""

    mod: ModSummary
    category_counts: tuple[PropertyCategoryCount, ...] = ()


@dataclass(frozen=True)
class AuthorSummary:
    """一个作者实体 + 关联的资源数。"""

    id: int
    name: str
    resource_count: int = 0


@dataclass(frozen=True)
class PluginSummary:
    """一个插件（KKEx 键）+ 引用它的资源数。"""

    plugin_guid: str
    resource_count: int = 0


__all__ = [
    "PropertyCategoryCount",
    "PropertyCategoryStats",
    "ReviewReason",
    "LibrarySummary",
    "ResourceSummary",
    "ResourceDetail",
    "ModUsage",
    "ResourceModRef",
    "ResourceAuthor",
    "ModSummary",
    "ModDetail",
    "AuthorSummary",
    "PluginSummary",
]
