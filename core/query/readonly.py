"""查询层的只读护栏（``SELECT`` / ``WITH``）—— Phase 1.3-A；Phase 3.2 抽出共享。

本模块是**唯一的**只读 SQL 执行边界：任何非 ``SELECT`` / ``WITH`` 语句都抛
:class:`ReadOnlyViolation`。

Phase 3.2 起由 ``core.query.queries`` 与 ``core.query.tag_queries`` 共同复用，
从而在**避免 ``tag_queries -> queries`` 反向 import** 的同时，保持单一护栏实现
（见 `docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md` §7.5）。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence


class ReadOnlyViolation(RuntimeError):
    """查询层只允许只读语句（SELECT / WITH）。"""


_ALLOWED_KEYWORDS = ("select", "with")


def _execute_select(
    conn: sqlite3.Connection, sql: str, params: Sequence[object] = ()
) -> sqlite3.Cursor:
    """执行一条只读语句；非 SELECT/WITH 一律拒绝。"""
    statement = sql.lstrip()
    keyword = statement.split(None, 1)[0].lower() if statement else ""
    if keyword not in _ALLOWED_KEYWORDS:
        raise ReadOnlyViolation(
            f"查询层只允许 SELECT / WITH 语句，收到：{keyword or '<空>'}!"
        )
    return conn.execute(sql, tuple(params))


def _fetchall(
    conn: sqlite3.Connection, sql: str, params: Sequence[object] = ()
) -> list[sqlite3.Row]:
    return _execute_select(conn, sql, params).fetchall()


def _fetchone(
    conn: sqlite3.Connection, sql: str, params: Sequence[object] = ()
) -> sqlite3.Row | None:
    return _execute_select(conn, sql, params).fetchone()


__all__ = ["ReadOnlyViolation", "_execute_select", "_fetchall", "_fetchone"]
