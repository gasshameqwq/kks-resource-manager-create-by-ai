"""Phase 1.1 / P1 修复② 验收：FTS 存量回填只在真正执行迁移时发生。

背景：``initialize()`` 原本在 ``fts_enabled`` 为真时**无条件**调用 ``_backfill_fts``。
该函数要跑 ``WHERE r.id NOT IN (SELECT rowid FROM resources_fts)`` 的全量比对，
而绝大多数启动都不会执行任何迁移 —— 于是每次启动都白扫一遍 resources。

修复后：只有 ``applied``（本次实际应用的迁移列表）非空时才回填。
新库首建、老库升级到启用 FTS 的版本仍然会回填，时机一个没少。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.database import schema as schema_mod  # noqa: E402


@pytest.fixture()
def db_file(tmp_path: Path) -> Path:
    return tmp_path / "backfill.db"


@pytest.fixture()
def backfill_spy(monkeypatch):
    """把 ``_backfill_fts`` 换成计数器，返回调用列表。"""
    calls: list[int] = []

    def spy(conn) -> None:  # noqa: ANN001 - 仅用于记录调用
        calls.append(1)

    monkeypatch.setattr(database, "_backfill_fts", spy)
    return calls


def test_backfill_runs_on_first_initialize(db_file: Path, backfill_spy):
    """新库首建：执行了迁移 → 应当回填（且只回填一次）。"""
    info = database.initialize(db_file)
    if not info["fts_enabled"]:
        pytest.skip("当前 SQLite 构建未启用 FTS5/trigram")
    assert info["applied_migrations"] == sorted(schema_mod.MIGRATIONS)
    assert len(backfill_spy) == 1


def test_backfill_skipped_when_nothing_applied(db_file: Path, backfill_spy):
    """最常见的启动路径：没有任何迁移 → 不应回填。"""
    database.initialize(db_file)  # 第一次建库（此时会回填）
    calls_after_first = len(backfill_spy)

    info = database.initialize(db_file)  # 第二次：无迁移
    assert info["applied_migrations"] == []
    assert len(backfill_spy) == calls_after_first, "无迁移时不应再触碰 FTS 回填"


def test_backfill_skipped_when_fts_disabled(db_file: Path, monkeypatch, backfill_spy):
    """FTS 不可用时（回退 LIKE）不应尝试回填。"""
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        conn.execute(
            "INSERT INTO app_meta(key, value) VALUES ('fts_enabled', '0') "
            "ON CONFLICT(key) DO UPDATE SET value = '0'"
        )
    finally:
        conn.close()

    before = len(backfill_spy)
    info = database.initialize(db_file)
    assert info["fts_enabled"] is False
    assert len(backfill_spy) == before


def test_backfill_runs_after_new_migration_on_existing_db(db_file: Path, monkeypatch, backfill_spy):
    """老库升级：只要本次跑了新迁移，就应当重新回填一次。"""
    database.initialize(db_file)  # 建到 v1
    before = len(backfill_spy)

    # 用 99 号假迁移，避免与真实存在的 v2 冲突
    probe_ddl = "CREATE TABLE IF NOT EXISTS _phase1_probe(x INTEGER);"
    monkeypatch.setitem(schema_mod.MIGRATIONS, 99, (probe_ddl, ""))

    info = database.initialize(db_file)
    assert info["applied_migrations"] == [99]
    assert info["schema_version"] == 99
    if info["fts_enabled"]:
        assert len(backfill_spy) == before + 1


def test_resources_inserted_by_trigger_do_not_need_backfill(db_file: Path):
    """回归护栏：不靠回填，FTS 触发器本身就要保证新行可被搜到。"""
    info = database.initialize(db_file)
    if not info["fts_enabled"]:
        pytest.skip("当前 SQLite 构建未启用 FTS5/trigram")

    conn = database.connect(db_file)
    try:
        conn.execute(
            "INSERT INTO resources(file_path, file_path_key, resource_type,"
            " display_name, name) VALUES ('D:/n.png','d:/n.png','character_card',"
            " '一乃 测试', '一乃测试')"
        )
        hit = conn.execute(
            "SELECT r.id FROM resources_fts f JOIN resources r ON r.id = f.rowid"
            " WHERE resources_fts MATCH ?",
            ("一乃测",),
        ).fetchall()
        assert len(hit) == 1

        # 再走一次 initialize（无迁移）后，索引仍然完好
        database.initialize(db_file)
        hit = conn.execute(
            "SELECT r.id FROM resources_fts f JOIN resources r ON r.id = f.rowid"
            " WHERE resources_fts MATCH ?",
            ("乃测试",),
        ).fetchall()
        assert len(hit) == 1
    finally:
        conn.close()
