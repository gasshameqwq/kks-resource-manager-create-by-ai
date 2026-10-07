"""只读查询层 —— Phase 1.3-A。

把「资源管理器」需要的查询集中成稳定的 Python API，UI / CLI 通过这里访问数据库，
不直接拼 SQL、不接触 cursor。本层**只读**：任何写语句都会被拒绝（``ReadOnlyViolation``）。

主要能力
--------
- 资源 → MOD / 插件 / 作者 / 逐槽位 usage
- MOD → 资源 / usage；缺失 MOD、孤立 MOD
- 插件 → 资源；作者 → 资源
- 按 property 语义（face / body / clothes / accessory / hair / makeup / unknown）筛选
- 基础资源列表、单资源详情、单 MOD 详情、KK/KKS 格式筛选

权威来源：``resource_mod_usages``（使用事实）、``resource_plugins``（插件事实）、
``resource_authors``（作者关系）、``COUNT(resource_plugins)``（插件数）。
``resource_mods.ref_count`` 仅作便利值；``metadata_json.plugin_count`` 不作事实来源。
"""

from core.query.card_format import (
    CARD_MARKER_KK,
    CARD_MARKER_KKS,
    GAME_KK,
    GAME_KKS,
    GAMES,
    card_marker_for_game,
    game_for_card_marker,
)
from core.query.browse import (
    BrowsePage,
    BrowseService,
    BrowserScope,
    ResourceListItem,
)
from core.query.dto import (
    AuthorSummary,
    DuplicateGroup,
    LibrarySummary,
    ModDetail,
    ModSummary,
    ModUsage,
    PluginSummary,
    PropertyCategoryCount,
    PropertyCategoryStats,
    ResourceAuthor,
    ResourceDetail,
    ResourceModRef,
    ResourceSummary,
    ReviewReason,
)
from core.query.property_map import (
    ALL_PROPERTY_TOKENS,
    PROPERTY_CATEGORIES,
    PROPERTY_CATEGORY_ACCESSORY,
    PROPERTY_CATEGORY_ALL,
    PROPERTY_CATEGORY_BODY,
    PROPERTY_CATEGORY_CLOTHES,
    PROPERTY_CATEGORY_FACE,
    PROPERTY_CATEGORY_HAIR,
    PROPERTY_CATEGORY_MAKEUP,
    PROPERTY_CATEGORY_UNKNOWN,
    category_tokens,
    classify_property,
    property_block,
    sql_category_predicate,
)
from core.query.queries import (
    REVIEW_REASON_CODES,
    REVIEW_REASON_MISSING_NAME,
    REVIEW_REASON_PARSE_FAILED,
    REVIEW_REASON_PARSE_PARTIAL,
    REVIEW_REASON_UNKNOWN_PROPERTY,
    REVIEW_REASON_UNKNOWN_TYPE,
    AuthorQuery,
    LibraryQuery,
    ModQuery,
    PluginQuery,
    ReadOnlyViolation,
    ResourceQuery,
    UsageQuery,
)
from core.query.search import (
    FTS_MIN_LENGTH,
    SEARCH_MODE_FTS,
    SEARCH_MODE_LIKE,
    SEARCH_MODE_NONE,
    SEARCH_MODES,
    SearchPlan,
    fts_match_expression,
    like_pattern,
    normalize_query,
    plan_search,
)

__all__ = [
    # Browse Read Model（Phase 1.4-B.3）
    "BrowseService",
    "BrowsePage",
    "BrowserScope",
    "ResourceListItem",
    # 查询 API
    "ResourceQuery",
    "LibraryQuery",
    "ModQuery",
    "AuthorQuery",
    "PluginQuery",
    "UsageQuery",
    "ReadOnlyViolation",
    # DTO
    "ResourceSummary",
    "ResourceDetail",
    "DuplicateGroup",
    "ModSummary",
    "ModDetail",
    "ModUsage",
    "ResourceModRef",
    "ResourceAuthor",
    "AuthorSummary",
    "PluginSummary",
    "PropertyCategoryCount",
    "PropertyCategoryStats",
    "ReviewReason",
    "LibrarySummary",
    # review reason（只读推导）
    "REVIEW_REASON_CODES",
    "REVIEW_REASON_PARSE_FAILED",
    "REVIEW_REASON_PARSE_PARTIAL",
    "REVIEW_REASON_MISSING_NAME",
    "REVIEW_REASON_UNKNOWN_TYPE",
    "REVIEW_REASON_UNKNOWN_PROPERTY",
    # 文本检索（Phase 1.4-A）
    "SearchPlan",
    "plan_search",
    "normalize_query",
    "like_pattern",
    "fts_match_expression",
    "FTS_MIN_LENGTH",
    "SEARCH_MODE_NONE",
    "SEARCH_MODE_LIKE",
    "SEARCH_MODE_FTS",
    "SEARCH_MODES",
    # property 分类
    "classify_property",
    "property_block",
    "category_tokens",
    "sql_category_predicate",
    "PROPERTY_CATEGORIES",
    "PROPERTY_CATEGORY_ALL",
    "PROPERTY_CATEGORY_FACE",
    "PROPERTY_CATEGORY_BODY",
    "PROPERTY_CATEGORY_CLOTHES",
    "PROPERTY_CATEGORY_ACCESSORY",
    "PROPERTY_CATEGORY_HAIR",
    "PROPERTY_CATEGORY_MAKEUP",
    "PROPERTY_CATEGORY_UNKNOWN",
    "ALL_PROPERTY_TOKENS",
    # 游戏格式
    "GAME_KKS",
    "GAME_KK",
    "GAMES",
    "CARD_MARKER_KKS",
    "CARD_MARKER_KK",
    "card_marker_for_game",
    "game_for_card_marker",
]
