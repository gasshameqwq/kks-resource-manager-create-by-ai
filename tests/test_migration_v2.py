"""Phase 1.2-A 验收：Schema v2 迁移。

验收目标（来自真实样本分析的结论，见 docs/phase1/SAMPLE_ANALYSIS.md）：

1. `resources.card_marker` 正式承载卡片格式（KoiKatuCharaSun / KoiKatuChara）；
2. `resource_plugins` 承载 KKEx 插件（**不是** MOD）；
3. `resource_mod_usages` 承载卡片 → MOD 的**逐槽位**使用关系；
4. `resource_authors` 支持多作者；
5. `metadata_json` 约定键（data_id / user_id / embedded_texture_count …）；
6. `dataID` 不做身份键；
7. `skin/eyes/hair/accessory` 不作为 PNG 文件类型；
8. **旧库可升级、v1 数据不丢**。

旧库是通过「只应用 v1 迁移」真实造出来的，不是手工建表 —— 这样才真的检验 ALTER。
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.database import schema as schema_mod  # noqa: E402
from core.models import (  # noqa: E402
    AUTO_DETECTABLE_TYPES,
    UNKNOWN_AUTHOR_SENTINEL,
    is_placeholder_author,
    partition_authors,
)


@pytest.fixture()
def db_file(tmp_path: Path) -> Path:
    return tmp_path / "migration.db"


def _create_v1_database(path: Path) -> None:
    """只跑 v1 迁移，造出一个真实的 1.x 老库。"""
    v1_only = {1: schema_mod.MIGRATIONS[1]}
    original = schema_mod.MIGRATIONS
    schema_mod.MIGRATIONS = v1_only  # type: ignore[assignment]
    try:
        database.initialize(path)
    finally:
        schema_mod.MIGRATIONS = original  # type: ignore[assignment]

    conn = database.connect(path)
    try:
        assert database.schema_version(conn) == 1
        assert "card_marker" not in database.column_names(conn, "resources")
    finally:
        conn.close()


def _seed_v1_data(path: Path) -> dict:
    """往老库里塞一份完整的 v1 数据，升级后逐项比对。"""
    conn = database.connect(path)
    try:
        with database.transaction(conn):
            lib_id = conn.execute(
                "INSERT INTO libraries(name, root_path, root_path_key, notes)"
                " VALUES ('主卡库', 'D:/KKS/Cards', 'd:/kks/cards', '重要')"
            ).lastrowid
            author_id = conn.execute(
                "INSERT INTO authors(name, name_key) VALUES ('Evaan', 'evaan')"
            ).lastrowid
            tag_id = conn.execute(
                "INSERT INTO tags(name, name_key) VALUES ('收藏', '收藏')"
            ).lastrowid
            col_id = conn.execute(
                "INSERT INTO collections(name, name_key) VALUES ('系列A', '系列a')"
            ).lastrowid
            res_id = conn.execute(
                "INSERT INTO resources(file_path, file_path_key, resource_type,"
                " display_name, name, library_id, author, author_id, file_size,"
                " needs_review) VALUES ('D:/KKS/Cards/a.png','d:/kks/cards/a.png',"
                " 'character_card','旧卡','旧卡', ?, 'Evaan', ?, 12345, 1)",
                (lib_id, author_id),
            ).lastrowid
            conn.execute(
                "INSERT INTO resource_tags(resource_id, tag_id, origin)"
                " VALUES (?, ?, 'user')",
                (res_id, tag_id),
            )
            conn.execute(
                "INSERT INTO resource_collections(resource_id, collection_id)"
                " VALUES (?, ?)",
                (res_id, col_id),
            )
            conn.execute(
                "INSERT INTO resource_mods(resource_id, mod_guid, mod_id, ref_count)"
                " VALUES (?, 'com.example.missing', NULL, 3)",
                (res_id,),
            )
            conn.execute(
                "INSERT INTO scan_records(library_id, status, files_seen, files_new)"
                " VALUES (?, 'completed', 10, 4)",
                (lib_id,),
            )
        return {
            "library_id": lib_id,
            "author_id": author_id,
            "tag_id": tag_id,
            "collection_id": col_id,
            "resource_id": res_id,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 版本与结构
# ---------------------------------------------------------------------------


def test_schema_version_is_2():
    assert schema_mod.SCHEMA_VERSION == 2
    assert set(schema_mod.MIGRATIONS) == {1, 2}
    # v1 的历史 DDL 不允许被改动
    assert schema_mod.MIGRATIONS[1] == (schema_mod._V1_SQL, schema_mod._V1_FTS_SQL)


def test_fresh_database_is_created_at_v2(db_file: Path):
    info = database.initialize(db_file)
    assert info["schema_version"] == 2
    assert info["applied_migrations"] == [1, 2]
    for table in schema_mod.CURRENT_TABLES:
        assert table in info["tables"], f"缺少数据表：{table}"


def test_v1_tables_are_untouched(db_file: Path):
    """v2 只新增，不改写 v1 的表结构（除新增列）。"""
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        for table in schema_mod.V1_TABLES:
            assert database.column_names(conn, table), f"v1 表被破坏：{table}"
    finally:
        conn.close()


def test_card_marker_column_exists(db_file: Path):
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        assert "card_marker" in database.column_names(conn, "resources")
    finally:
        conn.close()


def test_v2_tables_exist(db_file: Path):
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        names = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for table in schema_mod.V2_TABLES:
            assert table in names
    finally:
        conn.close()


def test_expected_indexes_exist(db_file: Path):
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        indexes = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
    finally:
        conn.close()
    for name in (
        "idx_resources_card_marker",
        "idx_resource_plugins_guid",
        "idx_resource_mod_usages_guid",
        "idx_resource_mod_usages_resource",
        "idx_resource_mod_usages_property",
        "idx_resource_authors_author",
    ):
        assert name in indexes, f"缺少索引：{name}"


# ---------------------------------------------------------------------------
# 旧库升级
# ---------------------------------------------------------------------------


def test_v1_database_upgrades_to_v2(db_file: Path):
    _create_v1_database(db_file)

    info = database.initialize(db_file)

    assert info["schema_version"] == 2
    assert info["applied_migrations"] == [2], "只应补跑 v2，不该重跑 v1"
    conn = database.connect(db_file)
    try:
        assert "card_marker" in database.column_names(conn, "resources")
    finally:
        conn.close()


def test_upgrade_preserves_all_v1_data(db_file: Path):
    _create_v1_database(db_file)
    ids = _seed_v1_data(db_file)

    database.initialize(db_file)  # 升级

    conn = database.connect(db_file)
    try:
        lib = conn.execute(
            "SELECT * FROM libraries WHERE id = ?", (ids["library_id"],)
        ).fetchone()
        assert lib["name"] == "主卡库"
        assert lib["root_path"] == "D:/KKS/Cards"
        assert lib["notes"] == "重要"

        res = conn.execute(
            "SELECT * FROM resources WHERE id = ?", (ids["resource_id"],)
        ).fetchone()
        assert res["display_name"] == "旧卡"
        assert res["file_size"] == 12345
        assert res["needs_review"] == 1
        assert res["library_id"] == ids["library_id"]
        assert res["author_id"] == ids["author_id"]
        assert res["card_marker"] is None, "新列对老数据应为 NULL，不能编造值"

        assert conn.execute("SELECT count(*) AS c FROM authors").fetchone()["c"] == 1
        assert conn.execute("SELECT count(*) AS c FROM tags").fetchone()["c"] == 1
        assert conn.execute("SELECT count(*) AS c FROM collections").fetchone()["c"] == 1
        assert conn.execute("SELECT count(*) AS c FROM resource_tags").fetchone()["c"] == 1
        assert (
            conn.execute("SELECT count(*) AS c FROM resource_collections").fetchone()["c"]
            == 1
        )
        assert conn.execute("SELECT count(*) AS c FROM resource_mods").fetchone()["c"] == 1
        assert conn.execute("SELECT count(*) AS c FROM scan_records").fetchone()["c"] == 1

        dependency = conn.execute(
            "SELECT mod_guid, mod_id, ref_count FROM resource_mods"
        ).fetchone()
        assert dependency["mod_guid"] == "com.example.missing"
        assert dependency["mod_id"] is None
        assert dependency["ref_count"] == 3
    finally:
        conn.close()


def test_upgrade_is_idempotent(db_file: Path):
    _create_v1_database(db_file)
    _seed_v1_data(db_file)

    first = database.initialize(db_file)
    second = database.initialize(db_file)

    assert first["applied_migrations"] == [2]
    assert second["applied_migrations"] == []
    assert second["schema_version"] == 2


def test_upgrade_via_forced_rerun_of_add_column_is_safe(db_file: Path):
    """即使 v2 被重跑（例如手工把 schema_version 改回 1），加列也不能报错。"""
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        conn.execute("UPDATE app_meta SET value = '1' WHERE key = 'schema_version'")
        assert database.schema_version(conn) == 1
    finally:
        conn.close()

    info = database.initialize(db_file)  # 会再跑一次 v2

    assert info["schema_version"] == 2
    assert info["applied_migrations"] == [2]
    conn = database.connect(db_file)
    try:
        assert "card_marker" in database.column_names(conn, "resources")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# v2 新增表的行为
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded(db_file: Path):
    database.initialize(db_file)
    conn = database.connect(db_file)
    cur = conn.execute(
        "INSERT INTO resources(file_path, file_path_key, resource_type, card_marker)"
        " VALUES ('D:/card.png', 'd:/card.png', 'character_card', 'KoiKatuCharaSun')"
    )
    resource_id = int(cur.lastrowid)
    yield conn, resource_id
    conn.close()


def test_card_marker_roundtrip(seeded):
    conn, resource_id = seeded
    row = conn.execute(
        "SELECT card_marker FROM resources WHERE id = ?", (resource_id,)
    ).fetchone()
    assert row["card_marker"] == "KoiKatuCharaSun"

    # KK / KKS 两种格式可以共存
    conn.execute(
        "INSERT INTO resources(file_path, file_path_key, resource_type, card_marker)"
        " VALUES ('D:/old.png', 'd:/old.png', 'character_card', 'KoiKatuChara')"
    )
    markers = [
        r["card_marker"]
        for r in conn.execute("SELECT card_marker FROM resources ORDER BY id").fetchall()
    ]
    assert markers == ["KoiKatuCharaSun", "KoiKatuChara"]


def test_plugins_are_separate_from_mods(seeded):
    conn, resource_id = seeded
    for guid in ("moreAccessories", "KSOX", "marco.authordata"):
        conn.execute(
            "INSERT INTO resource_plugins(resource_id, plugin_guid) VALUES (?, ?)",
            (resource_id, guid),
        )

    count = conn.execute(
        "SELECT count(*) AS c FROM resource_plugins WHERE resource_id = ?",
        (resource_id,),
    ).fetchone()["c"]
    assert count == 3

    # 插件绝不能污染 mods / resource_mods
    assert conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"] == 0
    assert conn.execute("SELECT count(*) AS c FROM resource_mods").fetchone()["c"] == 0

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO resource_plugins(resource_id, plugin_guid) VALUES (?, ?)",
            (resource_id, "KSOX"),
        )


def test_plugins_cascade_on_resource_delete(seeded):
    conn, resource_id = seeded
    conn.execute(
        "INSERT INTO resource_plugins(resource_id, plugin_guid) VALUES (?, 'KSOX')",
        (resource_id,),
    )
    conn.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
    assert conn.execute("SELECT count(*) AS c FROM resource_plugins").fetchone()["c"] == 0


def test_mod_usages_keep_every_slot(seeded):
    """同一个 MOD 用在 4 个槽位 → 4 行，槽位信息一条都不能丢。"""
    conn, resource_id = seeded
    rows = [
        ("com.Quokka.sisterveilb", "outfit6.accessory10.ChaFileAccessory.PartsInfo.id", 10),
        ("com.Quokka.sisterveilb", "outfit6.accessory11.ChaFileAccessory.PartsInfo.id", 11),
        ("com.Quokka.sisterveilb", "outfit6.accessory12.ChaFileAccessory.PartsInfo.id", 12),
        ("com.Quokka.sisterveilb", "outfit2.accessory1.ChaFileAccessory.PartsInfo.id", 1),
    ]
    for guid, prop, slot in rows:
        conn.execute(
            "INSERT INTO resource_mod_usages(resource_id, mod_guid, property, slot,"
            " local_slot, category_no) VALUES (?, ?, ?, ?, ?, ?)",
            (resource_id, guid, prop, slot, 987654321, 0),
        )

    assert (
        conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 4
    )
    unique_mods = conn.execute(
        "SELECT count(DISTINCT mod_guid) AS c FROM resource_mod_usages"
    ).fetchone()["c"]
    assert unique_mods == 1, "4 条记录只对应 1 个唯一 MOD"
    assert (
        conn.execute("SELECT count(DISTINCT property) AS c FROM resource_mod_usages")
        .fetchone()["c"]
        == 4
    )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO resource_mod_usages(resource_id, mod_guid, property)"
            " VALUES (?, 'com.Quokka.sisterveilb',"
            " 'outfit6.accessory10.ChaFileAccessory.PartsInfo.id')",
            (resource_id,),
        )


def test_mod_usages_allow_null_slot_fields(seeded):
    conn, resource_id = seeded
    conn.execute(
        "INSERT INTO resource_mod_usages(resource_id, mod_guid, property)"
        " VALUES (?, 'com.gf.collection', 'ChaFileFace.Pupil1')",
        (resource_id,),
    )
    row = conn.execute(
        "SELECT slot, local_slot, category_no FROM resource_mod_usages"
    ).fetchone()
    assert row["slot"] is None
    assert row["local_slot"] is None
    assert row["category_no"] is None


def test_mod_usages_allow_missing_local_mod(seeded):
    """缺失依赖：本地没有 mods 行，关系照样成立。"""
    conn, resource_id = seeded
    conn.execute(
        "INSERT INTO resource_mod_usages(resource_id, mod_guid, property)"
        " VALUES (?, 'com.ymgpt.acc_earrings_top', 'outfit6.accessory10.ChaFileAccessory.PartsInfo.id')",
        (resource_id,),
    )
    assert conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"] == 0
    assert (
        conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 1
    )


def test_mod_usages_reverse_lookup_across_resources(db_file: Path):
    """同一个 MOD 被两张卡使用 → 反向查询能列出两张卡。"""
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        ids = []
        for i in (1, 2):
            ids.append(
                int(
                    conn.execute(
                        "INSERT INTO resources(file_path, file_path_key, resource_type)"
                        f" VALUES ('D:/c{i}.png', 'd:/c{i}.png', 'character_card')"
                    ).lastrowid
                )
            )
        conn.execute(
            "INSERT INTO resource_mod_usages(resource_id, mod_guid, property)"
            " VALUES (?, 'com.Quokka.naginata', 'outfit0.accessory4.ChaFileAccessory.PartsInfo.id')",
            (ids[0],),
        )
        conn.execute(
            "INSERT INTO resource_mod_usages(resource_id, mod_guid, property)"
            " VALUES (?, 'com.Quokka.naginata', 'outfit4.accessory56.ChaFileAccessory.PartsInfo.id')",
            (ids[1],),
        )
        used_by = [
            r["resource_id"]
            for r in conn.execute(
                "SELECT DISTINCT resource_id FROM resource_mod_usages"
                " WHERE mod_guid = 'com.Quokka.naginata' ORDER BY resource_id"
            ).fetchall()
        ]
        assert used_by == ids
    finally:
        conn.close()


def test_mod_usages_cascade_on_resource_delete(seeded):
    conn, resource_id = seeded
    conn.execute(
        "INSERT INTO resource_mod_usages(resource_id, mod_guid, property)"
        " VALUES (?, 'com.gf.collection', 'ChaFileFace.Pupil1')",
        (resource_id,),
    )
    conn.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
    assert (
        conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 0
    )


def test_resource_authors_supports_multiple_authors(seeded):
    conn, resource_id = seeded
    evaan = int(
        conn.execute(
            "INSERT INTO authors(name, name_key) VALUES ('Evaan','evaan')"
        ).lastrowid
    )
    anonymous = int(
        conn.execute(
            "INSERT INTO authors(name, name_key) VALUES ('Anonymous','anonymous')"
        ).lastrowid
    )
    conn.execute(
        "INSERT INTO resource_authors(resource_id, author_id, ordinal, raw_name)"
        " VALUES (?, ?, 0, 'Evaan')",
        (resource_id, evaan),
    )
    conn.execute(
        "INSERT INTO resource_authors(resource_id, author_id, ordinal, raw_name)"
        " VALUES (?, ?, 1, 'anonymous')",
        (resource_id, anonymous),
    )

    rows = conn.execute(
        "SELECT a.name, ra.ordinal, ra.raw_name FROM resource_authors ra"
        " JOIN authors a ON a.id = ra.author_id"
        " WHERE ra.resource_id = ? ORDER BY ra.ordinal",
        (resource_id,),
    ).fetchall()
    assert [(r["name"], r["raw_name"]) for r in rows] == [
        ("Evaan", "Evaan"),
        ("Anonymous", "anonymous"),
    ]


def test_data_id_is_not_an_identity_key(seeded):
    """dataID 只作为元数据；两张卡可以有相同 dataID。"""
    conn, resource_id = seeded
    conn.execute(
        "UPDATE resources SET metadata_json = ? WHERE id = ?",
        ('{"data_id": "07ee7d46-559c-47c4-a2d2-8974ab43ecec"}', resource_id),
    )
    other = int(
        conn.execute(
            "INSERT INTO resources(file_path, file_path_key, resource_type, metadata_json)"
            " VALUES ('D:/twin.png','d:/twin.png','character_card',"
            ' \'{"data_id": "07ee7d46-559c-47c4-a2d2-8974ab43ecec"}\')'
        ).lastrowid
    )
    assert other != resource_id
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resources WHERE metadata_json LIKE '%07ee7d46%'"
        ).fetchone()["c"]
        == 2
    )


def test_metadata_json_convention_keys_are_documented():
    for key in (
        "user_id",
        "data_id",
        "embedded_texture_count",
        "plugin_count",
        "authors_raw",
    ):
        assert key in schema_mod.RESOURCE_METADATA_KEYS


# ---------------------------------------------------------------------------
# 类型与作者规则
# ---------------------------------------------------------------------------


def test_auto_detectable_types_exclude_fine_grained_art_types():
    """眼睛/皮肤/头发/配饰来自 Property 语义，不能作为 PNG 文件类型自动写入。"""
    for forbidden in ("skin", "eyes", "hair", "accessory"):
        assert forbidden not in AUTO_DETECTABLE_TYPES


def test_partition_authors_keeps_placeholder_out_of_aggregation():
    real, placeholders, raw = partition_authors(["[Unknown]", "Evaan"])
    assert real == ["Evaan"]
    assert placeholders == ["[Unknown]"]
    assert raw == ["[Unknown]", "Evaan"], "原始值不能丢"


def test_partition_authors_dedupes_and_strips():
    real, placeholders, raw = partition_authors(["  Evaan ", "Evaan", "", "Anonymous"])
    assert real == ["Evaan", "Anonymous"]
    assert placeholders == []
    assert raw == ["  Evaan ", "Evaan", "", "Anonymous"]


def test_partition_authors_handles_only_placeholders():
    real, placeholders, raw = partition_authors(["[Unknown]"])
    assert real == []
    assert placeholders == ["[Unknown]"]
    assert raw == ["[Unknown]"]


def test_is_placeholder_author_is_case_insensitive():
    assert is_placeholder_author("[Unknown]")
    assert is_placeholder_author("  [unknown]  ")
    assert not is_placeholder_author("Anonymous")
    assert not is_placeholder_author("")
    assert UNKNOWN_AUTHOR_SENTINEL == "[Unknown]"


def test_columns_exist_even_for_fresh_v2_database(db_file: Path):
    """fresh 库走的是「先 v1 建表、再 v2 加列」的路径，结果必须一致。"""
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        for table, column in (
            ("resources", "card_marker"),
            ("resource_plugins", "plugin_guid"),
            ("resource_mod_usages", "property"),
            ("resource_authors", "raw_name"),
        ):
            assert column in database.column_names(conn, table)
    finally:
        conn.close()
