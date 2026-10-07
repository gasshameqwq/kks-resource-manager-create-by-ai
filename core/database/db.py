"""SQLite 连接与初始化。

对外接口：

- ``connect(db_file=None)``  —— 打开连接（开启外键、WAL、行工厂）
- ``transaction(conn)`` —— 显式事务上下文（批量写入用，避免 autocommit 逐行落盘）
- ``initialize(db_file=None)`` —— 建库/升级到 ``SCHEMA_VERSION``，返回状态摘要
- ``table_names(conn)`` —— 业务表名列表
- ``normalize_path_key(path)`` / ``normalize_name_key(text)`` —— 归一化工具
"""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from core import app_paths
from core.database import schema as schema_mod


# ---------------------------------------------------------------------------
# 归一化工具（Windows 路径不区分大小写；名称去空白 + casefold）
# ---------------------------------------------------------------------------


def normalize_path_key(path: str | Path) -> str:
    """把路径归一化成可做唯一索引的 key。

    处理：展开用户目录 -> 绝对化 -> 统一分隔符 -> 去掉尾部分隔符 -> 小写。
    注意：不做 ``resolve()``（避免因符号链接/短路径造成同一文件两个 key）。
    """
    text = str(path).strip().strip('"')
    if not text:
        return ""
    try:
        p = Path(text).expanduser()
        if not p.is_absolute():
            p = p.absolute()
        text = str(p)
    except (OSError, ValueError):
        pass
    text = text.replace("\\", "/").rstrip("/")
    return text.casefold()


def normalize_name_key(text: str | None) -> str:
    """名称归一化：去首尾空白 + casefold，用于作者/标签/Collection 去重。"""
    return (text or "").strip().casefold()


# ---------------------------------------------------------------------------
# 连接
# ---------------------------------------------------------------------------


def connect(db_file: str | Path | None = None) -> sqlite3.Connection:
    """打开数据库连接。``db_file`` 为空时使用应用数据目录下的默认库。"""
    path = Path(db_file) if db_file else app_paths.db_path()
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), isolation_level=None)  # 自动提交，便于 DDL
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    return conn


@contextlib.contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """显式事务上下文：把多条写操作合并成一次提交。

    连接默认是 autocommit（``isolation_level=None``），这对单条 DDL / 单条 UI 操作
    最省心，但批量写入时每一行都要落一次盘。数万行规模下这会让扫描慢到不可接受，
    因此**批量写入必须包在事务里**：

        with db.transaction(conn):
            for row in rows:
                conn.execute("INSERT ...", row)

    语义：
    - 已在事务中调用时直接复用外层事务，不会提前提交（可安全嵌套）。
    - 块内抛异常 → 整个事务回滚并原样抛出异常。
    - 块正常结束 → 提交。
    """
    if conn.in_transaction:
        yield conn
        return

    conn.execute("BEGIN")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def table_names(conn: sqlite3.Connection) -> list[str]:
    """返回业务表名（排除 sqlite 内部表与 FTS 影子表）。"""
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    names = [r["name"] for r in rows]
    return [n for n in names if "resources_fts" not in n]


def _meta_get(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def _meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_meta(key, value, updated_at) VALUES (?, ?, datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
        (key, str(value)),
    )


def schema_version(conn: sqlite3.Connection) -> int:
    """读取当前 schema 版本；未初始化返回 0。"""
    try:
        value = _meta_get(conn, "schema_version", "0")
    except sqlite3.OperationalError:  # app_meta 还不存在
        return 0
    try:
        return int(value or 0)
    except ValueError:
        return 0


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    """返回某张表的列名集合（表不存在时返回空集）。"""
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return set()
    return {row["name"] for row in rows}


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, decl: str
) -> bool:
    """幂等加列：列已存在则跳过。返回是否真的执行了 ALTER。

    SQLite 的 ``ALTER TABLE ... ADD COLUMN`` 重复执行会报 duplicate column name，
    因此迁移里凡是加列都走这里，保证重复运行安全。
    """
    if column in column_names(conn, table):
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    return True


# ---------------------------------------------------------------------------
# 初始化 / 迁移
# ---------------------------------------------------------------------------


def initialize(db_file: str | Path | None = None) -> dict:
    """建库或升级到最新 schema，返回状态摘要 dict。

    幂等：重复调用不会重复建表，也不会破坏已有数据。
    """
    app_paths.ensure_dirs()
    path = Path(db_file) if db_file else app_paths.db_path()
    conn = connect(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_meta ("
            " key TEXT PRIMARY KEY, value TEXT,"
            " updated_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )

        current = schema_version(conn)
        applied: list[int] = []

        for version in sorted(schema_mod.MIGRATIONS):
            if version <= current:
                continue
            ddl, fts_ddl = schema_mod.MIGRATIONS[version]
            # 加列必须排在 DDL 之前：v2 的 DDL 里可能有依赖新列的索引。
            # （fresh 库先跑完 v1 建表，所以这里表一定已存在。）
            for table, column, decl in schema_mod.MIGRATION_ADDED_COLUMNS.get(version, ()):
                _add_column_if_missing(conn, table, column, decl)
            conn.executescript(ddl)
            if fts_ddl:
                _try_enable_fts(conn, fts_ddl)
            _meta_set(conn, "schema_version", str(version))
            applied.append(version)

        fts_enabled = bool(int(_meta_get(conn, "fts_enabled", "0") or 0))
        # 只在「本次真的执行了迁移」时才回填存量行。
        #
        # 之前这里是无条件调用：即使没有任何迁移（绝大多数启动都是这种情况），
        # 每次启动都要对 resources 跑一遍
        #     WHERE r.id NOT IN (SELECT rowid FROM resources_fts)
        # 的全量比对，资源上万后就是纯浪费。
        #
        # 新库首建、以及老库升级到启用 FTS 的版本时 applied 都非空，
        # 所以该回填的时机一个都没少；之后的增量由 FTS 触发器负责。
        if fts_enabled and applied:
            _backfill_fts(conn)

        return {
            "db_path": str(path),
            "schema_version": schema_version(conn),
            "tables": table_names(conn),
            "fts_enabled": fts_enabled,
            "applied_migrations": applied,
        }
    finally:
        conn.close()


def _try_enable_fts(conn: sqlite3.Connection, fts_ddl: str) -> bool:
    """尽力创建 FTS5 表；构建不支持（缺 FTS5 / 版本过旧）时静默回退。"""
    try:
        conn.executescript(fts_ddl)
    except sqlite3.Error as exc:  # noqa: BLE001 - 退化路径，不应让应用启动失败
        _meta_set(conn, "fts_enabled", "0")
        _meta_set(conn, "fts_error", f"{type(exc).__name__}: {exc}")
        return False
    _meta_set(conn, "fts_enabled", "1")
    _meta_set(conn, "fts_error", "")
    return True


def _backfill_fts(conn: sqlite3.Connection) -> None:
    """把 resources 中尚未进入 FTS 索引的行补进去（幂等，失败不致命）。"""
    try:
        conn.execute(
            "INSERT INTO resources_fts(rowid, display_name, name, author, series, description, notes) "
            "SELECT r.id, r.display_name, r.name, r.author, r.series, r.description, r.notes "
            "FROM resources r "
            "WHERE r.id NOT IN (SELECT rowid FROM resources_fts)"
        )
    except sqlite3.Error:
        pass
