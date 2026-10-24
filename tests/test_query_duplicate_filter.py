"""Phase 4.1：byte-duplicate / SHA-256 / author 只读筛选。"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

import main as cli
from core.app import TagWriteService
from core.database import db as database
from core.query import AuthorQuery, BrowserScope, ResourceFilter, ResourceQuery

HASH_A = "a" * 64
HASH_B = "b" * 64


def _add_author(conn, name: str) -> int:
    cursor = conn.execute(
        "INSERT INTO authors(name, name_key) VALUES (?, ?)",
        (name, name.casefold()),
    )
    return int(cursor.lastrowid)


def _add_resource(
    conn,
    index: int,
    *,
    sha256: str | None,
    author_id: int | None = None,
) -> int:
    path = f"d:/cards/phase4_{index}.png"
    cursor = conn.execute(
        "INSERT INTO resources(resource_type, type_source, name, file_path,"
        " file_path_key, relative_path, extension, sha256, author_id, scan_status,"
        " parse_status, needs_review)"
        " VALUES ('character_card', 'auto', ?, ?, ?, ?, '.png', ?, ?, 'present', 'ok', 0)",
        (
            f"Card{index}",
            path,
            path.casefold(),
            f"phase4_{index}.png",
            sha256,
            author_id,
        ),
    )
    return int(cursor.lastrowid)


@pytest.fixture()
def seeded_db(tmp_path: Path, monkeypatch) -> dict[str, object]:
    """同哈希两张、唯一哈希一张、空哈希一张；Alice 关联 1/3/4，Bob 关联 2。"""
    data_dir = tmp_path / "appdata"
    monkeypatch.setenv("KKS_RM_DATA_DIR", str(data_dir))
    db_file = data_dir / "kks_resource_manager.db"
    database.initialize(db_file)

    conn = database.connect(db_file)
    try:
        TagWriteService(conn).ensure_system_tags()
        alice = _add_author(conn, "Alice")
        bob = _add_author(conn, "Bob")
        r1 = _add_resource(conn, 1, sha256=HASH_A, author_id=alice)
        r2 = _add_resource(conn, 2, sha256=HASH_A, author_id=bob)
        r3 = _add_resource(conn, 3, sha256=HASH_B, author_id=alice)
        r4 = _add_resource(conn, 4, sha256=None, author_id=alice)
        for resource_id, author_id, raw_name in (
            (r1, alice, "Alice"),
            (r2, bob, "Bob"),
            (r3, alice, "Alice"),
            (r4, alice, "Alice"),
        ):
            conn.execute(
                "INSERT INTO resource_authors(resource_id, author_id, raw_name)"
                " VALUES (?, ?, ?)",
                (resource_id, author_id, raw_name),
            )
        conn.commit()
    finally:
        conn.close()

    return {
        "data_dir": data_dir,
        "db_file": db_file,
        "alice": alice,
        "bob": bob,
        "ids": [r1, r2, r3, r4],
    }


def _open(seeded_db: dict[str, object]):
    return database.connect(Path(seeded_db["db_file"]))


def _ids(rows) -> list[int]:
    return [row.id for row in rows]


def _count(conn, table: str) -> int:
    return int(conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"])


def _db_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("bad", [1, 0, "true", [], object()])
def test_has_duplicates_rejects_non_bool(bad) -> None:
    with pytest.raises(ValueError):
        ResourceFilter(has_duplicates=bad)


def test_filter_has_seventeen_fields_and_normalizes_sha256() -> None:
    assert len(dataclasses.fields(ResourceFilter)) == 17
    assert ResourceFilter(has_duplicates=True).has_duplicates is True
    assert ResourceFilter(has_duplicates=False).has_duplicates is False
    assert ResourceFilter(sha256=f"  {HASH_A}\n").sha256 == HASH_A
    assert ResourceFilter(sha256=" \t ").sha256 is None


def test_sha256_and_duplicate_filters_match_count_and_list(seeded_db) -> None:
    conn = _open(seeded_db)
    ids = seeded_db["ids"]
    try:
        rq = ResourceQuery(conn)

        assert _ids(rq.list(sha256=HASH_A)) == ids[:2]
        assert rq.count(sha256=HASH_A) == 2
        assert rq.list(sha256=HASH_A[:12]) == []

        duplicates = rq.list(has_duplicates=True)
        assert _ids(duplicates) == ids[:2]
        assert rq.count(has_duplicates=True) == len(duplicates) == 2
        assert all(row.sha256 == HASH_A for row in duplicates)

        non_duplicates = rq.list(has_duplicates=False)
        assert _ids(non_duplicates) == ids[2:]
        assert rq.count(has_duplicates=False) == len(non_duplicates) == 2
        assert non_duplicates[-1].sha256 is None

        combined = rq.list(has_duplicates=True, sha256=HASH_A)
        assert _ids(combined) == ids[:2]
        assert rq.count(has_duplicates=True, sha256=HASH_A) == 2
    finally:
        conn.close()


def test_browse_scope_maps_duplicate_and_hash_filters(seeded_db) -> None:
    conn = _open(seeded_db)
    try:
        scope = BrowserScope(has_duplicates=False, sha256=f" {HASH_B} ")
        filters = scope.filters()
        assert len(BrowserScope.FILTER_KEYS) == 16
        assert filters["has_duplicates"] is False
        assert filters["sha256"] == HASH_B
        assert _ids(ResourceQuery(conn).list(**filters)) == [seeded_db["ids"][2]]
    finally:
        conn.close()


def test_cli_new_filters_and_scope(seeded_db, capsys) -> None:
    ids = seeded_db["ids"]
    capsys.readouterr()

    assert cli.main(
        ["query", "resources", "--has-duplicates", "--sha256", HASH_A, "--json"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 2
    assert [r["id"] for r in payload["resources"]] == ids[:2]
    assert payload["scope"] == {"has_duplicates": True, "sha256": HASH_A}

    assert cli.main(["query", "resources", "--no-duplicates", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [r["id"] for r in payload["resources"]] == ids[2:]
    assert payload["scope"] == {"has_duplicates": False}

    # 空白哈希经 ResourceFilter 归一为 None，不应写入 scope。
    assert cli.main(["query", "resources", "--sha256", "   ", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 4
    assert "sha256" not in payload["scope"]


def test_cli_author_id_and_exact_name(seeded_db, capsys) -> None:
    ids = seeded_db["ids"]
    capsys.readouterr()

    assert cli.main(
        ["query", "resources", "--author", str(seeded_db["alice"]), "--json"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [r["id"] for r in payload["resources"]] == [ids[0], ids[2], ids[3]]
    assert payload["scope"] == {"author_id": seeded_db["alice"]}

    assert cli.main(["query", "resources", "--author", "alice", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 3
    assert payload["scope"] == {"author_id": seeded_db["alice"]}


def test_cli_author_not_found_does_not_query(seeded_db, capsys, monkeypatch) -> None:
    called = False

    def fail_if_called(self, *args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("resource query must not run for an unknown author")

    monkeypatch.setattr(ResourceQuery, "list", fail_if_called)
    capsys.readouterr()
    assert cli.main(["query", "resources", "--author", "Nobody", "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "Author not found: Nobody"
    assert called is False


def test_cli_duplicate_flags_are_mutually_exclusive(seeded_db) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            ["query", "resources", "--has-duplicates", "--no-duplicates"]
        )
    assert excinfo.value.code == 2


def test_new_cli_filters_are_read_only_and_duplicate_tables_stay_empty(
    seeded_db, capsys
) -> None:
    db_file = Path(seeded_db["db_file"])
    before = _db_sha256(db_file)
    capsys.readouterr()
    for argv in (
        ["query", "resources", "--has-duplicates"],
        ["query", "resources", "--no-duplicates"],
        ["query", "resources", "--sha256", HASH_A],
        ["query", "resources", "--author", "Alice"],
        ["query", "resources", "--author", "Missing"],
    ):
        assert cli.main(argv) == (1 if "Missing" in argv else 0)
    capsys.readouterr()

    assert _db_sha256(db_file) == before
    conn = _open(seeded_db)
    try:
        assert _count(conn, "duplicate_groups") == 0
        assert _count(conn, "duplicate_members") == 0
    finally:
        conn.close()
