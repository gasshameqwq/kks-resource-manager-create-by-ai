"""Phase 1.1 验收（CLI 通道）：``python main.py library ...``。

架构文档 §7 给步骤 1.1 定的验收方式就是「CLI 能列出已添加的 Library」，
因此这里直接调用 ``main.main(argv)`` 并检查退出码与输出。

数据目录通过 ``KKS_RM_DATA_DIR`` 环境变量重定向到临时目录，不污染项目 ``data/``。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main as cli  # noqa: E402
from core.database import db as database  # noqa: E402


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch) -> Path:
    target = tmp_path / "appdata"
    monkeypatch.setenv("KKS_RM_DATA_DIR", str(target))
    return target


@pytest.fixture()
def cards_dir(tmp_path: Path) -> Path:
    path = tmp_path / "KKS Cards"
    path.mkdir()
    return path


def test_library_list_on_empty_db(data_dir: Path, capsys):
    assert cli.main(["library", "list"]) == 0
    out = capsys.readouterr().out
    assert "尚未添加任何 Library" in out
    assert "library add" in out


def test_library_add_then_list(data_dir: Path, cards_dir: Path, capsys):
    assert cli.main(["library", "add", str(cards_dir)]) == 0
    add_out = capsys.readouterr().out
    assert "已添加 Library [1]" in add_out
    assert "KKS Cards" in add_out

    assert cli.main(["library", "list"]) == 0
    list_out = capsys.readouterr().out
    assert "已添加 Library（1）" in list_out
    assert str(cards_dir) in list_out
    assert "资源：0（待确认 0，缺失 0）" in list_out
    assert "上次扫描：从未" in list_out


def test_library_add_multiple_paths_at_once(data_dir: Path, tmp_path: Path, capsys):
    first, second = tmp_path / "A", tmp_path / "B"
    first.mkdir()
    second.mkdir()

    assert cli.main(["library", "add", str(first), str(second)]) == 0
    out = capsys.readouterr().out
    assert "已添加 Library [1]" in out
    assert "已添加 Library [2]" in out


def test_library_add_multiple_paths_rolls_back_on_bad_input(
    data_dir: Path, tmp_path: Path, capsys
):
    good = tmp_path / "A"
    good.mkdir()

    assert cli.main(["library", "add", str(good), str(tmp_path / "missing")]) == 1
    err = capsys.readouterr().err
    assert "添加失败" in err

    # 整批回滚：好的那个也没进去
    assert cli.main(["library", "list"]) == 0
    assert "尚未添加任何 Library" in capsys.readouterr().out


def test_library_add_name_only_for_single_path(data_dir: Path, tmp_path: Path, capsys):
    first, second = tmp_path / "A", tmp_path / "B"
    first.mkdir()
    second.mkdir()

    assert cli.main(["library", "add", str(first), str(second), "--name", "x"]) == 2
    assert "--name 只能配合单个目录使用" in capsys.readouterr().err


def test_library_add_missing_directory_reports_error(data_dir: Path, tmp_path: Path, capsys):
    assert cli.main(["library", "add", str(tmp_path / "nope")]) == 1
    assert "目录不存在" in capsys.readouterr().err


def test_library_remove_requires_confirmation(data_dir: Path, cards_dir: Path, capsys):
    cli.main(["library", "add", str(cards_dir)])
    capsys.readouterr()

    assert cli.main(["library", "remove", "1"]) == 1
    preview = capsys.readouterr().out
    assert "将要删除 Library [1]" in preview
    assert "确认请加 --yes" in preview

    assert cli.main(["library", "list"]) == 0
    assert "已添加 Library（1）" in capsys.readouterr().out

    assert cli.main(["library", "remove", "1", "--yes"]) == 0
    assert "已删除 Library [1]" in capsys.readouterr().out

    assert cli.main(["library", "list"]) == 0
    assert "尚未添加任何 Library" in capsys.readouterr().out


def test_library_remove_unknown_target_reports_error(data_dir: Path, capsys):
    assert cli.main(["library", "remove", "D:/nowhere", "--yes"]) == 1
    assert "找不到 Library" in capsys.readouterr().err


def test_library_enable_disable_by_path(data_dir: Path, cards_dir: Path, capsys):
    cli.main(["library", "add", str(cards_dir)])
    capsys.readouterr()

    assert cli.main(["library", "disable", str(cards_dir)]) == 0
    assert "已暂停 Library [1]" in capsys.readouterr().out

    assert cli.main(["library", "list"]) == 0
    assert "（暂停）" in capsys.readouterr().out

    assert cli.main(["library", "enable", "1"]) == 0
    assert "已启用 Library [1]" in capsys.readouterr().out


def test_info_reports_library_count(data_dir: Path, cards_dir: Path, capsys):
    cli.main(["library", "add", str(cards_dir)])
    capsys.readouterr()

    assert cli.main(["--info"]) == 0
    out = capsys.readouterr().out
    assert "已添加 Library（1）：1:KKS Cards" in out


def test_cli_writes_into_redirected_data_dir(data_dir: Path, cards_dir: Path):
    cli.main(["library", "add", str(cards_dir)])
    assert (data_dir / "kks_resource_manager.db").is_file()

    conn = database.connect(data_dir / "kks_resource_manager.db")
    try:
        rows = conn.execute("SELECT name, root_path FROM libraries").fetchall()
    finally:
        conn.close()
    assert [r["name"] for r in rows] == ["KKS Cards"]
