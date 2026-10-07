"""Phase 1.3-A：property 语义分类（``core.query.property_map``）单元测试。

分类层是查询层「按 property 语义筛选」的唯一事实来源，因此这里既测 Python
分类函数，也测「由同一份映射生成的 SQL 谓词」与 Python 结果完全一致。
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.query.property_map import (  # noqa: E402
    ALL_PROPERTY_TOKENS,
    PROPERTY_CATEGORY_ACCESSORY,
    PROPERTY_CATEGORY_ALL,
    PROPERTY_CATEGORY_BODY,
    PROPERTY_CATEGORY_CLOTHES,
    PROPERTY_CATEGORY_FACE,
    PROPERTY_CATEGORY_HAIR,
    PROPERTY_CATEGORY_MAKEUP,
    PROPERTY_CATEGORY_UNKNOWN,
    category_tokens,
    classify_property,
    property_block,
    sql_category_predicate,
)


# 覆盖全部 6 个块 + unknown + 一个「子串相似但整段不同」的陷阱。
SAMPLE_PROPERTIES = [
    "ChaFileFace.eyelineUpId",
    "ChaFileFace.Pupil1",
    "ChaFileFace.eyebrowId",
    "ChaFileBody.detailId",
    "ChaFileBody.nipId",
    "ChaFileClothes.ClothesTop",
    "ChaFileAccessory.PartsInfo.id",
    "ChaFileHair.HairBack",
    "ChaFileMakeup.PaintID1",
    "outfit6.ChaFileClothes.ClothesTop",
    "outfit6.accessory10.ChaFileAccessory.PartsInfo.id",
    "NotARealChaFileFace.Thing",  # 子串陷阱：整段不等于 ChaFileFace
    "Totally.Different",
]


@pytest.mark.parametrize(
    ("prop", "expected"),
    [
        ("ChaFileFace.eyelineUpId", PROPERTY_CATEGORY_FACE),
        ("ChaFileFace.Pupil1", PROPERTY_CATEGORY_FACE),
        ("ChaFileBody.detailId", PROPERTY_CATEGORY_BODY),
        ("ChaFileHair.HairBack", PROPERTY_CATEGORY_HAIR),
        ("ChaFileMakeup.PaintID1", PROPERTY_CATEGORY_MAKEUP),
        ("ChaFileClothes.ClothesTop", PROPERTY_CATEGORY_CLOTHES),
        ("ChaFileAccessory.PartsInfo.id", PROPERTY_CATEGORY_ACCESSORY),
        ("outfit6.ChaFileClothes.ClothesTop", PROPERTY_CATEGORY_CLOTHES),
        (
            "outfit6.accessory10.ChaFileAccessory.PartsInfo.id",
            PROPERTY_CATEGORY_ACCESSORY,
        ),
        ("outfit0.ChaFileClothes.ClothesBraPattern0", PROPERTY_CATEGORY_CLOTHES),
    ],
)
def test_classify_known_blocks(prop: str, expected: str) -> None:
    assert classify_property(prop) == expected


def test_unknown_and_empty_are_preserved() -> None:
    assert classify_property("Totally.Different") == PROPERTY_CATEGORY_UNKNOWN
    assert classify_property("NotARealChaFileFace.Thing") == PROPERTY_CATEGORY_UNKNOWN
    assert classify_property("") == PROPERTY_CATEGORY_UNKNOWN
    assert classify_property(None) == PROPERTY_CATEGORY_UNKNOWN


def test_face_is_coarse_not_eyes() -> None:
    """face 只表示「面部块」：瞳孔、眼线、眉毛、鼻子同属 face，不推断 eyes。"""
    for prop in (
        "ChaFileFace.Pupil1",
        "ChaFileFace.eyelineUpId",
        "ChaFileFace.eyebrowId",
        "ChaFileFace.noseId",
    ):
        assert classify_property(prop) == PROPERTY_CATEGORY_FACE


def test_property_block() -> None:
    assert property_block("outfit6.accessory10.ChaFileAccessory.PartsInfo.id") == (
        "ChaFileAccessory"
    )
    assert property_block("ChaFileBody.detailId") == "ChaFileBody"
    assert property_block("Totally.Different") is None


def test_category_tokens_and_invalid_category() -> None:
    assert category_tokens(PROPERTY_CATEGORY_CLOTHES) == ("ChaFileClothes",)
    assert category_tokens(PROPERTY_CATEGORY_UNKNOWN) == ()
    with pytest.raises(ValueError):
        category_tokens("nope")
    with pytest.raises(ValueError):
        sql_category_predicate("nope")


def test_sql_predicate_matches_python_classifier() -> None:
    """SQL 谓词与 Python 分类必须逐行一致（含 unknown 与子串陷阱）。"""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t(property TEXT)")
        conn.executemany(
            "INSERT INTO t(property) VALUES (?)",
            [(p,) for p in SAMPLE_PROPERTIES],
        )
        for category in PROPERTY_CATEGORY_ALL:
            fragment, params = sql_category_predicate(category)
            sql_hits = {
                row[0]
                for row in conn.execute(
                    f"SELECT property FROM t WHERE {fragment}", params
                )
            }
            python_hits = {
                p for p in SAMPLE_PROPERTIES if classify_property(p) == category
            }
            assert sql_hits == python_hits, category
    finally:
        conn.close()


def test_tokens_cover_all_known_categories() -> None:
    assert set(ALL_PROPERTY_TOKENS) == {
        "ChaFileFace",
        "ChaFileBody",
        "ChaFileClothes",
        "ChaFileAccessory",
        "ChaFileHair",
        "ChaFileMakeup",
    }
