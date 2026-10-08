"""Phase 3.2 —— TagWriteService 行为 / ownership / transaction 边界测试。

依据：`docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md`（§3–§7 / §12）。

覆盖 Contract §12 不变式（写侧）：
- T-A normalization（strip + casefold）/ 空白名拒绝
- T-B create collision（大小写不敏感，拒绝且不合并）
- T-C rename collision / system Tag immutable
- T-D system Tag 不可删 / 普通 Tag 删除级联清理 resource_tags
- T-E assign / unassign 幂等 + origin='user'
- T-F Favorite 持久化（唯一事实 = resource_tags）/ 幂等 / 用户不能创建 'favorite'
- T-H 仅 TagWriteService 写 tags / resource_tags（且不写 resources）
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.app import (
    InvalidTagValue,
    ReservedTagName,
    ResourceNotFound,
    SystemTagImmutable,
    TagNameConflict,
    TagNotFound,
    TagWriteService,
)
from core.database import db as database
from core.models import FAVORITE_TAG_KEY


# ---------------------------------------------------------------------------
# 夹具 / 工具
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "tag_write.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    try:
        yield connection
    finally:
        connection.close()


def _insert_resource(conn: sqlite3.Connection, *, name: str = "Alice") -> int:
    cursor = conn.execute(
        "INSERT INTO resources("
        " resource_type, type_source, name, file_path, file_path_key,"
        " relative_path, file_size, modified_time, extension, sha256,"
        " card_marker, metadata_json, scan_status, parse_status, needs_review)"
        " VALUES ('character_card', 'auto', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
        " 'present', 'ok', 0)",
        (
            name,
            "D:/cards/tag.png",
            "d:/cards/tag.png",
            "tag.png",
            10,
            1.0,
            ".png",
            "a" * 64,
            "KoiKatuCharaSun",
            "{}",
        ),
    )
    return int(cursor.lastrowid)


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"])


def _tag_row(conn: sqlite3.Connection, tag_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()


def _favorite_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT id FROM tags WHERE name_key = ?", (FAVORITE_TAG_KEY,)
    ).fetchone()
    assert row is not None, "favorite 系统 Tag 应当存在"
    return int(row["id"])


# ---------------------------------------------------------------------------
# T-A normalization / 空白名拒绝
# ---------------------------------------------------------------------------


def test_create_tag_stores_name_and_normalized_key(conn):
    tag_id = TagWriteService(conn).create_tag("  Favorite Style  ")
    row = _tag_row(conn, tag_id)
    assert row["name"] == "Favorite Style"
    assert row["name_key"] == "favorite style"


def test_create_tag_casefolds_key(conn):
    tag_id = TagWriteService(conn).create_tag("CUTE")
    assert _tag_row(conn, tag_id)["name_key"] == "cute"


@pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
def test_create_tag_rejects_blank_name(conn, bad):
    with pytest.raises(InvalidTagValue):
        TagWriteService(conn).create_tag(bad)


def test_create_tag_rejects_non_string_name(conn):
    with pytest.raises(InvalidTagValue):
        TagWriteService(conn).create_tag(None)  # type: ignore[arg-type]
    with pytest.raises(InvalidTagValue):
        TagWriteService(conn).create_tag(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T-B create collision
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("second", ["cute", "CUTE", "  Cute  "])
def test_create_tag_collision_rejected_case_insensitive(conn, second):
    service = TagWriteService(conn)
    service.create_tag("Cute")
    with pytest.raises(TagNameConflict):
        service.create_tag(second)
    assert _count(conn, "tags") == 1


def test_create_tag_rejects_reserved_key(conn):
    service = TagWriteService(conn)
    for name in ("favorite", "Favorite", "FAVORITE", "  favorite  "):
        with pytest.raises(ReservedTagName):
            service.create_tag(name)
    assert _count(conn, "tags") == 0


# ---------------------------------------------------------------------------
# T-C rename
# ---------------------------------------------------------------------------


def test_rename_tag_updates_name_and_key(conn):
    service = TagWriteService(conn)
    tag_id = service.create_tag("Cute")
    service.rename_tag(tag_id, "  Pretty  ")
    row = _tag_row(conn, tag_id)
    assert row["name"] == "Pretty"
    assert row["name_key"] == "pretty"


def test_rename_tag_collision_rejected(conn):
    service = TagWriteService(conn)
    first = service.create_tag("Cute")
    service.create_tag("Pretty")
    with pytest.raises(TagNameConflict):
        service.rename_tag(first, "PRETTY")
    assert _tag_row(conn, first)["name"] == "Cute"


def test_rename_tag_to_own_key_is_allowed(conn):
    service = TagWriteService(conn)
    tag_id = service.create_tag("Cute")
    service.rename_tag(tag_id, "CUTE")
    assert _tag_row(conn, tag_id)["name"] == "CUTE"


def test_rename_unknown_tag_raises(conn):
    with pytest.raises(TagNotFound):
        TagWriteService(conn).rename_tag(9999, "x")


def test_rename_tag_rejects_blank(conn):
    service = TagWriteService(conn)
    tag_id = service.create_tag("Cute")
    with pytest.raises(InvalidTagValue):
        service.rename_tag(tag_id, "   ")


def test_rename_user_tag_to_reserved_key_rejected(conn):
    service = TagWriteService(conn)
    tag_id = service.create_tag("Cute")
    with pytest.raises(ReservedTagName):
        service.rename_tag(tag_id, "favorite")


# ---------------------------------------------------------------------------
# T-D delete
# ---------------------------------------------------------------------------


def test_delete_tag_removes_assignments_via_cascade(conn):
    service = TagWriteService(conn)
    resource_id = _insert_resource(conn)
    tag_id = service.create_tag("Cute")
    service.assign_tag(resource_id, tag_id)
    assert _count(conn, "resource_tags") == 1

    service.delete_tag(tag_id)
    assert _tag_row(conn, tag_id) is None
    assert _count(conn, "resource_tags") == 0


def test_delete_unknown_tag_raises(conn):
    with pytest.raises(TagNotFound):
        TagWriteService(conn).delete_tag(9999)


def test_system_tag_cannot_be_renamed_or_deleted(conn):
    service = TagWriteService(conn)
    service.ensure_system_tags()
    favorite_id = _favorite_id(conn)
    with pytest.raises(SystemTagImmutable):
        service.rename_tag(favorite_id, "Fav")
    with pytest.raises(SystemTagImmutable):
        service.delete_tag(favorite_id)
    assert _tag_row(conn, favorite_id) is not None


# ---------------------------------------------------------------------------
# T-E assign / unassign
# ---------------------------------------------------------------------------


def test_assign_tag_is_idempotent_and_user_origin(conn):
    service = TagWriteService(conn)
    resource_id = _insert_resource(conn)
    tag_id = service.create_tag("Cute")
    service.assign_tag(resource_id, tag_id)
    service.assign_tag(resource_id, tag_id)
    rows = conn.execute("SELECT * FROM resource_tags").fetchall()
    assert len(rows) == 1
    assert rows[0]["origin"] == "user"


def test_unassign_tag_is_idempotent(conn):
    service = TagWriteService(conn)
    resource_id = _insert_resource(conn)
    tag_id = service.create_tag("Cute")
    service.assign_tag(resource_id, tag_id)
    service.unassign_tag(resource_id, tag_id)
    service.unassign_tag(resource_id, tag_id)
    assert _count(conn, "resource_tags") == 0


def test_assign_unknown_resource_raises(conn):
    service = TagWriteService(conn)
    tag_id = service.create_tag("Cute")
    with pytest.raises(ResourceNotFound):
        service.assign_tag(9999, tag_id)


def test_assign_unknown_tag_raises(conn):
    service = TagWriteService(conn)
    resource_id = _insert_resource(conn)
    with pytest.raises(TagNotFound):
        service.assign_tag(resource_id, 9999)


# ---------------------------------------------------------------------------
# T-F Favorite
# ---------------------------------------------------------------------------


def test_ensure_system_tags_is_idempotent(conn):
    service = TagWriteService(conn)
    service.ensure_system_tags()
    service.ensure_system_tags()
    rows = conn.execute(
        "SELECT id, name, name_key FROM tags WHERE name_key = ?",
        (FAVORITE_TAG_KEY,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["name"] == "Favorite"


def test_set_favorite_persists_only_via_resource_tags(conn):
    service = TagWriteService(conn)
    resource_id = _insert_resource(conn)
    service.set_favorite(resource_id, True)

    favorite_id = _favorite_id(conn)
    rows = conn.execute("SELECT * FROM resource_tags").fetchall()
    assert len(rows) == 1
    assert int(rows[0]["tag_id"]) == favorite_id
    assert rows[0]["origin"] == "user"
    # 不存在第二套 Favorite 持久化
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(resources)").fetchall()
    }
    assert "favorite" not in columns


def test_set_favorite_true_and_false_are_idempotent(conn):
    service = TagWriteService(conn)
    resource_id = _insert_resource(conn)
    service.set_favorite(resource_id, True)
    service.set_favorite(resource_id, True)
    assert _count(conn, "resource_tags") == 1
    service.set_favorite(resource_id, False)
    service.set_favorite(resource_id, False)
    assert _count(conn, "resource_tags") == 0
    # 系统 Tag 行保留
    assert _count(conn, "tags") == 1


def test_set_favorite_unknown_resource_does_not_create_system_tag(conn):
    service = TagWriteService(conn)
    with pytest.raises(ResourceNotFound):
        service.set_favorite(9999, True)
    assert _count(conn, "tags") == 0


def test_set_favorite_requires_bool(conn):
    service = TagWriteService(conn)
    resource_id = _insert_resource(conn)
    with pytest.raises(InvalidTagValue):
        service.set_favorite(resource_id, "yes")  # type: ignore[arg-type]


def test_system_tag_can_be_assigned_via_normal_path(conn):
    service = TagWriteService(conn)
    resource_id = _insert_resource(conn)
    service.ensure_system_tags()
    service.assign_tag(resource_id, _favorite_id(conn))
    assert _count(conn, "resource_tags") == 1


# ---------------------------------------------------------------------------
# color / category（metadata，不扩展语义）
# ---------------------------------------------------------------------------


def test_create_tag_stores_color_and_category(conn):
    tag_id = TagWriteService(conn).create_tag(
        "Cute", color="#8ab4f8", category="style"
    )
    row = _tag_row(conn, tag_id)
    assert row["color"] == "#8ab4f8"
    assert row["category"] == "style"


def test_blank_color_and_category_become_null(conn):
    tag_id = TagWriteService(conn).create_tag("Cute", color="  ", category="")
    row = _tag_row(conn, tag_id)
    assert row["color"] is None
    assert row["category"] is None


# ---------------------------------------------------------------------------
# T-H ownership / transaction boundary
# ---------------------------------------------------------------------------


def test_tag_write_never_writes_resources_table(conn):
    service = TagWriteService(conn)
    resource_id = _insert_resource(conn)
    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        tag_id = service.create_tag("Cute")
        service.assign_tag(resource_id, tag_id)
        service.unassign_tag(resource_id, tag_id)
        service.set_favorite(resource_id, True)
    finally:
        conn.set_trace_callback(None)

    writes = [
        sql
        for sql in statements
        if sql.lstrip()[:6].lower() in ("insert", "update", "delete")
    ]
    assert writes, "测试必须先产生对 tags / resource_tags 的写入"
    assert all("resources" not in sql.lower() for sql in writes)
    assert any("into tags" in sql.lower() for sql in writes)
    assert any("into resource_tags" in sql.lower() for sql in writes)


def test_create_tag_conflict_leaves_no_partial_row(conn):
    service = TagWriteService(conn)
    service.create_tag("Cute")
    before = _count(conn, "tags")
    with pytest.raises(TagNameConflict):
        service.create_tag("cute")
    assert _count(conn, "tags") == before
