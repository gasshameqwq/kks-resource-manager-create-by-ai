"""Library 写操作 + 扫描的极薄 application 服务 —— Phase 1.5-A / 1.5-B。

设计约束（见 ``docs/phase1/PHASE1_5_DESIGN_REVIEW.md`` §3-A 与 §9-Q2）：

- **不写业务 SQL**：库表的增删改仍全部在 ``LibraryStore`` 内；
- **不复制业务规则**：路径归一化 / 目录校验 / 重复拒绝 / 删除级联语义
  全部以 ``LibraryStore`` 为准，本层不做二次判断；
- **只做转发与编排**：短操作复用调用方连接（``LibraryAdminService``）；
  长任务（扫描）用 ``run_scan`` 自开自关连接，交给后台 worker 调用。

连接与线程
----------
``db.connect()`` 默认 ``check_same_thread=True``，连接**绑定创建它的线程**。
因此：

- ``LibraryAdminService`` 的方法必须在**拥有该连接的线程**（GUI 主线程）调用；
- ``run_scan()`` 在**它被调用的线程**里自己开连接、自己关连接（见 Phase 1.5-B）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.database import db as database
from core.library import LibraryRemovalReport, LibraryStore
from core.models import Library
from core.scanner import LibraryScanner, ScanResult


class LibraryAdminService:
    """转发现有 ``LibraryStore`` 的薄写操作服务。

    方法语义与 ``LibraryStore`` **完全一致**，异常原样向上抛（由 GUI 决定如何展示）：

    - ``add_library``    → ``LibraryStore.add``（路径必须存在；重复 root_path 抛
      ``LibraryAlreadyExists``）；
    - ``set_enabled``    → ``LibraryStore.set_enabled``；
    - ``preview_removal``→ ``LibraryStore.preview_removal``（只读预览，不修改）；
    - ``remove_library`` → ``LibraryStore.remove``（只删库记录，不碰文件 / 资源）。
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._store = LibraryStore(conn)

    def add_library(
        self,
        root_path: str | Path,
        *,
        name: str | None = None,
        notes: str = "",
        enabled: bool = True,
        allow_missing: bool = False,
    ) -> Library:
        """添加一个扫描根目录（沿用 ``LibraryStore`` 的全部既有语义）。"""
        return self._store.add(
            root_path,
            name=name,
            notes=notes,
            enabled=enabled,
            allow_missing=allow_missing,
        )

    def set_enabled(self, library_id: int, enabled: bool) -> Library:
        """启用 / 暂停某个 Library（只改 ``libraries.enabled``）。"""
        return self._store.set_enabled(library_id, enabled)

    def preview_removal(self, library_id: int) -> LibraryRemovalReport:
        """删除影响预览（只读，不做任何修改）。"""
        return self._store.preview_removal(library_id)

    def remove_library(self, library_id: int) -> LibraryRemovalReport:
        """移除 Library 记录：资源保留（``library_id`` 置空）、扫描记录级联删除，
        **不删除 / 不移动任何文件**。"""
        return self._store.remove(library_id)

    def database_path(self) -> str | None:
        """返回本服务所用连接的数据库文件路径（只读 PRAGMA，不做任何写入）。

        后台扫描 worker 必须在自己的线程里重新 ``connect``，因此需要这个路径。
        内存数据库返回 ``None``。
        """
        try:
            rows = self.conn.execute("PRAGMA database_list").fetchall()
        except sqlite3.Error:
            return None
        for row in rows:
            if row[1] == "main":
                return str(row[2]) or None
        return None


def run_scan(
    db_path: str | Path,
    library_id: int,
    *,
    mode: str = "incremental",
) -> ScanResult:
    """在**调用线程**里扫描一个 Library（Phase 1.5-B，供后台 worker 使用）。

    职责只有「连接生命周期 + 转发」：

    ``db.connect(db_path)`` → ``LibraryScanner(conn).scan(...)`` → ``conn.close()``

    为什么不接收连接：``db.connect()`` 的 SQLite 连接绑定创建它的线程，
    GUI 线程的连接**不能**在 worker 线程里使用，所以由本函数自己开、自己关。
    无论扫描成功还是抛异常，连接都在 ``finally`` 里关闭。

    扫描逻辑一行都不在这里：增量 / 全量、解析、入库、missing 判定全部由现有
    ``LibraryScanner`` 决定。
    """
    conn = database.connect(db_path)
    try:
        return LibraryScanner(conn).scan(library_id, mode=mode)
    finally:
        conn.close()


__all__ = ["LibraryAdminService", "run_scan"]
