"""后台扫描 worker —— Phase 1.5-B。

唯一职责：在**非 GUI 线程**里调用 ``core.app.run_scan()``，把结果通过 Qt 信号
送回 GUI 线程。

严格约束
--------
- 本模块**不**操作任何 QWidget / QAbstractItemModel / QMessageBox；
- **不**自己刷新 Query、**不**缓存扫描结果、**不**做进度 / 取消；
- **不**接收 GUI 线程的 SQLite 连接（连接绑定线程）——只拿 ``db_path``，
  由 ``run_scan()`` 在 worker 线程里自己开、自己关。

线程模型：``QThreadPool`` + ``QRunnable`` + ``QObject`` 信号载体，
与 ``ui/preview_worker.py`` 同构，但刻意**不**与它抽象成通用 Worker。
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from core.app import run_scan


class ScanSignals(QObject):
    """扫描信号载体（在 GUI 线程创建 → 跨线程 emit 走队列连接）。

    ``failed`` 额外带上 ``library_id``：GUI 需要知道是哪一次扫描失败才能清除
    对应的「扫描中」状态（消息本体仍是 ``message``）。
    """

    started = pyqtSignal()
    finished = pyqtSignal(object)          # ScanResult
    failed = pyqtSignal(object, str)       # library_id, message


class ScanWorker(QRunnable):
    """在后台线程扫描一个 Library。"""

    def __init__(
        self,
        db_path,
        library_id: int,
        *,
        mode: str = "incremental",
        signals: ScanSignals | None = None,
    ) -> None:
        super().__init__()
        self._db_path = db_path
        self._library_id = int(library_id)
        self._mode = mode
        self.signals = signals if signals is not None else ScanSignals()
        self.setAutoDelete(True)

    # ---- 只读属性（便于测试与调试） -------------------------------------

    @property
    def db_path(self):
        return self._db_path

    @property
    def library_id(self) -> int:
        return self._library_id

    @property
    def mode(self) -> str:
        return self._mode

    # ---- QRunnable 入口 -------------------------------------------------

    def run(self) -> None:  # noqa: D102 - QRunnable 入口
        self.signals.started.emit()
        try:
            result = run_scan(self._db_path, self._library_id, mode=self._mode)
        except Exception as exc:  # noqa: BLE001 - 任何异常都不能杀死线程 / 界面
            self.signals.failed.emit(
                self._library_id, f"{type(exc).__name__}: {exc}"
            )
            return
        self.signals.finished.emit(result)


__all__ = ["ScanWorker", "ScanSignals"]
