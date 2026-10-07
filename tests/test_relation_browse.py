"""Phase 1.4-C-5：关系反向查询（MOD / Author / Plugin → Resource）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.query import (  # noqa: E402
    AuthorQuery,
    BrowseService,
    ModQuery,
    PluginQuery,
)
from core.thumbnails import PreviewService  # noqa: E402
from ui.browser_panel import NO_MATCH_TEXT, NO_RESOURCE_TEXT  # noqa: E402
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
    db_file = tmp_path / "relation.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    connection.execute(
        "INSERT INTO libraries(id, name, root_path, root_path_key)"
        " VALUES (1, 'LibOne', 'D:/l1', 'd:/l1')"
    )
    yield connection
    connection.close()


def _add_resource(
    conn,
    resource_id: int,
    *,
    name: str,
    resource_type: str = "character_card",
    needs_review: int = 0,
) -> None:
    conn.execute(
        "INSERT INTO resources(id, resource_type, name, display_name, file_path,"
        " file_path_key, relative_path, extension, library_id, scan_status,"
        " parse_status, needs_review) VALUES (?,?,?,?,?,?,?,?,?,'present','ok',?)",
        (
            resource_id,
            resource_type,
            name,
            name,
            f"D:/l1/{name}.png",
            f"d:/l1/{name}.png".casefold(),
            f"Cards/{name}.png",
            ".png",
            1,
            needs_review,
        ),
    )


def _add_mod(conn, guid: str, name: str | None = None) -> None:
    conn.execute("INSERT INTO mods(guid, name) VALUES (?, ?)", (guid, name or guid))


def _add_usage(conn, resource_id: int, guid: str, prop: str) -> None:
    conn.execute(
        "INSERT INTO resource_mod_usages(resource_id, mod_guid, property, slot,"
        " local_slot, category_no) VALUES (?,?,?,0,0,0)",
        (resource_id, guid, prop),
    )


def _add_resource_mod(conn, resource_id: int, guid: str, *, installed: bool) -> None:
    mod_id = None
    if installed:
        row = conn.execute("SELECT id FROM mods WHERE guid = ?", (guid,)).fetchone()
        mod_id = row["id"] if row is not None else None
    conn.execute(
        "INSERT INTO resource_mods(resource_id, mod_guid, mod_id, relation, ref_count)"
        " VALUES (?,?,?,'uses',1)",
        (resource_id, guid, mod_id),
    )


def _add_plugin(conn, resource_id: int, guid: str) -> None:
    conn.execute(
        "INSERT INTO resource_plugins(resource_id, plugin_guid) VALUES (?,?)",
        (resource_id, guid),
    )


def _add_author(conn, author_id: int, name: str) -> None:
    conn.execute(
        "INSERT INTO authors(id, name, name_key) VALUES (?,?,?)",
        (author_id, name, name.casefold()),
    )


def _link_author(conn, resource_id: int, author_id: int, ordinal: int = 0) -> None:
    conn.execute(
        "INSERT INTO resource_authors(resource_id, author_id, ordinal, raw_name)"
        " VALUES (?,?,?,'')",
        (resource_id, author_id, ordinal),
    )


@pytest.fixture()
def seeded(conn):
    """R1: installed.a + missing.x / Evaan / moreAccessories
    R2: installed.a / Anonymous / moreAccessories
    R3: missing.y / Evaan / KSOX
    R4: 无关系；另有 1 个未使用的已安装 MOD（orphan）与 1 个无资源作者。"""
    _add_mod(conn, "com.installed.a", "InstalledMod")
    _add_mod(conn, "orphan.mod", "OrphanMod")
    _add_resource(conn, 1, name="Alice")
    _add_resource(conn, 2, name="Bob")
    _add_resource(conn, 3, name="Carol", resource_type="outfit_card")
    _add_resource(conn, 4, name="Dave")

    _add_usage(conn, 1, "com.installed.a", "ChaFileFace.Pupil1")
    _add_usage(conn, 1, "missing.x", "ChaFileHair.hairId")
    _add_usage(conn, 2, "com.installed.a", "ChaFileFace.Pupil1")
    _add_usage(conn, 3, "missing.y", "outfit6.ChaFileClothes.ClothesTop")
    _add_resource_mod(conn, 1, "com.installed.a", installed=True)
    _add_resource_mod(conn, 1, "missing.x", installed=False)
    _add_resource_mod(conn, 2, "com.installed.a", installed=True)
    _add_resource_mod(conn, 3, "missing.y", installed=False)

    _add_plugin(conn, 1, "moreAccessories")
    _add_plugin(conn, 2, "moreAccessories")
    _add_plugin(conn, 3, "KSOX")

    _add_author(conn, 1, "Evaan")
    _add_author(conn, 2, "Anonymous")
    _add_author(conn, 3, "Unused")
    _link_author(conn, 1, 1)
    _link_author(conn, 3, 1)
    _link_author(conn, 2, 2)
    return conn


@pytest.fixture()
def window(qapp, seeded, tmp_path):
    w = MainWindow(BrowseService(seeded), PreviewService(cache_dir=tmp_path / "cache"))
    yield w
    w.close()


# ---------------------------------------------------------------------------
# C-5-a：BrowseService 关系查询转发
# ---------------------------------------------------------------------------


def test_authors_forwarding(seeded) -> None:
    service = BrowseService(seeded)
    authors = service.authors()
    assert [(a.id, a.name, a.resource_count) for a in authors] == [
        (2, "Anonymous", 1),
        (1, "Evaan", 2),
        (3, "Unused", 0),
    ]
    # 与底层 Query 完全一致
    assert authors == AuthorQuery(seeded).list()
    # with_resources=True 过滤掉没有资源的作者
    filtered = service.authors(with_resources=True)
    assert [a.name for a in filtered] == ["Anonymous", "Evaan"]


def test_plugins_forwarding(seeded) -> None:
    service = BrowseService(seeded)
    plugins = service.plugins()
    assert [(p.plugin_guid, p.resource_count) for p in plugins] == [
        ("KSOX", 1),
        ("moreAccessories", 2),
    ]
    assert plugins == PluginQuery(seeded).list()


def test_missing_mods_forwarding(seeded) -> None:
    service = BrowseService(seeded)
    missing = service.missing_mods()
    assert {m.guid for m in missing} == {"missing.x", "missing.y"}
    assert all(m.installed is False for m in missing)
    assert all(m.used_by_count >= 1 for m in missing)
    assert missing == ModQuery(seeded).missing()


def test_orphan_mods_forwarding(seeded) -> None:
    service = BrowseService(seeded)
    orphans = service.orphan_mods()
    assert [m.guid for m in orphans] == ["orphan.mod"]
    assert orphans[0].installed is True
    assert orphans == ModQuery(seeded).orphan()


def test_relation_apis_are_read_only(seeded) -> None:
    conn = seeded
    before = conn.total_changes
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))
    service = BrowseService(conn)
    for _ in range(3):
        service.authors()
        service.authors(with_resources=True)
        service.plugins()
        service.missing_mods()
        service.orphan_mods()
    assert conn.total_changes == before
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta


def test_browse_service_relation_methods_have_no_sql() -> None:
    """BrowseService 只做转发：不得出现 SQL。"""
    import core.query.browse as browse_mod

    source = Path(browse_mod.__file__).read_text(encoding="utf-8")
    assert ".execute(" not in source
    assert "SELECT " not in source.upper()


# ---------------------------------------------------------------------------
# C-5-b：FilterBar 关系筛选
# ---------------------------------------------------------------------------


def test_filter_bar_defaults_are_none(window) -> None:
    fb = window.browser_panel.filter_bar
    assert fb.author_id() is None
    assert fb.plugin_guid() is None
    assert fb.mod_guid() is None
    assert fb.author_combo.itemData(0) is None
    assert fb.plugin_combo.itemData(0) is None
    assert fb.mod_combo.itemData(0) is None


def test_filter_bar_options_are_populated_from_service(window) -> None:
    fb = window.browser_panel.filter_bar
    # 全部 + 2 个有资源的作者（Unused 被 with_resources=True 过滤）
    assert fb.author_combo.count() == 3
    assert sorted(
        fb.author_combo.itemData(i) for i in range(1, fb.author_combo.count())
    ) == [1, 2]
    # 全部 + 2 个插件
    assert fb.plugin_combo.count() == 3
    # 全部 + 2 个缺失 MOD
    assert fb.mod_combo.count() == 3
    assert fb.mod_combo.isEditable() is True


def test_filter_bar_mod_combo_sorted_by_used_by(window) -> None:
    fb = window.browser_panel.filter_bar
    # missing.x / missing.y 都被 1 个资源使用 → 按 guid 升序
    assert [fb.mod_combo.itemText(i) for i in range(1, 3)] == [
        "missing.x（1）",
        "missing.y（1）",
    ]


def test_filter_bar_author_selection_updates_scope_and_result(window) -> None:
    bp = window.browser_panel
    fb = bp.filter_bar
    assert bp.total() == 4
    fb.set_author(1)   # Evaan
    assert bp.scope().author_id == 1
    assert {i.resource.id for i in bp.model.items()} == {1, 3}
    assert bp.total() == 2


def test_filter_bar_plugin_selection_updates_scope_and_result(window) -> None:
    bp = window.browser_panel
    fb = bp.filter_bar
    fb.set_plugin("moreAccessories")
    assert bp.scope().plugin_guid == "moreAccessories"
    assert {i.resource.id for i in bp.model.items()} == {1, 2}
    fb.set_plugin("KSOX")
    assert {i.resource.id for i in bp.model.items()} == {3}


def test_filter_bar_mod_selection_updates_scope_and_result(window) -> None:
    bp = window.browser_panel
    fb = bp.filter_bar
    fb.set_missing_mod("missing.y")
    assert bp.scope().mod_guid == "missing.y"
    assert {i.resource.id for i in bp.model.items()} == {3}
    fb.set_missing_mod("missing.x")
    assert {i.resource.id for i in bp.model.items()} == {1}


def test_filter_bar_set_missing_mod_accepts_installed_guid(window) -> None:
    """详情面板可能传入已安装 MOD（不在缺失列表里）→ 临时补条目。"""
    bp = window.browser_panel
    fb = bp.filter_bar
    assert fb.mod_combo.findData("com.installed.a") < 0
    fb.set_missing_mod("com.installed.a")
    assert fb.mod_guid() == "com.installed.a"
    assert {i.resource.id for i in bp.model.items()} == {1, 2}


def test_filter_bar_clear_relation_filters(window) -> None:
    bp = window.browser_panel
    fb = bp.filter_bar
    fb.set_author(1)
    fb.set_plugin("moreAccessories")
    fb.set_missing_mod("missing.x")
    assert bp.total() < 4

    fb.clear_relation_filters()
    assert fb.author_id() is None
    assert fb.plugin_guid() is None
    assert fb.mod_guid() is None
    assert bp.total() == 4


# ---------------------------------------------------------------------------
# C-5-b：与其它筛选组合
# ---------------------------------------------------------------------------


def test_search_combined_with_relation(window) -> None:
    bp = window.browser_panel
    fb = bp.filter_bar
    fb.set_author(1)
    fb.set_query("Carol")
    fb.flush_search()
    assert bp.scope().query == "Carol" and bp.scope().author_id == 1
    assert {i.resource.id for i in bp.model.items()} == {3}

    fb.set_query("Bob")   # Bob 属于 Anonymous，不属于 Evaan
    fb.flush_search()
    assert bp.total() == 0


def test_type_combined_with_relation(window) -> None:
    bp = window.browser_panel
    fb = bp.filter_bar
    fb.set_plugin("KSOX")
    fb.set_resource_type("outfit_card")
    assert bp.scope().resource_type == "outfit_card"
    assert {i.resource.id for i in bp.model.items()} == {3}
    fb.set_resource_type("character_card")
    assert bp.total() == 0


def test_missing_mod_combined_with_specific_mod(window) -> None:
    bp = window.browser_panel
    fb = bp.filter_bar
    fb.set_has_missing_mods(True)
    assert {i.resource.id for i in bp.model.items()} == {1, 3}
    fb.set_missing_mod("missing.x")
    scope = bp.scope()
    assert scope.has_missing_mods is True and scope.mod_guid == "missing.x"
    assert {i.resource.id for i in bp.model.items()} == {1}


def test_review_combined_with_relation(window) -> None:
    bp = window.browser_panel
    fb = bp.filter_bar
    fb.set_author(1)
    fb.set_needs_review(True)
    assert bp.total() == 0
    assert bp.message_text() == NO_MATCH_TEXT
    assert bp.message_text() != NO_RESOURCE_TEXT
    assert bp.scope().author_id == 1 and bp.scope().needs_review is True


def test_sort_combined_with_relation(window) -> None:
    bp = window.browser_panel
    fb = bp.filter_bar
    fb.set_author(1)
    fb.set_sort("name", True)
    assert bp.scope().order_by == "name" and bp.scope().descending is True
    assert [i.resource.id for i in bp.model.items()] == [3, 1]  # Carol, Alice


def test_zero_result_active_filter_text_for_each_relation(window) -> None:
    bp = window.browser_panel
    fb = bp.filter_bar

    # 作者筛选 → 0 结果（Anonymous 没有 KSOX）
    fb.set_author(2)
    fb.set_plugin("KSOX")
    assert bp.total() == 0
    assert bp.message_text() == NO_MATCH_TEXT
    assert bp.message_text() != NO_RESOURCE_TEXT

    fb.clear_relation_filters()
    # 插件筛选 → 0 结果（KSOX 没有 character_card）
    fb.set_plugin("KSOX")
    fb.set_resource_type("character_card")
    assert bp.total() == 0
    assert bp.message_text() == NO_MATCH_TEXT

    fb.clear_relation_filters()
    fb.set_resource_type(None)
    # MOD 筛选 → 0 结果（不存在的 guid）
    fb.set_missing_mod("no.such.mod")
    assert bp.total() == 0
    assert bp.message_text() == NO_MATCH_TEXT


def test_apply_relation_filter_from_panel(window) -> None:
    bp = window.browser_panel
    bp.apply_relation_filter(mod_guid="missing.y")
    assert bp.scope().mod_guid == "missing.y"
    assert {i.resource.id for i in bp.model.items()} == {3}
    bp.reload_relation_options()
    assert bp.filter_bar.mod_combo.count() >= 3


# ---------------------------------------------------------------------------
# C-5-c：DetailPanel → MOD → Resource 闭环
# ---------------------------------------------------------------------------


def test_mod_filter_button_requires_selection(window) -> None:
    window._on_resource_selected(1)  # noqa: SLF001
    panel = window.detail_panel
    assert len(panel.mod_rows()) == 2
    assert panel.is_mod_filter_enabled() is False
    panel.select_mod_row(0)
    assert panel.is_mod_filter_enabled() is True


def test_mod_filter_button_disabled_without_mods(window) -> None:
    window._on_resource_selected(4)  # noqa: SLF001 - Dave 没有 MOD
    panel = window.detail_panel
    assert panel.mod_rows() == []
    assert panel.is_mod_filter_enabled() is False


def test_mod_filter_emits_installed_and_missing_guids(window) -> None:
    window._on_resource_selected(1)  # noqa: SLF001
    panel = window.detail_panel
    received: list[str] = []
    panel.mod_filter_requested.connect(lambda guid: received.append(guid))

    # rows 按 guid 排序：com.installed.a（已安装）、missing.x（缺失）
    panel.select_mod_row(0)
    panel.click_mod_filter()
    panel.select_mod_row(1)
    panel.click_mod_filter()
    assert received == ["com.installed.a", "missing.x"]


def test_detail_to_browser_closure(window) -> None:
    """点击「按此 MOD 筛选」→ MainWindow → BrowserPanel 应用 mod_guid。"""
    bp = window.browser_panel
    window._on_resource_selected(1)  # noqa: SLF001
    panel = window.detail_panel

    panel.select_mod_row(0)      # com.installed.a → 被 R1/R2 使用
    panel.click_mod_filter()
    assert bp.scope().mod_guid == "com.installed.a"
    assert {i.resource.id for i in bp.model.items()} == {1, 2}

    # 闭环后 detail 已因 reload 清空 → 重新选中再按第二个 MOD
    window._on_resource_selected(1)  # noqa: SLF001
    panel.select_mod_row(1)          # missing.x → 只有 R1
    panel.click_mod_filter()
    assert bp.scope().mod_guid == "missing.x"
    assert {i.resource.id for i in bp.model.items()} == {1}


def test_reload_after_closure_keeps_selection_lifecycle(window) -> None:
    bp = window.browser_panel
    window._on_resource_selected(1)  # noqa: SLF001
    window.detail_panel.select_mod_row(0)
    window.detail_panel.click_mod_filter()
    # 列表已被替换 → 详情必须清空（C-4 行为不回归）
    assert window.detail_panel.current_resource_id() is None
    assert window.detail_panel.is_empty_state()


# ---------------------------------------------------------------------------
# 架构约束 / 只读不变量
# ---------------------------------------------------------------------------


def test_ui_does_not_import_query_layer_relation_classes() -> None:
    ui_dir = Path(__file__).resolve().parent.parent / "ui"
    for path in sorted(ui_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        import_lines = [
            line
            for line in source.splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        joined = "\n".join(import_lines)
        for forbidden in (
            "ModQuery",
            "AuthorQuery",
            "PluginQuery",
            "ResourceQuery",
            "UsageQuery",
            "sqlite3",
        ):
            assert forbidden not in joined, f"{path.name} 不得使用 {forbidden}"


def test_relation_browse_is_read_only(seeded, qapp, tmp_path) -> None:
    conn = seeded
    before_changes = conn.total_changes
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))
    before_flags = {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    }
    tables = (
        "resources",
        "mods",
        "resource_mods",
        "resource_mod_usages",
        "resource_plugins",
        "resource_authors",
    )
    before_counts = {
        t: conn.execute(f"SELECT count(*) AS c FROM {t}").fetchone()["c"] for t in tables
    }

    w = MainWindow(BrowseService(conn), PreviewService(cache_dir=tmp_path / "cache"))
    try:
        fb = w.browser_panel.filter_bar
        fb.set_author(1)
        fb.set_plugin("moreAccessories")
        fb.set_missing_mod("missing.x")
        fb.clear_relation_filters()
        w._on_resource_selected(1)      # noqa: SLF001
        w.detail_panel.select_mod_row(0)
        w.detail_panel.click_mod_filter()
        w.browser_panel.wait_for_previews()
    finally:
        w.close()

    assert conn.total_changes == before_changes, "关系反查不得写库"
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta
    assert {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    } == before_flags
    assert {
        t: conn.execute(f"SELECT count(*) AS c FROM {t}").fetchone()["c"] for t in tables
    } == before_counts
