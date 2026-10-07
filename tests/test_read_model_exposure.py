"""Phase 3.1 Step 4 —— Read Model Exposure（``type_source`` / ``notes``）。

依据：`docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md` §1-7 / §7 Step 4 / §8。

覆盖：
- ``type_source`` 只读暴露，并随用户类型修正变为 ``'user'``；
- ``notes`` 只读暴露，可写入 / 清空；
- Scanner rescan 不影响 Query 读到的用户字段（notes / user type）；
- Step 3 的 ``effective_display_name`` / ``title`` 行为不受影响；
- 旧式 ``ResourceSummary`` 构造（不含新字段）仍然有效（向后兼容）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.app import ResourceWriteService
from core.database import db as database
from core.library import LibraryStore
from core.query import ResourceQuery, ResourceSummary
from core.scanner import LibraryScanner
from tests.builders import write_card


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "read_model.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    try:
        yield connection
    finally:
        connection.close()


def _insert_resource(
    conn: sqlite3.Connection,
    *,
    resource_type: str = "unknown",
    type_source: str = "auto",
    name: str | None = "Alice",
    notes: str | None = None,
    path: str = "D:/cards/alice.png",
) -> int:
    cursor = conn.execute(
        "INSERT INTO resources(resource_type, type_source, name, notes,"
        " file_path, file_path_key)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (resource_type, type_source, name, notes, path, database.normalize_path_key(path)),
    )
    return int(cursor.lastrowid)


# ---------------------------------------------------------------------------
# 1. type_source read
# ---------------------------------------------------------------------------


def test_type_source_is_exposed_and_follows_user_override(conn):
    rid = _insert_resource(conn, resource_type="unknown", type_source="auto")

    summary = ResourceQuery(conn).summary(rid)
    assert summary.resource_type == "unknown"
    assert summary.type_source == "auto"

    ResourceWriteService(conn).set_resource_type(rid, "mod")

    summary = ResourceQuery(conn).summary(rid)
    assert summary.resource_type == "mod"
    assert summary.type_source == "user"


def test_type_source_is_exposed_in_list(conn):
    _insert_resource(conn, resource_type="character_card", type_source="auto")
    rows = ResourceQuery(conn).list()
    assert len(rows) == 1
    assert rows[0].type_source == "auto"


# ---------------------------------------------------------------------------
# 2. notes read
# ---------------------------------------------------------------------------


def test_notes_is_exposed_and_can_be_cleared(conn):
    rid = _insert_resource(conn)
    assert ResourceQuery(conn).summary(rid).notes is None

    ResourceWriteService(conn).set_notes(rid, "Some notes")
    assert ResourceQuery(conn).summary(rid).notes == "Some notes"

    ResourceWriteService(conn).set_notes(rid, None)
    assert ResourceQuery(conn).summary(rid).notes is None


def test_notes_reads_existing_value(conn):
    rid = _insert_resource(conn, notes="已有备注")
    assert ResourceQuery(conn).summary(rid).notes == "已有备注"


# ---------------------------------------------------------------------------
# 3. Scanner isolation（Query 视角）
# ---------------------------------------------------------------------------


def test_scanner_rescan_does_not_change_exposed_user_fields(tmp_path: Path):
    db_file = tmp_path / "scan.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    try:
        root = tmp_path / "library"
        root.mkdir()
        library = LibraryStore(connection).add(root, name="lib")
        card = write_card(root / "card.png", lastname="Old", firstname="Name")
        scanner = LibraryScanner(connection)
        scanner.scan(library.id)

        rid = int(connection.execute("SELECT id FROM resources").fetchone()["id"])
        service = ResourceWriteService(connection)
        service.set_notes(rid, "keep me")
        service.set_resource_type(rid, "mod")

        # 改变文件内容 → 触发 Scanner 的 UPDATE 路径
        write_card(card, lastname="Renamed", firstname="Character")
        scanner.scan(library.id)

        summary = ResourceQuery(connection).summary(rid)
        assert summary.notes == "keep me"
        assert summary.resource_type == "mod"
        assert summary.type_source == "user"
        assert summary.name == "RenamedCharacter"   # machine fact 正常更新
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# 4. display name regression（Step 3 行为不受 Step 4 影响）
# ---------------------------------------------------------------------------


def test_display_name_semantics_unaffected_by_new_fields(conn):
    rid = _insert_resource(conn, name="Alice")
    service = ResourceWriteService(conn)

    service.set_display_name(rid, "Alice")   # 与 name 相同 → 仍是 override
    summary = ResourceQuery(conn).summary(rid)
    assert summary.display_name == "Alice"
    assert summary.effective_display_name == "Alice"
    assert summary.title == "Alice"

    service.set_display_name(rid, None)      # clear → 回退 name
    summary = ResourceQuery(conn).summary(rid)
    assert summary.display_name is None
    assert summary.effective_display_name == "Alice"
    assert summary.title == "Alice"


# ---------------------------------------------------------------------------
# 5. Backward compatibility
# ---------------------------------------------------------------------------


_BASE_KWARGS = dict(
    id=1,
    resource_type="character_card",
    name="N",
    display_name=None,
    file_path="D:/x/y/z.png",
    relative_path="a\\b\\c.png",
    extension=".png",
    card_marker=None,
    file_size=None,
    modified_time=None,
    library_id=None,
    scan_status="present",
    parse_status="ok",
    needs_review=False,
)


def test_old_keyword_construction_still_works_without_new_fields():
    """旧式关键字构造不提供新字段时，新字段取默认值。"""
    summary = ResourceSummary(**_BASE_KWARGS)
    assert summary.type_source == "auto"
    assert summary.notes is None


def test_old_positional_construction_still_works():
    """旧式 positional 构造（Phase 2.3 时代的 19 个字段）仍然有效。"""
    summary = ResourceSummary(
        1, "character_card", "N", None, "D:/x/y/z.png", "a\\b\\c.png", ".png",
        None, None, None, None, "present", "ok", False, 0, 0, 0, 0, None,
    )
    assert summary.type_source == "auto"
    assert summary.notes is None
    assert summary.sha256 is None


def test_new_fields_can_be_set_explicitly():
    summary = ResourceSummary(**_BASE_KWARGS, type_source="user", notes="hi")
    assert summary.type_source == "user"
    assert summary.notes == "hi"
