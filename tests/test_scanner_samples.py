"""Phase 1.2-C 验收：Scanner 跑在**真实样本**上（22 卡 + 13 zipmod）。

只读：直接扫描真实样本目录（不复制、不修改）；`sample_root` 夹具会在会话前后
比对全部文件 sha256。需要「修改 / 删除文件」的增量测试全部在**临时副本**里做。
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.scanner import LibraryScanner  # noqa: E402


@pytest.fixture()
def scanned(tmp_path: Path, sample_root: Path):
    """把真实样本目录扫进一个临时数据库，返回 (conn, library, 第一次结果, 第二次结果)。"""
    db_file = tmp_path / "samples.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    library = LibraryStore(conn).add(sample_root, name="真实样本")
    scanner = LibraryScanner(conn)
    first = scanner.scan(library.id)
    second = scanner.scan(library.id)
    yield conn, library, first, second
    conn.close()


def _norm(text: str) -> str:
    """统一比较用的路径分隔符（DB 里存的是 Windows 原生分隔符）。"""
    return text.replace("\\", "/")


def _resource_id(conn, relative_path: str) -> int:
    row = conn.execute(
        "SELECT id FROM resources WHERE replace(relative_path, '\\', '/') = ?",
        (_norm(relative_path),),
    ).fetchone()
    assert row is not None, f"没有入库：{relative_path}"
    return int(row["id"])


def _usage_rows(conn, resource_id: int):
    return conn.execute(
        "SELECT * FROM resource_mod_usages WHERE resource_id = ? ORDER BY property",
        (resource_id,),
    ).fetchall()


def _metadata(conn, resource_id: int) -> dict:
    row = conn.execute(
        "SELECT metadata_json FROM resources WHERE id = ?", (resource_id,)
    ).fetchone()
    return json.loads(row["metadata_json"])


# ---------------------------------------------------------------------------
# 首次 / 第二次扫描
# ---------------------------------------------------------------------------


def test_first_scan_inserts_everything(scanned):
    conn, _library, first, _second = scanned

    assert first.status == "completed"
    assert first.stats.discovered == 35, "22 张卡 + 13 个 zipmod"
    assert first.stats.parsed == 35
    assert first.stats.inserted == 35
    assert first.stats.updated == 0
    assert first.stats.skipped == 0
    assert first.stats.failed == 0, first.issues
    assert first.stats.not_a_resource == 0

    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 35
    assert conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"] == 13
    assert conn.execute("SELECT count(*) AS c FROM resource_plugins").fetchone()["c"] == 206
    assert conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 1527
    assert conn.execute("SELECT count(*) AS c FROM resource_mods").fetchone()["c"] == 315
    assert conn.execute("SELECT count(*) AS c FROM scan_records").fetchone()["c"] == 2


def test_second_scan_skips_everything(scanned):
    conn, _library, first, second = scanned

    assert second.stats.discovered == 35
    assert second.stats.parsed == 0, "第二次不得重新解析任何文件"
    assert second.stats.skipped == 35
    assert second.stats.inserted == 0
    assert second.stats.updated == 0
    assert second.stats.failed == 0

    # 第二次扫描后总量保持不变（scan_records 自然会多一条）
    assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 35
    assert conn.execute("SELECT count(*) AS c FROM resource_plugins").fetchone()["c"] == 206
    assert conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 1527
    assert conn.execute("SELECT count(*) AS c FROM resource_mods").fetchone()["c"] == 315
    assert conn.execute("SELECT count(*) AS c FROM mods").fetchone()["c"] == 13
    assert second.scan_record_id != first.scan_record_id


def test_resource_types_only_card_and_mod(scanned):
    conn, *_ = scanned
    types = {
        r["resource_type"]
        for r in conn.execute("SELECT resource_type FROM resources").fetchall()
    }
    assert types == {"character_card", "mod"}
    for forbidden in ("eyes", "skin", "hair", "accessory"):
        assert forbidden not in types


# ---------------------------------------------------------------------------
# B 组：dependency 记录 ↔ usage 行
# ---------------------------------------------------------------------------


def test_sayaka_four_usages_one_unique_mod(scanned):
    conn, *_ = scanned
    rid = _resource_id(conn, "B_带MOD角色卡/魔法少女小圆 - 美树沙耶香.png")

    usages = _usage_rows(conn, rid)
    assert len(usages) == 4
    assert len({u["mod_guid"] for u in usages}) == 1
    assert {u["mod_guid"] for u in usages} == {"com.Quokka.sisterveilb"}
    assert len({u["property"] for u in usages}) == 4, "4 个槽位一个都不能丢"

    summary = conn.execute(
        "SELECT * FROM resource_mods WHERE resource_id = ?", (rid,)
    ).fetchall()
    assert len(summary) == 1
    assert summary[0]["ref_count"] == 4


def test_kyoko_five_usages_three_unique_mods(scanned):
    conn, *_ = scanned
    rid = _resource_id(conn, "B_带MOD角色卡/魔法少女小圆 - 佐仓杏子.png")

    usages = _usage_rows(conn, rid)
    assert len(usages) == 5
    assert {u["mod_guid"] for u in usages} == {
        "com.Quokka.chinadresstop",
        "com.Quokka.crossstaff",
        "com.ymgpt.acc_earrings_top",
    }
    assert len(conn.execute(
        "SELECT * FROM resource_mods WHERE resource_id = ?", (rid,)
    ).fetchall()) == 3

    # 本地装了的两个 MOD 要回填 mod_id；缺失的那个必须为空
    by_guid = {
        r["mod_guid"]: r["mod_id"]
        for r in conn.execute(
            "SELECT mod_guid, mod_id FROM resource_mods WHERE resource_id = ?", (rid,)
        ).fetchall()
    }
    assert by_guid["com.Quokka.chinadresstop"] is not None
    assert by_guid["com.Quokka.crossstaff"] is not None
    assert by_guid["com.ymgpt.acc_earrings_top"] is None, "缺失 MOD 不能凭空建实体"


# ---------------------------------------------------------------------------
# C 组：眼睛 Property 原样保留（不做来源推断）
# ---------------------------------------------------------------------------


def test_ayame_eye_properties_are_stored(scanned):
    conn, *_ = scanned
    rid = _resource_id(conn, "C_自定义眼睛/没有黄段子的无聊世界 - 华城绫女.png")

    properties = {u["property"] for u in _usage_rows(conn, rid)}
    assert "ChaFileFace.eyelineUpId" in properties
    assert "ChaFileFace.Pupil1" in properties
    assert "ChaFileFace.Pupil2" in properties

    # 不产生任何 eyes-source 字段 / 类型
    columns = {
        r[1] for r in conn.execute("PRAGMA table_info(resources)").fetchall()
    }
    assert not any("eye" in c.lower() for c in columns)
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resources WHERE resource_type = 'eyes'"
        ).fetchone()["c"]
        == 0
    )


# ---------------------------------------------------------------------------
# D / E 组：metadata 与服装 Property
# ---------------------------------------------------------------------------


def test_cocoa_metadata_and_mods(scanned):
    conn, *_ = scanned
    rid = _resource_id(conn, "D_皮肤身体贴图/请问您今天要来点兔子吗 - 保登心爱.png")

    metadata = _metadata(conn, rid)
    assert metadata["embedded_texture_count"] == 7
    assert metadata["plugin_count"] == 4

    usages = _usage_rows(conn, rid)
    assert {u["mod_guid"] for u in usages} == {
        "com.Blanketman.AdditionalSkinMod",
        "com.Blanketman.NonLightStockings",
    }
    properties = {u["property"] for u in usages}
    assert "ChaFileBody.detailId" in properties


def test_clothing_properties_are_preserved(scanned):
    conn, *_ = scanned
    tomoe = _resource_id(conn, "E_角色加衣服MOD/青春猪头少年系列 - 古贺朋绘.png")
    shalltear = _resource_id(conn, "E_角色加衣服MOD/不死者之王 - 夏提雅 布拉德弗伦.png")

    assert [u["property"] for u in _usage_rows(conn, tomoe)] == [
        "outfit6.ChaFileClothes.ClothesTop"
    ]
    assert sorted(u["property"] for u in _usage_rows(conn, shalltear)) == [
        "outfit3.ChaFileClothes.ClothesBot",
        "outfit6.ChaFileClothes.ClothesBot",
    ]


# ---------------------------------------------------------------------------
# F 组：多作者（当前被 Parser 能力阻塞）
# ---------------------------------------------------------------------------


def test_group_f_authors_are_stored(scanned):
    conn, *_ = scanned
    rid = _resource_id(conn, "F_同作者多角色/Koikatu_F_20201023022200944_Hermione_Evaan.png")

    rows = conn.execute(
        "SELECT a.name, ra.ordinal, ra.raw_name FROM resource_authors ra"
        " JOIN authors a ON a.id = ra.author_id WHERE ra.resource_id = ?"
        " ORDER BY ra.ordinal",
        (rid,),
    ).fetchall()
    assert [r["name"] for r in rows] == ["Evaan"]
    assert rows[0]["raw_name"] == "Evaan"

    # `[Unknown]` 不能成为作者实体，但原始值要留在 metadata 里
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM authors WHERE name_key LIKE '%unknown%'"
        ).fetchone()["c"]
        == 0
    )
    assert _metadata(conn, rid)["authors_raw"] == ["[Unknown]", "Evaan"]


F_GROUP_CARDS = [
    "F_同作者多角色/Koikatu_F_20201023022200944_Hermione_Evaan.png",
    "F_同作者多角色/Koikatu_F_20230324192530956_Tatsumaki_Evaan.png",
    "F_同作者多角色/Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png",
]


def test_group_f_all_three_cards_link_to_evaan(scanned):
    conn, *_ = scanned
    for rel in F_GROUP_CARDS:
        rid = _resource_id(conn, rel)
        rows = conn.execute(
            "SELECT a.name, ra.ordinal, ra.raw_name FROM resource_authors ra"
            " JOIN authors a ON a.id = ra.author_id WHERE ra.resource_id = ?"
            " ORDER BY ra.ordinal",
            (rid,),
        ).fetchall()
        assert len(rows) == 1, f"{rel} 应当只有一个真实作者关联"
        assert rows[0]["name"] == "Evaan"
        # ordinal 是**原始列表下标**：raw = ['[Unknown]', 'Evaan'] → Evaan 在位 1
        assert rows[0]["ordinal"] == 1
        assert rows[0]["raw_name"] == "Evaan"
        assert _metadata(conn, rid)["authors_raw"] == ["[Unknown]", "Evaan"]


def test_unknown_sentinel_is_not_an_author_entity(scanned):
    conn, *_ = scanned
    names = {r["name"] for r in conn.execute("SELECT name FROM authors").fetchall()}
    assert names == {"Evaan", "Anonymous", "Azurou"}
    assert not any("unknown" in n.casefold() for n in names)
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM authors WHERE name_key LIKE '%unknown%'"
        ).fetchone()["c"]
        == 0
    )


def test_author_rows_are_not_duplicated_on_rescan(scanned):
    conn, _library, _first, second = scanned
    assert second.stats.skipped == 35
    # 会话夹具已经扫过两次
    assert (
        conn.execute("SELECT count(*) AS c FROM resource_authors").fetchone()["c"] == 14
    )
    assert conn.execute("SELECT count(*) AS c FROM authors").fetchone()["c"] == 3
    # 每个 (resource, author) 只出现一次
    duplicated = conn.execute(
        "SELECT resource_id, author_id, count(*) AS c FROM resource_authors"
        " GROUP BY resource_id, author_id HAVING c > 1"
    ).fetchall()
    assert duplicated == []


def test_author_relations_are_rebuilt_after_change(tmp_path: Path, sample_root: Path):
    lib_root = tmp_path / "library"
    lib_root.mkdir()
    source = (
        sample_root
        / "F_同作者多角色"
        / "Koikatu_F_20201023022200944_Hermione_Evaan.png"
    )
    copy = lib_root / "hermione.png"
    shutil.copyfile(source, copy)

    db_file = tmp_path / "authors.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        library = LibraryStore(conn).add(lib_root, name="副本库")
        scanner = LibraryScanner(conn)
        scanner.scan(library.id)
        assert (
            conn.execute("SELECT count(*) AS c FROM resource_authors").fetchone()["c"] == 1
        )

        copy.write_bytes(copy.read_bytes() + b"\x00")  # 内容变化
        result = scanner.scan(library.id)

        assert result.stats.updated == 1
        assert (
            conn.execute("SELECT count(*) AS c FROM resource_authors").fetchone()["c"] == 1
        ), "作者关系必须重建而不是累加"
        assert conn.execute("SELECT count(*) AS c FROM authors").fetchone()["c"] == 1
        row = conn.execute(
            "SELECT a.name, ra.raw_name FROM resource_authors ra"
            " JOIN authors a ON a.id = ra.author_id"
        ).fetchone()
        assert row["name"] == "Evaan"
        assert row["raw_name"] == "Evaan"
    finally:
        conn.close()


def test_cards_without_authors_have_no_author_rows(scanned):
    conn, *_ = scanned
    rid = _resource_id(conn, "A_普通角色卡_无MOD/魔法少女小圆 - 鹿目圆.png")
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resource_authors WHERE resource_id = ?", (rid,)
        ).fetchone()["c"]
        == 0
    )
    assert _metadata(conn, rid)["authors_raw"] == []


def test_author_ordinal_follows_raw_position(scanned):
    """ordinal 必须等于「在 authors_raw 里的下标」，而不是过滤后的序号。"""
    conn, *_ = scanned
    cases = {
        "F_同作者多角色/Koikatu_F_20201023022200944_Hermione_Evaan.png": [
            ("Evaan", 1)  # raw = ['[Unknown]', 'Evaan']
        ],
        "H_共享MOD多角色/明日方舟 - 红豆.png": [("Anonymous", 1)],
        "I_文件名混乱重名/同名不同时间戳/KoikatsuSun_F_20260905140632481_Higashiyama Kobeni.png": [
            ("Azurou", 0),  # raw = ['Azurou', 'Anonymous']
            ("Anonymous", 1),
        ],
        "I_文件名混乱重名/混乱命名/KK_317794.png": [("Azurou", 0)],  # raw = ['Azurou']
        "J_复杂完整角色/刀剑神域 - 绀野木棉季.png": [
            ("Anonymous", 0)  # raw = ['Anonymous']（没有哨兵）
        ],
    }
    for rel, expected in cases.items():
        rid = _resource_id(conn, rel)
        rows = conn.execute(
            "SELECT a.name, ra.ordinal FROM resource_authors ra"
            " JOIN authors a ON a.id = ra.author_id"
            " WHERE ra.resource_id = ? ORDER BY ra.ordinal",
            (rid,),
        ).fetchall()
        assert [(r["name"], r["ordinal"]) for r in rows] == expected, rel


def test_db_authors_match_parser_authors(scanned):
    """数据库中建立作者实体的集合，必须与 Parser 的 authors 完全一致。"""
    conn, _library, *_ = scanned
    from core.parsers import parse_card

    expected: set[str] = set()
    for path in sample_root_cards(conn):
        expected.update(parse_card(path).authors)
    stored = {r["name"] for r in conn.execute("SELECT name FROM authors").fetchall()}
    assert stored == expected == {"Evaan", "Anonymous", "Azurou"}


def sample_root_cards(conn):
    """从库里取出所有卡片的绝对路径（避免再次依赖 sample_root 夹具）。"""
    rows = conn.execute(
        "SELECT file_path FROM resources WHERE resource_type = 'character_card'"
    ).fetchall()
    from pathlib import Path as _Path

    return [_Path(r["file_path"]) for r in rows]


def test_author_invariant_ref_count_matches_usages(scanned):
    """作者功能不能破坏 1.2-C 的不变式：ref_count == usage 行数。"""
    conn, *_ = scanned
    mismatched = conn.execute(
        "SELECT rm.resource_id, rm.mod_guid, rm.ref_count,"
        " (SELECT count(*) FROM resource_mod_usages u"
        "  WHERE u.resource_id = rm.resource_id AND u.mod_guid = rm.mod_guid) AS actual"
        " FROM resource_mods rm"
    ).fetchall()
    assert mismatched, "应当有数据可供校验"
    bad = [
        dict(r) for r in mismatched if r["ref_count"] != r["actual"]
    ]
    assert bad == []


# ---------------------------------------------------------------------------
# G 组：孤立 MOD
# ---------------------------------------------------------------------------


def test_orphan_mods_are_stored_without_relations(scanned):
    conn, *_ = scanned
    for rel, guid in (
        ("G_孤立MOD_无角色卡/MOD/NoHair.zipmod", "NoHair"),
        ("G_孤立MOD_无角色卡/MOD/[ucklline] Elven Panst.zipmod", "elven_panst"),
        (
            "G_孤立MOD_无角色卡/MOD/[Unknown] koikatu.AltSlot.co_bot_19.zipmod",
            "koikatu.AltSlot.co_bot_19",
        ),
    ):
        rid = _resource_id(conn, rel)
        mod = conn.execute("SELECT * FROM mods WHERE guid = ?", (guid,)).fetchone()
        assert mod is not None
        assert mod["resource_id"] == rid
        assert (
            conn.execute(
                "SELECT count(*) AS c FROM resource_mods WHERE mod_guid = ?", (guid,)
            ).fetchone()["c"]
            == 0
        ), f"{guid} 应当是孤立 MOD"


def test_nohair_abnormal_values_are_stored(scanned):
    conn, *_ = scanned
    mod = conn.execute("SELECT * FROM mods WHERE guid = 'NoHair'").fetchone()
    assert mod["author"] == ""
    assert mod["version"] == "0"


# ---------------------------------------------------------------------------
# H 组：共享 MOD 反向查询
# ---------------------------------------------------------------------------


def test_shared_naginata_reachable_from_both_cards(scanned):
    conn, *_ = scanned
    hongdou = _resource_id(conn, "H_共享MOD多角色/明日方舟 - 红豆.png")
    nagao = _resource_id(conn, "H_共享MOD多角色/FATE - 长尾景虎.png")

    used_by = {
        r["resource_id"]
        for r in conn.execute(
            "SELECT DISTINCT resource_id FROM resource_mod_usages WHERE mod_guid = ?",
            ("com.Quokka.naginata",),
        ).fetchall()
    }
    assert used_by == {hongdou, nagao}

    # 两张卡使用它的槽位不同
    props_hongdou = {
        u["property"] for u in _usage_rows(conn, hongdou) if u["mod_guid"] == "com.Quokka.naginata"
    }
    props_nagao = {
        u["property"] for u in _usage_rows(conn, nagao) if u["mod_guid"] == "com.Quokka.naginata"
    }
    assert props_hongdou and props_nagao and props_hongdou != props_nagao

    mod_id = conn.execute(
        "SELECT id FROM mods WHERE guid = 'com.Quokka.naginata'"
    ).fetchone()["id"]
    assert {
        r["mod_id"]
        for r in conn.execute(
            "SELECT mod_id FROM resource_mods WHERE mod_guid = 'com.Quokka.naginata'"
        ).fetchall()
    } == {mod_id}


# ---------------------------------------------------------------------------
# I 组：重名 / 同内容 / KK vs KKS
# ---------------------------------------------------------------------------


def test_two_kugisaki_keep_their_own_markers(scanned):
    conn, *_ = scanned
    sun = conn.execute(
        "SELECT * FROM resources WHERE replace(relative_path, '\\', '/')"
        " LIKE '%同名不同目录/female/Koikatu_F_20240209185711407%'"
    ).fetchone()
    kk = conn.execute(
        "SELECT * FROM resources WHERE replace(relative_path, '\\', '/')"
        " LIKE '%old_female%'"
    ).fetchone()

    assert sun["card_marker"] == "KoiKatuCharaSun"
    assert kk["card_marker"] == "KoiKatuChara"
    assert sun["card_marker"] != kk["card_marker"]
    # KK 卡没有 About → metadata 里是 null，且不算失败
    assert kk["parse_status"] == "ok"
    assert _metadata(conn, int(kk["id"]))["data_id"] is None
    assert _metadata(conn, int(sun["id"]))["data_id"] is not None


def test_identical_kugisaki_files_are_both_kept(scanned):
    """两份 sha256 完全相同的 Kugisaki：两个路径都要保留。"""
    conn, *_ = scanned
    rows = conn.execute(
        "SELECT id, relative_path FROM resources WHERE relative_path LIKE '%Kugisaki Nobara%'"
    ).fetchall()
    paths = {_norm(r["relative_path"]) for r in rows}
    assert len(paths) == 3, "F 组 + I 组两份，路径各不相同"
    assert sum(1 for p in paths if "同名不同目录/female" in p) == 1
    assert sum(1 for p in paths if "old_female" in p) == 1


def test_kobeni_data_id_is_not_identity(scanned):
    conn, *_ = scanned
    rows = conn.execute(
        "SELECT id, relative_path, metadata_json FROM resources"
        " WHERE relative_path LIKE '%Higashiyama Kobeni%' ORDER BY relative_path"
    ).fetchall()
    assert len(rows) == 2
    data_ids = [json.loads(r["metadata_json"])["data_id"] for r in rows]
    assert len(set(data_ids)) == 2, "两张卡的 dataID 不同"
    assert len({r["relative_path"] for r in rows}) == 2
    # 两张卡都在库里，且各自有自己的 usage 行
    for row in rows:
        assert _usage_rows(conn, int(row["id"])), "近似文件不能互相覆盖关系"


def test_kk317794_same_character_different_card(scanned):
    """同角色 HigashiyamaKobeni 有 3 张不同的卡 —— 三行都要在。"""
    conn, *_ = scanned
    rows = conn.execute(
        "SELECT id, name FROM resources WHERE name = 'HigashiyamaKobeni'"
    ).fetchall()
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# J 组：高复杂度
# ---------------------------------------------------------------------------


def test_yuuki_high_complexity_counts(scanned):
    conn, *_ = scanned
    rid = _resource_id(conn, "J_复杂完整角色/刀剑神域 - 绀野木棉季.png")

    usages = _usage_rows(conn, rid)
    assert len(usages) == 220, "220 条 dependency 记录不能因去重丢失"
    assert len({u["mod_guid"] for u in usages}) == 31
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resource_plugins WHERE resource_id = ?", (rid,)
        ).fetchone()["c"]
        == 21
    )
    assert _metadata(conn, rid)["embedded_texture_count"] == 120
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resource_mods WHERE resource_id = ?", (rid,)
        ).fetchone()["c"]
        == 31
    )


# ---------------------------------------------------------------------------
# 增量：修改 / 删除（在临时副本上做，真实样本不动）
# ---------------------------------------------------------------------------


def test_incremental_with_real_copies(tmp_path: Path, sample_root: Path):
    lib_root = tmp_path / "library"
    lib_root.mkdir()
    source = sample_root / "A_普通角色卡_无MOD" / "碧蓝航线 - 罗德尼.png"
    copy = lib_root / "rodney.png"
    shutil.copyfile(source, copy)

    db_file = tmp_path / "inc.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        library = LibraryStore(conn).add(lib_root, name="副本库")
        scanner = LibraryScanner(conn)

        first = scanner.scan(library.id)
        assert first.stats.inserted == 1

        second = scanner.scan(library.id)
        assert second.stats.skipped == 1
        assert second.stats.parsed == 0

        # 改动副本（追加一个字节 → size 变化）
        copy.write_bytes(copy.read_bytes() + b"\x00")
        third = scanner.scan(library.id)
        assert third.stats.updated == 1
        assert third.stats.inserted == 0
        assert third.stats.parsed == 1
        assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 1
        assert (
            conn.execute("SELECT file_size FROM resources").fetchone()["file_size"]
            == copy.stat().st_size
        )

        # 删除副本
        copy.unlink()
        fourth = scanner.scan(library.id)
        assert fourth.stats.missing == 1
        assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 1
        assert (
            conn.execute("SELECT scan_status FROM resources").fetchone()["scan_status"]
            == "missing"
        )
    finally:
        conn.close()


def test_changed_card_relations_are_rebuilt(tmp_path: Path, sample_root: Path):
    """改动内容 → 关系被重建而不是累加。"""
    lib_root = tmp_path / "library"
    lib_root.mkdir()
    source = sample_root / "B_带MOD角色卡" / "魔法少女小圆 - 美树沙耶香.png"
    copy = lib_root / "sayaka.png"
    shutil.copyfile(source, copy)

    db_file = tmp_path / "changed.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        library = LibraryStore(conn).add(lib_root, name="副本库")
        scanner = LibraryScanner(conn)
        scanner.scan(library.id)
        assert conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 4

        copy.write_bytes(copy.read_bytes() + b"\x00")
        result = scanner.scan(library.id)

        assert result.stats.updated == 1
        assert conn.execute("SELECT count(*) AS c FROM resources").fetchone()["c"] == 1
        assert (
            conn.execute("SELECT count(*) AS c FROM resource_mod_usages").fetchone()["c"] == 4
        ), "重扫必须替换关系，不能累加"
        assert (
            conn.execute("SELECT count(*) AS c FROM resource_mods").fetchone()["c"] == 1
        )
    finally:
        conn.close()
