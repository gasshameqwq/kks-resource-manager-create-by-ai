"""Library 管理对话框 —— Phase 1.5-A。

职责边界
--------
- **只收集用户输入 / 展示确认**：不访问数据库、不写 SQL、不判断业务规则。
- 实际写操作由 ``core.app.LibraryAdminService`` 完成（沿用 ``LibraryStore`` 语义）。

包含两部分：

- :class:`AddLibraryDialog` —— 选择目录 + 可选 ``name`` / ``notes`` / ``enabled`` /
  ``allow_missing``（后两项与 CLI 的 ``--allow-missing`` 语义一致）。
- :func:`confirm_remove` + :func:`build_removal_text` —— 移除前的二次确认，
  文案必须逐字表达「只删库记录、资源保留、不动文件、删除扫描历史」这一真实语义。
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


ADD_TITLE = "添加资源库"
REMOVE_TITLE = "移除资源库"


def build_removal_text(report) -> str:
    """由 ``LibraryRemovalReport`` 生成移除确认文案（逐字表达真实语义）。"""
    library = report.library
    return (
        f"将移除资源库「{library.name}」\n"
        "  · 只删除数据库中的库记录\n"
        "  · 已入库的资源会保留（但不再属于任何库）\n"
        "  · 不会删除或移动你的任何文件\n"
        "  · 该库的扫描历史记录将被删除\n"
        "\n"
        f"影响预览：{report.resources_orphaned} 条资源将解除关联，"
        f"{report.scan_records_deleted} 条扫描记录将被删除。"
    )


def confirm_remove(parent, report) -> bool:
    """弹出移除确认框；用户点「移除」返回 ``True``，否则 ``False``。

    默认按钮是「取消」，避免误触；这是删除前唯一的确认关口。
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(REMOVE_TITLE)
    box.setText(build_removal_text(report))
    remove_button = box.addButton("移除", QMessageBox.ButtonRole.DestructiveRole)
    cancel_button = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel_button)
    box.exec()
    return box.clickedButton() is remove_button


class AddLibraryDialog(QDialog):
    """添加资源库对话框：选目录 + 可选名称 / 备注 / 启用 / 允许目录缺失。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(ADD_TITLE)
        self.setMinimumWidth(460)

        self._path = QLineEdit()
        self._path.setPlaceholderText("选择一个目录（只会被读取，不会被修改）")
        self._browse = QPushButton("浏览…")
        self._browse.clicked.connect(self._choose_directory)

        path_row = QWidget()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self._path, 1)
        path_layout.addWidget(self._browse)

        self._name = QLineEdit()
        self._name.setPlaceholderText("留空则使用文件夹名")
        self._notes = QLineEdit()
        self._notes.setPlaceholderText("可选")
        self._enabled = QCheckBox("启用（参与扫描）")
        self._enabled.setChecked(True)
        self._allow_missing = QCheckBox("允许目录暂时不存在（如临时离线的盘符）")

        form = QFormLayout()
        form.addRow(QLabel("目录"), path_row)
        form.addRow(QLabel("名称"), self._name)
        form.addRow(QLabel("备注"), self._notes)
        form.addRow(QLabel(""), self._enabled)
        form.addRow(QLabel(""), self._allow_missing)

        hint = QLabel("添加只写入数据库，不会扫描、移动或修改你的任何文件。")
        hint.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("添加")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    # ---- 输入 -----------------------------------------------------------

    def values(self) -> dict:
        """返回可直接喂给 ``LibraryAdminService.add_library(**values)`` 的字典。"""
        return {
            "root_path": self._path.text().strip(),
            "name": self._name.text().strip() or None,
            "notes": self._notes.text().strip(),
            "enabled": self._enabled.isChecked(),
            "allow_missing": self._allow_missing.isChecked(),
        }

    def set_root_path(self, path: str) -> None:
        self._path.setText(str(path))

    # ---- 内部 -----------------------------------------------------------

    def _choose_directory(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "选择资源库目录")
        if chosen:
            self._path.setText(chosen)

    def _on_accept(self) -> None:
        if not self._path.text().strip():
            QMessageBox.warning(self, ADD_TITLE, "请选择或填写一个目录。")
            return
        self.accept()


__all__ = [
    "AddLibraryDialog",
    "build_removal_text",
    "confirm_remove",
    "ADD_TITLE",
    "REMOVE_TITLE",
]
