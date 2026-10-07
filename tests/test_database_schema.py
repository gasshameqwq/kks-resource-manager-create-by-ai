"""Phase 0 验收测试：SQLite schema 可建成、结构完整、约束生效。

这些测试不依赖 PyQt6，可在无 UI 环境下运行：

    python -m pytest tests/test_database_schema.py -q
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.database import schema as schema_mod  # noqa: E402


@pytest.fixture()
def db_file(tmp_path: Path) -> Path:
    return tmp_path / "test_kks_rm.db"


def test_initialize_creates_all_tables(db_file: Path):
    info = database.initialize(db_file)
    assert info["schema_version"] == schema_mod.SCHEMA_VERSION
    for table in schema_mod.V1_TABLES:
        assert table in info["tables"], f"缺少数据表：{table}"


def test_initialize_is_idempotent(db_file: Path):
    first = database.initialize(db_file)
    second = database.initialize(db_file)
    assert first["schema_version"] == second["schema_version"]
    assert second["applied_migrations"] == []


def test_foreign_keys_enforced(db_file: Path):
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO resource_tags(resource_id, tag_id) VALUES (99999, 99999)"
            )
    finally:
        conn.close()


def test_resource_type_check_constraint(db_file: Path):
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO resources(file_path, file_path_key, resource_type) "
                "VALUES ('D:/x.png', 'd:/x.png', 'not_a_real_type')"
            )
    finally:
        conn.close()


def test_file_path_key_is_unique(db_file: Path):
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        conn.execute(
            "INSERT INTO resources(file_path, file_path_key) VALUES ('D:/a.png', 'd:/a.png')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO resources(file_path, file_path_key) "
                "VALUES ('D:/A.PNG', 'd:/a.png')"
            )
    finally:
        conn.close()


def test_mod_dependency_allows_missing_mod(db_file: Path):
    """关键设计：依赖用 mod_guid 做主键，未安装的 MOD 也能记录。"""
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        cur = conn.execute(
            "INSERT INTO resources(file_path, file_path_key, resource_type) "
            "VALUES ('D:/card.png', 'd:/card.png', 'character_card')"
        )
        rid = cur.lastrowid
        conn.execute(
            "INSERT INTO resource_mods(resource_id, mod_guid, mod_id) VALUES (?, ?, NULL)",
            (rid, "com.example.not-installed"),
        )
        row = conn.execute(
            "SELECT mod_guid, mod_id FROM resource_mods WHERE resource_id = ?", (rid,)
        ).fetchone()
        assert row["mod_guid"] == "com.example.not-installed"
        assert row["mod_id"] is None
    finally:
        conn.close()


def test_normalize_path_key_windows_case_insensitive():
    a = database.normalize_path_key("D:/KKS/Cards/A.png")
    b = database.normalize_path_key(r"D:\KKS\cards\a.png")
    assert a == b
    assert a == "d:/kks/cards/a.png"


def test_normalize_name_key():
    assert database.normalize_name_key("  Favorite ") == "favorite"
    assert database.normalize_name_key("作者A") == "作者a"


def test_fts_search_works_when_enabled(db_file: Path):
    info = database.initialize(db_file)
    if not info["fts_enabled"]:
        pytest.skip("当前 SQLite 构建未启用 FTS5/trigram，已按设计回退 LIKE 搜索")
    conn = database.connect(db_file)
    try:
        conn.execute(
            "INSERT INTO resources(file_path, file_path_key, resource_type, display_name, name) "
            "VALUES ('D:/c.png', 'd:/c.png', 'character_card', '白峰 一乃', '白峰一乃')"
        )
        # 注意：FTS5 trigram 只索引长度 >= 3 的子串。
        # 1~2 字查询（如「一乃」）必须走 LIKE 回退，见 core/search 的检索策略。
        hit = conn.execute(
            "SELECT r.display_name FROM resources_fts f "
            "JOIN resources r ON r.id = f.rowid WHERE resources_fts MATCH ?",
            ("白峰一",),
        ).fetchall()
        assert len(hit) == 1

        short = conn.execute(
            "SELECT display_name FROM resources WHERE display_name LIKE ?",
            ("%一乃%",),
        ).fetchall()
        assert len(short) == 1
    finally:
        conn.close()
