"""Phase 1.2-C 验收：Scanner（synthetic tests）。

覆盖：空 Library、非资源文件、损坏文件、MOD dependency / orphan / shared、
重复扫描、文件变化、单文件失败隔离、事务回滚、Unicode、KK+KKS、同 dataID。

所有样本都在临时目录里构造，真实样本目录不受影响。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.scanner import LibraryScanner, ResourceStore  # noqa: E402
from tests.builders import (  # noqa: E402
    MARKER_KK,
    MARKER_SUN,
    MODLIST_PLUGIN,
    write_broken_png,
    write_broken_zip,
    write_card,
    write_plain_png,
    write_zip_without_manifest,
    write_zipmod,
)


@pytest.fixture()
def env(tmp_path: Path):
    """一个干净的数据库 + 一个空的 Library 目录。"""
    db_file = tmp_path / "scan.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    root = tmp_path / "library"
    root.mkdir()
    library = LibraryStore(conn).add(root, name="测试库")
    yield conn, root, library
    conn.close()


def _counts(conn) -> dict:
    return {
        table: conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"]
        for table in (
            "resources",
            "mods",
            "resource_mods",
            "resource_mod_usages",
            "resource_plugins",
            "resource_authors",
            "authors",
            "scan_records",
        )
    }


# ---------------------------------------------------------------------------
# 基本流程
# ---------------------------------------------------------------------------


def test_empty_library(env):
    conn, _root, library = env
    result = LibraryScanner(conn).scan(library.id)

    assert result.status == "completed"
    assert result.stats.discovered == 0
    assert result.stats.inserted == 0
    assert conn.execute("SELECT count(*) AS c FROM scan_records").fetchone()["c"] == 1


def test_valid_card_is_inserted(env):
    conn, root, library = env
    write_card(root / "card.png", lastname="鹿目", firstname="まどか")

    result = LibraryScanner(conn).scan(library.id)

    assert (result.stats.discovered, result.stats.parsed, result.stats.inserted) == (1, 1, 1)
    assert result.stats.failed == 0
    row = conn.execute("SELECT * FROM resources").fetchone()
    assert row["resource_type"] == "character_card"
    assert row["name"] == "鹿目まどか"
    assert row["card_marker"] == MARKER_SUN.strip("【】")
    assert row["library_id"] == library.id
    assert row["parse_status"] == "ok"
    assert row["file_size"] == (root / "card.png").stat().st_size
    assert row["relative_path"] == "card.png"
    assert row["extension"] == ".png"


def test_card_metadata_json_is_written(env):
    conn, root, library = env
    write_card(
        root / "card.png",
        user_id="u-1",
        data_id="d-1",
        embedded_pngs=3,
        plugin_guids=("moreAccessories", "KSOX"),
    )
    LibraryScanner(conn).scan(library.id)

    metadata = json.loads(
        conn.execute("SELECT metadata_json FROM resources").fetchone()["metadata_json"]
    )
    assert metadata["user_id"] == "u-1"
    assert metadata["data_id"] == "d-1"
    assert metadata["embedded_texture_count"] == 3
    assert metadata["plugin_count"] == 3  # MODLIST + moreAccessories + KSOX
    assert metadata["card_version"] == "0.0.0"
    assert metadata["face_preview_kind"] == "jpeg"
    assert isinstance(metadata["block_sizes"], dict)


def test_kk_and_kks_markers_are_preserved_separately(env):
    conn, root, library = env
    write_card(root / "sun.png", marker=MARKER_SUN)
    write_card(root / "kk.png", marker=MARKER_KK, user_id=None, data_id=None)
    LibraryScanner(conn).scan(library.id)

    markers = [
        r["card_marker"]
        for r in conn.execute(
            "SELECT card_marker FROM resources ORDER BY card_marker"
        ).fetchall()
    ]
    assert markers == [MARKER_KK.strip("【】"), MARKER_SUN.strip("【】")]

    kk = conn.execute(
        "SELECT * FROM resources WHERE card_marker = ?", (MARKER_KK.strip("【】"),)
    ).fetchone()
    assert kk["parse_status"] == "ok"
    metadata = json.loads(kk["metadata_json"])
    assert metadata["user_id"] is None
    assert metadata["data_id"] is None


def test_no_eyes_skin_hair_clothes_resource_types(env):
    conn, root, library = env
    write_card(
        root / "card.png",
        dependencies=(
            ("com.gf.collection", "ChaFileFace.Pupil1", None),
            ("com.Blanketman.AdditionalSkinMod", "ChaFileBody.detailId", None),
            ("shinyBunny", "outfit6.ChaFileClothes.ClothesTop", None),
        ),
    )
    write_zipmod(root / "mod.zipmod", "shinyBunny")
    LibraryScanner(conn).scan(library.id)

    types = {
        r["resource_type"]
        for r in conn.execute("SELECT resource_type FROM resources").fetchall()
    }
    assert types <= {"character_card", "mod"}
    properties = {
        r["property"]
        for r in conn.execute("SELECT property FROM resource_mod_usages").fetchall()
    }
    assert "ChaFileFace.Pupil1" in properties
    assert "ChaFileBody.detailId" in properties
    assert "outfit6.ChaFileClothes.ClothesTop" in properties


# ---------------------------------------------------------------------------
# 非资源 / 损坏文件
# ---------------------------------------------------------------------------


def test_plain_png_does_not_create_resource(env):
    conn, root, library = env
    write_plain_png(root / "photo.png")

    result = LibraryScanner(conn).scan(library.id)

    assert result.stats.parsed == 1
    assert result.stats.inserted == 0
    assert result.stats.failed == 1
    assert result.stats.not_a_resource == 1
    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 0
    assert result.issues[0].stage == "not_a_resource"


def test_zip_without_manifest_does_not_create_mod(env):
    conn, root, library = env
    write_zip_without_manifest(root / "archive.zip")

    result = LibraryScanner(conn).scan(library.id)

    assert result.stats.inserted == 0
    assert result.stats.failed == 1
    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 0
    assert conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"] == 0


def test_broken_files_are_counted_not_crashing(env):
    conn, root, library = env
    write_broken_png(root / "broken.png")
    write_broken_zip(root / "broken.zipmod")
    write_card(root / "good.png")

    result = LibraryScanner(conn).scan(library.id)

    assert result.status == "completed"
    assert result.stats.discovered == 3
    assert result.stats.failed == 2
    assert result.stats.inserted == 1
    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 1


def test_single_file_failure_does_not_affect_others(env):
    """A 成功 / B 解析失败 / C 成功 —— A、C 必须照常入库。"""
    conn, root, library = env
    write_card(root / "a_card.png", lastname="A")
    write_plain_png(root / "b_broken.png")
    write_card(root / "c_card.png", lastname="C")

    result = LibraryScanner(conn).scan(library.id)

    names = {
        r["name"] for r in conn.execute("SELECT name FROM resources").fetchall()
    }
    assert names == {"A角色", "C角色"}
    assert result.stats.inserted == 2
    assert result.stats.failed == 1
    assert [i.stage for i in result.issues] == ["not_a_resource"]


def test_store_error_isolated_and_rolled_back(env, monkeypatch):
    """入库阶段抛异常：该文件回滚，且不影响其它文件。"""
    conn, root, library = env
    write_card(root / "a.png", lastname="A")
    write_card(root / "b.png", lastname="B")
    write_card(root / "c.png", lastname="C")

    original = ResourceStore.upsert_card_resource
    state = {"count": 0}

    def flaky(self, **kwargs):
        state["count"] += 1
        if state["count"] == 2:
            raise RuntimeError("模拟入库失败")
        return original(self, **kwargs)

    monkeypatch.setattr(ResourceStore, "upsert_card_resource", flaky)
    result = LibraryScanner(conn).scan(library.id)

    assert result.status == "completed"
    assert result.stats.inserted == 2
    assert result.stats.failed == 1
    assert [i.stage for i in result.issues] == ["store"]

    names = {r["name"] for r in conn.execute("SELECT name FROM resources").fetchall()}
    assert names == {"A角色", "C角色"}, "失败文件不能留下半截数据"
    assert conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 0


def test_relations_rollback_together(env, monkeypatch):
    """关系写入中途失败 → 该文件整体回滚（资源行也不会留下）。"""
    conn, root, library = env
    write_card(
        root / "a.png",
        dependencies=(("com.example.x", "outfit0.accessory1.ChaFileAccessory.PartsInfo.id", 1),),
    )

    def boom(self, resource_id, dependencies):
        raise RuntimeError("关系写入失败")

    monkeypatch.setattr(ResourceStore, "_replace_usages", boom)
    result = LibraryScanner(conn).scan(library.id)

    assert result.stats.failed == 1
    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 0
    assert conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 0


# ---------------------------------------------------------------------------
# MOD 关系
# ---------------------------------------------------------------------------


def test_dependency_records_become_usage_rows(env):
    conn, root, library = env
    write_card(
        root / "sayaka.png",
        dependencies=(
            ("com.Quokka.sisterveilb", "outfit6.accessory10.ChaFileAccessory.PartsInfo.id", 10),
            ("com.Quokka.sisterveilb", "outfit6.accessory11.ChaFileAccessory.PartsInfo.id", 11),
            ("com.Quokka.sisterveilb", "outfit2.accessory1.ChaFileAccessory.PartsInfo.id", 1),
        ),
    )
    LibraryScanner(conn).scan(library.id)

    resource_id = conn.execute("SELECT id FROM resources").fetchone()["id"]
    usages = conn.execute(
        "SELECT * FROM resource_mod_usages WHERE resource_id = ? ORDER BY property",
        (resource_id,),
    ).fetchall()
    assert len(usages) == 3
    assert {u["mod_guid"] for u in usages} == {"com.Quokka.sisterveilb"}
    assert [u["slot"] for u in usages] == [1, 10, 11]
    assert [u["local_slot"] for u in usages] == [1, 10, 11]
    assert {u["category_no"] for u in usages} == {0}

    summary = conn.execute(
        "SELECT * FROM resource_mods WHERE resource_id = ?", (resource_id,)
    ).fetchall()
    assert len(summary) == 1
    assert summary[0]["ref_count"] == 3
    assert summary[0]["relation"] == "uses"
    assert summary[0]["mod_id"] is None, "本地没有该 zipmod → mod_id 为空"


def test_missing_mod_keeps_relation_without_creating_mod_entity(env):
    conn, root, library = env
    write_card(
        root / "kyoko.png",
        dependencies=(("com.ymgpt.acc_earrings_top", "outfit6.accessory10.ChaFileAccessory.PartsInfo.id", 10),),
    )
    LibraryScanner(conn).scan(library.id)

    assert conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"] == 0
    assert conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 1
    assert conn.execute("SELECT mod_id FROM resource_mods").fetchone()["mod_id"] is None


def test_present_mod_backfills_mod_id(env):
    """先扫卡片（MOD 未安装），再扫到 zipmod → mod_id 被回填。"""
    conn, root, library = env
    write_card(
        root / "card.png",
        dependencies=(("com.example.mod", "outfit0.accessory1.ChaFileAccessory.PartsInfo.id", 1),),
    )
    scanner = LibraryScanner(conn)
    scanner.scan(library.id)
    assert conn.execute("SELECT mod_id FROM resource_mods").fetchone()["mod_id"] is None

    write_zipmod(root / "themod.zipmod", "com.example.mod")
    scanner.scan(library.id)

    mod_id = conn.execute(
        "SELECT id FROM mods WHERE guid = 'com.example.mod'"
    ).fetchone()["id"]
    assert conn.execute("SELECT mod_id FROM resource_mods").fetchone()["mod_id"] == mod_id


def test_zipmod_is_stored_with_manifest_fields(env):
    conn, root, library = env
    write_zipmod(
        root / "mod.zipmod", "shinyBunny",
        name="shinyBunny", author="essu", version="1.0", website=None,
    )

    result = LibraryScanner(conn).scan(library.id)

    assert result.stats.inserted == 1
    mod = conn.execute("SELECT * FROM mods").fetchone()
    assert mod["guid"] == "shinyBunny", "非 dotted GUID 也必须接受"
    assert mod["name"] == "shinyBunny"
    assert mod["author"] == "essu"
    assert mod["version"] == "1.0"
    resource = conn.execute("SELECT * FROM resources").fetchone()
    assert resource["resource_type"] == "mod"
    assert resource["id"] == mod["resource_id"]
    assert conn.execute("SELECT count(*) AS c FROM resource_plugins").fetchone()["c"] == 0
    assert conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 0


def test_empty_author_and_version_are_stored(env):
    conn, root, library = env
    write_zipmod(root / "nohair.zipmod", "NoHair", name="NoHair Head", author="", version="0")
    LibraryScanner(conn).scan(library.id)
    mod = conn.execute("SELECT * FROM mods").fetchone()
    assert mod["author"] == ""
    assert mod["version"] == "0"


def test_orphan_mod_has_no_relations(env):
    conn, root, library = env
    write_zipmod(root / "orphan.zipmod", "elven_panst")
    LibraryScanner(conn).scan(library.id)
    assert conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"] == 1
    assert conn.execute("SELECT count(*) AS c FROM resource_mods").fetchone()["c"] == 0


def test_shared_mod_between_two_cards(env):
    conn, root, library = env
    write_card(
        root / "a.png",
        dependencies=(("com.Quokka.naginata", "outfit0.accessory4.ChaFileAccessory.PartsInfo.id", 4),),
    )
    write_card(
        root / "b.png",
        dependencies=(("com.Quokka.naginata", "outfit4.accessory56.ChaFileAccessory.PartsInfo.id", 56),),
    )
    write_zipmod(root / "naginata.zipmod", "com.Quokka.naginata")
    LibraryScanner(conn).scan(library.id)

    used_by = conn.execute(
        "SELECT DISTINCT resource_id FROM resource_mod_usages WHERE mod_guid = ?"
        " ORDER BY resource_id",
        ("com.Quokka.naginata",),
    ).fetchall()
    assert len(used_by) == 2
    mod_id = conn.execute(
        "SELECT id FROM mods WHERE guid='com.Quokka.naginata'"
    ).fetchone()["id"]
    assert {
        r["mod_id"] for r in conn.execute("SELECT mod_id FROM resource_mods").fetchall()
    } == {mod_id}


def test_plugins_are_stored_separately_from_mods(env):
    conn, root, library = env
    write_card(root / "card.png", plugin_guids=("moreAccessories", "KSOX", "marco.authordata"))
    LibraryScanner(conn).scan(library.id)

    plugins = {
        r["plugin_guid"]
        for r in conn.execute("SELECT plugin_guid FROM resource_plugins").fetchall()
    }
    assert plugins == {MODLIST_PLUGIN, "moreAccessories", "KSOX", "marco.authordata"}
    assert conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"] == 0


# ---------------------------------------------------------------------------
# 增量扫描
# ---------------------------------------------------------------------------


def test_second_scan_skips_everything(env):
    conn, root, library = env
    write_card(root / "card.png", dependencies=(("com.example.x", "outfit0.a", 0),))
    write_zipmod(root / "mod.zipmod", "com.example.x")
    scanner = LibraryScanner(conn)

    first = scanner.scan(library.id)
    before = _counts(conn)
    second = scanner.scan(library.id)
    after = _counts(conn)

    assert first.stats.inserted == 2
    assert second.stats.discovered == 2
    assert second.stats.parsed == 0, "未变化的文件不得重新解析"
    assert second.stats.skipped == 2
    assert second.stats.inserted == second.stats.updated == 0
    # scan_records 每次扫描都会多一条，这是预期；其余表必须一行不差
    assert before.pop("scan_records") == after.pop("scan_records") - 1
    assert before == after, "重复扫描不能新增任何数据行"


def test_changed_file_is_reparsed_and_relations_rebuilt(env):
    conn, root, library = env
    card = root / "card.png"
    write_card(card, dependencies=(("com.example.old", "outfit0.a", 0),))
    scanner = LibraryScanner(conn)
    scanner.scan(library.id)
    assert (
        conn.execute("SELECT mod_guid FROM resource_mods").fetchone()["mod_guid"]
        == "com.example.old"
    )

    write_card(
        card,
        lastname="新",
        dependencies=(
            ("com.example.new", "outfit1.a", 1),
            ("com.example.new", "outfit2.a", 2),
        ),
    )
    result = scanner.scan(library.id)

    assert result.stats.updated == 1
    assert result.stats.inserted == 0
    assert result.stats.parsed == 1
    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 1
    assert conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 2
    assert {
        r["mod_guid"] for r in conn.execute("SELECT mod_guid FROM resource_mods").fetchall()
    } == {"com.example.new"}
    assert conn.execute("SELECT ref_count FROM resource_mods").fetchone()["ref_count"] == 2
    assert conn.execute("SELECT name FROM resources").fetchone()["name"] == "新角色"


def test_full_mode_reparses_unchanged_files(env):
    conn, root, library = env
    write_card(root / "card.png")
    scanner = LibraryScanner(conn)
    scanner.scan(library.id)

    result = scanner.scan(library.id, mode="full")

    assert result.stats.parsed == 1
    assert result.stats.updated == 1
    assert result.stats.skipped == 0


def test_deleted_file_is_marked_missing_not_deleted(env):
    conn, root, library = env
    card = root / "card.png"
    write_card(card)
    scanner = LibraryScanner(conn)
    scanner.scan(library.id)
    assert (
        conn.execute("SELECT scan_status FROM resources").fetchone()["scan_status"]
        == "present"
    )

    card.unlink()
    result = scanner.scan(library.id)

    assert result.stats.missing == 1
    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 1, (
        "不自动删除 resources"
    )
    assert (
        conn.execute("SELECT scan_status FROM resources").fetchone()["scan_status"]
        == "missing"
    )


def test_returning_file_restores_present(env):
    conn, root, library = env
    card = root / "card.png"
    payload = write_card(card).read_bytes()
    scanner = LibraryScanner(conn)
    scanner.scan(library.id)
    card.unlink()
    scanner.scan(library.id)
    assert (
        conn.execute("SELECT scan_status FROM resources").fetchone()["scan_status"]
        == "missing"
    )

    card.write_bytes(payload)
    result = scanner.scan(library.id)

    assert result.stats.missing == 0
    assert (
        conn.execute("SELECT scan_status FROM resources").fetchone()["scan_status"]
        == "present"
    )


def test_disabled_library_is_not_scanned(env):
    conn, root, library = env
    write_card(root / "card.png")
    LibraryStore(conn).set_enabled(library.id, False)

    result = LibraryScanner(conn).scan(library.id)

    assert result.status == "skipped"
    assert result.stats.discovered == 0
    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 0
    assert conn.execute("SELECT count(*) AS c FROM scan_records").fetchone()["c"] == 0


# ---------------------------------------------------------------------------
# 边缘情况
# ---------------------------------------------------------------------------


def test_unicode_file_names(env):
    conn, root, library = env
    write_card(root / "魔法少女小圆 - 鹿目圆.png", lastname="鹿目", firstname="まどか")
    write_zipmod(root / "[Quokka] 服装 1.0.zipmod", "com.Quokka.x")
    LibraryScanner(conn).scan(library.id)

    names = {r["name"] for r in conn.execute("SELECT name FROM resources").fetchall()}
    assert names == {"鹿目まどか", "Test Mod"}
    relative = {
        r["relative_path"]
        for r in conn.execute("SELECT relative_path FROM resources").fetchall()
    }
    assert "魔法少女小圆 - 鹿目圆.png" in relative


def test_two_cards_with_same_data_id_both_stored(env):
    conn, root, library = env
    write_card(root / "a.png", data_id="SAME-ID")
    write_card(root / "b.png", lastname="別", data_id="SAME-ID")
    LibraryScanner(conn).scan(library.id)

    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 2
    ids = {
        json.loads(r["metadata_json"])["data_id"]
        for r in conn.execute("SELECT metadata_json FROM resources").fetchall()
    }
    assert ids == {"SAME-ID"}, "dataID 不是唯一键"


def test_identical_bytes_at_two_paths_are_both_kept(env):
    """两个路径、内容完全相同的卡片 → 保留两行（不做静默去重）。"""
    conn, root, library = env
    payload = write_card(root / "a.png").read_bytes()
    (root / "b.png").write_bytes(payload)
    LibraryScanner(conn).scan(library.id)

    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 2


def test_scan_record_statistics(env):
    conn, root, library = env
    write_card(root / "card.png")
    write_plain_png(root / "photo.png")
    scanner = LibraryScanner(conn)
    scanner.scan(library.id)
    scanner.scan(library.id)

    rows = conn.execute("SELECT * FROM scan_records ORDER BY id").fetchall()
    assert len(rows) == 2

    first, second = rows
    assert first["status"] == "completed"
    assert first["mode"] == "incremental"
    assert (first["files_seen"], first["files_new"], first["files_failed"]) == (2, 1, 1)
    assert first["duration_ms"] is not None
    assert first["finished_at"] is not None

    assert (second["files_seen"], second["files_skipped"], second["files_failed"]) == (2, 1, 1)
    assert second["error_message"], "失败信息要留在 scan_records 里"


def test_scan_records_keep_existing_column_semantics(env):
    """映射检查：discovered→files_seen、inserted→files_new …（不新增列）。"""
    conn, root, library = env
    write_card(root / "card.png")
    result = LibraryScanner(conn).scan(library.id)

    fields = result.stats.scan_record_fields()
    assert set(fields) == {
        "files_seen",
        "files_new",
        "files_changed",
        "files_skipped",
        "files_missing",
        "files_failed",
    }
    row = conn.execute("SELECT * FROM scan_records").fetchone()
    for column, value in fields.items():
        assert row[column] == value


# ---------------------------------------------------------------------------
# 作者（Phase 1.2-D）
# ---------------------------------------------------------------------------


def _author_rows(conn):
    return conn.execute(
        "SELECT a.name, ra.ordinal, ra.raw_name FROM resource_authors ra"
        " JOIN authors a ON a.id = ra.author_id ORDER BY ra.ordinal"
    ).fetchall()


def test_authors_are_stored_with_raw_ordinal(env):
    """``['[Unknown]', 'Evaan', 'Alice']`` → Evaan=1、Alice=2（保原始位置）。"""
    conn, root, library = env
    write_card(root / "card.png", authors=("[Unknown]", "Evaan", "Alice"))
    LibraryScanner(conn).scan(library.id)

    rows = _author_rows(conn)
    assert [(r["name"], r["ordinal"], r["raw_name"]) for r in rows] == [
        ("Evaan", 1, "Evaan"),
        ("Alice", 2, "Alice"),
    ]
    assert {r["name"] for r in conn.execute("SELECT name FROM authors").fetchall()} == {
        "Evaan",
        "Alice",
    }, "[Unknown] 不能成为作者实体"


def test_authors_raw_kept_in_metadata(env):
    conn, root, library = env
    write_card(root / "card.png", authors=("[Unknown]", "Evaan"))
    LibraryScanner(conn).scan(library.id)

    metadata = json.loads(
        conn.execute("SELECT metadata_json FROM resources").fetchone()["metadata_json"]
    )
    assert metadata["authors_raw"] == ["[Unknown]", "Evaan"]


def test_duplicate_and_blank_authors_follow_partition_rules(env):
    """重复 / 空白按 partition_authors 处理，但 ordinal 仍是原始下标。"""
    conn, root, library = env
    write_card(
        root / "card.png",
        authors=("[Unknown]", "  Evaan ", "Evaan", "", "Anonymous"),
    )
    LibraryScanner(conn).scan(library.id)

    rows = _author_rows(conn)
    # Evaan 第一次出现在下标 1（带空格）→ raw_name 保留原样、ordinal=1；
    # 下标 2 的重复 Evaan 被主键挡掉；下标 3 是空串；Anonymous 在下标 4。
    assert [(r["name"], r["ordinal"], r["raw_name"]) for r in rows] == [
        ("Evaan", 1, "  Evaan "),
        ("Anonymous", 4, "Anonymous"),
    ]
    # metadata 里的原始列表一字不改
    metadata = json.loads(
        conn.execute("SELECT metadata_json FROM resources").fetchone()["metadata_json"]
    )
    assert metadata["authors_raw"] == ["[Unknown]", "  Evaan ", "Evaan", "", "Anonymous"]


def test_card_without_authors_stores_nothing(env):
    conn, root, library = env
    write_card(root / "card.png", authors=None)
    LibraryScanner(conn).scan(library.id)

    assert conn.execute("SELECT count(*) AS c FROM authors").fetchone()["c"] == 0
    assert conn.execute("SELECT count(*) AS c FROM resource_authors").fetchone()["c"] == 0
    metadata = json.loads(
        conn.execute("SELECT metadata_json FROM resources").fetchone()["metadata_json"]
    )
    assert metadata["authors_raw"] == []


def test_broken_author_block_still_stores_the_card(env):
    conn, root, library = env
    write_card(
        root / "card.png",
        broken_authors=True,
        dependencies=(("com.example.mod", "outfit0.a", 0),),
    )
    result = LibraryScanner(conn).scan(library.id)

    assert result.stats.inserted == 1
    row = conn.execute("SELECT * FROM resources").fetchone()
    assert row["parse_status"] == "partial", "损坏的作者块只降级为 partial"
    assert row["name"] == "測試角色"
    assert conn.execute("SELECT count(*) AS c FROM authors").fetchone()["c"] == 0
    assert conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 1


def test_author_relations_rebuilt_not_duplicated(env):
    conn, root, library = env
    card = root / "card.png"
    write_card(card, authors=("[Unknown]", "Evaan", "Alice"))
    scanner = LibraryScanner(conn)
    scanner.scan(library.id)
    assert conn.execute("SELECT count(*) AS c FROM resource_authors").fetchone()["c"] == 2

    scanner.scan(library.id)  # 未变化 → skipped，关系不变
    assert conn.execute("SELECT count(*) AS c FROM resource_authors").fetchone()["c"] == 2

    write_card(card, authors=("[Unknown]", "Evaan"), lastname="新")  # 内容变化
    result = scanner.scan(library.id)
    assert result.stats.updated == 1
    rows = _author_rows(conn)
    assert [(r["name"], r["ordinal"]) for r in rows] == [("Evaan", 1)], "关系应被重建"
    assert conn.execute("SELECT count(*) AS c FROM authors").fetchone()["c"] == 2, (
        "Alice 的实体可以保留，但不再与该资源关联"
    )
