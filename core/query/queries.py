"""只读查询层 —— Phase 1.3-A。

职责
----
把「资源管理器」需要的查询集中成稳定的 Python API，UI / CLI **不得**直接拼 SQL。
本层：

- **只读**：所有语句都经 :func:`_execute_select`，只允许 ``SELECT`` / ``WITH``；
  任何写语句都抛 :class:`ReadOnlyViolation`。
- **不暴露 cursor**：对外只返回 ``core.query.dto`` 里的不可变对象。
- **不依赖 UI / Scanner / Parser**：只依赖 schema 与 :mod:`core.query.property_map`。

权威来源（见 Phase 1.3 审计）
---------------------------
- MOD 使用事实：``resource_mod_usages``
- MOD 汇总：``resource_mods``（``ref_count`` 仅作便利值）
- 插件事实：``resource_plugins``
- 作者关系：``resource_authors``
- 原始作者列表：``resources.metadata_json.authors_raw``
- ``plugin_count`` 权威值：``COUNT(resource_plugins)``（**不**读 metadata_json）
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence

from core.database import db as database
from core.models.tags import FAVORITE_TAG_KEY
from core.query.card_format import card_marker_for_game
from core.query.dto import (
    AuthorSummary,
    DuplicateGroup,
    LibrarySummary,
    ModDetail,
    ModSummary,
    ModUsage,
    PluginSummary,
    PropertyCategoryCount,
    PropertyCategoryStats,
    ResourceAuthor,
    ResourceDetail,
    ResourceModRef,
    ResourceSummary,
    ReviewReason,
)
from core.query.property_map import (
    PROPERTY_CATEGORIES,
    PROPERTY_CATEGORY_UNKNOWN,
    classify_property,
    sql_category_predicate,
)
from core.query.search import (
    SEARCH_MODE_FTS,
    fts_match_expression,
    like_pattern,
    plan_search,
)
from core.query.readonly import (
    ReadOnlyViolation,
    _execute_select,
)
from core.query.tag_queries import TagQuery


# ---------------------------------------------------------------------------
# 只读护栏
# ---------------------------------------------------------------------------


# 只读护栏：``ReadOnlyViolation`` / ``_execute_select`` 由 ``core.query.readonly``
# 提供（模块顶部已导入），使 ``tag_queries`` 能复用同一护栏而不产生反向 import。
#
# ``_fetchall`` / ``_fetchone`` 仍**在本模块定义**：它们引用本模块的 ``_execute_select``
# 名字，从而保留既有「monkeypatch ``queries._execute_select`` 观察只读护栏」的测试点
# （见 tests/test_duplicate_query.py / tests/test_query_surfacing.py）。


def _fetchall(
    conn: sqlite3.Connection, sql: str, params: Sequence[object] = ()
) -> list[sqlite3.Row]:
    return _execute_select(conn, sql, params).fetchall()


def _fetchone(
    conn: sqlite3.Connection, sql: str, params: Sequence[object] = ()
) -> sqlite3.Row | None:
    return _execute_select(conn, sql, params).fetchone()


# ---------------------------------------------------------------------------
# 行 -> DTO
# ---------------------------------------------------------------------------


def _row_to_mod_usage(row: sqlite3.Row) -> ModUsage:
    return ModUsage(
        resource_id=int(row["resource_id"]),
        mod_guid=row["mod_guid"],
        property=row["property"],
        category=classify_property(row["property"]),
        slot=row["slot"],
        local_slot=row["local_slot"],
        category_no=row["category_no"],
    )


def _ordered_categories() -> tuple[str, ...]:
    """语义类别的稳定展示顺序：已知类别在前，``unknown`` 最后。"""
    return PROPERTY_CATEGORIES + (PROPERTY_CATEGORY_UNKNOWN,)


# ---------------------------------------------------------------------------
# Review reason（只读推导，不写库、不改 needs_review）
# ---------------------------------------------------------------------------
#
# ``resources.needs_review`` 是「review state」（现有布尔，由 Scanner 写入）；
# 下面这些 reason 是「review reason」——完全由既有列**只读推导**，绝不落库。

REVIEW_REASON_PARSE_FAILED = "parse_failed"
REVIEW_REASON_PARSE_PARTIAL = "parse_partial"
REVIEW_REASON_MISSING_NAME = "missing_name"
REVIEW_REASON_UNKNOWN_TYPE = "unknown_type"
REVIEW_REASON_UNKNOWN_PROPERTY = "unknown_property"

_REVIEW_REASON_LABELS: dict[str, str] = {
    REVIEW_REASON_PARSE_FAILED: "解析失败",
    REVIEW_REASON_PARSE_PARTIAL: "解析不完整",
    REVIEW_REASON_MISSING_NAME: "缺少名称",
    REVIEW_REASON_UNKNOWN_TYPE: "类型未知",
    REVIEW_REASON_UNKNOWN_PROPERTY: "存在无法识别的 property",
}

# 稳定的 reason code 顺序（同一资源的多个 reason 按此顺序返回）。
REVIEW_REASON_CODES: tuple[str, ...] = tuple(_REVIEW_REASON_LABELS)

# 这些 parse_status 会触发对应的 parse reason。
_PARSE_REASON_BY_STATUS: dict[str, str] = {
    "failed": REVIEW_REASON_PARSE_FAILED,
    "partial": REVIEW_REASON_PARSE_PARTIAL,
}


# ---------------------------------------------------------------------------
# 资源概要：公共 SELECT / WHERE
# ---------------------------------------------------------------------------


_RESOURCE_SUMMARY_COLUMNS = """
    r.id, r.resource_type, r.name, r.display_name, r.file_path, r.relative_path,
    r.extension, r.card_marker, r.file_size, r.modified_time, r.library_id,
    r.scan_status, r.parse_status, r.needs_review, r.sha256,
    r.type_source, r.notes,
    (SELECT count(*) FROM resource_mods rm WHERE rm.resource_id = r.id) AS mod_count,
    (SELECT count(*) FROM resource_mod_usages u WHERE u.resource_id = r.id) AS usage_count,
    (SELECT count(*) FROM resource_plugins p WHERE p.resource_id = r.id) AS plugin_count,
    (SELECT count(*) FROM resource_authors ra WHERE ra.resource_id = r.id) AS author_count
"""

_RESOURCE_ORDER_COLUMNS = {
    "id": "r.id",
    "name": "r.name",
    "display_name": "r.display_name",
    "file_size": "r.file_size",
    "modified_time": "r.modified_time",
    "created_at": "r.created_at",
    "updated_at": "r.updated_at",
}


def _row_to_resource_summary(row: sqlite3.Row) -> ResourceSummary:
    return ResourceSummary(
        id=int(row["id"]),
        resource_type=row["resource_type"],
        name=row["name"],
        display_name=row["display_name"],
        file_path=row["file_path"],
        relative_path=row["relative_path"],
        extension=row["extension"],
        card_marker=row["card_marker"],
        file_size=row["file_size"],
        modified_time=row["modified_time"],
        library_id=row["library_id"],
        scan_status=row["scan_status"],
        parse_status=row["parse_status"],
        needs_review=bool(row["needs_review"]),
        sha256=row["sha256"],
        type_source=row["type_source"],
        notes=row["notes"],
        mod_count=int(row["mod_count"]),
        usage_count=int(row["usage_count"]),
        plugin_count=int(row["plugin_count"]),
        author_count=int(row["author_count"]),
    )


def _fts_available(conn: sqlite3.Connection) -> bool:
    """**只读**判断 FTS 检索是否可用。

    条件是「``app_meta.fts_enabled == '1'``」且「``resources_fts`` 表存在」。
    任何缺失 / 读取失败都返回 ``False``（退化为 LIKE），**不写库、不改状态**。
    """
    try:
        row = _execute_select(
            conn, "SELECT value FROM app_meta WHERE key = 'fts_enabled'"
        ).fetchone()
    except sqlite3.Error:
        return False
    if row is None or str(row["value"]) != "1":
        return False
    try:
        exists = _execute_select(
            conn,
            "SELECT 1 FROM sqlite_master"
            " WHERE type = 'table' AND name = 'resources_fts'",
        ).fetchone()
    except sqlite3.Error:
        return False
    return exists is not None


def _text_search_clause(
    conn: sqlite3.Connection, query: str | None
) -> tuple[str, list[object]] | None:
    """把文本查询编译成一个可组合的 WHERE 片段；无文本条件时返回 ``None``。

    覆盖三类事实来源（用 ``OR`` 合并，因此共用同一个 ``query`` 参数）：

    1. **资源自身** —— ``resources.name`` / ``resources.display_name``
       （≥3 字走 ``resources_fts`` MATCH，1–2 字或 FTS 不可用走 LIKE）；
    2. **相对路径** —— ``resources.relative_path``（文件名 + 用户目录）；
       **在任何模式下都走 LIKE**，不进 FTS，因此 FTS 开关不改变搜索语义，
       也能搜到「文件名与解析名不同语言」的资源（见 Phase 1.4-A.1）；
    3. **作者** —— 只经 ``resource_authors`` + ``authors`` 关系（关系 EXISTS + LIKE），
       **不读** ``resources.author`` 死列。

    只搜 ``relative_path``，**不搜** ``file_path``（绝对路径含盘符/父目录噪声，
    跨机器不稳定）与 ``file_path_key``（身份键，非展示字符串）。
    """
    plan = plan_search(query, fts_available=_fts_available(conn))
    if not plan.is_active:
        return None

    pattern = like_pattern(plan.text)
    if plan.mode == SEARCH_MODE_FTS:
        name_clause = (
            "r.id IN (SELECT rowid FROM resources_fts"
            " WHERE resources_fts MATCH ?)"
        )
        name_params: list[object] = [fts_match_expression(plan.text)]
    else:
        name_clause = (
            "((r.name LIKE ? ESCAPE '\\') OR (r.display_name LIKE ? ESCAPE '\\'))"
        )
        name_params = [pattern, pattern]

    # 路径恒定走 LIKE（FTS 开关不影响这一路的结果集）。
    path_clause = "r.relative_path LIKE ? ESCAPE '\\'"

    author_clause = (
        "EXISTS (SELECT 1 FROM resource_authors ra"
        " JOIN authors a ON a.id = ra.author_id"
        " WHERE ra.resource_id = r.id"
        " AND (a.name LIKE ? ESCAPE '\\' OR ra.raw_name LIKE ? ESCAPE '\\'))"
    )

    clause = f"({name_clause} OR {path_clause} OR {author_clause})"
    # 参数顺序：name 条件 → path 条件 → author 条件（name/raw_name 各一个）
    return clause, [*name_params, pattern, pattern, pattern]


def _resource_where(
    conn: sqlite3.Connection,
    *,
    resource_type: str | None,
    game: str | None,
    card_marker: str | None,
    library_id: int | None,
    scan_status: str | None,
    needs_review: bool | None,
    mod_guid: str | None,
    plugin_guid: str | None,
    author_id: int | None,
    property_category: str | None,
    has_mods: bool | None,
    has_missing_mods: bool | None,
    query: str | None,
    tag_id: int | None,
    favorite: bool | None,
    has_duplicates: bool | None,
    sha256: str | None,
) -> tuple[list[str], list[object]]:
    clauses: list[str] = []
    params: list[object] = []

    if resource_type is not None:
        clauses.append("r.resource_type = ?")
        params.append(resource_type)
    if card_marker is not None:
        clauses.append("r.card_marker = ?")
        params.append(card_marker)
    if game is not None:
        clauses.append("r.card_marker = ?")
        params.append(card_marker_for_game(game))
    if library_id is not None:
        clauses.append("r.library_id = ?")
        params.append(library_id)
    if scan_status is not None:
        clauses.append("r.scan_status = ?")
        params.append(scan_status)
    if needs_review is not None:
        clauses.append("r.needs_review = ?")
        params.append(1 if needs_review else 0)
    if mod_guid is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM resource_mod_usages u"
            " WHERE u.resource_id = r.id AND u.mod_guid = ?)"
        )
        params.append(mod_guid)
    if plugin_guid is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM resource_plugins p"
            " WHERE p.resource_id = r.id AND p.plugin_guid = ?)"
        )
        params.append(plugin_guid)
    if author_id is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM resource_authors ra"
            " WHERE ra.resource_id = r.id AND ra.author_id = ?)"
        )
        params.append(author_id)
    if has_mods is not None:
        exists = "EXISTS" if has_mods else "NOT EXISTS"
        clauses.append(
            f"{exists} (SELECT 1 FROM resource_mod_usages u"
            " WHERE u.resource_id = r.id)"
        )
    if has_missing_mods is not None:
        # missing MOD = usage 引用的 mod_guid 在 ``mods`` 里没有对应行
        # （与 ModQuery.missing() 同一口径：resource_mod_usages LEFT JOIN mods）。
        # 用 EXISTS / NOT EXISTS 而不是 COUNT，重复关系不会改变判断。
        exists = "EXISTS" if has_missing_mods else "NOT EXISTS"
        clauses.append(
            f"{exists} (SELECT 1 FROM resource_mod_usages u"
            " LEFT JOIN mods m ON m.guid = u.mod_guid"
            " WHERE u.resource_id = r.id AND m.id IS NULL)"
        )
    if property_category is not None:
        fragment, category_params = sql_category_predicate(
            property_category, column="u.property"
        )
        clauses.append(
            "EXISTS (SELECT 1 FROM resource_mod_usages u"
            f" WHERE u.resource_id = r.id AND {fragment})"
        )
        params.extend(category_params)
    if query is not None:
        text_clause = _text_search_clause(conn, query)
        if text_clause is not None:
            fragment, text_params = text_clause
            clauses.append(fragment)
            params.extend(text_params)
    if tag_id is not None:
        # Phase 3.3（契约 §6.1.1）：按单个 Tag 的 surrogate id 筛选。
        # 未知 / 0 / 负数 id 自然匹配不到任何行 ⇒ 空结果，不抛异常（契约 §4.4）。
        clauses.append(
            "EXISTS (SELECT 1 FROM resource_tags rt"
            " WHERE rt.resource_id = r.id AND rt.tag_id = ?)"
        )
        params.append(tag_id)
    if favorite is not None:
        # Phase 3.3（契约 §6.1.2 / §6.1.3）：Favorite 判据与既有权威只读路径
        # ``TagQuery.is_favorite()`` 保持一致（同为 JOIN ``tags t`` + ``name_key``），
        # 仅在**外层查询形态**上使用 correlated EXISTS / NOT EXISTS。
        # 不使用 ``resources`` 的任何收藏列（不存在），也不新建收藏表。
        exists = "EXISTS" if favorite else "NOT EXISTS"
        clauses.append(
            f"{exists} (SELECT 1 FROM resource_tags rt"
            " JOIN tags t ON t.id = rt.tag_id"
            " WHERE rt.resource_id = r.id AND t.name_key = ?)"
        )
        params.append(FAVORITE_TAG_KEY)
    if sha256 is not None:
        clauses.append("r.sha256 = ?")
        params.append(sha256)
    if has_duplicates is not None:
        # byte-duplicate 只依既有 sha256；相关 EXISTS 使用
        # idx_resources_sha256。空哈希永不视为重复。
        peer_exists = (
            "EXISTS (SELECT 1 FROM resources r2"
            " WHERE r2.sha256 = r.sha256 AND r2.id != r.id)"
        )
        if has_duplicates:
            clauses.append("r.sha256 IS NOT NULL")
            clauses.append(peer_exists)
        else:
            clauses.append(f"(r.sha256 IS NULL OR NOT {peer_exists})")

    return clauses, params


def _resource_summary_query(
    conn: sqlite3.Connection,
    clauses: list[str],
    params: list[object],
    *,
    order_by: str = "id",
    descending: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> list[ResourceSummary]:
    if order_by not in _RESOURCE_ORDER_COLUMNS:
        raise ValueError(
            f"不支持的排序字段：{order_by!r}（可选 {tuple(_RESOURCE_ORDER_COLUMNS)}）"
        )
    sql = f"SELECT {_RESOURCE_SUMMARY_COLUMNS} FROM resources r"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    direction = "DESC" if descending else "ASC"
    sql += f" ORDER BY {_RESOURCE_ORDER_COLUMNS[order_by]} {direction}, r.id ASC"
    query_params = list(params)
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        query_params.extend([int(limit), int(offset)])
    elif offset:
        sql += " LIMIT -1 OFFSET ?"
        query_params.append(int(offset))

    return [
        _row_to_resource_summary(r) for r in _fetchall(conn, sql, query_params)
    ]


# ---------------------------------------------------------------------------
# LibraryQuery
# ---------------------------------------------------------------------------


class LibraryQuery:
    """``libraries`` 的只读查询（导航 / 概要用）。

    统计来自 ``resources.library_id`` 的**只读聚合**，因此本类：

    - **不调用**写层 ``LibraryStore``（Query Layer 不依赖写层）；
    - **不写任何数据**（所有语句经 ``_execute_select`` 只读护栏）；
    - 返回不可变 DTO :class:`LibrarySummary`。

    排序与写层 ``LibraryStore.list_all`` 保持一致：``name`` 不区分大小写 + ``id``，
    保证同名（含仅大小写不同）时的稳定顺序。
    """

    # 只读列：Library 自身事实 + 来自 resources.library_id 的计数（派生）。
    _COLUMNS = """
        l.id, l.name, l.root_path, l.enabled, l.notes, l.last_scan_at,
        (SELECT count(*) FROM resources r WHERE r.library_id = l.id) AS resource_count
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @staticmethod
    def _row_to_summary(row: sqlite3.Row) -> LibrarySummary:
        return LibrarySummary(
            id=int(row["id"]),
            name=row["name"],
            root_path=row["root_path"],
            enabled=bool(row["enabled"]),
            notes=row["notes"] or "",
            last_scan_at=row["last_scan_at"],
            resource_count=int(row["resource_count"]),
        )

    def list(self, *, include_disabled: bool = True) -> list[LibrarySummary]:
        """列出 Library（默认含已暂停的），按 name（不区分大小写）+ id 稳定排序。"""
        sql = f"SELECT {self._COLUMNS} FROM libraries l"
        if not include_disabled:
            sql += " WHERE l.enabled = 1"
        sql += " ORDER BY l.name COLLATE NOCASE, l.id"
        return [self._row_to_summary(r) for r in _fetchall(self.conn, sql)]

    def count(self, *, include_disabled: bool = True) -> int:
        """Library 总数；``include_disabled=False`` 时只数启用中的。"""
        sql = "SELECT count(*) AS c FROM libraries"
        if not include_disabled:
            sql += " WHERE enabled = 1"
        row = _fetchone(self.conn, sql)
        return int(row["c"]) if row else 0

    def get(self, library_id: int) -> LibrarySummary | None:
        """按 id 取单个 Library；不存在 / 无效 id 返回 ``None``（不抛异常）。"""
        rows = _fetchall(
            self.conn,
            f"SELECT {self._COLUMNS} FROM libraries l WHERE l.id = ?",
            [library_id],
        )
        return self._row_to_summary(rows[0]) if rows else None


# ---------------------------------------------------------------------------
# ResourceQuery
# ---------------------------------------------------------------------------


class ResourceQuery:
    """``resources`` 及其关系的只读查询。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def count(
        self,
        *,
        resource_type: str | None = None,
        game: str | None = None,
        card_marker: str | None = None,
        library_id: int | None = None,
        scan_status: str | None = None,
        needs_review: bool | None = None,
        mod_guid: str | None = None,
        plugin_guid: str | None = None,
        author_id: int | None = None,
        property_category: str | None = None,
        has_mods: bool | None = None,
        has_missing_mods: bool | None = None,
        query: str | None = None,
        tag_id: int | None = None,
        favorite: bool | None = None,
        has_duplicates: bool | None = None,
        sha256: str | None = None,
    ) -> int:
        clauses, params = _resource_where(
            self.conn,
            resource_type=resource_type,
            game=game,
            card_marker=card_marker,
            library_id=library_id,
            scan_status=scan_status,
            needs_review=needs_review,
            mod_guid=mod_guid,
            plugin_guid=plugin_guid,
            author_id=author_id,
            property_category=property_category,
            has_mods=has_mods,
            has_missing_mods=has_missing_mods,
            query=query,
            tag_id=tag_id,
            favorite=favorite,
            has_duplicates=has_duplicates,
            sha256=sha256,
        )
        sql = "SELECT count(*) AS c FROM resources r"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        row = _fetchone(self.conn, sql, params)
        return int(row["c"]) if row else 0

    def list(
        self,
        *,
        resource_type: str | None = None,
        game: str | None = None,
        card_marker: str | None = None,
        library_id: int | None = None,
        scan_status: str | None = None,
        needs_review: bool | None = None,
        mod_guid: str | None = None,
        plugin_guid: str | None = None,
        author_id: int | None = None,
        property_category: str | None = None,
        has_mods: bool | None = None,
        has_missing_mods: bool | None = None,
        query: str | None = None,
        tag_id: int | None = None,
        favorite: bool | None = None,
        has_duplicates: bool | None = None,
        sha256: str | None = None,
        order_by: str = "id",
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ResourceSummary]:
        """基础资源列表（带文本检索 / 筛选 / 排序 / 分页）。

        ``query`` 是可选的文本检索词（名称 / 作者子串；详见
        :mod:`core.query.search`），与其它结构化筛选是 **AND** 关系；
        为 ``None`` / 空 / 纯空白时不追加任何文本条件。

        注意 ``has_mods`` 与 ``has_missing_mods`` 语义不同：
        ``has_mods`` 指「有没有 MOD 依赖」（无论是否安装），
        ``has_missing_mods`` 指「依赖里有没有本地未安装的 MOD」。
        因此 ``has_missing_mods=True`` 一定是 ``has_mods=True`` 的子集。
        """
        clauses, params = _resource_where(
            self.conn,
            resource_type=resource_type,
            game=game,
            card_marker=card_marker,
            library_id=library_id,
            scan_status=scan_status,
            needs_review=needs_review,
            mod_guid=mod_guid,
            plugin_guid=plugin_guid,
            author_id=author_id,
            property_category=property_category,
            has_mods=has_mods,
            has_missing_mods=has_missing_mods,
            query=query,
            tag_id=tag_id,
            favorite=favorite,
            has_duplicates=has_duplicates,
            sha256=sha256,
        )
        return _resource_summary_query(
            self.conn,
            clauses,
            params,
            order_by=order_by,
            descending=descending,
            limit=limit,
            offset=offset,
        )

    def summary(self, resource_id: int) -> ResourceSummary | None:
        rows = _resource_summary_query(
            self.conn, ["r.id = ?"], [resource_id], limit=1
        )
        return rows[0] if rows else None

    def resolve(self, target: str | int) -> ResourceSummary | None:
        """把「id / 绝对路径 / 归一化路径 key / relative_path」解析成一个资源。

        找不到返回 ``None``。这是**身份解析**，属于查询层职责，CLI 不应自己拼 SQL。
        """
        if isinstance(target, int):
            return self.summary(target)
        text = (target or "").strip().strip('"')
        if not text:
            return None
        if text.isdigit():
            found = self.summary(int(text))
            if found is not None:
                return found
        key = database.normalize_path_key(text)
        if key:
            row = _fetchone(
                self.conn,
                "SELECT id FROM resources WHERE file_path_key = ?",
                [key],
            )
            if row is not None:
                return self.summary(int(row["id"]))
        row = _fetchone(
            self.conn, "SELECT id FROM resources WHERE file_path = ?", [text]
        )
        if row is not None:
            return self.summary(int(row["id"]))
        row = _fetchone(
            self.conn,
            "SELECT id FROM resources WHERE replace(relative_path, '\\', '/') = ?",
            [text.replace("\\", "/")],
        )
        return self.summary(int(row["id"])) if row is not None else None

    def get(self, resource_id: int) -> ResourceDetail | None:
        """单资源详情（概要 + usages + mods + plugins + authors + metadata + tags）。

        Phase 3.2 起**只读**填充用户 Tag 事实（``tags``）与派生 Favorite 状态
        （``is_favorite``）；不写库，也不提供任何 Tag 过滤 / 搜索语义。
        """
        summary = self.summary(resource_id)
        if summary is None:
            return None
        tags = tuple(TagQuery(self.conn).for_resource(resource_id))
        return ResourceDetail(
            resource=summary,
            usages=tuple(self.usages(resource_id)),
            mods=tuple(self.mods(resource_id)),
            plugins=tuple(self.plugins(resource_id)),
            authors=tuple(self.authors(resource_id)),
            metadata=self.metadata(resource_id),
            tags=tags,
            is_favorite=any(tag.name_key == FAVORITE_TAG_KEY for tag in tags),
        )

    def usages(
        self, resource_id: int, *, category: str | None = None
    ) -> list[ModUsage]:
        """资源 → 逐槽位 MOD 使用事实（可按 property 语义类别筛选）。"""
        sql = (
            "SELECT resource_id, mod_guid, property, slot, local_slot, category_no"
            " FROM resource_mod_usages WHERE resource_id = ?"
        )
        params: list[object] = [resource_id]
        if category is not None:
            fragment, category_params = sql_category_predicate(category)
            sql += f" AND {fragment}"
            params.extend(category_params)
        sql += " ORDER BY property, mod_guid"
        return [_row_to_mod_usage(r) for r in _fetchall(self.conn, sql, params)]

    def mods(self, resource_id: int) -> list[ResourceModRef]:
        """资源 → 它使用的 MOD 汇总（含是否本地已安装、逐类别）。"""
        rows = _fetchall(
            self.conn,
            "SELECT rm.mod_guid, rm.mod_id, rm.ref_count, rm.relation,"
            " CASE WHEN m.id IS NULL THEN 0 ELSE 1 END AS installed"
            " FROM resource_mods rm LEFT JOIN mods m ON m.guid = rm.mod_guid"
            " WHERE rm.resource_id = ? ORDER BY rm.mod_guid",
            [resource_id],
        )
        categories = _categories_by_mod_for_resource(self.conn, resource_id)
        return [
            ResourceModRef(
                mod_guid=row["mod_guid"],
                mod_id=row["mod_id"],
                installed=bool(row["installed"]),
                ref_count=int(row["ref_count"]),
                relation=row["relation"],
                categories=categories.get(row["mod_guid"], ()),
            )
            for row in rows
        ]

    def plugins(self, resource_id: int) -> list[str]:
        """资源 → 插件 GUID 列表（权威来源：``resource_plugins``）。"""
        rows = _fetchall(
            self.conn,
            "SELECT plugin_guid FROM resource_plugins WHERE resource_id = ?"
            " ORDER BY plugin_guid",
            [resource_id],
        )
        return [row["plugin_guid"] for row in rows]

    def authors(self, resource_id: int) -> list[ResourceAuthor]:
        """资源 → 作者（按卡内出现顺序）。"""
        rows = _fetchall(
            self.conn,
            "SELECT a.id AS author_id, a.name, ra.ordinal, ra.raw_name"
            " FROM resource_authors ra JOIN authors a ON a.id = ra.author_id"
            " WHERE ra.resource_id = ? ORDER BY ra.ordinal, a.name",
            [resource_id],
        )
        return [
            ResourceAuthor(
                author_id=int(row["author_id"]),
                name=row["name"],
                ordinal=int(row["ordinal"]),
                raw_name=row["raw_name"],
            )
            for row in rows
        ]

    def metadata(self, resource_id: int) -> dict:
        """资源的 ``metadata_json``（解析成 dict；缺失返回空 dict）。"""
        row = _fetchone(
            self.conn,
            "SELECT metadata_json FROM resources WHERE id = ?",
            [resource_id],
        )
        if row is None or not row["metadata_json"]:
            return {}
        try:
            value = json.loads(row["metadata_json"])
        except (ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    def authors_raw(self, resource_id: int) -> list[str]:
        """资源 → 卡片原始作者列表（含哨兵；仅存在于 metadata_json）。"""
        raw = self.metadata(resource_id).get("authors_raw")
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, str)]
        return []

    # ---- byte-duplicate（只读派生；Phase 2.2）---------------------------

    def duplicates(self) -> list[DuplicateGroup]:
        """按 ``sha256`` 分组的 byte-duplicate 派生查询（只读，不落库）。

        语义（Phase 2.0-C §8 / §13.7；Phase 2.2 冻结决定）
        -------------------------------------------------
        - **只为 byte-identical 分组**：``sha256`` 相等**仅**表示文件字节完全相同，
          **不**表示同角色 / 同 MOD / 同逻辑资源；本方法不做任何逻辑相似性推断。
        - **最低成员数固定为 2**：单例资源不成组、不返回（无 ``min_group_size`` 参数）。
        - **``sha256 IS NULL`` 排除**：从未解析 / 未计算哈希的资源不参与分组。
        - **稳定顺序**：组按 ``sha256`` 升序；组内成员按 ``resources.id`` 升序；
          相同数据库状态下重复调用结果一致。
        - **完全只读**：经 ``_execute_select`` 执行（继承只读护栏），
          **不写** ``duplicate_groups`` / ``duplicate_members`` / 任何其它表，
          不新增 schema；``sha256`` 只是分组键，不是新的 Content ID。
        """
        sql = (
            f"SELECT {_RESOURCE_SUMMARY_COLUMNS}, r.sha256"
            " FROM resources r"
            " WHERE r.sha256 IS NOT NULL"
            " AND r.sha256 IN ("
            "   SELECT s.sha256 FROM resources s"
            "   WHERE s.sha256 IS NOT NULL"
            "   GROUP BY s.sha256"
            "   HAVING count(*) >= 2"
            " )"
            " ORDER BY r.sha256 ASC, r.id ASC"
        )
        grouped: dict[str, list[ResourceSummary]] = {}
        for row in _fetchall(self.conn, sql):
            grouped.setdefault(row["sha256"], []).append(
                _row_to_resource_summary(row)
            )
        return [
            DuplicateGroup(sha256=sha256, resources=tuple(members))
            for sha256, members in grouped.items()
        ]

    def duplicate_group_for(self, resource_id: int) -> DuplicateGroup | None:
        """该资源所属的 byte-duplicate 组；不属于任何组时返回 ``None``。

        语义与 :meth:`duplicates` **严格一致**（同一 ``sha256`` 分组键、同组成员、
        组内按 ``resources.id`` 升序）；本方法只是「单资源视角」的等价视图，
        **不改变** ``duplicates()`` 的分组语义，也不引入任何新判据：

        - ``sha256 IS NULL``（从未解析 / 未计算哈希）⇒ ``None``；
        - 该 ``sha256`` 只有 1 个成员（非重复）⇒ ``None``；
        - 资源不存在 ⇒ ``None``；
        - 完全只读（经 ``_execute_select``），不落库、不新增持久化。
        """
        rows = _fetchall(
            self.conn,
            f"SELECT {_RESOURCE_SUMMARY_COLUMNS}"
            " FROM resources r"
            " WHERE r.sha256 IS NOT NULL"
            " AND r.sha256 = (SELECT s.sha256 FROM resources s WHERE s.id = ?)"
            " ORDER BY r.id ASC",
            [resource_id],
        )
        if len(rows) < 2:
            return None
        sha256 = rows[0]["sha256"]
        if sha256 is None:  # pragma: no cover - WHERE r.sha256 IS NOT NULL 已保证
            return None
        members = [_row_to_resource_summary(row) for row in rows]
        return DuplicateGroup(sha256=sha256, resources=tuple(members))

    # ---- review reason（只读推导）---------------------------------------

    def review_reasons(self, resource_id: int) -> tuple[ReviewReason, ...]:
        """**只读推导**该资源「为什么需要人工查看」的理由。

        完全基于既有列，绝不写库、绝不修改 ``needs_review``：

        - ``parse_failed`` / ``parse_partial`` —— 由 ``parse_status`` 推导；
        - ``missing_name`` —— ``name`` 为空/NULL；
        - ``unknown_type`` —— ``resource_type = 'unknown'``；
        - ``unknown_property`` —— 该资源的 usage 里存在无法归类的 property。

        资源不存在时返回空元组；无任何理由时同样返回空元组。
        多个理由按 ``REVIEW_REASON_CODES`` 的稳定顺序返回。
        """
        row = _fetchone(
            self.conn,
            "SELECT resource_type, name, parse_status, parse_error"
            " FROM resources WHERE id = ?",
            [resource_id],
        )
        if row is None:
            return ()

        reasons: list[ReviewReason] = []
        parse_code = _PARSE_REASON_BY_STATUS.get(row["parse_status"] or "")
        if parse_code is not None:
            reasons.append(
                ReviewReason(parse_code, _REVIEW_REASON_LABELS[parse_code], row["parse_error"])
            )
        if not (row["name"] or "").strip():
            reasons.append(
                ReviewReason(
                    REVIEW_REASON_MISSING_NAME, _REVIEW_REASON_LABELS[REVIEW_REASON_MISSING_NAME]
                )
            )
        if row["resource_type"] == "unknown":
            reasons.append(
                ReviewReason(
                    REVIEW_REASON_UNKNOWN_TYPE, _REVIEW_REASON_LABELS[REVIEW_REASON_UNKNOWN_TYPE]
                )
            )
        unknown = self._unknown_properties(resource_id)
        if unknown:
            reasons.append(
                ReviewReason(
                    REVIEW_REASON_UNKNOWN_PROPERTY,
                    _REVIEW_REASON_LABELS[REVIEW_REASON_UNKNOWN_PROPERTY],
                    ", ".join(unknown),
                )
            )
        return tuple(reasons)

    def _unknown_properties(self, resource_id: int) -> list[str]:
        """该资源里无法归类的 property（去重、稳定排序）。"""
        fragment, params = sql_category_predicate(PROPERTY_CATEGORY_UNKNOWN)
        rows = _fetchall(
            self.conn,
            "SELECT DISTINCT property FROM resource_mod_usages"
            f" WHERE resource_id = ? AND {fragment} ORDER BY property",
            [resource_id, *params],
        )
        return [row["property"] for row in rows]


def _categories_by_mod_for_resource(
    conn: sqlite3.Connection, resource_id: int
) -> dict[str, tuple[str, ...]]:
    """资源内每个 MOD 用到的语义类别（按 property 顺序去重）。"""
    grouped: dict[str, list[str]] = {}
    for row in _fetchall(
        conn,
        "SELECT mod_guid, property FROM resource_mod_usages"
        " WHERE resource_id = ? ORDER BY property, mod_guid",
        [resource_id],
    ):
        category = classify_property(row["property"])
        categories = grouped.setdefault(row["mod_guid"], [])
        if category not in categories:
            categories.append(category)
    return {guid: tuple(items) for guid, items in grouped.items()}


# ---------------------------------------------------------------------------
# ModQuery
# ---------------------------------------------------------------------------


class ModQuery:
    """``mods`` 及「缺失 / 孤立」判定的只读查询。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @staticmethod
    def _installed_summary(row: sqlite3.Row) -> ModSummary:
        return ModSummary(
            guid=row["guid"],
            installed=True,
            id=int(row["id"]),
            name=row["name"],
            author=row["author"],
            version=row["version"],
            website=row["website"],
            file_path=row["file_path"],
            resource_id=row["resource_id"],
            library_id=row["library_id"],
            used_by_count=int(row["used_by_count"]),
            usage_count=int(row["usage_count"]),
        )

    def installed(self) -> list[ModSummary]:
        """本地已安装的全部 MOD（无论是否被引用）。"""
        rows = _fetchall(
            self.conn,
            "SELECT m.id, m.guid, m.name, m.author, m.version, m.website,"
            " m.file_path, m.resource_id, m.library_id,"
            " (SELECT count(DISTINCT u.resource_id) FROM resource_mod_usages u"
            "  WHERE u.mod_guid = m.guid) AS used_by_count,"
            " (SELECT count(*) FROM resource_mod_usages u"
            "  WHERE u.mod_guid = m.guid) AS usage_count"
            " FROM mods m ORDER BY m.guid",
        )
        return [self._installed_summary(r) for r in rows]

    def missing(self) -> list[ModSummary]:
        """被资源引用、但本地 ``mods`` 没有对应 guid 的 MOD。"""
        rows = _fetchall(
            self.conn,
            "SELECT u.mod_guid AS guid,"
            " count(DISTINCT u.resource_id) AS used_by_count,"
            " count(*) AS usage_count"
            " FROM resource_mod_usages u LEFT JOIN mods m ON m.guid = u.mod_guid"
            " WHERE m.id IS NULL GROUP BY u.mod_guid ORDER BY u.mod_guid",
        )
        return [
            ModSummary(
                guid=row["guid"],
                installed=False,
                used_by_count=int(row["used_by_count"]),
                usage_count=int(row["usage_count"]),
            )
            for row in rows
        ]

    def orphan(self) -> list[ModSummary]:
        """本地已安装、但没有任何资源引用的 MOD。"""
        rows = _fetchall(
            self.conn,
            "SELECT m.id, m.guid, m.name, m.author, m.version, m.website,"
            " m.file_path, m.resource_id, m.library_id, 0 AS used_by_count,"
            " 0 AS usage_count"
            " FROM mods m"
            " WHERE NOT EXISTS (SELECT 1 FROM resource_mod_usages u"
            "                   WHERE u.mod_guid = m.guid)"
            " ORDER BY m.guid",
        )
        return [self._installed_summary(r) for r in rows]

    def get(self, guid: str) -> ModSummary | None:
        """取单个 MOD；被引用但未安装也能取到；完全不存在返回 ``None``。"""
        row = _fetchone(
            self.conn,
            "SELECT m.id, m.guid, m.name, m.author, m.version, m.website,"
            " m.file_path, m.resource_id, m.library_id,"
            " (SELECT count(DISTINCT u.resource_id) FROM resource_mod_usages u"
            "  WHERE u.mod_guid = m.guid) AS used_by_count,"
            " (SELECT count(*) FROM resource_mod_usages u"
            "  WHERE u.mod_guid = m.guid) AS usage_count"
            " FROM mods m WHERE m.guid = ?",
            [guid],
        )
        if row is not None:
            return self._installed_summary(row)

        usage = _fetchone(
            self.conn,
            "SELECT count(DISTINCT resource_id) AS used_by_count, count(*) AS usage_count"
            " FROM resource_mod_usages WHERE mod_guid = ?",
            [guid],
        )
        if usage is not None and int(usage["usage_count"]) > 0:
            return ModSummary(
                guid=guid,
                installed=False,
                used_by_count=int(usage["used_by_count"]),
                usage_count=int(usage["usage_count"]),
            )
        return None

    def exists(self, guid: str) -> bool:
        return self.get(guid) is not None

    def detail(self, guid: str) -> ModDetail | None:
        """单 MOD 详情（概要 + 逐语义类别使用统计）。"""
        summary = self.get(guid)
        if summary is None:
            return None
        counts = UsageQuery(self.conn).category_counts(mod_guid=guid)
        return ModDetail(mod=summary, category_counts=counts)

    def resources(self, guid: str) -> list[ResourceSummary]:
        """MOD → 使用它的资源列表。"""
        return ResourceQuery(self.conn).list(mod_guid=guid)

    def usages(self, guid: str, *, category: str | None = None) -> list[ModUsage]:
        """MOD → 它的逐槽位使用事实。"""
        return UsageQuery(self.conn).for_mod(guid, category=category)


# ---------------------------------------------------------------------------
# AuthorQuery
# ---------------------------------------------------------------------------


class AuthorQuery:
    """``authors`` 与 ``resource_authors`` 的只读查询。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def list(self) -> list[AuthorSummary]:
        rows = _fetchall(
            self.conn,
            "SELECT a.id, a.name,"
            " (SELECT count(DISTINCT ra.resource_id) FROM resource_authors ra"
            "  WHERE ra.author_id = a.id) AS resource_count"
            " FROM authors a ORDER BY a.name COLLATE NOCASE, a.id",
        )
        return [
            AuthorSummary(
                id=int(row["id"]),
                name=row["name"],
                resource_count=int(row["resource_count"]),
            )
            for row in rows
        ]

    def get(self, author_id: int) -> AuthorSummary | None:
        row = _fetchone(
            self.conn,
            "SELECT a.id, a.name,"
            " (SELECT count(DISTINCT ra.resource_id) FROM resource_authors ra"
            "  WHERE ra.author_id = a.id) AS resource_count"
            " FROM authors a WHERE a.id = ?",
            [author_id],
        )
        if row is None:
            return None
        return AuthorSummary(
            id=int(row["id"]),
            name=row["name"],
            resource_count=int(row["resource_count"]),
        )

    def find_by_name(self, name: str) -> AuthorSummary | None:
        """按归一化名称查找作者（与入库时的去重规则一致）。"""
        key = database.normalize_name_key(name)
        if not key:
            return None
        row = _fetchone(
            self.conn, "SELECT id FROM authors WHERE name_key = ?", [key]
        )
        return self.get(int(row["id"])) if row is not None else None

    def resolve(self, target: str | int) -> AuthorSummary | None:
        """把「id 或名字」解析成作者；找不到返回 ``None``。"""
        if isinstance(target, int):
            return self.get(target)
        text = (target or "").strip()
        if not text:
            return None
        if text.isdigit():
            found = self.get(int(text))
            if found is not None:
                return found
        return self.find_by_name(text)

    def resources(self, author_id: int) -> list[ResourceSummary]:
        """作者 → 资源列表。"""
        return ResourceQuery(self.conn).list(author_id=author_id)


# ---------------------------------------------------------------------------
# PluginQuery
# ---------------------------------------------------------------------------


class PluginQuery:
    """``resource_plugins`` 的只读查询（插件与 MOD 严格分离）。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def list(self) -> list[PluginSummary]:
        rows = _fetchall(
            self.conn,
            "SELECT plugin_guid, count(DISTINCT resource_id) AS resource_count"
            " FROM resource_plugins GROUP BY plugin_guid ORDER BY plugin_guid",
        )
        return [
            PluginSummary(
                plugin_guid=row["plugin_guid"],
                resource_count=int(row["resource_count"]),
            )
            for row in rows
        ]

    def get(self, plugin_guid: str) -> PluginSummary | None:
        row = _fetchone(
            self.conn,
            "SELECT count(DISTINCT resource_id) AS resource_count"
            " FROM resource_plugins WHERE plugin_guid = ?",
            [plugin_guid],
        )
        if row is None or int(row["resource_count"]) == 0:
            return None
        return PluginSummary(
            plugin_guid=plugin_guid, resource_count=int(row["resource_count"])
        )

    def resources(self, plugin_guid: str) -> list[ResourceSummary]:
        """插件 → 使用它的资源列表。"""
        return ResourceQuery(self.conn).list(plugin_guid=plugin_guid)


# ---------------------------------------------------------------------------
# UsageQuery
# ---------------------------------------------------------------------------


class UsageQuery:
    """``resource_mod_usages`` 的只读查询（含 property 语义分类）。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _rows(
        self,
        *,
        resource_id: int | None,
        mod_guid: str | None,
        category: str | None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        clauses: list[str] = []
        params: list[object] = []
        if resource_id is not None:
            clauses.append("resource_id = ?")
            params.append(resource_id)
        if mod_guid is not None:
            clauses.append("mod_guid = ?")
            params.append(mod_guid)
        if category is not None:
            fragment, category_params = sql_category_predicate(category)
            clauses.append(fragment)
            params.extend(category_params)
        sql = (
            "SELECT resource_id, mod_guid, property, slot, local_slot, category_no"
            " FROM resource_mod_usages"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY property, mod_guid"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([int(limit), int(offset)])
        elif offset:
            sql += " LIMIT -1 OFFSET ?"
            params.append(int(offset))
        return _fetchall(self.conn, sql, params)

    def all(
        self,
        *,
        category: str | None = None,
        resource_id: int | None = None,
        mod_guid: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ModUsage]:
        """全库 usage 查询（可按资源 / MOD / 语义类别筛选，可分页）。"""
        return [
            _row_to_mod_usage(r)
            for r in self._rows(
                resource_id=resource_id,
                mod_guid=mod_guid,
                category=category,
                limit=limit,
                offset=offset,
            )
        ]

    def for_resource(
        self, resource_id: int, *, category: str | None = None
    ) -> list[ModUsage]:
        return [
            _row_to_mod_usage(r)
            for r in self._rows(
                resource_id=resource_id, mod_guid=None, category=category
            )
        ]

    def for_mod(
        self, mod_guid: str, *, category: str | None = None
    ) -> list[ModUsage]:
        return [
            _row_to_mod_usage(r)
            for r in self._rows(
                resource_id=None, mod_guid=mod_guid, category=category
            )
        ]

    def category_counts(
        self, *, resource_id: int | None = None, mod_guid: str | None = None
    ) -> tuple[PropertyCategoryCount, ...]:
        """按语义类别统计 usage 行数，返回**全部类别**（含计数 0 与 unknown）。"""
        counts = {category: 0 for category in PROPERTY_CATEGORIES}
        counts[PROPERTY_CATEGORY_UNKNOWN] = 0
        for row in self._rows(
            resource_id=resource_id, mod_guid=mod_guid, category=None
        ):
            counts[classify_property(row["property"])] += 1
        return tuple(
            PropertyCategoryCount(category=c, count=counts[c])
            for c in _ordered_categories()
        )

    def category_stats(
        self, *, resource_id: int | None = None, mod_guid: str | None = None
    ) -> tuple[PropertyCategoryStats, ...]:
        """按语义类别给出使用次数 + 涉及资源数 / MOD 数（全部类别，含 0）。"""
        usages = {category: 0 for category in _ordered_categories()}
        resources: dict[str, set[int]] = {
            category: set() for category in _ordered_categories()
        }
        mods: dict[str, set[str]] = {
            category: set() for category in _ordered_categories()
        }
        for row in self._rows(
            resource_id=resource_id, mod_guid=mod_guid, category=None
        ):
            category = classify_property(row["property"])
            usages[category] += 1
            resources[category].add(int(row["resource_id"]))
            mods[category].add(row["mod_guid"])
        return tuple(
            PropertyCategoryStats(
                category=c,
                usage_count=usages[c],
                resource_count=len(resources[c]),
                mod_count=len(mods[c]),
            )
            for c in _ordered_categories()
        )

    def resources_using(
        self, mod_guid: str, *, category: str | None = None
    ) -> list[int]:
        """使用某个 MOD 的资源 id（可按语义类别筛选）。"""
        clauses = ["mod_guid = ?"]
        params: list[object] = [mod_guid]
        if category is not None:
            fragment, category_params = sql_category_predicate(category)
            clauses.append(fragment)
            params.extend(category_params)
        rows = _fetchall(
            self.conn,
            "SELECT DISTINCT resource_id FROM resource_mod_usages WHERE "
            + " AND ".join(clauses)
            + " ORDER BY resource_id",
            params,
        )
        return [int(r["resource_id"]) for r in rows]

    def mods_in_resource(
        self, resource_id: int, *, category: str | None = None
    ) -> list[str]:
        """某个资源使用的 MOD guid（可按语义类别筛选）。"""
        clauses = ["resource_id = ?"]
        params: list[object] = [resource_id]
        if category is not None:
            fragment, category_params = sql_category_predicate(category)
            clauses.append(fragment)
            params.extend(category_params)
        rows = _fetchall(
            self.conn,
            "SELECT DISTINCT mod_guid FROM resource_mod_usages WHERE "
            + " AND ".join(clauses)
            + " ORDER BY mod_guid",
            params,
        )
        return [r["mod_guid"] for r in rows]

    def unknown_properties(
        self, *, resource_id: int | None = None, mod_guid: str | None = None
    ) -> list[str]:
        """列出无法归类的原始 property（用于审计「unknown」到底长什么样）。"""
        seen: list[str] = []
        for row in self._rows(
            resource_id=resource_id, mod_guid=mod_guid, category=None
        ):
            prop = row["property"]
            if classify_property(prop) == PROPERTY_CATEGORY_UNKNOWN and prop not in seen:
                seen.append(prop)
        return seen


__all__ = [
    "ReadOnlyViolation",
    "ResourceQuery",
    "ModQuery",
    "AuthorQuery",
    "PluginQuery",
    "UsageQuery",
    "REVIEW_REASON_CODES",
    "REVIEW_REASON_PARSE_FAILED",
    "REVIEW_REASON_PARSE_PARTIAL",
    "REVIEW_REASON_MISSING_NAME",
    "REVIEW_REASON_UNKNOWN_TYPE",
    "REVIEW_REASON_UNKNOWN_PROPERTY",
]
