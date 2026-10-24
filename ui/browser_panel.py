"""中栏：筛选栏 + 资源网格 + 底部状态 / 加载更多 —— Phase 1.4-C-2 / C-3。

数据只经 ``BrowseService.page(...)``（**不允许**直接调用 ``ResourceQuery``）。
本层不做搜索路由 / 排序 / 缺 MOD 判定 / 类型判定——这些都在 core 里，
GUI 只负责把控件值组装成 :class:`BrowserScope`。

两种刷新路径严格区分：

- **筛选变化 / 切换 Library**：清空结果、从 offset 0 重新查询（``reload``）；
- **加载更多**：保留已有结果、按已加载数量取下一页并**追加**（``load_more``）。

Phase 1.4-C-3：preview 调度也在本层（``QThreadPool`` + ``PreviewWorker``），
并用 ``_preview_epoch`` 丢弃过期结果，避免切换筛选时「串图」。
``QPixmap`` 只在本层（GUI 线程）创建，model 只保存状态。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListView,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from core.query import BrowserScope
from core.thumbnails import (
    PREVIEW_FAILED as CORE_PREVIEW_FAILED,
    PREVIEW_MISSING as CORE_PREVIEW_MISSING,
    PREVIEW_READY as CORE_PREVIEW_READY,
    PREVIEW_UNSUPPORTED as CORE_PREVIEW_UNSUPPORTED,
    PreviewService,
)
from ui.filter_bar import FilterBar
from ui.preview_worker import PreviewWorker
from ui.resource_model import (
    PREVIEW_FAILED,
    PREVIEW_LOADING,
    PREVIEW_MISSING,
    PREVIEW_READY,
    PREVIEW_UNREQUESTED,
    PREVIEW_UNSUPPORTED,
    ResourceListModel,
)

#: 每页条数（第一版固定）。
PAGE_SIZE = 100

NO_LIBRARY_TEXT = "没有资源库\n请先使用 CLI 添加资源库"
NO_RESOURCE_TEXT = "该资源库暂无资源"
NO_MATCH_TEXT = "没有匹配的资源"


class BrowserPanel(QWidget):
    """资源浏览器：FilterBar + ResourceListView + 底部状态/加载更多。"""

    resource_selected = pyqtSignal(object)

    def __init__(self, browse_service, preview_service=None, parent=None) -> None:
        super().__init__(parent)
        self._service = browse_service
        self._preview = preview_service if preview_service is not None else PreviewService()
        self._library_id: int | None = None
        self._total = 0
        self._load_more_wanted = False
        # preview 并发控制：epoch 防串图；pending 同时充当「重复任务保护」与引用保活。
        self._preview_epoch = 0
        self._pending_previews: dict[tuple[int, int], PreviewWorker] = {}
        self._pool = QThreadPool.globalInstance()

        self.filter_bar = FilterBar(self)

        self.model = ResourceListModel(self)
        self.view = QListView()
        self.view.setModel(self.model)
        self.view.setViewMode(QListView.ViewMode.IconMode)
        self.view.setResizeMode(QListView.ResizeMode.Adjust)
        self.view.setMovement(QListView.Movement.Static)
        self.view.setUniformItemSizes(True)
        self.view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.view.setMinimumWidth(320)
        self.view.setWordWrap(True)

        self._message = QLabel("")
        self._message.setWordWrap(True)
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._stack = QStackedLayout()
        self._stack.addWidget(self.view)      # index 0
        self._stack.addWidget(self._message)  # index 1
        body = QWidget()
        body.setLayout(self._stack)

        self._status = QLabel("")
        self._load_more_button = QPushButton("加载更多")
        self._load_more_button.setVisible(False)

        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(self._status, 1)
        bottom_layout.addWidget(self._load_more_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.filter_bar)
        layout.addWidget(body, 1)
        layout.addWidget(bottom)

        selection = self.view.selectionModel()
        if selection is not None:
            selection.currentChanged.connect(self._on_current_changed)

        self.filter_bar.criteria_changed.connect(self.reload)
        self._load_more_button.clicked.connect(self.load_more)

        self.reload_relation_options()
        self.reload_tag_options()
        self._show_message(NO_LIBRARY_TEXT)

    # ---- 状态 → scope ---------------------------------------------------

    def scope(self) -> BrowserScope:
        """把当前 UI 状态组装成 frozen 的 ``BrowserScope``（不改 DTO 本身）。"""
        return BrowserScope(
            query=self.filter_bar.query(),
            resource_type=self.filter_bar.resource_type(),
            library_id=self._library_id,
            needs_review=self.filter_bar.needs_review(),
            has_missing_mods=self.filter_bar.has_missing_mods(),
            mod_guid=self.filter_bar.mod_guid(),
            plugin_guid=self.filter_bar.plugin_guid(),
            author_id=self.filter_bar.author_id(),
            tag_id=self.filter_bar.tag_id(),
            favorite=self.filter_bar.favorite_filter(),
            order_by=self.filter_bar.order_by(),
            descending=self.filter_bar.descending(),
        )

    def set_library(self, library_id: int | None) -> None:
        """切换所属 Library；``None`` 表示当前没有可浏览的库。"""
        if library_id == self._library_id:
            return
        self._library_id = library_id
        self.reload()

    # ---- 关系反查（C-5）-------------------------------------------------

    def reload_relation_options(self) -> None:
        """用 BrowseService 的只读关系列表填充 FilterBar 的三个下拉。"""
        try:
            authors = self._service.authors(with_resources=True)
            plugins = self._service.plugins()
            missing_mods = self._service.missing_mods()
        except Exception:  # noqa: BLE001 - 关系选项加载失败不应阻塞浏览
            return
        self.filter_bar.set_relation_options(
            authors=authors, plugins=plugins, missing_mods=missing_mods
        )

    def reload_tag_options(self) -> None:
        """用 BrowseService 的只读 Tag 列表填充筛选下拉。"""
        try:
            tags = self._service.tags()
        except Exception:  # noqa: BLE001 - Tag 选项加载失败不应阻塞浏览
            return
        self.filter_bar.set_tag_options(tags)

    def apply_relation_filter(
        self,
        *,
        mod_guid: str | None = None,
        author_id: int | None = None,
        plugin_guid: str | None = None,
    ) -> None:
        """应用关系筛选（例如详情面板点「按此 MOD 筛选」）。

        只设置传入的项；FilterBar 会发出 ``criteria_changed`` → ``reload()``，
        因此筛选状态与查询始终一致。
        """
        if mod_guid is not None:
            self.filter_bar.set_missing_mod(mod_guid)
        if author_id is not None:
            self.filter_bar.set_author(author_id)
        if plugin_guid is not None:
            self.filter_bar.set_plugin(plugin_guid)

    # ---- 刷新（筛选 / 切换库） -------------------------------------------

    def reload(self) -> None:
        """清空并从 offset 0 重新查询（筛选、搜索、排序、切换库都走这里）。"""
        # 任何一次「集合变化」都让旧 preview 任务作废（epoch 不匹配即丢弃）。
        self._preview_epoch += 1

        if self._library_id is None:
            self.model.clear()
            self._total = 0
            self._status.setText("")
            self._update_load_more()
            self._show_message(NO_LIBRARY_TEXT)
            self._emit_selection_cleared()
            return

        scope = self.scope()
        try:
            page = self._service.page(scope, limit=PAGE_SIZE, offset=0)
        except Exception as exc:  # noqa: BLE001 - 查询失败就地展示
            self.model.clear()
            self._total = 0
            self._status.setText("")
            self._update_load_more()
            self._show_message(f"读取资源失败：{type(exc).__name__}: {exc}")
            self._emit_selection_cleared()
            return

        self.model.set_items(page.items)
        self._total = page.total

        if page.total == 0:
            self._show_message(
                NO_MATCH_TEXT if self._has_active_filters(scope) else NO_RESOURCE_TEXT
            )
        else:
            self._stack.setCurrentIndex(0)

        self._update_status()
        self._update_load_more()
        self._schedule_previews(page.items)
        # 列表已被替换：显式通知「当前没有选中项」，确保详情面板不会残留旧资源
        # （Qt 在模型 reset 后不保证一定发出 currentChanged）。
        self._emit_selection_cleared()

    def _emit_selection_cleared(self) -> None:
        self.resource_selected.emit(None)

    # ---- 加载更多 -------------------------------------------------------

    def load_more(self) -> None:
        """取下一页并**追加**到 model（不清空已有结果）。"""
        if self._library_id is None or not self.has_more():
            return
        offset = self.model.rowCount()
        try:
            page = self._service.page(self.scope(), limit=PAGE_SIZE, offset=offset)
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"加载更多失败：{type(exc).__name__}: {exc}")
            return
        self.model.append_items(page.items)
        self._total = page.total
        self._update_status()
        self._update_load_more()
        # 只为本页**新增**的 items 调度 preview；已有 READY 的行不会被重新生成。
        self._schedule_previews(page.items)

    def has_more(self) -> bool:
        return self.model.rowCount() < self._total

    def is_load_more_visible(self) -> bool:
        return self._load_more_wanted

    def click_load_more(self) -> None:
        """供测试触发按钮（等价于用户点击）。"""
        self._load_more_button.click()

    # ---- preview 调度（GUI 线程） ----------------------------------------

    def preview_epoch(self) -> int:
        return self._preview_epoch

    def pending_preview_count(self) -> int:
        return len(self._pending_previews)

    def is_preview_pending(self, resource_id: int) -> bool:
        """该资源是否已提交了「当前 epoch」的 preview 任务（重复保护查询）。"""
        return (int(resource_id), self._preview_epoch) in self._pending_previews

    def wait_for_previews(self, timeout_ms: int = 30000) -> bool:
        """等待所有 preview 任务结束并派发已排队的信号（测试用）。"""
        done = self._pool.waitForDone(timeout_ms)
        QApplication.processEvents()
        return done

    def _schedule_previews(self, items) -> None:
        """为给定 items 调度 preview（只为当前 model 中的资源，不预加载全库）。"""
        for item in items:
            self._start_preview(item.resource)

    def _start_preview(self, resource) -> None:
        resource_id = resource.id
        wanted = self.model.preview_state(resource_id)
        if wanted not in (PREVIEW_UNREQUESTED,):
            return  # 已经 LOADING / READY / UNSUPPORTED / MISSING / FAILED：不重复提交

        key = (resource_id, self._preview_epoch)
        if key in self._pending_previews:
            return  # 同一 resource + epoch 只提交一次

        # ``status()`` 是轻量检查，允许在 GUI 线程执行（不生成、不写缓存）。
        status = self._preview.status(resource)
        if status.state == CORE_PREVIEW_READY and status.path is not None:
            pixmap = self._load_pixmap(status.path)
            if pixmap is not None:
                self.model.set_preview_state(resource_id, PREVIEW_READY, pixmap)
                return
        if status.state == CORE_PREVIEW_UNSUPPORTED:
            self.model.set_preview_state(resource_id, PREVIEW_UNSUPPORTED)
            return
        if status.state == CORE_PREVIEW_FAILED:
            self.model.set_preview_state(resource_id, PREVIEW_FAILED)
            return
        if status.state == CORE_PREVIEW_MISSING and status.cache_key is None:
            # 源文件不存在 / 不是普通文件 → 无预览，也不生成
            self.model.set_preview_state(resource_id, PREVIEW_MISSING)
            return

        # 其余情况（缓存尚未生成）→ 交给后台线程生成
        self.model.set_preview_state(resource_id, PREVIEW_LOADING)
        worker = PreviewWorker(
            self._preview, resource, epoch=self._preview_epoch, resource_id=resource_id
        )
        worker.signals.finished.connect(self._on_preview_finished)
        worker.signals.failed.connect(self._on_preview_failed)
        self._pending_previews[key] = worker
        self._pool.start(worker)

    def _on_preview_finished(self, resource_id, epoch, status) -> None:
        """worker 成功返回（已在 GUI 线程；QPixmap 只在这里创建）。"""
        self._pending_previews.pop((resource_id, epoch), None)
        if epoch != self._preview_epoch:
            return  # 过期结果：直接丢弃，绝不写入当前列表
        if resource_id is None:
            return
        rid = int(resource_id)
        if status is not None and getattr(status, "state", None) == CORE_PREVIEW_READY:
            path = getattr(status, "path", None)
            pixmap = self._load_pixmap(path) if path is not None else None
            if pixmap is not None:
                self.model.set_preview_state(rid, PREVIEW_READY, pixmap)
                return
        if status is not None and getattr(status, "state", None) == CORE_PREVIEW_FAILED:
            self.model.set_preview_state(rid, PREVIEW_FAILED)
            return
        if status is not None and getattr(status, "state", None) == CORE_PREVIEW_UNSUPPORTED:
            self.model.set_preview_state(rid, PREVIEW_UNSUPPORTED)
            return
        self.model.set_preview_state(rid, PREVIEW_MISSING)

    def _on_preview_failed(self, resource_id, epoch, message) -> None:
        """worker 抛异常（已在 GUI 线程；只标记失败，不写库、不留永久状态）。"""
        self._pending_previews.pop((resource_id, epoch), None)
        if epoch != self._preview_epoch:
            return
        if resource_id is None:
            return
        self.model.set_preview_state(int(resource_id), PREVIEW_FAILED)

    @staticmethod
    def _load_pixmap(path) -> QPixmap | None:
        """在 GUI 线程创建 QPixmap（worker 线程绝不创建 QPixmap）。"""
        if path is None:
            return None
        pixmap = QPixmap(str(path))
        return None if pixmap.isNull() else pixmap

    # ---- 状态 -----------------------------------------------------------

    def _has_active_filters(self, scope: BrowserScope) -> bool:
        return bool(
            scope.query
            or scope.resource_type is not None
            or scope.has_missing_mods is not None
            or scope.needs_review is not None
            or scope.mod_guid is not None
            or scope.plugin_guid is not None
            or scope.author_id is not None
            or scope.tag_id is not None
            or scope.favorite is not None
        )

    def _update_status(self) -> None:
        self._status.setText(
            f"共 {self._total} 条，已显示 {self.model.rowCount()} 条"
        )

    def _update_load_more(self) -> None:
        self._load_more_wanted = self._total > 0 and self.has_more()
        self._load_more_button.setVisible(self._load_more_wanted)
        self._load_more_button.setEnabled(self._load_more_wanted)

    def _show_message(self, text: str) -> None:
        self._message.setText(text)
        self._stack.setCurrentIndex(1)

    def total(self) -> int:
        return self._total

    def shown(self) -> int:
        return self.model.rowCount()

    def status_text(self) -> str:
        return self._status.text()

    def message_text(self) -> str:
        return self._message.text()

    def is_showing_message(self) -> bool:
        return self._stack.currentIndex() == 1

    # ---- 选择 -----------------------------------------------------------

    def current_resource_id(self) -> int | None:
        selection = self.view.selectionModel()
        if selection is None:
            return None
        return self.model.resource_id_at(selection.currentIndex())

    def select_row(self, row: int) -> None:
        index = self.model.index(row, 0)
        if index.isValid():
            self.view.setCurrentIndex(index)

    def select_resource(self, resource_id: int) -> bool:
        """选中当前结果页中的资源；不存在时返回 ``False``。"""
        wanted = int(resource_id)
        for row, item in enumerate(self.model.items()):
            if item.resource.id == wanted:
                self.select_row(row)
                return True
        return False

    def _on_current_changed(self, current, _previous) -> None:
        self.resource_selected.emit(self.model.resource_id_at(current))


__all__ = [
    "BrowserPanel",
    "PAGE_SIZE",
    "NO_LIBRARY_TEXT",
    "NO_RESOURCE_TEXT",
    "NO_MATCH_TEXT",
]
