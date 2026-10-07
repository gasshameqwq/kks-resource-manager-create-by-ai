"""Phase 1.2-B 验收：ZIPMOD Parser（**真实样本**）。

判定规则：只有 ZIP 内存在 ``manifest.xml`` 才算 ZIPMOD；文件名/目录名不参与判断。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.parsers import ZipmodParseResult, parse_zipmod  # noqa: E402

# (相对路径, guid, name, author, version)
ZIPMOD_EXPECTATIONS = [
    (
        "B_带MOD角色卡/MOD/[Quokka] Sister Veil b 1.0.zipmod",
        "com.Quokka.sisterveilb",
        "Sister_veil_b",
        "Quokka",
        "1.0",
    ),
    (
        "B_带MOD角色卡/MOD/[Quokka] Accessory Cross Staff 1.0.zipmod",
        "com.Quokka.crossstaff",
        "Cross_staff",
        "Quokka",
        "1.0",
    ),
    (
        "B_带MOD角色卡/MOD/[Quokka] China Dress Top 1.0.zipmod",
        "com.Quokka.chinadresstop",
        "China_dress_top",
        "Quokka",
        "1.0",
    ),
    (
        "C_自定义眼睛/mod/[GF] Character Texture Pack v1.7.3.zipmod",
        "com.gf.collection",
        "GF mods",
        "GF",
        "1.7.3",
    ),
    (
        "C_自定义眼睛/mod/[RCL_circuit] Ranrin-Yuiki Amayui Castle Meister.zipmod",
        "RCL_circuit.Mod.RanrinYuiki",
        "Ranrin-Yuiki Amayui Castle Meister",
        "RCL_circuit",
        "1.0",
    ),
    (
        "D_皮肤身体贴图/MOD/[Blanketman] Additional Skin Pack v2.3.zipmod",
        "com.Blanketman.AdditionalSkinMod",
        "Additional Skin Pack",
        "Blanketman",
        "2.3",
    ),
    (
        "E_角色加衣服MOD/MOD/[essu] shinyBunny v1.zipmod",
        "shinyBunny",
        "shinyBunny",
        "essu",
        "1.0",
    ),
    (
        "E_角色加衣服MOD/MOD/[Quokka] Classic Maid Skirt 1.0.zipmod",
        "com.Quokka.classicmaidskirt",
        "Classic_maid_skirt",
        "Quokka",
        "1.0",
    ),
    (
        "F_同作者多角色/MOD/[ryo2003] VanillaEx Stiletto1 v1.0.zipmod",
        "ryo2003.stiletto",
        "VanillaEx Stiletto",
        "ryo2003",
        "1.0",
    ),
    ("G_孤立MOD_无角色卡/MOD/NoHair.zipmod", "NoHair", "NoHair Head", "", "0"),
    (
        "G_孤立MOD_无角色卡/MOD/[ucklline] Elven Panst.zipmod",
        "elven_panst",
        "elven_panst",
        "ucklline",
        "1.5",
    ),
    (
        "G_孤立MOD_无角色卡/MOD/[Unknown] koikatu.AltSlot.co_bot_19.zipmod",
        "koikatu.AltSlot.co_bot_19",
        "koikatu.AltSlot.co_bot_19",
        "Unknown",
        "1.0",
    ),
    (
        "H_共享MOD多角色/MOD/[Quokka] Accessory Naginata 1.0.zipmod",
        "com.Quokka.naginata",
        "Naginata",
        "Quokka",
        "1.0",
    ),
]


@pytest.mark.parametrize(
    "expected", ZIPMOD_EXPECTATIONS, ids=[e[0].split("/")[-1] for e in ZIPMOD_EXPECTATIONS]
)
def test_real_zipmod_matches_ground_truth(sample_root: Path, expected):
    rel, guid, name, author, version = expected
    result = parse_zipmod(sample_root / rel)

    assert result.success, f"{rel} 解析失败：{result.error}"
    assert result.is_zipmod is True
    assert result.manifest_entry == "manifest.xml"
    assert result.guid == guid
    assert result.name == name
    assert result.author == author
    assert result.version == version


def test_all_zipmods_are_parsed(sample_files):
    zipmods = sample_files["zipmods"]
    assert len(zipmods) == 13, f"期望 13 个 zipmod，实际 {len(zipmods)}"
    failures = []
    guids = []
    for path in zipmods:
        result = parse_zipmod(path)
        if not result.success or not result.guid:
            failures.append((path.name, result.error or result.warnings))
        else:
            guids.append(result.guid)
    assert not failures, f"以下 zipmod 解析失败：{failures}"
    assert len(set(guids)) == 13, "13 个 zipmod 的 guid 应当各不相同"


def test_abnormal_author_and_version_do_not_fail(sample_root: Path):
    """NoHair 的 author 为空、version 为 '0' —— 不能因此判定解析失败。"""
    result = parse_zipmod(sample_root / "G_孤立MOD_无角色卡/MOD/NoHair.zipmod")
    assert result.success
    assert result.guid == "NoHair"
    assert result.author == ""
    assert result.version == "0"


def test_guid_format_is_not_assumed(sample_root: Path):
    """GUID 既有 `shinyBunny` 这种无点写法，也有 `com.Quokka.*` 点分写法，都必须接受。"""
    plain = parse_zipmod(
        sample_root / "E_角色加衣服MOD/MOD/[essu] shinyBunny v1.zipmod"
    )
    dotted = parse_zipmod(
        sample_root / "E_角色加衣服MOD/MOD/[Quokka] Classic Maid Skirt 1.0.zipmod"
    )
    assert plain.guid == "shinyBunny" and "." not in plain.guid
    assert dotted.guid == "com.Quokka.classicmaidskirt" and "." in dotted.guid


def test_filename_does_not_decide_type(sample_root: Path, tmp_path: Path):
    """把一个真实 zipmod 改名成完全不相关的名字，结论必须不变。"""
    import shutil

    source = sample_root / "G_孤立MOD_无角色卡/MOD/NoHair.zipmod"
    renamed = tmp_path / "totally_unrelated_name.zipmod"
    shutil.copyfile(source, renamed)  # 只复制到临时目录，样本目录不动

    result = parse_zipmod(renamed)
    assert result.success
    assert result.guid == "NoHair"


def test_website_is_optional(sample_root: Path):
    result = parse_zipmod(sample_root / "G_孤立MOD_无角色卡/MOD/NoHair.zipmod")
    assert result.website is None or isinstance(result.website, str)
