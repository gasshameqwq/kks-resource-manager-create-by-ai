"""Phase 1.4-C-2：搜索 / 筛选 / 排序 / 有界加载 的 GUI 测试。

全程离屏（``QT_QPA_PLATFORM=offscreen``），只使用临时数据库，不使用真实样本。
核心断言：所有查询都经 ``BrowseService.page()``，筛选变化重置 offset，
「加载更多」追加而不替换。
"""

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
from ui.browser_panel import (  # noqa: E402
    NO_LIBRARY_TEXT,
    NO_MATCH_TEXT,
    NO_RESOURCE_TEXT,
    PAGE_SIZE,
    BrowserPanel,
)
from ui.filter_bar import SORT_OPTIONS, FilterBar  # noqa: E402
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
    db_file = tmp_path / "gui_filters.db"
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
    resource_type: str = "character_card",
    needs_review: int = 0,
    file_size: int | None = None,
    relative_path: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO resources(id, resource_type, name, display_name, file_path,"
        " file_path_key, relative_path, library_id, needs_review, file_size)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            resource_id,
            resource_type,
            name,
            name,
            f"D:/lib/{resource_id}.png",
            f"d:/lib/{resource_id}.png",
            relative_path if relative_path is not None else f"Cards/{name}.png",
            library_id,
            needs_review,
            file_size if file_size is not None else resource_id * 100,
        ),
    )


def _add_mod(conn, guid: str) -> None:
    conn.execute("INSERT INTO mods(guid, name) VALUES (?, ?)", (guid, guid))


def _add_usage(conn, resource_id: int, mod_guid: str, prop: str) -> None:
    conn.execute(
        "INSERT INTO resource_mod_usages(resource_id, mod_guid, property, slot,"
        " local_slot, category_no) VALUES (?, ?, ?, 0, 0, 0)",
        (resource_id, mod_guid, prop),
    )


@pytest.fixture()
def seeded(conn):
    """7 个资源 / 2 个 Library；含缺 MOD、待确认、三种类型。"""
    _add_library(conn, 1, "Alpha")
    _add_library(conn, 2, "Beta")
    _add_mod(conn, "com.installed.a")

    _add_resource(conn, 1, library_id=1, name="Alice")
    _add_resource(conn, 2, library_id=1, name="Bob")
    _add_resource(conn, 3, library_id=1, name="Carol", resource_type="outfit_card")
    _add_resource(conn, 4, library_id=1, name="Dave", resource_type="mod")
    _add_resource(conn, 5, library_id=1, name="Eve", needs_review=1)
    _add_resource(conn, 6, library_id=2, name="Frank")
    _add_resource(conn, 7, library_id=2, name="Grace", resource_type="outfit_card")

    _add_usage(conn, 2, "com.missing.x", "ChaFileFace.eyelineUpId")
    _add_usage(conn, 3, "com.missing.y", "ChaFileHair.hairId")
    _add_usage(conn, 5, "com.missing.z", "ChaFileBody.detailId")
    _add_usage(conn, 6, "com.installed.a", "ChaFileFace.Pupil1")
    return conn


def _ids(panel: BrowserPanel) -> list[int]:
    return [item.resource.id for item in panel.model.items()]


@pytest.fixture()
def window(qapp, seeded):
    w = MainWindow(BrowseService(seeded))
    yield w
    w.close()


@pytest.fixture()
def browser(window) -> BrowserPanel:
    return window.browser_panel


def _filter_bar(browser: BrowserPanel) -> FilterBar:
    return browser.filter_bar


# ---------------------------------------------------------------------------
# 默认状态
# ---------------------------------------------------------------------------


def test_default_scope_and_status(browser) -> None:
    scope = browser.scope()
    assert scope.query is None
    assert scope.resource_type is None
    assert scope.has_missing_mods is None
    assert scope.needs_review is None
    assert (scope.order_by, scope.descending) == ("name", False)
    # 默认选中第一个 Library（Alpha，id=1）→ 5 条
    assert scope.library_id == 1
    assert browser.total() == 5
    assert browser.shown() == 5
    assert browser.status_text() == "共 5 条，已显示 5 条"
    assert not browser.is_load_more_visible()


def test_filter_bar_defaults(browser) -> None:
    fb = _filter_bar(browser)
    assert fb.type_combo.currentData() is None
    assert fb.missing_check.isChecked() is False
    assert fb.needs_review_check.isChecked() is False
    assert fb.sort_combo.count() == len(SORT_OPTIONS)


# ---------------------------------------------------------------------------
# Search（含 debounce）
# ---------------------------------------------------------------------------


def test_search_is_debounced(browser) -> None:
    fb = _filter_bar(browser)
    before_total = browser.total()
    assert before_total == 5

    fb.set_query("Carol")
    # 输入后不应立即查询
    assert fb.is_search_pending()
    assert browser.total() == before_total
    assert browser.shown() == 5

    fb.flush_search()
    assert not fb.is_search_pending()
    assert browser.scope().query == "Carol"
    assert _ids(browser) == [3]
    assert browser.total() == 1
    assert browser.status_text() == "共 1 条，已显示 1 条"


def test_search_debounce_restart_emits_once(browser) -> None:
    fb = _filter_bar(browser)
    calls: list[int] = []
    fb.criteria_changed.connect(lambda: calls.append(1))

    fb.set_query("Ca")
    fb.set_query("Car")
    fb.set_query("Carol")
    assert fb.is_search_pending()
    fb.flush_search()
    assert calls == [1]


def test_empty_search_restores_all(browser) -> None:
    fb = _filter_bar(browser)
    fb.set_query("Carol")
    fb.flush_search()
    assert browser.total() == 1

    fb.set_query("")
    fb.flush_search()
    assert browser.scope().query is None
    assert browser.total() == 5


def test_search_matches_relative_path(browser) -> None:
    fb = _filter_bar(browser)
    # 搜索范围包含 relative_path（Phase 1.4-A.1）
    fb.set_query("Cards/Carol")
    fb.flush_search()
    assert _ids(browser) == [3]

    # 绝对 file_path 不是搜索字段（A.1 的决定）
    fb.set_query("D:/lib/3.png")
    fb.flush_search()
    assert _ids(browser) == []


# ---------------------------------------------------------------------------
# Resource Type
# ---------------------------------------------------------------------------


def test_resource_type_filter(browser) -> None:
    fb = _filter_bar(browser)
    fb.set_resource_type("outfit_card")
    assert browser.scope().resource_type == "outfit_card"
    assert set(_ids(browser)) == {3}

    fb.set_resource_type("mod")
    assert set(_ids(browser)) == {4}

    fb.set_resource_type("character_card")
    assert set(_ids(browser)) == {1, 2, 5}

    fb.set_resource_type(None)
    assert browser.scope().resource_type is None
    assert browser.total() == 5


def test_type_combo_uses_core_resource_types() -> None:
    from core.models import RESOURCE_TYPES

    bar = FilterBar()
    try:
        values = [bar.type_combo.itemData(i) for i in range(bar.type_combo.count())]
        assert values[0] is None
        assert values[1:] == list(RESOURCE_TYPES)
    finally:
        bar.deleteLater()


# ---------------------------------------------------------------------------
# Missing MOD / Needs Review
# ---------------------------------------------------------------------------


def test_missing_mod_checkbox(browser) -> None:
    fb = _filter_bar(browser)
    assert browser.scope().has_missing_mods is None

    fb.set_has_missing_mods(True)
    assert browser.scope().has_missing_mods is True
    assert set(_ids(browser)) == {2, 3, 5}
    assert browser.total() == 3

    fb.set_has_missing_mods(False)
    assert browser.scope().has_missing_mods is None
    assert browser.total() == 5


def test_needs_review_checkbox(browser) -> None:
    fb = _filter_bar(browser)
    assert browser.scope().needs_review is None

    fb.set_needs_review(True)
    assert browser.scope().needs_review is True
    assert _ids(browser) == [5]

    fb.set_needs_review(False)
    assert browser.scope().needs_review is None
    assert browser.total() == 5


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------


def test_sort_mapping_and_descending(browser) -> None:
    fb = _filter_bar(browser)

    fb.set_sort("name", False)
    assert _ids(browser) == [1, 2, 3, 4, 5]  # Alice..Eve（当前 Library 内）

    fb.set_sort("name", True)
    assert browser.scope().descending is True
    assert _ids(browser) == [5, 4, 3, 2, 1]

    fb.set_sort("file_size", True)
    assert (browser.scope().order_by, browser.scope().descending) == ("file_size", True)
    assert _ids(browser) == [5, 4, 3, 2, 1]  # file_size = id * 100

    fb.set_sort("file_size", False)
    assert _ids(browser) == [1, 2, 3, 4, 5]

    fb.set_sort("modified_time", True)
    assert browser.scope().order_by == "modified_time"


def test_sort_does_not_sort_in_gui(browser) -> None:
    """资源排序必须交给 core：GUI 不对**资源行**做 Python 端 sorted()。

    （C-5 起 FilterBar 会对自己的下拉选项排序——那是展示顺序，不是资源排序。）
    """
    import ui.browser_panel as bp_mod
    import ui.filter_bar as fb_mod

    bp_source = Path(bp_mod.__file__).read_text(encoding="utf-8")
    assert "sorted(" not in bp_source, "资源列表不得在 UI 端排序"

    fb_source = Path(fb_mod.__file__).read_text(encoding="utf-8")
    assert "ResourceListItem" not in fb_source, "FilterBar 不接触资源行"


# ---------------------------------------------------------------------------
# Library 联动
# ---------------------------------------------------------------------------


def test_library_switch_reloads_and_resets(browser, window) -> None:
    assert set(_ids(browser)) == {1, 2, 3, 4, 5}
    assert browser.scope().library_id == 1

    window.library_panel._list.setCurrentRow(1)  # noqa: SLF001 - 测试驱动 UI
    assert browser.scope().library_id == 2
    assert set(_ids(browser)) == {6, 7}
    assert browser.total() == 2


def test_library_switch_resets_offset(big_window) -> None:
    browser = big_window.browser_panel
    browser.click_load_more()
    assert browser.shown() == 150

    big_window.library_panel._list.setCurrentRow(1)  # noqa: SLF001 - 另一个库
    assert browser.shown() == 5          # 回到第一页（并且是另一个库）
    assert browser.total() == 5


# ---------------------------------------------------------------------------
# 有界加载：加载更多必须「追加」
# ---------------------------------------------------------------------------


@pytest.fixture()
def big_conn(tmp_path: Path):
    db_file = tmp_path / "big.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    _add_library(connection, 1, "Big")
    _add_library(connection, 2, "Small")
    for i in range(1, 151):
        _add_resource(connection, i, library_id=1, name=f"Card{i:03d}")
    for i in range(151, 156):
        _add_resource(connection, i, library_id=2, name=f"Small{i:03d}")
    yield connection
    connection.close()


@pytest.fixture()
def big_window(qapp, big_conn):
    w = MainWindow(BrowseService(big_conn))
    yield w
    w.close()


def test_bounded_loading_uses_page_size(big_window) -> None:
    browser = big_window.browser_panel
    assert PAGE_SIZE == 100
    assert browser.total() == 150
    assert browser.shown() == 100
    assert browser.status_text() == "共 150 条，已显示 100 条"
    assert browser.is_load_more_visible()
    assert browser.has_more()


def test_load_more_appends_instead_of_replacing(big_window) -> None:
    browser = big_window.browser_panel
    first_page_ids = _ids(browser)
    assert len(first_page_ids) == 100

    browser.click_load_more()

    after_ids = _ids(browser)
    assert len(after_ids) == 150
    assert after_ids[:100] == first_page_ids, "第一批必须保留（追加而不是替换）"
    assert len(set(after_ids)) == 150
    assert browser.total() == 150
    assert browser.status_text() == "共 150 条，已显示 150 条"
    assert not browser.is_load_more_visible()
    assert not browser.has_more()


def test_load_more_is_idempotent_when_exhausted(big_window) -> None:
    browser = big_window.browser_panel
    browser.click_load_more()
    browser.click_load_more()  # 已无更多
    assert browser.shown() == 150


def test_filter_change_clears_and_resets_offset(big_window) -> None:
    browser = big_window.browser_panel
    browser.click_load_more()
    assert browser.shown() == 150

    fb = _filter_bar(browser)
    fb.set_query("Card01")
    fb.flush_search()

    # 筛选变化 → 清空旧的「已加载 150」，从第一页重新开始
    assert browser.total() == 10          # Card010..Card019
    assert browser.shown() == 10
    assert browser.status_text() == "共 10 条，已显示 10 条"
    assert not browser.is_load_more_visible()


def test_model_append_items_keeps_existing(qapp) -> None:
    from core.query import ResourceSummary
    from ui.resource_model import ResourceListModel

    def make(idx: int):
        from core.query import ResourceListItem

        summary = ResourceSummary(
            id=idx,
            resource_type="character_card",
            name=f"n{idx}",
            display_name=f"n{idx}",
            file_path=f"D:/{idx}.png",
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
        return ResourceListItem(resource=summary, library_name="L", authors=())

    model = ResourceListModel()
    model.set_items([make(1), make(2)])
    model.append_items([make(3)])
    assert [i.resource.id for i in model.items()] == [1, 2, 3]
    model.append_items([])
    assert model.rowCount() == 3


# ---------------------------------------------------------------------------
# 组合筛选
# ---------------------------------------------------------------------------


def test_combined_library_search_type(browser, window) -> None:
    fb = _filter_bar(browser)
    fb.set_query("Carol")
    fb.flush_search()
    fb.set_resource_type("outfit_card")
    scope = browser.scope()
    assert (scope.library_id, scope.query, scope.resource_type) == (1, "Carol", "outfit_card")
    assert _ids(browser) == [3]

    window.library_panel._list.setCurrentRow(1)  # 切到 Beta
    assert browser.total() == 0
    assert browser.message_text() == NO_MATCH_TEXT


def test_combined_library_and_missing_mod(browser) -> None:
    fb = _filter_bar(browser)
    fb.set_has_missing_mods(True)
    assert set(_ids(browser)) == {2, 3, 5}
    assert browser.scope().library_id == 1


def test_combined_search_missing_mod_and_sort(browser) -> None:
    fb = _filter_bar(browser)
    fb.set_has_missing_mods(True)
    fb.set_sort("name", True)
    fb.set_query("o")
    fb.flush_search()
    scope = browser.scope()
    assert scope.query == "o"
    assert scope.has_missing_mods is True
    assert (scope.order_by, scope.descending) == ("name", True)
    # 缺 MOD 的 {2 Bob, 3 Carol, 5 Eve} 中含 "o" 的：Bob、Carol → 名称降序 Carol(3), Bob(2)
    assert _ids(browser) == [3, 2]


# ---------------------------------------------------------------------------
# 空状态
# ---------------------------------------------------------------------------


def test_empty_state_no_library(qapp, conn) -> None:
    w = MainWindow(BrowseService(conn))
    try:
        assert w.browser_panel.message_text() == NO_LIBRARY_TEXT
        assert w.browser_panel.total() == 0
    finally:
        w.close()


def test_empty_state_library_without_resources(qapp, conn) -> None:
    _add_library(conn, 1, "Empty")
    w = MainWindow(BrowseService(conn))
    try:
        assert w.browser_panel.message_text() == NO_RESOURCE_TEXT
    finally:
        w.close()


def test_empty_state_no_match_keeps_message_distinct(browser) -> None:
    fb = _filter_bar(browser)
    fb.set_query("zzz-no-such")
    fb.flush_search()
    assert browser.total() == 0
    assert browser.message_text() == NO_MATCH_TEXT
    assert browser.message_text() != NO_RESOURCE_TEXT
    # 筛选条件仍然存在，没有被清掉
    assert browser.scope().query == "zzz-no-such"


def test_no_match_by_type_message(browser) -> None:
    fb = _filter_bar(browser)
    fb.set_query("Alice")
    fb.flush_search()
    fb.set_resource_type("mod")
    assert browser.total() == 0
    assert browser.message_text() == NO_MATCH_TEXT


# ---------------------------------------------------------------------------
# 只读不变量
# ---------------------------------------------------------------------------


def test_search_filter_sort_is_read_only(seeded, qapp) -> None:
    conn = seeded
    before_changes = conn.total_changes
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))
    before_flags = {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    }

    w = MainWindow(BrowseService(conn))
    try:
        browser = w.browser_panel
        fb = browser.filter_bar
        fb.set_query("Car")
        fb.flush_search()
        fb.set_resource_type("outfit_card")
        fb.set_has_missing_mods(True)
        fb.set_needs_review(True)
        fb.set_sort("file_size", True)
        fb.set_query("")
        fb.flush_search()
        browser.select_row(0)
        browser.reload()
    finally:
        w.close()

    assert conn.total_changes == before_changes, "GUI 筛选不得写库"
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta
    assert {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    } == before_flags


def test_ui_still_bypasses_nothing_new() -> None:
    """UI 不得绕过 Query Layer（C-3 起允许使用 PreviewService 与线程池）。"""
    ui_dir = Path(__file__).resolve().parent.parent / "ui"
    for path in sorted(ui_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        import_lines = [
            line
            for line in source.splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        joined = "\n".join(import_lines)
        assert "ResourceQuery" not in joined, path.name
        assert "LibraryQuery" not in joined, path.name
        assert not any("sqlite3" in line for line in import_lines), path.name
