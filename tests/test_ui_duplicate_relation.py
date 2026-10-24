"""Phase 4.2：GUI 重复筛选、副本列表与关系反查闭环。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.query import BrowseService  # noqa: E402
from core.thumbnails import PreviewService  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

HASH_A = "a" * 64
HASH_B = "b" * 64
ALICE_ID = 10
BOB_ID = 20


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _add_resource(
    conn,
    resource_id: int,
    *,
    name: str,
    sha256: str | None,
    relative_path: str,
) -> None:
    conn.execute(
        "INSERT INTO resources(id, resource_type, type_source, name, display_name,"
        " file_path, file_path_key, relative_path, extension, sha256, library_id,"
        " scan_status, parse_status, needs_review)"
        " VALUES (?, 'character_card', 'auto', ?, ?, ?, ?, ?, '.png', ?, 1,"
        " 'present', 'ok', 0)",
        (
            resource_id,
            name,
            name,
            f"D:/phase4-gui/{resource_id}.png",
            f"d:/phase4-gui/{resource_id}.png",
            relative_path,
            sha256,
        ),
    )


def _add_relation_rows(conn) -> None:
    conn.execute(
        "INSERT INTO authors(id, name, name_key) VALUES (?, 'Alice', 'alice')",
        (ALICE_ID,),
    )
    conn.execute(
        "INSERT INTO authors(id, name, name_key) VALUES (?, 'Bob', 'bob')",
        (BOB_ID,),
    )
    for resource_id, author_id in ((1, ALICE_ID), (2, BOB_ID), (3, ALICE_ID)):
        conn.execute(
            "INSERT INTO resource_authors(resource_id, author_id, ordinal, raw_name)"
            " VALUES (?, ?, 0, '')",
            (resource_id, author_id),
        )
    for resource_id, guid in ((1, "Plugin.Shared"), (2, "Plugin.Shared"), (3, "Plugin.Solo")):
        conn.execute(
            "INSERT INTO resource_plugins(resource_id, plugin_guid) VALUES (?, ?)",
            (resource_id, guid),
        )


@pytest.fixture()
def gui(qapp, tmp_path: Path):
    db_file = tmp_path / "phase4_gui.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    conn.execute(
        "INSERT INTO libraries(id, name, root_path, root_path_key)"
        " VALUES (1, 'Phase4', 'D:/phase4-gui', 'd:/phase4-gui')"
    )
    _add_resource(
        conn,
        1,
        name="DupOne",
        sha256=HASH_A,
        relative_path="Cards/DupOne.png",
    )
    _add_resource(
        conn,
        2,
        name="DupTwo",
        sha256=HASH_A,
        relative_path="Copies/DupTwo.png",
    )
    _add_resource(
        conn,
        3,
        name="Solo",
        sha256=HASH_B,
        relative_path="Cards/Solo.png",
    )
    _add_resource(
        conn,
        4,
        name="NoHash",
        sha256=None,
        relative_path="Cards/NoHash.png",
    )
    _add_relation_rows(conn)
    conn.commit()

    window = MainWindow(
        BrowseService(conn),
        PreviewService(cache_dir=tmp_path / "preview-cache"),
    )
    try:
        yield window
    finally:
        window.close()
        conn.close()


def _ids(window: MainWindow) -> set[int]:
    return {item.resource.id for item in window.browser_panel.model.items()}


def test_duplicate_tri_state_updates_scope_and_results(gui: MainWindow) -> None:
    browser = gui.browser_panel
    bar = browser.filter_bar
    assert [
        bar.duplicates_combo.itemData(index)
        for index in range(bar.duplicates_combo.count())
    ] == [None, True, False]
    assert browser.scope().has_duplicates is None

    bar.set_has_duplicates_filter(True)
    assert browser.scope().has_duplicates is True
    assert _ids(gui) == {1, 2}

    bar.set_has_duplicates_filter(False)
    assert browser.scope().has_duplicates is False
    assert _ids(gui) == {3, 4}

    bar.set_has_duplicates_filter(None)
    assert browser.scope().has_duplicates is None
    assert _ids(gui) == {1, 2, 3, 4}


def test_sha256_external_filter_state_clear_and_offset(
    gui: MainWindow, monkeypatch
) -> None:
    browser = gui.browser_panel
    bar = browser.filter_bar
    offsets: list[int] = []
    original_page = browser._service.page

    def capture_page(scope, *, limit=None, offset=0):
        offsets.append(offset)
        return original_page(scope, limit=limit, offset=offset)

    monkeypatch.setattr(browser._service, "page", capture_page)
    browser.apply_relation_filter(sha256=f"  {HASH_A}  ")

    assert offsets[-1] == 0
    assert browser.scope().sha256 == HASH_A
    assert _ids(gui) == {1, 2}
    assert HASH_A.startswith(bar.sha256_text().removeprefix("SHA-256：").rstrip("…"))
    assert bar.sha256_label.toolTip() == HASH_A
    assert bar.clear_sha256_button.isVisibleTo(bar)

    bar.click_clear_sha256()
    assert browser.scope().sha256 is None
    assert _ids(gui) == {1, 2, 3, 4}
    assert bar.sha256_text() == "SHA-256：全部"
    assert not bar.clear_sha256_button.isVisibleTo(bar)


def test_detail_renders_all_duplicate_members_and_emits_sha(gui: MainWindow) -> None:
    browser = gui.browser_panel
    assert browser.select_resource(1)
    panel = gui.detail_panel

    assert panel.duplicate_rows() == [
        (1, "DupOne", "Cards/DupOne.png"),
        (2, "DupTwo", "Copies/DupTwo.png"),
    ]
    assert panel.duplicate_sha256() == HASH_A
    assert panel.is_sha256_filter_enabled()

    requested: list[str] = []
    panel.sha256_filter_requested.connect(requested.append)
    panel.click_sha256_filter()

    assert requested == [HASH_A]
    assert browser.scope().sha256 == HASH_A
    assert _ids(gui) == {1, 2}


def test_author_and_plugin_filters_close_the_loop(gui: MainWindow) -> None:
    browser = gui.browser_panel
    assert browser.select_resource(1)
    panel = gui.detail_panel

    authors = panel.author_rows()
    assert (ALICE_ID, "Alice") in authors
    author_requests: list[int] = []
    panel.author_filter_requested.connect(author_requests.append)
    panel.click_author(ALICE_ID)
    assert author_requests == [ALICE_ID]
    assert browser.scope().author_id == ALICE_ID
    assert _ids(gui) == {1, 3}

    browser.filter_bar.clear_relation_filters()
    assert browser.select_resource(1)
    assert panel.plugin_rows() == ["Plugin.Shared"]
    plugin_requests: list[str] = []
    panel.plugin_filter_requested.connect(plugin_requests.append)
    panel.click_plugin(0)
    assert plugin_requests == ["Plugin.Shared"]
    assert browser.scope().plugin_guid == "Plugin.Shared"
    assert _ids(gui) == {1, 2}


def test_relations_reset_pagination_offset(gui: MainWindow, monkeypatch) -> None:
    browser = gui.browser_panel
    offsets: list[int] = []
    original_page = browser._service.page

    def capture_page(scope, *, limit=None, offset=0):
        offsets.append(offset)
        return original_page(scope, limit=limit, offset=offset)

    monkeypatch.setattr(browser._service, "page", capture_page)
    browser.apply_relation_filter(author_id=ALICE_ID)
    browser.apply_relation_filter(plugin_guid="Plugin.Shared")
    assert offsets
    assert all(offset == 0 for offset in offsets)
