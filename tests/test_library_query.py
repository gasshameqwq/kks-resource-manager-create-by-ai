"""Phase 1.4-B.1：Library 只读查询测试。

覆盖：空库、单/多 Library、资源计数、空 Library、稳定排序、启用/暂停过滤、
按 id 查询（含不存在 id）、与 ``ResourceQuery`` 组合一致、只读不变量、真实样本只读验证。
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.database import schema as schema_mod  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.query import LibraryQuery, LibrarySummary, ResourceQuery  # noqa: E402
from core.scanner import LibraryScanner  # noqa: E402


# ---------------------------------------------------------------------------
# 夹具 / 构造器
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "library_query.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    yield connection
    connection.close()


def _add_library(
    conn,
    library_id: int,
    *,
    name: str,
    root_path: str | None = None,
    enabled: int = 1,
    notes: str = "",
    last_scan_at: str | None = None,
) -> None:
    root = root_path if root_path is not None else f"D:/lib{library_id}"
    conn.execute(
        "INSERT INTO libraries(id, name, root_path, root_path_key, enabled, notes,"
        " last_scan_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (library_id, name, root, root.casefold(), enabled, notes, last_scan_at),
    )


def _add_resource(conn, resource_id: int, *, library_id: int | None, name: str = "r") -> None:
    conn.execute(
        "INSERT INTO resources(id, resource_type, name, display_name, file_path,"
        " file_path_key, library_id) VALUES (?, 'character_card', ?, ?, ?, ?, ?)",
        (
            resource_id,
            name,
            name,
            f"D:/r/{resource_id}.png",
            f"d:/r/{resource_id}.png",
            library_id,
        ),
    )


def _ids(rows) -> list[int]:
    return [row.id for row in rows]


# ---------------------------------------------------------------------------
# 空 / 单 / 多
# ---------------------------------------------------------------------------


def test_empty_database(conn) -> None:
    lq = LibraryQuery(conn)
    assert lq.list() == []
    assert lq.list(include_disabled=False) == []
    assert lq.count() == 0
    assert lq.count(include_disabled=False) == 0


def test_single_library_without_resources(conn) -> None:
    _add_library(conn, 1, name="Cards", root_path="D:/Cards")
    lq = LibraryQuery(conn)
    rows = lq.list()
    assert len(rows) == 1
    summary = rows[0]
    assert isinstance(summary, LibrarySummary)
    assert summary.id == 1
    assert summary.name == "Cards"
    assert summary.root_path == "D:/Cards"
    assert summary.enabled is True
    assert summary.resource_count == 0
    assert lq.count() == 1


def test_multiple_libraries_counts(conn) -> None:
    _add_library(conn, 1, name="Alpha", root_path="D:/a")
    _add_library(conn, 2, name="Beta", root_path="D:/b")
    _add_library(conn, 3, name="Gamma", root_path="D:/c")
    _add_resource(conn, 1, library_id=1)
    _add_resource(conn, 2, library_id=1)
    _add_resource(conn, 3, library_id=2)
    # 无归属资源（library_id = NULL）不属于任何 Library
    _add_resource(conn, 4, library_id=None)

    lq = LibraryQuery(conn)
    by_id = {row.id: row for row in lq.list()}
    assert by_id[1].resource_count == 2
    assert by_id[2].resource_count == 1
    assert by_id[3].resource_count == 0  # 空 Library 仍然出现
    assert set(by_id) == {1, 2, 3}
    assert sum(row.resource_count for row in lq.list()) == 3


def test_empty_library_is_listed_with_zero(conn) -> None:
    _add_library(conn, 7, name="Empty", root_path="D:/empty")
    rows = LibraryQuery(conn).list()
    assert [r.id for r in rows] == [7]
    assert rows[0].resource_count == 0


# ---------------------------------------------------------------------------
# 排序稳定性
# ---------------------------------------------------------------------------


def test_stable_ordering_by_name_then_id(conn) -> None:
    # 大小写不同的同名 -> name NOCASE 相等 -> 用 id 决出稳定顺序
    _add_library(conn, 3, name="alpha", root_path="D:/3")
    _add_library(conn, 1, name="zeta", root_path="D:/1")
    _add_library(conn, 2, name="Alpha", root_path="D:/2")
    _add_library(conn, 4, name="Beta", root_path="D:/4")

    lq = LibraryQuery(conn)
    expected = [2, 3, 4, 1]
    assert _ids(lq.list()) == expected
    # 重复调用结果稳定
    assert _ids(lq.list()) == expected


# ---------------------------------------------------------------------------
# 启用 / 暂停
# ---------------------------------------------------------------------------


def test_include_disabled_filter(conn) -> None:
    _add_library(conn, 1, name="On", root_path="D:/on", enabled=1)
    _add_library(conn, 2, name="Off", root_path="D:/off", enabled=0)
    _add_resource(conn, 1, library_id=1)
    _add_resource(conn, 2, library_id=2)

    lq = LibraryQuery(conn)
    assert _ids(lq.list()) == [2, 1]  # Off < On（name NOCASE）
    assert _ids(lq.list(include_disabled=False)) == [1]
    assert lq.count() == 2
    assert lq.count(include_disabled=False) == 1
    # 暂停的 Library 仍然带自己的资源计数
    by_id = {row.id: row for row in lq.list()}
    assert by_id[2].enabled is False
    assert by_id[2].resource_count == 1
    assert by_id[1].enabled is True


# ---------------------------------------------------------------------------
# 按 id 查询
# ---------------------------------------------------------------------------


def test_get_existing_and_missing(conn) -> None:
    _add_library(conn, 1, name="Cards", root_path="D:/Cards", notes="备注", last_scan_at="2026-10-06 12:00:00")
    _add_resource(conn, 1, library_id=1)

    lq = LibraryQuery(conn)
    summary = lq.get(1)
    assert summary is not None
    assert summary.id == 1
    assert summary.notes == "备注"
    assert summary.last_scan_at == "2026-10-06 12:00:00"
    assert summary.resource_count == 1

    # 不存在的 id（含负数）返回 None，不抛异常
    assert lq.get(999999) is None
    assert lq.get(-1) is None


# ---------------------------------------------------------------------------
# 与 ResourceQuery 组合一致
# ---------------------------------------------------------------------------


def test_counts_match_resource_query(conn) -> None:
    _add_library(conn, 1, name="A", root_path="D:/a")
    _add_library(conn, 2, name="B", root_path="D:/b")
    _add_library(conn, 3, name="C", root_path="D:/c")
    _add_resource(conn, 1, library_id=1)
    _add_resource(conn, 2, library_id=1)
    _add_resource(conn, 3, library_id=2)
    _add_resource(conn, 4, library_id=None)

    lq = LibraryQuery(conn)
    rq = ResourceQuery(conn)
    for summary in lq.list():
        assert summary.resource_count == rq.count(library_id=summary.id)
    # NULL library_id 的资源不计入任何一个 Library
    assert sum(s.resource_count for s in lq.list()) == rq.count() - 1


def test_query_layer_does_not_depend_on_write_layer(conn) -> None:
    """统计必须来自 resources 聚合，而不是写层 LibraryStore。"""
    _add_library(conn, 1, name="A", root_path="D:/a")
    _add_resource(conn, 1, library_id=1)

    # 写层 stats() 与只读聚合一致（作为对照，不参与 Query Layer 实现）
    write_layer = LibraryStore(conn).stats(1)
    summary = LibraryQuery(conn).get(1)
    assert summary is not None
    assert summary.resource_count == write_layer.resources == 1

    import core.query.queries as queries_mod

    source = Path(queries_mod.__file__).read_text(encoding="utf-8")
    import_lines = [
        line
        for line in source.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    assert not any("core.library" in line for line in import_lines), "Query Layer 不得依赖写层"
    assert not any("LibraryStore" in line for line in import_lines)


# ---------------------------------------------------------------------------
# DTO 形状（不夹带 UI 专用字段）
# ---------------------------------------------------------------------------


def test_library_summary_fields_and_frozen() -> None:
    names = {f.name for f in dataclasses.fields(LibrarySummary)}
    assert names == {
        "id",
        "name",
        "root_path",
        "enabled",
        "notes",
        "last_scan_at",
        "resource_count",
    }
    for forbidden in ("color", "icon", "selected", "expanded", "hidden", "order"):
        assert forbidden not in names

    summary = LibrarySummary(
        id=1, name="n", root_path="p", enabled=True, notes="", last_scan_at=None
    )
    assert summary.resource_count == 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        summary.name = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 只读不变量
# ---------------------------------------------------------------------------


def test_library_query_is_read_only(conn) -> None:
    _add_library(conn, 1, name="A", root_path="D:/a")
    _add_library(conn, 2, name="B", root_path="D:/b", enabled=0)
    _add_resource(conn, 1, library_id=1)
    _add_resource(conn, 2, library_id=2)

    lq = LibraryQuery(conn)
    before_changes = conn.total_changes
    before_flags = {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    }
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))

    for _ in range(3):
        lq.list()
        lq.list(include_disabled=False)
        lq.count()
        lq.get(1)
        lq.get(999999)

    assert conn.total_changes == before_changes, "LibraryQuery 不得写库"
    assert {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    } == before_flags
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta


def test_schema_version_unchanged() -> None:
    assert schema_mod.SCHEMA_VERSION == 2
    assert sorted(schema_mod.MIGRATIONS) == [1, 2]


# ---------------------------------------------------------------------------
# 真实样本（临时库，只读）
# ---------------------------------------------------------------------------


@pytest.fixture()
def real_db(tmp_path: Path, sample_root: Path):
    db_file = tmp_path / "samples.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    library = LibraryStore(connection).add(sample_root, name="真实样本")
    LibraryScanner(connection).scan(library.id)
    yield connection, library
    connection.close()


def test_real_sample_library_summary(real_db) -> None:
    conn, library = real_db
    lq = LibraryQuery(conn)
    rows = lq.list()

    assert lq.count() == 1
    assert len(rows) == 1
    summary = rows[0]
    assert summary.id == library.id
    assert summary.name == "真实样本"
    assert summary.root_path == library.root_path
    assert summary.enabled is True

    total = ResourceQuery(conn).count()
    assert total == 35
    assert summary.resource_count == total == 35
    assert summary.resource_count == ResourceQuery(conn).count(library_id=library.id)
    assert sum(r.resource_count for r in rows) == total


def test_real_sample_library_query_is_read_only(real_db) -> None:
    conn, library = real_db
    lq = LibraryQuery(conn)
    before_changes = conn.total_changes
    before_flags = conn.execute(
        "SELECT count(*) AS c FROM resources WHERE needs_review = 1"
    ).fetchone()["c"]
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))

    for _ in range(3):
        lq.list()
        lq.count()
        lq.get(library.id)
        lq.get(999999)

    assert conn.total_changes == before_changes
    assert before_flags == 0
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resources WHERE needs_review = 1"
        ).fetchone()["c"]
        == 0
    )
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta
