"""Phase 1.4-A：Search Core（只读文本检索）测试。

覆盖：空查询、长度路由（1–2 字 LIKE / ≥3 字 FTS）、FTS 回退、FTS 输入安全、
作者关系搜索、与结构化筛选/排序/分页组合、只读不变量，以及真实样本验证。

所有测试都**只读**：不修改真实样本（``sample_root`` 会话夹具会前后比对 sha256）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db as database  # noqa: E402
from core.database import schema as schema_mod  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.query import (  # noqa: E402
    FTS_MIN_LENGTH,
    SEARCH_MODE_FTS,
    SEARCH_MODE_LIKE,
    SEARCH_MODE_NONE,
    ResourceQuery,
    fts_match_expression,
    like_pattern,
    normalize_query,
    plan_search,
)
from core.scanner import LibraryScanner  # noqa: E402


# ---------------------------------------------------------------------------
# 合成夹具
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path):
    """建一个临时库，返回 ``(conn, fts_enabled)``。"""
    db_file = tmp_path / "search.db"
    info = database.initialize(db_file)
    conn = database.connect(db_file)
    yield conn, bool(info["fts_enabled"])
    conn.close()


def _add_library(conn, library_id: int, root: str) -> None:
    conn.execute(
        "INSERT INTO libraries(id, name, root_path, root_path_key) VALUES (?, ?, ?, ?)",
        (library_id, f"lib{library_id}", root, root.casefold()),
    )


def _add_resource(
    conn,
    resource_id: int,
    *,
    name: str,
    display_name: str | None = None,
    relative_path: str | None = None,
    resource_type: str = "character_card",
    library_id: int | None = None,
    scan_status: str = "present",
    parse_status: str = "ok",
    needs_review: int = 0,
) -> None:
    conn.execute(
        "INSERT INTO resources(id, resource_type, name, display_name, file_path,"
        " file_path_key, relative_path, library_id, scan_status, parse_status,"
        " needs_review) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            resource_id,
            resource_type,
            name,
            display_name if display_name is not None else name,
            f"D:/lib/{resource_id}.png",
            f"d:/lib/{resource_id}.png",
            relative_path,
            library_id,
            scan_status,
            parse_status,
            needs_review,
        ),
    )


def _link_author(
    conn, resource_id: int, name: str, *, ordinal: int = 0, raw_name: str | None = None
) -> None:
    key = name.strip().casefold()
    conn.execute(
        "INSERT INTO authors(name, name_key) VALUES (?, ?)"
        " ON CONFLICT(name_key) DO NOTHING",
        (name, key),
    )
    row = conn.execute("SELECT id FROM authors WHERE name_key = ?", (key,)).fetchone()
    conn.execute(
        "INSERT INTO resource_authors(resource_id, author_id, ordinal, raw_name)"
        " VALUES (?, ?, ?, ?)",
        (resource_id, int(row["id"]), ordinal, raw_name if raw_name is not None else name),
    )


def _add_usage(conn, resource_id: int, mod_guid: str, prop: str) -> None:
    conn.execute(
        "INSERT INTO resource_mod_usages(resource_id, mod_guid, property, slot,"
        " local_slot, category_no) VALUES (?, ?, ?, 0, 0, 0)",
        (resource_id, mod_guid, prop),
    )


@pytest.fixture()
def seeded(db):
    """一个可控的合成库。

    - #1 美树沙耶香（库 1，有 clothes usage）
    - #2 佐仓杏子（库 1，有 accessory usage，作者 Evaan）
    - #3 Sayaka Miki（库 2，type=mod）
    - #4 鹿目圆（库 1，needs_review=1 / partial，作者 Anonymous）
    - #5 ABC沙耶香xyz（库 1，中英混合）
    """
    conn, fts_enabled = db
    _add_library(conn, 1, "D:/lib")
    _add_library(conn, 2, "E:/other")
    _add_resource(conn, 1, name="美树沙耶香", library_id=1)
    _add_resource(conn, 2, name="佐仓杏子", library_id=1)
    _add_resource(conn, 3, name="Sayaka Miki", resource_type="mod", library_id=2)
    _add_resource(
        conn, 4, name="鹿目圆", library_id=1, needs_review=1, parse_status="partial"
    )
    _add_resource(conn, 5, name="ABC沙耶香xyz", library_id=1)
    _add_usage(conn, 1, "com.example.clothes", "outfit6.ChaFileClothes.ClothesTop")
    _add_usage(conn, 2, "com.example.acc", "ChaFileAccessory.PartsInfo.id")
    _link_author(conn, 2, "Evaan")
    _link_author(conn, 4, "Anonymous", ordinal=1, raw_name="Anonymous")
    return conn, fts_enabled


@pytest.fixture()
def path_seeded(db):
    """专门验证「文件名/相对路径」检索的合成库（复刻真实样本的命名差异）。

    - #1 name=``美樹さやか``（日文），relative_path 含中文文件名「美树沙耶香.png」
    - #2 name=``佐倉杏子``（日文），relative_path 含中文文件名「佐仓杏子.png」
    - #3 ``ExtraHairMod``，relative_path 在子目录 ``Mods\\hair\\`` 下（type=mod）
    - #4 ``鹿目圆``（needs_review=1，无 usage）
    """
    conn, fts_enabled = db
    _add_library(conn, 1, "D:/lib")
    _add_library(conn, 2, "E:/other")
    _add_resource(
        conn,
        1,
        name="美樹さやか",
        relative_path="B_带MOD角色卡/魔法少女小圆 - 美树沙耶香.png",
        library_id=1,
    )
    _add_resource(
        conn,
        2,
        name="佐倉杏子",
        relative_path="B_带MOD角色卡/魔法少女小圆 - 佐仓杏子.png",
        library_id=1,
    )
    _add_resource(
        conn,
        3,
        name="ExtraHairMod",
        relative_path="Mods\\hair\\ExtraHair.zipmod",
        resource_type="mod",
        library_id=2,
    )
    _add_resource(
        conn,
        4,
        name="鹿目圆",
        relative_path="A_普通角色卡/魔法少女小圆 - 鹿目圆.png",
        library_id=1,
        needs_review=1,
    )
    _add_usage(conn, 1, "com.example.clothes", "outfit6.ChaFileClothes.ClothesTop")
    _add_usage(conn, 2, "com.example.acc", "ChaFileAccessory.PartsInfo.id")
    return conn, fts_enabled


# ---------------------------------------------------------------------------
# 纯函数：归一化 / 路由 / 转义
# ---------------------------------------------------------------------------


def test_normalize_query() -> None:
    assert normalize_query(None) is None
    assert normalize_query("") is None
    assert normalize_query("   ") is None
    assert normalize_query("\t\n") is None
    assert normalize_query("  沙耶 ") == "沙耶"
    with pytest.raises(TypeError):
        normalize_query(123)  # type: ignore[arg-type]


def test_plan_routes_by_length() -> None:
    assert FTS_MIN_LENGTH == 3
    assert plan_search(None, fts_available=True).mode == SEARCH_MODE_NONE
    assert plan_search("", fts_available=True).mode == SEARCH_MODE_NONE
    assert plan_search("   ", fts_available=True).mode == SEARCH_MODE_NONE
    # ASCII 按字符数
    assert plan_search("a", fts_available=True).mode == SEARCH_MODE_LIKE
    assert plan_search("ab", fts_available=True).mode == SEARCH_MODE_LIKE
    assert plan_search("abc", fts_available=True).mode == SEARCH_MODE_FTS
    assert plan_search("abcd", fts_available=True).mode == SEARCH_MODE_FTS
    # CJK 同样按字符数（不是字节数）
    assert plan_search("沙", fts_available=True).mode == SEARCH_MODE_LIKE
    assert plan_search("沙耶", fts_available=True).mode == SEARCH_MODE_LIKE
    assert plan_search("沙耶香", fts_available=True).mode == SEARCH_MODE_FTS
    # 首尾空白不影响长度判定
    assert plan_search("  沙耶  ", fts_available=True).mode == SEARCH_MODE_LIKE


def test_plan_falls_back_to_like_when_fts_unavailable() -> None:
    for query in ("a", "ab", "abc", "abcd", "沙", "沙耶", "沙耶香"):
        assert plan_search(query, fts_available=False).mode == SEARCH_MODE_LIKE
    assert plan_search(None, fts_available=False).mode == SEARCH_MODE_NONE
    assert plan_search("  ", fts_available=False).mode == SEARCH_MODE_NONE


def test_like_pattern_escapes_wildcards() -> None:
    assert like_pattern("沙耶") == "%沙耶%"
    assert like_pattern("50%") == "%50\\%%"
    assert like_pattern("a_b") == "%a\\_b%"
    assert like_pattern("a\\b") == "%a\\\\b%"


def test_fts_match_expression_is_a_quoted_phrase() -> None:
    assert fts_match_expression("沙耶香") == '{display_name name} : "沙耶香"'
    assert fts_match_expression('a"b') == '{display_name name} : "a""b"'


# ---------------------------------------------------------------------------
# 基本行为
# ---------------------------------------------------------------------------


def test_none_query_matches_all(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert rq.count() == 5
    assert rq.count(query=None) == 5
    assert [r.id for r in rq.list()] == [1, 2, 3, 4, 5]
    assert [r.id for r in rq.list(query=None)] == [1, 2, 3, 4, 5]


def test_empty_and_whitespace_query_are_noops(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    base = [r.id for r in rq.list()]
    for query in ("", "   ", "\t\n", " \t "):
        assert [r.id for r in rq.list(query=query)] == base
        assert rq.count(query=query) == rq.count()


def test_ascii_and_cjk_substring(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="Sayaka")] == [3]
    assert [r.id for r in rq.list(query="美树")] == [1]
    assert [r.id for r in rq.list(query="鹿目圆")] == [4]
    assert [r.id for r in rq.list(query="nope")] == []


# ---------------------------------------------------------------------------
# 路由在 ResourceQuery 上的实际生效（不只是纯函数）
# ---------------------------------------------------------------------------


def test_long_query_uses_fts_expression(seeded, monkeypatch) -> None:
    conn, fts_enabled = seeded
    if not fts_enabled:
        pytest.skip("当前 SQLite 构建未启用 FTS5/trigram")

    import core.query.queries as queries_mod

    seen: list[str] = []
    real = queries_mod.fts_match_expression
    monkeypatch.setattr(
        queries_mod,
        "fts_match_expression",
        lambda text: (seen.append(text), real(text))[1],
    )

    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="沙耶香")] == [1, 5]
    assert seen == ["沙耶香"]
    seen.clear()

    # 2 字查询不得触发 FTS
    assert [r.id for r in rq.list(query="沙耶")] == [1, 5]
    assert seen == []


def test_short_query_works_via_like(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="沙耶")] == [1, 5]
    assert [r.id for r in rq.list(query="沙")] == [1, 5]


def test_mixed_cjk_ascii_query(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="C沙耶香x")] == [5]  # >=3 字 -> FTS
    assert [r.id for r in rq.list(query="C沙")] == [5]        # 2 字 -> LIKE
    assert [r.id for r in rq.list(query="xyz")] == [5]


# ---------------------------------------------------------------------------
# FTS 回退
# ---------------------------------------------------------------------------


def test_fts_disabled_falls_back_to_like(seeded) -> None:
    conn, fts_enabled = seeded
    if not fts_enabled:
        pytest.skip("当前 SQLite 构建未启用 FTS5/trigram")
    rq = ResourceQuery(conn)
    queries = ["沙耶香", "沙耶", "佐仓杏子", "Sayaka", "Evaan", "ABC沙耶香xyz"]
    before = {q: [r.id for r in rq.list(query=q)] for q in queries}

    conn.execute("UPDATE app_meta SET value = '0' WHERE key = 'fts_enabled'")

    after = {q: [r.id for r in rq.list(query=q)] for q in queries}
    assert after == before, "FTS 关闭后结果必须与 FTS 路径一致（LIKE 回退）"

    value = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'fts_enabled'"
    ).fetchone()["value"]
    assert value == "0", "搜索本身不得改变 fts_enabled"


def test_fts_disabled_still_returns_correct_rows(seeded) -> None:
    conn, _ = seeded
    conn.execute("UPDATE app_meta SET value = '0' WHERE key = 'fts_enabled'")
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="沙耶香")] == [1, 5]
    assert [r.id for r in rq.list(query="佐仓杏子")] == [2]
    assert [r.id for r in rq.list(query="Evaan")] == [2]


# ---------------------------------------------------------------------------
# FTS 输入安全
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "needle",
    [
        '"',
        '""',
        '"""',
        '沙"耶',
        'a"b',
        "NEAR(",
        "AND",
        "OR",
        "NOT",
        "^x",
        "x*",
        "col:val",
        "{q}",
        "(x)",
        "a-b",
        "a_b",
        "50%",
        "*",
        ":",
        "-",
        "沙耶 香",
        "ABC沙耶香xyz",
        "  沙耶香  ",
    ],
)
def test_special_input_never_raises(seeded, needle) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    rows = rq.list(query=needle)
    assert isinstance(rows, list)
    assert rq.count(query=needle) == len(rows)


@pytest.mark.parametrize(
    "needle",
    [
        '沙" OR 1=1 --',
        '" OR "1" = "1',
        "* OR *",
        "NEAR(沙耶)",
        "沙耶 OR 佐仓",
        "%",
        "__",
        "沙%耶",
    ],
)
def test_injection_like_input_does_not_widen_results(seeded, needle) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert rq.list(query=needle) == []
    assert rq.count(query=needle) == 0


def test_multiword_query_is_a_literal_substring(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert rq.list(query="沙耶 香") == []
    assert rq.count(query="沙耶 香") == 0


def test_like_wildcards_are_literal(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert rq.list(query="%") == []
    assert rq.list(query="__") == []
    assert rq.list(query="沙%耶") == []


# ---------------------------------------------------------------------------
# 作者搜索（只走关系表）
# ---------------------------------------------------------------------------


def test_author_search_hits_related_resource(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resources WHERE author IS NOT NULL"
        ).fetchone()["c"]
        == 0
    ), "resources.author 是死列"
    assert [r.id for r in rq.list(query="Evaan")] == [2]


def test_author_search_matches_raw_name(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="Anonymous")] == [4]


def test_author_search_is_case_insensitive(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="evaan")] == [2]


def test_author_search_works_with_fts_disabled(seeded) -> None:
    conn, _ = seeded
    conn.execute("UPDATE app_meta SET value = '0' WHERE key = 'fts_enabled'")
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="Evaan")] == [2]


# ---------------------------------------------------------------------------
# 文件名 / 相对路径检索（Phase 1.4-A.1）
# ---------------------------------------------------------------------------


def test_filename_search_hits_when_parsed_name_differs(path_seeded) -> None:
    conn, _ = path_seeded
    rq = ResourceQuery(conn)
    # #1 解析名是日文「美樹さやか」，不含「沙耶香」→ 命中只能来自 relative_path
    assert "沙耶香" not in "美樹さやか"
    assert [r.id for r in rq.list(query="沙耶香")] == [1]
    assert [r.id for r in rq.list(query="沙耶")] == [1]
    # 简体「佐仓」与日文「佐倉」是不同字符 → 命中来自 relative_path
    assert [r.id for r in rq.list(query="佐仓杏子")] == [2]
    assert [r.id for r in rq.list(query="佐仓")] == [2]


def test_filename_search_by_directory_and_mod_name(path_seeded) -> None:
    conn, _ = path_seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="ExtraHair")] == [3]
    assert [r.id for r in rq.list(query="hair")] == [3]


def test_filename_search_does_not_search_absolute_path_or_key(path_seeded) -> None:
    conn, _ = path_seeded
    rq = ResourceQuery(conn)
    # file_path = D:/lib/N.png、file_path_key = d:/lib/N.png 都不是搜索字段
    assert rq.list(query="d:/lib") == []
    assert rq.list(query="/lib/1.png") == []


def test_filename_search_long_query_still_routes_path_through_like(
    path_seeded, monkeypatch
) -> None:
    conn, fts_enabled = path_seeded
    if not fts_enabled:
        pytest.skip("当前 SQLite 构建未启用 FTS5/trigram")

    import core.query.queries as queries_mod

    seen: list[str] = []
    real = queries_mod.fts_match_expression
    monkeypatch.setattr(
        queries_mod,
        "fts_match_expression",
        lambda text: (seen.append(text), real(text))[1],
    )
    rq = ResourceQuery(conn)

    # >=3 字：name/display 走 FTS，path 仍走 LIKE → 仍命中 path-only 的 #1
    assert [r.id for r in rq.list(query="沙耶香")] == [1]
    assert seen == ["沙耶香"]

    # 2 字：不调用 FTS
    seen.clear()
    assert [r.id for r in rq.list(query="沙耶")] == [1]
    assert seen == []


def test_filename_search_fts_on_off_consistent(path_seeded) -> None:
    conn, fts_enabled = path_seeded
    if not fts_enabled:
        pytest.skip("当前 SQLite 构建未启用 FTS5/trigram")
    rq = ResourceQuery(conn)
    queries = [
        "沙耶香",
        "沙耶",
        "佐仓杏子",
        "佐仓",
        "ExtraHair",
        "hair",
        "鹿目圆",
        "美樹さやか",
    ]
    before = {q: [r.id for r in rq.list(query=q)] for q in queries}

    conn.execute("UPDATE app_meta SET value = '0' WHERE key = 'fts_enabled'")

    after = {q: [r.id for r in rq.list(query=q)] for q in queries}
    assert after == before, "路径恒走 LIKE，FTS 开关不得改变结果集"


def test_filename_search_combines_with_filters(path_seeded) -> None:
    conn, _ = path_seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="沙耶香", resource_type="character_card")] == [1]
    assert rq.list(query="沙耶香", resource_type="mod") == []
    assert [r.id for r in rq.list(query="沙耶香", library_id=1)] == [1]
    assert rq.list(query="沙耶香", library_id=2) == []
    assert [r.id for r in rq.list(query="沙耶香", has_mods=True)] == [1]
    assert rq.list(query="沙耶香", has_mods=False) == []
    assert [r.id for r in rq.list(query="沙耶香", property_category="clothes")] == [1]
    assert rq.list(query="沙耶香", property_category="accessory") == []
    assert [r.id for r in rq.list(query="鹿目圆", needs_review=True)] == [4]
    assert rq.list(query="鹿目圆", needs_review=False) == []
    assert [
        r.id for r in rq.list(query="ExtraHair", resource_type="mod", library_id=2)
    ] == [3]
    assert rq.list(query="ExtraHair", library_id=1) == []


def test_filename_search_sort_and_pagination(path_seeded) -> None:
    conn, _ = path_seeded
    rq = ResourceQuery(conn)
    # 「魔法少女小圆」只出现在 #1/#2/#4 的 relative_path 里
    assert rq.count(query="魔法少女小圆") == 3
    assert [
        r.id for r in rq.list(query="魔法少女小圆", order_by="id", limit=2, offset=0)
    ] == [1, 2]
    assert [
        r.id for r in rq.list(query="魔法少女小圆", order_by="id", limit=2, offset=1)
    ] == [2, 4]
    assert [
        r.id
        for r in rq.list(query="魔法少女小圆", order_by="id", descending=True)
    ] == [4, 2, 1]


def test_filename_search_wildcards_are_literal(path_seeded) -> None:
    conn, _ = path_seeded
    rq = ResourceQuery(conn)
    # '%' / 复合串都不是通配符：没有路径含这些字面量
    assert rq.list(query="%") == []
    assert rq.list(query="沙%耶") == []
    assert rq.list(query="沙_耶") == []
    assert rq.list(query="___") == []
    assert rq.list(query='美"树') == []
    # '_' 不是「任意单字符」：只命中含**字面量下划线**的路径（目录名里的 A_/B_），
    # 若被当成通配符则会命中全部 4 个资源
    hits = {r.id for r in rq.list(query="_")}
    assert hits == {1, 2, 4}
    assert rq.count(query="_") == 3


@pytest.mark.parametrize(
    "needle", ["*", "(x)", "NEAR(", "col:val", "{q}", "a-b", "hair)", "Extra*Hair"]
)
def test_filename_search_special_input_never_raises(path_seeded, needle) -> None:
    conn, _ = path_seeded
    rq = ResourceQuery(conn)
    assert rq.count(query=needle) == len(rq.list(query=needle))


def test_filename_search_list_count_and_read_only(path_seeded) -> None:
    conn, _ = path_seeded
    rq = ResourceQuery(conn)
    before_changes = conn.total_changes
    before_flags = {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    }
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))

    cases = [
        {"query": "沙耶香"},
        {"query": "沙耶"},
        {"query": "佐仓杏子"},
        {"query": "ExtraHair"},
        {"query": "沙耶香", "library_id": 1},
        {"query": "沙耶香", "has_mods": True},
        {"query": "鹿目圆", "needs_review": True},
        {"query": "ExtraHair", "resource_type": "mod"},
    ]
    for scope in cases:
        assert rq.count(**scope) == len(rq.list(**scope)), scope

    assert conn.total_changes == before_changes
    assert {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    } == before_flags
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta


# ---------------------------------------------------------------------------
# 与结构化筛选组合
# ---------------------------------------------------------------------------


def test_query_combines_with_type(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="Sayaka")] == [3]
    assert [r.id for r in rq.list(query="Sayaka", resource_type="mod")] == [3]
    assert rq.list(query="Sayaka", resource_type="character_card") == []


def test_query_combines_with_library(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="沙耶香", library_id=1)] == [1, 5]
    assert rq.list(query="沙耶香", library_id=2) == []


def test_query_combines_with_needs_review(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="鹿目", needs_review=True)] == [4]
    assert rq.list(query="鹿目", needs_review=False) == []


def test_query_combines_with_property_category(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="佐仓", property_category="accessory")] == [2]
    assert rq.list(query="佐仓", property_category="clothes") == []
    assert [r.id for r in rq.list(query="沙耶香", property_category="clothes")] == [1]


def test_query_combines_with_has_mods(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert [r.id for r in rq.list(query="沙耶香", has_mods=True)] == [1]
    assert [r.id for r in rq.list(query="沙耶香", has_mods=False)] == [5]
    assert [r.id for r in rq.list(query="鹿目", has_mods=False)] == [4]


def test_query_with_sort_and_pagination(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    assert rq.count(query="沙耶香") == 2
    assert [r.id for r in rq.list(query="沙耶香", limit=1, offset=0)] == [1]
    assert [r.id for r in rq.list(query="沙耶香", limit=1, offset=1)] == [5]
    assert [
        r.id for r in rq.list(query="沙耶香", order_by="id", descending=True)
    ] == [5, 1]
    assert rq.count(query="沙耶香") == 2


def test_list_and_count_agree_across_combinations(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    cases = [
        {"query": None},
        {"query": ""},
        {"query": "沙耶香"},
        {"query": "沙耶"},
        {"query": "沙耶香", "library_id": 1},
        {"query": "沙耶香", "has_mods": True},
        {"query": "佐仓", "property_category": "accessory"},
        {"query": "鹿目", "needs_review": True},
        {"query": "Sayaka", "resource_type": "mod"},
        {"query": "Evaan"},
        {"query": "nope"},
    ]
    for scope in cases:
        assert rq.count(**scope) == len(rq.list(**scope)), scope


# ---------------------------------------------------------------------------
# 只读不变量
# ---------------------------------------------------------------------------


def test_search_is_read_only(seeded) -> None:
    conn, _ = seeded
    rq = ResourceQuery(conn)
    before_changes = conn.total_changes
    before_flags = {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    }
    before_meta = dict(conn.execute("SELECT key, value FROM app_meta"))

    for query in ("沙耶香", "沙耶", "Evaan", '"', "OR 1=1", "   ", None, "ABC沙耶香xyz"):
        rq.list(query=query)
        rq.count(query=query)

    assert conn.total_changes == before_changes, "Search Core 不得写库"
    assert {
        r["id"]: r["needs_review"]
        for r in conn.execute("SELECT id, needs_review FROM resources")
    } == before_flags
    assert dict(conn.execute("SELECT key, value FROM app_meta")) == before_meta


def test_schema_version_unchanged() -> None:
    assert schema_mod.SCHEMA_VERSION == 2
    assert sorted(schema_mod.MIGRATIONS) == [1, 2]


# ---------------------------------------------------------------------------
# 真实样本验证
# ---------------------------------------------------------------------------

_SAMPLE_SAYAKA = "B_带MOD角色卡/魔法少女小圆 - 美树沙耶香.png"
_SAMPLE_KYOKO = "B_带MOD角色卡/魔法少女小圆 - 佐仓杏子.png"

# 重要事实：真实卡片的**文件名**用中文，但卡片内解析出的 ``name``（来自
# Parameter 的 lastname/firstname）是**日文**。搜索字段是 ``name``/``display_name``，
# 不是文件路径 —— 所以本样本里「沙耶香/佐仓杏子」这类**文件名串搜不到**。
_SAYAKA_NAME = "美樹さやか"
_KYOKO_NAME = "佐倉杏子"


@pytest.fixture()
def real_db(tmp_path: Path, sample_root: Path):
    db_file = tmp_path / "samples.db"
    info = database.initialize(db_file)
    conn = database.connect(db_file)
    library = LibraryStore(conn).add(sample_root, name="真实样本")
    LibraryScanner(conn).scan(library.id)
    yield conn, bool(info["fts_enabled"])
    conn.close()


def _id_by_rel(conn, relative_path: str) -> int:
    row = conn.execute(
        "SELECT id FROM resources WHERE replace(relative_path, '\\', '/') = ?",
        (relative_path.replace("\\", "/"),),
    ).fetchone()
    assert row is not None, f"没有入库：{relative_path}"
    return int(row["id"])


def test_real_sample_filename_search_hits_via_relative_path(real_db) -> None:
    """文件名（中文）现在能命中；命中来自 ``relative_path`` —— 解析名仍是日文。"""
    conn, _ = real_db
    rq = ResourceQuery(conn)
    sayaka = _id_by_rel(conn, _SAMPLE_SAYAKA)
    row = conn.execute(
        "SELECT name, display_name, relative_path FROM resources WHERE id = ?",
        (sayaka,),
    ).fetchone()
    # 事实断言（Phase 1.4-A 保留）：解析名是日文，文件名是中文
    assert row["name"] == _SAYAKA_NAME
    assert row["display_name"] == _SAYAKA_NAME
    assert "沙耶香" in row["relative_path"], "文件名里确实是中文"
    assert "沙耶香" not in row["name"], "但解析名里没有该子串"
    # 事实断言（Phase 1.4-A 保留）：resources.author 是死列
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resources"
            " WHERE author IS NOT NULL AND author <> ''"
        ).fetchone()["c"]
        == 0
    )
    # Phase 1.4-A.1：按文件名串搜索命中该资源，且命中只能来自 relative_path
    assert sayaka in {r.id for r in rq.list(query="沙耶香")}


def test_real_sample_filename_queries_hit(real_db) -> None:
    """指令要求的三个文件名串都要命中对应资源。"""
    conn, _ = real_db
    rq = ResourceQuery(conn)
    sayaka = _id_by_rel(conn, _SAMPLE_SAYAKA)
    kyoko = _id_by_rel(conn, _SAMPLE_KYOKO)

    assert sayaka in {r.id for r in rq.list(query="沙耶香")}   # 3 字
    assert sayaka in {r.id for r in rq.list(query="沙耶")}     # 2 字
    assert kyoko in {r.id for r in rq.list(query="佐仓杏子")}  # 4 字（简体「仓」在文件名里）


def test_real_sample_three_and_two_char_queries(real_db) -> None:
    conn, fts_enabled = real_db
    if not fts_enabled:
        pytest.skip("当前 SQLite 构建未启用 FTS5/trigram")
    rq = ResourceQuery(conn)
    sayaka = _id_by_rel(conn, _SAMPLE_SAYAKA)
    kyoko = _id_by_rel(conn, _SAMPLE_KYOKO)

    # 3 字（日文假名）→ FTS
    assert plan_search("さやか", fts_available=True).mode == SEARCH_MODE_FTS
    assert sayaka in {r.id for r in rq.list(query="さやか")}
    # 2 字 → LIKE
    assert plan_search("さや", fts_available=True).mode == SEARCH_MODE_LIKE
    assert sayaka in {r.id for r in rq.list(query="さや")}
    # 4 字（日文汉字）→ FTS
    assert {r.id for r in rq.list(query=_KYOKO_NAME)} == {kyoko}
    # 2 字 → LIKE
    assert {r.id for r in rq.list(query="杏子")} == {kyoko}


def test_real_sample_routing_uses_fts_for_three_chars(real_db, monkeypatch) -> None:
    conn, fts_enabled = real_db
    if not fts_enabled:
        pytest.skip("当前 SQLite 构建未启用 FTS5/trigram")

    import core.query.queries as queries_mod

    seen: list[str] = []
    real = queries_mod.fts_match_expression
    monkeypatch.setattr(
        queries_mod,
        "fts_match_expression",
        lambda text: (seen.append(text), real(text))[1],
    )
    rq = ResourceQuery(conn)

    rq.list(query="さやか")
    assert seen == ["さやか"]
    seen.clear()

    rq.list(query="さや")
    assert seen == []


def test_real_sample_author_search(real_db) -> None:
    conn, _ = real_db
    rq = ResourceQuery(conn)
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resources"
            " WHERE author IS NOT NULL AND author <> ''"
        ).fetchone()["c"]
        == 0
    )
    evaan = {r.id for r in rq.list(query="Evaan")}
    assert len(evaan) == 5


def test_real_sample_fts_disabled_matches_like(real_db) -> None:
    conn, fts_enabled = real_db
    if not fts_enabled:
        pytest.skip("当前 SQLite 构建未启用 FTS5/trigram")
    rq = ResourceQuery(conn)
    queries = [
        "さやか",
        "さや",
        _KYOKO_NAME,
        "杏子",
        "沙耶香",
        "沙耶",
        "佐仓杏子",
        "Evaan",
        "Kugisaki",
        "a-b",
        "(B)",
    ]
    before = {q: [r.id for r in rq.list(query=q)] for q in queries}

    conn.execute("UPDATE app_meta SET value = '0' WHERE key = 'fts_enabled'")

    after = {q: [r.id for r in rq.list(query=q)] for q in queries}
    assert after == before
    assert (
        conn.execute(
            "SELECT value FROM app_meta WHERE key = 'fts_enabled'"
        ).fetchone()["value"]
        == "0"
    )


def test_real_sample_search_is_read_only(real_db) -> None:
    conn, _ = real_db
    rq = ResourceQuery(conn)
    before_changes = conn.total_changes
    before_flags = conn.execute(
        "SELECT count(*) AS c FROM resources WHERE needs_review = 1"
    ).fetchone()["c"]

    for query in (
        "さやか",
        "さや",
        _KYOKO_NAME,
        "杏子",
        "沙耶香",
        "佐仓杏子",
        "Evaan",
        '"',
        "OR 1=1 --",
        "   ",
    ):
        rq.list(query=query)
        rq.count(query=query)

    assert conn.total_changes == before_changes
    assert before_flags == 0
    assert (
        conn.execute(
            "SELECT count(*) AS c FROM resources WHERE needs_review = 1"
        ).fetchone()["c"]
        == 0
    )
