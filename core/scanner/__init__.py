"""目录扫描层 —— Phase 1.2-C。

``LibraryScanner`` 遍历 Library 根目录，把候选文件交给 ``core.parsers``（纯只读），
再把 ParseResult 写进 Schema v2 的表。Scanner **不自己解析**文件，
也**不**根据文件名 / 目录名 / 大小判断资源类型。

安全约定
--------
- **只读**：绝不修改 / 移动 / 重命名 / 删除用户文件，也不写缓存文件。
- **不自动删除**：文件消失只标记 ``scan_status='missing'``，不删行、更不删文件。
- **失败隔离**：每个文件一个事务，单文件失败不影响同批其它文件。
- **内容哈希与解析同频（Phase 2.1）**：增量门仍是 ``(file_path_key, file_size,
  modified_time)``；只有新增 / 变化 / ``mode='full'`` 的文件才解析并计算
  ``resources.sha256``（见 ``core.scanner.hashing``）。读取窗口内文件变化则不提交。
"""

from core.scanner.models import (
    RESULT_SKIPPED,
    SCAN_COMPLETED,
    SCAN_FAILED,
    STAGE_IO,
    STAGE_NOT_A_RESOURCE,
    STAGE_PARSE,
    STAGE_STORE,
    ScanIssue,
    ScanResult,
    ScanStats,
)
from core.scanner.hashing import sha256_of_file
from core.scanner.scanner import CANDIDATE_SUFFIXES, LibraryScanner, iter_candidates
from core.scanner.store import (
    OUTCOME_INSERTED,
    OUTCOME_UPDATED,
    ResourceStore,
    build_card_metadata,
)

__all__ = [
    "LibraryScanner",
    "iter_candidates",
    "CANDIDATE_SUFFIXES",
    "sha256_of_file",
    "ResourceStore",
    "build_card_metadata",
    "OUTCOME_INSERTED",
    "OUTCOME_UPDATED",
    "ScanResult",
    "ScanStats",
    "ScanIssue",
    "SCAN_COMPLETED",
    "SCAN_FAILED",
    "RESULT_SKIPPED",
    "STAGE_IO",
    "STAGE_PARSE",
    "STAGE_STORE",
    "STAGE_NOT_A_RESOURCE",
]
