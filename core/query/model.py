"""Query Model —— Phase 3.3。

依据 `docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md`（§4 / §5 / §6）。

:class:`ResourceFilter` 是「一次资源筛选条件」的正式载体：

- **纯值对象**：``frozen=True``；不持有连接、不执行任何数据库语句、不含 UI 状态；
- **唯一条件载体**：``BrowserScope`` 与 CLI 参数都编译为它；
- **不是执行器**：条件仍只由 ``core.query.queries._resource_where`` 构造；
  本模块**不提供**任何 SQL 出口（不提供 ``to_sql()`` / ``to_where()``）；
- **不做文本语法解析**：``parse()`` / ``compile()`` 一律不提供。

字段与 ``ResourceQuery.count`` / ``ResourceQuery.list`` 的筛选参数一一对应
（契约 §4.2）：13 个既有字段 + 本阶段新增的 ``tag_id`` / ``favorite``，
共 15 项；排序（``order_by`` / ``descending``）与分页（``limit`` / ``offset``）
**不属于**本模型。

本模块只依赖标准库（依赖方向单向：``browse`` → ``model``；``model`` 不反向依赖）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceFilter:
    """一次资源筛选条件（不可变值对象）。

    全部字段默认 ``None``，表示「不启用该条件」；空条件等价于「无任何筛选」，
    与既有 ``ResourceQuery.list()`` / ``count()`` 的默认行为逐字一致。

    ``to_params()`` 返回的键集恒为下述 15 个字段，可直接展开为
    ``ResourceQuery.count(**f.to_params())`` /
    ``ResourceQuery.list(**f.to_params(), order_by=..., limit=..., offset=...)``。

    该 15 键集合是**内部 Query 调用接口**，不是对外输出契约：
    CLI 的 JSON ``scope`` 另按契约 §6.6 的独立规则构造（仅输出实际提供的键）。
    """

    # ---- 既有筛选面（13 项，与 count / list 逐名一致）-------------------
    query: str | None = None
    resource_type: str | None = None
    game: str | None = None
    card_marker: str | None = None
    library_id: int | None = None
    scan_status: str | None = None
    needs_review: bool | None = None
    has_mods: bool | None = None
    has_missing_mods: bool | None = None
    mod_guid: str | None = None
    plugin_guid: str | None = None
    author_id: int | None = None
    property_category: str | None = None

    # ---- 本阶段新增（Phase 3.3）-----------------------------------------
    tag_id: int | None = None
    """单个 Tag 的 surrogate id（``tags.id``），**不是** ``name_key``。

    名称解析**不在** Query 层：调用方（如 CLI）先用
    ``TagQuery.find_by_name()`` 解析为 id。未知 / ``0`` / 负数 id
    在 Query 层表示「不存在的 Tag」⇒ 空结果，且不抛异常。
    """

    favorite: bool | None = None
    """``True`` 仅收藏 / ``False`` 仅非收藏 / ``None`` 不筛选。

    语义完全由「``name_key == FAVORITE_TAG_KEY`` 的保留系统 Tag 关联」定义
    （与 ``TagQuery.is_favorite()`` 同一谓词）。
    """

    def __post_init__(self) -> None:
        # 契约 §4.4：``tag_id`` 仅接受 ``None`` 与 ``int``；
        # ``bool`` 虽然是 ``int`` 的子类，但必须拒绝（``True`` / ``False`` 不是合法 id）。
        if self.tag_id is not None and (
            isinstance(self.tag_id, bool) or not isinstance(self.tag_id, int)
        ):
            raise TypeError(
                f"tag_id 必须是 int 或 None，收到：{type(self.tag_id).__name__}"
            )
        # 契约 §4.4：``favorite`` 仅接受 ``None`` / ``True`` / ``False``。
        if self.favorite is not None and not isinstance(self.favorite, bool):
            raise TypeError(
                f"favorite 必须是 bool 或 None，收到：{type(self.favorite).__name__}"
            )

    def to_params(self) -> dict[str, object]:
        """筛选条件 → ``ResourceQuery.count`` / ``list`` 的关键字参数。

        键集恒为 15 个筛选字段（键恒存在，值可为 ``None``）；
        调用方按需取用子集（GUI 取 ``BrowserScope.FILTER_KEYS`` 的 14 键投影；
        CLI 只取新增的 ``tag_id`` / ``favorite`` 两项，见契约 §5-3 / §6.5）。
        """
        return {
            "query": self.query,
            "resource_type": self.resource_type,
            "game": self.game,
            "card_marker": self.card_marker,
            "library_id": self.library_id,
            "scan_status": self.scan_status,
            "needs_review": self.needs_review,
            "has_mods": self.has_mods,
            "has_missing_mods": self.has_missing_mods,
            "mod_guid": self.mod_guid,
            "plugin_guid": self.plugin_guid,
            "author_id": self.author_id,
            "property_category": self.property_category,
            "tag_id": self.tag_id,
            "favorite": self.favorite,
        }


__all__ = ["ResourceFilter"]
