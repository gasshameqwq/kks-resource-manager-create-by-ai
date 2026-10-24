"""Browse Read Model —— Phase 1.4-B.3。

只读的「查询编排 + 行模型」：把 GUI 需要的组合集中到 core，避免 UI 承担业务组合。

职责
----
- 用一个 :class:`BrowserScope` 同时驱动 ``ResourceQuery.count`` 与 ``list``，
  保证「总数」与「本页行」的作用域完全一致（调用方不需要拼两遍参数）。
- 为列表行补上**跨实体**信息：Library 名（``library_id → name``）与作者显示名。
- 可选地按需附带 ``review_reasons``。
- 直接转发 Library 列表与资源详情。
- 直接转发 byte-duplicate 派生结果（供 GUI 以 ``GUI → BrowseService → Query`` 访问）。

硬性约束
--------
- **本模块不含任何 SQL**：全部数据访问复用 ``LibraryQuery`` / ``ResourceQuery``
  （它们才持有 SQL 与只读护栏）。
- **只读**：不写数据库、不改 ``needs_review``、不新增字段 / migration / view / cache。
- **不执行 preview**：``PreviewService`` 保持独立，由 GUI 直接按需调用；
  本模块只提供 ``ResourceSummary``（含 ``file_path``）作为其输入。
- **不改变既有语义**：筛选语义完全来自 ``ResourceQuery``；
  review reason 语义完全来自 ``ResourceQuery.review_reasons()``。
- 刻意**不含** UI 专用字段 / 状态（选中态、收藏、颜色、图标、主题等）。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import ClassVar

from core.query.dto import (
    AuthorSummary,
    DuplicateGroup,
    LibrarySummary,
    ModSummary,
    PluginSummary,
    ResourceDetail,
    ResourceSummary,
    ReviewReason,
    TagSummary,
)
from core.query.model import ResourceFilter
from core.query.queries import (
    AuthorQuery,
    LibraryQuery,
    ModQuery,
    PluginQuery,
    ResourceQuery,
)
from core.query.tag_queries import TagQuery


@dataclass(frozen=True)
class BrowserScope:
    """一次浏览查询的作用域（筛选 + 排序）。

    字段语义与 ``ResourceQuery.list/count`` 的对应参数**完全一致**，不重新定义。
    ``order_by`` / ``descending`` 只作用于 ``list``（``count`` 不需要排序）。
    """

    query: str | None = None
    resource_type: str | None = None
    game: str | None = None
    library_id: int | None = None
    scan_status: str | None = None
    needs_review: bool | None = None
    has_mods: bool | None = None
    has_missing_mods: bool | None = None
    mod_guid: str | None = None
    plugin_guid: str | None = None
    author_id: int | None = None
    property_category: str | None = None
    tag_id: int | None = None
    favorite: bool | None = None
    has_duplicates: bool | None = None
    sha256: str | None = None
    order_by: str = "id"
    descending: bool = False

    #: GUI 作用域真正装配的筛选键集：Phase 3.3 的 14 键 +
    #: Phase 4.1 新增的 ``has_duplicates`` / ``sha256``。
    #:
    #: ``ResourceQuery.count`` / ``list`` 的筛选面为 **17** 项（多一个 GUI 不暴露的
    #: ``card_marker``），因此 :meth:`filters` 是本键集上的**投影**，
    #: 与 ``to_filter().to_params()``（17 键）**必然不等** —— 不得用字典相等做断言。
    FILTER_KEYS: ClassVar[tuple[str, ...]] = (
        "query",
        "resource_type",
        "game",
        "library_id",
        "scan_status",
        "needs_review",
        "has_mods",
        "has_missing_mods",
        "mod_guid",
        "plugin_guid",
        "author_id",
        "property_category",
        "tag_id",
        "favorite",
        "has_duplicates",
        "sha256",
    )

    def to_filter(self) -> ResourceFilter:
        """作用域 → :class:`ResourceFilter`：GUI 条件的**唯一**字段值映射实现。

        字段语义与 ``ResourceQuery.count`` / ``list`` 的对应参数完全一致，
        本方法只做搬运，不重新定义语义、不新增校验。
        """
        return ResourceFilter(
            query=self.query,
            resource_type=self.resource_type,
            game=self.game,
            card_marker=None,
            library_id=self.library_id,
            scan_status=self.scan_status,
            needs_review=self.needs_review,
            has_mods=self.has_mods,
            has_missing_mods=self.has_missing_mods,
            mod_guid=self.mod_guid,
            plugin_guid=self.plugin_guid,
            author_id=self.author_id,
            property_category=self.property_category,
            tag_id=self.tag_id,
            favorite=self.favorite,
            has_duplicates=self.has_duplicates,
            sha256=self.sha256,
        )

    def filters(self) -> dict[str, object]:
        """作用域 → ``ResourceQuery`` 筛选参数的**唯一**转换点（键投影）。

        ``page()`` 的 ``count`` 与 ``list`` 都使用本方法的返回值，
        因此不存在「两条路径参数不一致」的可能（调用方也不需要各自拼一遍）。

        实现上**只做键投影**：先经 :meth:`to_filter` 完成唯一的字段值映射，
        再按 :data:`FILTER_KEYS` 取子集。返回值**恰好**包含这 16 个键，
        且键恒存在、值可为 ``None``（与 ``ResourceQuery`` 的默认值语义一致）。
        """
        params = self.to_filter().to_params()
        return {key: params[key] for key in self.FILTER_KEYS}


@dataclass(frozen=True)
class ResourceListItem:
    """资源列表的一行：``ResourceSummary`` + 跨实体信息。

    - ``resource``     ：资源自身事实（**未修改** ``ResourceSummary``）；
    - ``library_name`` ：所属 Library 名（``library_id`` 为空时为 ``None``）；
    - ``authors``      ：作者显示名，保留 tuple 语义（0 / 1 / 多个）；
    - ``review_reasons``：默认为空 tuple；只有 ``page(with_review_reasons=True)`` 才填充。

    刻意**不含** ``has_missing_mods`` 行内标记（v1 只用它做筛选 / 专门视图），
    也不含任何 GUI 状态字段。
    """

    resource: ResourceSummary
    library_name: str | None
    authors: tuple[str, ...]
    review_reasons: tuple[ReviewReason, ...] = ()


@dataclass(frozen=True)
class BrowsePage:
    """一页资源列表：行 + 总数 + 分页信息。

    ``total`` 与 ``items`` 使用同一个 :class:`BrowserScope`（见 ``BrowserScope.filters``），
    因此过滤条件下 ``total`` 一定等于「该作用域下的全部匹配数」，与当前页无关。
    """

    items: tuple[ResourceListItem, ...]
    total: int
    limit: int | None
    offset: int


class BrowseService:
    """只读 Browse 编排服务（无自有 SQL，只复用现成 Query）。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._libraries = LibraryQuery(conn)
        self._resources = ResourceQuery(conn)
        self._authors = AuthorQuery(conn)
        self._plugins = PluginQuery(conn)
        self._mods = ModQuery(conn)
        self._tags = TagQuery(conn)

    # ---- 左栏：Library --------------------------------------------------

    def libraries(self, *, include_disabled: bool = True) -> list[LibrarySummary]:
        """Library 列表（默认含已暂停），直接复用 ``LibraryQuery.list()``。"""
        return self._libraries.list(include_disabled=include_disabled)

    # ---- 中栏：资源列表 --------------------------------------------------

    def page(
        self,
        scope: BrowserScope,
        *,
        limit: int | None = None,
        offset: int = 0,
        with_review_reasons: bool = False,
    ) -> BrowsePage:
        """取一页资源列表。

        - ``count`` 与 ``list`` 共用 ``scope.filters()``（不可能漂移）；
        - Library 名按**本页**涉及的 id 建立一次映射（不对每行查 Library）；
        - 作者按行取（``ResourceQuery.authors``）；
        - ``with_review_reasons=False`` 时**不查询** review reasons。
        """
        filters = scope.filters()
        total = self._resources.count(**filters)
        rows = self._resources.list(
            **filters,
            order_by=scope.order_by,
            descending=scope.descending,
            limit=limit,
            offset=offset,
        )

        library_names = self._library_names({row.library_id for row in rows})

        items: list[ResourceListItem] = []
        for row in rows:
            authors = tuple(author.name for author in self._resources.authors(row.id))
            reasons: tuple[ReviewReason, ...] = (
                self._resources.review_reasons(row.id) if with_review_reasons else ()
            )
            items.append(
                ResourceListItem(
                    resource=row,
                    library_name=library_names.get(row.library_id),
                    authors=authors,
                    review_reasons=reasons,
                )
            )
        return BrowsePage(
            items=tuple(items), total=total, limit=limit, offset=offset
        )

    def _library_names(self, library_ids: set[int | None]) -> dict[int, str]:
        """本页所需的 ``library_id → name`` 映射（一次查询，不逐行查）。"""
        wanted = {lid for lid in library_ids if lid is not None}
        if not wanted:
            return {}
        return {
            library.id: library.name
            for library in self._libraries.list()
            if library.id in wanted
        }

    # ---- 右栏：详情 / review reasons ------------------------------------

    def detail(self, resource_id: int) -> ResourceDetail | None:
        """单资源详情，直接复用 ``ResourceQuery.get()``；不存在返回 ``None``。"""
        return self._resources.get(resource_id)

    def review_reasons(self, resource_id: int) -> tuple[ReviewReason, ...]:
        """单资源 review reason，直接复用 ``ResourceQuery.review_reasons()``。"""
        return self._resources.review_reasons(resource_id)

    # ---- 关系反查（只读转发，供 GUI 从 MOD/作者/插件出发找资源）----------

    def authors(self, *, with_resources: bool = False) -> list[AuthorSummary]:
        """作者列表，直接复用 ``AuthorQuery.list()``。

        ``with_resources=True`` 时只返回**确实关联了资源**的作者
        （用 ``AuthorSummary.resource_count`` 过滤；不产生新 SQL、不查关系明细）。
        """
        authors = self._authors.list()
        if with_resources:
            return [author for author in authors if author.resource_count > 0]
        return authors

    def plugins(self) -> list[PluginSummary]:
        """插件列表（GUID + 引用资源数），直接复用 ``PluginQuery.list()``。"""
        return self._plugins.list()

    def missing_mods(self) -> list[ModSummary]:
        """被资源引用但本地未安装的 MOD，直接复用 ``ModQuery.missing()``。

        返回的 ``ModSummary`` 含 ``guid`` / ``used_by_count`` / ``usage_count``
        （缺失 MOD 没有名称，因为本地没有 manifest）。
        """
        return self._mods.missing()

    def orphan_mods(self) -> list[ModSummary]:
        """本地已安装但没有任何资源引用的 MOD，直接复用 ``ModQuery.orphan()``。"""
        return self._mods.orphan()

    # ---- byte-duplicate（只读转发，无自有 SQL；Phase 2.3-A）-------------

    def duplicates(self) -> list[DuplicateGroup]:
        """byte-identical 资源组，直接复用 ``ResourceQuery.duplicates()``。

        ``sha256`` 相等**只**表示文件**字节完全相同**（byte-identical），
        **不**表示同角色 / 同 MOD / 同逻辑资源；本层不做任何相似性推断，
        也不改变 ``ResourceQuery.duplicates()`` 的分组语义。
        """
        return self._resources.duplicates()

    def duplicate_group_for(self, resource_id: int) -> DuplicateGroup | None:
        """某资源所属的 byte-duplicate 组，直接复用 ``ResourceQuery.duplicate_group_for()``。

        非重复资源（单例 / ``sha256`` 为空 / 不存在）返回 ``None``；
        语义与 :meth:`duplicates` 严格一致。
        """
        return self._resources.duplicate_group_for(resource_id)

    # ---- Tag（只读转发，Phase 3.2；无自有 SQL）--------------------------

    def tags(self) -> list[TagSummary]:
        """全部 Tag（含系统 Tag），直接复用 ``TagQuery.list()``。"""
        return self._tags.list()

    def resource_tags(self, resource_id: int) -> list[TagSummary]:
        """某个资源上的 Tag，直接复用 ``TagQuery.for_resource()``。"""
        return self._tags.for_resource(resource_id)

    def system_tags(self) -> list[TagSummary]:
        """保留系统 Tag 子集，直接复用 ``TagQuery.system_tags()``。"""
        return self._tags.system_tags()

    def is_favorite(self, resource_id: int) -> bool:
        """该资源是否收藏，直接复用 ``TagQuery.is_favorite()``。"""
        return self._tags.is_favorite(resource_id)

    def favorite_resource_ids(self) -> list[int]:
        """全部收藏资源 id，直接复用 ``TagQuery.favorite_resource_ids()``。"""
        return self._tags.favorite_resource_ids()


__all__ = [
    "BrowserScope",
    "ResourceListItem",
    "BrowsePage",
    "BrowseService",
]
