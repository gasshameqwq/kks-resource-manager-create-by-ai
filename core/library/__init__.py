"""Library（扫描根目录）管理 —— Phase 1.1。

Phase 1.1 的验收目标是「能添加 / 删除 / 列出扫描根目录，并写进 ``libraries`` 表」。
本包只做数据库层面的 Library 管理，**不包含目录遍历与文件解析**：

- 该扫什么、怎么扫、增量判定 —— Phase 1.2（``core/scanner/``）。
- 卡片解析与缩略图 —— Phase 1.3（``core/parsers/`` / ``core/thumbnails/``）。
- 界面 —— Phase 1.4（``ui/``）。

安全约定：删除 Library 只删数据库记录，绝不动用户的目录与文件。
"""

from core.library.store import (
    InvalidLibraryPath,
    LibraryAlreadyExists,
    LibraryError,
    LibraryNotFound,
    LibraryRemovalReport,
    LibraryStats,
    LibraryStore,
)

__all__ = [
    "LibraryError",
    "InvalidLibraryPath",
    "LibraryNotFound",
    "LibraryAlreadyExists",
    "LibraryStats",
    "LibraryRemovalReport",
    "LibraryStore",
]
