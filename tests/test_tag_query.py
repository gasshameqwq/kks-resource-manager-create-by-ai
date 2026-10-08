"""Phase 3.2 —— TagQuery 只读 read model 测试。

依据：`docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md`（§7.2–§8 / §10 / §12）。

覆盖 Contract §12 不变式（读侧）：
- T-I TagQuery 只发 SELECT（只读 boundary）；不写库、不创建系统 Tag
- T-J find_by_name 精确匹配（空 / 未知 ⇒ None；不做模糊）
- T-K resource_count == len(resource_ids(tag_id))
- T-L DTO 追加字段带默认值、向后兼容
- T-M schema 仍为 v2
"""

from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path

import pytest

from core.app import TagWriteService
from core.database import db as database
from core.database import schema as schema_mod
from core.query import (
    ResourceDetail,
    ResourceQuery,
    ResourceSummary,
    TagQuery,
    TagSummary,
)


# ---------------------------------------------------------------------------
# 夹具 / 工具
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "tag_query.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    try:
        yield connection
    finally:
        connection.close()


def _insert_resource(conn: sqlite3.Connection, index: int) -> int:
    path = f"d:/cards/r{index}.png"
    cursor = conn.execute(
        "INSERT INTO resources("
        " resource_type, type_source, name, file_path, file_path_key,"
        " relative_path, extension, scan_status, parse_status, needs_review)"
        " VALUES ('character_card', 'auto', ?, ?, ?, ?, '.png', 'present', 'ok', 0)",
        (f"Card{index}", path, path, f"r{index}.png"),
    )
    return int(cursor.lastrowid)


# ---------------------------------------------------------------------------
# list / get
# ---------------------------------------------------------------------------


def test_list_returns_tags_with_derived_resource_count(conn):
    service = TagWriteService(conn)
    query = TagQuery(conn)
    first = _insert_resource(conn, 1)
    second = _insert_resource(conn, 2)
    cute = service.create_tag("Cute")
    service.create_tag("Empty")
    service.assign_tag(first, cute)
    service.assign_tag(second, cute)

    tags = {tag.name_key: tag for tag in query.list()}
    assert tags["cute"].resource_count == 2
    assert tags["empty"].resource_count == 0
    assert [tag.name_key for tag in query.list()] == ["cute", "empty"]


def test_get_returns_summary_or_none(conn):
    service = TagWriteService(conn)
    query = TagQuery(conn)
    tag_id = service.create_tag("Cute", color="#fff", category="style")
    got = query.get(tag_id)
    assert got is not None
    assert got.name == "Cute"
    assert got.name_key == "cute"
    assert got.color == "#fff"
    assert got.category == "style"
    assert got.is_system is False
    assert got.resource_count == 0
    assert query.get(9999) is None


def test_list_reports_system_flag_for_reserved_key(conn):
    service = TagWriteService(conn)
    service.ensure_system_tags()
    service.create_tag("Cute")
    flags = {tag.name_key: tag.is_system for tag in TagQuery(conn).list()}
    assert flags["favorite"] is True
    assert flags["cute"] is False


# ---------------------------------------------------------------------------
# T-J find_by_name
# ---------------------------------------------------------------------------


def test_find_by_name_is_exact_and_case_insensitive(conn):
    TagWriteService(conn).create_tag("Cute")
    query = TagQuery(conn)
    assert query.find_by_name("cute") is not None
    assert query.find_by_name("  CUTE ") is not None
    assert query.find_by_name("Cute").name_key == "cute"


@pytest.mark.parametrize("bad", [None, "", "   ", "nope"])
def test_find_by_name_blank_or_unknown_returns_none(conn, bad):
    TagWriteService(conn).create_tag("Cute")
    assert TagQuery(conn).find_by_name(bad) is None


def test_find_by_name_is_not_fuzzy(conn):
    TagWriteService(conn).create_tag("cute")
    query = TagQuery(conn)
    assert query.find_by_name("cut") is None
    assert query.find_by_name("cute!") is None
    assert query.find_by_name("%cute%") is None


# ---------------------------------------------------------------------------
# for_resource / resource_ids
# ---------------------------------------------------------------------------


def test_for_resource_and_resource_ids(conn):
    service = TagWriteService(conn)
    query = TagQuery(conn)
    first = _insert_resource(conn, 1)
    second = _insert_resource(conn, 2)
    tag_a = service.create_tag("A")
    tag_b = service.create_tag("B")
    service.assign_tag(first, tag_a)
    service.assign_tag(first, tag_b)
    service.assign_tag(second, tag_a)

    assert [tag.name_key for tag in query.for_resource(first)] == ["a", "b"]
    assert query.for_resource(9999) == []
    assert query.resource_ids(tag_a) == [first, second]
    assert query.resource_ids(tag_b) == [first]
    assert query.resource_ids(9999) == []


# ---------------------------------------------------------------------------
# system_tags / favorite
# ---------------------------------------------------------------------------


def test_system_tags_only_returns_reserved_tags(conn):
    service = TagWriteService(conn)
    service.ensure_system_tags()
    service.create_tag("Cute")
    system = TagQuery(conn).system_tags()
    assert [tag.name_key for tag in system] == ["favorite"]
    assert all(tag.is_system for tag in system)


def test_system_tags_empty_before_ensure(conn):
    assert TagQuery(conn).system_tags() == []


def test_is_favorite_and_favorite_resource_ids(conn):
    service = TagWriteService(conn)
    query = TagQuery(conn)
    first = _insert_resource(conn, 1)
    second = _insert_resource(conn, 2)
    service.set_favorite(first, True)
    assert query.is_favorite(first) is True
    assert query.is_favorite(second) is False
    assert query.favorite_resource_ids() == [first]
    service.set_favorite(first, False)
    assert query.is_favorite(first) is False
    assert query.favorite_resource_ids() == []


# ---------------------------------------------------------------------------
# T-K resource_count consistency
# ---------------------------------------------------------------------------


def test_resource_count_matches_resource_ids(conn):
    service = TagWriteService(conn)
    query = TagQuery(conn)
    resources = [_insert_resource(conn, i) for i in range(1, 4)]
    tag_a = service.create_tag("A")
    tag_b = service.create_tag("B")
    service.assign_tag(resources[0], tag_a)
    service.assign_tag(resources[1], tag_a)
    service.assign_tag(resources[2], tag_b)
    for tag in query.list():
        assert tag.resource_count == len(query.resource_ids(tag.id))


# ---------------------------------------------------------------------------
# T-I read-only boundary
# ---------------------------------------------------------------------------


def test_tag_query_performs_no_writes(conn):
    service = TagWriteService(conn)
    query = TagQuery(conn)
    resource_id = _insert_resource(conn, 1)
    tag_id = service.create_tag("Cute")
    service.assign_tag(resource_id, tag_id)

    before = conn.total_changes
    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        query.list()
        query.get(tag_id)
        query.find_by_name("cute")
        query.for_resource(resource_id)
        query.resource_ids(tag_id)
        query.system_tags()
        query.is_favorite(resource_id)
        query.favorite_resource_ids()
    finally:
        conn.set_trace_callback(None)

    assert conn.total_changes == before
    assert statements, "应当至少执行了若干 SELECT"
    assert all(sql.lstrip().lower().startswith("select") for sql in statements)


def test_tag_query_does_not_create_system_tag(conn):
    query = TagQuery(conn)
    assert query.list() == []
    assert query.system_tags() == []
    assert query.is_favorite(1) is False
    assert conn.execute("SELECT count(*) AS c FROM tags").fetchone()["c"] == 0


def test_tag_query_exposes_no_resolve(conn):
    assert not hasattr(TagQuery(conn), "resolve")


# ---------------------------------------------------------------------------
# T-L DTO additive compatibility / ResourceDetail wiring
# ---------------------------------------------------------------------------


def test_tag_summary_defaults_and_frozen():
    tag = TagSummary(
        id=1, name="Cute", name_key="cute", color=None, category=None, is_system=False
    )
    assert tag.resource_count == 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        tag.name = "x"  # type: ignore[misc]


def test_resource_detail_defaults_are_backwards_compatible():
    summary = ResourceSummary(
        id=1,
        resource_type="unknown",
        name=None,
        display_name=None,
        file_path="d:/x.png",
        relative_path=None,
        extension=".png",
        card_marker=None,
        file_size=None,
        modified_time=None,
        library_id=None,
        scan_status="present",
        parse_status="ok",
        needs_review=False,
    )
    detail = ResourceDetail(resource=summary)
    assert detail.tags == ()
    assert detail.is_favorite is False


def test_resource_query_get_populates_tags_and_favorite(conn):
    service = TagWriteService(conn)
    resource_id = _insert_resource(conn, 1)
    tag_id = service.create_tag("Cute")
    service.assign_tag(resource_id, tag_id)
    service.set_favorite(resource_id, True)

    detail = ResourceQuery(conn).get(resource_id)
    assert detail is not None
    keys = {tag.name_key for tag in detail.tags}
    assert {"cute", "favorite"} <= keys
    assert detail.is_favorite is True


# ---------------------------------------------------------------------------
# T-M schema unchanged
# ---------------------------------------------------------------------------


def test_schema_remains_v2(conn):
    assert schema_mod.SCHEMA_VERSION == 2
    assert sorted(schema_mod.MIGRATIONS) == [1, 2]
    assert len(schema_mod.CURRENT_TABLES) == 16
    assert not any(
        name == "favorites" for name in database.table_names(conn)
    )
