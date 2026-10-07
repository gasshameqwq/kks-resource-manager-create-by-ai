"""KKS Resource Manager 入口（Phase 0 版本）。

**不实现完整 UI**：入口提供最小可运行的命令行。

    python main.py --init-db                 初始化/升级数据库并打印结构摘要
    python main.py --info                    打印路径与数据库状态
    python main.py                           等价于 --info（数据库不存在时自动初始化）
    python main.py --version                 打印版本号

    python main.py library list              列出已添加的扫描根目录
    python main.py library add <目录> [...]   添加扫描根目录（可一次多个）
    python main.py library remove <id|路径>   删除扫描根目录（需 --yes 确认）
    python main.py library enable <id|路径>   启用
    python main.py library disable <id|路径>  暂停

    python main.py scan [<id|路径>] [--full]   扫描 Library（省略目标则扫描全部启用的库）

    python main.py query resources [--type ...] [--game KKS|KK] [--json]
    python main.py query missing-mods | orphan-mods | usage-categories | ...
                                               只读查询（Phase 1.3-B；薄封装 Query Layer）

    python main.py resource set-display-name <id|路径> <名称>
    python main.py resource set-display-name <id|路径> --clear
    python main.py resource set-notes <id|路径> <备注>
    python main.py resource set-notes <id|路径> --clear
    python main.py resource set-type <id|路径> <类型>
                                               用户数据编辑（Phase 3.1；薄适配层）

    python main.py gui                        启动 PyQt6 图形界面（Phase 1.4-C）

GUI 逻辑全部放在 ``ui/`` 中，本入口只负责创建 ``QApplication`` 并进入事件循环；
核心逻辑始终留在 ``core/`` 中。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import __phase__, __version__  # noqa: E402
from core import app_paths  # noqa: E402
from cli_query import add_query_parser, dispatch_query  # noqa: E402


def _open_store():
    """初始化数据库并返回 ``(connection, LibraryStore)``；调用方负责关闭连接。"""
    from core.database import db as database
    from core.library import LibraryStore

    database.initialize()
    conn = database.connect()
    return conn, LibraryStore(conn)


def cmd_init_db() -> int:
    from core.database import db as database

    info = database.initialize()
    print(f"数据库已就绪：{info['db_path']}")
    print(f"schema 版本：{info['schema_version']}")
    print(f"FTS 搜索表：{'已启用' if info['fts_enabled'] else '未启用（回退 LIKE 搜索）'}")
    print(f"数据表（{len(info['tables'])}）：{', '.join(info['tables'])}")
    return 0


def cmd_info() -> int:
    from core.database import db as database

    print("正在检查数据库……")
    info = database.initialize()
    print(f"应用版本：{__version__}  |  {__phase__}")
    print(f"项目根目录：{app_paths.app_root()}")
    print(f"数据目录：{app_paths.data_dir()}")
    print(f"数据库：{info['db_path']}（schema v{info['schema_version']}）")
    print(f"缩略图缓存：{app_paths.thumbnail_dir()}")
    print(f"日志目录：{app_paths.logs_dir()}")
    print(f"数据表（{len(info['tables'])}）：{', '.join(info['tables'])}")

    conn = database.connect()
    try:
        libraries = conn.execute(
            "SELECT id, name FROM libraries ORDER BY name COLLATE NOCASE, id"
        ).fetchall()
    finally:
        conn.close()
    if libraries:
        listed = "、".join(f"{r['id']}:{r['name']}" for r in libraries)
        print(f"已添加 Library（{len(libraries)}）：{listed}")
    else:
        print("已添加 Library（0）：用 `python main.py library add <目录>` 添加")
    return 0


# ---------------------------------------------------------------------------
# Phase 1.1 —— Library 管理
# ---------------------------------------------------------------------------


def cmd_library_list() -> int:
    conn, store = _open_store()
    try:
        libraries = store.list_all(include_disabled=True)
        if not libraries:
            print("尚未添加任何 Library。")
            print("用法：python main.py library add <目录>")
            return 0
        print(f"已添加 Library（{len(libraries)}）：")
        for lib in libraries:
            stats = store.stats(lib.id)
            state = "启用" if lib.enabled else "暂停"
            print(f"  [{lib.id}] {lib.name}  （{state}）")
            print(f"        根目录：{lib.root_path}")
            print(
                f"        资源：{stats.resources}"
                f"（待确认 {stats.needs_review}，缺失 {stats.missing}）"
                f"    上次扫描：{lib.last_scan_at or '从未'}"
            )
            if lib.notes:
                print(f"        备注：{lib.notes}")
        return 0
    finally:
        conn.close()


def cmd_library_add(
    paths: list[str],
    name: str | None = None,
    notes: str = "",
    allow_missing: bool = False,
) -> int:
    from core.library import LibraryError

    if name and len(paths) > 1:
        print("--name 只能配合单个目录使用。", file=sys.stderr)
        return 2

    conn, store = _open_store()
    try:
        try:
            if len(paths) == 1:
                added = [
                    store.add(
                        paths[0],
                        name=name,
                        notes=notes,
                        allow_missing=allow_missing,
                    )
                ]
            else:
                added = store.add_many(
                    paths, notes=notes, allow_missing=allow_missing
                )
        except LibraryError as exc:
            print(f"添加失败：{exc}", file=sys.stderr)
            return 1

        for lib in added:
            state = "启用" if lib.enabled else "暂停"
            print(f"已添加 Library [{lib.id}]（{state}）：{lib.name}")
            print(f"  根目录：{lib.root_path}")
        return 0
    finally:
        conn.close()


def cmd_library_remove(target: str, assume_yes: bool = False) -> int:
    from core.library import LibraryError

    conn, store = _open_store()
    try:
        try:
            lib = store.resolve(target)
        except LibraryError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if not assume_yes:
            report = store.preview_removal(lib.id)
            print(f"将要删除 Library [{lib.id}]：{lib.name}")
            print(f"  根目录：{lib.root_path}")
            print(
                f"  影响：{report.resources_orphaned} 条资源解除关联（资源与文件都保留），"
                f"{report.scan_records_deleted} 条扫描记录被删除"
            )
            print("  目录和文件不会被删除。确认请加 --yes 重新执行。")
            return 1

        report = store.remove(lib.id)
        print(f"已删除 Library [{report.library.id}]：{report.library.name}")
        print(f"  已解除关联资源：{report.resources_orphaned}（文件未改动）")
        print(f"  已删除扫描记录：{report.scan_records_deleted}")
        return 0
    finally:
        conn.close()


def cmd_library_set_enabled(target: str, enabled: bool) -> int:
    from core.library import LibraryError

    conn, store = _open_store()
    try:
        try:
            lib = store.resolve(target)
            lib = store.set_enabled(lib.id, enabled)
        except LibraryError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"已{'启用' if enabled else '暂停'} Library [{lib.id}]：{lib.name}")
        return 0
    finally:
        conn.close()


def cmd_scan(target: str | None = None, full: bool = False) -> int:
    from core.library import LibraryError, LibraryStore
    from core.scanner import LibraryScanner

    conn, library_store = _open_store()
    try:
        try:
            libraries = (
                [library_store.resolve(target)]
                if target
                else library_store.list_all(include_disabled=False)
            )
        except LibraryError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if not libraries:
            print("没有可扫描的 Library（可用 `python main.py library add <目录>` 添加）。")
            return 0

        scanner = LibraryScanner(conn)
        exit_code = 0
        for lib in libraries:
            result = scanner.scan(lib.id, mode="full" if full else "incremental")
            stats = result.stats
            mode = "全量" if full else "增量"
            if result.status == "skipped":
                print(f"[{lib.id}] {lib.name}：{result.skip_reason}")
                continue
            if result.status != "completed":
                exit_code = 1
                print(f"[{lib.id}] {lib.name}：扫描失败（{result.skip_reason}）")
                continue
            print(f"[{lib.id}] {lib.name}（{mode}）  {lib.root_path}")
            print(
                f"      发现 {stats.discovered} · 解析 {stats.parsed}"
                f" · 新增 {stats.inserted} · 更新 {stats.updated}"
                f" · 跳过 {stats.skipped} · 失败 {stats.failed}"
                f" · 缺失 {stats.missing}      耗时 {result.duration_ms} ms"
            )
            for issue in result.issues[:5]:
                print(f"      ! [{issue.stage}] {issue.path}: {issue.message}")
            if len(result.issues) > 5:
                print(f"      ! ...还有 {len(result.issues) - 5} 条问题")
            if stats.failed:
                exit_code = 1
        return exit_code
    finally:
        conn.close()


def _dispatch_library(args) -> int:
    command = args.library_command
    if command == "list":
        return cmd_library_list()
    if command == "add":
        return cmd_library_add(args.paths, args.name, args.notes, args.allow_missing)
    if command == "remove":
        return cmd_library_remove(args.target, assume_yes=args.yes)
    if command in ("enable", "disable"):
        return cmd_library_set_enabled(args.target, command == "enable")
    return 2  # pragma: no cover - argparse 已保证不会走到这里


# ---------------------------------------------------------------------------
# Phase 3.1 —— 用户数据编辑（CLI 薄适配层）
# ---------------------------------------------------------------------------
#
# 严格分层（Contract §5.3）：
#
#     CLI → ResourceQuery.resolve()（只读解析目标） → ResourceWriteService → DB
#
# 本层**不写 SQL**、不 import sqlite3、不调用 ResourceStore，也不复制写服务语义；
# 值的归一化 / 校验 / 事务 / 错误语义全部以 ResourceWriteService 为准。


def _resource_write_context():
    """初始化数据库并返回 ``(conn, ResourceQuery, ResourceWriteService)``。"""
    from core.app import ResourceWriteService
    from core.database import db as database
    from core.query import ResourceQuery

    database.initialize()
    conn = database.connect()
    return conn, ResourceQuery(conn), ResourceWriteService(conn)


def _resolve_resource_id(query, target: str) -> int | None:
    """用只读的 ``ResourceQuery.resolve()`` 解析目标；找不到返回 ``None``。"""
    summary = query.resolve(target)
    return int(summary.id) if summary is not None else None


def _report_write_error(exc: Exception) -> int:
    """把写服务异常转成简洁的 CLI 错误输出（不吞异常、不打印 traceback）。"""
    from core.app import InvalidResourceValue, ResourceNotFound

    if isinstance(exc, ResourceNotFound):
        print(f"找不到资源：{exc.resource_id}", file=sys.stderr)
    elif isinstance(exc, InvalidResourceValue):
        print(f"非法取值（{exc.field}）：{exc.value!r}", file=sys.stderr)
    else:
        print(f"写入失败：{exc}", file=sys.stderr)
    return 1


def _run_optional_value_command(
    target: str,
    value: str | None,
    clear: bool,
    *,
    method_name: str,
    label: str,
) -> int:
    """``set-display-name`` / ``set-notes`` 共用的薄流程（value 与 --clear 互斥）。"""
    from core.app import ResourceWriteError

    if clear and value is not None:
        print(f"参数错误：--clear 不能与 {label} 值同时使用。", file=sys.stderr)
        return 2
    if not clear and value is None:
        print(f"参数错误：需要提供 {label} 值，或使用 --clear。", file=sys.stderr)
        return 2

    conn, query, service = _resource_write_context()
    try:
        resource_id = _resolve_resource_id(query, target)
        if resource_id is None:
            print(f"找不到资源：{target}", file=sys.stderr)
            return 1
        try:
            getattr(service, method_name)(resource_id, None if clear else value)
        except ResourceWriteError as exc:
            return _report_write_error(exc)
        if clear:
            print(f"已清除资源 #{resource_id} 的{label}（写为 NULL）")
        else:
            print(f"已设置资源 #{resource_id} 的{label}")
        return 0
    finally:
        conn.close()


def cmd_resource_set_display_name(target: str, value: str | None, clear: bool) -> int:
    """设置 / 清除用户展示名覆盖（``display_name``）。"""
    return _run_optional_value_command(
        target, value, clear, method_name="set_display_name", label="展示名覆盖"
    )


def cmd_resource_set_notes(target: str, value: str | None, clear: bool) -> int:
    """设置 / 清除用户备注（``notes``）。"""
    return _run_optional_value_command(
        target, value, clear, method_name="set_notes", label="备注"
    )


def cmd_resource_set_type(target: str, value: str) -> int:
    """设置用户类型修正（``resource_type`` + ``type_source='user'``）。"""
    from core.app import ResourceWriteError

    conn, query, service = _resource_write_context()
    try:
        resource_id = _resolve_resource_id(query, target)
        if resource_id is None:
            print(f"找不到资源：{target}", file=sys.stderr)
            return 1
        try:
            service.set_resource_type(resource_id, value)
        except ResourceWriteError as exc:
            return _report_write_error(exc)
        print(f"已设置资源 #{resource_id} 的用户类型：{value}（type_source = 'user'）")
        return 0
    finally:
        conn.close()


def _dispatch_resource(args) -> int:
    command = args.resource_command
    if command == "set-display-name":
        return cmd_resource_set_display_name(args.target, args.value, args.clear)
    if command == "set-notes":
        return cmd_resource_set_notes(args.target, args.value, args.clear)
    if command == "set-type":
        return cmd_resource_set_type(args.target, args.value)
    return 2  # pragma: no cover - argparse 已保证不会走到这里


def cmd_gui() -> int:
    """启动 PyQt6 GUI（入口只负责启动；界面逻辑在 ``ui/``）。"""
    from ui.main_window import run_gui

    return run_gui()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kks-resource-manager",
        description="KKS Resource Manager（Phase 1.2：Library 扫描 + 解析入库）",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--init-db", action="store_true", help="初始化或升级 SQLite 数据库")
    group.add_argument("--info", action="store_true", help="打印路径与数据库状态")
    group.add_argument("--version", action="store_true", help="打印版本号")

    sub = parser.add_subparsers(dest="command")
    library = sub.add_parser("library", help="管理扫描根目录（Phase 1.1）")
    library_sub = library.add_subparsers(dest="library_command", required=True)

    library_sub.add_parser("list", help="列出已添加的扫描根目录")

    add = library_sub.add_parser("add", help="添加扫描根目录（目录不会被修改）")
    add.add_argument("paths", nargs="+", help="一个或多个根目录；一次多个时整批原子写入")
    add.add_argument("--name", default=None, help="显示名（仅单个目录时可用）")
    add.add_argument("--notes", default="", help="备注")
    add.add_argument(
        "--allow-missing",
        action="store_true",
        help="不检查目录是否存在（用于暂时离线的盘符）",
    )

    remove = library_sub.add_parser("remove", help="删除扫描根目录（不动文件）")
    remove.add_argument("target", help="Library 的 id 或根目录路径")
    remove.add_argument("--yes", action="store_true", help="确认执行（不加则只预览）")

    for name, action_help in (("enable", "启用"), ("disable", "暂停")):
        item = library_sub.add_parser(name, help=f"{action_help}某个扫描根目录")
        item.add_argument("target", help="Library 的 id 或根目录路径")

    scan = sub.add_parser("scan", help="扫描 Library：解析并入库（只读，不动文件）")
    scan.add_argument(
        "target", nargs="?", default=None, help="Library 的 id 或根目录路径；省略则扫描全部启用的库"
    )
    scan.add_argument(
        "--full", action="store_true", help="忽略增量捷径，全部重新解析"
    )

    # Phase 1.3-B：只读查询（Query Layer 的薄 CLI 适配层）
    add_query_parser(sub)

    # Phase 3.1：用户数据编辑（薄适配层 → ResourceWriteService）
    resource = sub.add_parser(
        "resource", help="编辑资源上的用户数据（展示名 / 备注 / 用户类型）"
    )
    resource_sub = resource.add_subparsers(dest="resource_command", required=True)

    display = resource_sub.add_parser(
        "set-display-name", help="设置或清除用户展示名覆盖（display_name）"
    )
    display.add_argument("target", help="资源的 id / 路径 / path_key / relative_path")
    display.add_argument(
        "value", nargs="?", default=None, help="展示名；用 --clear 清除（写 NULL）"
    )
    display.add_argument("--clear", action="store_true", help="清除展示名覆盖")

    notes = resource_sub.add_parser("set-notes", help="设置或清除用户备注（notes）")
    notes.add_argument("target", help="资源的 id / 路径 / path_key / relative_path")
    notes.add_argument(
        "value", nargs="?", default=None, help="备注；用 --clear 清除（写 NULL）"
    )
    notes.add_argument("--clear", action="store_true", help="清除备注")

    type_cmd = resource_sub.add_parser(
        "set-type", help="设置用户类型修正（type_source='user'）"
    )
    type_cmd.add_argument("target", help="资源的 id / 路径 / path_key / relative_path")
    type_cmd.add_argument("value", help="资源类型（见 core.models.RESOURCE_TYPES）")

    sub.add_parser("gui", help="启动图形界面（Phase 1.4-C）")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"{__version__} ({__phase__})")
        return 0
    if args.init_db:
        return cmd_init_db()
    if getattr(args, "command", None) == "library":
        return _dispatch_library(args)
    if getattr(args, "command", None) == "scan":
        return cmd_scan(args.target, full=args.full)
    if getattr(args, "command", None) == "query":
        return dispatch_query(args)
    if getattr(args, "command", None) == "resource":
        return _dispatch_resource(args)
    if getattr(args, "command", None) == "gui":
        return cmd_gui()
    return cmd_info()


if __name__ == "__main__":
    raise SystemExit(main())
