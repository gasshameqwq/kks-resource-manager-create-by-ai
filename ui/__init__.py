"""界面层（Phase 1.4-C 起实现）。

原则（见 docs/ARCHITECTURE.md）：

- UI 不包含业务逻辑，只调用 ``core/`` 并展示结果；
- 数据一律经 ``BrowseService``（列表/详情）与 ``PreviewService``（缩略图）；
  UI 不直接访问 SQLite、不写 SQL、不绕过 Query Layer；
- 耗时操作必须放到后台线程（Phase 1.4-C-3 起）。

依赖方向严格单向：``ui/ → core/``，``core/`` 永不反向依赖 UI。
"""

from ui.main_window import MainWindow, create_main_window, run_gui

__all__ = ["MainWindow", "create_main_window", "run_gui"]
