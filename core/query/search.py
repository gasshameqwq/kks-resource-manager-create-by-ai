"""只读文本检索路由 —— Phase 1.4-A（Search Core）。

把「用户输入的搜索词」翻译成安全的、可与结构化筛选组合的 SQL 片段。
本模块**只做纯函数式的路由与转义，不执行任何 SQL、不持有连接**，
因此结构上不可能写库。

检索策略（与 ``docs/ARCHITECTURE.md`` §5.3 一致）
------------------------------------------------

====  ==================  ==========================================
长度   走哪条路            原因
====  ==================  ==========================================
空    不加文本条件         与原来的 ``list/count`` 行为完全一致
1–2 字 ``LIKE '%q%'``      FTS5 trigram 只索引长度 ≥ 3 的子串
≥ 3 字 ``resources_fts``   MATCH，长查询走索引
====  ==================  ==========================================

- **FTS 回退**：``app_meta.fts_enabled != '1'``（或 ``resources_fts`` 不存在）时，
  **所有长度**都走 LIKE。
- **FTS 输入安全**：用户输入被当作**整段短语**（内部引号以 ``""`` 转义），
  因此 ``AND`` / ``OR`` / ``NEAR`` / ``*`` / ``:`` / ``{`` / ``}`` 等字符
  不会改变 FTS 查询语义，也不会引发语法错误。

搜索字段（事实来源）
------------------

- 资源自身：``resources.name`` / ``resources.display_name``；
  FTS 路径用 ``{display_name name}`` 列过滤，与 LIKE 路径覆盖的列一致。
- 相对路径：``resources.relative_path``（文件名 + 用户目录）。
  **恒定走 LIKE，从不进 FTS** —— 这样 FTS 开关不会改变搜索语义，
  且能搜到「文件名与解析名不同语言」的资源（Phase 1.4-A.1）。
  不搜 ``file_path``（绝对路径噪声/跨机器不稳定）与 ``file_path_key``（身份键）。
- 作者：**只经** ``resource_authors`` + ``authors`` 关系（关系 EXISTS + LIKE）。
  **绝不使用** ``resources.author`` —— 那是 v1 死列，Phase 1.2 起不再写入。
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: FTS5 trigram 只索引长度 ≥ 3 的子串；更短的查询必须走 LIKE。
FTS_MIN_LENGTH = 3

# 检索模式（稳定标识，供测试与诊断使用）。
SEARCH_MODE_NONE = "none"   # 无文本条件
SEARCH_MODE_LIKE = "like"   # LIKE '%q%' 子串匹配
SEARCH_MODE_FTS = "fts"     # resources_fts MATCH 短语匹配

SEARCH_MODES: tuple[str, ...] = (SEARCH_MODE_NONE, SEARCH_MODE_LIKE, SEARCH_MODE_FTS)

#: LIKE 的转义字符；用户输入里的 ``%`` / ``_`` / ``\`` 会被转义成字面量。
LIKE_ESCAPE_CHAR = "\\"

#: FTS 路径检索的列（与 LIKE 路径的 name / display_name 对齐）。
_FTS_COLUMNS: tuple[str, ...] = ("display_name", "name")


# ---------------------------------------------------------------------------
# 输入归一化与路由
# ---------------------------------------------------------------------------


def normalize_query(value: str | None) -> str | None:
    """把原始查询归一化成「去掉首尾空白」的文本；空 / 纯空白返回 ``None``。

    ``None``、``""``、``"   "`` 都表示**不加文本条件**——调用方据此走原路径。
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"query 必须是 str 或 None，收到 {type(value).__name__}")
    text = value.strip()
    return text or None


@dataclass(frozen=True)
class SearchPlan:
    """一次检索的路由结果：归一化后的文本 + 选定的模式。"""

    text: str | None
    mode: str

    @property
    def is_active(self) -> bool:
        """是否需要追加文本过滤条件。"""
        return self.mode != SEARCH_MODE_NONE


def plan_search(value: str | None, *, fts_available: bool) -> SearchPlan:
    """决定一次查询走哪条路径（空 / LIKE / FTS）。

    ``fts_available=False`` 时（FTS 未启用或不可用）**所有长度**都退化为 LIKE。
    """
    text = normalize_query(value)
    if text is None:
        return SearchPlan(None, SEARCH_MODE_NONE)
    if fts_available and len(text) >= FTS_MIN_LENGTH:
        return SearchPlan(text, SEARCH_MODE_FTS)
    return SearchPlan(text, SEARCH_MODE_LIKE)


# ---------------------------------------------------------------------------
# 安全的转义 / 表达式构造（纯函数，供 queries.py 拼装 SQL）
# ---------------------------------------------------------------------------


def like_pattern(text: str) -> str:
    """构造 ``LIKE`` 用的 ``%...%`` 模式，把 ``%`` / ``_`` / ``\\`` 转成字面量。

    必须配合 ``ESCAPE '\\'`` 使用；这样 ``50%``、``a_b`` 这类输入会被当成普通
    子串，而不是通配符。
    """
    escaped = (
        text.replace(LIKE_ESCAPE_CHAR, LIKE_ESCAPE_CHAR * 2)
        .replace("%", LIKE_ESCAPE_CHAR + "%")
        .replace("_", LIKE_ESCAPE_CHAR + "_")
    )
    return f"%{escaped}%"


def fts_match_expression(text: str) -> str:
    """构造安全的 FTS5 ``MATCH`` 表达式：对 ``display_name`` / ``name`` 做短语匹配。

    形如 ``{display_name name} : "沙耶香"``：

    - 整段用双引号包成 FTS5 **短语**，语义等价于「包含该子串」；
    - 文本内部的 ``"`` 以 ``""`` 转义，用户输入无法注入 FTS5 运算符；
    - 用 ``{display_name name}`` 限定列，使 FTS 与 LIKE 两路覆盖同样的字段。
    """
    quoted = '"' + text.replace('"', '""') + '"'
    columns = " ".join(_FTS_COLUMNS)
    return f"{{{columns}}} : {quoted}"


__all__ = [
    "FTS_MIN_LENGTH",
    "SEARCH_MODE_NONE",
    "SEARCH_MODE_LIKE",
    "SEARCH_MODE_FTS",
    "SEARCH_MODES",
    "LIKE_ESCAPE_CHAR",
    "SearchPlan",
    "normalize_query",
    "plan_search",
    "like_pattern",
    "fts_match_expression",
]
