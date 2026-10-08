"""Tag 领域的纯数据定义（与数据库 / UI 无关）—— Phase 3.2。

依据
----
`docs/phase3/PHASE3_2_IMPLEMENTATION_CONTRACT.md`（§4.4 / §9 / §16）。

本模块只提供**纯数据**：

- ``SystemTagSpec`` / ``SYSTEM_TAGS``：保留系统 Tag 的注册表（``name_key -> spec``）；
- ``RESERVED_SYSTEM_TAG_KEYS``：保留 key 集合；
- ``is_system_tag_key()``：按 ``name_key`` 判断是否系统 Tag。

约定
----
- system identity 由**保留 key 派生**，因此**不需要** ``tags.is_system`` 列
  （Phase 3.2 保持 schema v2 零变更）；
- ``name_key`` 是已归一化（``strip() + casefold()``）的业务身份；
  本模块**不做**再次归一化（归一化统一由 ``core.database.db.normalize_name_key`` 负责）。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 保留系统 Tag：Favorite（Phase 3.2 唯一的系统 Tag）。
FAVORITE_TAG_KEY = "favorite"


@dataclass(frozen=True)
class SystemTagSpec:
    """一个保留系统 Tag 的定义（``name_key`` 为身份，``name`` 为展示文本）。"""

    name_key: str
    name: str


#: 保留系统 Tag 注册表：``name_key -> SystemTagSpec``。
#: 新增保留 Tag 必须走 Contract 变更控制（Phase 3.0 §16）。
SYSTEM_TAGS: dict[str, SystemTagSpec] = {
    FAVORITE_TAG_KEY: SystemTagSpec(name_key=FAVORITE_TAG_KEY, name="Favorite"),
}

#: 保留 key 集合（用于拒绝用户创建 / rename 到保留 key）。
RESERVED_SYSTEM_TAG_KEYS: frozenset[str] = frozenset(SYSTEM_TAGS)


def is_system_tag_key(name_key: str | None) -> bool:
    """判断一个**已归一化**的 ``name_key`` 是否属于保留系统 Tag。

    调用方传入的应是 ``tags.name_key``（已 ``strip() + casefold()``）。
    """
    return (name_key or "") in RESERVED_SYSTEM_TAG_KEYS


__all__ = [
    "FAVORITE_TAG_KEY",
    "SystemTagSpec",
    "SYSTEM_TAGS",
    "RESERVED_SYSTEM_TAG_KEYS",
    "is_system_tag_key",
]
