"""Phase 3.1 Step 1 —— ResourceWriteService 行为与 ownership 边界测试。

依据：`docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md`（§4 / §5 / §7 Step 1 / §8）。

覆盖：
- display_name：正常值 / strip / None / 空串 / 纯空白 / 等于 name 仍是 override /
  不存在资源 / 幂等；
- notes：正常值 / strip / None / 空白 / 不存在资源；
- resource_type：合法值 / type_source='user' / 非法值（不改库）/ 不存在资源；
- ownership：写服务只改用户列，machine facts 原样；
- 事务：失败回滚 + 原样抛出 + 不留下部分更新。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.app import (
    InvalidResourceValue,
    ResourceNotFound,
    ResourceWriteService,
)
from core.database import db as database
from core.models import RESOURCE_TYPES


# ---------------------------------------------------------------------------
# 夹具 / 工具
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "resource_write.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    try:
        yield connection
    finally:
        connection.close()


def _insert_resource(
    conn: sqlite3.Connection,
    *,
    name: str | None = "Alice",
    resource_type: str = "character_card",
    type_source: str = "auto",
    display_name: str | None = None,
    notes: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO resources("
        " resource_type, type_source, name, display_name, notes,"
        " file_path, file_path_key, relative_path, file_size, modified_time,"
        " extension, sha256, card_marker, metadata_json,"
        " scan_status, parse_status, needs_review)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'present', 'ok', 0)",
        (
            resource_type,
            type_source,
            name,
            display_name,
            notes,
            "D:/cards/alice.png",
            "d:/cards/alice.png",
            "alice.png",
            1234,
            111.5,
            ".png",
            "a" * 64,
            "KoiKatuCharaSun",
            '{"user_id": "u1"}',
        ),
    )
    return int(cursor.lastrowid)


def _row(conn: sqlite3.Connection, resource_id: int) -> sqlite3.Row:
    return conn.execute(
        "SELECT * FROM resources WHERE id = ?", (resource_id,)
    ).fetchone()


#: machine fact 列（不含系统簿记 ``updated_at``，它按 Contract §5.2.1 允许被写入）。
_MACHINE_COLUMNS = (
    "id",
    "name",
    "file_path",
    "file_path_key",
    "relative_path",
    "file_size",
    "modified_time",
    "extension",
    "sha256",
    "card_marker",
    "metadata_json",
    "parse_status",
    "parse_error",
    "scan_status",
    "last_scanned_at",
    "created_at",
)


def _machine_snapshot(conn: sqlite3.Connection, resource_id: int) -> dict:
    row = _row(conn, resource_id)
    return {column: row[column] for column in _MACHINE_COLUMNS}


# ---------------------------------------------------------------------------
# display_name
# ---------------------------------------------------------------------------


def test_set_display_name_stores_value(conn):
    rid = _insert_resource(conn)
    ResourceWriteService(conn).set_display_name(rid, "新名字")
    assert _row(conn, rid)["display_name"] == "新名字"


def test_set_display_name_strips_whitespace(conn):
    rid = _insert_resource(conn)
    ResourceWriteService(conn).set_display_name(rid, "  Alice  ")
    assert _row(conn, rid)["display_name"] == "Alice"


@pytest.mark.parametrize("value", [None, "", "   ", "\t\n "])
def test_set_display_name_clears_to_null(conn, value):
    rid = _insert_resource(conn, display_name="旧展示名")
    ResourceWriteService(conn).set_display_name(rid, value)
    assert _row(conn, rid)["display_name"] is None


def test_display_name_equal_to_name_is_still_an_override(conn):
    """name == display_name 仍是有效 override（不得用相等性判断 override）。"""
    rid = _insert_resource(conn, name="Alice", display_name=None)
    ResourceWriteService(conn).set_display_name(rid, "Alice")
    row = _row(conn, rid)
    assert row["name"] == "Alice"           # 写服务不碰 name
    assert row["display_name"] == "Alice"   # 值被原样保存
    assert row["display_name"] is not None  # 非 NULL ⇒ override 存在
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resources"
            " WHERE id = ? AND display_name IS NOT NULL",
            (rid,),
        ).fetchone()["c"]
        == 1
    )


def test_set_display_name_unknown_resource(conn):
    with pytest.raises(ResourceNotFound):
        ResourceWriteService(conn).set_display_name(999, "x")


def test_set_display_name_rejects_non_string(conn):
    rid = _insert_resource(conn)
    with pytest.raises(InvalidResourceValue):
        ResourceWriteService(conn).set_display_name(rid, 123)  # type: ignore[arg-type]
    assert _row(conn, rid)["display_name"] is None


def test_set_display_name_is_idempotent(conn):
    rid = _insert_resource(conn)
    service = ResourceWriteService(conn)
    service.set_display_name(rid, "Alice")
    first = _row(conn, rid)["display_name"]
    service.set_display_name(rid, "Alice")
    second = _row(conn, rid)["display_name"]
    assert first == second == "Alice"
    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 1


# ---------------------------------------------------------------------------
# notes
# ---------------------------------------------------------------------------


def test_set_notes_stores_value_and_strips(conn):
    rid = _insert_resource(conn)
    ResourceWriteService(conn).set_notes(rid, "  需要补风扇  ")
    assert _row(conn, rid)["notes"] == "需要补风扇"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_set_notes_clears_to_null(conn, value):
    rid = _insert_resource(conn, notes="旧备注")
    ResourceWriteService(conn).set_notes(rid, value)
    assert _row(conn, rid)["notes"] is None


def test_set_notes_unknown_resource(conn):
    with pytest.raises(ResourceNotFound):
        ResourceWriteService(conn).set_notes(999, "x")


# ---------------------------------------------------------------------------
# resource_type
# ---------------------------------------------------------------------------


def test_set_resource_type_sets_user_source(conn):
    rid = _insert_resource(conn, resource_type="unknown", type_source="auto")
    ResourceWriteService(conn).set_resource_type(rid, "character_card")
    row = _row(conn, rid)
    assert row["resource_type"] == "character_card"
    assert row["type_source"] == "user"


@pytest.mark.parametrize("value", list(RESOURCE_TYPES))
def test_set_resource_type_accepts_every_declared_type(conn, value):
    rid = _insert_resource(conn, resource_type="unknown")
    ResourceWriteService(conn).set_resource_type(rid, value)
    assert _row(conn, rid)["resource_type"] == value


@pytest.mark.parametrize("value", ["not_a_type", "", "Character_Card", "mod "])
def test_set_resource_type_rejects_invalid_value_without_writing(conn, value):
    rid = _insert_resource(conn, resource_type="unknown", type_source="auto")
    with pytest.raises(InvalidResourceValue):
        ResourceWriteService(conn).set_resource_type(rid, value)
    row = _row(conn, rid)
    assert row["resource_type"] == "unknown"   # 未修改
    assert row["type_source"] == "auto"        # 未修改


def test_set_resource_type_unknown_resource(conn):
    with pytest.raises(ResourceNotFound):
        ResourceWriteService(conn).set_resource_type(999, "mod")


# ---------------------------------------------------------------------------
# ownership boundary
# ---------------------------------------------------------------------------


def test_user_writes_leave_machine_facts_untouched(conn):
    rid = _insert_resource(conn, resource_type="unknown", type_source="auto")
    service = ResourceWriteService(conn)

    before = _machine_snapshot(conn, rid)
    service.set_display_name(rid, "New Name")
    service.set_notes(rid, "hello")
    service.set_resource_type(rid, "mod")
    after = _machine_snapshot(conn, rid)

    assert after == before, "用户写入不得改变任何 machine fact"
    row = _row(conn, rid)
    assert row["display_name"] == "New Name"
    assert row["notes"] == "hello"
    assert row["resource_type"] == "mod"
    assert row["type_source"] == "user"


def test_user_write_sql_only_targets_user_columns(conn):
    """SQL 层面证明：UPDATE 的 SET 目标只含用户列 + 系统簿记 updated_at。"""
    rid = _insert_resource(conn)
    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        service = ResourceWriteService(conn)
        service.set_display_name(rid, "X")
        service.set_notes(rid, "Y")
        service.set_resource_type(rid, "mod")
    finally:
        conn.set_trace_callback(None)

    allowed = {"display_name", "notes", "resource_type", "type_source", "updated_at"}
    # 注意：SQLite 触发器的内部语句会以「外层 UPDATE」的形式重复上报，
    # 因此这里断言「出现的 SET 目标集合」而不是语句条数。
    updates = [
        sql
        for sql in statements
        if sql.lstrip().upper().startswith("UPDATE RESOURCES")
    ]
    assert updates, "应当发出 UPDATE resources"
    target_sets = set()
    for sql in updates:
        set_part = sql.split(" SET ", 1)[1].split(" WHERE ", 1)[0]
        targets = frozenset(piece.split("=")[0].strip() for piece in set_part.split(","))
        assert targets <= allowed, targets
        target_sets.add(targets)
    assert target_sets == {
        frozenset({"display_name", "updated_at"}),
        frozenset({"notes", "updated_at"}),
        frozenset({"resource_type", "type_source", "updated_at"}),
    }, target_sets


def test_user_write_updates_updated_at(conn):
    rid = _insert_resource(conn)
    conn.execute(
        "UPDATE resources SET updated_at = '2000-01-01 00:00:00' WHERE id = ?",
        (rid,),
    )
    ResourceWriteService(conn).set_notes(rid, "x")
    assert _row(conn, rid)["updated_at"] != "2000-01-01 00:00:00"


# ---------------------------------------------------------------------------
# transaction
# ---------------------------------------------------------------------------


def test_failed_write_rolls_back_and_propagates(conn):
    """写入被强制打断时：原样抛出、事务回滚、不留下部分更新。"""
    rid = _insert_resource(conn, resource_type="unknown", type_source="auto")
    before = _machine_snapshot(conn, rid)
    conn.execute(
        "CREATE TRIGGER test_block_resource_update BEFORE UPDATE ON resources"
        " BEGIN SELECT RAISE(ABORT, 'blocked for test'); END"
    )

    with pytest.raises(sqlite3.IntegrityError):
        ResourceWriteService(conn).set_resource_type(rid, "mod")

    row = _row(conn, rid)
    assert row["resource_type"] == "unknown"   # resource_type 未部分更新
    assert row["type_source"] == "auto"        # type_source 未被顺带改成 user
    assert not conn.in_transaction, "失败事务必须已回滚"
    assert _machine_snapshot(conn, rid) == before
