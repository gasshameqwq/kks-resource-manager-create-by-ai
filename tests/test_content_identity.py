"""Phase 2.1 验收：Content Identity（``resources.sha256``）。

覆盖
++++

- **Identity**：新资源 sha256 正确、64 位小写十六进制、相同字节同哈希、不同字节异哈希
- **Scanner**：新增计算、``(size, mtime)`` 变化重算、``mode='full'`` 重算、
  普通增量未变不读取 / 不计算
- **C7**：读取窗口内文件被改写 ⇒ 本次解析结果与 sha256 整体不提交，下次扫描重来
- **Schema**：``SCHEMA_VERSION == 2``、无 migration、表结构不变

所有样本都在临时目录里构造；真实样本仅通过 ``sample_root`` 夹具只读使用。
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.database import schema  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.scanner import LibraryScanner, sha256_of_file  # noqa: E402
from core.scanner import scanner as scanner_module  # noqa: E402
from tests.builders import write_card, write_zipmod  # noqa: E402

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _force_newer_mtime(path: Path, delta: float = 5.0) -> None:
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + delta))


def _row(conn, path: Path):
    return conn.execute(
        "SELECT sha256, file_size, modified_time FROM resources"
        " WHERE file_path_key = ?",
        (database.normalize_path_key(path),),
    ).fetchone()


def _sha_of(conn, path: Path) -> str | None:
    row = _row(conn, path)
    return None if row is None else row["sha256"]


@pytest.fixture()
def env(tmp_path: Path):
    """一个干净的数据库 + 一个空的 Library 目录。"""
    db_file = tmp_path / "content_identity.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    root = tmp_path / "library"
    root.mkdir()
    library = LibraryStore(conn).add(root, name="content-identity")
    yield conn, root, library
    conn.close()


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def test_sha256_of_file_matches_hashlib(tmp_path: Path):
    target = tmp_path / "x.bin"
    target.write_bytes(b"hello kks")
    assert sha256_of_file(target) == hashlib.sha256(b"hello kks").hexdigest()


def test_new_card_gets_correct_sha256(env):
    conn, root, library = env
    card = write_card(root / "a.png", lastname="A")
    LibraryScanner(conn).scan(library.id)
    assert _sha_of(conn, card) == _file_sha256(card)


def test_new_zipmod_gets_correct_sha256(env):
    conn, root, library = env
    mod = write_zipmod(root / "m.zipmod", guid="com.example.phase21")
    LibraryScanner(conn).scan(library.id)
    assert _sha_of(conn, mod) == _file_sha256(mod)


def test_sha256_is_lowercase_hex64(env):
    conn, root, library = env
    card = write_card(root / "a.png")
    LibraryScanner(conn).scan(library.id)
    value = _sha_of(conn, card)
    assert value is not None
    assert _HEX64.match(value) is not None, f"不是 64 位小写 hex：{value!r}"


def test_same_bytes_yield_same_sha256(env):
    conn, root, library = env
    sub = root / "sub"
    sub.mkdir()
    a = write_card(root / "a.png", lastname="Same")
    b = write_card(sub / "b.png", lastname="Same")
    assert a.read_bytes() == b.read_bytes(), "前提：两份文件字节完全相同"
    LibraryScanner(conn).scan(library.id)
    sha_a, sha_b = _sha_of(conn, a), _sha_of(conn, b)
    assert sha_a is not None and sha_a == sha_b


def test_different_bytes_yield_different_sha256(env):
    conn, root, library = env
    a = write_card(root / "a.png", lastname="Alpha")
    b = write_card(root / "b.png", lastname="Beta")
    LibraryScanner(conn).scan(library.id)
    assert _sha_of(conn, a) != _sha_of(conn, b)


# ---------------------------------------------------------------------------
# Scanner：计算时机
# ---------------------------------------------------------------------------


def test_changed_content_recomputes_sha256(env):
    conn, root, library = env
    card = write_card(root / "a.png", lastname="Before")
    LibraryScanner(conn).scan(library.id)
    first = _sha_of(conn, card)

    write_card(root / "a.png", lastname="AfterLonger")
    _force_newer_mtime(card)

    LibraryScanner(conn).scan(library.id)
    second = _sha_of(conn, card)
    assert second == _file_sha256(card)
    assert second != first


def test_full_scan_recomputes_sha256(env, monkeypatch):
    conn, root, library = env
    write_card(root / "a.png")
    LibraryScanner(conn).scan(library.id)

    calls = {"n": 0}
    real = scanner_module.sha256_of_file

    def counting(path, **kwargs):
        calls["n"] += 1
        return real(path, **kwargs)

    monkeypatch.setattr(scanner_module, "sha256_of_file", counting)
    LibraryScanner(conn).scan(library.id, mode="full")
    assert calls["n"] == 1, "full 扫描必须重新计算 sha256"


def test_unchanged_incremental_does_not_read_or_hash(env, monkeypatch):
    conn, root, library = env
    write_card(root / "a.png")
    LibraryScanner(conn).scan(library.id)

    def forbidden(path, **kwargs):  # pragma: no cover - 不应被调用
        raise AssertionError("未变化的增量扫描不得读取 / 计算 sha256")

    monkeypatch.setattr(scanner_module, "sha256_of_file", forbidden)
    result = LibraryScanner(conn).scan(library.id)
    assert result.stats.skipped == 1


# ---------------------------------------------------------------------------
# C7：读取一致性（解释 ii）
# ---------------------------------------------------------------------------


def test_c7_unstable_read_new_file_not_committed(env, monkeypatch):
    """新文件在读取窗口内被改写 → 本次整体不提交，下次扫描重来。"""
    conn, root, library = env
    card = write_card(root / "a.png", lastname="A")
    real = scanner_module.sha256_of_file

    def mutating(path, **kwargs):
        # 模拟读取窗口内被外部程序改写：先改文件，再返回哈希
        with open(path, "ab") as fh:
            fh.write(b"\x00phase21-extra")
        return real(path, **kwargs)

    monkeypatch.setattr(scanner_module, "sha256_of_file", mutating)
    result = LibraryScanner(conn).scan(library.id)

    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 0
    assert result.stats.failed == 0, "C7 不是失败"
    assert result.issues == [], "C7 不产生 ScanIssue"

    monkeypatch.setattr(scanner_module, "sha256_of_file", real)
    LibraryScanner(conn).scan(library.id)
    assert _sha_of(conn, card) == _file_sha256(card)


def test_c7_unstable_read_keeps_existing_row(env, monkeypatch):
    """既有文件在读取窗口内被改写 → 数据库保持原状态（不覆盖）。"""
    conn, root, library = env
    card = write_card(root / "a.png", lastname="Before")
    LibraryScanner(conn).scan(library.id)
    before = _row(conn, card)

    write_card(root / "a.png", lastname="AfterLonger")
    _force_newer_mtime(card)

    real = scanner_module.sha256_of_file

    def mutating(path, **kwargs):
        with open(path, "ab") as fh:
            fh.write(b"\x00phase21-extra")
        return real(path, **kwargs)

    monkeypatch.setattr(scanner_module, "sha256_of_file", mutating)
    result = LibraryScanner(conn).scan(library.id)

    after = _row(conn, card)
    assert after["sha256"] == before["sha256"]
    assert after["file_size"] == before["file_size"]
    assert after["modified_time"] == before["modified_time"]
    assert result.stats.failed == 0


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


def test_resources_columns_unchanged(env):
    conn, root, library = env
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(resources)")}
    assert {"sha256", "quick_hash", "content_key"} <= columns


# ---------------------------------------------------------------------------
# 真实样本（只读）
# ---------------------------------------------------------------------------


def test_real_sample_sha256_matches_bytes(sample_root, tmp_path: Path):
    db_file = tmp_path / "sample_identity.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        library = LibraryStore(conn).add(sample_root, name="samples")
        LibraryScanner(conn).scan(library.id)
        rows = conn.execute(
            "SELECT file_path, sha256 FROM resources WHERE sha256 IS NOT NULL"
        ).fetchall()
        assert rows, "样本扫描应至少写出一条 sha256"
        for row in rows:
            assert row["sha256"] == _file_sha256(Path(row["file_path"]))
    finally:
        conn.close()
