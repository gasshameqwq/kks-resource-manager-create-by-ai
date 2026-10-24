"""主窗口 —— Phase 1.4-C-1 / C-3 / 1.5-A / 1.5-B。

结构::

    MainWindow (QMainWindow)
    ├── LibraryPanel   左：资源库列表 + 管理 / 扫描入口
    ├── BrowserPanel   中：资源网格（QListView + ResourceListModel）
    └── DetailPanel    右：详情面板

职责边界
--------
- MainWindow 只做：创建 service、创建三个 panel、连接信号、协调后台扫描、处理启动级错误。
- **不写 SQL**、不做筛选 / preview / 扫描规则；读数据一律经 ``BrowseService``，
  写操作经 ``core.app.LibraryAdminService``，扫描经 ``core.app.run_scan``（后台 worker）。
- 数据库连接沿用项目既有机制（``core.database.db.initialize/connect``），
  不新造第二套连接管理；UI 不直接 ``sqlite3.connect``。

扫描（Phase 1.5-B）
------------------
- 后台执行：``ScanWorker(QRunnable)`` + ``QThreadPool``（与缩略图同一线程池）；
- GUI 只维护**任务运行状态** ``_scanning``（library_id → worker）：它不是 Library /
  resource 的第二份数据库状态，只用于禁用按钮、禁止重复启动、禁止移除扫描中的库、
  以及关窗时的等待策略；
- 扫描完成后**统一从 Query Layer / BrowseService 重新读取**，ScanResult 只用于
  显示一句完成提示，不缓存成 GUI 状态。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from core.app import (
    LibraryAdminService,
    ResourceWriteError,
    ResourceWriteService,
    TagWriteError,
    TagWriteService,
)
from core.scanner import RESULT_SKIPPED, SCAN_COMPLETED
from ui.browser_panel import BrowserPanel
from ui.detail_panel import DetailPanel
from ui.library_panel import (
    SCAN_FULL,
    SCAN_INCREMENTAL,
    SELECT_KEEP,
    LibraryPanel,
)
from ui.scan_worker import ScanWorker

WINDOW_TITLE = "KKS Resource Manager"

#: 关窗时等待后台扫描完成的单次超时（毫秒）。
CLOSE_WAIT_MS = 15000


def _open_browse_service():
    """用项目既有机制打开数据库并构造 ``BrowseService``。"""
    from core.database import db as database
    from core.query import BrowseService

    database.initialize()
    conn = database.connect()
    return conn, BrowseService(conn)


# ---------------------------------------------------------------------------
# 关窗确认（模块级函数 → 测试可覆写，不弹阻塞对话框）
# ---------------------------------------------------------------------------


def confirm_close_during_scan(parent) -> bool:
    """扫描进行中关窗：``True`` = 等待完成后退出，``False`` = 取消（继续扫描）。"""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("扫描进行中")
    box.setText("扫描仍在进行，是否等待完成后退出？")
    wait_button = box.addButton("等待并退出", QMessageBox.ButtonRole.AcceptRole)
    cancel_button = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(wait_button)
    box.exec()
    return box.clickedButton() is wait_button


def confirm_keep_waiting(parent) -> bool:
    """等待超时后再次询问：``True`` = 继续等待，``False`` = 现在退出。"""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("扫描仍在进行")
    box.setText("扫描仍未完成。继续等待，还是现在退出？")
    keep_button = box.addButton("继续等待", QMessageBox.ButtonRole.AcceptRole)
    quit_button = box.addButton("现在退出", QMessageBox.ButtonRole.DestructiveRole)
    box.setDefaultButton(keep_button)
    box.exec()
    return box.clickedButton() is keep_button


class MainWindow(QMainWindow):
    """三栏主窗口。``browse_service`` 为空时按项目既有机制自行打开数据库。"""

    def __init__(
        self,
        browse_service=None,
        preview_service=None,
        admin_service=None,
        tag_write_service=None,
        resource_write_service=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1200, 720)

        self._conn = None
        self._owns_connection = False
        self._startup_error: str | None = None
        self.library_panel: LibraryPanel | None = None
        self.browser_panel: BrowserPanel | None = None
        self.detail_panel: DetailPanel | None = None
        # 扫描任务运行状态：library_id → ScanWorker（不是数据库状态）。
        self._scanning: dict[int, ScanWorker] = {}

        service = browse_service
        if service is None:
            try:
                self._conn, service = _open_browse_service()
                self._owns_connection = True
            except Exception as exc:  # noqa: BLE001 - 启动级错误就地展示
                self._startup_error = f"{type(exc).__name__}: {exc}"

        self._service = service
        self._preview_service = preview_service
        self._admin_service = admin_service
        self._tag_write_service = tag_write_service
        self._resource_write_service = resource_write_service

        if self._startup_error is not None:
            self.setCentralWidget(self._build_error_widget(self._startup_error))
            return

        if self._preview_service is None:
            from core.thumbnails import PreviewService

            self._preview_service = PreviewService()

        conn = getattr(self._service, "conn", None)
        if conn is not None:
            if self._tag_write_service is None:
                self._tag_write_service = TagWriteService(conn)
            if self._resource_write_service is None:
                self._resource_write_service = ResourceWriteService(conn)

        self._build_ui()

    # ---- 构建 -----------------------------------------------------------

    def _build_ui(self) -> None:
        if self._admin_service is None:
            conn = getattr(self._service, "conn", None)
            if conn is not None:
                self._admin_service = LibraryAdminService(conn)

        self.library_panel = LibraryPanel(self._service, self._admin_service)
        self.browser_panel = BrowserPanel(self._service, self._preview_service)
        self.detail_panel = DetailPanel(self._preview_service)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.library_panel)
        splitter.addWidget(self.browser_panel)
        splitter.addWidget(self.detail_panel)
        splitter.setSizes([220, 660, 320])
        splitter.setChildrenCollapsible(False)
        self.setCentralWidget(splitter)

        self.library_panel.library_selected.connect(self._on_library_selected)
        self.library_panel.scan_requested.connect(self._on_scan_requested)
        self.browser_panel.resource_selected.connect(self._on_resource_selected)
        self.detail_panel.mod_filter_requested.connect(self._on_mod_filter_requested)
        self.detail_panel.tag_assign_requested.connect(self._on_tag_assign_requested)
        self.detail_panel.tag_unassign_requested.connect(
            self._on_tag_unassign_requested
        )
        self.detail_panel.tag_create_requested.connect(
            self._on_tag_create_requested
        )
        self.detail_panel.favorite_change_requested.connect(
            self._on_favorite_change_requested
        )
        self.detail_panel.display_name_save_requested.connect(
            self._on_display_name_save_requested
        )
        self.detail_panel.notes_save_requested.connect(
            self._on_notes_save_requested
        )
        self.detail_panel.resource_type_save_requested.connect(
            self._on_resource_type_save_requested
        )

        # 首次加载：LibraryPanel 构造时已选中默认库，这里同步启动中栏。
        self.detail_panel.show_empty()
        self.detail_panel.set_available_tags(self._service.tags())
        self._on_library_selected(self.library_panel.current_library_id())

    def _build_error_widget(self, message: str) -> QLabel:
        label = QLabel(f"启动失败：{message}")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    # ---- 槽 -------------------------------------------------------------

    def _on_library_selected(self, library_id) -> None:
        if self.browser_panel is None or self.detail_panel is None:
            return
        self.detail_panel.show_empty()
        self.browser_panel.set_library(library_id)

    def _on_resource_selected(self, resource_id) -> None:
        if self.detail_panel is None:
            return
        if resource_id is None:
            self.detail_panel.show_empty()
            return
        rid = int(resource_id)
        try:
            detail = self._service.detail(rid)
            reasons = self._service.review_reasons(rid) if detail is not None else ()
            # byte-duplicate 信息同样只经 BrowseService（GUI 不直接访问 Query Layer）。
            duplicate_group = (
                self._service.duplicate_group_for(rid) if detail is not None else None
            )
            tags = self._service.tags()
        except Exception as exc:  # noqa: BLE001 - 单次查询失败不影响界面
            self.detail_panel.show_error(f"{type(exc).__name__}: {exc}")
            return
        self.detail_panel.set_available_tags(tags)
        self.detail_panel.show_detail(
            detail,
            rid,
            reasons,
            self._current_library_name(),
            duplicate_group,
        )

    def _current_library_name(self) -> str | None:
        """当前浏览的 Library 名（详情面板展示用；不查库，复用已加载列表）。"""
        if self.library_panel is None or self.browser_panel is None:
            return None
        library_id = self.browser_panel.scope().library_id
        if library_id is None:
            return None
        for library in self.library_panel.libraries():
            if library.id == library_id:
                return library.name
        return None

    def _on_mod_filter_requested(self, mod_guid) -> None:
        """详情面板点「按此 MOD 筛选」→ 让中栏按该 MOD 过滤（不新建页面/导航栈）。"""
        if self.browser_panel is None or mod_guid is None:
            return
        self.browser_panel.apply_relation_filter(mod_guid=str(mod_guid))

    # ---- Tag / Favorite / 资源字段写入（Phase 3.5.2）-------------------

    def tag_write_service(self):
        return self._tag_write_service

    def resource_write_service(self):
        return self._resource_write_service

    def _on_tag_assign_requested(self, resource_id, tag_id) -> None:
        if self._tag_write_service is None:
            self._show_write_error(resource_id, "TagWriteService 不可用")
            return
        self._perform_ui_write(
            resource_id,
            lambda: self._tag_write_service.assign_tag(
                int(resource_id), int(tag_id)
            ),
            "已添加标签",
        )

    def _on_tag_unassign_requested(self, resource_id, tag_id) -> None:
        if self._tag_write_service is None:
            self._show_write_error(resource_id, "TagWriteService 不可用")
            return
        self._perform_ui_write(
            resource_id,
            lambda: self._tag_write_service.unassign_tag(
                int(resource_id), int(tag_id)
            ),
            "已移除标签",
        )

    def _on_tag_create_requested(self, resource_id, name) -> None:
        if self._tag_write_service is None:
            self._show_write_error(resource_id, "TagWriteService 不可用")
            return

        def create_and_assign() -> None:
            tag_id = self._tag_write_service.create_tag(str(name))
            self._tag_write_service.assign_tag(int(resource_id), tag_id)

        self._perform_ui_write(
            resource_id,
            create_and_assign,
            f"已创建并添加标签：{name}",
        )

    def _on_favorite_change_requested(self, resource_id, favorite) -> None:
        if self._tag_write_service is None:
            self._show_write_error(resource_id, "TagWriteService 不可用")
            return
        action = "收藏" if favorite else "取消收藏"
        self._perform_ui_write(
            resource_id,
            lambda: self._tag_write_service.set_favorite(
                int(resource_id), bool(favorite)
            ),
            f"已{action}",
        )

    def _on_display_name_save_requested(self, resource_id, value) -> None:
        if self._resource_write_service is None:
            self._show_write_error(resource_id, "ResourceWriteService 不可用")
            return
        message = "已清除展示名覆盖" if value is None else "已保存展示名覆盖"
        self._perform_ui_write(
            resource_id,
            lambda: self._resource_write_service.set_display_name(
                int(resource_id), value
            ),
            message,
        )

    def _on_notes_save_requested(self, resource_id, value) -> None:
        if self._resource_write_service is None:
            self._show_write_error(resource_id, "ResourceWriteService 不可用")
            return
        message = "已清除备注" if value is None else "已保存备注"
        self._perform_ui_write(
            resource_id,
            lambda: self._resource_write_service.set_notes(
                int(resource_id), value
            ),
            message,
        )

    def _on_resource_type_save_requested(self, resource_id, value) -> None:
        if self._resource_write_service is None:
            self._show_write_error(resource_id, "ResourceWriteService 不可用")
            return
        self._perform_ui_write(
            resource_id,
            lambda: self._resource_write_service.set_resource_type(
                int(resource_id), str(value)
            ),
            f"已保存资源类型修正：{value}",
        )

    def _perform_ui_write(self, resource_id, action, success_message: str) -> bool:
        """执行一次服务写入，再从 Query/Browse 层重建视图。"""
        try:
            action()
        except (TagWriteError, ResourceWriteError) as exc:
            self._refresh_after_ui_write(int(resource_id))
            self._show_write_error(resource_id, str(exc))
            return False
        except Exception as exc:  # noqa: BLE001 - 单次写失败不影响窗口
            self._refresh_after_ui_write(int(resource_id))
            self._show_write_error(
                resource_id, f"{type(exc).__name__}: {exc}"
            )
            return False

        self._refresh_after_ui_write(int(resource_id))
        if (
            self.detail_panel is not None
            and self.detail_panel.current_resource_id() == int(resource_id)
        ):
            self.detail_panel.show_operation_message(success_message)
        return True

    def _show_write_error(self, resource_id, message: str) -> None:
        if self.detail_panel is None:
            return
        text = f"写入失败：{message}"
        if self.detail_panel.current_resource_id() == int(resource_id):
            self.detail_panel.show_operation_message(text, error=True)
        else:
            self.detail_panel.show_error(text)

    def _refresh_after_ui_write(self, resource_id: int) -> None:
        """刷新 Tag 选项与筛选结果；资源仍匹配时恢复详情选择。"""
        if self.browser_panel is None or self.detail_panel is None:
            return
        self.browser_panel.reload_tag_options()
        self.detail_panel.set_available_tags(self._service.tags())
        self.browser_panel.reload()
        if not self.browser_panel.select_resource(resource_id):
            self.detail_panel.show_empty()
            return
        if self.detail_panel.current_resource_id() != resource_id:
            self._on_resource_selected(resource_id)

    # ---- 扫描（Phase 1.5-B） --------------------------------------------

    def _on_scan_requested(self, mode) -> None:
        self.start_scan(mode)

    def start_scan(self, mode: str = SCAN_INCREMENTAL):
        """启动一次后台扫描；返回 worker，未启动返回 ``None``。

        未启动的情形：模式非法 / 没有选中 Library / 同一 Library 已在扫描 /
        拿不到数据库路径。**不排队**：重复点击直接忽略。
        """
        if mode not in (SCAN_INCREMENTAL, SCAN_FULL):
            return None
        if self.library_panel is None:
            return None
        library_id = self.library_panel.current_library_id()
        if library_id is None or library_id in self._scanning:
            return None
        if self._scanning:
            # 单扫描策略：同一时刻最多一个 worker（也避免并发写争用 SQLite 写锁）。
            return None
        db_path = self._resolve_db_path()
        if not db_path:
            return None

        worker = ScanWorker(db_path, library_id, mode=mode)
        # 信号连到 MainWindow 的绑定方法（QObject，位于 GUI 线程）→ 队列连接，
        # 保证 finished / failed 一定在 GUI 线程处理。
        worker.signals.finished.connect(self._on_scan_finished)
        worker.signals.failed.connect(self._on_scan_failed)

        self._scanning[library_id] = worker
        self.library_panel.set_scan_message("")
        self._sync_scan_state()
        QThreadPool.globalInstance().start(worker)
        return worker

    def _resolve_db_path(self) -> str | None:
        """后台 worker 要用的数据库路径（连接本身不能跨线程，只能传路径）。"""
        if self._admin_service is not None:
            path = self._admin_service.database_path()
            if path:
                return path
        from core import app_paths

        return str(app_paths.db_path())

    def _sync_scan_state(self) -> None:
        if self.library_panel is not None:
            self.library_panel.set_scanning_library_ids(set(self._scanning))

    def _on_scan_finished(self, result) -> None:
        """worker 成功返回（已在 GUI 线程）：清除状态 + 统一刷新。"""
        library_id = getattr(result, "library_id", None)
        if library_id is not None:
            self._scanning.pop(int(library_id), None)
        self._sync_scan_state()

        if getattr(result, "status", None) == SCAN_COMPLETED:
            # 只有真的完成才刷新；skipped / failed 不假装成功。
            self._refresh_after_scan()

        if self.library_panel is not None:
            self.library_panel.set_scan_message(self._describe_scan_result(result))

    def _on_scan_failed(self, library_id, message) -> None:
        """worker 抛异常（已在 GUI 线程）：清除状态、恢复按钮、显示错误。"""
        if library_id is not None:
            self._scanning.pop(int(library_id), None)
        self._sync_scan_state()
        if self.library_panel is not None:
            self.library_panel.set_scan_message(f"扫描失败：{message}")

    def _refresh_after_scan(self) -> None:
        """扫描完成后**统一从 Query Layer 重新读取**（不维护第二份状态）。

        保持用户当前选择（``SELECT_KEEP``）：扫描的是 A 但用户在浏览 B 时，
        这里不会把选择强制切回 A。
        """
        if self.library_panel is None or self.browser_panel is None:
            return
        # 1) 左栏：名称 / enabled / resource_count
        self.library_panel.reload(select=SELECT_KEEP)
        # 2) 中栏：关系下拉 + 资源列表 / total / 空态
        self.browser_panel.reload_relation_options()
        self.browser_panel.reload()
        # 3) 右栏：reload 会清空 selection，Detail 由现有链路回到空状态

    @staticmethod
    def _describe_scan_result(result) -> str:
        """把 ScanResult 变成一句提示（不缓存成 GUI 状态）。"""
        status = getattr(result, "status", None)
        if status == SCAN_COMPLETED:
            stats = result.stats
            return (
                f"扫描完成：发现 {stats.discovered}，新增 {stats.inserted}，"
                f"更新 {stats.updated}，跳过 {stats.skipped}，"
                f"缺失 {stats.missing}，失败 {stats.failed}"
            )
        if status == RESULT_SKIPPED:
            return f"未扫描：{getattr(result, 'skip_reason', None) or '已跳过'}"
        issues = getattr(result, "issues", None) or []
        detail = issues[0].message if issues else None
        if not detail:
            detail = getattr(result, "skip_reason", None) or "未知错误"
        return f"扫描失败：{detail}"

    # ---- 扫描状态访问（供测试 / 外部读取） ------------------------------

    def scanning_library_ids(self) -> set[int]:
        return set(self._scanning)

    def is_scanning(self, library_id) -> bool:
        return library_id is not None and int(library_id) in self._scanning

    def wait_for_scans(self, timeout_ms: int = 30000) -> bool:
        """等待后台任务（含缩略图与扫描）结束并派发已排队信号（测试用）。"""
        done = QThreadPool.globalInstance().waitForDone(timeout_ms)
        QApplication.processEvents()
        return done

    # ---- 生命周期 -------------------------------------------------------

    def startup_error(self) -> str | None:
        return self._startup_error

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt 约定
        if not self._prepare_to_close():
            event.ignore()
            return
        if self._owns_connection and self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001 - 关闭失败不应阻塞退出
                pass
            self._conn = None
        super().closeEvent(event)

    def _prepare_to_close(self) -> bool:
        """返回 ``True`` 表示可以关闭窗口。

        扫描进行中时先征求用户确认；等待有超时，超时后再问一次。
        全程**不主动杀线程**、**不从 GUI 线程关闭 worker 的连接** ——
        worker 的连接由 ``run_scan()`` 的 ``finally`` 关闭。
        """
        while self._scanning:
            if not confirm_close_during_scan(self):
                return False  # 取消：不关窗，扫描继续
            if self._wait_for_background_workers(CLOSE_WAIT_MS):
                break
            if not confirm_keep_waiting(self):
                break  # 用户不想再等 → 走退出流程（下面仍会给一小段等待）
        # 兜底：等待缩略图等其它后台任务结束（沿用 C-5 的机制）。
        self._wait_for_background_workers()
        return True

    @staticmethod
    def _wait_for_background_workers(timeout_ms: int = 5000) -> bool:
        try:
            return bool(QThreadPool.globalInstance().waitForDone(timeout_ms))
        except Exception:  # noqa: BLE001 - 退出路径不应再抛异常
            return True


def create_main_window(
    browse_service=None,
    preview_service=None,
    admin_service=None,
    tag_write_service=None,
    resource_write_service=None,
) -> MainWindow:
    """创建主窗口；``browse_service`` 为空时按项目既有机制打开数据库。"""
    return MainWindow(
        browse_service,
        preview_service,
        admin_service,
        tag_write_service,
        resource_write_service,
    )


def run_gui(argv: list[str] | None = None) -> int:
    """创建 ``QApplication``、显示主窗口并进入事件循环。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(argv) if argv is not None else [])
    window = create_main_window()
    window.show()
    return int(app.exec())


__all__ = [
    "MainWindow",
    "create_main_window",
    "run_gui",
    "WINDOW_TITLE",
    "confirm_close_during_scan",
    "confirm_keep_waiting",
]
