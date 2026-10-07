"""左栏：Library 列表 + 管理 / 扫描入口 —— Phase 1.4-C-1 / 1.5-A / 1.5-B。

数据只来自 ``BrowseService.libraries()``（不直接调用 ``LibraryQuery``）；
写操作只经 ``LibraryAdminService``（不直接连 SQLite、不写 SQL、不复制 Store 规则）。

状态一致性
----------
本层**不维护第二份 Library 状态**：每次操作成功后一律调用 :meth:`reload` 重新从
Query Layer 读取，GUI 绝不靠「点一下按钮就把本地 enabled 改掉」来模拟结果。

唯一的例外是**扫描任务运行状态**（``_scanning_ids``）：它只表示「当前 GUI 生命周期
内哪些 Library 的 worker 正在跑」，不是 Library / resource 的第二份数据库状态。
它由 ``MainWindow`` 拥有并同步进来（见 :meth:`set_scanning_library_ids`），
用于：扫描期间禁用按钮、禁止重复启动、以及**禁止移除正在扫描的 Library**。

本阶段（1.5-B）**不**探测磁盘变化、**不**自动扫描、**不**做进度 / 取消。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.query import LibrarySummary
from ui.library_admin_dialog import AddLibraryDialog, confirm_remove

NO_LIBRARY_TEXT = "没有资源库\n请先使用 CLI 添加资源库"

#: ``reload()`` 的选择策略。
SELECT_PREFERRED = "preferred"  # 第一个 enabled（全 disabled 时退回第一个）
SELECT_KEEP = "keep"            # 尽量保持当前选中；已不在列表中则退回 preferred

#: 扫描模式（与 ``LibraryScanner.scan(mode=...)`` 的取值一致，不新造语义）。
SCAN_INCREMENTAL = "incremental"
SCAN_FULL = "full"


class LibraryPanel(QWidget):
    """Library 导航列表 + 添加 / 启用暂停 / 移除 / 扫描入口。

    信号：

    - ``library_selected(library_id)``：当前选中的 Library id（无则 ``None``）；
    - ``scan_requested(mode)``：用户请求扫描（``"incremental"`` / ``"full"``），
      实际执行由 ``MainWindow`` 负责（本面板不建 worker、不碰数据库）。
    """

    library_selected = pyqtSignal(object)
    scan_requested = pyqtSignal(str)

    def __init__(self, browse_service, admin_service=None, parent=None) -> None:
        super().__init__(parent)
        self._service = browse_service
        self._admin = admin_service
        self._libraries: list[LibrarySummary] = []
        # 扫描任务运行状态（由 MainWindow 同步）：library_id 集合，不是数据库状态。
        self._scanning_ids: set[int] = set()
        self._scan_message = ""

        self._title = QLabel("资源库")
        self._list = QListWidget()
        self._list.setMinimumWidth(180)
        self._empty = QLabel(NO_LIBRARY_TEXT)
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error = QLabel("")
        self._error.setWordWrap(True)
        self._error.setVisible(False)

        # 管理按钮：写操作只经 LibraryAdminService（无 service 时禁用，不做假行为）。
        self.add_button = QPushButton("添加…")
        self.toggle_button = QPushButton("暂停")
        self.remove_button = QPushButton("移除…")

        # 扫描入口（Phase 1.5-B 接线）：主操作 = 增量；次级 = 全量重扫。
        # 本面板只负责发信号；worker / 刷新 / 生命周期都在 MainWindow。
        self.scan_button = QPushButton("扫描")
        self.scan_button.setToolTip("增量扫描（size + mtime 未变的文件会跳过）")
        self.full_scan_button = QPushButton("全量重扫")
        self.full_scan_button.setToolTip("忽略增量捷径，全部重新解析")

        open_row = QHBoxLayout()
        open_row.setContentsMargins(0, 0, 0, 0)
        open_row.addWidget(self.add_button)
        open_row.addWidget(self.toggle_button)
        open_row.addWidget(self.remove_button)

        scan_row = QHBoxLayout()
        scan_row.setContentsMargins(0, 0, 0, 0)
        scan_row.addWidget(self.scan_button)
        scan_row.addWidget(self.full_scan_button)

        self._scan_status = QLabel("")
        self._scan_status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addWidget(self._list)
        layout.addWidget(self._empty)
        layout.addWidget(self._error)
        layout.addLayout(open_row)
        layout.addLayout(scan_row)
        layout.addWidget(self._scan_status)

        self._list.currentItemChanged.connect(self._on_current_item_changed)
        self.add_button.clicked.connect(self._on_add_clicked)
        self.toggle_button.clicked.connect(self._on_toggle_clicked)
        self.remove_button.clicked.connect(self._on_remove_clicked)
        self.scan_button.clicked.connect(self._on_scan_clicked)
        self.full_scan_button.clicked.connect(self._on_full_scan_clicked)

        self.reload()

    # ---- 数据 -----------------------------------------------------------

    def reload(self, select: int | str | None = SELECT_PREFERRED) -> None:
        """重新从 Query Layer 载入 Library 列表。

        ``select`` 决定载入后的选中项：

        - ``SELECT_PREFERRED``（默认）：第一个 enabled 的库（全 disabled 时退回第一个，
          不修改其状态）；
        - ``SELECT_KEEP``：尽量保持当前选中（仍在列表中），否则退回 preferred；
        - ``None``：不选中任何库；
        - ``<int>``：选中该 id 的库（不存在则退回 preferred）。
        """
        self._error.setVisible(False)
        previous_id = self.current_library_id()

        # 重建列表期间屏蔽信号，最后只统一发一次 library_selected，避免中间态抖动。
        self._list.blockSignals(True)
        try:
            self._list.clear()
            try:
                self._libraries = list(self._service.libraries())
            except Exception as exc:  # noqa: BLE001 - 启动级错误就地展示
                self._libraries = []
                self._error.setText(f"读取资源库失败：{type(exc).__name__}: {exc}")
                self._error.setVisible(True)

            for library in self._libraries:
                self._list.addItem(self._make_item(library))

            row = self._target_row(select, previous_id)
            if row is None:
                self._list.setCurrentRow(-1)
                self._list.clearSelection()
            else:
                self._list.setCurrentRow(row)
        finally:
            self._list.blockSignals(False)

        self._empty.setVisible(not self._libraries)
        self._update_actions()
        self.library_selected.emit(self.current_library_id())

    def _make_item(self, library: LibrarySummary) -> QListWidgetItem:
        item = QListWidgetItem(self._item_text(library))
        item.setData(Qt.ItemDataRole.UserRole, library.id)
        return item

    def _item_text(self, library: LibrarySummary) -> str:
        text = f"{library.name} ({library.resource_count})"
        if not library.enabled:
            text += "  [disabled]"
        if library.id in self._scanning_ids:
            text += "  [扫描中…]"
        return text

    def _update_item_texts(self) -> None:
        """只重算行文本（不重新查询、不动选中）。"""
        for row, library in enumerate(self._libraries):
            item = self._list.item(row)
            if item is not None:
                item.setText(self._item_text(library))

    def _target_row(self, select, previous_id: int | None) -> int | None:
        """把选择策略解析成行号（``None`` 表示不选中）。"""
        if not self._libraries:
            return None
        if select is None:
            return None
        if select == SELECT_KEEP:
            if previous_id is not None:
                for row, library in enumerate(self._libraries):
                    if library.id == previous_id:
                        return row
            return self._preferred_row()
        if isinstance(select, int) and select != SELECT_PREFERRED:
            for row, library in enumerate(self._libraries):
                if library.id == select:
                    return row
            return self._preferred_row()
        return self._preferred_row()

    def _preferred_row(self) -> int:
        """第一个 enabled 的库；若全为 disabled，则退回第一个（不修改其状态）。"""
        for row, library in enumerate(self._libraries):
            if library.enabled:
                return row
        return 0

    # ---- 扫描任务状态（由 MainWindow 同步） -----------------------------

    def set_scanning_library_ids(self, library_ids) -> None:
        """同步「当前正在扫描的 Library id 集合」（由 MainWindow 拥有）。"""
        self._scanning_ids = {int(lid) for lid in library_ids}
        self._update_item_texts()
        self._update_actions()

    def scanning_library_ids(self) -> set[int]:
        return set(self._scanning_ids)

    def is_scanning(self, library_id) -> bool:
        return library_id is not None and int(library_id) in self._scanning_ids

    def set_scan_message(self, text: str) -> None:
        """设置扫描结果 / 状态提示（空串表示清除）。"""
        self._scan_message = text or ""
        self._update_scan_status()

    def scan_status_text(self) -> str:
        return self._scan_status.text()

    def _update_scan_status(self) -> None:
        library = self._selected_library()
        if library is not None and library.id in self._scanning_ids:
            self._scan_status.setText("扫描中…")
        else:
            self._scan_status.setText(self._scan_message)

    # ---- 访问 -----------------------------------------------------------

    def libraries(self) -> list[LibrarySummary]:
        return list(self._libraries)

    def current_library_id(self) -> int | None:
        item = self._list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _selected_library(self) -> LibrarySummary | None:
        library_id = self.current_library_id()
        if library_id is None:
            return None
        for library in self._libraries:
            if library.id == library_id:
                return library
        return None

    def item_text(self, row: int) -> str | None:
        item = self._list.item(row)
        return item.text() if item is not None else None

    def count(self) -> int:
        return self._list.count()

    def has_libraries(self) -> bool:
        return bool(self._libraries)

    def is_empty(self) -> bool:
        return not self._libraries

    def error_text(self) -> str:
        return self._error.text()

    def actions_enabled(self) -> bool:
        """写操作入口是否可用（需要 LibraryAdminService）。"""
        return self._admin is not None

    def _require_admin(self):
        if self._admin is None:
            raise RuntimeError("未配置 LibraryAdminService，无法执行写操作")
        return self._admin

    # ---- 写操作（供按钮与测试共同调用） ---------------------------------

    def add_library(
        self,
        root_path,
        *,
        name: str | None = None,
        notes: str = "",
        enabled: bool = True,
        allow_missing: bool = False,
    ):
        """添加 Library：转发给 ``LibraryAdminService``，然后重新查询并选中新库。

        异常（例如重复 root_path 的 ``LibraryAlreadyExists``）原样向上抛，
        由调用方（对话框路径）决定如何展示。
        """
        library = self._require_admin().add_library(
            root_path,
            name=name,
            notes=notes,
            enabled=enabled,
            allow_missing=allow_missing,
        )
        self.reload(select=library.id)
        return library

    def set_library_enabled(self, library_id: int, enabled: bool):
        """启用 / 暂停：写库后重新查询（不做本地状态模拟），并尽量保持当前选中。"""
        library = self._require_admin().set_enabled(library_id, enabled)
        self.reload(select=SELECT_KEEP)
        return library

    def remove_library(self, library_id: int):
        """移除 Library：写库后重新查询，并清空当前选中（中 / 右栏回到空状态）。"""
        report = self._require_admin().remove_library(library_id)
        self.reload(select=None)
        return report

    # ---- 按钮槽 ---------------------------------------------------------

    def _on_add_clicked(self) -> None:
        values = self._prompt_add_library()
        if values is None:
            return
        try:
            self.add_library(**values)
        except Exception as exc:  # noqa: BLE001 - 就地展示，不崩溃
            QMessageBox.warning(self, "添加资源库失败", str(exc))

    def _prompt_add_library(self) -> dict | None:
        """弹出添加对话框；取消返回 ``None``（测试可覆写）。"""
        dialog = AddLibraryDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.values()

    def _on_toggle_clicked(self) -> None:
        library = self._selected_library()
        if library is None:
            return
        try:
            self.set_library_enabled(library.id, not library.enabled)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "操作失败", str(exc))

    def _on_remove_clicked(self) -> None:
        library = self._selected_library()
        if library is None:
            return
        # 扫描竞态防护：正在扫描的 Library 绝不允许移除（不只依赖按钮禁用）。
        if library.id in self._scanning_ids:
            QMessageBox.information(
                self, "无法移除", "该资源库正在扫描，请等待扫描完成。"
            )
            return
        try:
            report = self._require_admin().preview_removal(library.id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "移除资源库失败", str(exc))
            return
        if not confirm_remove(self, report):
            return
        try:
            self.remove_library(library.id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "移除资源库失败", str(exc))

    def _on_scan_clicked(self) -> None:
        self.scan_requested.emit(SCAN_INCREMENTAL)

    def _on_full_scan_clicked(self) -> None:
        self.scan_requested.emit(SCAN_FULL)

    # ---- 事件 -----------------------------------------------------------

    def _on_current_item_changed(self, current, _previous) -> None:
        self._update_actions()
        if current is None:
            self.library_selected.emit(None)
            return
        value = current.data(Qt.ItemDataRole.UserRole)
        self.library_selected.emit(int(value) if value is not None else None)

    def _update_actions(self) -> None:
        has_admin = self._admin is not None
        library = self._selected_library()
        current_scanning = library is not None and library.id in self._scanning_ids
        any_scanning = bool(self._scanning_ids)

        self.add_button.setEnabled(has_admin)
        self.toggle_button.setEnabled(has_admin and library is not None and not current_scanning)
        self.remove_button.setEnabled(has_admin and library is not None and not current_scanning)

        # 扫描按钮：**同一时刻只允许一个扫描在跑**（不同 Library 也不并发）——
        # 连接没有 busy_timeout 之外的协调，两个扫描并发写会争用 SQLite 写锁；
        # 单扫描既满足「同一 Library 不重复启动」，又避免 database is locked。
        can_scan = has_admin and library is not None and not any_scanning
        self.scan_button.setEnabled(can_scan)
        self.full_scan_button.setEnabled(can_scan)

        self.toggle_button.setText(
            "启用" if (library is not None and not library.enabled) else "暂停"
        )
        self._update_scan_status()


__all__ = [
    "LibraryPanel",
    "NO_LIBRARY_TEXT",
    "SELECT_PREFERRED",
    "SELECT_KEEP",
    "SCAN_INCREMENTAL",
    "SCAN_FULL",
]
