"""Phase 1.3-C-2：Review Reason 只读推导测试。

``review_reasons`` 完全由既有列（``parse_status`` / ``name`` / ``resource_type`` /
``resource_mod_usages.property``）推导，**不写库、不修改 ``needs_review``**。
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.database import schema as schema_mod  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.query import (  # noqa: E402
    REVIEW_REASON_CODES,
    REVIEW_REASON_MISSING_NAME,
    REVIEW_REASON_PARSE_FAILED,
    REVIEW_REASON_PARSE_PARTIAL,
    REVIEW_REASON_UNKNOWN_PROPERTY,
    REVIEW_REASON_UNKNOWN_TYPE,
    ResourceQuery,
)
from core.scanner import LibraryScanner  # noqa: E402


def _add_resource(
    conn,
    resource_id: int,
    *,
    name: str | None,
    resource_type: str = "character_card",
    parse_status: str = "ok",
    parse_error: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO resources(id, resource_type, name, file_path, file_path_key,"
        " parse_status, parse_error)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            resource_id,
            resource_type,
            name,
            f"D:/lib/{resource_id}.png",
            f"d:/lib/{resource_id}.png",
            parse_status,
            parse_error,
        ),
    )


def _add_usage(conn, resource_id: int, mod_guid: str, prop: str) -> None:
    conn.execute(
        "INSERT INTO resource_mod_usages(resource_id, mod_guid, property, slot,"
        " local_slot, category_no) VALUES (?, ?, ?, 0, 0, 0)",
        (resource_id, mod_guid, prop),
    )


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "review.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    yield connection
    connection.close()


def _codes(reasons) -> list[str]:
    return [r.code for r in reasons]


# ---------------------------------------------------------------------------
# 单独 reason
# ---------------------------------------------------------------------------


def test_clean_resource_has_no_reason(conn) -> None:
    _add_resource(conn, 1, name="Good")
    _add_usage(conn, 1, "m", "ChaFileFace.Pupil1")
    assert ResourceQuery(conn).review_reasons(1) == ()


def test_parse_failed_reason(conn) -> None:
    _add_resource(conn, 1, name="X", parse_status="failed", parse_error="broken header")
    reasons = ResourceQuery(conn).review_reasons(1)
    assert _codes(reasons) == [REVIEW_REASON_PARSE_FAILED]
    assert reasons[0].detail == "broken header"
    assert reasons[0].label  # 有可读 label


def test_parse_partial_reason(conn) -> None:
    _add_resource(conn, 1, name="X", parse_status="partial", parse_error="2 warnings")
    reasons = ResourceQuery(conn).review_reasons(1)
    assert _codes(reasons) == [REVIEW_REASON_PARSE_PARTIAL]
    assert reasons[0].detail == "2 warnings"


def test_missing_name_reason(conn) -> None:
    _add_resource(conn, 1, name="")
    _add_resource(conn, 2, name=None)
    assert _codes(ResourceQuery(conn).review_reasons(1)) == [REVIEW_REASON_MISSING_NAME]
    assert _codes(ResourceQuery(conn).review_reasons(2)) == [REVIEW_REASON_MISSING_NAME]


def test_unknown_type_reason(conn) -> None:
    _add_resource(conn, 1, name="X", resource_type="unknown")
    assert _codes(ResourceQuery(conn).review_reasons(1)) == [REVIEW_REASON_UNKNOWN_TYPE]


def test_unknown_property_reason(conn) -> None:
    _add_resource(conn, 1, name="X")
    _add_usage(conn, 1, "m1", "Totally.Different")
    _add_usage(conn, 1, "m2", "ChaFileFace.Pupil1")  # 已知 property 不应触发
    reasons = ResourceQuery(conn).review_reasons(1)
    assert _codes(reasons) == [REVIEW_REASON_UNKNOWN_PROPERTY]
    assert reasons[0].detail == "Totally.Different"


def test_unknown_properties_are_deduped_and_sorted(conn) -> None:
    _add_resource(conn, 1, name="X")
    _add_usage(conn, 1, "m1", "Zzz.Unknown")
    _add_usage(conn, 1, "m2", "Aaa.Unknown")
    _add_usage(conn, 1, "m3", "Zzz.Unknown")  # 重复
    reasons = ResourceQuery(conn).review_reasons(1)
    assert reasons[0].detail == "Aaa.Unknown, Zzz.Unknown"


# ---------------------------------------------------------------------------
# 组合 / 顺序 / 边界
# ---------------------------------------------------------------------------


def test_multiple_reasons_follow_stable_order(conn) -> None:
    _add_resource(
        conn, 1, name="", resource_type="unknown", parse_status="failed", parse_error="boom"
    )
    _add_usage(conn, 1, "m1", "Totally.Different")
    assert _codes(ResourceQuery(conn).review_reasons(1)) == [
        REVIEW_REASON_PARSE_FAILED,
        REVIEW_REASON_MISSING_NAME,
        REVIEW_REASON_UNKNOWN_TYPE,
        REVIEW_REASON_UNKNOWN_PROPERTY,
    ]
    # 顺序与公开的稳定 code 顺序一致
    assert list(REVIEW_REASON_CODES) == [
        "parse_failed",
        "parse_partial",
        "missing_name",
        "unknown_type",
        "unknown_property",
    ]


def test_nonexistent_resource_has_no_reason(conn) -> None:
    assert ResourceQuery(conn).review_reasons(999999) == ()


# ---------------------------------------------------------------------------
# 只读不变量
# ---------------------------------------------------------------------------


def test_review_reasons_do_not_write_database(conn) -> None:
    _add_resource(conn, 1, name="", parse_status="partial")
    _add_usage(conn, 1, "m1", "Totally.Different")
    before_changes = conn.total_changes
    before_flags = {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    }

    reasons = ResourceQuery(conn).review_reasons(1)
    assert reasons  # 有理由

    assert conn.total_changes == before_changes, "review_reasons 不得写库"
    after_flags = {
        r["id"]: r["needs_review"] for r in conn.execute("SELECT id, needs_review FROM resources")
    }
    assert after_flags == before_flags, "review_reasons 不得修改 needs_review"


def test_schema_unchanged() -> None:
    assert schema_mod.SCHEMA_VERSION == 2
    assert sorted(schema_mod.MIGRATIONS) == [1, 2]


# ---------------------------------------------------------------------------
# 真实样本：干净数据 → 无任何 reason
# ---------------------------------------------------------------------------


def test_real_sample_has_no_review_reasons(tmp_path: Path, sample_root: Path) -> None:
    db_file = tmp_path / "samples.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        library = LibraryStore(conn).add(sample_root, name="真实样本")
        LibraryScanner(conn).scan(library.id)

        rq = ResourceQuery(conn)
        all_ids = [r.id for r in rq.list()]
        assert len(all_ids) == 35
        assert all(rq.review_reasons(rid) == () for rid in all_ids)

        flagged = conn.execute(
            "SELECT count(*) AS c FROM resources WHERE needs_review = 1"
        ).fetchone()["c"]
        assert flagged == 0
    finally:
        conn.close()


def test_real_sample_database_unchanged_by_review_reasons(
    tmp_path: Path, sample_root: Path
) -> None:
    db_file = tmp_path / "samples.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        library = LibraryStore(conn).add(sample_root, name="真实样本")
        LibraryScanner(conn).scan(library.id)
        ids = [r.id for r in ResourceQuery(conn).list()]
    finally:
        conn.close()

    before = hashlib.sha256(db_file.read_bytes()).hexdigest()
    conn = database.connect(db_file)
    try:
        for rid in ids:
            ResourceQuery(conn).review_reasons(rid)
    finally:
        conn.close()
    after = hashlib.sha256(db_file.read_bytes()).hexdigest()
    assert before == after
