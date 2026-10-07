"""Property 语义分类 —— Phase 1.3-A 查询层。

``resource_mod_usages.property`` 是卡片上「某个 MOD 用在哪」的原始槽位路径，例如::

    ChaFileFace.eyelineUpId
    ChaFileBody.detailId
    outfit6.ChaFileClothes.ClothesTop
    outfit6.accessory10.ChaFileAccessory.PartsInfo.id

真实样本（22 张卡 / 1527 条 usage / 497 个不同 property）实测，所有 property 都
形如 ``[outfitN[.accessoryM].]<ChaFileXXX>.<字段…>``，其中块名 ``<ChaFileXXX>``
只出现 6 种。本模块把这 6 种块名集中映射为语义类别，是查询层
「按 property 语义筛选」的**唯一事实来源**。

设计原则
--------
1. **单一事实来源**：分类规则只在这里定义一次；查询层需要的 SQL 谓词也由同一份
   映射生成，禁止在别处散落 ``LIKE 'ChaFileFace.%'``。
2. **粗粒度**：``face`` 只表示「面部块」，**不等于** eyes —— 同一个块里还有
   眉毛 / 鼻子 / 嘴 / 脸型；``body`` 也不等于 skin。样本无法可靠区分这些更细的
   语义，因此保持粗粒度，不制造错误分类。
3. **不静默丢弃**：无法归类的 property 一律落到 ``unknown``，并且仍然出现在查询
   结果里（可用 ``unknown`` 类别单独筛查）。

匹配规则：把 property 按 ``.`` 切成段，取**第一个**恰好等于已知块名的段作为类别。
样本中没有任何 property 同时含两个不同块名，因此「第一个命中」是良定义的。
"""

from __future__ import annotations

# 语义类别取值。
PROPERTY_CATEGORY_FACE = "face"
PROPERTY_CATEGORY_BODY = "body"
PROPERTY_CATEGORY_CLOTHES = "clothes"
PROPERTY_CATEGORY_ACCESSORY = "accessory"
PROPERTY_CATEGORY_HAIR = "hair"
PROPERTY_CATEGORY_MAKEUP = "makeup"
PROPERTY_CATEGORY_UNKNOWN = "unknown"

# 已知类别（不含 unknown），顺序稳定，供 UI 展示与统计排序使用。
PROPERTY_CATEGORIES: tuple[str, ...] = (
    PROPERTY_CATEGORY_FACE,
    PROPERTY_CATEGORY_BODY,
    PROPERTY_CATEGORY_CLOTHES,
    PROPERTY_CATEGORY_ACCESSORY,
    PROPERTY_CATEGORY_HAIR,
    PROPERTY_CATEGORY_MAKEUP,
)

# 含 unknown 的全部取值。
PROPERTY_CATEGORY_ALL: tuple[str, ...] = PROPERTY_CATEGORIES + (
    PROPERTY_CATEGORY_UNKNOWN,
)

# 块名 token -> 语义类别。这是唯一的一份映射定义。
_TOKEN_CATEGORY: dict[str, str] = {
    "ChaFileFace": PROPERTY_CATEGORY_FACE,
    "ChaFileBody": PROPERTY_CATEGORY_BODY,
    "ChaFileClothes": PROPERTY_CATEGORY_CLOTHES,
    "ChaFileAccessory": PROPERTY_CATEGORY_ACCESSORY,
    "ChaFileHair": PROPERTY_CATEGORY_HAIR,
    "ChaFileMakeup": PROPERTY_CATEGORY_MAKEUP,
}

# 类别 -> 该类别对应的块名 tokens（通常 1 个，保留多个是为将来扩展）。
_CATEGORY_TOKENS: dict[str, tuple[str, ...]] = {}
for _token, _category in _TOKEN_CATEGORY.items():
    _CATEGORY_TOKENS[_category] = _CATEGORY_TOKENS.get(_category, ()) + (_token,)
del _token, _category

# 全部块名（顺序稳定），unknown 谓词与测试用。
ALL_PROPERTY_TOKENS: tuple[str, ...] = tuple(sorted(_TOKEN_CATEGORY))


def property_block(prop: str | None) -> str | None:
    """返回 property 中第一个命中的已知块名；没有命中返回 ``None``。"""
    if not prop:
        return None
    for segment in str(prop).split("."):
        if segment in _TOKEN_CATEGORY:
            return segment
    return None


def classify_property(prop: str | None) -> str:
    """把原始 property 归类成语义类别；无法归类返回 ``unknown``。

    >>> classify_property("outfit6.ChaFileClothes.ClothesTop")
    'clothes'
    >>> classify_property("ChaFileFace.eyebrowId")  # 面部块，不等于 eyes
    'face'
    >>> classify_property("Totally.Unknown")
    'unknown'
    """
    block = property_block(prop)
    if block is None:
        return PROPERTY_CATEGORY_UNKNOWN
    return _TOKEN_CATEGORY[block]


def category_tokens(category: str) -> tuple[str, ...]:
    """返回某个语义类别对应的块名 tokens（``unknown`` 返回空元组）。"""
    if category == PROPERTY_CATEGORY_UNKNOWN:
        return ()
    if category not in _CATEGORY_TOKENS:
        raise ValueError(
            f"未知 property 类别：{category!r}（可选 {PROPERTY_CATEGORY_ALL}）"
        )
    return _CATEGORY_TOKENS[category]


def sql_category_predicate(
    category: str, *, column: str = "property"
) -> tuple[str, tuple[object, ...]]:
    """生成「某语义类别」的 SQL 谓词，返回 ``(fragment, params)``。

    谓词用 ``('.' || <column> || '.') LIKE '%.<token>.%'`` 做**整段**匹配，
    因此不会把 ``NotARealChaFileFace`` 这类子串误判成 ``ChaFileFace``。
    谓词与 :func:`classify_property` 出自同一份映射，二者必须一致（有测试保证）。

    ``unknown`` 类别 = 不等于任何已知块名。
    """
    if category not in PROPERTY_CATEGORY_ALL:
        raise ValueError(
            f"未知 property 类别：{category!r}（可选 {PROPERTY_CATEGORY_ALL}）"
        )

    expr = f"('.' || {column} || '.')"
    if category == PROPERTY_CATEGORY_UNKNOWN:
        clauses = [f"{expr} NOT LIKE ?" for _ in ALL_PROPERTY_TOKENS]
        params = tuple(f"%.{token}.%" for token in ALL_PROPERTY_TOKENS)
        return "(" + " AND ".join(clauses) + ")", params

    tokens = _CATEGORY_TOKENS[category]
    clauses = [f"{expr} LIKE ?" for _ in tokens]
    params = tuple(f"%.{token}.%" for token in tokens)
    return "(" + " OR ".join(clauses) + ")", params


__all__ = [
    "PROPERTY_CATEGORY_FACE",
    "PROPERTY_CATEGORY_BODY",
    "PROPERTY_CATEGORY_CLOTHES",
    "PROPERTY_CATEGORY_ACCESSORY",
    "PROPERTY_CATEGORY_HAIR",
    "PROPERTY_CATEGORY_MAKEUP",
    "PROPERTY_CATEGORY_UNKNOWN",
    "PROPERTY_CATEGORIES",
    "PROPERTY_CATEGORY_ALL",
    "ALL_PROPERTY_TOKENS",
    "classify_property",
    "property_block",
    "category_tokens",
    "sql_category_predicate",
]
