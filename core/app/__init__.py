"""Application 层（Phase 1.5 起）。

职责：在 GUI 与既有 Store / Scanner 之间提供**极薄的边界**。

- 本层不写业务 SQL、不复制 Store 的业务规则，只做转发与编排；
- 短操作复用调用方传入的连接（``LibraryAdminService``，Phase 1.5-A）；
- 长任务（扫描）由 ``run_scan(db_path, library_id, mode=...)`` 在**调用线程**里
  自开自关连接，供后台 worker 使用（Phase 1.5-B）。

刻意**不引入**：Manager / Controller / EventBus / 通用 Task Framework。
"""

from core.app.admin import LibraryAdminService, run_scan

__all__ = ["LibraryAdminService", "run_scan"]
