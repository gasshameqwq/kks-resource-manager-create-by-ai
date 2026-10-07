"""ResourceWriteService —— Phase 3.1 唯一的用户数据 runtime 写入口。

依据
----
`docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md`（§4 / §5 / §7 Step 1）。

- 本模块是 Phase 3.1 **唯一**允许写用户数据的运行期代码（对称于 Library 侧的
  ``LibraryAdminService``）；
- 只写用户数据列与 ownership marker，**绝不**写任何 machine fact；
- 不扫描、不解析、不操作文件、不经 Query Layer、不读 Query Layer。

display_name 语义（Contract §4，冻结）
------------------------------------
::

    NULL          = no user override
    non-NULL      = user override exists
    equal-to-name = still user override（不是「无 override」信号）

    None / "" / 纯空白  → display_name = NULL（清除 override）
    非空字符串          → strip() 后保存

**禁止**用 ``display_name == name`` 判断 override 是否存在；
:meth:`ResourceWriteService.set_display_name` **不读取** ``name``，也不依赖它做任何决策。
即使解析名与展示名恰好相同（如都为 ``"Alice"``），它仍然是有效的 user override。
"""

from __future__ import annotations

import sqlite3

from core.database import db as database
from core.models import RESOURCE_TYPES


# ---------------------------------------------------------------------------
# 异常（保持简单：一个基类 + 两个具体异常，见 Contract §7 Step 1）
# ---------------------------------------------------------------------------


class ResourceWriteError(Exception):
    """ResourceWriteService 所有操作异常的基类。"""


class ResourceNotFound(ResourceWriteError):
    """目标 ``resource_id`` 不存在。"""

    def __init__(self, resource_id: int) -> None:
        self.resource_id = resource_id
        super().__init__(f"找不到资源：{resource_id}")


class InvalidResourceValue(ResourceWriteError):
    """用户提供的值非法（未知 resource_type、非字符串文本等）。"""

    def __init__(self, field: str, value: object) -> None:
        self.field = field
        self.value = value
        super().__init__(f"{field} 的取值非法：{value!r}")


# ---------------------------------------------------------------------------
# 归一化
# ---------------------------------------------------------------------------

#: 允许写入的用户列（用户数据 + ownership marker）。
#: ``updated_at`` 作为系统簿记列单独追加（Contract §5.2.1），不在此集合内。
_USER_WRITABLE_COLUMNS: frozenset[str] = frozenset(
    {"display_name", "notes", "resource_type", "type_source"}
)


def _normalize_optional_text(field: str, value: str | None) -> str | None:
    """Contract §4.1：``None`` / 空串 / 纯空白 ⇒ ``NULL``；非空 ⇒ ``strip()`` 后保存。"""
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidResourceValue(field, value)
    text = value.strip()
    return text or None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ResourceWriteService:
    """Phase 3.1 用户数据写入的唯一 runtime boundary。

    本类持有连接（与既有 ``LibraryAdminService`` 一致，短操作复用调用方连接）。
    每个 public 写方法 = 一个 ``db.transaction``；失败整体回滚并原样抛出异常。
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ---- 公共写 API ------------------------------------------------------

    def set_display_name(self, resource_id: int, value: str | None) -> None:
        """设置 / 清除用户展示名覆盖（Contract §4）。

        ``None`` / ``""`` / 纯空白 ⇒ ``display_name = NULL``（无 override）；
        非空字符串 ⇒ ``strip()`` 后保存。保存值即使与 ``name`` 完全相同，
        也仍是**有效 override**（本方法不读取、不比较 ``name``）。
        """
        normalized = _normalize_optional_text("display_name", value)
        self._update_user_columns(resource_id, {"display_name": normalized})

    def set_notes(self, resource_id: int, value: str | None) -> None:
        """设置 / 清除用户备注（``notes``，纯用户数据）。

        ``None`` / 空串 / 纯空白 ⇒ ``notes = NULL``；非空 ⇒ ``strip()`` 后保存。
        """
        normalized = _normalize_optional_text("notes", value)
        self._update_user_columns(resource_id, {"notes": normalized})

    def set_resource_type(self, resource_id: int, value: str) -> None:
        """设置用户类型修正：``resource_type = value`` 且 ``type_source = 'user'``。

        - 值必须是 ``core.models.RESOURCE_TYPES`` 之一，否则抛
          :class:`InvalidResourceValue` 且**不修改数据库**；
        - ``resource_type`` 与 ``type_source`` 在**同一个事务**内更新；
        - Phase 3.1 **不**提供 ``'user' → 'auto'`` 的回退。
        """
        if not isinstance(value, str) or value not in RESOURCE_TYPES:
            raise InvalidResourceValue("resource_type", value)
        self._update_user_columns(
            resource_id, {"resource_type": value, "type_source": "user"}
        )

    # ---- 内部 ------------------------------------------------------------

    def _update_user_columns(
        self, resource_id: int, assignments: dict[str, object]
    ) -> None:
        """在单个事务内只更新给定的用户列（外加系统簿记 ``updated_at``）。

        - **存在性优先**：先确认 resource 存在（不存在 ⇒ :class:`ResourceNotFound`），
          **不**用 "affected rows = 0" 模糊处理不同错误；
        - SQL **只**包含本次操作涉及的列，绝不整行覆盖，也不触碰 machine fact；
        - 任何失败 ⇒ 回滚并原样抛出（不吞异常）。
        """
        unknown = set(assignments) - _USER_WRITABLE_COLUMNS
        if unknown:  # 防御性：本类内部调用，键均为字面量
            raise ResourceWriteError(f"不允许写入的列：{sorted(unknown)}")

        columns = list(assignments)
        set_clause = ", ".join(f"{column} = ?" for column in columns)
        sql = (
            f"UPDATE resources SET {set_clause}, updated_at = datetime('now')"
            " WHERE id = ?"
        )
        params: list[object] = [assignments[column] for column in columns]
        params.append(resource_id)

        with database.transaction(self.conn):
            self._require_resource(resource_id)
            self.conn.execute(sql, params)

    def _require_resource(self, resource_id: int) -> None:
        row = self.conn.execute(
            "SELECT id FROM resources WHERE id = ?", (resource_id,)
        ).fetchone()
        if row is None:
            raise ResourceNotFound(resource_id)


__all__ = [
    "ResourceWriteService",
    "ResourceWriteError",
    "ResourceNotFound",
    "InvalidResourceValue",
]
