"""Library（扫描根目录）的数据访问层 —— Phase 1.1。

职责边界
--------
- **只管 ``libraries`` 表**的增删改查与统计。
- **不遍历目录、不读取文件内容**：目录遍历与增量扫描属于 Phase 1.2
  （``core/scanner/``），本模块刻意不实现。
- 删除 Library **只删数据库记录**，不触碰用户的任何目录与文件。

设计要点
--------
- 路径统一经 ``db.normalize_path_key`` 归一化后写入 ``root_path_key``，
  因此 ``D:\\KKS`` 与 ``d:/kks`` 会被识别为同一个 Library（Windows 路径不区分大小写）。
- 批量添加走 ``db.transaction``，避免 autocommit 逐行落盘；任一条失败则整批回滚。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from core.database import db as database
from core.models import Library


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class LibraryError(Exception):
    """Library 操作的基类异常。"""


class InvalidLibraryPath(LibraryError):
    """路径为空、不存在、或不是目录。"""

    def __init__(self, path: str | Path, reason: str) -> None:
        self.path = str(path)
        self.reason = reason
        super().__init__(f"{reason}：{path}")


class LibraryNotFound(LibraryError):
    """按 id 或路径都找不到对应的 Library。"""

    def __init__(self, target: str | int) -> None:
        self.target = target
        super().__init__(f"找不到 Library：{target}")


class LibraryAlreadyExists(LibraryError):
    """该根目录已经添加过（归一化后重复）。"""

    def __init__(self, root_path: str, existing_id: int | None) -> None:
        self.root_path = root_path
        self.existing_id = existing_id
        where = f"（已存在 id={existing_id}）" if existing_id is not None else ""
        super().__init__(f"该目录已添加过{where}：{root_path}")


# ---------------------------------------------------------------------------
# 统计 / 删除预览
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LibraryStats:
    """一个 Library 下的资源统计（只读查询，不触发扫描）。"""

    library_id: int
    resources: int = 0
    missing: int = 0
    needs_review: int = 0


@dataclass(frozen=True)
class LibraryRemovalReport:
    """删除 Library 的影响预览 —— 同时用于「确认前预览」与「删除后回报」。"""

    library: Library
    resources_orphaned: int
    scan_records_deleted: int


def _row_to_library(row: sqlite3.Row) -> Library:
    return Library(
        id=row["id"],
        name=row["name"],
        root_path=row["root_path"],
        enabled=bool(row["enabled"]),
        notes=row["notes"] or "",
        last_scan_at=row["last_scan_at"],
    )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class LibraryStore:
    """``libraries`` 表的 CRUD。

    一个实例绑定一个连接；本类自己开启事务的方法只有 ``add_many`` 与 ``remove``，
    其余单条操作用连接默认的 autocommit 即可（见 docs/ARCHITECTURE.md §5.4）。
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ---- 读取 -----------------------------------------------------------

    def require(self, library_id: int) -> Library:
        """按 id 取 Library，找不到抛 ``LibraryNotFound``。"""
        row = self.conn.execute(
            "SELECT * FROM libraries WHERE id = ?", (library_id,)
        ).fetchone()
        if row is None:
            raise LibraryNotFound(library_id)
        return _row_to_library(row)

    def find_by_path(self, path: str | Path) -> Library | None:
        """按（归一化后的）根目录路径查找。"""
        key = database.normalize_path_key(str(path))
        if not key:
            return None
        row = self.conn.execute(
            "SELECT * FROM libraries WHERE root_path_key = ?", (key,)
        ).fetchone()
        return _row_to_library(row) if row else None

    def resolve(self, target: str | int) -> Library:
        """把「id」或「路径」统一解析成 Library（CLI 用）。"""
        if isinstance(target, int) or (isinstance(target, str) and target.strip().isdigit()):
            return self.require(int(target))
        found = self.find_by_path(target)
        if found is None:
            raise LibraryNotFound(target)
        return found

    def list_all(self, include_disabled: bool = True) -> list[Library]:
        """列出全部 Library（默认含已暂停的）。"""
        sql = "SELECT * FROM libraries"
        if not include_disabled:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY name COLLATE NOCASE, id"
        return [_row_to_library(r) for r in self.conn.execute(sql).fetchall()]

    def stats(self, library_id: int) -> LibraryStats:
        """统计该 Library 下已入库的资源（不扫描磁盘）。"""
        self.require(library_id)
        row = self.conn.execute(
            "SELECT count(*) AS resources,"
            " sum(CASE WHEN scan_status = 'missing' THEN 1 ELSE 0 END) AS missing,"
            " sum(CASE WHEN needs_review = 1 THEN 1 ELSE 0 END) AS needs_review"
            " FROM resources WHERE library_id = ?",
            (library_id,),
        ).fetchone()
        return LibraryStats(
            library_id=library_id,
            resources=row["resources"] or 0,
            missing=row["missing"] or 0,
            needs_review=row["needs_review"] or 0,
        )

    # ---- 写入 -----------------------------------------------------------

    def add(
        self,
        root_path: str | Path,
        *,
        name: str | None = None,
        notes: str = "",
        enabled: bool = True,
        allow_missing: bool = False,
    ) -> Library:
        """添加一个扫描根目录。

        ``allow_missing=True`` 时不检查目录是否存在（用于暂时离线的盘符），
        Phase 1.2 的扫描器会自行跳过不可访问的根目录。
        """
        display = self._display_path(root_path)
        if not allow_missing:
            self._require_directory(Path(display), root_path)

        key = database.normalize_path_key(display)
        existing = self.conn.execute(
            "SELECT id FROM libraries WHERE root_path_key = ?", (key,)
        ).fetchone()
        if existing is not None:
            raise LibraryAlreadyExists(display, existing["id"])

        clean_name = (name or "").strip() or Path(display).name or display
        try:
            cur = self.conn.execute(
                "INSERT INTO libraries(name, root_path, root_path_key, enabled, notes)"
                " VALUES (?, ?, ?, ?, ?)",
                (clean_name, display, key, 1 if enabled else 0, (notes or "").strip()),
            )
        except sqlite3.IntegrityError as exc:  # 并发下的唯一约束兜底
            raise LibraryAlreadyExists(display, None) from exc
        return self.require(int(cur.lastrowid))

    def add_many(
        self,
        root_paths: list[str] | tuple[str, ...],
        *,
        notes: str = "",
        enabled: bool = True,
        allow_missing: bool = False,
    ) -> list[Library]:
        """一次添加多个根目录；任一条失败则整批回滚（不留下加了一半的状态）。"""
        added: list[Library] = []
        with database.transaction(self.conn):
            for path in root_paths:
                added.append(
                    self.add(
                        path, notes=notes, enabled=enabled, allow_missing=allow_missing
                    )
                )
        return added

    def update(
        self,
        library_id: int,
        *,
        name: str | None = None,
        notes: str | None = None,
        enabled: bool | None = None,
    ) -> Library:
        """局部更新；只传需要改的字段。"""
        self.require(library_id)
        sets: list[str] = []
        params: list[object] = []

        if name is not None:
            clean = name.strip()
            if not clean:
                raise LibraryError("Library 名称不能为空")
            sets.append("name = ?")
            params.append(clean)
        if notes is not None:
            sets.append("notes = ?")
            params.append(notes.strip())
        if enabled is not None:
            sets.append("enabled = ?")
            params.append(1 if enabled else 0)

        if not sets:
            return self.require(library_id)

        sets.append("updated_at = datetime('now')")
        params.append(library_id)
        self.conn.execute(
            f"UPDATE libraries SET {', '.join(sets)} WHERE id = ?", params
        )
        return self.require(library_id)

    def set_enabled(self, library_id: int, enabled: bool) -> Library:
        """启用 / 暂停某个 Library（暂停后扫描器会跳过它）。"""
        return self.update(library_id, enabled=enabled)

    def preview_removal(self, library_id: int) -> LibraryRemovalReport:
        """预览删除影响，不做任何修改。"""
        lib = self.require(library_id)
        resources = self.conn.execute(
            "SELECT count(*) AS c FROM resources WHERE library_id = ?", (library_id,)
        ).fetchone()["c"]
        scans = self.conn.execute(
            "SELECT count(*) AS c FROM scan_records WHERE library_id = ?", (library_id,)
        ).fetchone()["c"]
        return LibraryRemovalReport(
            library=lib, resources_orphaned=resources, scan_records_deleted=scans
        )

    def remove(self, library_id: int) -> LibraryRemovalReport:
        """删除 Library 记录。

        数据库层的影响：``resources.library_id`` 被置空（ON DELETE SET NULL，
        资源本身保留），``scan_records`` 级联删除。
        **用户的目录与文件完全不受影响** —— 本方法不接触文件系统。
        """
        report = self.preview_removal(library_id)
        with database.transaction(self.conn):
            self.conn.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
        return report

    # ---- 内部工具 -------------------------------------------------------

    def _display_path(self, root_path: str | Path) -> str:
        """去掉引号、展开 ~、转绝对路径，返回用于展示与入库的路径。"""
        text = str(root_path).strip().strip('"')
        if not text:
            raise InvalidLibraryPath(root_path, "路径为空")
        try:
            path = Path(text).expanduser()
            if not path.is_absolute():
                path = path.absolute()
        except (OSError, ValueError) as exc:
            raise InvalidLibraryPath(root_path, str(exc)) from exc
        return str(path)

    def _require_directory(self, path: Path, original: str | Path) -> None:
        if not path.exists():
            raise InvalidLibraryPath(
                original, "目录不存在（临时离线的盘符可加 --allow-missing）"
            )
        if not path.is_dir():
            raise InvalidLibraryPath(original, "不是一个目录")


__all__ = [
    "LibraryError",
    "InvalidLibraryPath",
    "LibraryNotFound",
    "LibraryAlreadyExists",
    "LibraryStats",
    "LibraryRemovalReport",
    "LibraryStore",
]
