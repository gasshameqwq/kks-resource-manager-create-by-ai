"""Scanner 的结果模型（结构化输出，替代随意 dict）。

统计口径
--------
用户要求至少能区分六种状态；本项目已有的 ``scan_records`` 列名不同，
因此这里做「同义映射」，不改动既有列（见 ``ScanStats.scan_record_fields``）::

    discovered(发现)  -> scan_records.files_seen
    inserted(新增)    -> scan_records.files_new
    updated(更新)     -> scan_records.files_changed
    skipped(跳过)     -> scan_records.files_skipped
    missing(缺失)     -> scan_records.files_missing
    failed(失败)      -> scan_records.files_failed
    parsed(已解析)    -> **没有对应列**，只在 ScanResult 里报告（见 docs/phase1/PHASE1_2_REPORT.md）

``parsed`` 指「真的调用了 Parser 的文件数」；``inserted + updated`` 是其中成功入库的部分，
``failed`` 里包含 Parser 判定「不是卡片 / 不是 zipmod」的文件。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 扫描记录状态（与 scan_records.status 的 CHECK 一致）
SCAN_RUNNING = "running"
SCAN_COMPLETED = "completed"
SCAN_FAILED = "failed"

# 结果状态：多一个 "skipped"，表示这次调用根本没有扫描（例如 Library 已暂停）
RESULT_SKIPPED = "skipped"

# issue 阶段
STAGE_IO = "io"                       # 读文件 / 取 stat 失败
STAGE_NOT_A_RESOURCE = "not_a_resource"  # Parser 明确判定「不是卡片 / 不是 zipmod」
STAGE_PARSE = "parse"                 # Parser 因损坏等原因失败
STAGE_STORE = "store"                 # 入库阶段异常


@dataclass
class ScanStats:
    """一次扫描的统计。"""

    discovered: int = 0   # 候选文件总数（按扩展名筛出来的）
    parsed: int = 0       # 真正调用过 Parser 的数量
    inserted: int = 0     # 新建的资源行
    updated: int = 0      # 更新过的资源行
    skipped: int = 0      # size + mtime 未变，未调用 Parser
    failed: int = 0       # 失败（含「不是资源」）
    missing: int = 0      # 之前入库、这次在磁盘上找不到
    not_a_resource: int = 0  # failed 的细分：Parser 判定「不是卡片 / 不是 zipmod」

    def scan_record_fields(self) -> dict[str, int]:
        """映射到 ``scan_records`` 的既有列（不新增列）。"""
        return {
            "files_seen": self.discovered,
            "files_new": self.inserted,
            "files_changed": self.updated,
            "files_skipped": self.skipped,
            "files_missing": self.missing,
            "files_failed": self.failed,
        }


@dataclass(frozen=True)
class ScanIssue:
    """单个文件的问题记录（只影响该文件）。"""

    path: str
    stage: str
    message: str


@dataclass
class ScanResult:
    """一次扫描的完整结果。"""

    library_id: int | None = None
    root_path: str | None = None
    mode: str = "incremental"
    status: str = SCAN_RUNNING
    skip_reason: str | None = None
    stats: ScanStats = field(default_factory=ScanStats)
    issues: list[ScanIssue] = field(default_factory=list)
    scan_record_id: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None

    @property
    def ok(self) -> bool:
        """是否顺利跑完（status 为 completed 或 skipped）。"""
        return self.status in (SCAN_COMPLETED, RESULT_SKIPPED)


__all__ = [
    "SCAN_RUNNING",
    "SCAN_COMPLETED",
    "SCAN_FAILED",
    "RESULT_SKIPPED",
    "STAGE_IO",
    "STAGE_PARSE",
    "STAGE_STORE",
    "STAGE_NOT_A_RESOURCE",
    "ScanStats",
    "ScanIssue",
    "ScanResult",
]
