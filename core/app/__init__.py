"""Application 层（Phase 1.5 起；Phase 3.1 扩展用户写入边界）。

职责：在 GUI / CLI 与既有 Store / Scanner 之间提供**极薄的边界**。

- ``LibraryAdminService``（Phase 1.5-A）：转发现有 ``LibraryStore``，本身不写业务 SQL；
- ``ResourceWriteService``（Phase 3.1）：**唯一**的用户数据 runtime 写入口，
  只写用户数据列（``display_name`` / ``notes`` / user-owned type + ``type_source``）
  与系统簿记 ``updated_at``，绝不触碰 machine facts；
- 短操作复用调用方传入的连接；
- 长任务（扫描）由 ``run_scan(db_path, library_id, mode=...)`` 在**调用线程**里
  自开自关连接，供后台 worker 使用（Phase 1.5-B）。

刻意**不引入**：Manager / Controller / EventBus / 通用 Task Framework。
"""

from core.app.admin import LibraryAdminService, run_scan
from core.app.resource_write import (
    InvalidResourceValue,
    ResourceNotFound,
    ResourceWriteError,
    ResourceWriteService,
)

__all__ = [
    "LibraryAdminService",
    "run_scan",
    "ResourceWriteService",
    "ResourceWriteError",
    "ResourceNotFound",
    "InvalidResourceValue",
]
