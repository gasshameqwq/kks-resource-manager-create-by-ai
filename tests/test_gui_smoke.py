"""Phase 1.4-C-1：GUI 骨架冒烟测试。

全程离屏（``QT_QPA_PLATFORM=offscreen``），不依赖真实屏幕，不使用真实样本。
只验证「GUI 能构造 + 三栏存在 + BrowseService → model → view → detail 链路成立 + 不写库」。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 必须在导入 PyQt6 之前设置，保证无显示环境也能建 QApplication。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.database import schema as schema_mod  # noqa: E402
from core.query import BrowseService  # noqa: E402
from ui.browser_panel import NO_LIBRARY_TEXT, NO_RESOURCE_TEXT, BrowserPanel  # noqa: E402
from ui.detail_panel import EMPTY_TEXT, DetailPanel  # noqa: E402
from ui.library_panel import LibraryPanel  # noqa: E402
from ui.main_window import MainWindow, WINDOW_TITLE, create_main_window  # noqa: E402
from ui.resource_model import ResourceListModel, display_title  # noqa: E402


# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "gui_smoke.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    yield connection
    connection.close()


def _add_library(conn, library_id: int, name: str, *, enabled: int = 1) -> None:
    root = f"D:/{library_id}"
    conn.execute(
        "INSERT INTO libraries(id, name, root_path, root_path_key, enabled)"
        " VALUES (?, ?, ?, ?, ?)",
        (library_id, name, root, root.casefold(), enabled),
    )


def _add_resource(
    conn,
    resource_id: int,
    *,
    library_id: int | None,
    name: str,
    display_name: str | None = None,
    resource_type: str = "character_card",
    relative_path: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO resources(id, resource_type, name, display_name, file_path,"
        " file_path_key, relative_path, library_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            resource_id,
            resource_type,
            name,
            display_name,
            f"D:/lib/{resource_id}.png",
            f"d:/lib/{resource_id}.png",
            relative_path,
            library_id,
        ),
    )


# ---------------------------------------------------------------------------
# QApplication / MainWindow
# ---------------------------------------------------------------------------


def test_qapplication_can_be_created(qapp) -> None:
    assert isinstance(qapp, QApplication)


def test_main_window_constructs_with_three_panels(qapp, conn) -> None:
    _add_library(conn, 1, "Lib A")
    _add_resource(conn, 1, library_id=1, name="Alice")

    window = MainWindow(BrowseService(conn))
    try:
        assert window.startup_error() is None
        assert window.windowTitle() == WINDOW_TITLE
        assert isinstance(window.library_panel, LibraryPanel)
        assert isinstance(window.browser_panel, BrowserPanel)
        assert isinstance(window.detail_panel, DetailPanel)
        assert isinstance(window.library_panel, QWidget)
        assert isinstance(window.browser_panel, QWidget)
        assert isinstance(window.detail_panel, QWidget)
    finally:
        window.close()


def test_create_main_window_factory(qapp, conn) -> None:
    _add_library(conn, 1, "Lib A")
    window = create_main_window(BrowseService(conn))
    try:
        assert isinstance(window, MainWindow)
    finally:
        window.close()


# ---------------------------------------------------------------------------
# 空数据库 / 空状态
# ---------------------------------------------------------------------------


def test_empty_database_does_not_crash(qapp, conn) -> None:
    window = MainWindow(BrowseService(conn))
    try:
        assert window.library_panel.is_empty()
        assert window.library_panel.count() == 0
        assert window.browser_panel.model.rowCount() == 0
        assert window.browser_panel.is_showing_message()
        assert window.browser_panel.message_text() == NO_LIBRARY_TEXT
        assert window.detail_panel.body_text() == EMPTY_TEXT
    finally:
        window.close()


def test_library_without_resources_shows_empty_message(qapp, conn) -> None:
    _add_library(conn, 1, "Empty Lib")
    window = MainWindow(BrowseService(conn))
    try:
        assert window.library_panel.count() == 1
        assert window.browser_panel.model.rowCount() == 0
        assert window.browser_panel.message_text() == NO_RESOURCE_TEXT
        assert window.browser_panel.total() == 0
    finally:
        window.close()


# ---------------------------------------------------------------------------
# LibraryPanel
# ---------------------------------------------------------------------------


def test_library_panel_shows_libraries(qapp, conn) -> None:
    _add_library(conn, 1, "Alpha")
    _add_library(conn, 2, "Beta", enabled=0)
    window = MainWindow(BrowseService(conn))
    try:
        assert window.library_panel.count() == 2
        assert window.library_panel.item_text(0) == "Alpha (0)"
        assert "[disabled]" in window.library_panel.item_text(1)
        # 默认选中第一个 enabled 的库
        assert window.library_panel.current_library_id() == 1
    finally:
        window.close()


def test_library_panel_prefers_first_enabled(qapp, conn) -> None:
    _add_library(conn, 1, "Alpha", enabled=0)
    _add_library(conn, 2, "Beta")
    window = MainWindow(BrowseService(conn))
    try:
        assert window.library_panel.current_library_id() == 2
    finally:
        window.close()


def test_library_panel_falls_back_when_all_disabled(qapp, conn) -> None:
    _add_library(conn, 1, "OnlyDisabled", enabled=0)
    window = MainWindow(BrowseService(conn))
    try:
        # 不修改其 enabled 状态，仍可选作浏览对象
        assert window.library_panel.current_library_id() == 1
        assert window.library_panel.libraries()[0].enabled is False
    finally:
        window.close()


def test_library_query_failure_shows_error(qapp, conn) -> None:
    class _BrokenService:
        def libraries(self):
            raise RuntimeError("boom")

        def page(self, *args, **kwargs):  # pragma: no cover - 不会走到
            raise RuntimeError("boom")

    panel = LibraryPanel(_BrokenService())
    try:
        assert "boom" in panel.error_text()
        assert panel.is_empty()
    finally:
        panel.deleteLater()


# ---------------------------------------------------------------------------
# ResourceListModel
# ---------------------------------------------------------------------------


def test_display_title_fallbacks() -> None:
    from core.query import ResourceSummary

    base = dict(
        id=1,
        resource_type="character_card",
        name=None,
        display_name=None,
        file_path="D:/x/y/z.png",
        relative_path="a\\b\\c.png",
        extension=".png",
        card_marker=None,
        file_size=None,
        modified_time=None,
        library_id=None,
        scan_status="present",
        parse_status="ok",
        needs_review=False,
    )
    assert display_title(ResourceSummary(**{**base, "display_name": "D", "name": "N"})) == "D"
    assert display_title(ResourceSummary(**{**base, "display_name": "", "name": "N"})) == "N"
    assert display_title(ResourceSummary(**base)) == "c.png"
    assert (
        display_title(ResourceSummary(**{**base, "relative_path": None}))
        == "D:/x/y/z.png"
    )


def test_resource_model_displays_items(qapp, conn) -> None:
    _add_library(conn, 1, "A")
    _add_resource(conn, 1, library_id=1, name="Alice", display_name="Alicia")
    _add_resource(conn, 2, library_id=1, name="Bob")

    window = MainWindow(BrowseService(conn))
    try:
        model = window.browser_panel.model
        assert isinstance(model, ResourceListModel)
        assert model.rowCount() == 2
        assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "Alicia"
        assert model.data(model.index(1, 0), Qt.ItemDataRole.DisplayRole) == "Bob"
        assert model.data(model.index(0, 0), Qt.ItemDataRole.UserRole) == 1
        assert model.resource_id_at(model.index(1, 0)) == 2
        assert window.browser_panel.status_text() == "共 2 条，已显示 2 条"
        assert not window.browser_panel.is_showing_message()
    finally:
        window.close()


def test_resource_view_is_icon_mode(qapp, conn) -> None:
    from PyQt6.QtWidgets import QListView

    _add_library(conn, 1, "A")
    window = MainWindow(BrowseService(conn))
    try:
        assert isinstance(window.browser_panel.view, QListView)
        assert window.browser_panel.view.viewMode() == QListView.ViewMode.IconMode
    finally:
        window.close()


# ---------------------------------------------------------------------------
# 链路：selection → BrowseService.detail → DetailPanel
# ---------------------------------------------------------------------------


def test_selection_updates_detail_panel(qapp, conn) -> None:
    _add_library(conn, 1, "A")
    _add_resource(conn, 1, library_id=1, name="Alice")
    _add_resource(conn, 2, library_id=1, name="Bob")

    window = MainWindow(BrowseService(conn))
    try:
        assert window.detail_panel.body_text() == EMPTY_TEXT
        window.browser_panel.select_row(1)
        assert window.browser_panel.current_resource_id() == 2
        assert window.detail_panel.body_text().startswith("Resource ID: 2")
        assert "Bob" in window.detail_panel.body_text()
    finally:
        window.close()


def test_switching_library_reloads_browser(qapp, conn) -> None:
    _add_library(conn, 1, "Alpha")
    _add_library(conn, 2, "Beta")
    _add_resource(conn, 1, library_id=1, name="InAlpha")
    _add_resource(conn, 2, library_id=2, name="InBeta")

    window = MainWindow(BrowseService(conn))
    try:
        assert window.browser_panel.model.rowCount() == 1
        assert window.browser_panel.model.data(
            window.browser_panel.model.index(0, 0), Qt.ItemDataRole.DisplayRole
        ) == "InAlpha"

        # 切到第二个 Library
        window.library_panel._list.setCurrentRow(1)  # noqa: SLF001 - 测试驱动 UI
        assert window.browser_panel.model.rowCount() == 1
        assert window.browser_panel.model.data(
            window.browser_panel.model.index(0, 0), Qt.ItemDataRole.DisplayRole
        ) == "InBeta"
    finally:
        window.close()


def test_missing_detail_falls_back_to_empty(qapp, conn) -> None:
    _add_library(conn, 1, "A")
    window = MainWindow(BrowseService(conn))
    try:
        window._on_resource_selected(999999)  # noqa: SLF001 - 直接验证兜底分支
        assert window.detail_panel.body_text().startswith("找不到资源 #999999")
    finally:
        window.close()


# ---------------------------------------------------------------------------
# 只读不变量
# ---------------------------------------------------------------------------


def test_gui_does_not_write_database(qapp, conn) -> None:
    _add_library(conn, 1, "A")
    _add_resource(conn, 1, library_id=1, name="Alice")
    _add_resource(conn, 2, library_id=1, name="Bob")

    before_changes = conn.total_changes
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))
    before_flags = {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    }

    window = MainWindow(BrowseService(conn))
    try:
        window.library_panel.reload()
        window.browser_panel.reload()
        window.browser_panel.select_row(0)
        window.browser_panel.select_row(1)
        window.browser_panel.reload()
    finally:
        window.close()

    assert conn.total_changes == before_changes, "GUI 不得写库"
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta
    assert {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    } == before_flags


def test_schema_version_unchanged() -> None:
    assert schema_mod.SCHEMA_VERSION == 2
    assert sorted(schema_mod.MIGRATIONS) == [1, 2]


# ---------------------------------------------------------------------------
# 架构约束（静态）：不绕过 Query Layer / 不引入线程或 preview
# ---------------------------------------------------------------------------


def test_ui_does_not_bypass_query_layer() -> None:
    ui_dir = Path(__file__).resolve().parent.parent / "ui"
    files = sorted(ui_dir.glob("*.py"))
    assert files, "ui/ 应当有源码文件"
    for path in files:
        source = path.read_text(encoding="utf-8")
        import_lines = [
            line
            for line in source.splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        assert not any(
            "sqlite3" in line for line in import_lines
        ), f"{path.name} 不得自己连数据库"
        joined = "\n".join(import_lines)
        assert "ResourceQuery" not in joined, f"{path.name} 不得直接用 ResourceQuery"
        assert "LibraryQuery" not in joined, f"{path.name} 不得直接用 LibraryQuery"
        # C-3 起允许在 ui/ 使用 PreviewService / QThreadPool，但生成只能在 worker 里
        if path.name != "preview_worker.py":
            assert "get_or_generate" not in source, (
                f"{path.name} 不得在 GUI 线程生成 preview（应交给 PreviewWorker）"
            )


def test_main_parser_accepts_gui_subcommand() -> None:
    from main import build_parser

    args = build_parser().parse_args(["gui"])
    assert args.command == "gui"
    # 既有命令不受影响
    assert build_parser().parse_args(["library", "list"]).command == "library"
    assert build_parser().parse_args([]).command is None
