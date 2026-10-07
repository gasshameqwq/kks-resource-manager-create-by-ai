"""Phase 1.1 / P1 修复① 验收：写入事务 ``db.transaction``。

背景：``connect()`` 默认是 autocommit（``isolation_level=None``），单条 DDL / 单条 UI
操作最省心，但批量写入会逐行落盘。Phase 1.2 的扫描器一次可能插入数千行，
**必须**把批量写入包进显式事务。这里先把该能力的语义测死：

- 正常结束 → 提交；
- 抛异常 → 整体回滚；
- 嵌套调用 → 复用外层事务，不提前提交；
- 未提交的数据对其他连接不可见（证明事务真的开着）；
- 批量插入确实比 autocommit 快（性能回归冒烟）。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402


@pytest.fixture()
def db_file(tmp_path: Path) -> Path:
    path = tmp_path / "tx.db"
    database.initialize(path)
    return path


@pytest.fixture()
def conn(db_file: Path):
    connection = database.connect(db_file)
    yield connection
    connection.close()


def _count_libraries(conn) -> int:
    return conn.execute("SELECT count(*) AS c FROM libraries").fetchone()["c"]


def _add_library(conn, name: str) -> None:
    conn.execute(
        "INSERT INTO libraries(name, root_path, root_path_key) VALUES (?, ?, ?)",
        (name, f"D:/{name}", f"d:/{name.lower()}"),
    )


def test_transaction_commits_on_success(conn, db_file: Path):
    with database.transaction(conn):
        _add_library(conn, "A")
        _add_library(conn, "B")
        assert conn.in_transaction is True

    assert conn.in_transaction is False
    assert _count_libraries(conn) == 2

    other = database.connect(db_file)
    try:
        assert _count_libraries(other) == 2
    finally:
        other.close()


def test_transaction_rolls_back_on_exception(conn):
    with pytest.raises(RuntimeError, match="boom"):
        with database.transaction(conn):
            _add_library(conn, "A")
            _add_library(conn, "B")
            raise RuntimeError("boom")

    assert conn.in_transaction is False
    assert _count_libraries(conn) == 0


def test_nested_transaction_reuses_outer_and_does_not_commit_early(conn, db_file: Path):
    with database.transaction(conn):
        _add_library(conn, "A")
        with database.transaction(conn):  # 内层
            _add_library(conn, "B")
            assert conn.in_transaction is True

        # 内层结束后外层事务仍在进行 → 另一个连接应当看不到任何一行
        other = database.connect(db_file)
        try:
            assert _count_libraries(other) == 0
        finally:
            other.close()

    assert _count_libraries(conn) == 2


def test_outer_rollback_discards_nested_writes(conn):
    with pytest.raises(RuntimeError):
        with database.transaction(conn):
            _add_library(conn, "A")
            with database.transaction(conn):
                _add_library(conn, "B")
            raise RuntimeError("外层失败")

    assert _count_libraries(conn) == 0


def test_uncommitted_rows_invisible_to_other_connection(conn, db_file: Path):
    other = database.connect(db_file)
    try:
        with database.transaction(conn):
            _add_library(conn, "A")
            assert _count_libraries(conn) == 1
            assert _count_libraries(other) == 0
        assert _count_libraries(other) == 1
    finally:
        other.close()


def test_outside_transaction_writes_are_autocommit(conn, db_file: Path):
    """不显式开事务时保持原有 autocommit 行为（单条 UI 操作依赖它）。"""
    _add_library(conn, "A")
    assert conn.in_transaction is False

    other = database.connect(db_file)
    try:
        assert _count_libraries(other) == 1
    finally:
        other.close()


def test_batched_insert_is_faster_than_autocommit(conn, db_file: Path):
    """性能冒烟：一条事务插入 N 行应当显著快于逐行 autocommit。

    阈值取得很宽松（至少快 1.7 倍），只用来拦住「事务被误删、退回逐行提交」这种回归，
    不追求精确计时。实测参考：800 行 autocommit ≈ 98 ms，事务内 ≈ 21 ms（约 4.7 倍）。
    """
    rows = [(f"D:/bulk/{i}.png", f"d:/bulk/{i}.png") for i in range(800)]
    insert = "INSERT INTO resources(file_path, file_path_key) VALUES (?, ?)"

    start = time.perf_counter()
    for row in rows:
        conn.execute(insert, row)
    autocommit_time = time.perf_counter() - start

    conn.execute("DELETE FROM resources")
    old_ids = {r["id"] for r in conn.execute("SELECT id FROM resources").fetchall()}
    assert old_ids == set()

    start = time.perf_counter()
    with database.transaction(conn):
        for row in rows:
            conn.execute(insert, row)
    batched_time = time.perf_counter() - start

    assert _count_resources(conn) == len(rows)
    assert batched_time < autocommit_time * 0.6, (
        f"批量事务未体现出优势：batched={batched_time:.4f}s "
        f"autocommit={autocommit_time:.4f}s"
    )


def _count_resources(conn) -> int:
    return conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"]
