"""右栏：资源详情面板 —— Phase 1.4-C-1 → C-4。

结构（普通 Qt Widgets，无 MVC/MVVM、无自定义 delegate）::

    DetailPanel(QWidget)
    └── QStackedLayout
        ├── 状态标签（无选择 / 找不到资源 / 读取失败）
        └── QScrollArea
            └── content
                ├── Preview
                ├── Identity（标题 / 类型 / 游戏 / 库 / 相对路径）
                ├── Basic Info（扩展名 / 大小 / 修改时间 / 扫描 / 解析 /
                │                内容哈希 / 字节完全相同的资源数）
                ├── Authors
                ├── MOD Dependencies（表格；缺失明显可辨）
                ├── Usage（category 摘要 + 可折叠明细）
                ├── Plugins（默认折叠）
                ├── Metadata（人可读键 + 折叠的原始 JSON）
                └── Parse / Scan / Review

职责边界
--------
- **不查询数据库**：详情由 MainWindow 经 ``BrowseService.detail()`` 取好后传入；
  review reason 同样由 MainWindow 传入（``BrowseService.review_reasons()``）。
- **不算哈希、不判重复**：``内容哈希`` 直接来自 ``ResourceSummary.sha256``（Phase 2.1 写入、
  Phase 2.3-A 暴露）；``字节完全相同的资源数`` 直接来自 MainWindow 传入的
  ``BrowseService.duplicate_group_for()`` 结果（``DuplicateGroup``）。本面板不做任何
  相似性 / 语义推断；``sha256`` 相等**只**表示文件**字节完全相同**（byte-identical）。
- **不自算业务语义**：``installed`` / ``category`` 等一律使用 core 给出的结果。
- preview 复用 C-3：``PreviewService.status()``（GUI 线程，轻量）+
  ``PreviewWorker``（后台生成）+ ``QThreadPool``；``QPixmap`` 只在 GUI 线程创建；
  用 **selection epoch** 丢弃过期结果。
"""

from __future__ import annotations

import json
from datetime import datetime

from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.query import DuplicateGroup, ResourceDetail, ReviewReason
from core.thumbnails import (
    PREVIEW_FAILED as CORE_FAILED,
    PREVIEW_MISSING as CORE_MISSING,
    PREVIEW_READY as CORE_READY,
    PREVIEW_UNSUPPORTED as CORE_UNSUPPORTED,
    PreviewService,
)
from ui.preview_worker import PreviewWorker
from ui.resource_model import (
    PREVIEW_FAILED,
    PREVIEW_LOADING,
    PREVIEW_MISSING,
    PREVIEW_READY,
    PREVIEW_UNREQUESTED,
    PREVIEW_UNSUPPORTED,
    display_title,
    placeholder_pixmap,
)

EMPTY_TEXT = "请选择一个资源"

#: Basic 区里「内容哈希」与「字节完全相同的资源数」的行标签（稳定；文案统一由此定义）。
LABEL_CONTENT_HASH = "内容哈希"
LABEL_BYTE_DUPLICATE_COUNT = "字节完全相同的资源数"

#: 内容哈希在界面上显示的字符数（其余以 ``…`` 省略；完整值放 tooltip）。
CONTENT_HASH_DISPLAY_CHARS = 12

#: 人可读的 metadata 键（按此顺序显示，不存在则跳过）。
METADATA_READABLE_KEYS: tuple[str, ...] = (
    "card_version",
    "user_id",
    "data_id",
    "embedded_texture_count",
    "face_preview_kind",
)

_MISSING_MARK = "缺失"
_INSTALLED_MARK = "已安装"
_MISSING_COLOR = QColor(176, 0, 32)


def format_file_size(size: int | None) -> str:
    """人类可读的文件大小。"""
    if size is None:
        return "-"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def format_timestamp(value: float | None) -> str:
    """epoch 秒 → 本地时间字符串。"""
    if value is None:
        return "-"
    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return str(value)


def format_sha256(value: str | None) -> str:
    """内容哈希的展示短形式：``None`` / 空 → ``-``；否则前若干字符 + ``…``。

    只做显示截断，**不**改值、**不**计算哈希；完整值由调用方放进 tooltip。
    """
    if not value:
        return "-"
    text = str(value)
    if len(text) <= CONTENT_HASH_DISPLAY_CHARS:
        return text
    return text[:CONTENT_HASH_DISPLAY_CHARS] + "…"


class _Section(QGroupBox):
    """可折叠分组：``QGroupBox`` 勾选框控制内容可见性（最简实现）。"""

    def __init__(self, title: str, *, expanded: bool = True, parent=None) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self._content = QWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.addWidget(self._content)
        self.toggled.connect(self._content.setVisible)
        self.setChecked(expanded)
        self._content.setVisible(expanded)

    def set_content_layout(self, layout) -> None:
        self._content.setLayout(layout)

    def is_expanded(self) -> bool:
        return self.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self.setChecked(bool(expanded))


class DetailPanel(QWidget):
    """只读资源详情面板。"""

    #: 用户在 MOD 依赖表里点「按此 MOD 筛选」时发出（payload = mod guid）。
    mod_filter_requested = pyqtSignal(object)

    def __init__(self, preview_service=None, parent=None) -> None:
        super().__init__(parent)
        self._preview = preview_service if preview_service is not None else PreviewService()
        self._preview_epoch = 0
        self._pending_previews: dict[tuple[int, int], PreviewWorker] = {}
        self._pool = QThreadPool.globalInstance()

        self._current_resource_id: int | None = None
        self._current_detail: ResourceDetail | None = None
        self._current_reasons: tuple[ReviewReason, ...] = ()
        self._usage_summary: dict[str, int] = {}

        self._sections: dict[str, _Section] = {}
        self._build_ui()
        self.show_empty()

    # ---- 构建 -----------------------------------------------------------

    def _build_ui(self) -> None:
        self._status_label = QLabel(EMPTY_TEXT)
        self._status_label.setWordWrap(True)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(8, 8, 8, 8)
        self._content_layout.setSpacing(8)
        self._scroll.setWidget(content)

        self._build_preview_section()
        self._build_identity_section()
        self._build_basic_section()
        self._build_authors_section()
        self._build_mods_section()
        self._build_usage_section()
        self._build_plugins_section()
        self._build_metadata_section()
        self._build_review_section()
        self._content_layout.addStretch(1)

        self._stack = QStackedLayout(self)
        self._stack.addWidget(self._status_label)  # index 0（状态态）
        self._stack.addWidget(self._scroll)        # index 1（详情态）

    def _add_section(self, name: str, title: str, *, expanded: bool) -> _Section:
        section = _Section(title, expanded=expanded)
        self._sections[name] = section
        self._content_layout.addWidget(section)
        return section

    def _build_preview_section(self) -> None:
        section = self._add_section("preview", "预览", expanded=True)
        self.preview_label = QLabel("")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        layout = QVBoxLayout()
        layout.addWidget(self.preview_label)
        section.set_content_layout(layout)

    def _build_identity_section(self) -> None:
        self.identity_section = self._add_section("identity", "标识", expanded=True)
        self._identity_layout = QFormLayout()
        self.identity_section.set_content_layout(self._identity_layout)

    def _build_basic_section(self) -> None:
        self.basic_section = self._add_section("basic", "基本信息", expanded=True)
        self._basic_layout = QFormLayout()
        self.basic_section.set_content_layout(self._basic_layout)

    def _build_authors_section(self) -> None:
        self.authors_section = self._add_section("authors", "作者", expanded=True)
        self.authors_label = QLabel("")
        self.authors_label.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addWidget(self.authors_label)
        self.authors_section.set_content_layout(layout)

    def _build_mods_section(self) -> None:
        self.mods_section = self._add_section("mods", "MOD 依赖", expanded=True)
        self.mods_empty_label = QLabel("无 MOD 依赖")
        self.mod_table = QTableWidget(0, 4)
        self.mod_table.setHorizontalHeaderLabels(["状态", "MOD GUID", "引用数", "类别"])
        self.mod_table.verticalHeader().setVisible(False)
        self.mod_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mod_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.mod_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.mod_table.horizontalHeader().setStretchLastSection(True)
        self.mod_table.setMaximumHeight(220)
        self.mod_filter_button = QPushButton("按此 MOD 筛选")
        self.mod_filter_button.setEnabled(False)
        self.mod_filter_button.clicked.connect(self._on_mod_filter_clicked)
        self.mod_table.itemSelectionChanged.connect(self._update_mod_filter_button)
        layout = QVBoxLayout()
        layout.addWidget(self.mods_empty_label)
        layout.addWidget(self.mod_table)
        layout.addWidget(self.mod_filter_button)
        self.mods_section.set_content_layout(layout)

    def _build_usage_section(self) -> None:
        self.usage_section = self._add_section("usage", "Usage 使用情况", expanded=True)
        self.usage_summary_label = QLabel("无 usage")
        self.usage_summary_label.setWordWrap(True)
        self.usage_detail_section = _Section("明细", expanded=False)
        self.usage_list = QListWidget()
        self.usage_list.setMaximumHeight(220)
        detail_layout = QVBoxLayout()
        detail_layout.addWidget(self.usage_list)
        self.usage_detail_section.set_content_layout(detail_layout)
        layout = QVBoxLayout()
        layout.addWidget(self.usage_summary_label)
        layout.addWidget(self.usage_detail_section)
        self.usage_section.set_content_layout(layout)

    def _build_plugins_section(self) -> None:
        self.plugins_section = self._add_section("plugins", "插件", expanded=False)
        self.plugins_label = QLabel("无插件")
        self.plugins_label.setWordWrap(True)
        self.plugins_list = QListWidget()
        self.plugins_list.setMaximumHeight(160)
        layout = QVBoxLayout()
        layout.addWidget(self.plugins_label)
        layout.addWidget(self.plugins_list)
        self.plugins_section.set_content_layout(layout)

    def _build_metadata_section(self) -> None:
        self.metadata_section = self._add_section("metadata", "元数据", expanded=True)
        self.metadata_empty_label = QLabel("无元数据")
        self._metadata_layout = QFormLayout()
        self.raw_metadata_section = _Section("原始 Metadata", expanded=False)
        self.raw_metadata_edit = QPlainTextEdit()
        self.raw_metadata_edit.setReadOnly(True)
        self.raw_metadata_edit.setMaximumHeight(220)
        raw_layout = QVBoxLayout()
        raw_layout.addWidget(self.raw_metadata_edit)
        self.raw_metadata_section.set_content_layout(raw_layout)
        layout = QVBoxLayout()
        layout.addWidget(self.metadata_empty_label)
        layout.addLayout(self._metadata_layout)
        layout.addWidget(self.raw_metadata_section)
        self.metadata_section.set_content_layout(layout)

    def _build_review_section(self) -> None:
        self.review_section = self._add_section("review", "解析 / 扫描 / 待确认", expanded=True)
        self._review_layout = QFormLayout()
        self.review_reasons_label = QLabel("状态正常")
        self.review_reasons_label.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(self._review_layout)
        layout.addWidget(self.review_reasons_label)
        self.review_section.set_content_layout(layout)

    # ---- 状态：无选择 / 找不到 / 失败 ------------------------------------

    def show_empty(self) -> None:
        self._current_resource_id = None
        self._current_detail = None
        self._current_reasons = ()
        self._current_duplicate_group = None
        self._status_label.setText(EMPTY_TEXT)
        self._stack.setCurrentIndex(0)

    def show_missing(self, resource_id: int) -> None:
        self._current_resource_id = int(resource_id)
        self._current_detail = None
        self._current_reasons = ()
        self._current_duplicate_group = None
        self._status_label.setText(f"找不到资源 #{int(resource_id)}")
        self._stack.setCurrentIndex(0)

    def show_error(self, text: str) -> None:
        self._current_detail = None
        self._current_reasons = ()
        self._current_duplicate_group = None
        self._status_label.setText(f"读取详情失败：{text}")
        self._stack.setCurrentIndex(0)

    # ---- 状态：显示详情 --------------------------------------------------

    def show_detail(
        self,
        detail: ResourceDetail | None,
        resource_id: int | None = None,
        review_reasons: tuple[ReviewReason, ...] = (),
        library_name: str | None = None,
        duplicate_group: DuplicateGroup | None = None,
    ) -> None:
        """渲染完整详情（数据由 MainWindow 调 ``BrowseService`` 取得）。

        ``duplicate_group`` 为可选的 byte-duplicate 组（``BrowseService.duplicate_group_for()``
        的结果，默认 ``None``）：只有它是本资源所属的组时才表示「存在字节完全相同的资源」。
        该参数带默认值，既有调用方（不传）行为不变。
        """
        if detail is None:
            if resource_id is None:
                self.show_empty()
            else:
                self.show_missing(resource_id)
            return

        # 选择代际：切换资源后旧 preview 结果一律作废
        self._preview_epoch += 1
        self._current_resource_id = detail.resource.id
        self._current_detail = detail
        self._current_reasons = tuple(review_reasons or ())
        self._current_duplicate_group = duplicate_group

        self._render_identity(detail, library_name)
        self._render_basic(detail, duplicate_group)
        self._render_authors(detail)
        self._render_mods(detail)
        self._render_usage(detail)
        self._render_plugins(detail)
        self._render_metadata(detail)
        self._render_review(detail)
        self._schedule_preview(detail.resource)

        self._stack.setCurrentIndex(1)

    # ---- 渲染：各区域 ----------------------------------------------------

    def _set_form_rows(
        self,
        layout: QFormLayout,
        rows: list[tuple[str, str]],
        *,
        tooltips: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """重建表单行；返回 ``{标签: 展示文本}``（供测试断言）。

        ``tooltips`` 为可选的 ``{标签: tooltip 文本}``；只对命中的行生效，
        空字符串按「无 tooltip」处理。既有调用方不传该参数时行为不变。
        """
        while layout.rowCount():
            layout.removeRow(0)
        written: dict[str, str] = {}
        for label, value in rows:
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            tooltip = (tooltips or {}).get(label)
            if tooltip:
                value_label.setToolTip(tooltip)
            layout.addRow(f"{label}：", value_label)
            written[label] = value
        return written

    def _render_identity(self, detail: ResourceDetail, library_name: str | None) -> None:
        resource = detail.resource
        rows = [
            ("标题", display_title(resource)),
            ("类型", resource.resource_type),
            ("游戏", resource.game or "-"),
        ]
        if library_name:
            rows.append(("资源库", library_name))
        rows.append(("相对路径", resource.relative_path or "-"))
        self._identity_rows = self._set_form_rows(self._identity_layout, rows)
        # 完整路径放 tooltip（不直接占用版面）
        self.identity_section.setToolTip(resource.file_path)

    def _render_basic(
        self, detail: ResourceDetail, duplicate_group: DuplicateGroup | None = None
    ) -> None:
        resource = detail.resource
        # 内容哈希：直接展示已有列（只读派生值），不计算、不推断。
        sha256 = resource.sha256
        # 字节完全相同的资源数：属于 byte-duplicate 组时为组大小；否则为 1（仅本资源）。
        duplicate_count = (
            duplicate_group.member_count if duplicate_group is not None else 1
        )
        if duplicate_group is not None:
            duplicate_tooltip = (
                f"本资源与另外 {duplicate_group.member_count - 1} 个资源的文件"
                "字节完全相同（byte-identical）"
            )
        else:
            duplicate_tooltip = "没有其它与本资源文件字节完全相同的资源"
        tooltips = {
            LABEL_CONTENT_HASH: sha256 or "",
            LABEL_BYTE_DUPLICATE_COUNT: duplicate_tooltip,
        }
        self._basic_rows = self._set_form_rows(
            self._basic_layout,
            [
                ("文件类型", resource.extension or "-"),
                ("文件大小", format_file_size(resource.file_size)),
                ("修改时间", format_timestamp(resource.modified_time)),
                ("扫描状态", resource.scan_status),
                ("解析状态", resource.parse_status),
                (LABEL_CONTENT_HASH, format_sha256(sha256)),
                (LABEL_BYTE_DUPLICATE_COUNT, str(duplicate_count)),
            ],
            tooltips=tooltips,
        )
        self._basic_tooltips = {
            label: text for label, text in tooltips.items() if text
        }

    def _render_authors(self, detail: ResourceDetail) -> None:
        if detail.authors:
            names = [author.name for author in detail.authors]
            self.authors_label.setText("\n".join(names))
        else:
            raw = detail.metadata.get("authors_raw")
            if isinstance(raw, list) and raw:
                self.authors_label.setText(
                    "无作者信息\n（卡内原始作者列表：" + ", ".join(str(x) for x in raw) + "）"
                )
            else:
                self.authors_label.setText("无作者信息")

    def _render_mods(self, detail: ResourceDetail) -> None:
        self.mod_table.setRowCount(0)
        self.mod_table.clearSelection()
        self._update_mod_filter_button()
        self._mod_rows: list[tuple[str, str, int, str]] = []
        for mod in detail.mods:
            status = _MISSING_MARK if not mod.installed else _INSTALLED_MARK
            categories = ", ".join(mod.categories) if mod.categories else "-"
            row = (status, mod.mod_guid, mod.ref_count, categories)
            self._mod_rows.append(row)

            row_index = self.mod_table.rowCount()
            self.mod_table.insertRow(row_index)
            for column, text in enumerate((status, mod.mod_guid, str(mod.ref_count), categories)):
                item = QTableWidgetItem(text)
                if not mod.installed:
                    item.setForeground(_MISSING_COLOR)
                self.mod_table.setItem(row_index, column, item)

        has_mods = bool(self._mod_rows)
        self.mods_empty_label.setVisible(not has_mods)
        self.mod_table.setVisible(has_mods)

    def _render_usage(self, detail: ResourceDetail) -> None:
        counts: dict[str, int] = {}
        for usage in detail.usages:
            counts[usage.category] = counts.get(usage.category, 0) + 1
        self._usage_summary = counts

        if not detail.usages:
            self.usage_summary_label.setText("无 usage")
        else:
            ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            self.usage_summary_label.setText(
                f"共 {len(detail.usages)} 条："
                + "；".join(f"{category} {count}" for category, count in ordered)
            )

        self.usage_list.clear()
        self._usage_detail_rows: list[str] = []
        for usage in detail.usages:
            text = (
                f"[{usage.category}] {usage.property}  "
                f"slot={usage.slot}  mod={usage.mod_guid}"
            )
            self._usage_detail_rows.append(text)
            self.usage_list.addItem(text)

    def _render_plugins(self, detail: ResourceDetail) -> None:
        self.plugins_list.clear()
        for guid in detail.plugins:
            self.plugins_list.addItem(guid)
        self.plugins_label.setVisible(not detail.plugins)

    def _render_metadata(self, detail: ResourceDetail) -> None:
        metadata = detail.metadata or {}
        rows = [
            (key, str(metadata[key]))
            for key in METADATA_READABLE_KEYS
            if key in metadata and metadata[key] is not None
        ]
        self._metadata_rows = self._set_form_rows(self._metadata_layout, rows)
        self.metadata_empty_label.setVisible(not metadata)
        self.raw_metadata_edit.setPlainText(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True)
            if metadata
            else ""
        )

    def _render_review(self, detail: ResourceDetail) -> None:
        resource = detail.resource
        self._review_rows = self._set_form_rows(
            self._review_layout,
            [
                ("扫描状态", resource.scan_status),
                ("解析状态", resource.parse_status),
                ("待确认", "是" if resource.needs_review else "否"),
            ],
        )
        if not self._current_reasons:
            self.review_reasons_label.setText("状态正常")
            return
        lines = []
        for reason in self._current_reasons:
            line = reason.label
            if reason.detail:
                line += f"（{reason.detail}）"
            lines.append(line)
        self.review_reasons_label.setText("\n".join(lines))

    # ---- Preview（复用 C-3）--------------------------------------------

    def _set_preview_state(self, state: str) -> None:
        self._preview_state = state
        self.preview_label.setPixmap(placeholder_pixmap(state))

    def _schedule_preview(self, resource) -> None:
        status = self._preview.status(resource)
        if status.state == CORE_READY and status.path is not None:
            pixmap = self._load_pixmap(status.path)
            if pixmap is not None:
                self._preview_state = PREVIEW_READY
                self.preview_label.setPixmap(pixmap)
                return
        if status.state == CORE_UNSUPPORTED:
            self._set_preview_state(PREVIEW_UNSUPPORTED)
            return
        if status.state == CORE_FAILED:
            self._set_preview_state(PREVIEW_FAILED)
            return
        if status.state == CORE_MISSING and status.cache_key is None:
            self._set_preview_state(PREVIEW_MISSING)
            return

        self._set_preview_state(PREVIEW_LOADING)
        key = (int(resource.id), self._preview_epoch)
        if key in self._pending_previews:
            return
        worker = PreviewWorker(
            self._preview, resource, epoch=self._preview_epoch, resource_id=resource.id
        )
        worker.signals.finished.connect(self._on_preview_finished)
        worker.signals.failed.connect(self._on_preview_failed)
        self._pending_previews[key] = worker
        self._pool.start(worker)

    def _on_preview_finished(self, resource_id, epoch, status) -> None:
        self._pending_previews.pop((resource_id, epoch), None)
        if epoch != self._preview_epoch:
            return  # 过期结果：丢弃
        if resource_id is None or int(resource_id) != self._current_resource_id:
            return
        state = getattr(status, "state", None)
        if state == CORE_READY:
            path = getattr(status, "path", None)
            pixmap = self._load_pixmap(path) if path is not None else None
            if pixmap is not None:
                self._preview_state = PREVIEW_READY
                self.preview_label.setPixmap(pixmap)
                return
        if state == CORE_FAILED:
            self._set_preview_state(PREVIEW_FAILED)
            return
        if state == CORE_UNSUPPORTED:
            self._set_preview_state(PREVIEW_UNSUPPORTED)
            return
        self._set_preview_state(PREVIEW_MISSING)

    def _on_preview_failed(self, resource_id, epoch, message) -> None:
        self._pending_previews.pop((resource_id, epoch), None)
        if epoch != self._preview_epoch:
            return
        if resource_id is None or int(resource_id) != self._current_resource_id:
            return
        # 并发场景下另一个组件可能已经写好了缓存 → 复查一次再判定失败
        if self._current_detail is not None:
            status = self._preview.status(self._current_detail.resource)
            if status.state == CORE_READY and status.path is not None:
                pixmap = self._load_pixmap(status.path)
                if pixmap is not None:
                    self._preview_state = PREVIEW_READY
                    self.preview_label.setPixmap(pixmap)
                    return
        self._set_preview_state(PREVIEW_FAILED)

    @staticmethod
    def _load_pixmap(path) -> QPixmap | None:
        """只在 GUI 线程创建 QPixmap。"""
        if path is None:
            return None
        pixmap = QPixmap(str(path))
        return None if pixmap.isNull() else pixmap

    def wait_for_previews(self, timeout_ms: int = 30000) -> bool:
        done = self._pool.waitForDone(timeout_ms)
        QApplication.processEvents()
        return done

    def preview_epoch(self) -> int:
        return self._preview_epoch

    def pending_preview_count(self) -> int:
        return len(self._pending_previews)

    def is_preview_pending(self, resource_id: int) -> bool:
        return (int(resource_id), self._preview_epoch) in self._pending_previews

    def preview_state(self) -> str:
        return getattr(self, "_preview_state", PREVIEW_UNREQUESTED)

    def preview_pixmap(self):
        return self.preview_label.pixmap()

    # ---- 只读访问器（供测试 / 调试）-------------------------------------

    def current_resource_id(self) -> int | None:
        return self._current_resource_id

    def detail(self) -> ResourceDetail | None:
        return self._current_detail

    def review_reasons(self) -> tuple[ReviewReason, ...]:
        return self._current_reasons

    def is_empty_state(self) -> bool:
        return self._stack.currentIndex() == 0

    def status_text(self) -> str:
        return self._status_label.text()

    def body_text(self) -> str:
        """纯文本摘要（空/错误态即状态文本；详情态为 id + 名称 + 类型）。"""
        if self._stack.currentIndex() == 0 or self._current_detail is None:
            return self._status_label.text()
        resource = self._current_detail.resource
        return "\n".join(
            [
                f"Resource ID: {resource.id}",
                f"名称：{display_title(resource)}",
                f"类型：{resource.resource_type}",
            ]
        )

    def title_text(self) -> str:
        if self._current_detail is None:
            return ""
        return display_title(self._current_detail.resource)

    def identity_rows(self) -> dict[str, str]:
        return dict(getattr(self, "_identity_rows", {}))

    def basic_rows(self) -> dict[str, str]:
        return dict(getattr(self, "_basic_rows", {}))

    def basic_row_tooltips(self) -> dict[str, str]:
        """Basic 区各行的 tooltip（只包含非空 tooltip）。"""
        return dict(getattr(self, "_basic_tooltips", {}))

    def authors_text(self) -> str:
        return self.authors_label.text()

    def mod_rows(self) -> list[tuple[str, str, int, str]]:
        return list(getattr(self, "_mod_rows", []))

    def usage_summary(self) -> dict[str, int]:
        return dict(self._usage_summary)

    def usage_detail_rows(self) -> list[str]:
        return list(getattr(self, "_usage_detail_rows", []))

    def plugin_rows(self) -> list[str]:
        return [self.plugins_list.item(i).text() for i in range(self.plugins_list.count())]

    def metadata_rows(self) -> dict[str, str]:
        return dict(getattr(self, "_metadata_rows", {}))

    def raw_metadata_text(self) -> str:
        return self.raw_metadata_edit.toPlainText()

    def is_raw_metadata_read_only(self) -> bool:
        return self.raw_metadata_edit.isReadOnly()

    def review_text(self) -> str:
        return self.review_reasons_label.text()

    def review_rows(self) -> dict[str, str]:
        return dict(getattr(self, "_review_rows", {}))

    def section_expanded(self, name: str) -> bool:
        section = self._sections.get(name)
        return bool(section is not None and section.is_expanded())

    def set_section_expanded(self, name: str, expanded: bool) -> None:
        section = self._sections.get(name)
        if section is not None:
            section.set_expanded(expanded)

    # ---- MOD → 资源 闭环（C-5）------------------------------------------

    def _update_mod_filter_button(self) -> None:
        row = self.mod_table.currentRow()
        self.mod_filter_button.setEnabled(0 <= row < len(getattr(self, "_mod_rows", [])))

    def _on_mod_filter_clicked(self) -> None:
        row = self.mod_table.currentRow()
        rows = getattr(self, "_mod_rows", [])
        if 0 <= row < len(rows):
            self.mod_filter_requested.emit(rows[row][1])

    def select_mod_row(self, row: int) -> None:
        """选中 MOD 表的某一行（测试 / 交互用）。"""
        if 0 <= row < self.mod_table.rowCount():
            self.mod_table.selectRow(row)

    def is_mod_filter_enabled(self) -> bool:
        return self.mod_filter_button.isEnabled()

    def click_mod_filter(self) -> None:
        self.mod_filter_button.click()


__all__ = [
    "DetailPanel",
    "EMPTY_TEXT",
    "LABEL_CONTENT_HASH",
    "LABEL_BYTE_DUPLICATE_COUNT",
    "CONTENT_HASH_DISPLAY_CHARS",
    "METADATA_READABLE_KEYS",
    "format_file_size",
    "format_sha256",
    "format_timestamp",
]
