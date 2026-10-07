"""Phase 2.2 验收：Query Layer 的 byte-duplicate 只读派生查询。

覆盖
+++

- **分组**：不同路径、字节完全相同 ⇒ 恰好 1 组、2 成员；单例不成组。
- **反例**：同大小不同 bytes、跨格式（KKS/KK）同角色 ⇒ **不得**成组。
- **NULL**：``sha256 IS NULL`` 的资源被排除，不报错。
- **稳定**：组顺序（sha256 升序）与组内成员顺序（id 升序）确定；重复调用结果一致。
- **只读**：查询不产生 DB 写入；``duplicate_groups`` / ``duplicate_members`` 保持零写入；
  查询经 ``_execute_select`` 且只发 SELECT。
- **Schema 冻结**：``SCHEMA_VERSION == 2``、``MIGRATIONS == {1, 2}``。
- **真实样本（只读）**：恰好 1 组 byte-duplicate（Kugisaki Nobara 两文件）。

所有样本都在临时目录里构造；真实样本仅通过 ``sample_root`` 夹具只读使用。
"""

from __future__ import annotations

import dataclasses
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.query.queries as queries_module  # noqa: E402
from core.database import db as database  # noqa: E402
from core.database import schema  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.query import DuplicateGroup, ResourceQuery  # noqa: E402
from core.scanner import LibraryScanner  # noqa: E402
from tests import builders  # noqa: E402


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count(conn, table: str) -> int:
    return int(conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"])


def _member_paths(group: DuplicateGroup) -> set[str]:
    return {r.file_path for r in group.resources}


@pytest.fixture()
def env(tmp_path: Path):
    """一个干净的数据库 + 一个空的 Library 目录。"""
    db_file = tmp_path / "duplicate_query.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    root = tmp_path / "library"
    root.mkdir()
    library = LibraryStore(conn).add(root, name="duplicate-query")
    yield conn, root, library
    conn.close()


# ---------------------------------------------------------------------------
# 分组
# ---------------------------------------------------------------------------


def test_two_identical_files_form_one_group(env):
    """两个不同路径、bytes 完全相同 ⇒ 恰好 1 组、2 成员。"""
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    a = builders.write_card(root / "a.png", lastname="Same")
    b = builders.write_card(sub / "b.png", lastname="Same")
    assert a.read_bytes() == b.read_bytes(), "前提：两份文件字节完全相同"

    LibraryScanner(conn).scan(library.id)
    groups = ResourceQuery(conn).duplicates()

    assert len(groups) == 1
    group = groups[0]
    assert isinstance(group, DuplicateGroup)
    assert group.member_count == 2
    assert group.sha256 == _file_sha256(a)
    assert _member_paths(group) == {str(a), str(b)}


def test_singleton_not_returned(env):
    """单例资源不成组、不返回（最低成员数固定为 2）。"""
    conn, root, library = env
    builders.write_card(root / "only.png", lastname="Only")
    LibraryScanner(conn).scan(library.id)
    assert ResourceQuery(conn).duplicates() == []


def test_three_identical_files_form_single_group(env):
    """三个字节相同的文件 ⇒ 1 组、3 成员。"""
    conn, root, library = env
    for i in range(3):
        sub = root / f"d{i}"
        sub.mkdir()
        builders.write_card(sub / "same.png", lastname="Triple")
    LibraryScanner(conn).scan(library.id)
    groups = ResourceQuery(conn).duplicates()
    assert len(groups) == 1
    assert groups[0].member_count == 3


# ---------------------------------------------------------------------------
# 反例（不得成组）
# ---------------------------------------------------------------------------


def test_same_size_different_bytes_not_grouped(env):
    """同 file size 但 bytes 不同 ⇒ 不得成组。"""
    conn, root, library = env
    a = builders.write_card(root / "a.png", lastname="Alpha")
    b = builders.write_card(root / "b.png", lastname="Bravo")
    assert a.stat().st_size == b.stat().st_size, "前提：两份文件大小相同"
    assert _file_sha256(a) != _file_sha256(b), "前提：两份文件内容不同"

    LibraryScanner(conn).scan(library.id)
    assert ResourceQuery(conn).duplicates() == []


def test_cross_format_same_character_not_grouped(env):
    """跨格式（KKS / KK）逻辑上可能是同一角色 ⇒ 不因该事实产生 duplicate。"""
    conn, root, library = env
    kks = builders.write_card(
        root / "kks.png",
        lastname="Nobara",
        firstname="Kugisaki",
        marker=builders.MARKER_SUN,
    )
    kk = builders.write_card(
        root / "kk.png",
        lastname="Nobara",
        firstname="Kugisaki",
        marker=builders.MARKER_KK,
    )
    assert _file_sha256(kks) != _file_sha256(kk), "前提：两格式字节不同"

    LibraryScanner(conn).scan(library.id)
    assert ResourceQuery(conn).duplicates() == []


# ---------------------------------------------------------------------------
# NULL 处理
# ---------------------------------------------------------------------------


def test_null_sha256_excluded(env):
    """``sha256 IS NULL`` 的资源被排除，不参与分组、不报错。"""
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    a = builders.write_card(root / "a.png", lastname="Same")
    b = builders.write_card(sub / "b.png", lastname="Same")
    nulled = builders.write_card(root / "c.png", lastname="Unique")

    LibraryScanner(conn).scan(library.id)
    conn.execute(
        "UPDATE resources SET sha256 = NULL WHERE file_path_key = ?",
        (database.normalize_path_key(nulled),),
    )

    groups = ResourceQuery(conn).duplicates()
    assert len(groups) == 1
    assert _member_paths(groups[0]) == {str(a), str(b)}
    assert nulled not in {r.file_path for g in groups for r in g.resources}


# ---------------------------------------------------------------------------
# 确定性
# ---------------------------------------------------------------------------


def test_ordering_is_deterministic(env):
    """组按 sha256 升序、组内成员按 id 升序；重复调用结果一致。"""
    conn, root, library = env
    for tag, count in (("One", 2), ("Two", 2), ("Three", 3)):
        sub = root / tag
        sub.mkdir()
        for i in range(count):
            builders.write_card(sub / f"{tag}{i}.png", lastname=tag)

    LibraryScanner(conn).scan(library.id)
    first = ResourceQuery(conn).duplicates()
    second = ResourceQuery(conn).duplicates()

    assert first == second, "相同数据库状态下重复调用结果必须一致"
    assert sorted(g.member_count for g in first) == [2, 2, 3]
    assert len(first) == 3

    group_keys = [g.sha256 for g in first]
    assert group_keys == sorted(group_keys), "组顺序必须按 sha256 升序"
    for group in first:
        ids = [r.id for r in group.resources]
        assert ids == sorted(ids), "组内成员顺序必须按 id 升序"


def test_dto_is_immutable(env):
    """``DuplicateGroup`` 是 immutable / read-only。"""
    group = DuplicateGroup(sha256="0" * 64, resources=())
    with pytest.raises(dataclasses.FrozenInstanceError):
        group.sha256 = "f" * 64  # type: ignore[misc]
    assert group.member_count == 0


# ---------------------------------------------------------------------------
# 只读
# ---------------------------------------------------------------------------


def test_query_performs_no_db_writes(env):
    """查询不产生任何 DB 写入（``total_changes`` 不变）。"""
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    builders.write_card(root / "a.png", lastname="Same")
    builders.write_card(sub / "b.png", lastname="Same")
    LibraryScanner(conn).scan(library.id)

    before_changes = conn.total_changes
    before_resources = _count(conn, "resources")
    ResourceQuery(conn).duplicates()

    assert conn.total_changes == before_changes
    assert _count(conn, "resources") == before_resources


def test_duplicate_tables_remain_unwritten(env):
    """``duplicate_groups`` / ``duplicate_members`` 保持零写入。"""
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    builders.write_card(root / "a.png", lastname="Same")
    builders.write_card(sub / "b.png", lastname="Same")
    LibraryScanner(conn).scan(library.id)

    ResourceQuery(conn).duplicates()
    assert _count(conn, "duplicate_groups") == 0
    assert _count(conn, "duplicate_members") == 0


def test_duplicates_goes_through_read_only_guard(env, monkeypatch):
    """查询必须经 ``_execute_select``，且只发 SELECT / WITH。"""
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    builders.write_card(root / "a.png", lastname="Same")
    builders.write_card(sub / "b.png", lastname="Same")
    LibraryScanner(conn).scan(library.id)

    seen: list[str] = []
    real = queries_module._execute_select

    def spy(c, sql, params=()):
        seen.append(sql)
        return real(c, sql, params)

    monkeypatch.setattr(queries_module, "_execute_select", spy)
    ResourceQuery(conn).duplicates()

    assert seen, "duplicates() 必须经 _execute_select 执行"
    for sql in seen:
        keyword = sql.lstrip().split(None, 1)[0].lower()
        assert keyword in ("select", "with")


# ---------------------------------------------------------------------------
# Schema 冻结
# ---------------------------------------------------------------------------


def test_schema_version_frozen():
    assert schema.SCHEMA_VERSION == 2
    assert set(schema.MIGRATIONS) == {1, 2}
    assert schema.MIGRATION_ADDED_COLUMNS == {
        2: (("resources", "card_marker", "TEXT"),)
    }
    assert len(schema.CURRENT_TABLES) == 16


# ---------------------------------------------------------------------------
# 真实样本（只读）
# ---------------------------------------------------------------------------


def test_real_sample_byte_duplicate_query(sample_root: Path, tmp_path: Path):
    """真实样本：只读 duplicate 查询应恰好返回 1 组（Kugisaki Nobara 两文件）。"""
    db_file = tmp_path / "sample_duplicate.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        library = LibraryStore(conn).add(sample_root, name="samples")
        LibraryScanner(conn).scan(library.id)
        groups = ResourceQuery(conn).duplicates()
    finally:
        conn.close()

    assert len(groups) == 1, f"样本应恰有 1 组 byte-duplicate，实际 {len(groups)}"
    group = groups[0]
    assert group.member_count == 2
    assert all("Kugisaki" in (r.file_path or "") for r in group.resources), (
        "该组应为 Kugisaki Nobara 的两个字节相同文件"
    )

    # 直接对文件字节做 sha256，确认组内确实字节完全相同。
    digests = {_file_sha256(Path(r.file_path)) for r in group.resources}
    assert digests == {group.sha256}

    # 同大小不同内容（Higashiyama Kobeni）与跨格式（KKS vs KK）不得成组。
    grouped_paths = {r.file_path for g in groups for r in g.resources}
    assert not any("Higashiyama" in (p or "") for p in grouped_paths)
