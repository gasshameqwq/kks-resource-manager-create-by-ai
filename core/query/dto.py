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
    """资源列表行 / 概要（不含明细关系）。

    ``sha256`` 是**已有** ``resources.sha256`` 列的只读派生值（Phase 2.1 写入），
    表示该文件**原始字节**的内容哈希；它**只**表示 byte-identical，
    **不**表示同角色 / 同 MOD / 同逻辑资源。本 DTO **不计算**任何哈希，
    未解析 / 未计算哈希的资源为 ``None``。为避免破坏既有构造方式，
    该字段带默认值并置于末尾。

    Phase 3.1 Step 4 起，追加两个**只读**用户相关字段（同样是 additive、
    带默认值、置于末尾，保持 Phase 2.3 以来的兼容原则）：

    - ``type_source`` —— ``resources.type_source`` 的只读值（``'auto'`` / ``'user'``），
      表示 ``resource_type`` 当前由机器还是用户负责；
    - ``notes``       —— ``resources.notes`` 的只读值（用户备注，未设置为 ``None``）。

    本 DTO **不修改**数据库值，也不包含任何写能力；
    用户数据的写入只经 ``core.app.ResourceWriteService``。
    """

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
    sha256: str | None = None
    type_source: str = "auto"
    notes: str | None = None

    @property
    def game(self) -> str | None:
        """卡片游戏格式（KKS / KK）；非卡片返回 ``None``。"""
        return game_for_card_marker(self.card_marker)

    @property
    def effective_display_name(self) -> str | None:
        """业务展示名 —— Phase 3.1 Contract §4.4 的**唯一权威定义**。

        ``display_name`` 非 NULL 且 ``strip()`` 后非空 ⇒ 它就是用户 override；
        否则回退到机器解析名 ``name``。

        - 历史遗留的 ``""`` / 纯空白按「无 override」处理（读取侧归一化）；
        - **不得**用 ``display_name == name`` 判断 override：两者相等时
          ``display_name`` 仍是非 NULL，依然是有效 override。
        """
        if self.display_name is not None and self.display_name.strip() != "":
            return self.display_name
        return self.name

    @property
    def title(self) -> str:
        """展示用标题（core 唯一权威实现）。

        回退顺序：``effective_display_name`` → ``relative_path`` 的文件名 → ``file_path``。
        UI / CLI 一律消费本属性，不得各自维护独立的 fallback chain。
        """
        effective = self.effective_display_name
        if effective:
            return effective
        if self.relative_path:
            filename = self.relative_path.replace("\\", "/").rsplit("/", 1)[-1]
            if filename:
                return filename
        return self.file_path


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
class DuplicateGroup:
    """一组 **byte-identical** 的资源（``sha256`` 完全相同）。

    语义边界（Phase 2.2）
    --------------------
    - ``sha256`` 相等**只**表示**文件字节完全相同**（byte-identical）；
      **不**表示「同角色 / 同 MOD / 同逻辑资源」，本层不做任何逻辑相似性推断。
    - 这是**只读派生结果**：由 ``GROUP BY sha256`` 计算得到，**不落库**
      （不写 ``duplicate_groups`` / ``duplicate_members``，也不新增任何表）。
    - ``sha256`` 是分组键，**不是**新的 Content ID / Content 实体。

    字段
    ----
    - ``sha256``    —— 该组的字节内容哈希（64 位小写十六进制）。
    - ``resources`` —— 组成员（``ResourceSummary``），按 ``resources.id`` 稳定升序。
    """

    sha256: str
    resources: tuple[ResourceSummary, ...] = ()

    @property
    def member_count(self) -> int:
        """该组的资源数（byte-duplicate 组恒 ``>= 2``）。"""
        return len(self.resources)


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
    "DuplicateGroup",
    "ModUsage",
    "ResourceModRef",
    "ResourceAuthor",
    "ModSummary",
    "ModDetail",
    "AuthorSummary",
    "PluginSummary",
]
