"""Phase 3.5.2 —— PyQt6 Tag / Favorite / 用户字段编辑集成测试。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.app import ResourceWriteService, TagWriteService  # noqa: E402
from core.database import db as database  # noqa: E402
from core.database import schema as schema_mod  # noqa: E402
from core.query import BrowseService  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _insert_resource(
    conn,
    resource_id: int,
    name: str,
    *,
    resource_type: str = "character_card",
) -> None:
    path = f"D:/phase352/{resource_id}.png"
    conn.execute(
        "INSERT INTO resources("
        " id, resource_type, type_source, name, file_path, file_path_key,"
        " relative_path, extension, library_id, scan_status, parse_status,"
        " needs_review)"
        " VALUES (?, ?, 'auto', ?, ?, ?, ?, '.png', 1, 'present', 'ok', 0)",
        (
            resource_id,
            resource_type,
            name,
            path,
            database.normalize_path_key(path),
            f"Cards/{name}.png",
        ),
    )


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "phase352.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    connection.execute(
        "INSERT INTO libraries(id, name, root_path, root_path_key)"
        " VALUES (1, 'GUI', 'D:/phase352', 'd:/phase352')"
    )
    _insert_resource(connection, 1, "Alice")
    _insert_resource(connection, 2, "Bob")
    _insert_resource(connection, 3, "Carol", resource_type="unknown")

    tags = TagWriteService(connection)
    tags.ensure_system_tags()
    cute = tags.create_tag("Cute")
    style = tags.create_tag("Style", color="#88ccff", category="look")
    tags.assign_tag(1, cute)
    tags.set_favorite(2, True)
    connection.commit()
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture()
def window(qapp, conn):
    value = MainWindow(BrowseService(conn))
    try:
        yield value
    finally:
        value.close()


def _ids(browser) -> list[int]:
    return [item.resource.id for item in browser.model.items()]


def _tag_id(conn, name_key: str) -> int:
    row = conn.execute(
        "SELECT id FROM tags WHERE name_key = ?", (name_key,)
    ).fetchone()
    assert row is not None
    return int(row["id"])


def _resource_tag_ids(conn, resource_id: int) -> set[int]:
    return {
        int(row["tag_id"])
        for row in conn.execute(
            "SELECT tag_id FROM resource_tags WHERE resource_id = ?",
            (resource_id,),
        ).fetchall()
    }


def test_filter_bar_exposes_favorite_and_tags(window, conn) -> None:
    bar = window.browser_panel.filter_bar
    favorite_values = [
        bar.favorite_combo.itemData(index)
        for index in range(bar.favorite_combo.count())
    ]
    assert favorite_values == [None, True, False]

    tag_values = {
        bar.tag_combo.itemData(index)
        for index in range(bar.tag_combo.count())
    }
    assert None in tag_values
    assert _tag_id(conn, "cute") in tag_values
    assert _tag_id(conn, "style") in tag_values
    assert _tag_id(conn, "favorite") in tag_values


def test_favorite_filter_maps_into_scope_and_results(window) -> None:
    browser = window.browser_panel
    bar = browser.filter_bar

    bar.set_favorite_filter(True)
    scope = browser.scope()
    assert scope.favorite is True
    assert scope.to_filter().favorite is True
    assert _ids(browser) == [2]

    bar.set_favorite_filter(False)
    assert browser.scope().favorite is False
    assert set(_ids(browser)) == {1, 3}

    bar.set_favorite_filter(None)
    assert browser.scope().favorite is None
    assert set(_ids(browser)) == {1, 2, 3}


def test_tag_filter_maps_into_scope_and_results(window, conn) -> None:
    browser = window.browser_panel
    cute = _tag_id(conn, "cute")

    browser.filter_bar.set_tag(cute)
    scope = browser.scope()
    assert scope.tag_id == cute
    assert scope.to_filter().tag_id == cute
    assert _ids(browser) == [1]

    browser.filter_bar.set_tag(None)
    assert browser.scope().tag_id is None
    assert set(_ids(browser)) == {1, 2, 3}


def test_tag_and_favorite_filters_combine_with_and(window, conn) -> None:
    browser = window.browser_panel
    bar = browser.filter_bar
    bar.set_tag(_tag_id(conn, "cute"))
    bar.set_favorite_filter(False)

    assert browser.scope().tag_id == _tag_id(conn, "cute")
    assert browser.scope().favorite is False
    assert _ids(browser) == [1]


def test_detail_displays_assigned_tags_and_available_catalog(window, conn) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    assert browser.select_resource(1)

    rows = detail.tag_rows()
    assert [name for _tag_id_value, name, _system in rows] == ["Cute"]
    cute = _tag_id(conn, "cute")
    style = _tag_id(conn, "style")
    assert cute in {tag_id for tag_id, _name, _system in rows}
    available = set(detail.available_tag_ids())
    assert style in available
    assert cute not in available
    assert _tag_id(conn, "favorite") not in available


def test_detail_displays_favorite_state(window, conn) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    assert browser.select_resource(2)

    assert detail.is_favorite_checked() is True
    assert any(system for _id, _name, system in detail.tag_rows())
    favorite_id = _tag_id(conn, "favorite")
    assert detail.select_tag_row(0) is None
    assert detail.remove_tag_button.isEnabled() is False
    assert favorite_id in _resource_tag_ids(conn, 2)


def test_add_existing_tag_from_detail_updates_database_and_ui(
    window, conn
) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    assert browser.select_resource(1)

    style = _tag_id(conn, "style")
    detail.select_tag_to_add(style)
    detail.click_add_existing_tag()

    assert style in _resource_tag_ids(conn, 1)
    assert {name for _id, name, _system in detail.tag_rows()} == {
        "Cute",
        "Style",
    }
    assert "已添加标签" in detail.operation_feedback()
    assert style not in detail.available_tag_ids()


def test_create_and_assign_new_tag_from_detail(window, conn) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    assert browser.select_resource(1)

    detail.set_new_tag_name("  NewTag  ")
    assert detail.create_tag_button.isEnabled()
    detail.click_create_tag()

    new_id = _tag_id(conn, "newtag")
    assert new_id in _resource_tag_ids(conn, 1)
    assert "NewTag" in {name for _id, name, _system in detail.tag_rows()}
    assert "已创建并添加标签" in detail.operation_feedback()

    indexes = [
        browser.filter_bar.tag_combo.findData(new_id),
    ]
    assert indexes[0] >= 0


def test_create_tag_conflict_shows_feedback_without_merge(window, conn) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    assert browser.select_resource(1)
    detail.set_new_tag_name("CUTE")
    detail.click_create_tag()

    assert "写入失败" in detail.operation_feedback()
    assert "标签名已存在" in detail.operation_feedback()
    rows = conn.execute(
        "SELECT count(*) AS c FROM tags WHERE name_key = 'cute'"
    ).fetchone()
    assert rows["c"] == 1


def test_remove_tag_from_detail_updates_database_and_ui(window, conn) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    assert browser.select_resource(1)

    cute = _tag_id(conn, "cute")
    row = next(
        index
        for index, (tag_id, _name, _system) in enumerate(detail.tag_rows())
        if tag_id == cute
    )
    detail.select_tag_row(row)
    assert detail.remove_tag_button.isEnabled()
    detail.click_remove_tag()

    assert cute not in _resource_tag_ids(conn, 1)
    assert detail.tag_rows() == []
    assert "已移除标签" in detail.operation_feedback()
    assert cute in detail.available_tag_ids()


def test_favorite_toggle_from_detail_is_idempotent_at_service_level(
    window, conn
) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    assert browser.select_resource(1)

    detail.click_favorite()
    assert detail.is_favorite_checked() is True
    assert _tag_id(conn, "favorite") in _resource_tag_ids(conn, 1)

    detail.click_favorite()
    assert detail.is_favorite_checked() is False
    assert _tag_id(conn, "favorite") not in _resource_tag_ids(conn, 1)


def test_unfavorite_disappears_from_current_favorite_filter(window) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    browser.filter_bar.set_favorite_filter(True)
    assert browser.select_resource(2)
    assert detail.is_favorite_checked() is True

    detail.click_favorite()

    assert _ids(browser) == []
    assert browser.scope().favorite is True
    assert detail.current_resource_id() is None


def test_removing_tag_disappears_from_current_tag_filter(window, conn) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    cute = _tag_id(conn, "cute")
    browser.filter_bar.set_tag(cute)
    assert browser.select_resource(1)

    row = next(
        index
        for index, (tag_id, _name, _system) in enumerate(detail.tag_rows())
        if tag_id == cute
    )
    detail.select_tag_row(row)
    detail.click_remove_tag()

    assert _ids(browser) == []
    assert browser.scope().tag_id == cute
    assert detail.current_resource_id() is None


def test_display_name_save_and_clear_refresh_list(window, conn) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    assert browser.select_resource(1)

    detail.set_display_name_value("Alicia")
    detail.click_save_display_name()
    row = conn.execute(
        "SELECT display_name FROM resources WHERE id = 1"
    ).fetchone()
    assert row["display_name"] == "Alicia"
    assert detail.title_text() == "Alicia"
    assert next(
        item.resource.display_name
        for item in browser.model.items()
        if item.resource.id == 1
    ) == "Alicia"

    detail.click_clear_display_name()
    row = conn.execute(
        "SELECT display_name FROM resources WHERE id = 1"
    ).fetchone()
    assert row["display_name"] is None
    assert detail.title_text() == "Alice"


def test_notes_save_and_clear(window, conn) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    assert browser.select_resource(1)

    detail.set_notes_value("private note")
    detail.click_save_notes()
    assert conn.execute(
        "SELECT notes FROM resources WHERE id = 1"
    ).fetchone()["notes"] == "private note"
    assert detail.notes_value() == "private note"

    detail.click_clear_notes()
    assert conn.execute(
        "SELECT notes FROM resources WHERE id = 1"
    ).fetchone()["notes"] is None
    assert detail.notes_value() == ""


def test_resource_type_save_updates_effective_type_and_filter(
    window, conn
) -> None:
    browser = window.browser_panel
    detail = window.detail_panel
    assert browser.select_resource(1)

    detail.set_resource_type_value("mod")
    detail.click_save_resource_type()
    row = conn.execute(
        "SELECT resource_type, type_source FROM resources WHERE id = 1"
    ).fetchone()
    assert (row["resource_type"], row["type_source"]) == ("mod", "user")
    assert "用户修正" in detail.type_source_label.text()

    browser.filter_bar.set_resource_type("mod")
    assert 1 in _ids(browser)
    assert browser.scope().resource_type == "mod"


def test_resource_type_clear_is_not_faked_by_gui(window) -> None:
    """冻结的 Phase 3.1 契约没有 user → auto API，GUI 不伪造清除。"""
    detail = window.detail_panel
    assert "不提供从用户修正恢复自动类型的 API" in (
        detail.type_source_label.toolTip()
    )
    assert not hasattr(detail, "resource_type_clear_button")


def test_main_window_owns_write_services_on_same_connection(window, conn) -> None:
    assert isinstance(window.tag_write_service(), TagWriteService)
    assert isinstance(window.resource_write_service(), ResourceWriteService)
    assert window.tag_write_service().conn is conn
    assert window.resource_write_service().conn is conn


def test_main_window_accepts_injected_write_services(qapp, conn) -> None:
    tag_writer = TagWriteService(conn)
    resource_writer = ResourceWriteService(conn)
    value = MainWindow(
        BrowseService(conn),
        tag_write_service=tag_writer,
        resource_write_service=resource_writer,
    )
    try:
        assert value.tag_write_service() is tag_writer
        assert value.resource_write_service() is resource_writer
    finally:
        value.close()


def test_ui_has_no_direct_sql_and_core_has_no_pyqt6() -> None:
    repo = Path(__file__).resolve().parent.parent
    for path in sorted((repo / "ui").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        imports = [
            line
            for line in source.splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        assert not any("sqlite3" in line for line in imports), path.name
        assert ".execute(" not in source, path.name

    for path in sorted((repo / "core").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        imports = [
            line
            for line in source.splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        assert not any("PyQt6" in line for line in imports), path


def test_schema_remains_v2_with_sixteen_business_tables() -> None:
    assert schema_mod.SCHEMA_VERSION == 2
    assert sorted(schema_mod.MIGRATIONS) == [1, 2]
    assert len(schema_mod.CURRENT_TABLES) == 16
