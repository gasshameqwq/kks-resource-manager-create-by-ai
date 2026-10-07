"""Phase 1.5-A：Library GUI 管理测试（Add / Enable / Disable / Remove）。

全程离屏（``QT_QPA_PLATFORM=offscreen``），只使用临时数据库 + 临时目录，
不使用真实样本、不污染 ``data/``。

覆盖点（对应 1.5-A 验收）：
Add → 左栏出现 / 自动选中 / 不自动扫描；duplicate 报错；Enable/Disable 改库且
disabled 仍可浏览；Remove 需确认、preview 语义正确、只删库记录（资源保留、
扫描记录级联删除、不碰文件系统）、清空 selection 与 Detail。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.app import LibraryAdminService  # noqa: E402
from core.database import db as database  # noqa: E402
from core.library import LibraryAlreadyExists  # noqa: E402
from core.query import BrowseService  # noqa: E402
from core.thumbnails import PreviewService  # noqa: E402
from tests.builders import write_card  # noqa: E402
import ui.library_panel as library_panel_module  # noqa: E402
from ui.detail_panel import EMPTY_TEXT  # noqa: E402
from ui.library_admin_dialog import AddLibraryDialog, build_removal_text  # noqa: E402
from ui.library_panel import NO_LIBRARY_TEXT, LibraryPanel  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


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
def conn(tmp_path: Path):
    db_file = tmp_path / "library_admin.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    yield connection
    connection.close()


@pytest.fixture()
def cards_dir(tmp_path: Path) -> Path:
    path = tmp_path / "KKS Cards"
    path.mkdir()
    return path


@pytest.fixture()
def window(qapp, conn, tmp_path: Path):
    """真实 MainWindow：读经 BrowseService，写经 MainWindow 自建的 Admin 服务。"""
    w = MainWindow(BrowseService(conn), PreviewService(cache_dir=tmp_path / "cache"))
    yield w
    w.close()


def _add_resource(
    conn,
    resource_id: int,
    *,
    library_id: int | None,
    name: str,
    resource_type: str = "character_card",
) -> int:
    conn.execute(
        "INSERT INTO resources(id, resource_type, name, display_name, file_path,"
        " file_path_key, relative_path, library_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            resource_id,
            resource_type,
            name,
            name,
            f"D:/lib/{resource_id}.png",
            f"d:/lib/{resource_id}.png",
            f"Cards/{name}.png",
            library_id,
        ),
    )
    return resource_id


def _count(conn, table: str) -> int:
    return conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"]


# ---------------------------------------------------------------------------
# Add Library
# ---------------------------------------------------------------------------


def test_gui_add_library_appears_and_is_selected(window, cards_dir: Path) -> None:
    library = window.library_panel.add_library(str(cards_dir))

    assert window.library_panel.count() == 1
    assert window.library_panel.item_text(0) == "KKS Cards (0)"
    # Add 成功后自动选中新 Library
    assert window.library_panel.current_library_id() == library.id
    # 新库 resource_count 为 0（无资源）
    assert window.library_panel.libraries()[0].resource_count == 0


def test_gui_add_does_not_scan(window, conn, cards_dir: Path) -> None:
    # 目录里放一张**结构合法**的卡片：如果误触发扫描，就会产生资源行。
    write_card(cards_dir / "card.png", lastname="測試")

    window.library_panel.add_library(str(cards_dir))

    assert _count(conn, "resources") == 0
    assert _count(conn, "scan_records") == 0
    assert window.library_panel.libraries()[0].last_scan_at is None


def test_gui_add_supports_name_notes_and_disabled(window, conn, cards_dir: Path) -> None:
    library = window.library_panel.add_library(
        str(cards_dir), name="我的卡库", notes="来自测试", enabled=False
    )
    assert library.name == "我的卡库"
    assert library.notes == "来自测试"
    assert library.enabled is False
    # name 允许重复：再加另一个目录但用同一个名字不应报错
    second_dir = cards_dir.parent / "Another"
    second_dir.mkdir()
    window.library_panel.add_library(str(second_dir), name="我的卡库")
    assert _count(conn, "libraries") == 2


def test_gui_add_duplicate_raises_existing_error(window, cards_dir: Path) -> None:
    window.library_panel.add_library(str(cards_dir))
    with pytest.raises(LibraryAlreadyExists) as excinfo:
        window.library_panel.add_library(str(cards_dir))
    assert "已添加过" in str(excinfo.value)
    # 未新增第二行
    assert window.library_panel.count() == 1


def test_gui_add_duplicate_shows_warning(monkeypatch, window, cards_dir: Path) -> None:
    window.library_panel.add_library(str(cards_dir))

    calls: list[tuple] = []
    monkeypatch.setattr(
        library_panel_module.QMessageBox, "warning", lambda *a, **k: calls.append(a)
    )
    monkeypatch.setattr(
        window.library_panel,
        "_prompt_add_library",
        lambda: {
            "root_path": str(cards_dir),
            "name": None,
            "notes": "",
            "enabled": True,
            "allow_missing": False,
        },
    )

    window.library_panel.add_button.click()

    assert calls, "重复添加必须弹出错误提示"
    assert "已添加过" in calls[0][2]
    assert window.library_panel.count() == 1


def test_gui_add_button_adds_via_dialog_values(monkeypatch, window, cards_dir: Path) -> None:
    monkeypatch.setattr(
        window.library_panel,
        "_prompt_add_library",
        lambda: {
            "root_path": str(cards_dir),
            "name": "按钮加的库",
            "notes": "",
            "enabled": True,
            "allow_missing": False,
        },
    )
    window.library_panel.add_button.click()

    assert window.library_panel.count() == 1
    assert window.library_panel.item_text(0).startswith("按钮加的库 (0)")
    assert window.library_panel.current_library_id() is not None


# ---------------------------------------------------------------------------
# Enable / Disable
# ---------------------------------------------------------------------------


def test_gui_enable_disable_updates_database(window, conn, cards_dir: Path) -> None:
    library = window.library_panel.add_library(str(cards_dir))

    window.library_panel.set_library_enabled(library.id, False)
    assert (
        conn.execute("SELECT enabled FROM libraries WHERE id = ?", (library.id,)).fetchone()[
            "enabled"
        ]
        == 0
    )
    assert "[disabled]" in window.library_panel.item_text(0)
    assert window.library_panel.toggle_button.text() == "启用"

    window.library_panel.set_library_enabled(library.id, True)
    assert (
        conn.execute("SELECT enabled FROM libraries WHERE id = ?", (library.id,)).fetchone()[
            "enabled"
        ]
        == 1
    )
    assert "[disabled]" not in window.library_panel.item_text(0)


def test_gui_toggle_button_flips_state(window, conn, cards_dir: Path) -> None:
    library = window.library_panel.add_library(str(cards_dir))

    window.library_panel.toggle_button.click()
    assert (
        conn.execute("SELECT enabled FROM libraries WHERE id = ?", (library.id,)).fetchone()[
            "enabled"
        ]
        == 0
    )
    window.library_panel.toggle_button.click()
    assert (
        conn.execute("SELECT enabled FROM libraries WHERE id = ?", (library.id,)).fetchone()[
            "enabled"
        ]
        == 1
    )


def test_gui_disabled_library_is_not_hidden_and_still_browsable(
    window, conn, cards_dir: Path
) -> None:
    library = window.library_panel.add_library(str(cards_dir))
    _add_resource(conn, 1, library_id=library.id, name="Alice")

    window.library_panel.set_library_enabled(library.id, False)

    # 不隐藏、不删除；仍保持选中
    assert window.library_panel.count() == 1
    assert window.library_panel.current_library_id() == library.id
    # disabled 只影响**扫描**，不影响浏览
    window.browser_panel.reload()
    assert window.browser_panel.total() == 1
    assert window.browser_panel.model.rowCount() == 1


def test_gui_reload_reads_state_from_database(window, conn, cards_dir: Path) -> None:
    library = window.library_panel.add_library(str(cards_dir))

    # 直接改库（模拟其它入口 / 外部改动），不经过 GUI 的写操作
    conn.execute("UPDATE libraries SET enabled = 0 WHERE id = ?", (library.id,))
    assert "[disabled]" not in window.library_panel.item_text(0)  # 尚未刷新

    window.library_panel.reload(select=library.id)

    # 刷新后以数据库为准，GUI 不靠本地状态模拟
    assert "[disabled]" in window.library_panel.item_text(0)
    assert window.library_panel.toggle_button.text() == "启用"


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


def test_gui_remove_requires_confirmation(monkeypatch, window, conn, cards_dir: Path) -> None:
    library = window.library_panel.add_library(str(cards_dir))
    _add_resource(conn, 1, library_id=library.id, name="Alice")
    window.library_panel.reload(select=library.id)

    seen: dict = {}

    def decline(parent, report):
        seen["report"] = report
        return False

    monkeypatch.setattr(library_panel_module, "confirm_remove", decline)
    window.library_panel.remove_button.click()

    # 未确认 → 不删除
    assert "report" in seen
    assert seen["report"].library.id == library.id
    assert seen["report"].resources_orphaned == 1
    assert _count(conn, "libraries") == 1
    assert window.library_panel.count() == 1

    # 确认 → 删除
    monkeypatch.setattr(library_panel_module, "confirm_remove", lambda parent, report: True)
    window.library_panel.remove_button.click()
    assert _count(conn, "libraries") == 0


def test_gui_remove_preview_semantics(window, conn, cards_dir: Path) -> None:
    library = window.library_panel.add_library(str(cards_dir))
    _add_resource(conn, 1, library_id=library.id, name="a")
    _add_resource(conn, 2, library_id=library.id, name="b")
    conn.execute(
        "INSERT INTO scan_records(library_id, status) VALUES (?, 'completed')",
        (library.id,),
    )

    report = LibraryAdminService(conn).preview_removal(library.id)

    assert report.resources_orphaned == 2
    assert report.scan_records_deleted == 1
    # 预览是只读的：什么都不改
    assert _count(conn, "libraries") == 1
    assert _count(conn, "resources") == 2
    assert _count(conn, "scan_records") == 1

    text = build_removal_text(report)
    assert "只删除数据库中的库记录" in text
    assert "已入库的资源会保留（但不再属于任何库）" in text
    assert "不会删除或移动你的任何文件" in text
    assert "该库的扫描历史记录将被删除" in text


def test_gui_remove_only_deletes_db_record(window, conn, cards_dir: Path) -> None:
    sample = cards_dir / "sample.png"
    sample.write_bytes(b"fake card")

    library = window.library_panel.add_library(str(cards_dir))
    resource_id = _add_resource(conn, 1, library_id=library.id, name="a")
    conn.execute(
        "INSERT INTO scan_records(library_id, status) VALUES (?, 'completed')",
        (library.id,),
    )

    report = window.library_panel.remove_library(library.id)

    # Library 记录消失
    assert report.library.id == library.id
    assert window.library_panel.count() == 0
    assert _count(conn, "libraries") == 0
    # 资源保留，仅解除关联
    row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
    assert row is not None
    assert row["library_id"] is None
    # 扫描记录按现有级联语义删除
    assert _count(conn, "scan_records") == 0
    # 文件系统毫发无损
    assert sample.read_bytes() == b"fake card"
    assert cards_dir.is_dir()


def test_gui_remove_clears_selection_and_detail(window, conn, cards_dir: Path) -> None:
    library = window.library_panel.add_library(str(cards_dir))
    _add_resource(conn, 1, library_id=library.id, name="Alice")
    window.library_panel.reload(select=library.id)
    window.browser_panel.reload()
    window.browser_panel.select_row(0)
    assert window.browser_panel.current_resource_id() == 1
    assert "Alice" in window.detail_panel.body_text()

    window.library_panel.remove_library(library.id)

    # 刷新后无残留 selection / Detail 状态
    assert window.library_panel.current_library_id() is None
    assert window.browser_panel.model.rowCount() == 0
    assert window.browser_panel.is_showing_message()
    assert window.browser_panel.message_text() == NO_LIBRARY_TEXT
    assert window.detail_panel.body_text() == EMPTY_TEXT


def test_gui_remove_unknown_selection_is_noop(window) -> None:
    # 没有任何 Library 时点「移除」不应崩溃、不应有写操作
    window.library_panel.remove_button.click()
    assert window.library_panel.count() == 0


# ---------------------------------------------------------------------------
# 只读边界 / 入口位置
# ---------------------------------------------------------------------------


def test_gui_without_admin_service_is_read_only(qapp, conn) -> None:
    panel = LibraryPanel(BrowseService(conn))
    try:
        assert not panel.actions_enabled()
        assert not panel.add_button.isEnabled()
        assert not panel.toggle_button.isEnabled()
        assert not panel.remove_button.isEnabled()
        # 只读面板仍能正常列出（此处为空）
        assert panel.is_empty()
    finally:
        panel.deleteLater()


def test_scan_entry_points_present(window) -> None:
    # 1.5-B 起扫描入口已接线：增量（主）+ 全量（次级）；
    # 没有选中 Library 时两者都不可点（不伪造可扫描状态）。
    assert window.library_panel.scan_button.text() == "扫描"
    assert window.library_panel.full_scan_button.text() == "全量重扫"
    assert not window.library_panel.scan_button.isEnabled()
    assert not window.library_panel.full_scan_button.isEnabled()


def test_add_dialog_values_defaults(qapp) -> None:
    dialog = AddLibraryDialog()
    try:
        dialog.set_root_path("D:/KKS/Cards")
        values = dialog.values()
        assert values["root_path"] == "D:/KKS/Cards"
        assert values["name"] is None
        assert values["notes"] == ""
        assert values["enabled"] is True
        assert values["allow_missing"] is False
    finally:
        dialog.deleteLater()
