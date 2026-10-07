"""Phase 1.5-B：后台扫描（ScanWorker / GUI 接线 / 刷新 / 竞态防护）测试。

全程离屏（``QT_QPA_PLATFORM=offscreen``），只使用临时数据库 + 临时目录 + 临时缓存，
不使用真实样本、不污染 ``data/``。

策略：

- **worker 层**直接测 ``run_scan`` / ``ScanWorker``（含连接线程与关闭）。
- **GUI 层**用可控的 ``run_scan`` 替身（阻塞在 ``threading.Event`` 上）来稳定地
  制造「扫描中」窗口，验证按钮禁用、重复启动、切换 Library、Remove 防护、刷新链。
"""

from __future__ import annotations

import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QObject, QThreadPool  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.app import run_scan  # noqa: E402
import core.app.admin as admin_module  # noqa: E402
from core.database import db as database  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.query import BrowseService  # noqa: E402
from core.scanner import RESULT_SKIPPED, SCAN_COMPLETED, ScanResult  # noqa: E402
from core.thumbnails import PreviewService  # noqa: E402
from tests.builders import write_card  # noqa: E402
import ui.library_panel as library_panel_module  # noqa: E402
import ui.main_window as main_window_module  # noqa: E402
import ui.scan_worker as scan_worker_module  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.scan_worker import ScanSignals, ScanWorker  # noqa: E402


# ---------------------------------------------------------------------------
# 夹具 / 工具
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def db_file(tmp_path: Path) -> Path:
    path = tmp_path / "scan.db"
    database.initialize(path)
    return path


@pytest.fixture()
def conn(db_file: Path):
    connection = database.connect(db_file)
    yield connection
    connection.close()


@pytest.fixture()
def lib_dir(tmp_path: Path) -> Path:
    path = tmp_path / "KKS Cards"
    path.mkdir()
    return path


@pytest.fixture()
def other_dir(tmp_path: Path) -> Path:
    path = tmp_path / "KKS Mods"
    path.mkdir()
    return path


@pytest.fixture()
def window(qapp, conn, tmp_path: Path, monkeypatch):
    # 安全网：万一测试结束时仍有扫描在跑，关窗不要弹出阻塞对话框。
    monkeypatch.setattr(
        main_window_module, "confirm_close_during_scan", lambda parent: True
    )
    monkeypatch.setattr(
        main_window_module, "confirm_keep_waiting", lambda parent: False
    )
    w = MainWindow(BrowseService(conn), PreviewService(cache_dir=tmp_path / "cache"))
    yield w
    w.wait_for_scans(5000)
    w.close()


class _Collector(QObject):
    """接收 worker 信号的 QObject（保证跨线程走队列连接）。"""

    def __init__(self) -> None:
        super().__init__()
        self.started = 0
        self.finished: list = []
        self.failed: list = []

    def on_started(self) -> None:
        self.started += 1

    def on_finished(self, result) -> None:
        self.finished.append(result)

    def on_failed(self, library_id, message) -> None:
        self.failed.append((library_id, message))


class ControlledScan:
    """``run_scan`` 的可控替身：阻塞直到测试 ``release``，便于观察「扫描中」。"""

    def __init__(self, factory) -> None:
        self._factory = factory
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls: list[tuple] = []

    def __call__(self, db_path, library_id, *, mode="incremental"):
        self.calls.append((db_path, library_id, mode))
        self.started.set()
        self.release.wait(10)
        return self._factory(library_id, mode)


def _completed(library_id, mode, **stats):
    from core.scanner import ScanStats

    return ScanResult(
        library_id=library_id,
        mode=mode,
        status=SCAN_COMPLETED,
        stats=ScanStats(**stats),
    )


def _count(conn, table: str) -> int:
    return conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"]


# ---------------------------------------------------------------------------
# Worker 层
# ---------------------------------------------------------------------------


def test_run_scan_incremental_success(db_file, conn, lib_dir: Path) -> None:
    library = LibraryStore(conn).add(lib_dir)
    write_card(lib_dir / "a.png", lastname="測試")

    result = run_scan(db_file, library.id, mode="incremental")

    assert result.status == SCAN_COMPLETED
    assert result.stats.discovered == 1
    assert result.stats.inserted == 1
    assert _count(conn, "resources") == 1


def test_run_scan_full_success(db_file, conn, lib_dir: Path) -> None:
    library = LibraryStore(conn).add(lib_dir)
    write_card(lib_dir / "a.png", lastname="測試")

    run_scan(db_file, library.id, mode="incremental")
    result = run_scan(db_file, library.id, mode="full")

    assert result.status == SCAN_COMPLETED
    # full 忽略增量捷径：同一个文件重新解析 → updated
    assert result.stats.updated == 1
    assert result.stats.skipped == 0
    assert _count(conn, "resources") == 1


def test_run_scan_second_incremental_skips(db_file, conn, lib_dir: Path) -> None:
    library = LibraryStore(conn).add(lib_dir)
    write_card(lib_dir / "a.png", lastname="測試")

    run_scan(db_file, library.id, mode="incremental")
    result = run_scan(db_file, library.id, mode="incremental")

    assert result.stats.skipped == 1
    assert result.stats.inserted == 0
    assert _count(conn, "resources") == 1  # 无重复资源


def test_scan_worker_failed_emits(db_file: Path) -> None:
    collector = _Collector()
    worker = ScanWorker(db_file, 999999, mode="incremental")
    worker.signals.failed.connect(collector.on_failed)

    worker.run()  # 同步执行（本线程）

    assert collector.failed, "未知 Library 必须 emit failed"
    library_id, message = collector.failed[0]
    assert library_id == 999999
    assert message
    assert collector.finished == []


def test_scan_worker_finished_emits(db_file, conn, lib_dir: Path) -> None:
    library = LibraryStore(conn).add(lib_dir)
    collector = _Collector()
    worker = ScanWorker(db_file, library.id, mode="incremental")
    worker.signals.started.connect(collector.on_started)
    worker.signals.finished.connect(collector.on_finished)

    worker.run()

    assert collector.started == 1
    assert len(collector.finished) == 1
    assert collector.finished[0].status == SCAN_COMPLETED
    assert collector.failed == []


def test_run_scan_closes_its_connection(monkeypatch, db_file: Path) -> None:
    record: dict = {}

    class FakeScanner:
        def __init__(self, connection) -> None:
            record["conn"] = connection
            record["alive"] = connection.execute("SELECT 1").fetchone() is not None

        def scan(self, library_id, *, mode="incremental"):
            record["scanned"] = (library_id, mode)
            return ScanResult(library_id=library_id, mode=mode, status=SCAN_COMPLETED)

    monkeypatch.setattr(admin_module, "LibraryScanner", FakeScanner)

    result = run_scan(db_file, 7, mode="full")

    assert result.status == SCAN_COMPLETED
    assert record["alive"] is True
    assert record["scanned"] == (7, "full")
    # 连接必须已关闭（run_scan 的 finally）
    with pytest.raises(sqlite3.ProgrammingError):
        record["conn"].execute("SELECT 1")


def test_scan_worker_uses_own_thread_connection(
    qapp, monkeypatch, db_file: Path
) -> None:
    main_thread = threading.get_ident()
    record: dict = {}

    class FakeScanner:
        def __init__(self, connection) -> None:
            record["thread"] = threading.get_ident()

        def scan(self, library_id, *, mode="incremental"):
            return ScanResult(library_id=library_id, mode=mode, status=SCAN_COMPLETED)

    monkeypatch.setattr(admin_module, "LibraryScanner", FakeScanner)

    collector = _Collector()
    worker = ScanWorker(db_file, 1, mode="incremental")
    worker.signals.finished.connect(collector.on_finished)
    QThreadPool.globalInstance().start(worker)
    assert QThreadPool.globalInstance().waitForDone(10000)
    # 队列连接：等事件循环把 worker 线程 emit 的信号投递到主线程
    deadline = time.monotonic() + 5
    while not collector.finished and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)

    # 连接是在 worker 线程里创建的，而不是复用 GUI / 主线程的连接
    assert record["thread"] != main_thread
    assert len(collector.finished) == 1


# ---------------------------------------------------------------------------
# GUI：启动扫描
# ---------------------------------------------------------------------------


def test_scan_button_starts_incremental_worker(monkeypatch, window, db_file, lib_dir):
    library = window.library_panel.add_library(str(lib_dir))
    ctrl = ControlledScan(lambda lid, mode: _completed(lid, mode, inserted=0))
    monkeypatch.setattr(scan_worker_module, "run_scan", ctrl)

    window.library_panel.scan_button.click()

    assert ctrl.started.wait(5)
    assert window.is_scanning(library.id)
    assert ctrl.calls[0][0] == str(db_file)   # 用的是注入连接的数据库路径
    assert ctrl.calls[0][2] == "incremental"
    ctrl.release.set()
    window.wait_for_scans(10000)
    assert not window.is_scanning(library.id)


def test_full_scan_button_starts_full_worker(monkeypatch, window, lib_dir):
    library = window.library_panel.add_library(str(lib_dir))
    ctrl = ControlledScan(lambda lid, mode: _completed(lid, mode))
    monkeypatch.setattr(scan_worker_module, "run_scan", ctrl)

    window.library_panel.full_scan_button.click()

    assert ctrl.started.wait(5)
    assert ctrl.calls[0][2] == "full"
    ctrl.release.set()
    window.wait_for_scans(10000)


def test_add_library_does_not_auto_scan(window, conn, lib_dir) -> None:
    write_card(lib_dir / "a.png", lastname="測試")
    window.library_panel.add_library(str(lib_dir))

    assert window.scanning_library_ids() == set()
    assert _count(conn, "scan_records") == 0
    assert _count(conn, "resources") == 0


# ---------------------------------------------------------------------------
# GUI：扫描期间状态
# ---------------------------------------------------------------------------


def test_buttons_disabled_while_scanning(monkeypatch, window, lib_dir) -> None:
    library = window.library_panel.add_library(str(lib_dir))
    ctrl = ControlledScan(lambda lid, mode: _completed(lid, mode))
    monkeypatch.setattr(scan_worker_module, "run_scan", ctrl)

    window.library_panel.scan_button.click()
    assert ctrl.started.wait(5)

    assert not window.library_panel.scan_button.isEnabled()
    assert not window.library_panel.full_scan_button.isEnabled()
    assert not window.library_panel.remove_button.isEnabled()
    assert "[扫描中…]" in window.library_panel.item_text(0)
    assert window.library_panel.scan_status_text() == "扫描中…"

    ctrl.release.set()
    window.wait_for_scans(10000)
    assert window.library_panel.scan_button.isEnabled()
    assert window.library_panel.remove_button.isEnabled()
    assert "[扫描中…]" not in window.library_panel.item_text(0)


def test_same_library_cannot_start_two_scans(monkeypatch, window, lib_dir) -> None:
    library = window.library_panel.add_library(str(lib_dir))
    ctrl = ControlledScan(lambda lid, mode: _completed(lid, mode))
    monkeypatch.setattr(scan_worker_module, "run_scan", ctrl)

    window.library_panel.scan_button.click()
    assert ctrl.started.wait(5)

    assert window.start_scan("incremental") is None   # 重复启动被忽略（不排队）
    assert len(ctrl.calls) == 1
    assert window.scanning_library_ids() == {library.id}

    ctrl.release.set()
    window.wait_for_scans(10000)


def test_can_browse_other_library_while_scanning(monkeypatch, window, lib_dir, other_dir):
    lib_a = window.library_panel.add_library(str(lib_dir), name="A")
    lib_b = window.library_panel.add_library(str(other_dir), name="B")
    window.library_panel.reload(select=lib_a.id)
    ctrl = ControlledScan(lambda lid, mode: _completed(lid, mode))
    monkeypatch.setattr(scan_worker_module, "run_scan", ctrl)

    window.start_scan("incremental")
    assert ctrl.started.wait(5)

    window.library_panel.reload(select=lib_b.id)      # 切到 B

    assert window.library_panel.current_library_id() == lib_b.id
    assert window.is_scanning(lib_a.id)               # A 仍在扫描
    # 单扫描策略：A 在扫描时，任何 Library 的扫描按钮都禁用
    assert not window.library_panel.scan_button.isEnabled()
    # 但 B 可以正常浏览（只读）
    assert window.browser_panel.scope().library_id == lib_b.id

    ctrl.release.set()
    window.wait_for_scans(10000)
    assert not window.is_scanning(lib_a.id)


def test_finished_clears_scanning_state(monkeypatch, window, lib_dir) -> None:
    library = window.library_panel.add_library(str(lib_dir))
    ctrl = ControlledScan(lambda lid, mode: _completed(lid, mode))
    monkeypatch.setattr(scan_worker_module, "run_scan", ctrl)

    window.start_scan("incremental")
    assert ctrl.started.wait(5)
    ctrl.release.set()
    window.wait_for_scans(10000)

    assert not window.is_scanning(library.id)
    assert window.scanning_library_ids() == set()
    assert "扫描完成" in window.library_panel.scan_status_text()


def test_failed_clears_state_and_restores_buttons(monkeypatch, window, lib_dir) -> None:
    library = window.library_panel.add_library(str(lib_dir))

    def boom(db_path, library_id, *, mode="incremental"):
        raise RuntimeError("disk exploded")

    monkeypatch.setattr(scan_worker_module, "run_scan", boom)

    window.start_scan("incremental")
    window.wait_for_scans(10000)

    assert not window.is_scanning(library.id)
    assert window.library_panel.scan_button.isEnabled()
    assert window.library_panel.full_scan_button.isEnabled()
    text = window.library_panel.scan_status_text()
    assert "扫描失败" in text and "disk exploded" in text


def test_skipped_is_not_treated_as_completed(monkeypatch, window, conn, lib_dir) -> None:
    library = window.library_panel.add_library(str(lib_dir), enabled=False)

    def skipped(db_path, library_id, *, mode="incremental"):
        return ScanResult(
            library_id=library_id,
            mode=mode,
            status=RESULT_SKIPPED,
            skip_reason="Library 已暂停（enabled=0），未执行扫描",
        )

    monkeypatch.setattr(scan_worker_module, "run_scan", skipped)

    window.start_scan("incremental")
    window.wait_for_scans(10000)

    assert not window.is_scanning(library.id)
    assert window.library_panel.scan_button.isEnabled()
    text = window.library_panel.scan_status_text()
    assert "未扫描" in text and "暂停" in text
    assert _count(conn, "scan_records") == 0


# ---------------------------------------------------------------------------
# GUI：Remove 与扫描的竞态
# ---------------------------------------------------------------------------


def test_cannot_remove_scanning_library(monkeypatch, window, conn, lib_dir) -> None:
    library = window.library_panel.add_library(str(lib_dir))
    ctrl = ControlledScan(lambda lid, mode: _completed(lid, mode))
    monkeypatch.setattr(scan_worker_module, "run_scan", ctrl)
    monkeypatch.setattr(library_panel_module, "confirm_remove", lambda parent, report: True)
    infos: list = []
    monkeypatch.setattr(
        library_panel_module.QMessageBox, "information", lambda *a, **k: infos.append(a)
    )

    window.start_scan("incremental")
    assert ctrl.started.wait(5)

    # 按钮已禁用……
    assert not window.library_panel.remove_button.isEnabled()
    # ……但真正的护栏在操作层：直接调用也必须被拦下（不只依赖按钮禁用）
    window.library_panel._on_remove_clicked()  # noqa: SLF001 - 验证显式竞态防护
    assert _count(conn, "libraries") == 1
    assert infos, "必须给出「正在扫描」的明确提示"
    assert "扫描" in infos[0][2]

    ctrl.release.set()
    window.wait_for_scans(10000)
    # 扫描结束后可以正常移除
    window.library_panel.remove_button.click()
    assert _count(conn, "libraries") == 0


def test_remove_other_library_while_scanning(
    monkeypatch, window, conn, lib_dir, other_dir
) -> None:
    lib_a = window.library_panel.add_library(str(lib_dir), name="A")
    lib_b = window.library_panel.add_library(str(other_dir), name="B")
    window.library_panel.reload(select=lib_a.id)
    ctrl = ControlledScan(lambda lid, mode: _completed(lid, mode))
    monkeypatch.setattr(scan_worker_module, "run_scan", ctrl)
    monkeypatch.setattr(library_panel_module, "confirm_remove", lambda parent, report: True)

    window.start_scan("incremental")   # 扫 A
    assert ctrl.started.wait(5)

    window.library_panel.reload(select=lib_b.id)
    assert window.library_panel.remove_button.isEnabled()   # B 未在扫描 → 可移除
    window.library_panel.remove_button.click()
    assert _count(conn, "libraries") == 1                    # B 已移除，A 仍存在

    ctrl.release.set()
    window.wait_for_scans(10000)
    assert not window.is_scanning(lib_a.id)
    assert lib_a.id == conn.execute("SELECT id FROM libraries").fetchone()["id"]


# ---------------------------------------------------------------------------
# GUI：扫描完成后的统一刷新
# ---------------------------------------------------------------------------


def test_scan_refreshes_library_count_and_browse(window, conn, lib_dir) -> None:
    write_card(lib_dir / "a.png", lastname="測試")
    window.library_panel.add_library(str(lib_dir))
    assert window.library_panel.item_text(0) == "KKS Cards (0)"
    assert window.browser_panel.total() == 0

    window.start_scan("incremental")
    window.wait_for_scans(10000)

    # 左栏计数 + 中栏列表都重新从 Query Layer 读取
    assert window.library_panel.item_text(0) == "KKS Cards (1)"
    assert window.browser_panel.total() == 1
    assert window.browser_panel.model.rowCount() == 1
    assert _count(conn, "resources") == 1


def test_scan_refreshes_relation_options(window, conn, lib_dir) -> None:
    write_card(
        lib_dir / "a.png",
        lastname="測試",
        dependencies=(("com.example.missing", "outfit6", 0),),
        authors=("Evaan",),
        plugin_guids=(),
    )
    window.library_panel.add_library(str(lib_dir))

    # 扫描前：关系下拉只有「全部」占位
    assert window.browser_panel.filter_bar.author_combo.count() == 1
    assert window.browser_panel.filter_bar.mod_combo.count() == 1

    window.start_scan("incremental")
    window.wait_for_scans(10000)

    # 扫描后：作者与缺失 MOD 下拉被重新读取
    assert window.browser_panel.filter_bar.author_combo.count() == 2
    assert window.browser_panel.filter_bar.mod_combo.count() == 2


def test_scan_keeps_current_selection(monkeypatch, window, lib_dir, other_dir) -> None:
    lib_a = window.library_panel.add_library(str(lib_dir), name="A")
    lib_b = window.library_panel.add_library(str(other_dir), name="B")
    window.library_panel.reload(select=lib_a.id)
    ctrl = ControlledScan(lambda lid, mode: _completed(lid, mode))
    monkeypatch.setattr(scan_worker_module, "run_scan", ctrl)

    window.start_scan("incremental")   # 扫描 A
    assert ctrl.started.wait(5)
    window.library_panel.reload(select=lib_b.id)   # 用户切到 B
    ctrl.release.set()
    window.wait_for_scans(10000)

    # 扫描完成后不强制切回 A，保持用户当前选择 B
    assert window.library_panel.current_library_id() == lib_b.id
    assert window.browser_panel.scope().library_id == lib_b.id


# ---------------------------------------------------------------------------
# GUI：关窗时的扫描生命周期（closeEvent）
# ---------------------------------------------------------------------------


def test_close_cancelled_keeps_scanning(monkeypatch, window, lib_dir) -> None:
    library = window.library_panel.add_library(str(lib_dir))
    ctrl = ControlledScan(lambda lid, mode: _completed(lid, mode))
    monkeypatch.setattr(scan_worker_module, "run_scan", ctrl)
    monkeypatch.setattr(main_window_module, "confirm_close_during_scan", lambda parent: False)
    window.show()

    window.start_scan("incremental")
    assert ctrl.started.wait(5)
    window.close()

    assert window.isVisible()                # 取消 → 窗口未关闭
    assert window.is_scanning(library.id)    # 扫描继续

    ctrl.release.set()
    window.wait_for_scans(10000)


def test_close_waits_for_scan_then_closes(monkeypatch, window, lib_dir) -> None:
    window.library_panel.add_library(str(lib_dir))
    ctrl = ControlledScan(lambda lid, mode: _completed(lid, mode))
    monkeypatch.setattr(scan_worker_module, "run_scan", ctrl)
    monkeypatch.setattr(main_window_module, "confirm_close_during_scan", lambda parent: True)
    window.show()

    window.start_scan("incremental")
    assert ctrl.started.wait(5)
    ctrl.release.set()
    window.close()

    assert not window.isVisible()
    assert ctrl.calls, "worker 确实运行过"
