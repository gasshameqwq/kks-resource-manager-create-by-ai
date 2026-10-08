"""Phase 3.1 Step 2/3 —— ownership 静态护栏 + Scanner SQL 运行时护栏。

依据：`docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md` §5 / §7 / §8（Invariant F）。

两条独立证据：
1. **静态**：只有 allowlist 中的模块对 ``resources`` 执行 INSERT / UPDATE；
   UI / CLI 不得自己连数据库。
2. **运行时**：真实扫描（INSERT + UPDATE 两条路径）实际执行的 SQL 里，
   对 ``resources`` 的写入**不含** user-owned columns（``display_name`` / ``notes`` /
   ``type_source='user'``）。Scanner 仍可写机器初始化值 ``type_source = 'auto'``。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.database import db as database
from core.library import LibraryStore
from core.scanner import LibraryScanner
from tests.builders import write_card, write_zipmod

REPO = Path(__file__).resolve().parent.parent

#: 唯一允许对 `resources` 执行 INSERT / UPDATE 的模块。
ALLOWED_RESOURCE_WRITERS = {
    "core/scanner/store.py",      # machine writer
    "core/app/resource_write.py",  # user writer（Phase 3.1 唯一用户写入口）
}

#: Phase 3.2：唯一允许对 `tags` / `resource_tags` 执行 INSERT / UPDATE / DELETE 的模块。
ALLOWED_TAG_WRITERS = {
    "core/app/tag_write.py",      # Tag 域唯一 runtime writer
}

#: 精确匹配「对 resources 表的写入」，不会误伤 `resources_fts`。
#: 接受 `INSERT [OR ...] INTO` 形式（收紧既有护栏）。
_RESOURCE_WRITE_RE = re.compile(
    r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+resources\s*\(|UPDATE\s+resources\s+SET\b",
    re.IGNORECASE,
)

#: 匹配「对 tags / resource_tags 表的写入」（含 `INSERT OR IGNORE` 形式）。
_TAG_WRITE_RE = re.compile(
    r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+(?:tags|resource_tags)\s*\("
    r"|UPDATE\s+(?:tags|resource_tags)\s+SET\b"
    r"|DELETE\s+FROM\s+(?:tags|resource_tags)\b",
    re.IGNORECASE,
)


def _scanned_sources() -> list[Path]:
    paths: list[Path] = []
    for folder in ("core", "ui"):
        paths.extend(sorted((REPO / folder).rglob("*.py")))
    paths.extend([REPO / "main.py", REPO / "cli_query.py"])
    return paths


# ---------------------------------------------------------------------------
# 静态护栏
# ---------------------------------------------------------------------------


def test_only_allowlisted_modules_write_resources():
    offenders: list[str] = []
    for path in _scanned_sources():
        if _RESOURCE_WRITE_RE.search(path.read_text(encoding="utf-8")):
            relative = path.relative_to(REPO).as_posix()
            if relative not in ALLOWED_RESOURCE_WRITERS:
                offenders.append(relative)
    assert offenders == [], (
        "只有 machine writer 与 user writer 可以写 resources，违规文件：" + ", ".join(offenders)
    )


def test_ui_and_cli_do_not_import_sqlite3():
    for path in _scanned_sources():
        if path.parent.name not in {"ui"} and path.name not in {"main.py", "cli_query.py"}:
            continue
        import_lines = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        assert not any("sqlite3" in line for line in import_lines), (
            f"{path.relative_to(REPO).as_posix()} 不得自己连数据库"
        )


# ---------------------------------------------------------------------------
# 运行时护栏：Scanner 执行的 SQL 不写 user-owned columns
# ---------------------------------------------------------------------------


@pytest.fixture()
def scan_env(tmp_path: Path):
    db_file = tmp_path / "ownership.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    root = tmp_path / "library"
    root.mkdir()
    library = LibraryStore(conn).add(root, name="ownership")
    try:
        yield conn, root, library
    finally:
        conn.close()


def test_scanner_executed_sql_never_writes_user_columns(scan_env):
    """Scanner 走完 INSERT 与 UPDATE 两条路径后，SQL 层面不得触碰用户列。"""
    conn, root, library = scan_env
    card = write_card(root / "card.png", lastname="Alice", firstname="Card")
    write_zipmod(root / "mod.zipmod", "com.example.x")
    scanner = LibraryScanner(conn)

    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        scanner.scan(library.id)                                  # INSERT 路径
        write_card(card, lastname="Renamed", firstname="Character")
        scanner.scan(library.id)                                  # UPDATE 路径
    finally:
        conn.set_trace_callback(None)

    resources_writes = [sql for sql in statements if _RESOURCE_WRITE_RE.match(sql)]
    assert resources_writes, "测试必须先产生对 resources 的 INSERT / UPDATE"

    for sql in resources_writes:
        lowered = sql.lower()
        assert "display_name" not in lowered, f"Scanner 写了 display_name：{sql}"
        assert "notes" not in lowered, f"Scanner 写了 notes：{sql}"
        assert "'user'" not in lowered, f"Scanner 写了 type_source='user'：{sql}"

    # 正向证据：Scanner 仍然在正常维护 machine facts（name 必须被写入）。
    assert any("name" in sql.lower() for sql in resources_writes)


def test_scanner_insert_keeps_type_source_auto(scan_env):
    """``type_source='auto'`` 是 Contract 允许的 machine 初始化，不得处理成违规。"""
    conn, root, library = scan_env
    write_card(root / "card.png")
    LibraryScanner(conn).scan(library.id)

    row = conn.execute("SELECT type_source FROM resources").fetchone()
    assert row["type_source"] == "auto"


# ---------------------------------------------------------------------------
# Phase 3.2：Tag 表写路径护栏（tags / resource_tags 只允许 TagWriteService）
# ---------------------------------------------------------------------------


def test_only_tag_write_service_writes_tag_tables():
    offenders: list[str] = []
    for path in _scanned_sources():
        if _TAG_WRITE_RE.search(path.read_text(encoding="utf-8")):
            relative = path.relative_to(REPO).as_posix()
            if relative not in ALLOWED_TAG_WRITERS:
                offenders.append(relative)
    assert offenders == [], (
        "只有 TagWriteService 可以写 tags / resource_tags，违规文件："
        + ", ".join(offenders)
    )


def test_tag_guard_actually_matches_tag_write_service():
    """正向证据：护栏确实能命中 TagWriteService 的写入（防正则写错假通过）。"""
    source = (REPO / "core/app/tag_write.py").read_text(encoding="utf-8")
    assert _TAG_WRITE_RE.search(source), "护栏必须能命中 TagWriteService 的写入语句"


def test_scanner_executed_sql_never_writes_tag_tables(scan_env):
    """Scanner 重扫（INSERT + UPDATE 两条路径）不得写 `tags` / `resource_tags`。"""
    conn, root, library = scan_env
    card = write_card(root / "card.png", lastname="Alice", firstname="Card")
    write_zipmod(root / "mod.zipmod", "com.example.x")
    scanner = LibraryScanner(conn)

    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        scanner.scan(library.id)
        write_card(card, lastname="Renamed", firstname="Character")
        scanner.scan(library.id)
    finally:
        conn.set_trace_callback(None)

    for sql in statements:
        assert not _TAG_WRITE_RE.search(sql), f"Scanner 写了 Tag 表：{sql}"


def test_rescan_preserves_resource_tags(scan_env):
    """重扫不得删除用户 Tag 关联（资源行不删、机器 writer 不碰 Tag 表）。"""
    from core.app import TagWriteService

    conn, root, library = scan_env
    card = write_card(root / "card.png", lastname="Alice", firstname="Card")
    scanner = LibraryScanner(conn)
    scanner.scan(library.id)
    resource_id = int(conn.execute("SELECT id FROM resources").fetchone()["id"])

    service = TagWriteService(conn)
    tag_id = service.create_tag("Cute")
    service.assign_tag(resource_id, tag_id)
    service.set_favorite(resource_id, True)

    write_card(card, lastname="Renamed", firstname="Character")
    scanner.scan(library.id)

    assert conn.execute("SELECT count(*) AS c FROM resource_tags").fetchone()["c"] == 2
    assert conn.execute("SELECT count(*) AS c FROM tags").fetchone()["c"] == 2
