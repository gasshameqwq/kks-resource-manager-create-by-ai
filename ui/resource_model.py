"""资源列表的 Qt Model —— Phase 1.4-C-1 / C-3。

把 ``BrowseService`` 返回的 :class:`ResourceListItem` 暴露给 ``QListView``。

本层**没有业务逻辑**：不查询、不筛选、**不读取图片、不生成图片、不调用
``PreviewService``、不创建线程**；只保存数据 + UI 临时状态，并提供 Qt model roles。

preview 状态属于 UI 临时状态（**不进 core / schema**），由 ``BrowserPanel`` 调度、
通过 :meth:`ResourceListModel.set_preview_state` 写入；写入只刷新对应那一行。
"""

from __future__ import annotations

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap

from core.query import ResourceListItem, ResourceSummary

# ---- preview 状态（UI 临时状态，不落库）------------------------------------

PREVIEW_UNREQUESTED = "unrequested"
PREVIEW_LOADING = "loading"
PREVIEW_READY = "ready"
PREVIEW_UNSUPPORTED = "unsupported"
PREVIEW_MISSING = "missing"
PREVIEW_FAILED = "failed"

PREVIEW_STATES: tuple[str, ...] = (
    PREVIEW_UNREQUESTED,
    PREVIEW_LOADING,
    PREVIEW_READY,
    PREVIEW_UNSUPPORTED,
    PREVIEW_MISSING,
    PREVIEW_FAILED,
)

#: 占位图大小（像素）。
PLACEHOLDER_SIZE = 160

_PLACEHOLDER_LABELS: dict[str, str] = {
    PREVIEW_UNREQUESTED: "",
    PREVIEW_LOADING: "加载中…",
    PREVIEW_UNSUPPORTED: "不支持预览",
    PREVIEW_MISSING: "无预览",
    PREVIEW_FAILED: "预览不可用",
}

_PLACEHOLDER_CACHE: dict[str, QPixmap] = {}


def placeholder_pixmap(state: str) -> QPixmap:
    """按状态返回占位图（记忆化；**必须在 GUI 线程调用**）。"""
    cached = _PLACEHOLDER_CACHE.get(state)
    if cached is not None:
        return cached
    pixmap = QPixmap(PLACEHOLDER_SIZE, PLACEHOLDER_SIZE)
    pixmap.fill(QColor(238, 238, 238))
    painter = QPainter(pixmap)
    try:
        painter.setPen(QColor(150, 150, 150))
        painter.drawRect(0, 0, PLACEHOLDER_SIZE - 1, PLACEHOLDER_SIZE - 1)
        painter.setPen(QColor(110, 110, 110))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            _PLACEHOLDER_LABELS.get(state, ""),
        )
    finally:
        painter.end()
    _PLACEHOLDER_CACHE[state] = pixmap
    return pixmap


def display_title(resource: ResourceSummary) -> str:
    """列表显示名：``display_name`` → ``name`` → 文件名 → 完整路径。"""
    if resource.display_name:
        return resource.display_name
    if resource.name:
        return resource.name
    if resource.relative_path:
        return resource.relative_path.replace("\\", "/").rsplit("/", 1)[-1]
    return resource.file_path


class ResourceListModel(QAbstractListModel):
    """``list[ResourceListItem]`` → Qt 列表模型。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[ResourceListItem] = []
        self._preview_state: dict[int, str] = {}
        self._preview_pixmap: dict[int, QPixmap] = {}

    # ---- 只读访问 -------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return display_title(item.resource)
        if role == Qt.ItemDataRole.ToolTipRole:
            return item.resource.file_path
        if role == Qt.ItemDataRole.UserRole:
            return item.resource.id
        if role == Qt.ItemDataRole.DecorationRole:
            return self.decoration_for(item.resource.id)
        return None

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {
            int(Qt.ItemDataRole.DisplayRole): b"display",
            int(Qt.ItemDataRole.UserRole): b"resourceId",
        }

    # ---- 变更 -----------------------------------------------------------

    def set_items(self, items) -> None:
        """整体替换行数据（C-1 的刷新方式）。"""
        self.beginResetModel()
        self._items = list(items)
        self._preview_state.clear()
        self._preview_pixmap.clear()
        self.endResetModel()

    def append_items(self, items) -> None:
        """在末尾追加行（「加载更多」用）——**不清空**已有数据。"""
        new_items = list(items)
        if not new_items:
            return
        start = len(self._items)
        self.beginInsertRows(QModelIndex(), start, start + len(new_items) - 1)
        self._items.extend(new_items)
        self.endInsertRows()

    def clear(self) -> None:
        self.set_items([])

    # ---- 便捷访问 -------------------------------------------------------

    def item_at(self, index: QModelIndex) -> ResourceListItem | None:
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        return self._items[index.row()]

    def item_at_row(self, row: int) -> ResourceListItem | None:
        if not (0 <= row < len(self._items)):
            return None
        return self._items[row]

    def resource_id_at(self, index: QModelIndex) -> int | None:
        item = self.item_at(index)
        return item.resource.id if item is not None else None

    def items(self) -> list[ResourceListItem]:
        return list(self._items)

    # ---- preview 状态（UI 临时；由 BrowserPanel 写入）-------------------

    def row_for_resource(self, resource_id: int) -> int | None:
        for row, item in enumerate(self._items):
            if item.resource.id == resource_id:
                return row
        return None

    def preview_state(self, resource_id: int) -> str:
        return self._preview_state.get(resource_id, PREVIEW_UNREQUESTED)

    def preview_pixmap(self, resource_id: int) -> QPixmap | None:
        return self._preview_pixmap.get(resource_id)

    def decoration_for(self, resource_id: int) -> QPixmap:
        """DecorationRole：READY 返回缩略图，其余返回对应占位图。"""
        pixmap = self._preview_pixmap.get(resource_id)
        if pixmap is not None:
            return pixmap
        return placeholder_pixmap(self._preview_state.get(resource_id, PREVIEW_UNREQUESTED))

    def set_preview_state(
        self, resource_id: int, state: str, pixmap: QPixmap | None = None
    ) -> None:
        """更新某个资源的 preview 状态；**只刷新对应那一行**（不 reset model）。"""
        self._preview_state[resource_id] = state
        if pixmap is not None:
            self._preview_pixmap[resource_id] = pixmap
        elif state != PREVIEW_READY:
            self._preview_pixmap.pop(resource_id, None)

        row = self.row_for_resource(resource_id)
        if row is None:
            return
        index = self.index(row, 0)
        self.dataChanged.emit(
            index, index, [Qt.ItemDataRole.DecorationRole, Qt.ItemDataRole.ToolTipRole]
        )


__all__ = [
    "ResourceListModel",
    "display_title",
    "placeholder_pixmap",
    "PREVIEW_UNREQUESTED",
    "PREVIEW_LOADING",
    "PREVIEW_READY",
    "PREVIEW_UNSUPPORTED",
    "PREVIEW_MISSING",
    "PREVIEW_FAILED",
    "PREVIEW_STATES",
    "PLACEHOLDER_SIZE",
]
