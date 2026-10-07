"""Phase 1.3-A：只读查询层（``core.query``）测试。

分两部分：
- **合成场景**：用 ``tests.builders`` 造可控卡片 / zipmod，覆盖每个查询的正常结果与
  边界（不存在、missing、orphan、unknown property、跨资源不同 slot、只读）。
- **真实样本**：扫描 22 卡 + 13 zipmod，断言查询结果与 Phase 1.2/1.3 基线一致。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.query import (  # noqa: E402
    GAME_KK,
    GAME_KKS,
    AuthorQuery,
    ModQuery,
    PluginQuery,
    ReadOnlyViolation,
    ResourceQuery,
    UsageQuery,
)
from core.query.queries import _execute_select  # noqa: E402
from core.scanner import LibraryScanner  # noqa: E402
from tests import builders  # noqa: E402


def _rid(conn, relative_path: str) -> int:
    row = conn.execute(
        "SELECT id FROM resources WHERE replace(relative_path, '\\', '/') = ?",
        (relative_path.replace("\\", "/"),),
    ).fetchone()
    assert row is not None, f"没有入库：{relative_path}"
    return int(row["id"])


# ---------------------------------------------------------------------------
# 合成场景
# ---------------------------------------------------------------------------


@pytest.fixture()
def synth(tmp_path: Path):
    """一个可控的小型资源库。

    cardA: com.x.body(body) + com.x.cloth(clothes)，插件 moreAccessories+KSOX，作者 Alice
    cardB: com.x.body(body, 不同 slot) + com.missing(body)，插件 moreAccessories，作者 Bob
    cardC: com.weird(unknown property)，插件 moreAccessories+KSOX，作者 Alice
    cardD: 无 MOD 依赖，插件 moreAccessories

    本地 zipmod：com.x.body / com.x.cloth / com.orphan（com.orphan 无人引用）。
    """
    root = tmp_path / "lib"
    root.mkdir()
    builders.write_card(
        root / "cardA.png",
        lastname="A",
        firstname="Card",
        plugin_guids=("moreAccessories", "KSOX"),
        dependencies=(
            ("com.x.body", "ChaFileBody.detailId", 7426),
            ("com.x.cloth", "outfit6.ChaFileClothes.ClothesTop", 103),
        ),
        authors=("Alice", "[Unknown]"),
    )
    builders.write_card(
        root / "cardB.png",
        lastname="B",
        firstname="Card",
        plugin_guids=("moreAccessories",),
        dependencies=(
            ("com.x.body", "ChaFileBody.detailId", 7427),
            ("com.missing", "ChaFileBody.nipId", 9),
        ),
        authors=("Bob",),
    )
    builders.write_card(
        root / "cardC.png",
        lastname="C",
        firstname="Card",
        plugin_guids=("moreAccessories", "KSOX"),
        dependencies=(("com.weird", "Totally.Different", 1),),
        authors=("Alice",),
    )
    builders.write_card(
        root / "cardD.png",
        lastname="D",
        firstname="Card",
        plugin_guids=("moreAccessories",),
        dependencies=(),
    )
    builders.write_zipmod(root / "installed_body.zipmod", "com.x.body", name="Body")
    builders.write_zipmod(root / "installed_cloth.zipmod", "com.x.cloth", name="Cloth")
    builders.write_zipmod(root / "orphan.zipmod", "com.orphan", name="Orphan")

    db_file = tmp_path / "query.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    library = LibraryStore(conn).add(root, name="synth")
    LibraryScanner(conn).scan(library.id)
    yield conn
    conn.close()


def test_resource_to_mods(synth) -> None:
    rid = _rid(synth, "cardA.png")
    mods = ResourceQuery(synth).mods(rid)
    assert {m.mod_guid for m in mods} == {"com.x.body", "com.x.cloth"}
    by_guid = {m.mod_guid: m for m in mods}
    assert by_guid["com.x.body"].installed is True
    assert by_guid["com.x.body"].ref_count == 1
    assert by_guid["com.x.cloth"].categories == ("clothes",)


def test_mod_to_resources(synth) -> None:
    rids = {r.id for r in ModQuery(synth).resources("com.x.body")}
    assert rids == {_rid(synth, "cardA.png"), _rid(synth, "cardB.png")}


def test_resource_to_plugins(synth) -> None:
    rid = _rid(synth, "cardA.png")
    plugins = ResourceQuery(synth).plugins(rid)
    assert "moreAccessories" in plugins and "KSOX" in plugins


def test_plugin_to_resources(synth) -> None:
    query = PluginQuery(synth)
    assert {r.id for r in query.resources("KSOX")} == {
        _rid(synth, "cardA.png"),
        _rid(synth, "cardC.png"),
    }
    summary = query.get("moreAccessories")
    assert summary is not None and summary.resource_count == 4


def test_resource_to_authors_and_author_to_resources(synth) -> None:
    rq = ResourceQuery(synth)
    aq = AuthorQuery(synth)

    authors_a = rq.authors(_rid(synth, "cardA.png"))
    assert [(a.name, a.ordinal, a.raw_name) for a in authors_a] == [
        ("Alice", 0, "Alice")
    ]
    assert rq.authors_raw(_rid(synth, "cardA.png")) == ["Alice", "[Unknown]"]

    alice = aq.find_by_name("alice")
    assert alice is not None
    assert {r.id for r in aq.resources(alice.id)} == {
        _rid(synth, "cardA.png"),
        _rid(synth, "cardC.png"),
    }
    assert {a.name: a.resource_count for a in aq.list()} == {"Alice": 2, "Bob": 1}


def test_missing_mods(synth) -> None:
    missing = ModQuery(synth).missing()
    assert {m.guid for m in missing} == {"com.missing", "com.weird"}
    for mod in missing:
        assert mod.installed is False and mod.id is None


def test_orphan_mods(synth) -> None:
    orphan = ModQuery(synth).orphan()
    assert {m.guid for m in orphan} == {"com.orphan"}
    assert orphan[0].used_by_count == 0


def test_property_category_filters(synth) -> None:
    rq = ResourceQuery(synth)
    assert {r.id for r in rq.list(property_category="clothes")} == {
        _rid(synth, "cardA.png")
    }
    assert {r.id for r in rq.list(property_category="body")} == {
        _rid(synth, "cardA.png"),
        _rid(synth, "cardB.png"),
    }
    assert {r.id for r in rq.list(property_category="unknown")} == {
        _rid(synth, "cardC.png")
    }
    assert {r.id for r in rq.list(property_category="hair")} == set()


def test_unknown_property_is_preserved(synth) -> None:
    usage = UsageQuery(synth)
    rid = _rid(synth, "cardC.png")
    counts = {c.category: c.count for c in usage.category_counts(resource_id=rid)}
    assert counts["unknown"] == 1
    assert usage.unknown_properties(resource_id=rid) == ["Totally.Different"]
    assert usage.for_mod("com.weird")[0].category == "unknown"
    detail = ModQuery(synth).detail("com.weird")
    assert detail is not None
    assert {c.category: c.count for c in detail.category_counts}["unknown"] == 1


def test_mod_used_with_category(synth) -> None:
    usage = UsageQuery(synth)
    assert len(usage.for_mod("com.x.body", category="body")) == 2
    assert usage.for_mod("com.x.body", category="clothes") == []
    assert usage.resources_using("com.x.body", category="body") == [
        _rid(synth, "cardA.png"),
        _rid(synth, "cardB.png"),
    ]
    assert usage.mods_in_resource(_rid(synth, "cardA.png"), category="clothes") == [
        "com.x.cloth"
    ]


def test_same_mod_different_slot_across_resources(synth) -> None:
    rows = ModQuery(synth).usages("com.x.body")
    assert {r.slot for r in rows} == {7426, 7427}
    assert all(r.property == "ChaFileBody.detailId" for r in rows)


def test_one_resource_many_mods_and_one_mod_many_resources(synth) -> None:
    rq = ResourceQuery(synth)
    assert rq.summary(_rid(synth, "cardA.png")).mod_count == 2
    assert rq.summary(_rid(synth, "cardD.png")).mod_count == 0
    assert ModQuery(synth).get("com.x.body").used_by_count == 2


def test_nonexistent_targets_return_empty(synth) -> None:
    assert ResourceQuery(synth).get(999999) is None
    assert ResourceQuery(synth).summary(999999) is None
    assert ResourceQuery(synth).mods(999999) == []
    assert ModQuery(synth).get("does.not.exist") is None
    assert ModQuery(synth).detail("does.not.exist") is None
    assert ModQuery(synth).resources("does.not.exist") == []
    assert PluginQuery(synth).get("nope") is None
    assert PluginQuery(synth).resources("nope") == []
    assert AuthorQuery(synth).get(999999) is None
    assert AuthorQuery(synth).find_by_name("nobody") is None


def test_resource_resolve_by_id_path_and_relative(synth) -> None:
    rq = ResourceQuery(synth)
    summary = rq.resolve("cardA.png")
    assert summary is not None
    assert rq.resolve(str(summary.id)).id == summary.id
    assert rq.resolve(summary.file_path).id == summary.id
    assert rq.resolve("no/such/file.png") is None


def test_has_mods_filter(synth) -> None:
    rq = ResourceQuery(synth)
    assert {
        r.id for r in rq.list(resource_type="character_card", has_mods=False)
    } == {_rid(synth, "cardD.png")}
    assert {
        r.id for r in rq.list(resource_type="character_card", has_mods=True)
    } == {
        _rid(synth, "cardA.png"),
        _rid(synth, "cardB.png"),
        _rid(synth, "cardC.png"),
    }


def test_author_resolve(synth) -> None:
    aq = AuthorQuery(synth)
    assert aq.resolve("Bob").name == "Bob"
    assert aq.resolve("bob").name == "Bob"
    assert aq.resolve("999999") is None


def test_usage_all_and_category_stats(synth) -> None:
    usage = UsageQuery(synth)
    assert len(usage.all()) == 5
    assert len(usage.all(limit=2)) == 2
    stats = {s.category: s for s in usage.category_stats()}
    assert stats["body"].usage_count == 3
    assert stats["body"].resource_count == 2
    assert stats["body"].mod_count == 2
    assert stats["unknown"].usage_count == 1


def test_query_layer_is_read_only(synth) -> None:
    conn = synth
    before = conn.total_changes
    counts_before = {
        table: conn.execute(f"SELECT count(*) c FROM {table}").fetchone()["c"]
        for table in (
            "resources",
            "mods",
            "resource_mods",
            "resource_mod_usages",
            "resource_plugins",
            "resource_authors",
        )
    }

    ResourceQuery(conn).list()
    ResourceQuery(conn).get(_rid(conn, "cardA.png"))
    ModQuery(conn).installed()
    ModQuery(conn).missing()
    ModQuery(conn).orphan()
    PluginQuery(conn).list()
    AuthorQuery(conn).list()
    UsageQuery(conn).category_counts()

    assert conn.total_changes == before, "查询层不得产生任何写操作"
    for table, count in counts_before.items():
        assert conn.execute(f"SELECT count(*) c FROM {table}").fetchone()["c"] == count

    with pytest.raises(ReadOnlyViolation):
        _execute_select(conn, "DELETE FROM resources")
    with pytest.raises(ReadOnlyViolation):
        _execute_select(conn, "UPDATE resources SET name = 'x'")


# ---------------------------------------------------------------------------
# 真实样本
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sample_db(tmp_path_factory: pytest.TempPathFactory, sample_root: Path):
    db_file = tmp_path_factory.mktemp("query_sample") / "samples.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    library = LibraryStore(conn).add(sample_root, name="真实样本")
    LibraryScanner(conn).scan(library.id)
    yield conn
    conn.close()


def test_sample_baseline_counts(sample_db) -> None:
    conn = sample_db
    assert conn.execute("SELECT count(*) c FROM resources").fetchone()["c"] == 35
    assert conn.execute("SELECT count(*) c FROM mods").fetchone()["c"] == 13
    assert (
        conn.execute("SELECT count(*) c FROM resource_mod_usages").fetchone()["c"]
        == 1527
    )
    assert conn.execute("SELECT count(*) c FROM resource_mods").fetchone()["c"] == 315
    assert conn.execute("SELECT count(*) c FROM resource_plugins").fetchone()["c"] == 206
    assert conn.execute("SELECT count(*) c FROM resource_authors").fetchone()["c"] == 14
    assert conn.execute("SELECT count(*) c FROM authors").fetchone()["c"] == 3


def test_sample_resource_list_and_game_filter(sample_db) -> None:
    rq = ResourceQuery(sample_db)
    assert len(rq.list()) == 35
    assert rq.count(game=GAME_KKS) == 21
    assert rq.count(game=GAME_KK) == 1
    assert rq.count(resource_type="mod") == 13
    kks = rq.list(game=GAME_KKS)
    assert all(r.game == GAME_KKS for r in kks)


def test_sample_mods_missing_orphan(sample_db) -> None:
    mq = ModQuery(sample_db)
    assert len(mq.installed()) == 13
    assert len(mq.missing()) == 134
    orphans = {m.guid for m in mq.orphan()}
    assert orphans == {"NoHair", "elven_panst", "koikatu.AltSlot.co_bot_19"}


def test_sample_sayaka_and_kyoko(sample_db) -> None:
    rq = ResourceQuery(sample_db)
    mq = ModQuery(sample_db)

    cards = rq.list(resource_type="character_card")
    sayaka = next(r for r in cards if "美树沙耶香" in (r.relative_path or ""))
    detail = rq.get(sayaka.id)
    assert detail is not None
    assert [m.mod_guid for m in detail.mods] == ["com.Quokka.sisterveilb"]
    assert detail.mods[0].ref_count == 4
    assert len(detail.usages) == 4

    kyoko = next(r for r in cards if "佐仓杏子" in (r.relative_path or ""))
    refs = rq.mods(kyoko.id)
    assert len(refs) == 3
    by_guid = {r.mod_guid: r for r in refs}
    assert by_guid["com.ymgpt.acc_earrings_top"].installed is False
    assert mq.get("com.ymgpt.acc_earrings_top").installed is False


def test_sample_property_category_totals(sample_db) -> None:
    counts = {c.category: c.count for c in UsageQuery(sample_db).category_counts()}
    assert counts == {
        "face": 62,
        "body": 25,
        "clothes": 280,
        "accessory": 1129,
        "hair": 18,
        "makeup": 13,
        "unknown": 0,
    }
    assert sum(counts.values()) == 1527


def test_sample_shared_mod_across_resources(sample_db) -> None:
    mq = ModQuery(sample_db)
    resources = mq.resources("com.Quokka.naginata")
    assert len(resources) == 2
    usages = mq.usages("com.Quokka.naginata")
    assert len({u.resource_id for u in usages}) == 2
    assert len({u.property for u in usages}) == 2


def test_sample_plugin_and_author_queries(sample_db) -> None:
    plugins = {p.plugin_guid: p.resource_count for p in PluginQuery(sample_db).list()}
    assert plugins["moreAccessories"] > 0
    authors = {a.name: a.resource_count for a in AuthorQuery(sample_db).list()}
    assert authors == {"Anonymous": 6, "Evaan": 5, "Azurou": 3}


def test_sample_plugin_count_is_authoritative(sample_db) -> None:
    rq = ResourceQuery(sample_db)
    for summary in rq.list(resource_type="character_card"):
        assert summary.plugin_count == len(rq.plugins(summary.id))


def test_sample_ref_count_matches_usages(sample_db) -> None:
    rq = ResourceQuery(sample_db)
    checked = 0
    for summary in rq.list():
        for ref in rq.mods(summary.id):
            actual = sum(
                1 for u in rq.usages(summary.id) if u.mod_guid == ref.mod_guid
            )
            assert ref.ref_count == actual
            checked += 1
    assert checked == 315


def test_sample_query_layer_is_read_only(sample_db) -> None:
    conn = sample_db
    before = conn.total_changes
    ResourceQuery(conn).list()
    ModQuery(conn).missing()
    ModQuery(conn).orphan()
    UsageQuery(conn).category_counts()
    assert conn.total_changes == before
