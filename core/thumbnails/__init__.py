"""缩略图缓存层 —— Phase 1.3-C-1。

``PreviewService`` 把 PNG 资源渲染成 ``data/thumbnail_cache/<cache_key>.webp``。

定位：**可丢弃的派生数据**——删除整个 ``thumbnail_cache/`` 不会损坏数据库，
也不会损坏原始资源；cache 可随时重建。本层**只读源文件、绝不写数据库**。

公共 API
--------
- ``PreviewService`` / ``PreviewStatus``
- 状态常量：``PREVIEW_UNSUPPORTED`` / ``PREVIEW_MISSING`` / ``PREVIEW_READY`` / ``PREVIEW_FAILED``
"""

from core.thumbnails.service import (
    DEFAULT_MAX_SIZE,
    DEFAULT_WEBP_QUALITY,
    PREVIEW_FAILED,
    PREVIEW_MISSING,
    PREVIEW_READY,
    PREVIEW_UNSUPPORTED,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_RESOURCE_TYPES,
    PreviewService,
    PreviewStatus,
    preview_cache_key,
)

__all__ = [
    "PreviewService",
    "PreviewStatus",
    "preview_cache_key",
    "PREVIEW_UNSUPPORTED",
    "PREVIEW_MISSING",
    "PREVIEW_READY",
    "PREVIEW_FAILED",
    "SUPPORTED_RESOURCE_TYPES",
    "SUPPORTED_EXTENSIONS",
    "DEFAULT_MAX_SIZE",
    "DEFAULT_WEBP_QUALITY",
]
