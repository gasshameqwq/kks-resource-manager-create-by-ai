"""Phase 1.4-C-4：Detail Panel 测试（离屏、临时库 / 临时缓存）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QThread  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.query import (  # noqa: E402
    BrowseService,
    ModUsage,
    ResourceAuthor,
    ResourceDetail,
    ResourceModRef,
    ResourceSummary,
    ReviewReason,
)
from core.thumbnails import (  # noqa: E402
    PREVIEW_READY as CORE_READY,
    PreviewService,
    PreviewStatus,
)
from tests.builders import write_card  # noqa: E402
from ui.browser_panel import BrowserPanel  # noqa: E402
from ui.detail_panel import (  # noqa: E402
    EMPTY_TEXT,
    DetailPanel,
    format_file_size,
    format_timestamp,
)
from ui.main_window import MainWindow  # noqa: E402
from ui.resource_model import (  # noqa: E402
    PREVIEW_FAILED,
    PREVIEW_LOADING,
    PREVIEW_MISSING,
    PREVIEW_READY,
    PREVIEW_UNSUPPORTED,
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
    cards = tmp_path / "cards"
    cards.mkdir()
    good = cards / "good.png"
    write_card(good, lastname="Good")
    bad = cards / "bad.png"
    bad.write_bytes(b"not an image")
    return {
        "good": good,
        "bad": bad,
        "missing": cards / "nope.png",
        "cache": tmp_path / "cache",
    }


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "detail.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    connection.execute(
        "INSERT INTO libraries(id, name, root_path, root_path_key)"
        " VALUES (1, 'LibOne', 'D:/l1', 'd:/l1')"
    )
    connection.execute(
        "INSERT INTO libraries(id, name, root_path, root_path_key)"
        " VALUES (2, 'LibTwo', 'D:/l2', 'd:/l2')"
    )
    yield connection
    connection.close()


def _add_resource(
    conn,
    resource_id: int,
    *,
    name: str,
    path: Path,
    extension: str = ".png",
    resource_type: str = "character_card",
    library_id: int = 1,
    card_marker: str | None = "KoiKatuCharaSun",
    file_size: int | None = 2048,
    modified_time: float | None = 1700000000.0,
    metadata_json: str | None = None,
    needs_review: int = 0,
    parse_status: str = "ok",
) -> None:
    conn.execute(
        "INSERT INTO resources(id, resource_type, name, display_name, file_path,"
        " file_path_key, relative_path, extension, card_marker, file_size,"
        " modified_time, library_id, scan_status, parse_status, needs_review,"
        " metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            resource_id,
            resource_type,
            name,
            name,
            str(path),
            str(path).casefold(),
            f"Cards/{name}{extension}",
            extension,
            card_marker,
            file_size,
            modified_time,
            library_id,
            "present",
            parse_status,
            needs_review,
            metadata_json,
        ),
    )


def _add_mod(conn, guid: str) -> None:
    conn.execute("INSERT INTO mods(guid, name) VALUES (?, ?)", (guid, guid))


def _add_usage(conn, resource_id: int, guid: str, prop: str, slot: int = 0) -> None:
    conn.execute(
        "INSERT INTO resource_mod_usages(resource_id, mod_guid, property, slot,"
        " local_slot, category_no) VALUES (?,?,?,?,0,0)",
        (resource_id, guid, prop, slot),
    )


def _add_resource_mod(conn, resource_id: int, guid: str, *, installed: bool, ref_count: int = 1) -> None:
    mod_id = None
    if installed:
        row = conn.execute("SELECT id FROM mods WHERE guid = ?", (guid,)).fetchone()
        mod_id = row["id"] if row is not None else None
    conn.execute(
        "INSERT INTO resource_mods(resource_id, mod_guid, mod_id, relation, ref_count)"
        " VALUES (?,?,?,'uses',?)",
        (resource_id, guid, mod_id, ref_count),
    )


def _add_plugin(conn, resource_id: int, guid: str) -> None:
    conn.execute(
        "INSERT INTO resource_plugins(resource_id, plugin_guid) VALUES (?, ?)",
        (resource_id, guid),
    )


def _add_author(conn, author_id: int, name: str) -> None:
    conn.execute(
        "INSERT INTO authors(id, name, name_key) VALUES (?,?,?)",
        (author_id, name, name.casefold()),
    )


def _link_author(conn, resource_id: int, author_id: int, ordinal: int) -> None:
    conn.execute(
        "INSERT INTO resource_authors(resource_id, author_id, ordinal, raw_name)"
        " VALUES (?,?,?, '')",
        (resource_id, author_id, ordinal),
    )


@pytest.fixture()
def preview_service(assets):
    return PreviewService(cache_dir=assets["cache"])


def _make_window(conn, preview_service, qapp):
    return MainWindow(BrowseService(conn), preview_service)


# ---------------------------------------------------------------------------
# 基础状态
# ---------------------------------------------------------------------------


def test_detail_panel_creation(qapp, preview_service) -> None:
    panel = DetailPanel(preview_service)
    try:
        assert panel.is_empty_state()
        assert panel.status_text() == EMPTY_TEXT
        assert panel.current_resource_id() is None
        assert panel.body_text() == EMPTY_TEXT
    finally:
        panel.deleteLater()


def test_show_missing_and_error(qapp, preview_service) -> None:
    panel = DetailPanel(preview_service)
    try:
        panel.show_missing(42)
        assert "找不到资源 #42" in panel.status_text()
        assert panel.is_empty_state()
        panel.show_error("boom")
        assert "读取详情失败" in panel.status_text()
        assert "boom" in panel.status_text()
        panel.show_empty()
        assert panel.status_text() == EMPTY_TEXT
    finally:
        panel.deleteLater()


def test_format_helpers() -> None:
    assert format_file_size(None) == "-"
    assert format_file_size(512) == "512 B"
    assert format_file_size(2048) == "2.0 KB"
    assert format_file_size(5 * 1024 * 1024) == "5.0 MB"
    assert format_timestamp(None) == "-"
    assert format_timestamp(1700000000.0).startswith("2023-")


# ---------------------------------------------------------------------------
# 详情渲染（MainWindow 集成）
# ---------------------------------------------------------------------------


import json  # noqa: E402  (放在此处避免与上方 import 块混淆)


@pytest.fixture()
def seeded(conn, assets):
    """资源 1：有 MOD(含缺失)/插件/作者/metadata；资源 2：几乎全空；资源 3：parse_partial。"""
    _add_mod(conn, "com.installed.a")
    metadata = json.dumps(
        {
            "card_version": "0.0.0",
            "user_id": "u1",
            "data_id": "d1",
            "embedded_texture_count": 3,
            "face_preview_kind": "png",
            "block_sizes": {"About": 10},
        },
        ensure_ascii=False,
    )
    _add_resource(conn, 1, name="Alpha", path=assets["good"], metadata_json=metadata)
    _add_usage(conn, 1, "com.installed.a", "ChaFileFace.Pupil1")
    _add_usage(conn, 1, "com.missing.x", "ChaFileHair.hairId")
    _add_usage(conn, 1, "com.missing.x", "outfit6.ChaFileClothes.ClothesTop")
    _add_resource_mod(conn, 1, "com.installed.a", installed=True, ref_count=1)
    _add_resource_mod(conn, 1, "com.missing.x", installed=False, ref_count=2)
    _add_plugin(conn, 1, "moreAccessories")
    _add_author(conn, 1, "Evaan")
    _add_author(conn, 2, "Anonymous")
    _link_author(conn, 1, 2, 0)   # ordinal 0 -> Anonymous
    _link_author(conn, 1, 1, 1)   # ordinal 1 -> Evaan

    _add_resource(conn, 2, name="Beta", path=assets["missing"], library_id=1)
    _add_resource(
        conn, 3, name="Gamma", path=assets["good"].parent / "gamma.png", library_id=2,
        parse_status="partial", needs_review=1,
    )
    _add_resource(
        conn, 4, name="SomeMod", path=assets["good"].parent / "m.zipmod",
        extension=".zipmod", resource_type="mod", library_id=1, card_marker=None,
    )
    _add_resource(conn, 5, name="Broken", path=assets["bad"], library_id=1)
    return conn


@pytest.fixture()
def sel_window(qapp, seeded, preview_service):
    w = MainWindow(BrowseService(seeded), preview_service)
    yield w
    w.close()


def _select(window, resource_id: int) -> None:
    window._on_resource_selected(resource_id)  # noqa: SLF001 - 直接驱动选择


def test_identity_and_basic_sections(sel_window) -> None:
    _select(sel_window, 1)
    panel = sel_window.detail_panel
    identity = panel.identity_rows()
    assert identity["标题"] == "Alpha"
    assert identity["类型"] == "character_card"
    assert identity["游戏"] == "KKS"
    assert identity["资源库"] == "LibOne"
    assert identity["相对路径"].endswith("Alpha.png")

    basic = panel.basic_rows()
    assert basic["文件类型"] == ".png"
    assert basic["文件大小"] == "2.0 KB"
    assert basic["扫描状态"] == "present"
    assert basic["解析状态"] == "ok"
    assert basic["修改时间"].startswith("2023-")


def test_authors_follow_dto_order_and_empty(sel_window) -> None:
    _select(sel_window, 1)
    assert sel_window.detail_panel.authors_text() == "Anonymous\nEvaan"
    _select(sel_window, 2)
    assert sel_window.detail_panel.authors_text() == "无作者信息"


def test_mod_table_installed_missing_counts_and_categories(sel_window) -> None:
    _select(sel_window, 1)
    panel = sel_window.detail_panel
    rows = panel.mod_rows()
    assert rows[0] == ("已安装", "com.installed.a", 1, "face")
    status, guid, ref_count, categories = rows[1]
    assert status == "缺失"
    assert guid == "com.missing.x"
    assert ref_count == 2
    assert "hair" in categories and "clothes" in categories
    assert panel.mod_table.isVisibleTo(panel.mods_section) is True
    assert panel.mods_empty_label.isVisibleTo(panel.mods_section) is False


def test_mod_table_empty(sel_window) -> None:
    _select(sel_window, 2)
    panel = sel_window.detail_panel
    assert panel.mod_rows() == []
    assert panel.mod_table.isVisibleTo(panel.mods_section) is False
    assert panel.mods_empty_label.isVisibleTo(panel.mods_section) is True


def test_usage_summary_and_detail(sel_window) -> None:
    _select(sel_window, 1)
    panel = sel_window.detail_panel
    assert panel.usage_summary() == {"face": 1, "hair": 1, "clothes": 1}
    assert len(panel.usage_detail_rows()) == 3
    assert all("slot=" in row for row in panel.usage_detail_rows())


def test_usage_detail_collapsed_by_default(sel_window) -> None:
    _select(sel_window, 1)
    panel = sel_window.detail_panel
    assert panel.section_expanded("usage") is True
    assert panel.usage_detail_section.is_expanded() is False


def test_usage_empty(sel_window) -> None:
    _select(sel_window, 2)
    panel = sel_window.detail_panel
    assert panel.usage_summary() == {}
    assert panel.usage_detail_rows() == []
    assert panel.usage_summary_label.text() == "无 usage"


def test_plugins_list_and_empty(sel_window) -> None:
    _select(sel_window, 1)
    assert sel_window.detail_panel.plugin_rows() == ["moreAccessories"]
    assert sel_window.detail_panel.section_expanded("plugins") is False
    _select(sel_window, 2)
    panel = sel_window.detail_panel
    assert panel.plugin_rows() == []
    assert panel.plugins_label.text() == "无插件"


def test_metadata_readable_and_raw_json(sel_window) -> None:
    _select(sel_window, 1)
    panel = sel_window.detail_panel
    rows = panel.metadata_rows()
    assert rows["card_version"] == "0.0.0"
    assert rows["user_id"] == "u1"
    assert rows["data_id"] == "d1"
    assert rows["embedded_texture_count"] == "3"
    assert rows["face_preview_kind"] == "png"
    assert "block_sizes" not in rows, "非人可读键不放进表单"
    assert '"block_sizes"' in panel.raw_metadata_text()
    assert panel.is_raw_metadata_read_only() is True
    assert panel.raw_metadata_section.is_expanded() is False


def test_metadata_empty(sel_window) -> None:
    _select(sel_window, 2)
    panel = sel_window.detail_panel
    assert panel.metadata_rows() == {}
    assert panel.raw_metadata_text() == ""
    assert panel.metadata_empty_label.isVisibleTo(panel.metadata_section) is True


def test_review_normal_and_with_reasons(sel_window) -> None:
    _select(sel_window, 1)
    assert sel_window.detail_panel.review_text() == "状态正常"
    assert sel_window.detail_panel.review_rows()["待确认"] == "否"

    _select(sel_window, 3)
    panel = sel_window.detail_panel
    assert "解析不完整" in panel.review_text()
    assert panel.review_rows()["待确认"] == "是"
    assert panel.review_reasons()[0].code == "parse_partial"


# ---------------------------------------------------------------------------
# Selection 生命周期
# ---------------------------------------------------------------------------


def test_selection_a_to_b(sel_window) -> None:
    _select(sel_window, 1)
    assert sel_window.detail_panel.current_resource_id() == 1
    assert sel_window.detail_panel.title_text() == "Alpha"
    _select(sel_window, 2)
    assert sel_window.detail_panel.current_resource_id() == 2
    assert sel_window.detail_panel.title_text() == "Beta"


def test_selection_cleared_to_none(sel_window) -> None:
    _select(sel_window, 1)
    _select(sel_window, None)
    panel = sel_window.detail_panel
    assert panel.current_resource_id() is None
    assert panel.is_empty_state()
    assert panel.status_text() == EMPTY_TEXT


def test_missing_resource_id(sel_window) -> None:
    _select(sel_window, 999999)
    panel = sel_window.detail_panel
    assert panel.is_empty_state()
    assert "找不到资源 #999999" in panel.status_text()


def test_reload_clears_detail(sel_window) -> None:
    """列表变了，详情不得残留旧资源。"""
    _select(sel_window, 1)
    assert sel_window.detail_panel.current_resource_id() == 1

    browser = sel_window.browser_panel
    browser.filter_bar.set_query("Beta")
    browser.filter_bar.flush_search()

    assert [i.resource.id for i in browser.model.items()] == [2]
    assert sel_window.detail_panel.current_resource_id() is None
    assert sel_window.detail_panel.is_empty_state()


def test_library_switch_does_not_keep_old_detail(sel_window) -> None:
    _select(sel_window, 1)
    assert sel_window.detail_panel.current_resource_id() == 1

    sel_window.library_panel._list.setCurrentRow(1)  # noqa: SLF001 - 切到 LibTwo
    assert sel_window.browser_panel.scope().library_id == 2
    assert sel_window.detail_panel.current_resource_id() is None
    assert sel_window.detail_panel.is_empty_state()


def test_query_failure_shows_error(sel_window, monkeypatch) -> None:
    def boom(_resource_id):
        raise RuntimeError("db down")

    monkeypatch.setattr(sel_window._service, "detail", boom)  # noqa: SLF001
    _select(sel_window, 1)
    panel = sel_window.detail_panel
    assert "读取详情失败" in panel.status_text()
    assert "db down" in panel.status_text()


# ---------------------------------------------------------------------------
# Preview 集成
# ---------------------------------------------------------------------------


def test_preview_ready_for_card(sel_window) -> None:
    _select(sel_window, 1)
    panel = sel_window.detail_panel
    assert panel.preview_state() == PREVIEW_LOADING
    assert panel.wait_for_previews()
    assert panel.preview_state() == PREVIEW_READY
    pixmap = panel.preview_pixmap()
    assert pixmap is not None and not pixmap.isNull()


def test_preview_unsupported_for_mod(sel_window) -> None:
    _select(sel_window, 4)
    panel = sel_window.detail_panel
    assert panel.preview_state() == PREVIEW_UNSUPPORTED
    assert panel.pending_preview_count() == 0


def test_preview_missing_for_absent_file(sel_window) -> None:
    _select(sel_window, 2)
    panel = sel_window.detail_panel
    assert panel.preview_state() == PREVIEW_MISSING
    assert panel.pending_preview_count() == 0


def test_preview_failed_for_broken_image(sel_window) -> None:
    _select(sel_window, 5)
    panel = sel_window.detail_panel
    assert panel.preview_state() == PREVIEW_LOADING
    assert panel.wait_for_previews()
    assert panel.preview_state() == PREVIEW_FAILED


def test_preview_cache_hit_skips_worker(qapp, seeded, preview_service) -> None:
    first = MainWindow(BrowseService(seeded), preview_service)
    try:
        _select(first, 1)
        assert first.detail_panel.wait_for_previews()
        assert first.detail_panel.preview_state() == PREVIEW_READY
    finally:
        first.close()

    second = MainWindow(BrowseService(seeded), preview_service)
    try:
        _select(second, 1)
        assert second.detail_panel.preview_state() == PREVIEW_READY
        assert second.detail_panel.pending_preview_count() == 0
    finally:
        second.close()


def test_selection_epoch_increments(sel_window) -> None:
    _select(sel_window, 1)
    first = sel_window.detail_panel.preview_epoch()
    _select(sel_window, 2)
    assert sel_window.detail_panel.preview_epoch() == first + 1


def test_stale_preview_result_is_discarded(sel_window, assets) -> None:
    _select(sel_window, 1)
    sel_window.detail_panel.wait_for_previews()
    panel = sel_window.detail_panel
    stale = panel.preview_epoch() - 1

    panel._set_preview_state(PREVIEW_LOADING)  # noqa: SLF001
    panel._on_preview_finished(  # noqa: SLF001 - 过期结果
        1, stale, PreviewStatus(CORE_READY, "k", assets["good"])
    )
    assert panel.preview_state() == PREVIEW_LOADING

    panel._on_preview_finished(  # noqa: SLF001 - 当前结果
        1, panel.preview_epoch(), PreviewStatus(CORE_READY, "k", assets["good"])
    )
    assert panel.preview_state() == PREVIEW_READY


def test_stale_result_for_other_resource_is_ignored(sel_window, assets) -> None:
    _select(sel_window, 2)
    panel = sel_window.detail_panel
    panel._set_preview_state(PREVIEW_LOADING)  # noqa: SLF001
    # epoch 相同但 resource_id 不是当前资源 → 丢弃
    panel._on_preview_finished(  # noqa: SLF001
        1, panel.preview_epoch(), PreviewStatus(CORE_READY, "k", assets["good"])
    )
    assert panel.preview_state() == PREVIEW_LOADING


def test_pixmap_created_on_gui_thread(qapp, seeded, preview_service) -> None:
    threads: list[object] = []
    real = DetailPanel._load_pixmap

    def spy(path):
        threads.append(QThread.currentThread())
        return real(path)

    DetailPanel._load_pixmap = staticmethod(spy)  # type: ignore[assignment]
    w = None
    try:
        w = MainWindow(BrowseService(seeded), preview_service)
        _select(w, 1)
        w.detail_panel.wait_for_previews()
    finally:
        if w is not None:
            w.close()
        DetailPanel._load_pixmap = staticmethod(real)  # type: ignore[assignment]

    assert threads, "应当有 QPixmap 加载"
    assert all(t is qapp.thread() for t in threads), "QPixmap 只能在 GUI 线程创建"


# ---------------------------------------------------------------------------
# 只读不变量 / 架构约束
# ---------------------------------------------------------------------------


def test_detail_does_not_write_database(seeded, qapp, preview_service) -> None:
    conn = seeded
    before_changes = conn.total_changes
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))
    before_flags = {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    }
    before_counts = {
        table: conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"]
        for table in ("resources", "mods", "resource_mods", "resource_mod_usages",
                      "resource_plugins", "resource_authors")
    }

    w = MainWindow(BrowseService(conn), preview_service)
    try:
        for rid in (1, 2, 3, 4, 5):
            _select(w, rid)
            w.detail_panel.wait_for_previews()
        _select(w, None)
    finally:
        w.close()

    assert conn.total_changes == before_changes, "详情面板不得写库"
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta
    assert {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    } == before_flags
    assert {
        table: conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"]
        for table in ("resources", "mods", "resource_mods", "resource_mod_usages",
                      "resource_plugins", "resource_authors")
    } == before_counts


def test_source_files_not_modified(seeded, qapp, preview_service, assets) -> None:
    before = {
        key: (assets[key].stat().st_size, assets[key].stat().st_mtime_ns)
        for key in ("good", "bad")
    }
    w = MainWindow(BrowseService(seeded), preview_service)
    try:
        for rid in (1, 5):
            _select(w, rid)
            w.detail_panel.wait_for_previews()
    finally:
        w.close()
    after = {
        key: (assets[key].stat().st_size, assets[key].stat().st_mtime_ns)
        for key in ("good", "bad")
    }
    assert before == after


def test_detail_panel_has_no_sql_or_query_layer_access() -> None:
    import ui.detail_panel as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert ".execute(" not in source
    assert "SELECT " not in source.upper()
    import_lines = [
        line
        for line in source.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    joined = "\n".join(import_lines)
    for forbidden in ("sqlite3", "ResourceQuery", "ModQuery", "AuthorQuery", "PluginQuery", "UsageQuery"):
        assert forbidden not in joined, f"DetailPanel 不得使用 {forbidden}"


def test_missing_marked_from_dto_not_recomputed() -> None:
    """installed/missing 只能来自 DTO 的 `installed` 字段。"""
    import ui.detail_panel as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "mod.installed" in source
    # 不得自己查 mods 表 / 自己 JOIN
    upper = source.upper()
    assert " LEFT JOIN" not in upper and " INNER JOIN" not in upper
    assert "SELECT " not in upper
    assert "mod_id IS NULL" not in source
