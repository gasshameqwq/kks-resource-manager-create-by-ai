"""Scanner 的入库层：把 Parser 结果写进 v2 表。

职责边界
--------
- **只做数据库读写**：不遍历目录、不调用 Parser、不做类型判断。
- 不做事务管理：每个文件的事务由 ``LibraryScanner`` 开启（失败隔离）。
  只有 ``mark_missing`` 自己开一个小事务。

入库规则（对应 docs/phase1/PHASE1_2_REPORT.md §1.2-C）
---------------------------------------------
- 一个文件 = 一行 ``resources``（``file_path_key`` 唯一）。
- 卡片：``resources.card_marker`` + ``metadata_json`` + 插件/依赖/作者关系。
- zipmod：``resources(type='mod')`` + 一行 ``mods``（以 ``guid`` 为身份）。
- 关系一律 **先删后插**（在同一个事务内），因此重扫不会产生重复行。
- 未安装的 MOD：``resource_mods.mod_id`` 留空，但关系行照建，**不**凭空造 ``mods`` 实体。

用户数据边界（Phase 3.1 Contract §2.2 / §3.1）
--------------------------------------------
- 本层是**机器写入者**：只写 machine facts（含新建资源时的 ``type_source = 'auto'`` 初始值）。
- 本层**绝不**写入 ``display_name`` / ``notes`` / ``type_source = 'user'``。
  用户展示名覆盖是纯用户数据，只由 ``core.app.ResourceWriteService`` 写入；
  重扫既不读取、也不比较、更不覆盖它。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.database import db as database
from core.models import partition_authors
from core.parsers import CharacterCardParseResult, ZipmodParseResult

OUTCOME_INSERTED = "inserted"
OUTCOME_UPDATED = "updated"


def build_card_metadata(parsed: CharacterCardParseResult, authors_raw=None) -> dict:
    """构造 ``resources.metadata_json`` 的内容。

    约定键见 ``core.database.schema.RESOURCE_METADATA_KEYS``。
    KK 卡片没有 About → ``user_id`` / ``data_id`` 明确写 ``null``（不编造值）。
    """
    metadata: dict = {
        "user_id": parsed.user_id,
        "data_id": parsed.data_id,
        "card_version": parsed.card_version,
        "embedded_texture_count": parsed.embedded_texture_count,
        "plugin_count": parsed.plugin_count,
        "face_preview_kind": parsed.face_preview_kind,
        "block_sizes": parsed.block_sizes,
    }
    if authors_raw is not None:
        metadata["authors_raw"] = list(authors_raw)
    return metadata


class ResourceStore:
    """``resources`` / ``mods`` / 关系表的写入器。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ---- 查询 -----------------------------------------------------------

    def find_by_path_key(self, path_key: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM resources WHERE file_path_key = ?", (path_key,)
        ).fetchone()

    def count_resources(self, library_id: int | None = None) -> int:
        if library_id is None:
            sql, params = "SELECT count(*) AS c FROM resources", ()
        else:
            sql, params = (
                "SELECT count(*) AS c FROM resources WHERE library_id = ?",
                (library_id,),
            )
        return self.conn.execute(sql, params).fetchone()["c"]

    # ---- 跳过 / 失败时的轻量更新 ----------------------------------------

    def touch_present(self, resource_id: int) -> None:
        """文件仍然存在（内容未变、被跳过）→ 确保不再是 missing 状态。"""
        self.conn.execute(
            "UPDATE resources SET scan_status = 'present',"
            " last_scanned_at = datetime('now')"
            " WHERE id = ? AND scan_status <> 'present'",
            (resource_id,),
        )

    def mark_parse_failed(self, resource_id: int, error: str | None) -> None:
        """已经入库过的文件这次解析失败：保留行，标记状态（**不删除**）。"""
        self.conn.execute(
            "UPDATE resources SET parse_status = 'failed', parse_error = ?,"
            " scan_status = 'error', updated_at = datetime('now'),"
            " last_scanned_at = datetime('now') WHERE id = ?",
            (error, resource_id),
        )

    # ---- 卡片 -----------------------------------------------------------

    def upsert_card_resource(
        self,
        *,
        library_id: int,
        path: Path,
        path_key: str,
        relative_path: str,
        size: int,
        modified_time: float,
        parsed: CharacterCardParseResult,
        sha256: str,
        authors_raw: list[str] | None = None,
    ) -> tuple[int, str]:
        """写入/更新一张卡片，并重建它的关系。返回 (resource_id, outcome)。

        只写机器事实；**不写** ``display_name``（纯用户数据，见模块 docstring）。
        """
        resource_type = parsed.card_type or "unknown"
        metadata = build_card_metadata(parsed, authors_raw)
        needs_review = 1 if (parsed.parse_status != "ok" or not parsed.name) else 0

        existing = self.find_by_path_key(path_key)
        if existing is None:
            cursor = self.conn.execute(
                "INSERT INTO resources("
                " resource_type, type_source, library_id, name,"
                " file_path, file_path_key, relative_path, file_size, modified_time,"
                " sha256,"
                " extension, parse_status, parse_error, card_marker, metadata_json,"
                " scan_status, needs_review, last_scanned_at)"
                " VALUES (?, 'auto', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
                " 'present', ?, datetime('now'))",
                (
                    resource_type,
                    library_id,
                    parsed.name,
                    str(path),
                    path_key,
                    relative_path,
                    size,
                    modified_time,
                    sha256,
                    path.suffix.lower(),
                    parsed.parse_status,
                    parsed.error,
                    parsed.card_marker,
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                    needs_review,
                ),
            )
            resource_id = int(cursor.lastrowid)
            outcome = OUTCOME_INSERTED
        else:
            resource_id = int(existing["id"])
            # 用户手工确认过的类型不允许被自动覆盖（Phase 0 约定）
            if existing["type_source"] == "user":
                resource_type = existing["resource_type"]
            # display_name 是纯用户数据（Phase 3.1 Contract §2.2 / §3.1）：
            # 重扫既不写它，也不依据「是否等于旧 name」做任何判断。
            self.conn.execute(
                "UPDATE resources SET library_id = ?, resource_type = ?, name = ?,"
                " file_path = ?, relative_path = ?, file_size = ?,"
                " modified_time = ?, sha256 = ?, extension = ?, parse_status = ?,"
                " parse_error = ?,"
                " card_marker = ?, metadata_json = ?, scan_status = 'present',"
                " needs_review = ?, updated_at = datetime('now'),"
                " last_scanned_at = datetime('now')"
                " WHERE id = ?",
                (
                    library_id,
                    resource_type,
                    parsed.name,
                    str(path),
                    relative_path,
                    size,
                    modified_time,
                    sha256,
                    path.suffix.lower(),
                    parsed.parse_status,
                    parsed.error,
                    parsed.card_marker,
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                    needs_review,
                    resource_id,
                ),
            )
            outcome = OUTCOME_UPDATED

        self._replace_plugins(resource_id, parsed.plugin_guids)
        self._replace_usages(resource_id, parsed.dependencies)
        self._replace_authors(resource_id, authors_raw or [])
        return resource_id, outcome

    # ---- zipmod ---------------------------------------------------------

    def upsert_mod_resource(
        self,
        *,
        library_id: int,
        path: Path,
        path_key: str,
        relative_path: str,
        size: int,
        modified_time: float,
        parsed: ZipmodParseResult,
        sha256: str,
    ) -> tuple[int, str]:
        """写入/更新一个 zipmod（resources + mods）。返回 (resource_id, outcome)。

        只写机器事实；**不写** ``display_name``（纯用户数据，见模块 docstring）。
        """
        display = parsed.name or parsed.guid
        existing = self.find_by_path_key(path_key)
        if existing is None:
            cursor = self.conn.execute(
                "INSERT INTO resources("
                " resource_type, type_source, library_id, name,"
                " file_path, file_path_key, relative_path, file_size, modified_time,"
                " sha256, extension, parse_status, scan_status, needs_review,"
                " last_scanned_at)"
                " VALUES ('mod', 'auto', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'present', 0,"
                " datetime('now'))",
                (
                    library_id,
                    display,
                    str(path),
                    path_key,
                    relative_path,
                    size,
                    modified_time,
                    sha256,
                    path.suffix.lower(),
                    parsed.parse_status,
                ),
            )
            resource_id = int(cursor.lastrowid)
            outcome = OUTCOME_INSERTED
        else:
            resource_id = int(existing["id"])
            resource_type = (
                existing["resource_type"]
                if existing["type_source"] == "user"
                else "mod"
            )
            # display_name 是纯用户数据：重扫不写、不判断、不覆盖。
            self.conn.execute(
                "UPDATE resources SET library_id = ?, resource_type = ?, name = ?,"
                " file_path = ?, relative_path = ?, file_size = ?,"
                " modified_time = ?, sha256 = ?, extension = ?, parse_status = ?,"
                " parse_error = NULL,"
                " scan_status = 'present', updated_at = datetime('now'),"
                " last_scanned_at = datetime('now') WHERE id = ?",
                (
                    library_id,
                    resource_type,
                    display,
                    str(path),
                    relative_path,
                    size,
                    modified_time,
                    sha256,
                    path.suffix.lower(),
                    parsed.parse_status,
                    resource_id,
                ),
            )
            outcome = OUTCOME_UPDATED

        # mods：GUID 才是身份；name/author/version/website 原样写入（空值也照写）
        self.conn.execute(
            "INSERT INTO mods(guid, name, author, version, website, file_path,"
            " file_path_key, resource_id, library_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(guid) DO UPDATE SET"
            " name = excluded.name, author = excluded.author,"
            " version = excluded.version, website = excluded.website,"
            " file_path = excluded.file_path, file_path_key = excluded.file_path_key,"
            " resource_id = excluded.resource_id, library_id = excluded.library_id,"
            " updated_at = datetime('now')",
            (
                parsed.guid,
                parsed.name,
                parsed.author,
                parsed.version,
                parsed.website,
                str(path),
                path_key,
                resource_id,
                library_id,
            ),
        )
        mod_row = self.conn.execute(
            "SELECT id FROM mods WHERE guid = ?", (parsed.guid,)
        ).fetchone()
        if mod_row is not None:
            # 之前扫描时该 MOD 还不存在 → 回填依赖关系的 mod_id
            self.conn.execute(
                "UPDATE resource_mods SET mod_id = ?"
                " WHERE mod_guid = ? AND (mod_id IS NULL OR mod_id <> ?)",
                (mod_row["id"], parsed.guid, mod_row["id"]),
            )
        return resource_id, outcome

    # ---- 关系重建 -------------------------------------------------------

    def _replace_plugins(self, resource_id: int, plugin_guids: list[str]) -> None:
        """插件关系先删后插；插件**绝不**写进 mods。"""
        self.conn.execute(
            "DELETE FROM resource_plugins WHERE resource_id = ?", (resource_id,)
        )
        for guid in dict.fromkeys(str(g) for g in plugin_guids):
            if not guid:
                continue
            self.conn.execute(
                "INSERT INTO resource_plugins(resource_id, plugin_guid) VALUES (?, ?)",
                (resource_id, guid),
            )

    def _replace_usages(self, resource_id: int, dependencies) -> None:
        """逐槽位关系 + 汇总关系一起重建（保持 v2 的不变式）。"""
        self.conn.execute(
            "DELETE FROM resource_mod_usages WHERE resource_id = ?", (resource_id,)
        )
        self.conn.execute(
            "DELETE FROM resource_mods WHERE resource_id = ?", (resource_id,)
        )

        # 同一 (mod_guid, property) 在 schema 里是同一行 → 先按主键去重（保留第一条）
        seen: dict[tuple[str, str], object] = {}
        for dep in dependencies:
            if not dep.mod_id or not dep.property:
                continue
            seen.setdefault((dep.mod_id, dep.property), dep)

        counts: dict[str, int] = {}
        for (mod_guid, prop), dep in seen.items():
            self.conn.execute(
                "INSERT INTO resource_mod_usages("
                " resource_id, mod_guid, property, slot, local_slot, category_no)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    resource_id,
                    mod_guid,
                    prop,
                    dep.slot,
                    dep.local_slot,
                    dep.category_no,
                ),
            )
            counts[mod_guid] = counts.get(mod_guid, 0) + 1

        for mod_guid, ref_count in counts.items():
            mod_row = self.conn.execute(
                "SELECT id FROM mods WHERE guid = ?", (mod_guid,)
            ).fetchone()
            self.conn.execute(
                "INSERT INTO resource_mods(resource_id, mod_guid, mod_id, relation,"
                " ref_count) VALUES (?, ?, ?, 'uses', ?)",
                (
                    resource_id,
                    mod_guid,
                    mod_row["id"] if mod_row is not None else None,
                    ref_count,
                ),
            )

    def _replace_authors(self, resource_id: int, authors_raw: list[str]) -> None:
        """写入多作者关联。

        ``[Unknown]`` 等哨兵值按 1.2-A 的规则处理：**不建 authors 实体**，
        但原始列表由调用方保存在 ``metadata_json.authors_raw`` 里，不丢。

        ``ordinal`` = **该作者在原始列表里的下标**（不是过滤后的序号）。
        例如 ``['[Unknown]', 'Evaan', 'Alice']`` → Evaan=1、Alice=2。
        这样即使哨兵位于列表首位，也不会把真实作者的序号改掉。
        """
        self.conn.execute(
            "DELETE FROM resource_authors WHERE resource_id = ?", (resource_id,)
        )
        raw_list = [a for a in (authors_raw or []) if isinstance(a, str)]
        real, _placeholders, _raw = partition_authors(raw_list)
        if not real:
            return

        for ordinal, name in enumerate(raw_list):
            cleaned = name.strip()
            # 哨兵 / 空串 / 重复项在 real 里不存在 → 跳过（但它们仍占原位，序号不变）
            if not cleaned or cleaned not in real:
                continue
            name_key = database.normalize_name_key(cleaned)
            self.conn.execute(
                "INSERT INTO authors(name, name_key) VALUES (?, ?)"
                " ON CONFLICT(name_key) DO NOTHING",
                (cleaned, name_key),
            )
            author_row = self.conn.execute(
                "SELECT id FROM authors WHERE name_key = ?", (name_key,)
            ).fetchone()
            if author_row is None:
                continue
            # 重复作者由主键 (resource_id, author_id) 挡掉，首次出现的 ordinal 生效
            self.conn.execute(
                "INSERT INTO resource_authors(resource_id, author_id, ordinal, raw_name)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(resource_id, author_id) DO NOTHING",
                (resource_id, author_row["id"], ordinal, name),
            )

    # ---- 缺失 -----------------------------------------------------------

    def mark_missing(self, library_id: int, seen_path_keys: set[str]) -> int:
        """把这次没扫到的既有资源标记为 ``missing``（**不删除任何行**）。"""
        rows = self.conn.execute(
            "SELECT id, file_path_key FROM resources"
            " WHERE library_id = ? AND scan_status = 'present'",
            (library_id,),
        ).fetchall()
        stale = [int(r["id"]) for r in rows if r["file_path_key"] not in seen_path_keys]
        if not stale:
            return 0
        with database.transaction(self.conn):
            self.conn.executemany(
                "UPDATE resources SET scan_status = 'missing',"
                " updated_at = datetime('now') WHERE id = ?",
                [(rid,) for rid in stale],
            )
        return len(stale)


__all__ = [
    "OUTCOME_INSERTED",
    "OUTCOME_UPDATED",
    "ResourceStore",
    "build_card_metadata",
]
