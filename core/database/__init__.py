"""数据库层：SQLite schema、迁移与连接管理。

本包只负责“索引与整理信息”的持久化；原始资源文件永远留在用户磁盘上，
不进数据库、不被复制。
"""

from core.database.db import connect, initialize, table_names  # noqa: F401

__all__ = ["initialize", "connect", "table_names"]
