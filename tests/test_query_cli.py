"""Phase 1.3-B：``python main.py query ...`` CLI 验收测试。

CLI 是 Query Layer 的薄适配层：这里既验证命令可用性 / 输出 / JSON / 错误处理，
也验证「CLI 结果 == Query Layer DTO」以及「CLI 不改数据库」。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main as cli  # noqa: E402
import cli_query as cli_query_module  # noqa: E402
from core.app import TagWriteService  # noqa: E402
from core.database import db as database  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.query import ModQuery, ResourceQuery, TagQuery  # noqa: E402
from core.scanner import LibraryScanner  # noqa: E402
from tests import builders  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def cli_lib(tmp_path: Path, monkeypatch) -> Path:
    """在重定向的数据目录里造一个可控资源库并扫描入库，返回 data_dir。"""
    data_dir = tmp_path / "appdata"
    monkeypatch.setenv("KKS_RM_DATA_DIR", str(data_dir))
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
    builders.write_card(
        root / "cardE.png",
        lastname="E",
        firstname="Card",
        plugin_guids=("moreAccessories",),
        dependencies=(("com.x.makeup", "ChaFileMakeup.PaintID1", 405),),
    )
    builders.write_zipmod(root / "body.zipmod", "com.x.body", name="Body")
    builders.write_zipmod(root / "cloth.zipmod", "com.x.cloth", name="Cloth")
    builders.write_zipmod(root / "makeup.zipmod", "com.x.makeup", name="Makeup")
    builders.write_zipmod(root / "orphan.zipmod", "com.orphan", name="Orphan")

    assert cli.main(["library", "add", str(root)]) == 0
    assert cli.main(["scan"]) == 0
    return data_dir


def _json_out(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


# ---------------------------------------------------------------------------
# 合成场景：命令可用性
# ---------------------------------------------------------------------------


def test_query_resources_and_filters(cli_lib, capsys):
    capsys.readouterr()
    assert cli.main(["query", "resources", "--json"]) == 0
    payload = _json_out(capsys)
    assert payload["count"] == 9  # 5 张卡 + 4 个 zipmod 都是资源
    assert {r["resource_type"] for r in payload["resources"]} == {
        "character_card",
        "mod",
    }

    assert cli.main(["query", "resources", "--type", "character_card", "--json"]) == 0
    assert _json_out(capsys)["count"] == 5

    assert cli.main(["query", "resources", "--game", "KKS", "--json"]) == 0
    assert _json_out(capsys)["count"] == 5

    assert cli.main(
        ["query", "resources", "--type", "character_card", "--without-mods", "--json"]
    ) == 0
    modless = _json_out(capsys)
    assert modless["count"] == 1
    assert modless["resources"][0]["title"] == "DCard"

    assert cli.main(
        ["query", "resources", "--type", "character_card", "--with-mods", "--json"]
    ) == 0
    assert _json_out(capsys)["count"] == 4


def test_query_resource_detail_and_relations(cli_lib, capsys):
    capsys.readouterr()
    # resource 详情
    assert cli.main(["query", "resource", "cardA.png", "--json"]) == 0
    detail = _json_out(capsys)
    assert detail["resource"]["name"] == "ACard"
    assert {m["mod_guid"] for m in detail["mods"]} == {"com.x.body", "com.x.cloth"}
    assert "moreAccessories" in detail["plugins"]
    assert detail["metadata"]["authors_raw"] == ["Alice", "[Unknown]"]

    # resource-mods
    assert cli.main(["query", "resource-mods", "cardA.png", "--json"]) == 0
    mods = _json_out(capsys)
    assert mods["count"] == 2

    # resource-plugins
    assert cli.main(["query", "resource-plugins", "cardA.png", "--json"]) == 0
    plugins = _json_out(capsys)
    assert "KSOX" in plugins["plugins"]

    # resource-authors
    assert cli.main(["query", "resource-authors", "cardA.png", "--json"]) == 0
    authors = _json_out(capsys)
    assert authors["authors"][0]["name"] == "Alice"
    assert authors["authors_raw"] == ["Alice", "[Unknown]"]


def test_query_mods_and_relations(cli_lib, capsys):
    capsys.readouterr()
    assert cli.main(["query", "mods", "--json"]) == 0
    mods = _json_out(capsys)
    assert mods["count"] == 4  # com.x.body / com.x.cloth / com.x.makeup / com.orphan

    assert cli.main(["query", "mod", "com.x.body", "--json"]) == 0
    mod = _json_out(capsys)
    assert mod["mod"]["installed"] is True
    assert mod["mod"]["used_by_count"] == 2

    assert cli.main(["query", "mod-resources", "com.x.body", "--json"]) == 0
    assert _json_out(capsys)["count"] == 2

    assert cli.main(["query", "mod-usages", "com.x.body", "--json"]) == 0
    usages = _json_out(capsys)
    assert usages["count"] == 2
    assert {u["slot"] for u in usages["usages"]} == {7426, 7427}


def test_query_authors(cli_lib, capsys):
    capsys.readouterr()
    assert cli.main(["query", "authors", "--json"]) == 0
    authors = {a["name"]: a["resource_count"] for a in _json_out(capsys)["authors"]}
    assert authors == {"Alice": 2, "Bob": 1}

    assert cli.main(["query", "author", "Bob", "--json"]) == 0
    assert _json_out(capsys)["author"]["name"] == "Bob"

    assert cli.main(["query", "author-resources", "alice", "--json"]) == 0
    assert _json_out(capsys)["count"] == 2


def test_query_plugins(cli_lib, capsys):
    capsys.readouterr()
    assert cli.main(["query", "plugins", "--json"]) == 0
    plugins = {p["plugin_guid"]: p["resource_count"] for p in _json_out(capsys)["plugins"]}
    assert plugins["KSOX"] == 2

    assert cli.main(["query", "plugin", "KSOX", "--json"]) == 0
    assert _json_out(capsys)["plugin"]["resource_count"] == 2

    assert cli.main(["query", "plugin-resources", "KSOX", "--json"]) == 0
    assert _json_out(capsys)["count"] == 2


def test_query_missing_and_orphan(cli_lib, capsys):
    capsys.readouterr()
    assert cli.main(["query", "missing-mods", "--json"]) == 0
    missing = {m["guid"] for m in _json_out(capsys)["mods"]}
    assert missing == {"com.missing", "com.weird"}

    assert cli.main(["query", "orphan-mods", "--json"]) == 0
    orphan = _json_out(capsys)
    assert orphan["count"] == 1 and orphan["mods"][0]["guid"] == "com.orphan"


def test_query_usages_and_categories(cli_lib, capsys):
    capsys.readouterr()
    assert cli.main(["query", "usages", "--json"]) == 0
    assert _json_out(capsys)["count"] == 6

    assert cli.main(["query", "usage-categories", "--json"]) == 0
    cats = {c["category"]: c for c in _json_out(capsys)["categories"]}
    assert cats["body"]["usage_count"] == 3
    assert cats["makeup"]["usage_count"] == 1
    assert cats["unknown"]["usage_count"] == 1

    # makeup 语义
    assert cli.main(["query", "usages", "--category", "makeup", "--json"]) == 0
    assert _json_out(capsys)["count"] == 1

    # unknown property 保留
    assert cli.main(["query", "unknown-properties", "--json"]) == 0
    unknown = _json_out(capsys)
    assert unknown["properties"] == ["Totally.Different"]


def test_query_empty_result_is_success(cli_lib, capsys):
    capsys.readouterr()
    assert cli.main(["query", "usages", "--category", "hair"]) == 0
    out = capsys.readouterr().out
    assert "(no results)" in out


def test_query_not_found_is_not_traceback(cli_lib, capsys):
    capsys.readouterr()
    assert cli.main(["query", "resource", "999999"]) == 1
    assert "Resource not found: 999999" in capsys.readouterr().err
    assert cli.main(["query", "mod", "nope"]) == 1
    assert "MOD not found: nope" in capsys.readouterr().err
    assert cli.main(["query", "plugin", "nope"]) == 1
    assert "Plugin not found: nope" in capsys.readouterr().err
    assert cli.main(["query", "author", "nobody"]) == 1
    assert "Author not found: nobody" in capsys.readouterr().err


def test_query_argument_errors_exit_2(cli_lib, capsys):
    capsys.readouterr()
    assert cli.main(["query", "resources", "--category", "bogus"]) == 2
    assert "参数错误" in capsys.readouterr().err
    assert cli.main(["query", "resources", "--game", "XXX"]) == 2
    assert "参数错误" in capsys.readouterr().err
    assert cli.main(["query", "resources", "--order", "bogus"]) == 2
    assert "参数错误" in capsys.readouterr().err


def test_cli_matches_query_layer_dto(cli_lib, capsys):
    capsys.readouterr()
    conn = database.connect(cli_lib / "kks_resource_manager.db")
    try:
        expected_ids = [r.id for r in ResourceQuery(conn).list()]
        expected_used_by = ModQuery(conn).get("com.x.body").used_by_count
    finally:
        conn.close()

    assert cli.main(["query", "resources", "--json"]) == 0
    assert [r["id"] for r in _json_out(capsys)["resources"]] == expected_ids

    assert cli.main(["query", "mod", "com.x.body", "--json"]) == 0
    assert _json_out(capsys)["mod"]["used_by_count"] == expected_used_by


def test_cli_does_not_modify_database(cli_lib, capsys):
    db_file = cli_lib / "kks_resource_manager.db"
    before = _sha256(db_file)
    capsys.readouterr()
    for argv in (
        ["query", "resources"],
        ["query", "resource", "1"],
        ["query", "mods"],
        ["query", "missing-mods"],
        ["query", "orphan-mods"],
        ["query", "duplicates"],
        ["query", "usage-categories"],
        ["query", "unknown-properties"],
        ["query", "usages", "--limit", "3"],
    ):
        assert cli.main(argv) == 0
    capsys.readouterr()
    assert _sha256(db_file) == before, "CLI 查询不得修改数据库"


# ---------------------------------------------------------------------------
# Phase 2.3-B：byte-duplicate CLI surfacing
# ---------------------------------------------------------------------------


_RESOURCE_JSON_KEYS = {
    "id",
    "resource_type",
    "name",
    "display_name",
    "title",
    "game",
    "card_marker",
    "file_path",
    "relative_path",
    "extension",
    "file_size",
    "modified_time",
    "library_id",
    "scan_status",
    "parse_status",
    "needs_review",
    "mod_count",
    "usage_count",
    "plugin_count",
    "author_count",
    "sha256",
}


@pytest.fixture()
def cli_dup(tmp_path: Path, monkeypatch) -> Path:
    """重定向数据目录；造出恰好 1 组 byte-duplicate（两文件字节完全相同）+ 1 个单例。"""
    data_dir = tmp_path / "appdata_dup"
    monkeypatch.setenv("KKS_RM_DATA_DIR", str(data_dir))
    root = tmp_path / "lib_dup"
    sub = root / "sub"
    sub.mkdir(parents=True)
    builders.write_card(root / "sameA.png", lastname="Same", firstname="Dup")
    builders.write_card(sub / "sameB.png", lastname="Same", firstname="Dup")
    builders.write_card(root / "unique.png", lastname="Only", firstname="Solo")
    assert cli.main(["library", "add", str(root)]) == 0
    assert cli.main(["scan"]) == 0
    return data_dir


def test_query_duplicates_default_output(cli_dup, capsys):
    """``query duplicates`` 默认输出：分组哈希、成员数、成员的 id / 标题 / 路径。"""
    capsys.readouterr()
    assert cli.main(["query", "duplicates"]) == 0
    out = capsys.readouterr().out
    assert "Byte-duplicate groups: 1" in out
    assert "members=2" in out
    assert "字节完全相同" in out
    assert "sameA.png" in out and "sameB.png" in out
    assert "unique.png" not in out, "单例资源不得出现在重复组里"


def test_query_duplicates_json_shape(cli_dup, capsys):
    """``query duplicates --json``：稳定结构 {count, groups:[{sha256, member_count, resources}]}。"""
    capsys.readouterr()
    assert cli.main(["query", "duplicates", "--json"]) == 0
    payload = _json_out(capsys)
    assert set(payload) == {"count", "groups"}
    assert payload["count"] == 1
    group = payload["groups"][0]
    assert set(group) == {"sha256", "member_count", "resources"}
    assert group["member_count"] == 2 == len(group["resources"])
    assert re.fullmatch(r"[0-9a-f]{64}", group["sha256"])
    for resource in group["resources"]:
        assert _RESOURCE_JSON_KEYS <= set(resource)
        assert resource["sha256"] == group["sha256"]


def test_query_duplicates_matches_query_layer_dto(cli_dup, capsys):
    """JSON 必须与 Query Layer 的 DuplicateGroup 数据一致（CLI 不自己分组）。"""
    conn = database.connect(cli_dup / "kks_resource_manager.db")
    try:
        expected = ResourceQuery(conn).duplicates()
    finally:
        conn.close()

    capsys.readouterr()
    assert cli.main(["query", "duplicates", "--json"]) == 0
    payload = _json_out(capsys)

    assert payload["count"] == len(expected) == 1
    assert [g["sha256"] for g in payload["groups"]] == [g.sha256 for g in expected]
    assert [g["member_count"] for g in payload["groups"]] == [
        g.member_count for g in expected
    ]
    assert [[r["id"] for r in g["resources"]] for g in payload["groups"]] == [
        [r.id for r in g.resources] for g in expected
    ]


def test_query_duplicates_members_are_byte_identical(cli_dup, capsys):
    """组成员确实是同一份字节（文件 sha256 与组键一致）。"""
    capsys.readouterr()
    assert cli.main(["query", "duplicates", "--json"]) == 0
    group = _json_out(capsys)["groups"][0]
    paths = {Path(r["file_path"]) for r in group["resources"]}
    assert {p.name for p in paths} == {"sameA.png", "sameB.png"}
    assert {_sha256(p) for p in paths} == {group["sha256"]}


def test_query_duplicates_empty_when_no_duplicates(cli_lib, capsys):
    """没有 byte-duplicate 时：JSON 返回空列表，人类可读给出合理提示，不报错。"""
    capsys.readouterr()
    assert cli.main(["query", "duplicates", "--json"]) == 0
    assert _json_out(capsys) == {"count": 0, "groups": []}

    capsys.readouterr()
    assert cli.main(["query", "duplicates"]) == 0
    assert "no results" in capsys.readouterr().out.lower()


def test_query_duplicates_excludes_null_sha256(cli_dup, capsys):
    """``sha256 IS NULL`` 的资源不参与分组；组因此只剩 1 人 ⇒ 不成组。"""
    conn = database.connect(cli_dup / "kks_resource_manager.db")
    try:
        row = conn.execute(
            "SELECT id FROM resources WHERE file_path LIKE '%sameB.png'"
        ).fetchone()
        assert row is not None
        conn.execute("UPDATE resources SET sha256 = NULL WHERE id = ?", (row["id"],))
        conn.commit()
    finally:
        conn.close()

    capsys.readouterr()
    assert cli.main(["query", "duplicates", "--json"]) == 0
    assert _json_out(capsys) == {"count": 0, "groups": []}


def test_query_resource_json_includes_sha256(cli_lib, capsys):
    """``query resource --json`` 新增 sha256（且既有字段全部保留）。"""
    capsys.readouterr()
    assert cli.main(["query", "resource", "cardA.png", "--json"]) == 0
    resource = _json_out(capsys)["resource"]
    assert resource["sha256"] == _sha256(Path(resource["file_path"]))
    assert _RESOURCE_JSON_KEYS <= set(resource)


def test_query_resources_json_includes_sha256(cli_lib, capsys):
    """``query resources --json`` 每行新增 sha256（additive-only）。"""
    capsys.readouterr()
    assert cli.main(["query", "resources", "--json"]) == 0
    payload = _json_out(capsys)
    assert payload["count"] == 9
    for resource in payload["resources"]:
        assert _RESOURCE_JSON_KEYS <= set(resource)
        assert re.fullmatch(r"[0-9a-f]{64}", resource["sha256"])


def test_query_duplicates_does_not_modify_database(cli_dup, capsys):
    """``query duplicates`` 前后数据库字节完全一致（只读）。"""
    db_file = cli_dup / "kks_resource_manager.db"
    before = _sha256(db_file)
    capsys.readouterr()
    assert cli.main(["query", "duplicates"]) == 0
    assert cli.main(["query", "duplicates", "--json"]) == 0
    capsys.readouterr()
    assert _sha256(db_file) == before, "CLI 查询不得修改数据库"


def test_cli_has_no_sql_and_no_sqlite_access():
    """架构约束（静态）：CLI 不直接访问 sqlite3、不自带 SQL、不自己分组。"""
    source = Path(cli_query_module.__file__).read_text(encoding="utf-8")
    assert "sqlite3" not in source, "CLI 不得直接访问 sqlite3"
    assert not re.search(
        r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|GROUP BY)\b", source
    ), "CLI 不得自己写 SQL / 自己分组"
    assert "duplicates()" in source, "重复查询必须复用 Query Layer"


# ---------------------------------------------------------------------------
# 真实样本验收
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sample_data_dir(tmp_path_factory: pytest.TempPathFactory, sample_root: Path) -> Path:
    data_dir = tmp_path_factory.mktemp("cli_sample")
    db_file = data_dir / "kks_resource_manager.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        library = LibraryStore(conn).add(sample_root, name="真实样本")
        LibraryScanner(conn).scan(library.id)
    finally:
        conn.close()
    return data_dir


@pytest.fixture()
def sample_cli(monkeypatch, sample_data_dir: Path) -> Path:
    monkeypatch.setenv("KKS_RM_DATA_DIR", str(sample_data_dir))
    return sample_data_dir


def test_sample_cli_resources_and_baseline(sample_cli, capsys):
    capsys.readouterr()
    assert cli.main(["query", "resources", "--json"]) == 0
    payload = _json_out(capsys)
    assert payload["count"] == 35
    assert sum(1 for r in payload["resources"] if r["resource_type"] == "character_card") == 22
    assert sum(1 for r in payload["resources"] if r["resource_type"] == "mod") == 13


def test_sample_cli_game_filter(sample_cli, capsys):
    capsys.readouterr()
    assert cli.main(["query", "resources", "--game", "KKS", "--json"]) == 0
    kks = _json_out(capsys)
    assert kks["count"] == 21 and all(r["game"] == "KKS" for r in kks["resources"])

    assert cli.main(["query", "resources", "--game", "KK", "--json"]) == 0
    assert _json_out(capsys)["count"] == 1


def test_sample_cli_missing_and_orphan(sample_cli, capsys):
    capsys.readouterr()
    assert cli.main(["query", "missing-mods", "--json"]) == 0
    assert _json_out(capsys)["count"] == 134

    assert cli.main(["query", "orphan-mods", "--json"]) == 0
    orphan = _json_out(capsys)
    assert orphan["count"] == 3
    assert {m["guid"] for m in orphan["mods"]} == {
        "NoHair",
        "elven_panst",
        "koikatu.AltSlot.co_bot_19",
    }


def test_sample_cli_category_totals(sample_cli, capsys):
    capsys.readouterr()
    assert cli.main(["query", "usage-categories", "--json"]) == 0
    cats = {c["category"]: c["usage_count"] for c in _json_out(capsys)["categories"]}
    assert cats == {
        "face": 62,
        "body": 25,
        "clothes": 280,
        "accessory": 1129,
        "hair": 18,
        "makeup": 13,
        "unknown": 0,
    }

    assert cli.main(["query", "usages", "--category", "makeup", "--json"]) == 0
    assert _json_out(capsys)["count"] == 13

    assert cli.main(["query", "unknown-properties", "--json"]) == 0
    assert _json_out(capsys)["count"] == 0


def test_sample_cli_shared_mod_and_modless_cards(sample_cli, capsys):
    capsys.readouterr()
    assert cli.main(["query", "mod-resources", "com.Quokka.naginata", "--json"]) == 0
    assert _json_out(capsys)["count"] == 2

    assert cli.main(
        ["query", "resources", "--type", "character_card", "--without-mods", "--json"]
    ) == 0
    assert _json_out(capsys)["count"] == 2


def test_sample_cli_does_not_modify_database(sample_cli, capsys):
    db_file = sample_cli / "kks_resource_manager.db"
    before = _sha256(db_file)
    capsys.readouterr()
    for argv in (
        ["query", "resources"],
        ["query", "resource", "1"],
        ["query", "mods"],
        ["query", "authors"],
        ["query", "plugins"],
        ["query", "missing-mods"],
        ["query", "orphan-mods"],
        ["query", "duplicates"],
        ["query", "usage-categories"],
    ):
        assert cli.main(argv) == 0
    capsys.readouterr()
    assert _sha256(db_file) == before, "真实样本 CLI 查询不得修改数据库"


# ---------------------------------------------------------------------------
# Phase 3.3 —— CLI 最小只读筛选入口（T-O / T-P / T-S）
# ---------------------------------------------------------------------------


def _seed_cli_tags(data_dir: Path) -> dict:
    """用户 Tag ``Alpha`` → 两张 ``character_card``；Favorite → 第 2 张卡 + 第 1 个 MOD。

    按 ``resource_type`` 选取（而非按 id 位置），避免依赖扫描入库顺序。
    写侧经 ``TagWriteService``（Phase 3.2 唯一 writer）；测试后续的读侧全程只读。
    """
    conn = database.connect(data_dir / "kks_resource_manager.db")
    try:
        cards = [row.id for row in ResourceQuery(conn).list(resource_type="character_card")]
        mods = [row.id for row in ResourceQuery(conn).list(resource_type="mod")]
        writer = TagWriteService(conn)
        alpha = writer.create_tag("Alpha")
        writer.assign_tag(cards[0], alpha)
        writer.assign_tag(cards[1], alpha)
        writer.set_favorite(cards[1], True)
        writer.set_favorite(mods[0], True)
        return {
            "alpha": alpha,
            "cards": cards,
            "mods": mods,
            "favorites": sorted([cards[1], mods[0]]),
        }
    finally:
        conn.close()


def test_query_resources_tag_matches_query_layer(cli_lib, capsys):
    seeded = _seed_cli_tags(cli_lib)
    capsys.readouterr()

    assert cli.main(["query", "resources", "--tag", "Alpha", "--json"]) == 0
    payload = _json_out(capsys)

    conn = database.connect(cli_lib / "kks_resource_manager.db")
    try:
        expected = [row.id for row in ResourceQuery(conn).list(tag_id=seeded["alpha"])]
    finally:
        conn.close()

    assert [r["id"] for r in payload["resources"]] == expected
    assert payload["count"] == len(expected) == 2
    assert payload["scope"]["tag_id"] == seeded["alpha"]
    assert "favorite" not in payload["scope"]


def test_query_resources_tag_accepts_casing_and_exact_name_only(cli_lib, capsys):
    _seed_cli_tags(cli_lib)
    capsys.readouterr()
    # 大小写不敏感（精确 name_key）
    assert cli.main(["query", "resources", "--tag", "alpha", "--json"]) == 0
    assert _json_out(capsys)["count"] == 2
    # 非模糊 / 非前缀：不命中就是 not-found（退出码 1）
    assert cli.main(["query", "resources", "--tag", "Alph"]) == 1
    assert "Tag not found: Alph" in capsys.readouterr().err
    assert cli.main(["query", "resources", "--tag", "Alpha%"]) == 1
    assert "Tag not found: Alpha%" in capsys.readouterr().err


def test_query_resources_favorite_and_no_favorite(cli_lib, capsys):
    seeded = _seed_cli_tags(cli_lib)
    all_ids = seeded["cards"] + seeded["mods"]
    capsys.readouterr()

    assert cli.main(["query", "resources", "--favorite", "--json"]) == 0
    payload = _json_out(capsys)
    assert payload["scope"]["favorite"] is True
    assert [r["id"] for r in payload["resources"]] == seeded["favorites"]

    assert cli.main(["query", "resources", "--no-favorite", "--json"]) == 0
    payload = _json_out(capsys)
    assert payload["scope"]["favorite"] is False
    returned = {r["id"] for r in payload["resources"]}
    assert returned == set(all_ids) - set(seeded["favorites"])


def test_query_resources_scope_only_lists_provided_filters(cli_lib, capsys):
    seeded = _seed_cli_tags(cli_lib)
    capsys.readouterr()

    assert cli.main(["query", "resources", "--json"]) == 0
    scope = _json_out(capsys)["scope"]
    assert "tag_id" not in scope
    assert "favorite" not in scope

    # 与新参数同用时，scope 与既有键遵循同一条「非 None 才输出」规则。
    assert cli.main(
        ["query", "resources", "--tag", "Alpha", "--favorite", "--json"]
    ) == 0
    payload = _json_out(capsys)
    assert payload["scope"] == {"tag_id": seeded["alpha"], "favorite": True}
    assert [r["id"] for r in payload["resources"]] == [seeded["cards"][1]]


def test_query_resources_new_filters_combine_with_existing_ones_as_and(
    cli_lib, capsys
):
    seeded = _seed_cli_tags(cli_lib)
    capsys.readouterr()

    assert cli.main(
        ["query", "resources", "--tag", "Alpha", "--type", "character_card", "--json"]
    ) == 0
    assert _json_out(capsys)["count"] == 2

    assert cli.main(
        ["query", "resources", "--tag", "Alpha", "--type", "mod", "--json"]
    ) == 0
    payload = _json_out(capsys)
    assert payload["count"] == 0
    assert payload["resources"] == []
    assert payload["scope"]["tag_id"] == seeded["alpha"]
    assert payload["scope"]["resource_type"] == "mod"


def test_query_resources_tag_not_found_is_not_traceback(cli_lib, capsys):
    capsys.readouterr()
    # 文本模式
    assert cli.main(["query", "resources", "--tag", "NoSuchTag"]) == 1
    captured = capsys.readouterr()
    assert "Tag not found: NoSuchTag" in captured.err
    assert captured.out == ""
    # JSON 模式同样不输出任何内容
    assert cli.main(["query", "resources", "--tag", "NoSuchTag", "--json"]) == 1
    captured = capsys.readouterr()
    assert "Tag not found: NoSuchTag" in captured.err
    assert captured.out == ""
    # 空 / 纯空白名称归一化后为空 ⇒ 同样 not-found
    assert cli.main(["query", "resources", "--tag", "   "]) == 1
    assert "Tag not found:" in capsys.readouterr().err


def test_query_resources_empty_result_with_new_filters_is_success(
    cli_lib, capsys
):
    seeded = _seed_cli_tags(cli_lib)
    capsys.readouterr()

    assert cli.main(["query", "resources", "--tag", "Alpha", "--type", "mod"]) == 0
    assert "(no results)" in capsys.readouterr().out

    assert cli.main(
        ["query", "resources", "--tag", "Alpha", "--type", "mod", "--json"]
    ) == 0
    payload = _json_out(capsys)
    assert payload["count"] == 0
    assert payload["resources"] == []
    assert payload["scope"]["tag_id"] == seeded["alpha"]


def test_query_resources_favorite_flags_are_mutually_exclusive(cli_lib):
    _seed_cli_tags(cli_lib)
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["query", "resources", "--favorite", "--no-favorite"])
    assert excinfo.value.code == 2


def test_query_resources_new_filters_do_not_modify_database(cli_lib, capsys):
    _seed_cli_tags(cli_lib)
    db_file = cli_lib / "kks_resource_manager.db"
    before = _sha256(db_file)
    conn = database.connect(db_file)
    try:
        before_tag_keys = [tag.name_key for tag in TagQuery(conn).list()]
    finally:
        conn.close()

    capsys.readouterr()
    for argv in (
        ["query", "resources", "--tag", "Alpha"],
        ["query", "resources", "--favorite"],
        ["query", "resources", "--no-favorite"],
        ["query", "resources", "--tag", "Alpha", "--favorite", "--json"],
        ["query", "resources", "--tag", "NoSuchTag"],
        ["query", "resources", "--tag", "   "],
    ):
        cli.main(argv)
    capsys.readouterr()

    assert _sha256(db_file) == before, "新增只读筛选不得修改数据库文件"
    conn = database.connect(db_file)
    try:
        # 读路径不得创建任何 Tag（含 not-found 分支与系统 Tag bootstrap）
        assert [tag.name_key for tag in TagQuery(conn).list()] == before_tag_keys
    finally:
        conn.close()
