"""Phase 3.5.1 —— Tag / Favorite CLI 入口与启动引导测试。

所有写命令都通过真实 CLI → Query 解析 → TagWriteService → SQLite 路径执行。
测试数据库通过 ``KKS_RM_DATA_DIR`` 重定向到 ``tmp_path``。
"""

from __future__ import annotations

from pathlib import Path

import pytest

import main as cli
from core.database import db as database
from core.database import schema as schema_mod
from core.models import FAVORITE_TAG_KEY


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch) -> Path:
    target = tmp_path / "appdata"
    monkeypatch.setenv("KKS_RM_DATA_DIR", str(target))
    return target


def _seed_resource(name: str = "Alice") -> int:
    database.initialize()
    conn = database.connect()
    try:
        path = f"D:/cards/{name.casefold()}.png"
        cursor = conn.execute(
            "INSERT INTO resources("
            " resource_type, type_source, name, file_path, file_path_key,"
            " relative_path, extension, scan_status, parse_status, needs_review)"
            " VALUES ('character_card', 'auto', ?, ?, ?, ?, '.png',"
            " 'present', 'ok', 0)",
            (
                name,
                path,
                database.normalize_path_key(path),
                f"{name.casefold()}.png",
            ),
        )
        return int(cursor.lastrowid)
    finally:
        conn.close()


def _tag_rows() -> list[dict]:
    conn = database.connect()
    try:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT id, name, name_key, color, category FROM tags"
                " ORDER BY name_key, id"
            ).fetchall()
        ]
    finally:
        conn.close()


def _resource_tag_keys(resource_id: int) -> list[str]:
    conn = database.connect()
    try:
        return [
            str(row["name_key"])
            for row in conn.execute(
                "SELECT t.name_key FROM resource_tags rt"
                " JOIN tags t ON t.id = rt.tag_id"
                " WHERE rt.resource_id = ? ORDER BY t.name_key",
                (resource_id,),
            ).fetchall()
        ]
    finally:
        conn.close()


def test_startup_bootstraps_favorite_idempotently(data_dir: Path, capsys):
    assert cli.main(["library", "list"]) == 0
    capsys.readouterr()

    assert cli.main(["tag", "list"]) == 0
    out = capsys.readouterr().out
    assert "Favorite" in out
    assert "yes" in out

    favorite_rows = [
        row for row in _tag_rows() if row["name_key"] == FAVORITE_TAG_KEY
    ]
    assert len(favorite_rows) == 1
    assert favorite_rows[0]["name"] == "Favorite"
    assert schema_mod.SCHEMA_VERSION == 2
    assert sorted(schema_mod.MIGRATIONS) == [1, 2]
    assert len(schema_mod.CURRENT_TABLES) == 16


def test_tag_create_and_list(data_dir: Path, capsys):
    assert (
        cli.main(
            [
                "tag",
                "create",
                "Cute",
                "--color",
                "#8ab4f8",
                "--category",
                "style",
            ]
        )
        == 0
    )
    create_out = capsys.readouterr().out
    assert "已创建标签" in create_out
    assert "Cute" in create_out

    assert cli.main(["tag", "list"]) == 0
    list_out = capsys.readouterr().out
    assert "ID\tNAME\tCOLOR\tCATEGORY\tSYSTEM" in list_out
    assert "Cute\t#8ab4f8\tstyle\tno" in list_out
    assert "Favorite\t-\t-\tyes" in list_out

    row = next(tag for tag in _tag_rows() if tag["name_key"] == "cute")
    assert row["color"] == "#8ab4f8"
    assert row["category"] == "style"


def test_tag_rename_by_name_and_delete_by_id(data_dir: Path, capsys):
    assert cli.main(["tag", "create", "Cute"]) == 0
    capsys.readouterr()

    assert cli.main(["tag", "rename", "cute", "Pretty"]) == 0
    assert "Cute → Pretty" in capsys.readouterr().out
    renamed = next(tag for tag in _tag_rows() if tag["name"] == "Pretty")
    assert renamed["name_key"] == "pretty"

    assert cli.main(["tag", "delete", str(renamed["id"])]) == 0
    assert "已删除标签" in capsys.readouterr().out
    assert all(tag["name"] != "Pretty" for tag in _tag_rows())


def test_tag_rename_by_id(data_dir: Path, capsys):
    assert cli.main(["tag", "create", "Cute"]) == 0
    tag_id = next(tag["id"] for tag in _tag_rows() if tag["name_key"] == "cute")
    capsys.readouterr()

    assert cli.main(["tag", "rename", str(tag_id), "Charming"]) == 0
    assert "已重命名标签" in capsys.readouterr().out
    assert any(tag["name_key"] == "charming" for tag in _tag_rows())


def test_tag_rename_conflict_is_rejected_without_merge(data_dir: Path, capsys):
    assert cli.main(["tag", "create", "Cute"]) == 0
    assert cli.main(["tag", "create", "Pretty"]) == 0
    capsys.readouterr()

    assert cli.main(["tag", "rename", "Cute", "PRETTY"]) == 1
    err = capsys.readouterr().err
    assert "标签名已存在" in err
    assert "不会自动合并" in err
    rows = {tag["name_key"]: tag for tag in _tag_rows()}
    assert rows["cute"]["name"] == "Cute"
    assert rows["pretty"]["name"] == "Pretty"


def test_tag_create_conflict_and_reserved_name_are_rejected(data_dir: Path, capsys):
    assert cli.main(["tag", "create", "Cute"]) == 0
    capsys.readouterr()

    assert cli.main(["tag", "create", "CUTE"]) == 1
    assert "标签名已存在" in capsys.readouterr().err

    assert cli.main(["tag", "create", "favorite"]) == 1
    assert "系统保留名" in capsys.readouterr().err


def test_reserved_favorite_tag_cannot_be_renamed_or_deleted(
    data_dir: Path, capsys
):
    assert cli.main(["tag", "delete", "favorite"]) == 1
    err = capsys.readouterr().err
    assert "系统标签不可重命名或删除" in err

    assert cli.main(["tag", "rename", "favorite", "Fav"]) == 1
    err = capsys.readouterr().err
    assert "系统标签不可重命名或删除" in err
    assert any(tag["name_key"] == FAVORITE_TAG_KEY for tag in _tag_rows())


@pytest.mark.parametrize("command", ["rename", "delete"])
def test_unknown_tag_target_reports_stderr_and_exit_one(
    data_dir: Path, capsys, command: str
):
    argv = (
        ["tag", command, "NoSuchTag", "NewName"]
        if command == "rename"
        else ["tag", command, "NoSuchTag"]
    )
    assert cli.main(argv) == 1
    assert "找不到标签" in capsys.readouterr().err


def test_resource_add_and_remove_tag_are_idempotent(data_dir: Path, capsys):
    resource_id = _seed_resource()
    assert cli.main(["tag", "create", "Cute"]) == 0
    capsys.readouterr()

    assert cli.main(["resource", "add-tag", str(resource_id), "cute"]) == 0
    assert "添加标签" in capsys.readouterr().out
    assert cli.main(["resource", "add-tag", str(resource_id), "CUTE"]) == 0
    assert "添加标签" in capsys.readouterr().out
    assert _resource_tag_keys(resource_id) == ["cute"]

    assert cli.main(["resource", "remove-tag", str(resource_id), "Cute"]) == 0
    assert "移除标签" in capsys.readouterr().out
    assert cli.main(["resource", "remove-tag", str(resource_id), "cute"]) == 0
    assert "移除标签" in capsys.readouterr().out
    assert _resource_tag_keys(resource_id) == []


def test_resource_favorite_and_unfavorite_are_idempotent(data_dir: Path, capsys):
    resource_id = _seed_resource()

    assert cli.main(["resource", "favorite", str(resource_id)]) == 0
    assert cli.main(["resource", "favorite", str(resource_id)]) == 0
    assert "已收藏资源" in capsys.readouterr().out
    assert _resource_tag_keys(resource_id) == [FAVORITE_TAG_KEY]

    assert cli.main(["resource", "unfavorite", str(resource_id)]) == 0
    assert cli.main(["resource", "unfavorite", str(resource_id)]) == 0
    assert "已取消收藏资源" in capsys.readouterr().out
    assert _resource_tag_keys(resource_id) == []


@pytest.mark.parametrize(
    "argv",
    [
        ["resource", "add-tag", "999999", "Cute"],
        ["resource", "remove-tag", "999999", "Cute"],
        ["resource", "favorite", "999999"],
        ["resource", "unfavorite", "999999"],
    ],
)
def test_resource_write_commands_reject_unknown_resource(
    data_dir: Path, capsys, argv: list[str]
):
    assert cli.main(["tag", "create", "Cute"]) == 0
    capsys.readouterr()

    assert cli.main(argv) == 1
    assert "找不到资源" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["add-tag", "remove-tag"])
def test_resource_tag_commands_reject_unknown_tag(
    data_dir: Path, capsys, command: str
):
    resource_id = _seed_resource()

    assert cli.main(["resource", command, str(resource_id), "NoSuchTag"]) == 1
    assert "找不到标签" in capsys.readouterr().err


def test_cli_tag_writes_are_confined_to_tag_write_service():
    source = (Path(__file__).resolve().parent.parent / "main.py").read_text(
        encoding="utf-8"
    )
    assert "TagWriteService" in source
    assert "ensure_system_tags" in source
    import_lines = [
        line
        for line in source.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    assert not any("sqlite3" in line for line in import_lines)
    for forbidden in (
        "INSERT INTO tags",
        "UPDATE tags",
        "DELETE FROM tags",
        "INSERT INTO resource_tags",
        "DELETE FROM resource_tags",
    ):
        assert forbidden not in source
