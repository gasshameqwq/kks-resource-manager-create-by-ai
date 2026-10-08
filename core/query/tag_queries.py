"""Tag 只读查询 —— Phase 3.2。

依据 `docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md`（§7.2 / §7.4 / §7.5 / §8）。

- **只读**：所有语句经 ``core.query.readonly._fetchall`` / ``_fetchone``
  （即同一 ``SELECT`` / ``WITH`` 护栏）；本模块不写库、**不创建**任何行；
- **不是 Search**：不提供 ``resolve()`` / ``tag:`` / ``favorite:`` / 布尔语法 / 过滤；
- **不反向依赖** ``core.query.queries``（避免 import cycle）：本模块只依赖
  ``core.query.readonly`` / ``core.query.dto`` / ``core.models.tags`` / 归一化工具；
- system Tag 由 ``core.app.TagWriteService.ensure_system_tags()`` 保证存在，读侧永不创建。
"""

from __future__ import annotations

import sqlite3

from core.database import db as database
from core.models.tags import (
    FAVORITE_TAG_KEY,
    RESERVED_SYSTEM_TAG_KEYS,
    is_system_tag_key,
)
from core.query.dto import TagSummary
from core.query.readonly import _fetchall, _fetchone

#: Tag 概要列（``resource_count`` 为读取时派生的聚合值）。
_TAG_COLUMNS = """
    t.id, t.name, t.name_key, t.color, t.category,
    (SELECT count(*) FROM resource_tags rt WHERE rt.tag_id = t.id) AS resource_count
"""


def _row_to_tag_summary(row: sqlite3.Row) -> TagSummary:
    return TagSummary(
        id=int(row["id"]),
        name=row["name"],
        name_key=row["name_key"],
        color=row["color"],
        category=row["category"],
        is_system=is_system_tag_key(row["name_key"]),
        resource_count=int(row["resource_count"]),
    )


class TagQuery:
    """``tags`` / ``resource_tags`` 的只读查询（Phase 3.2 read model）。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def list(self) -> list[TagSummary]:
        """全部 Tag（含系统 Tag），按 ``name_key`` + ``id`` 稳定排序。

        ``resource_count`` 由**一次聚合查询**得到（避免 N+1）。
        """
        rows = _fetchall(
            self.conn,
            "SELECT t.id, t.name, t.name_key, t.color, t.category,"
            " count(rt.resource_id) AS resource_count"
            " FROM tags t LEFT JOIN resource_tags rt ON rt.tag_id = t.id"
            " GROUP BY t.id, t.name, t.name_key, t.color, t.category"
            " ORDER BY t.name_key, t.id",
        )
        return [_row_to_tag_summary(row) for row in rows]

    def get(self, tag_id: int) -> TagSummary | None:
        """按 id 取单个 Tag；不存在返回 ``None``（不抛异常）。"""
        rows = _fetchall(
            self.conn,
            f"SELECT {_TAG_COLUMNS} FROM tags t WHERE t.id = ?",
            [tag_id],
        )
        return _row_to_tag_summary(rows[0]) if rows else None

    def find_by_name(self, name: str | None) -> TagSummary | None:
        """按**精确** ``name_key`` 查找（``strip() + casefold()``）；空 / 未知返回 ``None``。

        不做 LIKE / 前缀 / 模糊 / 分词 —— 这不是搜索入口，只是 identity 解析。
        """
        key = database.normalize_name_key(name)
        if not key:
            return None
        rows = _fetchall(
            self.conn,
            f"SELECT {_TAG_COLUMNS} FROM tags t WHERE t.name_key = ?",
            [key],
        )
        return _row_to_tag_summary(rows[0]) if rows else None

    def for_resource(self, resource_id: int) -> list[TagSummary]:
        """某个资源上已赋的全部 Tag（按 ``name_key`` + ``id`` 稳定排序）。"""
        rows = _fetchall(
            self.conn,
            f"SELECT {_TAG_COLUMNS} FROM resource_tags rt"
            " JOIN tags t ON t.id = rt.tag_id"
            " WHERE rt.resource_id = ? ORDER BY t.name_key, t.id",
            [resource_id],
        )
        return [_row_to_tag_summary(row) for row in rows]

    def resource_ids(self, tag_id: int) -> list[int]:
        """某个 Tag 关联的资源 id（升序）。Tag 不存在时返回空列表。"""
        rows = _fetchall(
            self.conn,
            "SELECT resource_id FROM resource_tags WHERE tag_id = ?"
            " ORDER BY resource_id",
            [tag_id],
        )
        return [int(row["resource_id"]) for row in rows]

    def system_tags(self) -> list[TagSummary]:
        """保留系统 Tag 子集（按 ``name_key`` + ``id`` 稳定排序）。"""
        keys = sorted(RESERVED_SYSTEM_TAG_KEYS)
        if not keys:
            return []
        placeholders = ", ".join("?" for _ in keys)
        rows = _fetchall(
            self.conn,
            f"SELECT {_TAG_COLUMNS} FROM tags t"
            f" WHERE t.name_key IN ({placeholders})"
            " ORDER BY t.name_key, t.id",
            list(keys),
        )
        return [_row_to_tag_summary(row) for row in rows]

    def is_favorite(self, resource_id: int) -> bool:
        """该资源是否带有保留 Favorite 系统 Tag（只读派生；不存在即为 ``False``）。"""
        row = _fetchone(
            self.conn,
            "SELECT 1 FROM resource_tags rt JOIN tags t ON t.id = rt.tag_id"
            " WHERE rt.resource_id = ? AND t.name_key = ? LIMIT 1",
            [resource_id, FAVORITE_TAG_KEY],
        )
        return row is not None

    def favorite_resource_ids(self) -> list[int]:
        """全部收藏资源的 id（升序）。"""
        rows = _fetchall(
            self.conn,
            "SELECT rt.resource_id FROM resource_tags rt JOIN tags t ON t.id = rt.tag_id"
            " WHERE t.name_key = ? ORDER BY rt.resource_id",
            [FAVORITE_TAG_KEY],
        )
        return [int(row["resource_id"]) for row in rows]


__all__ = ["TagQuery"]
