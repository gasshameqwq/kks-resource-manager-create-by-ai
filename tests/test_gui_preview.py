"""Phase 1.4-C-3：Preview / Thumbnail 异步加载测试。

全程离屏；只使用临时数据库 + 临时图片文件 + 临时 preview 缓存目录。
真实样本不参与本文件的 pytest。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QThread, Qt  # noqa: E402
from PyQt6.QtGui import QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.query import BrowseService, ResourceListItem, ResourceSummary  # noqa: E402
from core.thumbnails import (  # noqa: E402
    PREVIEW_READY as CORE_READY,
    PreviewService,
    PreviewStatus,
)
from tests.builders import tiny_png, write_card  # noqa: E402
from ui.browser_panel import BrowserPanel  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.preview_worker import PreviewWorker  # noqa: E402
from ui.resource_model import (  # noqa: E402
    PREVIEW_FAILED,
    PREVIEW_LOADING,
    PREVIEW_MISSING,
    PREVIEW_READY,
    PREVIEW_UNREQUESTED,
    PREVIEW_UNSUPPORTED,
    ResourceListModel,
    placeholder_pixmap,
)


# ---------------------------------------------------------------------------
# 夹具 / 构造器
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def assets(tmp_path: Path):
    """真实图片文件：合法卡片 PNG / 损坏 PNG / 不存在的路径 / 临时缓存目录。"""
    cards = tmp_path / "cards"
    cards.mkdir()
    good = cards / "good.png"
    write_card(good, lastname="Good")
    bad = cards / "bad.png"
    bad.write_bytes(b"this is not an image")
    return {
        "good": good,
        "bad": bad,
        "missing": cards / "nope.png",
        "cache": tmp_path / "preview_cache",
    }


@pytest.fixture()
def conn(tmp_path: Path, assets):
    db_file = tmp_path / "preview.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    connection.execute(
        "INSERT INTO libraries(id, name, root_path, root_path_key)"
        " VALUES (1, 'L', 'D:/l', 'd:/l')"
    )
    yield connection
    connection.close()


def _add_resource(
    conn,
    resource_id: int,
    *,
    name: str,
    path: Path,
    extension: str,
    resource_type: str = "character_card",
    library_id: int = 1,
) -> None:
    conn.execute(
        "INSERT INTO resources(id, resource_type, name, display_name, file_path,"
        " file_path_key, extension, library_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            resource_id,
            resource_type,
            name,
            name,
            str(path),
            str(path).casefold(),
            extension,
            library_id,
        ),
    )


@pytest.fixture()
def seeded(conn, assets):
    """4 个资源：正常卡片 / zipmod(不支持) / 损坏图片(失败) / 源文件缺失。"""
    _add_resource(conn, 1, name="Good", path=assets["good"], extension=".png")
    _add_resource(
        conn,
        2,
        name="SomeMod",
        path=assets["good"].parent / "m.zipmod",
        extension=".zipmod",
        resource_type="mod",
    )
    _add_resource(conn, 3, name="Bad", path=assets["bad"], extension=".png")
    _add_resource(conn, 4, name="Missing", path=assets["missing"], extension=".png")
    return conn


@pytest.fixture()
def preview_service(assets):
    return PreviewService(cache_dir=assets["cache"])


@pytest.fixture()
def window(qapp, seeded, preview_service):
    w = MainWindow(BrowseService(seeded), preview_service)
    yield w
    w.close()


@pytest.fixture()
def browser(window) -> BrowserPanel:
    return window.browser_panel


# ---------------------------------------------------------------------------
# status() 映射与占位图
# ---------------------------------------------------------------------------


def test_status_mapping_right_after_reload(browser) -> None:
    states = {
        i.resource.id: browser.model.preview_state(i.resource.id)
        for i in browser.model.items()
    }
    assert states[1] == PREVIEW_LOADING
    assert states[2] == PREVIEW_UNSUPPORTED
    assert states[3] == PREVIEW_LOADING
    assert states[4] == PREVIEW_MISSING
    assert browser.pending_preview_count() == 2
    assert browser.is_preview_pending(1) and browser.is_preview_pending(3)
    assert not browser.is_preview_pending(2) and not browser.is_preview_pending(4)


def test_generation_finishes_ready_or_failed(browser, assets) -> None:
    assert browser.wait_for_previews()
    assert browser.pending_preview_count() == 0
    assert browser.model.preview_state(1) == PREVIEW_READY
    pixmap = browser.model.preview_pixmap(1)
    assert pixmap is not None and not pixmap.isNull()
    assert browser.model.preview_state(2) == PREVIEW_UNSUPPORTED
    assert browser.model.preview_state(3) == PREVIEW_FAILED
    assert browser.model.preview_state(4) == PREVIEW_MISSING
    assert len(list(assets["cache"].glob("*.webp"))) == 1


def test_ready_cache_hit_skips_worker(qapp, tmp_path, assets) -> None:
    service = PreviewService(cache_dir=assets["cache"])
    db_file = tmp_path / "cachehit.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        conn.execute(
            "INSERT INTO libraries(id, name, root_path, root_path_key)"
            " VALUES (1, 'L', 'D:/l', 'd:/l')"
        )
        _add_resource(conn, 1, name="Good", path=assets["good"], extension=".png")
        first = MainWindow(BrowseService(conn), service)
        try:
            assert first.browser_panel.wait_for_previews()
            assert first.browser_panel.model.preview_state(1) == PREVIEW_READY
        finally:
            first.close()

        second = MainWindow(BrowseService(conn), service)
        try:
            assert second.browser_panel.model.preview_state(1) == PREVIEW_READY
            assert second.browser_panel.pending_preview_count() == 0
        finally:
            second.close()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Model：DecorationRole / 占位图 / 局部刷新
# ---------------------------------------------------------------------------


def _make_model() -> ResourceListModel:
    items = []
    for i in (1, 2, 3):
        summary = ResourceSummary(
            id=i,
            resource_type="character_card",
            name=f"n{i}",
            display_name=f"n{i}",
            file_path=f"D:/{i}.png",
            relative_path=None,
            extension=".png",
            card_marker=None,
            file_size=None,
            modified_time=None,
            library_id=1,
            scan_status="present",
            parse_status="ok",
            needs_review=False,
        )
        items.append(ResourceListItem(resource=summary, library_name="L", authors=()))
    model = ResourceListModel()
    model.set_items(items)
    return model


def test_decoration_role_returns_placeholders(qapp) -> None:
    model = _make_model()
    pixmap = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole)
    assert pixmap is not None and not pixmap.isNull()
    assert placeholder_pixmap(PREVIEW_UNREQUESTED) is placeholder_pixmap(PREVIEW_UNREQUESTED)


def test_decoration_role_loading_failed_unsupported(qapp) -> None:
    model = _make_model()
    index = model.index(0, 0)
    for state in (PREVIEW_LOADING, PREVIEW_FAILED, PREVIEW_UNSUPPORTED, PREVIEW_MISSING):
        model.set_preview_state(1, state)
        pixmap = model.data(index, Qt.ItemDataRole.DecorationRole)
        assert pixmap is not None and not pixmap.isNull(), state


def test_decoration_role_ready_returns_pixmap(qapp, tmp_path) -> None:
    model = _make_model()
    pixmap_file = tmp_path / "pix.png"
    pixmap_file.write_bytes(tiny_png())
    loaded = QPixmap(str(pixmap_file))
    model.set_preview_state(1, PREVIEW_READY, loaded)
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole) is loaded
    assert model.preview_pixmap(1) is loaded


def test_set_preview_state_refreshes_single_row_only(qapp) -> None:
    model = _make_model()
    changes: list[tuple[int, int, list]] = []
    resets: list[int] = []
    model.dataChanged.connect(
        lambda tl, br, roles=None: changes.append((tl.row(), br.row(), list(roles or [])))
    )
    model.modelAboutToBeReset.connect(lambda: resets.append(1))

    model.set_preview_state(2, PREVIEW_LOADING)

    assert changes == [
        (1, 1, [Qt.ItemDataRole.DecorationRole, Qt.ItemDataRole.ToolTipRole])
    ]
    assert resets == [], "刷新单个 preview 不得 reset 整个 model"


def test_set_preview_state_for_unknown_resource_is_noop(qapp) -> None:
    model = _make_model()
    changes: list[int] = []
    model.dataChanged.connect(lambda *a: changes.append(1))
    model.set_preview_state(999, PREVIEW_LOADING)
    assert changes == []


# ---------------------------------------------------------------------------
# Worker：同步调用（不涉及线程）
# ---------------------------------------------------------------------------


class _FakePreviewService:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self.calls: list[object] = []
        self._result = result
        self._error = error

    def get_or_generate(self, source):
        self.calls.append(source)
        if self._error is not None:
            raise self._error
        return self._result


def test_worker_calls_service_and_emits_finished(qapp) -> None:
    status = PreviewStatus(CORE_READY, "key", None)
    service = _FakePreviewService(result=status)
    worker = PreviewWorker(service, object(), epoch=3, resource_id=7)
    received: list[tuple] = []
    worker.signals.finished.connect(lambda *args: received.append(args))

    worker.run()

    assert len(service.calls) == 1
    assert received == [(7, 3, status)]
    assert worker.epoch == 3 and worker.resource_id == 7


def test_worker_emits_failed_on_exception(qapp) -> None:
    service = _FakePreviewService(error=RuntimeError("boom"))
    worker = PreviewWorker(service, object(), epoch=1, resource_id=5)
    failures: list[tuple] = []
    worker.signals.failed.connect(lambda *args: failures.append(args))

    worker.run()  # 不得抛出

    assert len(failures) == 1
    assert failures[0][0] == 5 and failures[0][1] == 1
    assert "boom" in failures[0][2]


def test_worker_module_has_no_gui_objects() -> None:
    import ui.preview_worker as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    import_lines = [
        line
        for line in source.splitlines()
        if line.startswith("from ") or line.startswith("import ")
    ]
    joined = "\n".join(import_lines)
    # worker 不得引入任何 GUI 模块（因此不可能碰 QWidget / QPixmap / model）
    assert "QtGui" not in joined, "worker 不得 import QtGui"
    assert "QtWidgets" not in joined, "worker 不得 import QtWidgets"
    assert "dataChanged" not in source


def test_preview_generation_only_in_worker() -> None:
    ui_dir = Path(__file__).resolve().parent.parent / "ui"
    for path in sorted(ui_dir.glob("*.py")):
        if path.name == "preview_worker.py":
            continue
        source = path.read_text(encoding="utf-8")
        assert "get_or_generate" not in source, (
            f"{path.name} 不得在 GUI 线程调用 get_or_generate"
        )


# ---------------------------------------------------------------------------
# epoch 防串图
# ---------------------------------------------------------------------------


def test_reload_increments_epoch(browser) -> None:
    browser.wait_for_previews()
    before = browser.preview_epoch()
    browser.reload()
    assert browser.preview_epoch() == before + 1
    browser.wait_for_previews()


def test_stale_epoch_result_is_discarded(browser, assets) -> None:
    browser.wait_for_previews()
    model = browser.model
    stale_epoch = browser.preview_epoch() - 1
    ready = PreviewStatus(CORE_READY, "key", assets["good"])

    model.set_preview_state(1, PREVIEW_LOADING)
    browser._on_preview_finished(1, stale_epoch, ready)  # noqa: SLF001 - 过期结果
    assert model.preview_state(1) == PREVIEW_LOADING, "过期结果不得写入"

    browser._on_preview_finished(1, browser.preview_epoch(), ready)  # noqa: SLF001
    assert model.preview_state(1) == PREVIEW_READY, "当前 epoch 结果应当写入"


def test_stale_failed_result_is_discarded(browser) -> None:
    browser.wait_for_previews()
    model = browser.model
    stale_epoch = browser.preview_epoch() - 1
    model.set_preview_state(1, PREVIEW_LOADING)
    browser._on_preview_failed(1, stale_epoch, "boom")  # noqa: SLF001
    assert model.preview_state(1) == PREVIEW_LOADING


def test_stale_result_does_not_leak_into_new_filter_result(
    qapp, tmp_path, assets
) -> None:
    db_file = tmp_path / "filter.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        conn.execute(
            "INSERT INTO libraries(id, name, root_path, root_path_key)"
            " VALUES (1, 'L', 'D:/l', 'd:/l')"
        )
        _add_resource(conn, 1, name="Good", path=assets["good"], extension=".png")
        _add_resource(conn, 2, name="Other", path=assets["missing"], extension=".png")
        w = MainWindow(BrowseService(conn), PreviewService(cache_dir=assets["cache"]))
        try:
            bp = w.browser_panel
            assert bp.wait_for_previews()
            old_epoch = bp.preview_epoch()
            assert bp.model.preview_state(1) == PREVIEW_READY

            fb = bp.filter_bar
            fb.set_query("Other")
            fb.flush_search()
            assert [i.resource.id for i in bp.model.items()] == [2]
            assert bp.preview_epoch() == old_epoch + 1

            # 旧 epoch 的结果即使到达也不能写进新列表
            ready = PreviewStatus(CORE_READY, "key", assets["good"])
            bp._on_preview_finished(1, old_epoch, ready)  # noqa: SLF001
            assert bp.model.preview_state(1) != PREVIEW_READY
            bp.wait_for_previews()
        finally:
            w.close()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 重复任务保护
# ---------------------------------------------------------------------------


def test_same_resource_epoch_is_not_submitted_twice(browser) -> None:
    browser.wait_for_previews()
    # 用 #3（损坏图片）：它每次都会失败、不会产生缓存，因此每次都会真的提交 worker
    browser.model.set_preview_state(3, PREVIEW_UNREQUESTED)
    item = next(i for i in browser.model.items() if i.resource.id == 3)

    browser._start_preview(item.resource)  # noqa: SLF001 - 第一次
    assert browser.is_preview_pending(3)
    pending = browser.pending_preview_count()

    browser._start_preview(item.resource)  # noqa: SLF001 - 第二次应被挡住
    assert browser.pending_preview_count() == pending
    assert browser.model.preview_state(3) == PREVIEW_LOADING

    browser.wait_for_previews()
    assert browser.model.preview_state(3) == PREVIEW_FAILED


# ---------------------------------------------------------------------------
# Load More：只为新 items 调度
# ---------------------------------------------------------------------------


def test_load_more_only_schedules_new_items(qapp, tmp_path, assets) -> None:
    db_file = tmp_path / "loadmore.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        conn.execute(
            "INSERT INTO libraries(id, name, root_path, root_path_key)"
            " VALUES (1, 'L', 'D:/l', 'd:/l')"
        )
        for i in range(1, 151):
            _add_resource(
                conn,
                i,
                name=f"Card{i:03d}",
                path=assets["missing"].parent / f"nope{i}.png",
                extension=".png",
            )

        service = PreviewService(cache_dir=assets["cache"])
        asked: list[int] = []
        real_status = service.status

        def spy_status(source):
            asked.append(source.id)
            return real_status(source)

        service.status = spy_status  # type: ignore[method-assign]

        w = MainWindow(BrowseService(conn), service)
        try:
            bp = w.browser_panel
            assert bp.total() == 150 and bp.shown() == 100
            first_page = set(asked)
            assert len(first_page) == 100
            assert bp.wait_for_previews()

            asked.clear()
            bp.click_load_more()
            assert bp.shown() == 150
            assert set(asked) == set(range(101, 151)), "只应为新增的 50 条调度 preview"
            assert not (set(asked) & first_page)
            bp.wait_for_previews()
        finally:
            w.close()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 线程边界
# ---------------------------------------------------------------------------


def test_generation_happens_off_gui_thread(qapp, seeded, preview_service) -> None:
    # 必须先装 spy、再构造窗口（构造时才会调度 preview）
    seen: list[object] = []
    real = preview_service.get_or_generate

    def spy(source):
        seen.append(QThread.currentThread())
        return real(source)

    preview_service.get_or_generate = spy  # type: ignore[method-assign]
    w = MainWindow(BrowseService(seeded), preview_service)
    try:
        w.browser_panel.wait_for_previews()
    finally:
        w.close()

    assert seen, "应当至少有一个后台生成任务"
    assert all(t is not qapp.thread() for t in seen), "get_or_generate 不得在 GUI 线程执行"


def test_pixmap_loaded_on_gui_thread(qapp, seeded, preview_service) -> None:
    threads: list[object] = []
    real = BrowserPanel._load_pixmap

    def spy(path):
        threads.append(QThread.currentThread())
        return real(path)

    BrowserPanel._load_pixmap = staticmethod(spy)  # type: ignore[assignment]
    w = None
    try:
        w = MainWindow(BrowseService(seeded), preview_service)
        w.browser_panel.wait_for_previews()
    finally:
        if w is not None:
            w.close()
        BrowserPanel._load_pixmap = staticmethod(real)  # type: ignore[assignment]

    assert threads, "应当有 QPixmap 加载"
    assert all(t is qapp.thread() for t in threads), "QPixmap 必须在 GUI 线程创建"


# ---------------------------------------------------------------------------
# 只读不变量（数据库只读；preview 缓存文件允许写入）
# ---------------------------------------------------------------------------


def test_preview_does_not_write_database(seeded, qapp, preview_service) -> None:
    conn = seeded
    before_changes = conn.total_changes
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))
    before_flags = {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    }

    w = MainWindow(BrowseService(conn), preview_service)
    try:
        w.browser_panel.wait_for_previews()
        w.browser_panel.reload()
        w.browser_panel.wait_for_previews()
    finally:
        w.close()

    assert conn.total_changes == before_changes, "preview 不得写数据库"
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta
    assert {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    } == before_flags


def test_preview_cache_files_are_written_and_sources_untouched(
    seeded, qapp, preview_service, assets
) -> None:
    before = {
        "good": (assets["good"].stat().st_size, assets["good"].stat().st_mtime_ns),
        "bad": (assets["bad"].stat().st_size, assets["bad"].stat().st_mtime_ns),
    }
    w = MainWindow(BrowseService(seeded), preview_service)
    try:
        w.browser_panel.wait_for_previews()
    finally:
        w.close()

    assert len(list(assets["cache"].glob("*.webp"))) == 1
    after = {
        "good": (assets["good"].stat().st_size, assets["good"].stat().st_mtime_ns),
        "bad": (assets["bad"].stat().st_size, assets["bad"].stat().st_mtime_ns),
    }
    assert before == after, "源文件不得被修改"
