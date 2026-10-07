"""Phase 1.4-B.2：``ResourceQuery.has_missing_mods`` 只读筛选测试。

「missing MOD」定义与 ``ModQuery.missing()`` 一致：
``resource_mod_usages`` 引用的 ``mod_guid`` 在 ``mods`` 表里没有对应行。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.database import schema as schema_mod  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.query import ModQuery, ResourceQuery  # noqa: E402
from core.scanner import LibraryScanner  # noqa: E402


# ---------------------------------------------------------------------------
# 夹具 / 构造器
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path):
    db_file = tmp_path / "missing_mods.db"
    database.initialize(db_file)
    connection = database.connect(db_file)
    yield connection
    connection.close()


def _add_library(conn, library_id: int, name: str, root: str) -> None:
    conn.execute(
        "INSERT INTO libraries(id, name, root_path, root_path_key) VALUES (?, ?, ?, ?)",
        (library_id, name, root, root.casefold()),
    )


def _add_resource(
    conn,
    resource_id: int,
    *,
    name: str,
    resource_type: str = "character_card",
    library_id: int | None = None,
    needs_review: int = 0,
    relative_path: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO resources(id, resource_type, name, display_name, file_path,"
        " file_path_key, relative_path, library_id, needs_review)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            resource_id,
            resource_type,
            name,
            name,
            f"D:/lib/{resource_id}.png",
            f"d:/lib/{resource_id}.png",
            relative_path,
            library_id,
            needs_review,
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
    """合成库：

    - #1 Alice   无 MOD 依赖
    - #2 Bob     1 个已安装 MOD
    - #3 Carol   1 个 missing MOD（face）
    - #4 Dave    1 已安装 + 1 missing（库 2）
    - #5 Eve     outfit_card，2 个 missing（库 2，路径含 Dress）
    - #6 Frank   2 个已安装
    - #7 Grace   同一个 missing MOD 的 2 条 usage（重复关系，face）
    - #8 Heidi   needs_review=1，1 个 missing（body）
    """
    _add_library(conn, 1, "A", "D:/a")
    _add_library(conn, 2, "B", "D:/b")
    _add_mod(conn, "com.installed.a")
    _add_mod(conn, "com.installed.b")

    _add_resource(conn, 1, name="Alice", library_id=1, relative_path="Cards/Alice.png")
    _add_resource(conn, 2, name="Bob", library_id=1, relative_path="Cards/Bob.png")
    _add_resource(conn, 3, name="Carol", library_id=1, relative_path="Cards/Carol.png")
    _add_resource(conn, 4, name="Dave", library_id=2, relative_path="Cards/Dave.png")
    _add_resource(
        conn,
        5,
        name="Eve",
        resource_type="outfit_card",
        library_id=2,
        relative_path="Outfits/EveDress.png",
    )
    _add_resource(conn, 6, name="Frank", library_id=1, relative_path="Cards/Frank.png")
    _add_resource(conn, 7, name="Grace", library_id=1, relative_path="Cards/Grace.png")
    _add_resource(
        conn, 8, name="Heidi", library_id=1, needs_review=1, relative_path="Cards/Heidi.png"
    )

    _add_usage(conn, 2, "com.installed.a", "ChaFileBody.detailId")
    _add_usage(conn, 3, "com.missing.x", "ChaFileFace.eyelineUpId")
    _add_usage(conn, 4, "com.installed.a", "outfit6.ChaFileClothes.ClothesTop")
    _add_usage(conn, 4, "com.missing.x", "ChaFileAccessory.PartsInfo.id")
    _add_usage(conn, 5, "com.missing.y", "ChaFileHair.hairId")
    _add_usage(conn, 5, "com.missing.z", "ChaFileMakeup.lipId")
    _add_usage(conn, 6, "com.installed.a", "ChaFileBody.detailId")
    _add_usage(conn, 6, "com.installed.b", "ChaFileFace.eyebrowId")
    _add_usage(conn, 7, "com.missing.x", "ChaFileFace.Pupil1")
    _add_usage(conn, 7, "com.missing.x", "ChaFileFace.Pupil2")
    _add_usage(conn, 8, "com.missing.y", "ChaFileBody.detailId")
    return conn


def _ids(rows) -> list[int]:
    return [row.id for row in rows]


WITH_MISSING = {3, 4, 5, 7, 8}
WITHOUT_MISSING = {1, 2, 6}


# ---------------------------------------------------------------------------
# 四种基本情形
# ---------------------------------------------------------------------------


def test_no_mod_dependencies(seeded) -> None:
    rq = ResourceQuery(seeded)
    assert rq.list(has_mods=False, has_missing_mods=False) != []
    assert {r.id for r in rq.list(has_mods=False)} == {1}
    assert [r.id for r in rq.list(has_mods=False, has_missing_mods=True)] == []


def test_all_mods_installed(seeded) -> None:
    rq = ResourceQuery(seeded)
    assert {r.id for r in rq.list(mod_guid="com.installed.a")} == {2, 4, 6}
    assert {r.id for r in rq.list(mod_guid="com.installed.a", has_missing_mods=False)} == {
        2,
        6,
    }
    # 用了已安装 MOD 不代表没有缺失：R4 同时缺一个
    assert [r.id for r in rq.list(mod_guid="com.installed.a", has_missing_mods=True)] == [4]


def test_single_missing_mod(seeded) -> None:
    conn = seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(mod_guid="com.missing.x")] == [3, 4, 7]
    assert {r.id for r in rq.list(mod_guid="com.missing.x", has_missing_mods=True)} == {
        3,
        4,
        7,
    }


def test_multiple_missing_mods(seeded) -> None:
    rq = ResourceQuery(seeded)
    assert [r.id for r in rq.list(mod_guid="com.missing.z")] == [5]
    assert [r.id for r in rq.list(has_missing_mods=True, mod_guid="com.missing.z")] == [5]


def test_partial_installed_partial_missing(seeded) -> None:
    rq = ResourceQuery(seeded)
    assert 4 in {r.id for r in rq.list(has_missing_mods=True)}
    assert 4 not in {r.id for r in rq.list(has_missing_mods=False)}
    # 该资源既有已安装也有缺失
    assert {r.id for r in rq.list(mod_guid="com.installed.a")} & {4} == {4}
    assert {r.id for r in rq.list(mod_guid="com.missing.x")} & {4} == {4}


# ---------------------------------------------------------------------------
# True / False / None 与 has_mods 的区分
# ---------------------------------------------------------------------------


def test_has_missing_mods_true_false_none(seeded) -> None:
    rq = ResourceQuery(seeded)
    assert _ids(rq.list(has_missing_mods=None, order_by="id")) == list(range(1, 9))
    assert {r.id for r in rq.list(has_missing_mods=True)} == WITH_MISSING
    assert {r.id for r in rq.list(has_missing_mods=False)} == WITHOUT_MISSING
    assert rq.count() == 8
    assert rq.count(has_missing_mods=True) + rq.count(has_missing_mods=False) == 8


def test_has_mods_is_not_the_same_as_has_missing_mods(seeded) -> None:
    rq = ResourceQuery(seeded)
    has_mods = {r.id for r in rq.list(has_mods=True)}
    missing = {r.id for r in rq.list(has_missing_mods=True)}

    assert has_mods == {2, 3, 4, 5, 6, 7, 8}
    assert missing == WITH_MISSING
    assert missing < has_mods, "missing 是 has_mods 的真子集"
    # 有 MOD 依赖 ≠ 有缺失 MOD
    assert {r.id for r in rq.list(has_mods=True, has_missing_mods=False)} == {2, 6}
    # 没有依赖就谈不上缺失
    assert rq.list(has_mods=False, has_missing_mods=True) == []


# ---------------------------------------------------------------------------
# 与其它筛选组合
# ---------------------------------------------------------------------------


def test_combination_with_query(seeded) -> None:
    rq = ResourceQuery(seeded)
    assert [r.id for r in rq.list(query="Carol", has_missing_mods=True)] == [3]
    assert rq.list(query="Carol", has_missing_mods=False) == []
    # 按 relative_path 命中（Outfits/EveDress.png）
    assert [r.id for r in rq.list(query="Dress", has_missing_mods=True)] == [5]
    assert rq.list(query="Dress", has_missing_mods=False) == []


def test_combination_with_library(seeded) -> None:
    rq = ResourceQuery(seeded)
    assert {r.id for r in rq.list(has_missing_mods=True, library_id=1)} == {3, 7, 8}
    assert {r.id for r in rq.list(has_missing_mods=True, library_id=2)} == {4, 5}
    assert {r.id for r in rq.list(has_missing_mods=False, library_id=1)} == {1, 2, 6}
    assert rq.list(has_missing_mods=False, library_id=2) == []


def test_combination_with_resource_type(seeded) -> None:
    rq = ResourceQuery(seeded)
    assert {r.id for r in rq.list(has_missing_mods=True, resource_type="outfit_card")} == {5}
    assert {r.id for r in rq.list(has_missing_mods=True, resource_type="character_card")} == {
        3,
        4,
        7,
        8,
    }


def test_combination_with_needs_review(seeded) -> None:
    rq = ResourceQuery(seeded)
    assert [r.id for r in rq.list(has_missing_mods=True, needs_review=True)] == [8]
    assert {r.id for r in rq.list(has_missing_mods=True, needs_review=False)} == {3, 4, 5, 7}


def test_combination_with_property_category(seeded) -> None:
    rq = ResourceQuery(seeded)
    # face usage + missing：R3、R7；R6 有 face 但无缺失
    assert {r.id for r in rq.list(has_missing_mods=True, property_category="face")} == {3, 7}
    assert {r.id for r in rq.list(has_missing_mods=True, property_category="clothes")} == {4}
    assert {r.id for r in rq.list(has_missing_mods=True, property_category="hair")} == {5}
    assert {r.id for r in rq.list(has_missing_mods=True, property_category="body")} == {8}


def test_sort_and_pagination(seeded) -> None:
    rq = ResourceQuery(seeded)
    assert _ids(rq.list(has_missing_mods=True, order_by="id")) == [3, 4, 5, 7, 8]
    assert _ids(
        rq.list(has_missing_mods=True, order_by="id", limit=2, offset=1)
    ) == [4, 5]
    assert _ids(
        rq.list(has_missing_mods=True, order_by="id", descending=True)
    ) == [8, 7, 5, 4, 3]


def test_list_and_count_consistency(seeded) -> None:
    rq = ResourceQuery(seeded)
    scopes = [
        {},
        {"has_missing_mods": None},
        {"has_missing_mods": True},
        {"has_missing_mods": False},
        {"has_missing_mods": True, "has_mods": True},
        {"has_missing_mods": True, "has_mods": False},
        {"has_missing_mods": True, "resource_type": "character_card"},
        {"has_missing_mods": True, "library_id": 1},
        {"has_missing_mods": True, "needs_review": True},
        {"has_missing_mods": True, "property_category": "face"},
        {"has_missing_mods": True, "query": "Carol"},
        {"has_missing_mods": False, "mod_guid": "com.installed.a"},
    ]
    for scope in scopes:
        assert rq.count(**scope) == len(rq.list(**scope)), scope


def test_duplicate_relations_do_not_duplicate_or_flip(seeded) -> None:
    rq = ResourceQuery(seeded)
    # #7 有同一 missing MOD 的两条 usage，必须只出现一次
    rows = rq.list(has_missing_mods=True, order_by="id")
    assert _ids(rows) == [3, 4, 5, 7, 8]
    assert len(rows) == len({r.id for r in rows})
    assert rq.count(has_missing_mods=True) == 5
    assert [r.id for r in rq.list(has_missing_mods=False, mod_guid="com.missing.x")] == []


def test_empty_database(conn) -> None:
    rq = ResourceQuery(conn)
    for flag in (None, True, False):
        assert rq.list(has_missing_mods=flag) == []
        assert rq.count(has_missing_mods=flag) == 0


def test_definition_matches_modquery_missing(seeded) -> None:
    """资源级筛选必须与 ModQuery.missing() 的 MOD 级口径一致。"""
    conn = seeded
    mq = ModQuery(conn)
    rq = ResourceQuery(conn)
    union: set[int] = set()
    for mod in mq.missing():
        union |= {r.id for r in mq.resources(mod.guid)}
    assert union == {r.id for r in rq.list(has_missing_mods=True)}
    assert {m.guid for m in mq.missing()} == {
        "com.missing.x",
        "com.missing.y",
        "com.missing.z",
    }


# ---------------------------------------------------------------------------
# 只读不变量
# ---------------------------------------------------------------------------


def test_has_missing_mods_is_read_only(seeded) -> None:
    conn = seeded
    rq = ResourceQuery(conn)
    before_changes = conn.total_changes
    before_flags = {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    }
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))
    before_mods = conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"]
    before_usages = conn.execute(
        "SELECT count(*) AS c FROM resource_mod_usages"
    ).fetchone()["c"]

    for _ in range(3):
        rq.list(has_missing_mods=True)
        rq.list(has_missing_mods=False)
        rq.count(has_missing_mods=True)
        rq.count(has_missing_mods=False)

    assert conn.total_changes == before_changes, "筛选不得写库"
    assert {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    } == before_flags
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta
    assert conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"] == before_mods
    assert (
        conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"]
        == before_usages
    )


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


def test_real_sample_has_missing_mods_partition(real_db) -> None:
    conn = real_db
    rq = ResourceQuery(conn)
    total = rq.count()
    with_missing = rq.count(has_missing_mods=True)
    without_missing = rq.count(has_missing_mods=False)

    assert total == 35
    assert with_missing + without_missing == total
    assert set(r.id for r in rq.list(has_missing_mods=True)).isdisjoint(
        r.id for r in rq.list(has_missing_mods=False)
    )
    assert len(rq.list(has_missing_mods=True)) == with_missing
    assert len(rq.list(has_missing_mods=False)) == without_missing


def test_real_sample_matches_modquery_missing(real_db) -> None:
    conn = real_db
    mq = ModQuery(conn)
    rq = ResourceQuery(conn)
    union: set[int] = set()
    for mod in mq.missing():
        union |= {r.id for r in mq.resources(mod.guid)}
    assert union == {r.id for r in rq.list(has_missing_mods=True)}


def test_real_sample_representative_resource(real_db) -> None:
    conn = real_db
    rq = ResourceQuery(conn)
    mq = ModQuery(conn)
    missing = mq.missing()
    assert missing, "真实样本应当存在缺失 MOD"
    guid = missing[0].guid
    users = mq.resources(guid)
    assert users, "缺失 MOD 应当至少被一个资源引用"
    rid = users[0].id
    # 该资源确实引用了这个缺失 MOD → has_missing_mods=True
    assert guid in {u.mod_guid for u in rq.usages(rid)}
    assert rid in {r.id for r in rq.list(has_missing_mods=True)}
    assert rid not in {r.id for r in rq.list(has_missing_mods=False)}


def test_real_sample_read_only(real_db) -> None:
    conn = real_db
    rq = ResourceQuery(conn)
    before_changes = conn.total_changes
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))
    before_mods = conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"]

    for _ in range(3):
        rq.list(has_missing_mods=True)
        rq.list(has_missing_mods=False)
        rq.count(has_missing_mods=True)

    assert conn.total_changes == before_changes
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta
    assert conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"] == before_mods
