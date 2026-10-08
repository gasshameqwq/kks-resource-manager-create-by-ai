"""TagWriteService —— Phase 3.2 唯一的 Tag 域 runtime 写入口。

依据
----
`docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md`（§3–§7）。

- 本模块是 ``tags`` / ``resource_tags`` 的**唯一**运行期 writer；
- 不写任何 machine fact，也不写 ``resources``（资源存在性只做只读检查）；
- 不扫描、不解析、不操作文件、不经 Query Layer；
- 每个 public 写方法 = 一个 ``db.transaction``；失败整体回滚并原样抛出。

Favorite（Contract §4.5）
------------------------
``set_favorite(r, True)``  ≡ assign 保留 Favorite 系统 Tag；
``set_favorite(r, False)`` ≡ unassign 保留 Favorite 系统 Tag。
**唯一持久化事实是 ``resource_tags``**，不存在第二套 Favorite 机制。
"""

from __future__ import annotations

import sqlite3

from core.app.resource_write import ResourceNotFound
from core.database import db as database
from core.models.tags import FAVORITE_TAG_KEY, SYSTEM_TAGS, is_system_tag_key


# ---------------------------------------------------------------------------
# 异常（Contract §6）
# ---------------------------------------------------------------------------


class TagWriteError(Exception):
    """TagWriteService 所有操作异常的基类。"""


class TagNotFound(TagWriteError):
    """目标 ``tag_id`` 不存在。"""

    def __init__(self, tag_id: int) -> None:
        self.tag_id = tag_id
        super().__init__(f"找不到标签：{tag_id}")


class TagNameConflict(TagWriteError):
    """``name_key`` 与既有 Tag 冲突（create / rename）。"""

    def __init__(self, name_key: str) -> None:
        self.name_key = name_key
        super().__init__(f"标签名已存在：{name_key!r}")


class ReservedTagName(TagWriteError):
    """目标是保留系统 key。"""

    def __init__(self, name_key: str) -> None:
        self.name_key = name_key
        super().__init__(f"标签名是保留的系统 key：{name_key!r}")


class SystemTagImmutable(TagWriteError):
    """试图 rename / delete 系统 Tag。"""

    def __init__(self, tag_id: int) -> None:
        self.tag_id = tag_id
        super().__init__(f"系统标签不可修改：{tag_id}")


class InvalidTagValue(TagWriteError):
    """用户提供的值非法（空白名、非字符串等）。"""

    def __init__(self, field: str, value: object) -> None:
        self.field = field
        self.value = value
        super().__init__(f"{field} 的取值非法：{value!r}")


# ---------------------------------------------------------------------------
# 归一化（复用既有 normalize_name_key，不新造 policy；Contract §4.2）
# ---------------------------------------------------------------------------


def _normalize_tag_name(field: str, value: str | None) -> tuple[str, str]:
    """名称必须是非空字符串；返回 ``(name, name_key)``。

    ``name`` 为 ``strip()`` 后的展示名；``name_key = normalize_name_key(name)``
    （``strip() + casefold()``）。空白 / 非字符串 ⇒ :class:`InvalidTagValue`。
    """
    if not isinstance(value, str):
        raise InvalidTagValue(field, value)
    name = value.strip()
    if not name:
        raise InvalidTagValue(field, value)
    return name, database.normalize_name_key(name)


def _normalize_optional_text(field: str, value: str | None) -> str | None:
    """可选文本：``None`` / 空白 ⇒ ``NULL``；非空 ⇒ ``strip()`` 后保存。"""
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidTagValue(field, value)
    text = value.strip()
    return text or None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TagWriteService:
    """Phase 3.2 ``tags`` / ``resource_tags`` 写入的唯一 runtime boundary。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ---- Tag lifecycle ---------------------------------------------------

    def create_tag(
        self, name: str, *, color: str | None = None, category: str | None = None
    ) -> int:
        """创建用户 Tag；返回新 Tag 的 id。

        - 空白 / 非字符串名 ⇒ :class:`InvalidTagValue`；
        - 保留系统 key ⇒ :class:`ReservedTagName`；
        - ``name_key`` 已存在 ⇒ :class:`TagNameConflict`（不合并、不静默复用）。
        """
        clean_name, name_key = _normalize_tag_name("name", name)
        color_value = _normalize_optional_text("color", color)
        category_value = _normalize_optional_text("category", category)
        if is_system_tag_key(name_key):
            raise ReservedTagName(name_key)
        with database.transaction(self.conn):
            if self._find_by_key(name_key) is not None:
                raise TagNameConflict(name_key)
            try:
                cursor = self.conn.execute(
                    "INSERT INTO tags(name, name_key, color, category)"
                    " VALUES (?, ?, ?, ?)",
                    (clean_name, name_key, color_value, category_value),
                )
            except sqlite3.IntegrityError as exc:  # UNIQUE(name_key) 兜底
                raise TagNameConflict(name_key) from exc
            return int(cursor.lastrowid)

    def rename_tag(self, tag_id: int, new_name: str) -> None:
        """重命名用户 Tag：``name`` / ``name_key`` / ``updated_at`` 同事务更新。

        - 不存在 ⇒ :class:`TagNotFound`；
        - 系统 Tag ⇒ :class:`SystemTagImmutable`；
        - 空白 ⇒ :class:`InvalidTagValue`；保留 key ⇒ :class:`ReservedTagName`；
        - 与**其它** Tag 冲突 ⇒ :class:`TagNameConflict`；
        - 新 ``name_key`` == 自身当前 key ⇒ 允许（幂等）。
        """
        clean_name, name_key = _normalize_tag_name("name", new_name)
        with database.transaction(self.conn):
            row = self._require_tag(tag_id)
            if is_system_tag_key(row["name_key"]):
                raise SystemTagImmutable(tag_id)
            if is_system_tag_key(name_key):
                raise ReservedTagName(name_key)
            existing = self._find_by_key(name_key)
            if existing is not None and int(existing["id"]) != tag_id:
                raise TagNameConflict(name_key)
            try:
                self.conn.execute(
                    "UPDATE tags SET name = ?, name_key = ?,"
                    " updated_at = datetime('now') WHERE id = ?",
                    (clean_name, name_key, tag_id),
                )
            except sqlite3.IntegrityError as exc:
                raise TagNameConflict(name_key) from exc

    def delete_tag(self, tag_id: int) -> None:
        """删除用户 Tag；其 ``resource_tags`` 关联经既有 FK cascade 清理。系统 Tag 不可删。"""
        with database.transaction(self.conn):
            row = self._require_tag(tag_id)
            if is_system_tag_key(row["name_key"]):
                raise SystemTagImmutable(tag_id)
            self.conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))

    # ---- Resource ↔ Tag --------------------------------------------------

    def assign_tag(self, resource_id: int, tag_id: int) -> None:
        """把 Tag 赋给资源（``origin='user'``）；幂等。

        resource 不存在 ⇒ :class:`ResourceNotFound`；tag 不存在 ⇒ :class:`TagNotFound`。
        """
        with database.transaction(self.conn):
            self._require_resource(resource_id)
            self._require_tag(tag_id)
            self.conn.execute(
                "INSERT OR IGNORE INTO resource_tags(resource_id, tag_id, origin)"
                " VALUES (?, ?, 'user')",
                (resource_id, tag_id),
            )

    def unassign_tag(self, resource_id: int, tag_id: int) -> None:
        """把 Tag 从资源移除；幂等（未赋过也为成功）。"""
        with database.transaction(self.conn):
            self._require_resource(resource_id)
            self._require_tag(tag_id)
            self.conn.execute(
                "DELETE FROM resource_tags WHERE resource_id = ? AND tag_id = ?",
                (resource_id, tag_id),
            )

    # ---- Favorite --------------------------------------------------------

    def set_favorite(self, resource_id: int, favorite: bool) -> None:
        """设置 / 取消收藏（保留 Favorite 系统 Tag 的 domain convenience；幂等）。

        - resource 不存在 ⇒ :class:`ResourceNotFound`；
        - 内部幂等 ``ensure_system_tags()`` 后取 favorite tag id；
        - ``True`` ⇒ assign 语义；``False`` ⇒ unassign 语义；
        - **不写任何第二套 Favorite 状态**（唯一事实 = ``resource_tags``）。
        """
        if not isinstance(favorite, bool):
            raise InvalidTagValue("favorite", favorite)
        with database.transaction(self.conn):
            self._require_resource(resource_id)
            tag_id = self._ensure_system_tags_in_txn()[FAVORITE_TAG_KEY]
            if favorite:
                self.conn.execute(
                    "INSERT OR IGNORE INTO resource_tags(resource_id, tag_id, origin)"
                    " VALUES (?, ?, 'user')",
                    (resource_id, tag_id),
                )
            else:
                self.conn.execute(
                    "DELETE FROM resource_tags WHERE resource_id = ? AND tag_id = ?",
                    (resource_id, tag_id),
                )

    # ---- System tags bootstrap -------------------------------------------

    def ensure_system_tags(self) -> None:
        """幂等保证保留系统 Tag 存在（当前只有 ``favorite``）。

        - 不产生重复 Favorite（``ON CONFLICT(name_key) DO NOTHING``）；
        - 不改变普通 Tag；不改变 schema。
        """
        with database.transaction(self.conn):
            self._ensure_system_tags_in_txn()

    # ---- 内部 ------------------------------------------------------------

    def _ensure_system_tags_in_txn(self) -> dict[str, int]:
        """在**调用方已开启的事务内**幂等插入系统 Tag，返回 ``{key: tag_id}``。"""
        ids: dict[str, int] = {}
        for key, spec in SYSTEM_TAGS.items():
            self.conn.execute(
                "INSERT INTO tags(name, name_key, color, category)"
                " VALUES (?, ?, NULL, NULL)"
                " ON CONFLICT(name_key) DO NOTHING",
                (spec.name, spec.name_key),
            )
            row = self.conn.execute(
                "SELECT id FROM tags WHERE name_key = ?", (spec.name_key,)
            ).fetchone()
            ids[key] = int(row["id"])
        return ids

    def _find_by_key(self, name_key: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT id, name_key FROM tags WHERE name_key = ?", (name_key,)
        ).fetchone()

    def _require_tag(self, tag_id: int) -> sqlite3.Row:
        row = self.conn.execute(
            "SELECT id, name_key FROM tags WHERE id = ?", (tag_id,)
        ).fetchone()
        if row is None:
            raise TagNotFound(tag_id)
        return row

    def _require_resource(self, resource_id: int) -> None:
        row = self.conn.execute(
            "SELECT id FROM resources WHERE id = ?", (resource_id,)
        ).fetchone()
        if row is None:
            raise ResourceNotFound(resource_id)


__all__ = [
    "TagWriteService",
    "TagWriteError",
    "TagNotFound",
    "TagNameConflict",
    "ReservedTagName",
    "SystemTagImmutable",
    "InvalidTagValue",
]
