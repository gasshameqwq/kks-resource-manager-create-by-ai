"""Phase 1.2-B 验收：Character Card Parser（**真实样本**）。

样本集：22 张卡片，覆盖 A–J 十组。期望值来自 docs/phase1/SAMPLE_ANALYSIS.md 的实测结论，
并且与用户提供的 Ground Truth（`00_样本清单.md`）逐项吻合。

只读：解析器不做任何写入；`sample_root` 夹具会在会话前后比对全部文件 sha256。
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.parsers import (  # noqa: E402
    CharacterCardParseResult,
    ModDependencyRecord,
    parse_card,
)

MARKER_SUN = "KoiKatuCharaSun"
MARKER_KK = "KoiKatuChara"

# (相对路径, 角色名, marker, 插件数, 唯一MOD, 内嵌PNG, 依赖记录数)
CARD_EXPECTATIONS = [
    # --- A 组：普通角色卡，无 MOD ---
    ("A_普通角色卡_无MOD/碧蓝航线 - 罗德尼.png", "HMSRodney", MARKER_SUN, 1, 0, 0, 0),
    ("A_普通角色卡_无MOD/魔法少女小圆 - 鹿目圆.png", "鹿目まどか", MARKER_SUN, 2, 0, 0, 0),
    # --- B 组：带 MOD 角色卡 ---
    ("B_带MOD角色卡/魔法少女小圆 - 美树沙耶香.png", "美樹さやか", MARKER_SUN, 2, 1, 0, 4),
    ("B_带MOD角色卡/魔法少女小圆 - 佐仓杏子.png", "佐倉杏子", MARKER_SUN, 2, 3, 0, 5),
    # --- C 组：自定义眼睛 ---
    ("C_自定义眼睛/没有黄段子的无聊世界 - 华城绫女.png", "KajoAyame", MARKER_SUN, 2, 1, 0, 3),
    ("C_自定义眼睛/天结堡主 - 岚燐结骑.png", "嵐燐結騎", MARKER_SUN, 2, 1, 0, 13),
    # --- D 组：皮肤 / 身体贴图 ---
    ("D_皮肤身体贴图/政宗君的复仇 - 安达垣爱姬.png", "安達垣愛姫", MARKER_SUN, 2, 1, 0, 1),
    ("D_皮肤身体贴图/请问您今天要来点兔子吗 - 保登心爱.png", "保登心愛", MARKER_SUN, 4, 2, 7, 2),
    # --- E 组：角色 + 衣服 MOD ---
    ("E_角色加衣服MOD/青春猪头少年系列 - 古贺朋绘.png", "古賀朋絵", MARKER_SUN, 2, 1, 0, 1),
    (
        "E_角色加衣服MOD/不死者之王 - 夏提雅 布拉德弗伦.png",
        "夏提雅·布拉德弗伦",
        MARKER_SUN,
        3,
        1,
        0,
        2,
    ),
    # --- F 组：同作者多角色 ---
    (
        "F_同作者多角色/Koikatu_F_20201023022200944_Hermione_Evaan.png",
        "GrangerHermione",
        MARKER_SUN,
        17,
        20,
        10,
        136,
    ),
    (
        "F_同作者多角色/Koikatu_F_20230324192530956_Tatsumaki_Evaan.png",
        "Tatsumaki",
        MARKER_SUN,
        19,
        19,
        10,
        31,
    ),
    (
        "F_同作者多角色/Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png",
        "KugisakiNobara",
        MARKER_SUN,
        18,
        13,
        17,
        30,
    ),
    # --- H 组：共享 MOD 的多角色 ---
    ("H_共享MOD多角色/明日方舟 - 红豆.png", "新倉ようこ", MARKER_SUN, 10, 26, 1, 112),
    ("H_共享MOD多角色/FATE - 长尾景虎.png", "KagemitsuNagao", MARKER_SUN, 10, 25, 0, 301),
    # --- I 组：文件名混乱 / 重名 ---
    (
        "I_文件名混乱重名/同名不同时间戳/KoikatsuSun_F_20260905140632481_Higashiyama Kobeni.png",
        "HigashiyamaKobeni",
        MARKER_SUN,
        14,
        42,
        0,
        192,
    ),
    (
        "I_文件名混乱重名/同名不同时间戳/KoikatsuSun_F_20260905140632862_Higashiyama Kobeni.png",
        "HigashiyamaKobeni",
        MARKER_SUN,
        14,
        42,
        0,
        192,
    ),
    (
        "I_文件名混乱重名/同名不同目录/female/Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png",
        "KugisakiNobara",
        MARKER_SUN,
        18,
        13,
        17,
        30,
    ),
    (
        "I_文件名混乱重名/同名不同目录/old_female/Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png",
        "KugisakiNobara",
        MARKER_KK,
        17,
        13,
        17,
        30,
    ),
    ("I_文件名混乱重名/混乱命名/[Yeeted] Sora .png", "IkushimaSora", MARKER_SUN, 14, 17, 22, 30),
    ("I_文件名混乱重名/混乱命名/KK_317794.png", "HigashiyamaKobeni", MARKER_SUN, 12, 43, 0, 192),
    # --- J 组：复杂完整角色 ---
    ("J_复杂完整角色/刀剑神域 - 绀野木棉季.png", "ユウキ", MARKER_SUN, 21, 31, 120, 220),
]


def _ids():
    return [e[0].replace("/", " | ") for e in CARD_EXPECTATIONS]


@pytest.mark.parametrize("expected", CARD_EXPECTATIONS, ids=_ids())
def test_real_card_matches_ground_truth(sample_root: Path, expected):
    rel, name, marker, plugins, unique, embedded, records = expected
    result = parse_card(sample_root / rel)

    assert result.parse_status in ("ok", "partial"), (
        f"{rel} 解析失败：{result.error} / {result.warnings}"
    )
    assert result.success
    assert result.card_marker == marker, f"{rel} marker 不符"
    assert result.card_type == "character_card"
    assert result.name == name, f"{rel} 角色名不符"
    assert result.plugin_count == plugins, f"{rel} 插件数不符"
    assert result.unique_mod_count == unique, f"{rel} 唯一 MOD 数不符"
    assert result.embedded_texture_count == embedded, f"{rel} 内嵌贴图数不符"
    assert result.dependency_records == records, f"{rel} 依赖记录数不符"


def test_all_cards_are_parsed(sample_files):
    cards = sample_files["cards"]
    assert len(cards) == 22, f"期望 22 张卡，实际 {len(cards)}"
    failures = []
    for path in cards:
        result = parse_card(path)
        if not result.success:
            failures.append((path.name, result.error))
    assert not failures, f"以下卡片解析失败：{failures}"


# ---------------------------------------------------------------------------
# 逐条验收要求
# ---------------------------------------------------------------------------


def _card(sample_root: Path, rel: str) -> CharacterCardParseResult:
    return parse_card(sample_root / rel)


def test_sayaka_records_and_unique_mod(sample_root: Path):
    result = _card(sample_root, "B_带MOD角色卡/魔法少女小圆 - 美树沙耶香.png")
    assert result.dependency_records == 4
    assert result.unique_mod_guids == ["com.Quokka.sisterveilb"]
    # 同一个 MOD 被 4 个槽位引用 → 4 条记录的 Property 各不相同
    assert len({d.property for d in result.dependencies}) == 4


def test_kyoko_records_and_unique_mods(sample_root: Path):
    result = _card(sample_root, "B_带MOD角色卡/魔法少女小圆 - 佐仓杏子.png")
    assert result.dependency_records == 5
    assert sorted(result.unique_mod_guids) == [
        "com.Quokka.chinadresstop",
        "com.Quokka.crossstaff",
        "com.ymgpt.acc_earrings_top",
    ]


def test_ayame_keeps_eye_properties_without_inference(sample_root: Path):
    """眼睛相关 Property 必须原样保留；但**不允许**做任何「来源」推断。"""
    result = _card(sample_root, "C_自定义眼睛/没有黄段子的无聊世界 - 华城绫女.png")
    properties = {d.property for d in result.dependencies}
    assert "ChaFileFace.eyelineUpId" in properties
    assert "ChaFileFace.Pupil1" in properties
    assert "ChaFileFace.Pupil2" in properties
    assert result.unique_mod_guids == ["com.gf.collection"]

    # 解析结果里不存在「类型推断」字段
    record_fields = {f.name for f in dataclasses.fields(ModDependencyRecord)}
    assert record_fields == {
        "mod_id",
        "property",
        "slot",
        "local_slot",
        "category_no",
        "author",
        "website",
        "name",
    }
    card_fields = {f.name for f in dataclasses.fields(CharacterCardParseResult)}
    for forbidden in ("eyes", "skin", "hair", "clothes", "accessory", "resource_type"):
        assert forbidden not in card_fields


def test_aki_body_detail_dependency(sample_root: Path):
    result = _card(sample_root, "D_皮肤身体贴图/政宗君的复仇 - 安达垣爱姬.png")
    assert [d.property for d in result.dependencies] == ["ChaFileBody.detailId"]
    assert result.unique_mod_guids == ["com.Blanketman.AdditionalSkinMod"]


def test_cocoa_embedded_textures_and_mods(sample_root: Path):
    result = _card(sample_root, "D_皮肤身体贴图/请问您今天要来点兔子吗 - 保登心爱.png")
    assert result.embedded_texture_count == 7
    assert sorted(result.unique_mod_guids) == [
        "com.Blanketman.AdditionalSkinMod",
        "com.Blanketman.NonLightStockings",
    ]
    assert result.plugin_count == 4


def test_ranrin_keeps_multiple_properties_for_same_mod(sample_root: Path):
    result = _card(sample_root, "C_自定义眼睛/天结堡主 - 岚燐结骑.png")
    assert result.unique_mod_guids == ["RCL_circuit.Mod.RanrinYuiki"]
    assert result.dependency_records == 13
    properties = [d.property for d in result.dependencies]
    assert len(set(properties)) > 1, "同一个 MOD 在多个 Property/Slot 上的关系不能丢失"
    assert any(p.startswith("ChaFileFace.") for p in properties)


def test_shared_mod_is_referenced_by_both_cards(sample_root: Path):
    """一个 MOD 被多个角色共享 → 两个结果里都能看到（反向查询的基础）。"""
    hongdou = _card(sample_root, "H_共享MOD多角色/明日方舟 - 红豆.png")
    nagao = _card(sample_root, "H_共享MOD多角色/FATE - 长尾景虎.png")
    shared = "com.Quokka.naginata"

    assert shared in hongdou.unique_mod_guids
    assert shared in nagao.unique_mod_guids

    hongdou_props = {d.property for d in hongdou.dependencies if d.mod_id == shared}
    nagao_props = {d.property for d in nagao.dependencies if d.mod_id == shared}
    assert hongdou_props and nagao_props
    assert hongdou_props != nagao_props, "两张卡使用同一 MOD 的槽位不同"


def test_missing_local_zipmod_dependency_is_kept(sample_root: Path, sample_files):
    """依赖的 MOD 在本样本里没有 zipmod，关系仍必须保留。"""
    local_guids = set()
    from core.parsers import parse_zipmod

    for path in sample_files["zipmods"]:
        parsed = parse_zipmod(path)
        if parsed.guid:
            local_guids.add(parsed.guid)

    missing = {
        "com.ymgpt.acc_earrings_top",   # 佐仓杏子依赖
        "com.Blanketman.NonLightStockings",  # 保登心爱依赖
    }
    assert not (missing & local_guids), "前提：这些 GUID 在样本里确实没有 zipmod"

    kyoko = _card(sample_root, "B_带MOD角色卡/魔法少女小圆 - 佐仓杏子.png")
    cocoa = _card(sample_root, "D_皮肤身体贴图/请问您今天要来点兔子吗 - 保登心爱.png")
    assert "com.ymgpt.acc_earrings_top" in kyoko.unique_mod_guids
    assert "com.Blanketman.NonLightStockings" in cocoa.unique_mod_guids


def test_two_kobeni_differ_only_by_data_id(sample_root: Path):
    """两张近似文件：dataID 不同，但它**不参与身份判断**。"""
    a = _card(
        sample_root,
        "I_文件名混乱重名/同名不同时间戳/KoikatsuSun_F_20260905140632481_Higashiyama Kobeni.png",
    )
    b = _card(
        sample_root,
        "I_文件名混乱重名/同名不同时间戳/KoikatsuSun_F_20260905140632862_Higashiyama Kobeni.png",
    )
    assert a.name == b.name == "HigashiyamaKobeni"
    assert a.data_id and b.data_id
    assert a.data_id != b.data_id
    assert a.user_id == b.user_id
    # 身份来自路径，不来自 dataID
    assert a.path != b.path
    assert a.data_id not in a.path and b.data_id not in b.path


def test_kk_and_kks_markers_stay_distinct(sample_root: Path):
    sun = _card(
        sample_root,
        "I_文件名混乱重名/同名不同目录/female/Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png",
    )
    kk = _card(
        sample_root,
        "I_文件名混乱重名/同名不同目录/old_female/Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png",
    )
    assert sun.card_marker == MARKER_SUN
    assert kk.card_marker == MARKER_KK
    assert sun.card_marker != kk.card_marker, "KK 与 KKS 不能被归一成同一个格式"
    # 两张卡是同一角色，但内容不同（插件数不同）
    assert sun.name == kk.name
    assert sun.plugin_count != kk.plugin_count


def test_unicode_character_names_survive(sample_root: Path):
    cases = {
        "J_复杂完整角色/刀剑神域 - 绀野木棉季.png": "ユウキ",
        "C_自定义眼睛/天结堡主 - 岚燐结骑.png": "嵐燐結騎",
        "E_角色加衣服MOD/不死者之王 - 夏提雅 布拉德弗伦.png": "夏提雅·布拉德弗伦",
        "I_文件名混乱重名/混乱命名/[Yeeted] Sora .png": "IkushimaSora",
    }
    for rel, expected in cases.items():
        result = _card(sample_root, rel)
        assert result.name == expected, f"{rel} 角色名被破坏"


def test_cards_without_mod_dependencies_are_ok_not_partial(sample_root: Path):
    """没有 MOD 依赖是正常状态（两种空形态），不能被判成 partial。"""
    rodney = _card(sample_root, "A_普通角色卡_无MOD/碧蓝航线 - 罗德尼.png")
    madoka = _card(sample_root, "A_普通角色卡_无MOD/魔法少女小圆 - 鹿目圆.png")

    assert rodney.parse_status == "ok"       # KKEx 里没有 sideloader 键
    assert madoka.parse_status == "ok"       # sideloader 键存在但 info 为空
    assert rodney.dependencies == [] and madoka.dependencies == []
    assert rodney.unique_mod_guids == [] and madoka.unique_mod_guids == []


def test_kk_format_has_no_about_block(sample_root: Path):
    """实测格式差异：KK（原版）卡片的 lstInfo 里没有 About 块，KKS 有。

    这不是解析失败：KK 卡照样能读出名字与依赖，只是没有 userID/dataID。
    """
    kk = _card(
        sample_root,
        "I_文件名混乱重名/同名不同目录/old_female/Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png",
    )
    sun = _card(
        sample_root,
        "I_文件名混乱重名/同名不同目录/female/Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png",
    )

    kk_blocks = {e.name for e in kk.lst_info}
    sun_blocks = {e.name for e in sun.lst_info}
    assert "About" not in kk_blocks, "KK 卡片实测没有 About 块"
    assert "About" in sun_blocks

    assert kk.user_id is None and kk.data_id is None
    assert sun.user_id and sun.data_id
    # 但 KK 卡依然能正常解析出名字与依赖
    assert kk.success and kk.name == "KugisakiNobara"
    assert kk.dependency_records == 30


def test_yuuki_records_not_lost_by_dedup(sample_root: Path):
    result = _card(sample_root, "J_复杂完整角色/刀剑神域 - 绀野木棉季.png")
    assert result.dependency_records == 220, "去重不能减少 records 数量"
    assert result.unique_mod_count == 31
    assert len(result.unique_mod_guids) == len(set(result.unique_mod_guids))


# ---------------------------------------------------------------------------
# 结构化字段与限制
# ---------------------------------------------------------------------------


def test_lst_info_is_sorted_by_pos(sample_root: Path):
    result = _card(sample_root, "A_普通角色卡_无MOD/魔法少女小圆 - 鹿目圆.png")
    positions = [e.pos for e in result.lst_info]
    assert positions == sorted(positions), "lstInfo 必须按 pos 排序"
    assert result.lst_info_reordered is True, "该样本的原始顺序确实与 pos 顺序不同"
    block_names = {e.name for e in result.lst_info}
    assert {"KKEx", "Custom", "Coordinate", "Parameter", "Status", "About"} <= block_names


def test_container_fields_are_preserved(sample_root: Path):
    result = _card(sample_root, "A_普通角色卡_无MOD/魔法少女小圆 - 鹿目圆.png")
    assert result.product_no == 100
    assert result.card_version == "0.0.0"
    assert result.card_marker_raw == "【KoiKatuCharaSun】"
    assert result.face_preview_kind == "jpeg"
    assert result.face_preview_size > 0
    assert result.file_level_reserved == 0
    assert result.region_covers_to_eof is True


def test_face_preview_kind_covers_both_formats(sample_root: Path):
    """实测面部预览图既有 JPEG 也有 PNG —— 解析器不能假设成一种。"""
    jpeg_card = _card(sample_root, "A_普通角色卡_无MOD/魔法少女小圆 - 鹿目圆.png")
    png_card = _card(sample_root, "A_普通角色卡_无MOD/碧蓝航线 - 罗德尼.png")
    assert jpeg_card.face_preview_kind == "jpeg"
    assert png_card.face_preview_kind == "png"


def test_parameter_fields_are_extracted(sample_root: Path):
    result = _card(sample_root, "A_普通角色卡_无MOD/魔法少女小圆 - 鹿目圆.png")
    assert result.lastname == "鹿目"
    assert result.firstname == "まどか"
    assert result.nickname == "まどか"
    assert result.personality == 8


def test_about_fields_are_extracted(sample_root: Path):
    result = _card(sample_root, "A_普通角色卡_无MOD/魔法少女小圆 - 鹿目圆.png")
    assert result.user_id == "c43c4055-cdf4-4a06-8035-d10cb0ce5f09"
    assert result.data_id == "07ee7d46-559c-47c4-a2d2-8974ab43ecec"


def test_dependency_record_keeps_all_fields(sample_root: Path):
    result = _card(sample_root, "B_带MOD角色卡/魔法少女小圆 - 美树沙耶香.png")
    record = result.dependencies[0]
    assert record.mod_id == "com.Quokka.sisterveilb"
    assert record.property.endswith(".ChaFileAccessory.PartsInfo.id")
    assert record.slot == 1
    assert record.local_slot is not None
    assert record.category_no == 0
    assert record.author is None      # 卡内该字段实测为 null
    assert record.website is None
    assert record.name is None


# ---------------------------------------------------------------------------
# 作者（Phase 1.2-D）
# ---------------------------------------------------------------------------


F_GROUP_CARDS = [
    "F_同作者多角色/Koikatu_F_20201023022200944_Hermione_Evaan.png",
    "F_同作者多角色/Koikatu_F_20230324192530956_Tatsumaki_Evaan.png",
    "F_同作者多角色/Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png",
]


@pytest.mark.parametrize("rel", F_GROUP_CARDS, ids=lambda r: r.split("/")[-1][:28])
def test_group_f_authors_from_card(sample_root: Path, rel: str):
    """F 组三张卡：真实作者是 Evaan，原始列表里含 [Unknown]。"""
    result = _card(sample_root, rel)

    assert result.authors == ["Evaan"]
    assert result.authors_raw == ["[Unknown]", "Evaan"]


def test_group_f_unknown_sentinel_is_not_a_real_author(sample_root: Path):
    for rel in F_GROUP_CARDS:
        result = _card(sample_root, rel)
        assert "[Unknown]" not in result.authors
        assert "[Unknown]" in result.authors_raw, "原始值不能丢"
        assert result.parse_status == "ok", "有作者数据不应该影响解析状态"


def test_cards_without_author_data_are_not_errors(sample_root: Path):
    """22 张里只有 12 张带 marco.authordata；其余 10 张必须正常且无警告。"""
    for rel in (
        "A_普通角色卡_无MOD/魔法少女小圆 - 鹿目圆.png",
        "A_普通角色卡_无MOD/碧蓝航线 - 罗德尼.png",
        "C_自定义眼睛/天结堡主 - 岚燐结骑.png",
        "E_角色加衣服MOD/青春猪头少年系列 - 古贺朋绘.png",
    ):
        result = _card(sample_root, rel)
        assert result.authors == []
        assert result.authors_raw == []
        assert result.parse_status == "ok"
        assert not any("authordata" in w for w in result.warnings)


def test_author_counts_across_samples(sample_root: Path):
    cards = sorted(sample_root.rglob("*.png"))
    assert len(cards) == 22
    with_authors = [p for p in cards if parse_card(p).authors]
    assert len(with_authors) == 12, "12 张卡带作者数据"
    evaan = [p for p in cards if "Evaan" in parse_card(p).authors]
    assert len(evaan) == 5, "Evaan 出现在 F 组 3 张 + I 组 2 张 Kugisaki"


def test_author_is_not_inferred_from_file_name(tmp_path: Path):
    """文件名里写着 Evaan，但卡内没有作者数据 → authors 必须为空。"""
    from tests.builders import write_card

    path = write_card(tmp_path / "Koikatu_F_20240101_Evaan.png")
    result = parse_card(path)

    assert result.name == "測試角色"
    assert result.authors == []
    assert result.authors_raw == []


def test_damaged_author_block_does_not_break_the_card(tmp_path: Path):
    from tests.builders import write_card

    path = write_card(
        tmp_path / "broken-authors.png",
        dependencies=(("com.example.mod", "outfit0.a", 0),),
        broken_authors=True,
    )
    result = parse_card(path)

    assert result.success, "作者数据损坏不能让整张卡失败"
    assert result.name == "測試角色"
    assert result.card_marker == MARKER_SUN
    assert result.unique_mod_guids == ["com.example.mod"], "其它 KKEx 数据不受影响"
    assert any("authordata" in w for w in result.warnings), "损坏要留下 warning"


def test_author_list_is_cleaned_and_deduped_but_raw_kept(tmp_path: Path):
    from tests.builders import write_card

    path = write_card(
        tmp_path / "authors.png",
        authors=("[Unknown]", "  Evaan ", "Evaan", "Anonymous", ""),
    )
    result = parse_card(path)

    assert result.authors == ["Evaan", "Anonymous"], "去空白、去重、去哨兵"
    assert result.authors_raw == [
        "[Unknown]",
        "  Evaan ",
        "Evaan",
        "Anonymous",
        "",
    ], "原始列表逐项保留"


def test_author_field_defaults_are_empty_lists(sample_root: Path):
    result = _card(sample_root, "A_普通角色卡_无MOD/碧蓝航线 - 罗德尼.png")
    assert result.authors == []
    assert result.authors_raw == []
    assert isinstance(result.authors, list)
    assert isinstance(result.authors_raw, list)
