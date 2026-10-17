"""Phase 3.3 —— Query Model（``ResourceFilter``）与 ``tag_id`` / ``favorite`` 只读筛选。

依据：`docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md`（§4–§9 / §12 / §13）。

覆盖契约 §12 不变式：**T-A / T-B / T-C / T-D / T-E / T-F / T-G / T-H / T-I /
T-J / T-K（运行时部分）/ T-M / T-N / T-Q / T-R**。
（T-O / T-P / T-S 属 CLI 行为，落在 ``tests/test_query_cli.py``。）

测试落点按「谁负责该行为」决定（契约 §10.1 r1 说明），故本文件为新增 focused 文件。
"""

from __future__ import annotations

import dataclasses
import inspect
import sqlite3
from pathlib import Path

import pytest

import core.query.queries as queries_module
from core.app import TagWriteService
from core.database import db as database
from core.database import schema as schema_mod
from core.models.tags import FAVORITE_TAG_KEY
from core.query import (
    BrowseService,
    BrowserScope,
    ResourceDetail,
    ResourceFilter,
    ResourceQuery,
    ResourceSummary,
    TagQuery,
    TagSummary,
)

ALPHA = "Alpha"


# ---------------------------------------------------------------------------
# 夹具 / 工具
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "query_model.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    try:
        yield connection
    finally:
        connection.close()


def _add_library(conn: sqlite3.Connection, name: str) -> int:
    cursor = conn.execute(
        "INSERT INTO libraries(name, root_path, root_path_key) VALUES (?, ?, ?)",
        (name, f"d:/{name}", f"d:/{name}".casefold()),
    )
    return int(cursor.lastrowid)


def _add_resource(
    conn: sqlite3.Connection,
    index: int,
    *,
    resource_type: str = "character_card",
    library_id: int | None = None,
) -> int:
    path = f"d:/cards/r{index}.png"
    cursor = conn.execute(
        "INSERT INTO resources(resource_type, type_source, name, file_path,"
        " file_path_key, relative_path, extension, library_id, scan_status,"
        " parse_status, needs_review)"
        " VALUES (?, 'auto', ?, ?, ?, ?, '.png', ?, 'present', 'ok', 0)",
        (
            resource_type,
            f"Card{index}",
            path,
            path.casefold(),
            f"r{index}.png",
            library_id,
        ),
    )
    return int(cursor.lastrowid)


def _count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()
    return int(row["c"])


def _ids(rows) -> list[int]:
    return [row.id for row in rows]


@pytest.fixture()
def seeded(conn):
    """2 个 Library + 5 个资源 + 用户 Tag ``Alpha``(r1,r2) + 系统 Favorite(r2,r4)。"""
    lib1 = _add_library(conn, "lib1")
    lib2 = _add_library(conn, "lib2")
    r1 = _add_resource(conn, 1, library_id=lib1)
    r2 = _add_resource(conn, 2, library_id=lib1)
    r3 = _add_resource(conn, 3, resource_type="outfit_card", library_id=lib1)
    r4 = _add_resource(conn, 4, library_id=lib2)
    r5 = _add_resource(conn, 5, resource_type="outfit_card", library_id=lib2)

    tags = TagWriteService(conn)
    alpha = tags.create_tag(ALPHA)
    tags.assign_tag(r1, alpha)
    tags.assign_tag(r2, alpha)
    tags.set_favorite(r2, True)
    tags.set_favorite(r4, True)
    return {
        "lib1": lib1,
        "lib2": lib2,
        "r1": r1,
        "r2": r2,
        "r3": r3,
        "r4": r4,
        "r5": r5,
        "alpha": alpha,
    }


# ---------------------------------------------------------------------------
# T-A：模型是 frozen 纯值对象；默认构造 == 无任何条件；参数集恒为 15 键
# ---------------------------------------------------------------------------


def test_resource_filter_is_frozen_and_has_fifteen_params():
    filt = ResourceFilter()
    assert dataclasses.is_dataclass(filt)

    params = filt.to_params()
    field_names = {field.name for field in dataclasses.fields(ResourceFilter)}
    assert set(params) == field_names
    assert len(params) == 15
    assert all(value is None for value in params.values())

    with pytest.raises(dataclasses.FrozenInstanceError):
        filt.tag_id = 1


def test_resource_filter_has_no_sql_or_parsing_surface():
    """契约 §4.3：不提供 SQL 出口，也不提供文本语法解析。"""
    for forbidden in ("to_sql", "to_where", "parse", "compile"):
        assert not hasattr(ResourceFilter, forbidden), forbidden


def test_resource_filter_fields_match_query_signatures():
    """契约 §4.2 / §4.6：字段与 count / list 的筛选参数**逐名一致**。"""
    filters = set(ResourceFilter().to_params())
    for method in (ResourceQuery.count, ResourceQuery.list):
        params = set(inspect.signature(method).parameters)
        assert filters <= params
    assert filters == (
        set(inspect.signature(ResourceQuery.count).parameters) - {"self"}
    )


# ---------------------------------------------------------------------------
# T-B：空条件等价性（既有语义零漂移）
# ---------------------------------------------------------------------------


def test_empty_filter_is_equivalent_to_no_conditions(seeded, conn):
    rq = ResourceQuery(conn)
    baseline = rq.list()
    expanded = rq.list(**ResourceFilter().to_params())
    assert _ids(baseline) == _ids(expanded)
    assert rq.count(**ResourceFilter().to_params()) == rq.count()


def test_to_params_expands_into_list_call(seeded, conn):
    filt = ResourceFilter(tag_id=seeded["alpha"], library_id=seeded["lib1"])
    rows = ResourceQuery(conn).list(
        **filt.to_params(), order_by="id", descending=False, limit=1, offset=0
    )
    assert _ids(rows) == [seeded["r1"]]


# ---------------------------------------------------------------------------
# T-C：tag_id 筛选 == TagQuery.resource_ids()（显式写出排序，不依赖隐含默认）
# ---------------------------------------------------------------------------


def test_tag_id_filter_matches_tag_query_resource_ids(seeded, conn):
    rows = ResourceQuery(conn).list(
        tag_id=seeded["alpha"], order_by="id", descending=False
    )
    assert _ids(rows) == sorted(TagQuery(conn).resource_ids(seeded["alpha"]))
    assert _ids(rows) == [seeded["r1"], seeded["r2"]]


# ---------------------------------------------------------------------------
# T-D：tag_id 类型校验与边界
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [True, False, "1", 1.0, [1], object()])
def test_tag_id_rejects_non_int_values(bad):
    with pytest.raises(TypeError):
        ResourceFilter(tag_id=bad)


def test_tag_id_accepts_none_and_int():
    assert ResourceFilter(tag_id=None).tag_id is None
    assert ResourceFilter(tag_id=7).tag_id == 7
    assert ResourceFilter(tag_id=-3).tag_id == -3


@pytest.mark.parametrize("missing", [0, -1, 999999])
def test_unknown_or_non_positive_tag_id_yields_empty_result(seeded, conn, missing):
    rq = ResourceQuery(conn)
    assert rq.list(tag_id=missing) == []
    assert rq.count(tag_id=missing) == 0


# ---------------------------------------------------------------------------
# T-E：favorite 语义（True / False / None）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [1, 0, "true", [], 1.0])
def test_favorite_rejects_non_bool(bad):
    with pytest.raises(TypeError):
        ResourceFilter(favorite=bad)


def test_favorite_accepts_none_true_false():
    assert ResourceFilter(favorite=None).favorite is None
    assert ResourceFilter(favorite=True).favorite is True
    assert ResourceFilter(favorite=False).favorite is False


def test_favorite_true_and_false_match_tag_query(seeded, conn):
    rq = ResourceQuery(conn)
    tq = TagQuery(conn)

    favorites = rq.list(favorite=True)
    assert _ids(favorites) == sorted(tq.favorite_resource_ids())
    assert _ids(favorites) == [seeded["r2"], seeded["r4"]]

    non_favorites = rq.list(favorite=False)
    all_ids = {row.id for row in rq.list()}
    assert {row.id for row in non_favorites} == all_ids - set(
        tq.favorite_resource_ids()
    )
    assert {row.id for row in non_favorites} == {
        seeded["r1"],
        seeded["r3"],
        seeded["r5"],
    }
    assert rq.count(favorite=True) + rq.count(favorite=False) == rq.count()


# ---------------------------------------------------------------------------
# T-F：系统 Tag 尚未 bootstrap 的库（只读、不隐式建 Tag、不抛异常）
# ---------------------------------------------------------------------------


def test_favorite_filter_without_system_tag_bootstrap(conn):
    lib = _add_library(conn, "lib")
    r1 = _add_resource(conn, 1, library_id=lib)
    r2 = _add_resource(conn, 2, library_id=lib)
    assert _count(conn, "tags") == 0

    before_changes = conn.total_changes
    rq = ResourceQuery(conn)
    assert rq.list(favorite=True) == []
    assert rq.count(favorite=True) == 0
    assert {row.id for row in rq.list(favorite=False)} == {r1, r2}

    assert conn.total_changes == before_changes, "筛选过程不得写库"
    assert _count(conn, "tags") == 0, "读路径不得隐式创建系统 Tag"
    row = conn.execute(
        "SELECT count(*) AS c FROM tags WHERE name_key = ?", (FAVORITE_TAG_KEY,)
    ).fetchone()
    assert int(row["c"]) == 0


# ---------------------------------------------------------------------------
# T-G：新增条件与既有条件恒为 AND
# ---------------------------------------------------------------------------


def test_new_conditions_combine_with_existing_ones_as_and(seeded, conn):
    rq = ResourceQuery(conn)
    assert _ids(rq.list(tag_id=seeded["alpha"], favorite=True)) == [seeded["r2"]]
    assert _ids(rq.list(tag_id=seeded["alpha"], favorite=False)) == [seeded["r1"]]
    assert _ids(rq.list(tag_id=seeded["alpha"], library_id=seeded["lib1"])) == [
        seeded["r1"],
        seeded["r2"],
    ]
    assert rq.list(tag_id=seeded["alpha"], resource_type="outfit_card") == []
    assert _ids(rq.list(favorite=True, library_id=seeded["lib2"])) == [seeded["r4"]]
    assert rq.list(tag_id=seeded["alpha"], library_id=seeded["lib2"]) == []


# ---------------------------------------------------------------------------
# T-H：count / list / Browse page 一致性
# ---------------------------------------------------------------------------


def test_count_matches_list_under_new_filters(seeded, conn):
    rq = ResourceQuery(conn)
    combos = [
        ResourceFilter(),
        ResourceFilter(tag_id=seeded["alpha"]),
        ResourceFilter(favorite=True),
        ResourceFilter(favorite=False),
        ResourceFilter(tag_id=seeded["alpha"], favorite=True),
        ResourceFilter(tag_id=seeded["alpha"], library_id=seeded["lib1"]),
        ResourceFilter(favorite=False, resource_type="outfit_card"),
    ]
    for filt in combos:
        params = filt.to_params()
        assert rq.count(**params) == len(rq.list(**params))


def test_browse_page_total_matches_scope_filters(seeded, conn):
    rq = ResourceQuery(conn)
    service = BrowseService(conn)
    for scope in (
        BrowserScope(),
        BrowserScope(tag_id=seeded["alpha"]),
        BrowserScope(favorite=True),
        BrowserScope(tag_id=seeded["alpha"], favorite=False),
        BrowserScope(favorite=False, library_id=seeded["lib2"]),
    ):
        page = service.page(scope)
        assert page.total == rq.count(**scope.filters())
        assert len(page.items) == page.total
        assert sum(1 for _ in page.items) <= page.total


# ---------------------------------------------------------------------------
# T-I：新增筛选不改变 limit / offset / order_by 行为
# ---------------------------------------------------------------------------


def test_pagination_and_sorting_unchanged_under_new_filters(seeded, conn):
    rq = ResourceQuery(conn)
    full = rq.list(tag_id=seeded["alpha"], order_by="id", descending=False)
    windowed = rq.list(
        tag_id=seeded["alpha"], order_by="id", descending=False, limit=1, offset=1
    )
    assert _ids(windowed) == _ids(full)[1:2]

    asc = rq.list(favorite=False, order_by="id", descending=False)
    desc = rq.list(favorite=False, order_by="id", descending=True)
    assert _ids(desc) == list(reversed(_ids(asc)))

    assert _ids(rq.list(favorite=True, offset=1)) == _ids(rq.list(favorite=True))[1:]


def test_illegal_order_by_still_raises_under_new_filters(seeded, conn):
    with pytest.raises(ValueError):
        ResourceQuery(conn).list(tag_id=seeded["alpha"], order_by="bogus")
    with pytest.raises(ValueError):
        ResourceQuery(conn).list(favorite=True, order_by="bogus")


# ---------------------------------------------------------------------------
# T-J：只读 + 参数化（经唯一护栏、以绑定参数传入）
# ---------------------------------------------------------------------------


def test_new_filters_do_not_write(seeded, conn):
    before_changes = conn.total_changes
    rq = ResourceQuery(conn)
    rq.list(tag_id=seeded["alpha"], favorite=True)
    rq.count(tag_id=seeded["alpha"], favorite=False)
    assert conn.total_changes == before_changes


def test_new_filters_go_through_read_only_guard_and_bind_parameters(
    seeded, conn, monkeypatch
):
    seen: list[str] = []
    real = queries_module._execute_select

    def spy(c, sql, params=()):
        seen.append(sql)
        return real(c, sql, params)

    monkeypatch.setattr(queries_module, "_execute_select", spy)
    ResourceQuery(conn).list(tag_id=seeded["alpha"], favorite=True)

    assert seen, "新增筛选必须经 _execute_select 执行"
    for sql in seen:
        assert sql.lstrip().split(None, 1)[0].lower() in ("select", "with")
    joined = " ".join(seen)
    assert "resource_tags" in joined
    assert "name_key" in joined
    # Favorite 判据以绑定参数传入（``?``），不把保留 key 拼进语句文本。
    assert FAVORITE_TAG_KEY not in joined


def test_new_filters_leave_all_tables_untouched(seeded, conn):
    """连接级 ``total_changes`` + 表计数不变（沿用既有只读测量方式）。"""
    tables = ("resources", "tags", "resource_tags")
    before_changes = conn.total_changes
    before_counts = {table: _count(conn, table) for table in tables}
    rq = ResourceQuery(conn)
    rq.list(favorite=False)
    rq.list(tag_id=0)
    rq.count(favorite=True)
    assert conn.total_changes == before_changes
    assert {table: _count(conn, table) for table in tables} == before_counts


# ---------------------------------------------------------------------------
# T-K（运行时部分）：SQL 元字符 / 引号 / 通配符不改变结果集、不报错
# ---------------------------------------------------------------------------


def test_sql_metacharacter_input_is_inert(conn):
    lib = _add_library(conn, "lib")
    r1 = _add_resource(conn, 1, library_id=lib)
    r2 = _add_resource(conn, 2, library_id=lib)
    tags = TagWriteService(conn)
    weird = "a'b%_\" OR 1=1 --"
    tag_id = tags.create_tag(weird)
    tags.assign_tag(r1, tag_id)

    rq = ResourceQuery(conn)
    assert _ids(rq.list(tag_id=tag_id)) == [r1]
    assert rq.count(tag_id=tag_id) == 1
    # 通配符 / 引号进入文本检索面同样按字面匹配（转义后不改变结果集）。
    assert rq.list(query="%'") == []
    assert rq.count(query="%'") == 0
    assert _ids(rq.list(query="Card")) == [r1, r2]


def test_tag_name_lookup_is_exact_not_fuzzy(seeded, conn):
    tq = TagQuery(conn)
    assert tq.find_by_name("Alpha") is not None
    assert tq.find_by_name("alpha") is not None
    assert tq.find_by_name("  ALPHA  ") is not None
    assert tq.find_by_name("Alph") is None
    assert tq.find_by_name("Alpha%") is None
    assert tq.find_by_name("") is None
    assert tq.find_by_name("   ") is None


# ---------------------------------------------------------------------------
# T-M：DTO 零变更
# ---------------------------------------------------------------------------


def test_dto_field_sets_are_unchanged():
    assert [f.name for f in dataclasses.fields(ResourceSummary)] == [
        "id",
        "resource_type",
        "name",
        "display_name",
        "file_path",
        "relative_path",
        "extension",
        "card_marker",
        "file_size",
        "modified_time",
        "library_id",
        "scan_status",
        "parse_status",
        "needs_review",
        "mod_count",
        "usage_count",
        "plugin_count",
        "author_count",
        "sha256",
        "type_source",
        "notes",
    ]
    assert [f.name for f in dataclasses.fields(ResourceDetail)] == [
        "resource",
        "usages",
        "mods",
        "plugins",
        "authors",
        "metadata",
        "tags",
        "is_favorite",
    ]
    assert [f.name for f in dataclasses.fields(TagSummary)] == [
        "id",
        "name",
        "name_key",
        "color",
        "category",
        "is_system",
        "resource_count",
    ]


def test_list_rows_gain_no_tag_columns(seeded, conn):
    """列表行（ResourceSummary）不得新增 tags / is_favorite 字段（契约 §2-5）。"""
    row = ResourceQuery(conn).list(tag_id=seeded["alpha"])[0]
    assert not hasattr(row, "tags")
    assert not hasattr(row, "is_favorite")


# ---------------------------------------------------------------------------
# T-N：schema 冻结
# ---------------------------------------------------------------------------


def test_schema_stays_v2():
    assert schema_mod.SCHEMA_VERSION == 2
    assert set(schema_mod.MIGRATIONS) == {1, 2}
    assert len(schema_mod.CURRENT_TABLES) == 16
    assert schema_mod.MIGRATION_ADDED_COLUMNS == {
        2: (("resources", "card_marker", "TEXT"),)
    }


# ---------------------------------------------------------------------------
# T-Q / T-R：GUI 键集投影与参数面约束
# ---------------------------------------------------------------------------


def test_scope_filters_are_a_projection_of_model_params():
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
        tag_id=3,
        favorite=True,
        order_by="name",
        descending=True,
    )
    params = scope.to_filter().to_params()
    filters = scope.filters()

    assert tuple(filters) == BrowserScope.FILTER_KEYS
    assert len(filters) == 14
    for key in BrowserScope.FILTER_KEYS:
        assert filters[key] == params[key], key

    # 模型 15 键（多一个 GUI 不暴露的 card_marker）⇒ 二者必然不等。
    assert len(params) == 15
    assert filters != params
    assert "card_marker" not in filters
    assert params["card_marker"] is None

    # 排序 / 分页不属于 Query Model。
    for key in ("order_by", "descending", "limit", "offset"):
        assert key not in filters
        assert key not in params

    # 新增键承载了值，既有键逐键保持。
    assert filters["tag_id"] == 3
    assert filters["favorite"] is True
    assert filters["query"] == "x"
    assert filters["has_missing_mods"] is True


def test_empty_scope_filters_have_all_fourteen_keys():
    filters = BrowserScope().filters()
    assert tuple(filters) == BrowserScope.FILTER_KEYS
    assert len(filters) == 14
    assert all(value is None for value in filters.values())


def test_filter_keys_is_a_class_constant_not_a_field():
    field_names = {field.name for field in dataclasses.fields(BrowserScope)}
    assert "FILTER_KEYS" not in field_names
    assert "tag_id" in field_names
    assert "favorite" in field_names


def test_filters_keys_and_model_keys_are_valid_query_params():
    count_params = set(inspect.signature(ResourceQuery.count).parameters)
    list_params = set(inspect.signature(ResourceQuery.list).parameters)
    assert set(BrowserScope().filters()) <= count_params
    assert set(BrowserScope().filters()) <= list_params
    assert set(ResourceFilter().to_params()) <= count_params
    assert set(ResourceFilter().to_params()) <= list_params


def test_new_scope_fields_are_appended_with_defaults():
    """契约 §9：新增字段置于末尾、带默认值 ⇒ 既有调用方式不受影响。"""
    field_names = [field.name for field in dataclasses.fields(BrowserScope)]
    assert field_names.index("tag_id") > field_names.index("property_category")
    assert field_names.index("favorite") > field_names.index("tag_id")
    assert field_names[-2:] == ["order_by", "descending"]
    assert BrowserScope().tag_id is None
    assert BrowserScope().favorite is None

    existing = {
        "query",
        "resource_type",
        "game",
        "library_id",
        "scan_status",
        "needs_review",
        "has_mods",
        "has_missing_mods",
        "mod_guid",
        "plugin_guid",
        "author_id",
        "property_category",
    }
    assert existing <= set(field_names)
    assert set(field_names) - existing == {
        "tag_id",
        "favorite",
        "order_by",
        "descending",
    }


def test_user_type_override_filters_by_effective_type(conn):
    """T-C：用户类型修正后，按有效类型筛选命中，ownership marker 为 user。"""
    from core.app import ResourceWriteService

    rid = _add_resource(conn, 61)
    rq = ResourceQuery(conn)

    assert [row.id for row in rq.list(resource_type="character_card")] == [rid]

    ResourceWriteService(conn).set_resource_type(rid, "mod")

    assert [row.id for row in rq.list(resource_type="mod")] == [rid]
    assert rq.list(resource_type="character_card") == []
    summary = rq.summary(rid)
    assert summary is not None
    assert summary.type_source == "user"
