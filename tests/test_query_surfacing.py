"""Phase 2.3-A 验收：Query / DTO Surfacing（``sha256`` + byte-duplicate 只读转发）。

覆盖
++++

- **DTO**：``ResourceSummary.sha256`` 默认 ``None``；提供值时正确保存；既有构造方式不变。
- **Query 映射**：``_RESOURCE_SUMMARY_COLUMNS`` 读取已有 ``resources.sha256``；
  ``None`` 值为 ``None``、非空值为正确字符串；不重算哈希。
- **duplicates() 语义不变**：既有 ``tests/test_duplicate_query.py`` 继续通过（本文件不改它）。
- **BrowseService**：``duplicates()`` / ``duplicate_group_for()`` 只读转发，
  结果与 ``ResourceQuery`` 一致；非重复 / 不存在返回 ``None``；不产生数据库写入。
- **不变量**：schema 冻结（v2 / 16 表 / 无 migration）；``duplicate_*`` 零写入；
  ``core/query`` 无写语句、不引用 ``quick_hash`` / ``content_key``。

所有合成样本都在临时目录里构造；不触碰真实样本。
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.query.browse as browse_module  # noqa: E402
import core.query.queries as queries_module  # noqa: E402
from core.database import db as database  # noqa: E402
from core.database import schema  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.query import (  # noqa: E402
    BrowseService,
    DuplicateGroup,
    ResourceQuery,
    ResourceSummary,
)
from core.scanner import LibraryScanner  # noqa: E402
from tests import builders  # noqa: E402


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count(conn, table: str) -> int:
    return int(conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"])


def _rid_by_path(conn, path: Path) -> int:
    row = conn.execute(
        "SELECT id FROM resources WHERE file_path_key = ?",
        (database.normalize_path_key(str(path)),),
    ).fetchone()
    assert row is not None, f"资源未入库：{path}"
    return int(row["id"])


@pytest.fixture()
def env(tmp_path: Path):
    """一个干净的数据库 + 一个空的 Library 目录。"""
    db_file = tmp_path / "surfacing.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    root = tmp_path / "library"
    root.mkdir()
    library = LibraryStore(conn).add(root, name="surfacing")
    yield conn, root, library
    conn.close()


def _summary_kwargs(**overrides) -> dict:
    """构造 ``ResourceSummary`` 的既有 14 个必填字段（不含新增的可选字段）。"""
    base = dict(
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
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


def test_resource_summary_sha256_defaults_to_none():
    """既有构造方式（不传 sha256）继续有效，且默认 ``None``。"""
    summary = ResourceSummary(**_summary_kwargs())
    assert summary.sha256 is None


def test_resource_summary_accepts_sha256():
    """提供 sha256 时正确保存；等于既有字段的只读派生值。"""
    digest = "a" * 64
    summary = ResourceSummary(**_summary_kwargs(), sha256=digest)
    assert summary.sha256 == digest


# ---------------------------------------------------------------------------
# Query 映射
# ---------------------------------------------------------------------------


def test_summary_carries_sha256_from_db(env):
    """从数据库读取资源时，``ResourceSummary.sha256`` 映射到真实文件哈希。"""
    conn, root, library = env
    card = builders.write_card(root / "card.png", lastname="Hash")
    LibraryScanner(conn).scan(library.id)

    summary = ResourceQuery(conn).summary(_rid_by_path(conn, card))
    assert summary is not None
    assert summary.sha256 == _file_sha256(card)


def test_list_carries_sha256(env):
    """``list()`` 返回的行同样携带 sha256（与文件字节一致）。"""
    conn, root, library = env
    card = builders.write_card(root / "card.png", lastname="Hash")
    LibraryScanner(conn).scan(library.id)

    rows = ResourceQuery(conn).list()
    assert len(rows) == 1
    assert rows[0].sha256 == _file_sha256(card)


def test_summary_sha256_is_none_when_null(env):
    """``sha256 IS NULL`` 的资源在 DTO 上是 ``None``（不报错、不推断）。"""
    conn, root, library = env
    card = builders.write_card(root / "card.png", lastname="Hash")
    LibraryScanner(conn).scan(library.id)
    rid = _rid_by_path(conn, card)
    conn.execute("UPDATE resources SET sha256 = NULL WHERE id = ?", (rid,))

    summary = ResourceQuery(conn).summary(rid)
    assert summary is not None
    assert summary.sha256 is None
    assert ResourceQuery(conn).list()[0].sha256 is None


# ---------------------------------------------------------------------------
# BrowseService（只读转发）
# ---------------------------------------------------------------------------


def test_browse_duplicates_forwards(env):
    """``BrowseService.duplicates()`` 转发结果与 ``ResourceQuery.duplicates()`` 一致。"""
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    builders.write_card(root / "a.png", lastname="Same")
    builders.write_card(sub / "b.png", lastname="Same")
    LibraryScanner(conn).scan(library.id)

    assert BrowseService(conn).duplicates() == ResourceQuery(conn).duplicates()


def test_browse_duplicate_group_for_hit(env):
    """``duplicate_group_for()`` 命中正确的 duplicate group。"""
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    a = builders.write_card(root / "a.png", lastname="Same")
    b = builders.write_card(sub / "b.png", lastname="Same")
    LibraryScanner(conn).scan(library.id)
    rid_a = _rid_by_path(conn, a)
    rid_b = _rid_by_path(conn, b)

    service = BrowseService(conn)
    group = service.duplicate_group_for(rid_a)
    assert isinstance(group, DuplicateGroup)
    assert group.member_count == 2
    assert group.sha256 == _file_sha256(a)
    assert {r.id for r in group.resources} == {rid_a, rid_b}
    # 组内成员按 id 升序（与 duplicates() 一致）
    assert [r.id for r in group.resources] == sorted([rid_a, rid_b])
    # 另一成员视角得到同一组
    assert service.duplicate_group_for(rid_b) == group


def test_browse_duplicate_group_for_non_duplicate_returns_none(env):
    """非重复资源（单例 / sha256 为空）返回 ``None``。"""
    conn, root, library = env
    unique = builders.write_card(root / "unique.png", lastname="Only")
    LibraryScanner(conn).scan(library.id)
    rid = _rid_by_path(conn, unique)

    service = BrowseService(conn)
    assert service.duplicate_group_for(rid) is None

    conn.execute("UPDATE resources SET sha256 = NULL WHERE id = ?", (rid,))
    assert service.duplicate_group_for(rid) is None


def test_browse_duplicate_group_for_missing_resource_returns_none(env):
    """不存在的资源 id ⇒ ``None``（不抛异常）。"""
    conn, root, library = env
    assert BrowseService(conn).duplicate_group_for(999999) is None
    assert ResourceQuery(conn).duplicate_group_for(999999) is None


def test_browse_duplicate_group_matches_duplicates_semantics(env):
    """单资源视图与 ``duplicates()`` 的分组语义一致（同一组、同 sha256）。"""
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    a = builders.write_card(root / "a.png", lastname="Same")
    builders.write_card(sub / "b.png", lastname="Same")
    builders.write_card(root / "u.png", lastname="Unique")
    LibraryScanner(conn).scan(library.id)

    service = BrowseService(conn)
    groups = service.duplicates()
    assert len(groups) == 1
    group = service.duplicate_group_for(_rid_by_path(conn, a))
    assert group is not None
    assert group.sha256 == groups[0].sha256
    assert {r.id for r in group.resources} == {r.id for r in groups[0].resources}


def test_browse_duplicates_performs_no_db_writes(env):
    """``duplicates()`` / ``duplicate_group_for()`` 均不产生数据库写入。"""
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    a = builders.write_card(root / "a.png", lastname="Same")
    builders.write_card(sub / "b.png", lastname="Same")
    LibraryScanner(conn).scan(library.id)
    rid = _rid_by_path(conn, a)

    before_changes = conn.total_changes
    before_resources = _count(conn, "resources")
    service = BrowseService(conn)
    service.duplicates()
    service.duplicate_group_for(rid)

    assert conn.total_changes == before_changes
    assert _count(conn, "resources") == before_resources
    assert _count(conn, "duplicate_groups") == 0
    assert _count(conn, "duplicate_members") == 0


def test_duplicate_group_for_goes_through_read_only_guard(env, monkeypatch):
    """新查询同样经 ``_execute_select``，只发 SELECT / WITH。"""
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    a = builders.write_card(root / "a.png", lastname="Same")
    builders.write_card(sub / "b.png", lastname="Same")
    LibraryScanner(conn).scan(library.id)
    rid = _rid_by_path(conn, a)

    seen: list[str] = []
    real = queries_module._execute_select

    def spy(c, sql, params=()):
        seen.append(sql)
        return real(c, sql, params)

    monkeypatch.setattr(queries_module, "_execute_select", spy)
    ResourceQuery(conn).duplicate_group_for(rid)

    assert seen, "duplicate_group_for() 必须经 _execute_select 执行"
    for sql in seen:
        keyword = sql.lstrip().split(None, 1)[0].lower()
        assert keyword in ("select", "with")


def test_browse_has_no_own_sql(monkeypatch):
    """架构约束：``BrowseService`` 只编排 / 转发 Query Layer，不自带 SQL。"""
    source = Path(browse_module.__file__).read_text(encoding="utf-8")
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b", source), (
        "BrowseService 不得自带 SQL"
    )
    assert "sqlite3" in source  # 仅用于类型注解，不直接 connect
    assert "connect(" not in source, "BrowseService 不得自建数据库连接"


# ---------------------------------------------------------------------------
# 不变量（schema 冻结 / 只读 / deprecated 字段不被引用）
# ---------------------------------------------------------------------------


def test_schema_frozen():
    assert schema.SCHEMA_VERSION == 2
    assert set(schema.MIGRATIONS) == {1, 2}
    assert schema.MIGRATION_ADDED_COLUMNS == {
        2: (("resources", "card_marker", "TEXT"),)
    }
    assert len(schema.CURRENT_TABLES) == 16


def test_query_layer_has_no_write_statements():
    """``core/query`` 内不得出现写语句（只读护栏只放行 SELECT / WITH）。"""
    for path in sorted(Path(queries_module.__file__).parent.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert not re.search(
            r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b", source
        ), f"{path.name} 含写语句关键字"


def test_query_layer_does_not_reference_deprecated_hash_fields():
    """``core/query`` 不得引用 ``quick_hash`` / ``content_key``（Phase 2 deprecated / unused）。"""
    for path in sorted(Path(queries_module.__file__).parent.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "quick_hash" not in source, f"{path.name} 引用了 quick_hash"
        assert "content_key" not in source, f"{path.name} 引用了 content_key"


def test_duplicate_tables_remain_unwritten(env):
    """``duplicate_groups`` / ``duplicate_members`` 在 surfacing 后仍零写入。"""
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    builders.write_card(root / "a.png", lastname="Same")
    builders.write_card(sub / "b.png", lastname="Same")
    LibraryScanner(conn).scan(library.id)
    BrowseService(conn).duplicates()

    assert _count(conn, "duplicate_groups") == 0
    assert _count(conn, "duplicate_members") == 0
