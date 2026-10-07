"""Phase 1.1 验收：``LibraryStore`` —— 扫描根目录的增删改查。

验收目标（架构文档 §7 / Phase 1 步骤 1.1）：
- 能添加 / 删除 / 列出扫描根目录，并写进 ``libraries`` 表；
- 路径大小写不敏感（Windows），重复添加被拒；
- 删除只动数据库：资源保留但解除关联，扫描记录级联删除，**不碰文件**。

本套测试**不涉及目录遍历** —— 扫描是 Phase 1.2，本阶段刻意未实现。
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.library import (  # noqa: E402
    InvalidLibraryPath,
    LibraryAlreadyExists,
    LibraryError,
    LibraryNotFound,
    LibraryStore,
)


@pytest.fixture()
def db_file(tmp_path: Path) -> Path:
    path = tmp_path / "lib.db"
    database.initialize(path)
    return path


@pytest.fixture()
def conn(db_file: Path):
    connection = database.connect(db_file)
    yield connection
    connection.close()


@pytest.fixture()
def store(conn) -> LibraryStore:
    return LibraryStore(conn)


@pytest.fixture()
def cards_dir(tmp_path: Path) -> Path:
    path = tmp_path / "KKS Cards"
    path.mkdir()
    return path


# ---------------------------------------------------------------------------
# 添加
# ---------------------------------------------------------------------------


def test_add_creates_row_with_folder_name(store: LibraryStore, cards_dir: Path, conn):
    lib = store.add(cards_dir)

    assert lib.id is not None
    assert lib.name == "KKS Cards"          # 默认取文件夹名
    assert lib.enabled is True
    assert lib.last_scan_at is None

    row = conn.execute("SELECT * FROM libraries WHERE id = ?", (lib.id,)).fetchone()
    assert row["root_path"] == str(cards_dir)
    assert row["root_path_key"] == str(cards_dir).replace("\\", "/").casefold()
    assert row["enabled"] == 1


def test_add_accepts_custom_name_and_notes(store: LibraryStore, cards_dir: Path):
    lib = store.add(cards_dir, name="  主卡库  ", notes="  来自 D 盘  ")
    assert lib.name == "主卡库"
    assert lib.notes == "来自 D 盘"


def test_add_rejects_missing_directory(store: LibraryStore, tmp_path: Path):
    with pytest.raises(InvalidLibraryPath) as excinfo:
        store.add(tmp_path / "not-there")
    assert "目录不存在" in str(excinfo.value)


def test_add_allow_missing_skips_existence_check(store: LibraryStore, tmp_path: Path):
    lib = store.add(tmp_path / "offline-drive", allow_missing=True)
    assert lib.id is not None


def test_add_rejects_file_path(store: LibraryStore, tmp_path: Path):
    a_file = tmp_path / "card.png"
    a_file.write_bytes(b"not a card")
    with pytest.raises(InvalidLibraryPath) as excinfo:
        store.add(a_file)
    assert "不是一个目录" in str(excinfo.value)


def test_add_duplicate_path_is_rejected_case_insensitively(store: LibraryStore, cards_dir: Path):
    first = store.add(cards_dir)
    with pytest.raises(LibraryAlreadyExists) as excinfo:
        store.add(str(cards_dir).upper())
    assert excinfo.value.existing_id == first.id


def test_add_rejects_empty_path(store: LibraryStore):
    with pytest.raises(InvalidLibraryPath):
        store.add("   ")


def test_add_many_is_atomic(store: LibraryStore, tmp_path: Path, conn):
    good_a = tmp_path / "A"
    good_b = tmp_path / "B"
    good_a.mkdir()
    good_b.mkdir()

    added = store.add_many([good_a, good_b])
    assert [lib.name for lib in added] == ["A", "B"]
    assert conn.execute("SELECT count(*) AS c FROM libraries").fetchone()["c"] == 2

    # 第二阶段：混入一个坏路径 → 整批回滚，不留下「加了一半」
    with pytest.raises(InvalidLibraryPath):
        store.add_many([tmp_path / "C", tmp_path / "does-not-exist"])
    assert conn.execute("SELECT count(*) AS c FROM libraries").fetchone()["c"] == 2


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------


def test_find_by_path_normalizes_separators_and_case(store: LibraryStore, cards_dir: Path):
    lib = store.add(cards_dir)
    mixed = str(cards_dir).replace("\\", "/").casefold()
    assert store.find_by_path(mixed).id == lib.id
    assert store.find_by_path("D:/nowhere") is None


def test_resolve_accepts_id_path_and_digits(store: LibraryStore, cards_dir: Path):
    lib = store.add(cards_dir)
    assert store.resolve(str(lib.id)).id == lib.id
    assert store.resolve(lib.id).id == lib.id
    assert store.resolve(str(cards_dir)).id == lib.id
    with pytest.raises(LibraryNotFound):
        store.resolve("D:/nowhere")


def test_list_all_orders_and_can_hide_disabled(store: LibraryStore, tmp_path: Path):
    b_dir, a_dir = tmp_path / "B", tmp_path / "A"
    b_dir.mkdir()
    a_dir.mkdir()
    b = store.add(b_dir)
    a = store.add(a_dir)
    store.set_enabled(b.id, False)

    all_libs = store.list_all()
    assert [lib.name for lib in all_libs] == ["A", "B"]

    enabled_only = store.list_all(include_disabled=False)
    assert [lib.name for lib in enabled_only] == ["A"]
    assert enabled_only[0].id == a.id


# ---------------------------------------------------------------------------
# 更新
# ---------------------------------------------------------------------------


def test_update_changes_only_given_fields(store: LibraryStore, cards_dir: Path):
    lib = store.add(cards_dir, notes="旧备注")
    updated = store.update(lib.id, name="新名字")

    assert updated.name == "新名字"
    assert updated.notes == "旧备注"        # 未传的字段保持不变
    assert updated.root_path == lib.root_path


def test_update_rejects_empty_name(store: LibraryStore, cards_dir: Path):
    lib = store.add(cards_dir)
    with pytest.raises(LibraryError):
        store.update(lib.id, name="   ")


def test_update_without_changes_is_noop(store: LibraryStore, cards_dir: Path):
    lib = store.add(cards_dir)
    assert store.update(lib.id) == lib


def test_set_enabled_toggles(store: LibraryStore, cards_dir: Path):
    lib = store.add(cards_dir)
    assert store.set_enabled(lib.id, False).enabled is False
    assert store.require(lib.id).enabled is False
    assert store.set_enabled(lib.id, True).enabled is True


# ---------------------------------------------------------------------------
# 统计与删除
# ---------------------------------------------------------------------------


def _add_resource(conn, library_id: int, name: str, *, needs_review: int = 0,
                  scan_status: str = "present") -> int:
    cur = conn.execute(
        "INSERT INTO resources(file_path, file_path_key, resource_type, display_name,"
        " library_id, needs_review, scan_status) VALUES (?, ?, 'unknown', ?, ?, ?, ?)",
        (f"D:/lib/{name}.png", f"d:/lib/{name}.png", name, library_id, needs_review, scan_status),
    )
    return int(cur.lastrowid)


def test_stats_counts_resources(store: LibraryStore, conn, cards_dir: Path):
    lib = store.add(cards_dir)
    _add_resource(conn, lib.id, "a", needs_review=1)
    _add_resource(conn, lib.id, "b")
    _add_resource(conn, lib.id, "c", scan_status="missing")

    stats = store.stats(lib.id)
    assert stats.library_id == lib.id
    assert stats.resources == 3
    assert stats.needs_review == 1
    assert stats.missing == 1


def test_remove_keeps_files_and_resources_but_unlinks_them(
    store: LibraryStore, conn, db_file: Path, cards_dir: Path
):
    lib = store.add(cards_dir)
    resource_id = _add_resource(conn, lib.id, "card")
    conn.execute(
        "INSERT INTO scan_records(library_id, status) VALUES (?, 'completed')", (lib.id,)
    )

    report = store.remove(lib.id)

    assert report.library.id == lib.id
    assert report.resources_orphaned == 1
    assert report.scan_records_deleted == 1

    # Library 记录没了
    assert conn.execute("SELECT count(*) AS c FROM libraries").fetchone()["c"] == 0
    # 资源还在，只是解除关联
    row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
    assert row is not None
    assert row["library_id"] is None
    # 扫描记录级联删除
    assert conn.execute("SELECT count(*) AS c FROM scan_records").fetchone()["c"] == 0
    # 目录本身毫发无损
    assert cards_dir.is_dir()


def test_preview_removal_does_not_change_anything(store: LibraryStore, conn, cards_dir: Path):
    lib = store.add(cards_dir)
    _add_resource(conn, lib.id, "card")

    report = store.preview_removal(lib.id)
    assert report.resources_orphaned == 1
    assert conn.execute("SELECT count(*) AS c FROM libraries").fetchone()["c"] == 1


def test_remove_unknown_id_raises(store: LibraryStore):
    with pytest.raises(LibraryNotFound):
        store.remove(4242)


def test_require_unknown_id_raises(store: LibraryStore):
    with pytest.raises(LibraryNotFound):
        store.require(4242)


def test_store_never_deletes_files(store: LibraryStore, cards_dir: Path):
    """安全护栏：整个增删流程跑完，目录与文件依然存在。"""
    sample = cards_dir / "sample.png"
    sample.write_bytes(b"fake card")

    lib = store.add(cards_dir)
    store.update(lib.id, name="renamed")
    store.set_enabled(lib.id, False)
    store.remove(lib.id)

    assert sample.read_bytes() == b"fake card"
