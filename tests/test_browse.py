"""Phase 1.4-B.3-a：Browse Read Model 测试。

Browse 层是只读的「查询编排 + 行模型」，**不含自有 SQL**，全部复用
``LibraryQuery`` / ``ResourceQuery``。
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.app import TagWriteService  # noqa: E402
from core.database import db as database  # noqa: E402
from core.database import schema as schema_mod  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.query import (  # noqa: E402
    REVIEW_REASON_PARSE_PARTIAL,
    AuthorQuery,
    BrowsePage,
    BrowseService,
    BrowserScope,
    LibraryQuery,
    ResourceListItem,
    ResourceQuery,
)
from core.scanner import LibraryScanner  # noqa: E402


# ---------------------------------------------------------------------------
# 夹具 / 构造器
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "browse.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    yield connection
    connection.close()


def _add_library(conn, library_id: int, name: str, root: str, *, enabled: int = 1) -> None:
    conn.execute(
        "INSERT INTO libraries(id, name, root_path, root_path_key, enabled)"
        " VALUES (?, ?, ?, ?, ?)",
        (library_id, name, root, root.casefold(), enabled),
    )


def _add_resource(
    conn,
    resource_id: int,
    *,
    name: str,
    resource_type: str = "character_card",
    library_id: int | None = None,
    needs_review: int = 0,
    parse_status: str = "ok",
    card_marker: str | None = None,
    relative_path: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO resources(id, resource_type, name, display_name, file_path,"
        " file_path_key, relative_path, card_marker, library_id, needs_review,"
        " parse_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            resource_id,
            resource_type,
            name,
            name,
            f"D:/lib/{resource_id}.png",
            f"d:/lib/{resource_id}.png",
            relative_path,
            card_marker,
            library_id,
            needs_review,
            parse_status,
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


def _add_resource_mod(conn, resource_id: int, mod_guid: str, ref_count: int = 1) -> None:
    """汇总关系（``resource_mods``）——详情 / ``mod_count`` 用它。"""
    row = conn.execute("SELECT id FROM mods WHERE guid = ?", (mod_guid,)).fetchone()
    conn.execute(
        "INSERT INTO resource_mods(resource_id, mod_guid, mod_id, relation, ref_count)"
        " VALUES (?, ?, ?, 'uses', ?)",
        (resource_id, mod_guid, row["id"] if row else None, ref_count),
    )


def _add_plugin(conn, resource_id: int, guid: str) -> None:
    conn.execute(
        "INSERT INTO resource_plugins(resource_id, plugin_guid) VALUES (?, ?)",
        (resource_id, guid),
    )


def _add_author(conn, author_id: int, name: str) -> None:
    conn.execute(
        "INSERT INTO authors(id, name, name_key) VALUES (?, ?, ?)",
        (author_id, name, name.casefold()),
    )


def _link_author(conn, resource_id: int, author_id: int, ordinal: int = 0) -> None:
    conn.execute(
        "INSERT INTO resource_authors(resource_id, author_id, ordinal, raw_name)"
        " VALUES (?, ?, ?, ?)",
        (resource_id, author_id, ordinal, ""),
    )


@pytest.fixture()
def seeded(conn):
    """10 个资源 / 3 个 Library（含 1 个 disabled）的合成库。"""
    _add_library(conn, 1, "Alpha", "D:/a")
    _add_library(conn, 2, "Beta", "D:/b")
    _add_library(conn, 3, "Gamma", "D:/c", enabled=0)
    _add_mod(conn, "com.installed.a")
    _add_mod(conn, "com.installed.b")

    _add_resource(conn, 1, name="Zoe", library_id=1, card_marker="KoiKatuCharaSun")
    _add_resource(conn, 2, name="Bob", library_id=1, card_marker="KoiKatuCharaSun")
    _add_resource(conn, 3, name="Carol", library_id=1, card_marker="KoiKatuCharaSun")
    _add_resource(
        conn,
        4,
        name="Dave",
        library_id=1,
        needs_review=1,
        parse_status="partial",
        card_marker="KoiKatuChara",
    )
    _add_resource(
        conn,
        5,
        name="Eve",
        resource_type="outfit_card",
        library_id=2,
        relative_path="Outfits/EveDress.png",
    )
    _add_resource(conn, 6, name="Frank", library_id=2, card_marker="KoiKatuCharaSun")
    _add_resource(conn, 7, name="Grace", resource_type="mod", library_id=2)
    _add_resource(conn, 8, name="Heidi", library_id=3, card_marker="KoiKatuCharaSun")
    _add_resource(conn, 9, name="Ivan", library_id=1, card_marker="KoiKatuCharaSun")
    _add_resource(conn, 10, name="Judy", library_id=None, card_marker="KoiKatuCharaSun")

    _add_usage(conn, 2, "com.installed.a", "ChaFileBody.detailId")
    _add_usage(conn, 3, "com.missing.x", "ChaFileFace.eyelineUpId")
    _add_usage(conn, 4, "com.missing.x", "ChaFileFace.Pupil1")
    _add_usage(conn, 5, "com.missing.y", "ChaFileHair.hairId")
    _add_usage(conn, 5, "com.missing.z", "ChaFileMakeup.lipId")
    _add_usage(conn, 6, "com.installed.a", "ChaFileBody.detailId")
    _add_usage(conn, 6, "com.installed.b", "ChaFileFace.eyebrowId")
    _add_usage(conn, 8, "com.missing.x", "ChaFileBody.detailId")
    _add_usage(conn, 9, "com.installed.a", "outfit6.ChaFileClothes.ClothesTop")

    _add_resource_mod(conn, 2, "com.installed.a")
    _add_resource_mod(conn, 3, "com.missing.x")
    _add_resource_mod(conn, 4, "com.missing.x")
    _add_resource_mod(conn, 5, "com.missing.y")
    _add_resource_mod(conn, 5, "com.missing.z")
    _add_resource_mod(conn, 6, "com.installed.a")
    _add_resource_mod(conn, 6, "com.installed.b")
    _add_resource_mod(conn, 8, "com.missing.x")
    _add_resource_mod(conn, 9, "com.installed.a")

    _add_plugin(conn, 2, "moreAccessories")
    _add_plugin(conn, 9, "moreAccessories")
    _add_plugin(conn, 9, "KSOX")

    _add_author(conn, 1, "Evaan")
    _add_author(conn, 2, "Anonymous")
    _link_author(conn, 1, 1, 0)
    _link_author(conn, 9, 1, 0)
    _link_author(conn, 9, 2, 1)
    _link_author(conn, 3, 2, 0)
    return conn


WITH_MISSING = {3, 4, 5, 8}


def _ids(page: BrowsePage) -> list[int]:
    return [item.resource.id for item in page.items]


# ---------------------------------------------------------------------------
# libraries()
# ---------------------------------------------------------------------------


def test_empty_database(conn) -> None:
    service = BrowseService(conn)
    assert service.libraries() == []
    page = service.page(BrowserScope())
    assert page.total == 0
    assert page.items == ()
    assert service.detail(1) is None
    assert service.review_reasons(1) == ()


def test_libraries_delegate_to_library_query(seeded) -> None:
    service = BrowseService(seeded)
    rows = service.libraries()
    assert [r.name for r in rows] == ["Alpha", "Beta", "Gamma"]
    assert {r.id: r.resource_count for r in rows} == {1: 5, 2: 3, 3: 1}
    assert service.libraries(include_disabled=False) == LibraryQuery(seeded).list(
        include_disabled=False
    )
    assert [r.id for r in service.libraries(include_disabled=False)] == [1, 2]


# ---------------------------------------------------------------------------
# page()：分页 / 总数 / scope 一致性
# ---------------------------------------------------------------------------


def test_page_default(seeded) -> None:
    page = BrowseService(seeded).page(BrowserScope())
    assert page.total == 10
    assert len(page.items) == 10
    assert page.limit is None
    assert page.offset == 0
    assert _ids(page) == list(range(1, 11))


def test_page_single_page_limit(seeded) -> None:
    page = BrowseService(seeded).page(BrowserScope(), limit=4)
    assert page.total == 10
    assert _ids(page) == [1, 2, 3, 4]
    assert page.limit == 4


def test_page_multiple_pages_and_offset(seeded) -> None:
    service = BrowseService(seeded)
    first = service.page(BrowserScope(), limit=4, offset=0)
    second = service.page(BrowserScope(), limit=4, offset=4)
    third = service.page(BrowserScope(), limit=4, offset=8)
    assert _ids(first) == [1, 2, 3, 4]
    assert _ids(second) == [5, 6, 7, 8]
    assert _ids(third) == [9, 10]
    assert first.total == second.total == third.total == 10

    offset_only = service.page(BrowserScope(), offset=8)
    assert _ids(offset_only) == [9, 10]


def test_empty_result_page(seeded) -> None:
    page = BrowseService(seeded).page(BrowserScope(query="no-such-name"))
    assert page.total == 0
    assert page.items == ()


def test_page_scope_matches_resource_query(seeded) -> None:
    """同一个 BrowserScope：total 与 items 必须等于 ResourceQuery 的对应调用。"""
    service = BrowseService(seeded)
    rq = ResourceQuery(seeded)
    scope = BrowserScope(resource_type="character_card", order_by="name", descending=True)
    page = service.page(scope, limit=3, offset=2)

    filters = scope.filters()
    assert page.total == rq.count(**filters)
    expected = rq.list(
        **filters,
        order_by=scope.order_by,
        descending=scope.descending,
        limit=3,
        offset=2,
    )
    assert _ids(page) == [r.id for r in expected]


def test_scope_filters_are_a_single_conversion_point() -> None:
    scope = BrowserScope(
        query="x",
        resource_type="character_card",
        game="KKS",
        library_id=1,
        scan_status="present",
        needs_review=True,
        has_mods=True,
        has_missing_mods=True,
        mod_guid="g",
        plugin_guid="p",
        author_id=1,
        property_category="face",
        order_by="name",
        descending=True,
    )
    filters = scope.filters()
    # 排序键不进 filters（count 不接受）
    assert "order_by" not in filters
    assert "descending" not in filters
    assert filters["query"] == "x"
    assert filters["has_missing_mods"] is True
    # filters 的键必须都是 ResourceQuery.count/list 的合法参数（防止漂移）
    count_params = set(inspect.signature(ResourceQuery.count).parameters)
    list_params = set(inspect.signature(ResourceQuery.list).parameters)
    assert set(filters) <= count_params
    assert set(filters) <= list_params


# ---------------------------------------------------------------------------
# page()：筛选（语义完全来自 ResourceQuery）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scope,expected",
    [
        (BrowserScope(query="Carol"), {3}),
        (BrowserScope(query="Dress"), {5}),           # 按 relative_path 命中
        (BrowserScope(resource_type="outfit_card"), {5}),
        (BrowserScope(resource_type="mod"), {7}),
        (BrowserScope(library_id=1), {1, 2, 3, 4, 9}),
        (BrowserScope(library_id=2), {5, 6, 7}),
        (BrowserScope(library_id=3), {8}),
        (BrowserScope(needs_review=True), {4}),
        (BrowserScope(has_mods=True), {2, 3, 4, 5, 6, 8, 9}),
        (BrowserScope(has_missing_mods=True), WITH_MISSING),
        (BrowserScope(has_missing_mods=False), {1, 2, 6, 7, 9, 10}),
        (BrowserScope(mod_guid="com.installed.a"), {2, 6, 9}),
        (BrowserScope(mod_guid="com.missing.x"), {3, 4, 8}),
        (BrowserScope(plugin_guid="moreAccessories"), {2, 9}),
        (BrowserScope(plugin_guid="KSOX"), {9}),
        (BrowserScope(author_id=1), {1, 9}),
        (BrowserScope(author_id=2), {3, 9}),
        (BrowserScope(property_category="face"), {3, 4, 6}),
        (BrowserScope(property_category="clothes"), {9}),
        (BrowserScope(game="KKS"), {1, 2, 3, 6, 8, 9, 10}),
        (BrowserScope(game="KK"), {4}),
        (BrowserScope(has_missing_mods=True, library_id=1), {3, 4}),
        (BrowserScope(has_missing_mods=True, resource_type="outfit_card"), {5}),
    ],
)
def test_page_filters(seeded, scope, expected) -> None:
    page = BrowseService(seeded).page(scope)
    assert set(_ids(page)) == expected
    assert page.total == len(expected)


def test_page_order_by_and_descending(seeded) -> None:
    service = BrowseService(seeded)
    ascending = service.page(BrowserScope(order_by="name"))
    assert _ids(ascending) == [2, 3, 4, 5, 6, 7, 8, 9, 10, 1]
    descending = service.page(BrowserScope(order_by="name", descending=True))
    assert _ids(descending) == [1, 10, 9, 8, 7, 6, 5, 4, 3, 2]


# ---------------------------------------------------------------------------
# page()：Library 名 / 作者 / review reasons
# ---------------------------------------------------------------------------


def test_library_name_mapping(seeded) -> None:
    page = BrowseService(seeded).page(BrowserScope())
    by_id = {item.resource.id: item for item in page.items}
    assert by_id[1].library_name == "Alpha"
    assert by_id[5].library_name == "Beta"
    assert by_id[8].library_name == "Gamma"   # disabled 库也要能显示名字
    assert by_id[10].library_name is None     # 无 Library


def test_authors_zero_one_and_many(seeded) -> None:
    page = BrowseService(seeded).page(BrowserScope())
    by_id = {item.resource.id: item for item in page.items}
    assert by_id[10].authors == ()                       # 0 个
    assert by_id[1].authors == ("Evaan",)                # 1 个
    assert by_id[9].authors == ("Evaan", "Anonymous")    # 多个，保留顺序
    assert isinstance(by_id[9].authors, tuple)


def test_page_does_not_load_review_reasons_by_default(seeded, monkeypatch) -> None:
    calls: list[int] = []
    real = ResourceQuery.review_reasons

    def spy(self, resource_id):
        calls.append(resource_id)
        return real(self, resource_id)

    monkeypatch.setattr(ResourceQuery, "review_reasons", spy)
    page = BrowseService(seeded).page(BrowserScope())
    assert calls == []
    assert all(item.review_reasons == () for item in page.items)


def test_page_loads_review_reasons_on_demand(seeded, monkeypatch) -> None:
    calls: list[int] = []
    real = ResourceQuery.review_reasons

    def spy(self, resource_id):
        calls.append(resource_id)
        return real(self, resource_id)

    monkeypatch.setattr(ResourceQuery, "review_reasons", spy)
    page = BrowseService(seeded).page(BrowserScope(), with_review_reasons=True)

    assert sorted(calls) == list(range(1, 11))
    by_id = {item.resource.id: item for item in page.items}
    assert [r.code for r in by_id[4].review_reasons] == [REVIEW_REASON_PARSE_PARTIAL]
    assert by_id[1].review_reasons == ()   # 干净资源没有 reason


def test_page_review_reasons_respect_limit(seeded, monkeypatch) -> None:
    calls: list[int] = []
    real = ResourceQuery.review_reasons

    def spy(self, resource_id):
        calls.append(resource_id)
        return real(self, resource_id)

    monkeypatch.setattr(ResourceQuery, "review_reasons", spy)
    BrowseService(seeded).page(BrowserScope(), limit=3, with_review_reasons=True)
    assert calls == [1, 2, 3]


# ---------------------------------------------------------------------------
# detail() / review_reasons()
# ---------------------------------------------------------------------------


def test_detail_delegates_to_resource_query(seeded) -> None:
    service = BrowseService(seeded)
    detail = service.detail(9)
    assert detail is not None
    assert detail == ResourceQuery(seeded).get(9)
    assert detail.resource.id == 9
    assert {m.mod_guid for m in detail.mods} == {"com.installed.a"}
    assert [p for p in detail.plugins] == ["KSOX", "moreAccessories"]
    assert [a.name for a in detail.authors] == ["Evaan", "Anonymous"]


def test_detail_missing_returns_none(seeded) -> None:
    assert BrowseService(seeded).detail(999999) is None
    assert BrowseService(seeded).detail(-1) is None


def test_review_reasons_delegates(seeded) -> None:
    service = BrowseService(seeded)
    rq = ResourceQuery(seeded)
    assert service.review_reasons(4) == rq.review_reasons(4)
    assert [r.code for r in service.review_reasons(4)] == [REVIEW_REASON_PARSE_PARTIAL]
    assert service.review_reasons(1) == ()
    assert service.review_reasons(999999) == ()


# ---------------------------------------------------------------------------
# 只读不变量 / 无自有 SQL
# ---------------------------------------------------------------------------


def test_browse_is_read_only(seeded) -> None:
    conn = seeded
    service = BrowseService(conn)
    before_changes = conn.total_changes
    before_flags = {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    }
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))
    before_counts = {
        table: conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"]
        for table in ("resources", "libraries", "mods", "resource_mod_usages")
    }

    for _ in range(2):
        service.libraries()
        service.page(BrowserScope(has_missing_mods=True), limit=3, with_review_reasons=True)
        service.page(BrowserScope(order_by="name", descending=True), limit=2, offset=1)
        service.detail(3)
        service.review_reasons(3)

    assert conn.total_changes == before_changes, "Browse 不得写库"
    assert {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    } == before_flags
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta
    assert {
        table: conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"]
        for table in ("resources", "libraries", "mods", "resource_mod_usages")
    } == before_counts


def test_browse_module_has_no_sql_and_no_preview() -> None:
    import core.query.browse as browse_mod

    source = Path(browse_mod.__file__).read_text(encoding="utf-8")
    assert ".execute(" not in source, "Browse 层不允许自己执行 SQL"
    assert "SELECT " not in source.upper(), "Browse 层不允许出现 SQL"
    import_lines = [
        line
        for line in source.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    assert any("core.query.queries" in line for line in import_lines)
    assert not any("PreviewService" in line for line in import_lines)
    assert not any("core.thumbnails" in line for line in import_lines)
    assert not any("core.library" in line for line in import_lines)


def test_schema_version_unchanged() -> None:
    assert schema_mod.SCHEMA_VERSION == 2
    assert sorted(schema_mod.MIGRATIONS) == [1, 2]


# ---------------------------------------------------------------------------
# 真实样本（临时库，只读）
# ---------------------------------------------------------------------------


@pytest.fixture()
def real_db(tmp_path: Path, sample_root: Path):
    db_file = tmp_path / "samples.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    library = LibraryStore(connection).add(sample_root, name="真实样本")
    LibraryScanner(connection).scan(library.id)
    yield connection
    connection.close()


def test_real_sample_default_page(real_db) -> None:
    page = BrowseService(real_db).page(BrowserScope())
    assert page.total == 35
    assert len(page.items) == 35
    assert page.limit is None


def test_real_sample_libraries(real_db) -> None:
    libraries = BrowseService(real_db).libraries()
    assert len(libraries) == 1
    assert libraries[0].name == "真实样本"
    assert libraries[0].resource_count == 35


def test_real_sample_search_and_missing(real_db) -> None:
    service = BrowseService(real_db)
    sayaka = [item.resource.id for item in service.page(BrowserScope(query="沙耶香")).items]
    assert len(sayaka) == 1
    assert service.page(BrowserScope(query="沙耶香")).total == 1

    missing = service.page(BrowserScope(has_missing_mods=True))
    assert missing.total == 14
    assert len(missing.items) == 14
    assert sum(1 for item in service.page(BrowserScope(has_missing_mods=False)).items) == 21


def test_real_sample_pagination(real_db) -> None:
    service = BrowseService(real_db)
    first = service.page(BrowserScope(order_by="id"), limit=10, offset=0)
    last = service.page(BrowserScope(order_by="id"), limit=10, offset=30)
    assert first.total == last.total == 35
    assert len(first.items) == 10
    assert len(last.items) == 5


def test_real_sample_authors_and_review_reasons(real_db) -> None:
    service = BrowseService(real_db)
    evaan = AuthorQuery(real_db).find_by_name("Evaan")
    assert evaan is not None
    page = service.page(BrowserScope(author_id=evaan.id), with_review_reasons=True)
    assert page.total == 5
    assert all(item.authors for item in page.items)
    # 真实样本 needs_review=0 / parse_status 全 ok → reason 应为空（不造数据）
    assert all(item.review_reasons == () for item in page.items)


def test_real_sample_detail(real_db) -> None:
    service = BrowseService(real_db)
    row = real_db.execute(
        "SELECT id FROM resources WHERE replace(relative_path, '\\', '/')"
        " LIKE '%美树沙耶香%'"
    ).fetchone()
    detail = service.detail(int(row["id"]))
    assert detail is not None
    assert detail.resource.id == int(row["id"])
    assert len(detail.mods) == 1
    assert detail.resource.mod_count == 1


def test_real_sample_browse_is_read_only(real_db) -> None:
    conn = real_db
    service = BrowseService(conn)
    before_changes = conn.total_changes
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))
    before_flags = conn.execute(
        "SELECT count(*) AS c FROM resources WHERE needs_review = 1"
    ).fetchone()["c"]
    before_resources = conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"]

    for _ in range(2):
        service.libraries()
        service.page(BrowserScope(query="沙耶"), limit=5, offset=0)
        service.page(BrowserScope(has_missing_mods=True), with_review_reasons=True)
        service.page(BrowserScope(order_by="name", descending=True), limit=3, offset=2)
        service.detail(1)
        service.review_reasons(1)

    assert conn.total_changes == before_changes
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resources WHERE needs_review = 1"
        ).fetchone()["c"]
        == before_flags
        == 0
    )
    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == before_resources


# ---------------------------------------------------------------------------
# Phase 3.3 —— BrowserScope 新增 tag_id / favorite（T-Q / T-R 补充）
# ---------------------------------------------------------------------------


def test_scope_filters_project_model_params_exactly() -> None:
    """``filters()`` 必须是 ``to_filter().to_params()`` 在 16 键上的**投影**。"""
    scope = BrowserScope(
        query="x", tag_id=7, favorite=False, order_by="name", descending=True
    )
    params = scope.to_filter().to_params()
    filters = scope.filters()

    assert tuple(filters) == BrowserScope.FILTER_KEYS
    assert len(filters) == 16
    for key in BrowserScope.FILTER_KEYS:
        assert filters[key] == params[key], key

    # 模型 17 键（含 GUI 不暴露的 card_marker）⇒ 与 filters() 必然不等。
    assert len(params) == 17
    assert filters != params
    assert "card_marker" not in filters
    assert params["card_marker"] is None

    assert filters["tag_id"] == 7
    assert filters["favorite"] is False
    assert filters["query"] == "x"


def test_scope_model_keys_are_accepted_by_query_layer() -> None:
    """T-R：filters() 的键必须都是 count / list 的合法参数（防漂移）。"""
    count_params = set(inspect.signature(ResourceQuery.count).parameters)
    list_params = set(inspect.signature(ResourceQuery.list).parameters)
    filters = BrowserScope(tag_id=1, favorite=True).filters()
    assert set(filters) <= count_params
    assert set(filters) <= list_params
    # 新增的两个键确实落在合法参数面内
    assert {"tag_id", "favorite"} <= count_params
    assert {"tag_id", "favorite"} <= list_params


def test_page_supports_tag_and_favorite_scope(seeded) -> None:
    writer = TagWriteService(seeded)
    alpha = writer.create_tag("Alpha")
    writer.assign_tag(1, alpha)
    writer.assign_tag(2, alpha)
    writer.set_favorite(2, True)

    service = BrowseService(seeded)
    rq = ResourceQuery(seeded)

    assert _ids(service.page(BrowserScope(tag_id=alpha))) == [1, 2]
    assert service.page(BrowserScope(tag_id=alpha)).total == 2
    assert _ids(service.page(BrowserScope(favorite=True))) == [2]
    assert _ids(service.page(BrowserScope(tag_id=alpha, favorite=True))) == [2]
    assert _ids(service.page(BrowserScope(tag_id=alpha, favorite=False))) == [1]

    for scope in (
        BrowserScope(tag_id=alpha),
        BrowserScope(favorite=True),
        BrowserScope(favorite=False),
        BrowserScope(tag_id=alpha, favorite=True),
    ):
        assert service.page(scope).total == rq.count(**scope.filters())


def test_page_with_new_filters_does_not_write(seeded) -> None:
    writer = TagWriteService(seeded)
    alpha = writer.create_tag("Alpha")
    writer.assign_tag(1, alpha)
    writer.set_favorite(1, True)

    before_changes = seeded.total_changes
    before_counts = {
        table: seeded.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"]
        for table in ("resources", "tags", "resource_tags")
    }
    service = BrowseService(seeded)
    service.page(BrowserScope(tag_id=alpha), limit=3)
    service.page(BrowserScope(favorite=True), with_review_reasons=True)
    service.page(BrowserScope(tag_id=alpha, favorite=False))

    assert seeded.total_changes == before_changes
    assert {
        table: seeded.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"]
        for table in ("resources", "tags", "resource_tags")
    } == before_counts
