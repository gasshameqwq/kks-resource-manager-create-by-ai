"""Library Scanner —— Phase 1.2-C：扫描 → 解析 → 入库 → 增量更新。

调用链（Scanner **不**自己解析文件）::

    Library root
        ↓ 递归遍历（只按扩展名找候选）
    候选文件 (.png / .zipmod / .zip)
        ↓ 增量判定 (file_path_key, file_size, modified_time)
        ├─ 未变 → 跳过（**不调用 Parser**）
        └─ 新增/变化 → core.parsers.parse_card / parse_zipmod（纯只读）
        ↓
    ParseResult
        ↓ 每个文件一个 db.transaction
    resources / mods / resource_mods / resource_mod_usages
    resource_plugins / resource_authors / scan_records

硬性约束
--------
- **只读**：绝不修改、移动、重命名、删除用户的文件；也不写任何缓存文件。
- **不自行解析**：文件类型完全由 Parser 决定，不看文件名/目录名/大小。
- **失败隔离**：每个文件一个事务，一个文件失败不影响同批其它文件。
- **内容哈希与解析同频（Phase 2.1）**：增量未变的文件跳过（不读文件、不算哈希）；
  新增 / ``(size, mtime)`` 变化 / ``mode='full'`` 才解析并计算 ``resources.sha256``。
  读取窗口内 ``(size, mtime)`` 变化则本次结果整体不提交（C7），下次扫描重来。
- **不自动删除**：文件消失只标记 ``scan_status='missing'``，绝不删行、更不删文件。
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from core.database import db as database
from core.library import LibraryStore
from core.parsers import parse_card, parse_zipmod
from core.scanner.hashing import sha256_of_file
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
from core.scanner.store import ResourceStore

# 候选扩展名：**只决定「是否值得尝试解析」，不决定资源类型**
CANDIDATE_SUFFIXES: tuple[str, ...] = (".png", ".zipmod", ".zip")

# mtime 用浮点存储，比较时留一点容差
_MTIME_EPSILON = 1e-6


def iter_candidates(root: Path, suffixes: tuple[str, ...] = CANDIDATE_SUFFIXES):
    """递归列出候选文件（顺序稳定，便于测试与复现）。"""
    wanted = {s.lower() for s in suffixes}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if Path(name).suffix.lower() in wanted:
                yield Path(dirpath) / name


class LibraryScanner:
    """把一个 Library 根目录扫描进数据库。"""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        suffixes: tuple[str, ...] = CANDIDATE_SUFFIXES,
        store: ResourceStore | None = None,
    ) -> None:
        self.conn = conn
        self.suffixes = suffixes
        self.store = store or ResourceStore(conn)
        self.libraries = LibraryStore(conn)

    # ---- 主入口 ---------------------------------------------------------

    def scan(
        self,
        library_id: int,
        *,
        mode: str = "incremental",
        root: Path | None = None,
    ) -> ScanResult:
        """扫描一个 Library。``mode='full'`` 时忽略增量捷径，全部重新解析。"""
        if mode not in ("incremental", "full"):
            raise ValueError(f"未知扫描模式：{mode}")

        library = self.libraries.require(library_id)
        root_path = Path(root) if root is not None else Path(library.root_path)
        result = ScanResult(
            library_id=library_id, root_path=str(root_path), mode=mode
        )

        if root is None and not library.enabled:
            result.status = RESULT_SKIPPED
            result.skip_reason = "Library 已暂停（enabled=0），未执行扫描"
            return result

        if not root_path.is_dir():
            result.status = SCAN_FAILED
            result.skip_reason = f"根目录不存在或不是目录：{root_path}"
            return result

        started = time.perf_counter()
        result.scan_record_id = self._begin_scan_record(library_id, mode)
        seen_keys: set[str] = set()
        result.started_at = self._now()

        try:
            for path in iter_candidates(root_path, self.suffixes):
                result.stats.discovered += 1
                self._process_file(
                    path=path,
                    library_id=library_id,
                    root_path=root_path,
                    mode=mode,
                    stats=result.stats,
                    issues=result.issues,
                    seen_keys=seen_keys,
                )
            result.stats.missing = self.store.mark_missing(library_id, seen_keys)
            result.status = SCAN_COMPLETED
        except Exception as exc:  # noqa: BLE001 - 扫描级别的兜底
            result.status = SCAN_FAILED
            result.issues.append(
                ScanIssue(str(root_path), STAGE_IO, f"{type(exc).__name__}: {exc}")
            )
        finally:
            result.duration_ms = int((time.perf_counter() - started) * 1000)
            result.finished_at = self._now()
            self._finish_scan_record(result)

        return result

    # ---- 单文件 ---------------------------------------------------------

    def _process_file(
        self,
        *,
        path: Path,
        library_id: int,
        root_path: Path,
        mode: str,
        stats: ScanStats,
        issues: list[ScanIssue],
        seen_keys: set[str],
    ) -> None:
        """处理一个候选文件。任何失败都只影响这一个文件。"""
        try:
            stat = path.stat()
        except OSError as exc:
            stats.failed += 1
            issues.append(ScanIssue(str(path), STAGE_IO, f"无法读取文件信息：{exc}"))
            return

        size = int(stat.st_size)
        modified_time = float(stat.st_mtime)
        path_key = database.normalize_path_key(path)
        seen_keys.add(path_key)

        existing = self.store.find_by_path_key(path_key)
        if (
            mode == "incremental"
            and existing is not None
            and existing["file_size"] == size
            and abs((existing["modified_time"] or 0.0) - modified_time) < _MTIME_EPSILON
        ):
            stats.skipped += 1
            # 之前被标记成 missing 的文件又回来了 → 恢复 present（不重新解析）
            self.store.touch_present(int(existing["id"]))
            return

        # ---- 交给 Parser（纯只读，Scanner 不自己解析）----
        suffix = path.suffix.lower()
        stats.parsed += 1
        try:
            if suffix == ".png":
                parsed = parse_card(path)
            else:
                parsed = parse_zipmod(path)
        except Exception as exc:  # noqa: BLE001 - Parser 理论上不抛，仍兜底
            stats.failed += 1
            issues.append(
                ScanIssue(str(path), STAGE_PARSE, f"{type(exc).__name__}: {exc}")
            )
            return

        # ---- Phase 2.1：同一次稳定读取窗口内计算 SHA-256（C7）----
        # 读取窗口 = stat_before（本函数开头的 ``stat``）→ parse → sha256 → stat_after。
        # 窗口内 size / mtime 变化 ⇒ 本次解析结果与 sha256 整体不提交，下次扫描重来。
        sha256: str | None = None
        if parsed.success:
            try:
                sha256 = sha256_of_file(path)
            except OSError as exc:
                stats.failed += 1
                issues.append(
                    ScanIssue(str(path), STAGE_IO, f"无法读取文件内容：{exc}")
                )
                return

        try:
            stat_after = path.stat()
        except OSError as exc:
            stats.failed += 1
            issues.append(
                ScanIssue(str(path), STAGE_IO, f"无法读取文件信息：{exc}")
            )
            return

        if (
            int(stat_after.st_size) != size
            or abs(float(stat_after.st_mtime) - modified_time) >= _MTIME_EPSILON
        ):
            # C7：文件在读取窗口内被改写 → 不写库、不开事务、不计失败、
            # 不加 issue、不调用 mark_parse_failed，保持数据库中既有状态。
            return

        if not parsed.success:
            stats.failed += 1
            stage = STAGE_NOT_A_RESOURCE if suffix == ".png" else STAGE_PARSE
            if suffix == ".zipmod" or (parsed.error and "manifest.xml" in parsed.error):
                stage = STAGE_NOT_A_RESOURCE
            if parsed.error is None and parsed.warnings:
                stage = STAGE_PARSE
            stats.not_a_resource += 1 if stage == STAGE_NOT_A_RESOURCE else 0
            issues.append(ScanIssue(str(path), stage, parsed.error or "解析失败"))
            if existing is not None:
                # 已入库过的文件这次解不动：保留行，只标记状态
                self.store.mark_parse_failed(int(existing["id"]), parsed.error)
            return

        assert sha256 is not None, "parsed.success 时 sha256 必须已在窗口内计算"
        relative_path = self._relative_path(path, root_path)
        # 作者取自 Parser 的**原始列表**（含 [Unknown] 之类的哨兵）；
        # 哨兵过滤与去重由 store 侧的 partition_authors 负责。
        authors_raw = getattr(parsed, "authors_raw", None)

        # ---- 入库：每个文件一个事务，互不牵连 ----
        try:
            with database.transaction(self.conn):
                if suffix == ".png":
                    _resource_id, outcome = self.store.upsert_card_resource(
                        library_id=library_id,
                        path=path,
                        path_key=path_key,
                        relative_path=relative_path,
                        size=size,
                        modified_time=modified_time,
                        parsed=parsed,
                        authors_raw=authors_raw,
                        sha256=sha256,
                    )
                else:
                    _resource_id, outcome = self.store.upsert_mod_resource(
                        library_id=library_id,
                        path=path,
                        path_key=path_key,
                        relative_path=relative_path,
                        size=size,
                        modified_time=modified_time,
                        parsed=parsed,
                        sha256=sha256,
                    )
        except Exception as exc:  # noqa: BLE001 - 单文件回滚，批次继续
            stats.failed += 1
            issues.append(
                ScanIssue(str(path), STAGE_STORE, f"{type(exc).__name__}: {exc}")
            )
            return

        if outcome == "inserted":
            stats.inserted += 1
        else:
            stats.updated += 1

    # ---- scan_records ---------------------------------------------------

    def _begin_scan_record(self, library_id: int, mode: str) -> int:
        cursor = self.conn.execute(
            "INSERT INTO scan_records(library_id, mode, status) VALUES (?, ?, 'running')",
            (library_id, mode),
        )
        return int(cursor.lastrowid)

    def _finish_scan_record(self, result: ScanResult) -> None:
        if result.scan_record_id is None:
            return
        fields = result.stats.scan_record_fields()
        message = None
        if result.issues:
            head = result.issues[:5]
            message = " | ".join(f"{i.path}: {i.message}" for i in head)
            if len(result.issues) > len(head):
                message += f" | ...（共 {len(result.issues)} 条）"
        self.conn.execute(
            "UPDATE scan_records SET status = ?, finished_at = datetime('now'),"
            " duration_ms = ?, files_seen = ?, files_new = ?, files_changed = ?,"
            " files_skipped = ?, files_missing = ?, files_failed = ?, error_message = ?"
            " WHERE id = ?",
            (
                result.status,
                result.duration_ms,
                fields["files_seen"],
                fields["files_new"],
                fields["files_changed"],
                fields["files_skipped"],
                fields["files_missing"],
                fields["files_failed"],
                message,
                result.scan_record_id,
            ),
        )

    # ---- 工具 -----------------------------------------------------------

    @staticmethod
    def _relative_path(path: Path, root_path: Path) -> str:
        try:
            return str(path.relative_to(root_path))
        except ValueError:
            return str(path)

    def _now(self) -> str:
        row = self.conn.execute("SELECT datetime('now') AS t").fetchone()
        return row["t"]


__all__ = ["CANDIDATE_SUFFIXES", "LibraryScanner", "iter_candidates"]
