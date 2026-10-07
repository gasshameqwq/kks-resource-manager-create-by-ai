"""后台缩略图 worker —— Phase 1.4-C-3。

唯一职责：在**非 GUI 线程**里调用 ``PreviewService.get_or_generate()``，
并把结果通过 Qt 信号送回 GUI 线程。

严格约束
--------
- 本模块**不**操作任何 QWidget / QAbstractListModel / QPixmap / QListView；
- 不生成 ``QPixmap``（那是 GUI 线程的事），只回传 ``PreviewStatus``（含缓存文件路径）；
- 不做缓存管理、不做调度、不做取消系统（epoch 由 BrowserPanel 判定）。

线程模型：``QThreadPool`` + ``QRunnable`` + 一个 ``QObject`` 信号载体。
项目当前 PyQt6 **没有 QtConcurrent**，因此不使用它。
"""

from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal


# 同一个源文件可能同时被「网格」和「详情」请求；PreviewService 的缓存写入不是
# 互斥的，两个线程同时写同一 cache key 会在 Windows 上触发 os.replace 的
# PermissionError。这里用**按源文件路径**的锁把它们串行化：
# 它不是缓存/管理器，只是一个并发原语（第二个任务随后会命中缓存）。
_LOCKS_GUARD = threading.Lock()
_LOCKS_BY_SOURCE: dict[str, threading.Lock] = {}


def _source_key(source) -> str:
    file_path = getattr(source, "file_path", None)
    return str(file_path) if file_path else str(id(source))


def _lock_for(source) -> threading.Lock:
    key = _source_key(source)
    with _LOCKS_GUARD:
        lock = _LOCKS_BY_SOURCE.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS_BY_SOURCE[key] = lock
        return lock


class PreviewSignals(QObject):
    """信号载体（在 GUI 线程创建 → 跨线程 emit 会走队列连接）。"""

    finished = pyqtSignal(object, object, object)  # resource_id, epoch, PreviewStatus
    failed = pyqtSignal(object, object, object)    # resource_id, epoch, error text


class PreviewWorker(QRunnable):
    """为单个资源生成/读取缩略图的后台任务。"""

    def __init__(
        self,
        preview_service,
        source,
        *,
        epoch: int,
        resource_id: int | None = None,
        signals: PreviewSignals | None = None,
    ) -> None:
        super().__init__()
        self._service = preview_service
        self._source = source
        self._epoch = int(epoch)
        self._resource_id = resource_id if resource_id is not None else getattr(
            source, "id", None
        )
        self.signals = signals if signals is not None else PreviewSignals()
        self.setAutoDelete(True)

    @property
    def resource_id(self):
        return self._resource_id

    @property
    def epoch(self) -> int:
        return self._epoch

    def run(self) -> None:  # noqa: D102 - QRunnable 入口
        try:
            with _lock_for(self._source):
                status = self._service.get_or_generate(self._source)
        except Exception as exc:  # noqa: BLE001 - 任何异常都不能杀死线程/界面
            self.signals.failed.emit(
                self._resource_id, self._epoch, f"{type(exc).__name__}: {exc}"
            )
            return
        self.signals.finished.emit(self._resource_id, self._epoch, status)


__all__ = ["PreviewWorker", "PreviewSignals"]
