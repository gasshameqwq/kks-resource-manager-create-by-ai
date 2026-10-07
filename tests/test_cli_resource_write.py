"""Phase 3.1 Step 5 —— CLI 用户编辑入口（``python main.py resource ...``）。

依据：`docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md` §5.3 / §7 Step 5。

分层验证：

    CLI → ResourceQuery.resolve()（只读） → ResourceWriteService → DB

数据目录通过 ``KKS_RM_DATA_DIR`` 重定向到临时目录，不污染项目 ``data/``。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main as cli  # noqa: E402
from core.database import db as database  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.scanner import LibraryScanner  # noqa: E402
from tests.builders import write_card  # noqa: E402


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch) -> Path:
    target = tmp_path / "appdata"
    monkeypatch.setenv("KKS_RM_DATA_DIR", str(target))
    return target


def _seed_resource(
    *,
    path: str = "D:/cards/alice.png",
    name: str = "Alice",
    resource_type: str = "character_card",
) -> int:
    database.initialize()
    conn = database.connect()
    try:
        cursor = conn.execute(
            "INSERT INTO resources(resource_type, type_source, name,"
            " file_path, file_path_key)"
            " VALUES (?, 'auto', ?, ?, ?)",
            (resource_type, name, path, database.normalize_path_key(path)),
        )
        return int(cursor.lastrowid)
    finally:
        conn.close()


def _read(resource_id: int, column: str):
    conn = database.connect()
    try:
        return conn.execute(
            f"SELECT {column} FROM resources WHERE id = ?", (resource_id,)
        ).fetchone()[column]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1. display-name
# ---------------------------------------------------------------------------


def test_cli_set_display_name_then_clear(data_dir: Path, capsys):
    rid = _seed_resource()

    assert cli.main(["resource", "set-display-name", str(rid), "Custom Name"]) == 0
    assert "已设置" in capsys.readouterr().out
    assert _read(rid, "display_name") == "Custom Name"

    assert cli.main(["resource", "set-display-name", str(rid), "--clear"]) == 0
    assert "已清除" in capsys.readouterr().out
    assert _read(rid, "display_name") is None


def test_cli_set_display_name_strips_value(data_dir: Path):
    rid = _seed_resource()
    assert cli.main(["resource", "set-display-name", str(rid), "  Alice  "]) == 0
    assert _read(rid, "display_name") == "Alice"


# ---------------------------------------------------------------------------
# 2. notes
# ---------------------------------------------------------------------------


def test_cli_set_notes_then_clear(data_dir: Path, capsys):
    rid = _seed_resource()

    assert cli.main(["resource", "set-notes", str(rid), "Some notes"]) == 0
    assert _read(rid, "notes") == "Some notes"

    assert cli.main(["resource", "set-notes", str(rid), "--clear"]) == 0
    assert _read(rid, "notes") is None


# ---------------------------------------------------------------------------
# 3. type
# ---------------------------------------------------------------------------


def test_cli_set_type_sets_user_source(data_dir: Path, capsys):
    rid = _seed_resource(resource_type="unknown")

    assert cli.main(["resource", "set-type", str(rid), "mod"]) == 0
    assert "type_source = 'user'" in capsys.readouterr().out
    assert _read(rid, "resource_type") == "mod"
    assert _read(rid, "type_source") == "user"


# ---------------------------------------------------------------------------
# 4. id / path 两种目标形式
# ---------------------------------------------------------------------------


def test_cli_resolves_target_by_id(data_dir: Path):
    rid = _seed_resource()
    assert cli.main(["resource", "set-notes", str(rid), "by id"]) == 0
    assert _read(rid, "notes") == "by id"


def test_cli_resolves_target_by_path(data_dir: Path):
    path = "D:/cards/bob.png"
    rid = _seed_resource(path=path, name="Bob")
    assert cli.main(["resource", "set-notes", path, "by path"]) == 0
    assert _read(rid, "notes") == "by path"


# ---------------------------------------------------------------------------
# 5. CLI boundary（静态）
# ---------------------------------------------------------------------------


def test_cli_modules_do_not_write_resources_directly():
    repo = Path(__file__).resolve().parent.parent
    for relative in ("main.py", "cli_query.py"):
        source = (repo / relative).read_text(encoding="utf-8")
        import_lines = [
            line
            for line in source.splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        assert not any("sqlite3" in line for line in import_lines), relative
        for forbidden in (
            "INSERT INTO resources",
            "UPDATE resources",
            "DELETE FROM resources",
            "executescript",
        ):
            assert forbidden not in source, f"{relative} 不得直接写 resources：{forbidden}"


def test_main_does_not_use_resource_store_for_user_edits():
    repo = Path(__file__).resolve().parent.parent
    source = (repo / "main.py").read_text(encoding="utf-8")
    import_lines = [
        line
        for line in source.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    assert not any("ResourceStore" in line for line in import_lines), (
        "CLI 不得 import machine writer（ResourceStore）做用户编辑"
    )
    # 用户编辑只经 ResourceWriteService
    assert "ResourceWriteService" in source


# ---------------------------------------------------------------------------
# 6. error handling
# ---------------------------------------------------------------------------


def test_cli_unknown_target(data_dir: Path, capsys):
    assert cli.main(["resource", "set-notes", "999", "x"]) == 1
    assert "找不到资源" in capsys.readouterr().err


def test_cli_invalid_type_reports_error_without_writing(data_dir: Path, capsys):
    rid = _seed_resource(resource_type="unknown")
    assert cli.main(["resource", "set-type", str(rid), "not_a_type"]) == 1
    err = capsys.readouterr().err
    assert "非法取值" in err
    assert _read(rid, "resource_type") == "unknown"
    assert _read(rid, "type_source") == "auto"


def test_cli_missing_value_is_argument_error(data_dir: Path, capsys):
    rid = _seed_resource()
    assert cli.main(["resource", "set-display-name", str(rid)]) == 2
    assert "参数错误" in capsys.readouterr().err
    assert _read(rid, "display_name") is None


def test_cli_clear_conflicts_with_value_is_argument_error(data_dir: Path, capsys):
    rid = _seed_resource()
    assert cli.main(["resource", "set-display-name", str(rid), "X", "--clear"]) == 2
    assert "参数错误" in capsys.readouterr().err
    assert _read(rid, "display_name") is None

    assert cli.main(["resource", "set-notes", str(rid), "Y", "--clear"]) == 2
    assert "参数错误" in capsys.readouterr().err
    assert _read(rid, "notes") is None


def test_cli_resource_subcommand_requires_a_command(data_dir: Path):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["resource"])
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# 7. ownership regression：CLI → WriteService → Scanner
# ---------------------------------------------------------------------------


def test_cli_writes_survive_scanner_rescan(data_dir: Path, tmp_path: Path):
    root = tmp_path / "library"
    root.mkdir()
    card = write_card(root / "card.png", lastname="Old", firstname="Name")

    database.initialize()
    conn = database.connect()
    try:
        library = LibraryStore(conn).add(root, name="lib")
        LibraryScanner(conn).scan(library.id)
        rid = int(conn.execute("SELECT id FROM resources").fetchone()["id"])
    finally:
        conn.close()

    assert cli.main(["resource", "set-display-name", str(rid), "Custom"]) == 0
    assert cli.main(["resource", "set-notes", str(rid), "keep"]) == 0
    assert cli.main(["resource", "set-type", str(rid), "mod"]) == 0

    # Scanner 重扫（内容变化 → UPDATE 路径）
    write_card(card, lastname="Renamed", firstname="Character")
    conn = database.connect()
    try:
        LibraryScanner(conn).scan(library.id)
    finally:
        conn.close()

    assert _read(rid, "name") == "RenamedCharacter"   # machine fact 正常更新
    assert _read(rid, "display_name") == "Custom"
    assert _read(rid, "notes") == "keep"
    assert _read(rid, "resource_type") == "mod"
    assert _read(rid, "type_source") == "user"
