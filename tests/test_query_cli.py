"""Phase 1.3-B：``python main.py query ...`` CLI 验收测试。

CLI 是 Query Layer 的薄适配层：这里既验证命令可用性 / 输出 / JSON / 错误处理，
也验证「CLI 结果 == Query Layer DTO」以及「CLI 不改数据库」。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main as cli  # noqa: E402
from core.database import db as database  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.query import ModQuery, ResourceQuery  # noqa: E402
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
        ["query", "usage-categories"],
        ["query", "unknown-properties"],
        ["query", "usages", "--limit", "3"],
    ):
        assert cli.main(argv) == 0
    capsys.readouterr()
    assert _sha256(db_file) == before, "CLI 查询不得修改数据库"


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
        ["query", "usage-categories"],
    ):
        assert cli.main(argv) == 0
    capsys.readouterr()
    assert _sha256(db_file) == before, "真实样本 CLI 查询不得修改数据库"
