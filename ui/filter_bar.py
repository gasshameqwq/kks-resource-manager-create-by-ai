"""中栏顶部筛选栏 —— Phase 1.4-C-2。

只负责「把用户输入变成筛选状态」，并发出一个 ``criteria_changed`` 信号；
不查询、不排序、不判断资源类型归属——那些都属于 core（``BrowserScope`` /
``BrowseService``）。

控件：SearchBox / ResourceTypeCombo / MissingMODCheck / NeedsReviewCheck / SortCombo。
搜索输入经过 250–300ms debounce 后才发信号。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core.models import RESOURCE_TYPES

#: 搜索 debounce（毫秒）。
SEARCH_DEBOUNCE_MS = 280

#: 资源类型显示名（以 core 的 RESOURCE_TYPES 为准，未列出的回退为原值）。
_RESOURCE_TYPE_LABELS: dict[str, str] = {
    "character_card": "角色卡",
    "outfit_card": "服装卡",
    "scene_card": "场景卡",
    "mod": "MOD",
    "skin": "皮肤",
    "eyes": "眼睛",
    "hair": "发型",
    "accessory": "配饰",
    "other": "其它",
    "unknown": "未知",
}

#: 排序项：``(order_by, descending, label)``，字段名必须在 ResourceQuery 白名单内。
SORT_OPTIONS: tuple[tuple[str, bool, str], ...] = (
    ("name", False, "名称 ↑"),
    ("name", True, "名称 ↓"),
    ("modified_time", True, "最近修改 ↓"),
    ("modified_time", False, "最近修改 ↑"),
    ("file_size", True, "文件大小 ↓"),
    ("file_size", False, "文件大小 ↑"),
)


class FilterBar(QWidget):
    """搜索 / 类型 / 缺 MOD / 待确认 / 排序 的筛选栏。"""

    criteria_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索名称 / 文件名 / 作者")
        self.search_box.setClearButtonEnabled(True)

        self.type_combo = QComboBox()
        self.type_combo.addItem("全部类型", None)
        for resource_type in RESOURCE_TYPES:
            self.type_combo.addItem(
                _RESOURCE_TYPE_LABELS.get(resource_type, resource_type), resource_type
            )

        self.missing_check = QCheckBox("只看缺 MOD")
        self.needs_review_check = QCheckBox("待确认")

        self.sort_combo = QComboBox()
        for _order_by, _descending, label in SORT_OPTIONS:
            self.sort_combo.addItem(label)

        # 关系反查（C-5）：作者 / 插件 / 缺失 MOD，内部值分别是 author_id / plugin_guid / mod_guid
        self.author_combo = QComboBox()
        self.author_combo.addItem("全部作者", None)
        self.plugin_combo = QComboBox()
        self.plugin_combo.addItem("全部插件", None)
        self.mod_combo = QComboBox()
        self.mod_combo.addItem("全部缺失 MOD", None)
        self.mod_combo.setEditable(True)
        self.mod_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.mod_combo.setMinimumWidth(240)
        completer = QCompleter(self.mod_combo.model(), self.mod_combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.mod_combo.setCompleter(completer)

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.addWidget(QLabel("搜索"))
        row1.addWidget(self.search_box, 1)
        row1.addWidget(self.type_combo)
        row1.addWidget(self.missing_check)
        row1.addWidget(self.needs_review_check)
        row1.addWidget(QLabel("排序"))
        row1.addWidget(self.sort_combo)

        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.addWidget(QLabel("作者"))
        row2.addWidget(self.author_combo)
        row2.addWidget(QLabel("插件"))
        row2.addWidget(self.plugin_combo)
        row2.addWidget(QLabel("MOD"))
        row2.addWidget(self.mod_combo, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addLayout(row1)
        layout.addLayout(row2)

        # 填充下拉项时不要触发查询
        self._populating = False

        # debounce：输入期间每次 keystroke 重启定时器，只有停顿后才查询。
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self.criteria_changed.emit)

        self.search_box.textChanged.connect(self._on_text_changed)
        self.type_combo.currentIndexChanged.connect(self._emit_changed)
        self.missing_check.toggled.connect(self._emit_changed)
        self.needs_review_check.toggled.connect(self._emit_changed)
        self.sort_combo.currentIndexChanged.connect(self._emit_changed)
        self.author_combo.currentIndexChanged.connect(self._emit_changed)
        self.plugin_combo.currentIndexChanged.connect(self._emit_changed)
        self.mod_combo.currentIndexChanged.connect(self._emit_changed)

    # ---- 当前筛选值 ------------------------------------------------------

    def query(self) -> str | None:
        text = self.search_box.text().strip()
        return text or None

    def resource_type(self) -> str | None:
        return self.type_combo.currentData()

    def has_missing_mods(self) -> bool | None:
        return True if self.missing_check.isChecked() else None

    def needs_review(self) -> bool | None:
        return True if self.needs_review_check.isChecked() else None

    def sort_spec(self) -> tuple[str, bool]:
        index = self.sort_combo.currentIndex()
        if not (0 <= index < len(SORT_OPTIONS)):
            index = 0
        order_by, descending, _label = SORT_OPTIONS[index]
        return order_by, descending

    def order_by(self) -> str:
        return self.sort_spec()[0]

    def descending(self) -> bool:
        return self.sort_spec()[1]

    def author_id(self) -> int | None:
        value = self.author_combo.currentData()
        return int(value) if value is not None else None

    def plugin_guid(self) -> str | None:
        value = self.plugin_combo.currentData()
        return str(value) if value is not None else None

    def mod_guid(self) -> str | None:
        value = self.mod_combo.currentData()
        return str(value) if value is not None else None

    # ---- 供测试 / 外部驱动 ----------------------------------------------

    def set_relation_options(
        self, *, authors=(), plugins=(), missing_mods=()
    ) -> None:
        """用只读关系列表填充三个下拉（填充期间不发信号、不触发查询）。"""
        self._populating = True
        try:
            self.author_combo.clear()
            self.author_combo.addItem("全部作者", None)
            for author in authors:
                self.author_combo.addItem(
                    f"{author.name}（{author.resource_count}）", author.id
                )

            self.plugin_combo.clear()
            self.plugin_combo.addItem("全部插件", None)
            for plugin in plugins:
                self.plugin_combo.addItem(
                    f"{plugin.plugin_guid}（{plugin.resource_count}）",
                    plugin.plugin_guid,
                )

            self.mod_combo.clear()
            self.mod_combo.addItem("全部缺失 MOD", None)
            # 缺失 MOD 按「被引用资源数」倒序（ModSummary.used_by_count 由 core 提供）
            for mod in sorted(missing_mods, key=lambda m: (-m.used_by_count, m.guid)):
                self.mod_combo.addItem(f"{mod.guid}（{mod.used_by_count}）", mod.guid)
            self.mod_combo.setEditText("")
        finally:
            self._populating = False

    def set_author(self, author_id: int | None) -> None:
        index = self.author_combo.findData(author_id)
        self.author_combo.setCurrentIndex(index if index >= 0 else 0)

    def set_plugin(self, plugin_guid: str | None) -> None:
        index = self.plugin_combo.findData(plugin_guid)
        self.plugin_combo.setCurrentIndex(index if index >= 0 else 0)

    def set_missing_mod(self, mod_guid: str | None, *, add_if_missing: bool = True) -> None:
        """选中某个 MOD guid。

        下拉默认只列**缺失 MOD**；若传入的是已安装 MOD（来自详情面板的闭环），
        在 ``add_if_missing=True`` 时临时补一个条目，避免「点了却没反应」。
        """
        if mod_guid is None:
            self.mod_combo.setCurrentIndex(0)
            return
        index = self.mod_combo.findData(mod_guid)
        if index < 0 and add_if_missing:
            self.mod_combo.addItem(f"{mod_guid}（已安装/其它）", mod_guid)
            index = self.mod_combo.count() - 1
        if index >= 0:
            self.mod_combo.setCurrentIndex(index)

    def clear_relation_filters(self) -> None:
        """把三个关系筛选都恢复成「全部」。"""
        self._populating = True
        try:
            self.author_combo.setCurrentIndex(0)
            self.plugin_combo.setCurrentIndex(0)
            self.mod_combo.setCurrentIndex(0)
            self.mod_combo.setEditText("")
        finally:
            self._populating = False
        self.criteria_changed.emit()

    def set_query(self, text: str) -> None:
        """设置搜索文本（会走 debounce；测试可随后调用 ``flush_search``）。"""
        self.search_box.setText(text)

    def flush_search(self) -> None:
        """立即触发一次待处理的搜索（跳过等待，供测试与「回车」使用）。"""
        if self._search_timer.isActive():
            self._search_timer.stop()
            self.criteria_changed.emit()

    def is_search_pending(self) -> bool:
        """是否还有未触发的搜索（debounce 进行中）。"""
        return self._search_timer.isActive()

    def set_resource_type(self, resource_type: str | None) -> None:
        index = self.type_combo.findData(resource_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)

    def set_has_missing_mods(self, checked: bool) -> None:
        self.missing_check.setChecked(bool(checked))

    def set_needs_review(self, checked: bool) -> None:
        self.needs_review_check.setChecked(bool(checked))

    def set_sort(self, order_by: str, descending: bool) -> None:
        for index, (field, desc, _label) in enumerate(SORT_OPTIONS):
            if field == order_by and bool(desc) == bool(descending):
                self.sort_combo.setCurrentIndex(index)
                return

    # ---- 内部 -----------------------------------------------------------

    def _on_text_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _emit_changed(self, *_args) -> None:
        if self._populating:
            return
        self.criteria_changed.emit()


__all__ = ["FilterBar", "SORT_OPTIONS", "SEARCH_DEBOUNCE_MS"]
