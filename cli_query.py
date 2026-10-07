"""Phase 1.3-B：``python main.py query ...`` 子命令（Query Layer 的薄 CLI 适配层）。

分层（严格遵守）::

    CLI arguments  ->  Query Layer (core.query)  ->  DTO  ->  CLI formatter

本模块**只做参数解析与展示**，绝不做查询逻辑：

- 不拼 SQL、不知道任何表结构；
- 不判断 missing / orphan MOD；
- 不判断 property category（未分类的由 Query Layer 给 ``unknown``）；
- 不解析 ``metadata_json``；
- 不做 author normalization（交给 ``AuthorQuery``）。
- 不计算哈希、不自己分组重复（交给 ``ResourceQuery.duplicates()``）；
  ``sha256`` 只是既有列的只读派生值。

默认人类可读输出；``--json`` 输出**来自 DTO 的稳定字段**，不序列化 SQLite cursor。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from core.query import AuthorQuery, ModQuery, PluginQuery, ResourceQuery, UsageQuery


# ---------------------------------------------------------------------------
# 基础设施
# ---------------------------------------------------------------------------


def _open_conn():
    from core.database import db as database

    database.initialize()
    return database.connect()


def _dump_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False))


def _emit(args, payload: Any, text: str | None) -> None:
    if getattr(args, "json", False):
        _dump_json(payload)
    else:
        print(text if text is not None else "(no results)")


def _not_found(kind: str, target: Any) -> int:
    print(f"{kind} not found: {target}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# DTO -> 稳定 dict（JSON 用）
# ---------------------------------------------------------------------------


def _resource_obj(r) -> dict:
    return {
        "id": r.id,
        "resource_type": r.resource_type,
        "name": r.name,
        "display_name": r.display_name,
        "title": r.title,
        "game": r.game,
        "card_marker": r.card_marker,
        "file_path": r.file_path,
        "relative_path": r.relative_path,
        "extension": r.extension,
        "file_size": r.file_size,
        "modified_time": r.modified_time,
        "library_id": r.library_id,
        "scan_status": r.scan_status,
        "parse_status": r.parse_status,
        "needs_review": r.needs_review,
        "mod_count": r.mod_count,
        "usage_count": r.usage_count,
        "plugin_count": r.plugin_count,
        "author_count": r.author_count,
        # Phase 2.3-A 起 ResourceSummary 携带已有的 resources.sha256（只读派生值）；
        # 仅表示「字节完全相同」，NULL 时序列化为 null。
        "sha256": r.sha256,
    }


def _duplicate_group_obj(group) -> dict:
    """一个 byte-duplicate 组 → 稳定 JSON（``sha256`` + 成员资源对象）。"""
    return {
        "sha256": group.sha256,
        "member_count": group.member_count,
        "resources": [_resource_obj(r) for r in group.resources],
    }


def _mod_obj(m) -> dict:
    return {
        "guid": m.guid,
        "installed": m.installed,
        "id": m.id,
        "name": m.name,
        "author": m.author,
        "version": m.version,
        "website": m.website,
        "file_path": m.file_path,
        "resource_id": m.resource_id,
        "library_id": m.library_id,
        "used_by_count": m.used_by_count,
        "usage_count": m.usage_count,
    }


def _usage_obj(u) -> dict:
    return {
        "resource_id": u.resource_id,
        "mod_guid": u.mod_guid,
        "property": u.property,
        "category": u.category,
        "slot": u.slot,
        "local_slot": u.local_slot,
        "category_no": u.category_no,
    }


def _resource_mod_obj(m) -> dict:
    return {
        "mod_guid": m.mod_guid,
        "mod_id": m.mod_id,
        "installed": m.installed,
        "ref_count": m.ref_count,
        "relation": m.relation,
        "categories": list(m.categories),
    }


def _author_obj(a) -> dict:
    return {"id": a.id, "name": a.name, "resource_count": a.resource_count}


def _resource_author_obj(a) -> dict:
    return {
        "author_id": a.author_id,
        "name": a.name,
        "ordinal": a.ordinal,
        "raw_name": a.raw_name,
    }


def _plugin_obj(p) -> dict:
    return {"plugin_guid": p.plugin_guid, "resource_count": p.resource_count}


def _category_stats_obj(s) -> dict:
    return {
        "category": s.category,
        "usage_count": s.usage_count,
        "resource_count": s.resource_count,
        "mod_count": s.mod_count,
    }


def _category_count_obj(c) -> dict:
    return {"category": c.category, "count": c.count}


# ---------------------------------------------------------------------------
# 人类可读格式化
# ---------------------------------------------------------------------------


def _game_label(r) -> str:
    return r.game or "-"


def _resource_line(r) -> str:
    return (
        f"#{r.id:>3}  {r.resource_type:<15} {_game_label(r):<4} {r.title}"
        f"    MOD {r.mod_count} · 插件 {r.plugin_count} · 作者 {r.author_count}"
    )


def _resource_detail_lines(detail) -> list[str]:
    r = detail.resource
    lines = [
        f"Resource #{r.id}",
        f"  Name: {r.name or '-'}",
        f"  Display: {r.display_name or '-'}",
        f"  Type: {r.resource_type}",
        f"  Format: {_game_label(r)}"
        + (f" ({r.card_marker})" if r.card_marker else ""),
        f"  Path: {r.file_path}",
        f"  Relative: {r.relative_path or '-'}",
        f"  Library: {r.library_id if r.library_id is not None else '-'}",
        f"  Scan/Parse: {r.scan_status} / {r.parse_status}",
        f"  Size: {r.file_size if r.file_size is not None else '-'}",
        f"  MODs: {r.mod_count}    Usages: {r.usage_count}"
        f"    Plugins: {r.plugin_count}    Authors: {r.author_count}",
    ]
    for mod in detail.mods:
        state = "installed" if mod.installed else "missing"
        cats = ",".join(mod.categories) if mod.categories else "-"
        lines.append(
            f"    - {mod.mod_guid}  [{state}, ref={mod.ref_count}, {cats}]"
        )
    if detail.plugins:
        lines.append("  Plugins: " + ", ".join(detail.plugins))
    else:
        lines.append("  Plugins: (none)")
    if detail.authors:
        lines.append(
            "  Authors: "
            + ", ".join(f"{a.name}(ord={a.ordinal})" for a in detail.authors)
        )
    else:
        raw = detail.metadata.get("authors_raw")
        lines.append(f"  Authors: (none)    authors_raw={raw if raw else []}")
    return lines


def _mod_line(m) -> str:
    state = "installed" if m.installed else "missing"
    extra = m.name or ""
    return (
        f"{m.guid}  [{state}]  used_by={m.used_by_count}  usages={m.usage_count}"
        f"  {extra}".rstrip()
    )


def _usage_line(u) -> str:
    return (
        f"#{u.resource_id:>3}  {u.mod_guid:<40} {u.category:<9} {u.property}"
        f"  slot={u.slot} local={u.local_slot} cat={u.category_no}"
    )


def _duplicate_group_lines(group) -> list[str]:
    """一个 byte-duplicate 组的人类可读块（成员显示 id / 类型 / 标题 / 路径）。"""
    lines = [
        f"sha256 {group.sha256}    members={group.member_count}"
        "    （以下资源文件字节完全相同）"
    ]
    for resource in group.resources:
        lines.append(f"  {_resource_line(resource)}")
        lines.append(f"      {resource.file_path}")
    return lines


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------


def _resource_list_scope(args) -> dict:
    scope = {}
    for key, value in (
        ("resource_type", args.resource_type),
        ("game", args.game),
        ("library_id", args.library),
        ("scan_status", args.status),
        ("needs_review", args.needs_review),
        ("mod_guid", args.mod_guid),
        ("plugin_guid", args.plugin_guid),
        ("property_category", args.category),
        ("has_mods", args.has_mods),
    ):
        if value is not None:
            scope[key] = value
    return scope


def cmd_resources(conn, args) -> int:
    rows = ResourceQuery(conn).list(
        resource_type=args.resource_type,
        game=args.game,
        library_id=args.library,
        scan_status=args.status,
        needs_review=args.needs_review,
        mod_guid=args.mod_guid,
        plugin_guid=args.plugin_guid,
        property_category=args.category,
        has_mods=args.has_mods,
        order_by=args.order,
        descending=args.desc,
        limit=args.limit,
        offset=args.offset,
    )
    payload = {
        "count": len(rows),
        "scope": _resource_list_scope(args),
        "resources": [_resource_obj(r) for r in rows],
    }
    lines = [f"Resources: {len(rows)}"]
    lines += [_resource_line(r) for r in rows]
    _emit(args, payload, "\n".join(lines) if rows else None)
    return 0


def cmd_resource(conn, args) -> int:
    rq = ResourceQuery(conn)
    summary = rq.resolve(args.target)
    if summary is None:
        return _not_found("Resource", args.target)
    detail = rq.get(summary.id)
    payload = {
        "resource": _resource_obj(detail.resource),
        "usages": [_usage_obj(u) for u in detail.usages],
        "mods": [_resource_mod_obj(m) for m in detail.mods],
        "plugins": list(detail.plugins),
        "authors": [_resource_author_obj(a) for a in detail.authors],
        "metadata": detail.metadata,
    }
    _emit(args, payload, "\n".join(_resource_detail_lines(detail)))
    return 0


def cmd_resource_mods(conn, args) -> int:
    rq = ResourceQuery(conn)
    summary = rq.resolve(args.target)
    if summary is None:
        return _not_found("Resource", args.target)
    mods = rq.mods(summary.id)
    payload = {
        "resource": _resource_obj(summary),
        "count": len(mods),
        "mods": [_resource_mod_obj(m) for m in mods],
    }
    lines = [f"Resource #{summary.id} ({summary.title}) MODs: {len(mods)}"]
    for m in mods:
        state = "installed" if m.installed else "missing"
        cats = ",".join(m.categories) if m.categories else "-"
        lines.append(f"  {m.mod_guid}  [{state}, ref={m.ref_count}, {cats}]")
    _emit(args, payload, "\n".join(lines) if mods else None)
    return 0


def cmd_resource_plugins(conn, args) -> int:
    rq = ResourceQuery(conn)
    summary = rq.resolve(args.target)
    if summary is None:
        return _not_found("Resource", args.target)
    plugins = rq.plugins(summary.id)
    payload = {
        "resource": _resource_obj(summary),
        "count": len(plugins),
        "plugins": plugins,
    }
    lines = [f"Resource #{summary.id} ({summary.title}) Plugins: {len(plugins)}"]
    lines += [f"  {p}" for p in plugins]
    _emit(args, payload, "\n".join(lines) if plugins else None)
    return 0


def cmd_resource_authors(conn, args) -> int:
    rq = ResourceQuery(conn)
    summary = rq.resolve(args.target)
    if summary is None:
        return _not_found("Resource", args.target)
    authors = rq.authors(summary.id)
    raw = rq.authors_raw(summary.id)
    payload = {
        "resource": _resource_obj(summary),
        "count": len(authors),
        "authors": [_resource_author_obj(a) for a in authors],
        "authors_raw": raw,
    }
    lines = [f"Resource #{summary.id} ({summary.title}) Authors: {len(authors)}"]
    for a in authors:
        lines.append(f"  {a.name}  (ordinal={a.ordinal}, raw={a.raw_name!r})")
    lines.append(f"  authors_raw: {raw}")
    _emit(args, payload, "\n".join(lines))
    return 0


def cmd_mods(conn, args) -> int:
    mods = ModQuery(conn).installed()
    payload = {"count": len(mods), "mods": [_mod_obj(m) for m in mods]}
    lines = [f"Installed MODs: {len(mods)}"]
    lines += [f"  {_mod_line(m)}" for m in mods]
    _emit(args, payload, "\n".join(lines) if mods else None)
    return 0


def cmd_mod(conn, args) -> int:
    detail = ModQuery(conn).detail(args.guid)
    if detail is None:
        return _not_found("MOD", args.guid)
    payload = {
        "mod": _mod_obj(detail.mod),
        "category_counts": [_category_count_obj(c) for c in detail.category_counts],
    }
    m = detail.mod
    lines = [
        f"MOD: {m.guid}",
        f"  Installed: {'yes' if m.installed else 'no'}",
        f"  Name: {m.name or '-'}",
        f"  Author: {m.author or '-'}",
        f"  Version: {m.version or '-'}",
        f"  Website: {m.website or '-'}",
        f"  Resources: {m.used_by_count}",
        f"  Usages: {m.usage_count}",
        "  By category:",
    ]
    for c in detail.category_counts:
        if c.count:
            lines.append(f"    {c.category:<9} {c.count}")
    _emit(args, payload, "\n".join(lines))
    return 0


def cmd_mod_resources(conn, args) -> int:
    mq = ModQuery(conn)
    if mq.get(args.guid) is None:
        return _not_found("MOD", args.guid)
    rows = mq.resources(args.guid)
    payload = {"guid": args.guid, "count": len(rows), "resources": [_resource_obj(r) for r in rows]}
    lines = [f"MOD {args.guid} is used by {len(rows)} resource(s):"]
    lines += [_resource_line(r) for r in rows]
    _emit(args, payload, "\n".join(lines) if rows else None)
    return 0


def cmd_mod_usages(conn, args) -> int:
    mq = ModQuery(conn)
    if mq.get(args.guid) is None:
        return _not_found("MOD", args.guid)
    rows = mq.usages(args.guid, category=args.category)
    payload = {
        "guid": args.guid,
        "category": args.category,
        "count": len(rows),
        "usages": [_usage_obj(u) for u in rows],
    }
    lines = [f"MOD {args.guid} usages: {len(rows)}"]
    lines += [f"  {_usage_line(u)}" for u in rows]
    _emit(args, payload, "\n".join(lines) if rows else None)
    return 0


def cmd_authors(conn, args) -> int:
    authors = AuthorQuery(conn).list()
    payload = {"count": len(authors), "authors": [_author_obj(a) for a in authors]}
    lines = [f"Authors: {len(authors)}"]
    lines += [f"  [{a.id}] {a.name}  resources={a.resource_count}" for a in authors]
    _emit(args, payload, "\n".join(lines) if authors else None)
    return 0


def cmd_author(conn, args) -> int:
    author = AuthorQuery(conn).resolve(args.target)
    if author is None:
        return _not_found("Author", args.target)
    payload = {"author": _author_obj(author)}
    lines = [
        f"Author #{author.id}: {author.name}",
        f"  Resources: {author.resource_count}",
    ]
    _emit(args, payload, "\n".join(lines))
    return 0


def cmd_author_resources(conn, args) -> int:
    aq = AuthorQuery(conn)
    author = aq.resolve(args.target)
    if author is None:
        return _not_found("Author", args.target)
    rows = aq.resources(author.id)
    payload = {
        "author": _author_obj(author),
        "count": len(rows),
        "resources": [_resource_obj(r) for r in rows],
    }
    lines = [f"Author {author.name} -> {len(rows)} resource(s):"]
    lines += [_resource_line(r) for r in rows]
    _emit(args, payload, "\n".join(lines) if rows else None)
    return 0


def cmd_plugins(conn, args) -> int:
    plugins = PluginQuery(conn).list()
    payload = {"count": len(plugins), "plugins": [_plugin_obj(p) for p in plugins]}
    lines = [f"Plugins: {len(plugins)}"]
    lines += [f"  {p.plugin_guid}  resources={p.resource_count}" for p in plugins]
    _emit(args, payload, "\n".join(lines) if plugins else None)
    return 0


def cmd_plugin(conn, args) -> int:
    plugin = PluginQuery(conn).get(args.guid)
    if plugin is None:
        return _not_found("Plugin", args.guid)
    payload = {"plugin": _plugin_obj(plugin)}
    lines = [
        f"Plugin: {plugin.plugin_guid}",
        f"  Resources: {plugin.resource_count}",
    ]
    _emit(args, payload, "\n".join(lines))
    return 0


def cmd_plugin_resources(conn, args) -> int:
    pq = PluginQuery(conn)
    if pq.get(args.guid) is None:
        return _not_found("Plugin", args.guid)
    rows = pq.resources(args.guid)
    payload = {
        "guid": args.guid,
        "count": len(rows),
        "resources": [_resource_obj(r) for r in rows],
    }
    lines = [f"Plugin {args.guid} is used by {len(rows)} resource(s):"]
    lines += [_resource_line(r) for r in rows]
    _emit(args, payload, "\n".join(lines) if rows else None)
    return 0


def cmd_missing_mods(conn, args) -> int:
    mq = ModQuery(conn)
    rows = mq.missing()
    payload = {"count": len(rows), "mods": [_mod_obj(m) for m in rows]}
    lines = [f"Missing MODs: {len(rows)}"]
    for m in rows:
        used_by = [r.id for r in mq.resources(m.guid)]
        used = ", ".join(f"Resource #{rid}" for rid in used_by) or "-"
        lines.append("")
        lines.append(m.guid)
        lines.append(f"  used by: {used}")
    _emit(args, payload, ("\n".join(lines) if rows else None))
    return 0


def cmd_orphan_mods(conn, args) -> int:
    rows = ModQuery(conn).orphan()
    payload = {"count": len(rows), "mods": [_mod_obj(m) for m in rows]}
    lines = [f"Orphan MODs: {len(rows)}"]
    lines += [f"  {_mod_line(m)}" for m in rows]
    _emit(args, payload, "\n".join(lines) if rows else None)
    return 0


def cmd_duplicates(conn, args) -> int:
    """``query duplicates``：按 ``sha256`` 分组的 byte-duplicate 资源组。

    数据全部来自 ``ResourceQuery.duplicates()``（只读派生查询）；
    CLI 不拼 SQL、不重新分组、不计算哈希。

    语义边界（Phase 2.0-C §5.4 / §8 / §13.7）：``sha256`` 相等**只**表示
    文件**字节完全相同**（byte-identical），**不**表示同角色 / 同 MOD /
    同逻辑资源；本命令不提供 canonical / primary / status / dismiss 等概念。
    """
    groups = ResourceQuery(conn).duplicates()
    payload = {
        "count": len(groups),
        "groups": [_duplicate_group_obj(g) for g in groups],
    }
    lines = [f"Byte-duplicate groups: {len(groups)}"]
    for group in groups:
        lines.append("")
        lines.extend(_duplicate_group_lines(group))
    _emit(args, payload, "\n".join(lines) if groups else None)
    return 0


def cmd_usages(conn, args) -> int:
    resource_id = None
    if args.resource is not None:
        summary = ResourceQuery(conn).resolve(args.resource)
        if summary is None:
            return _not_found("Resource", args.resource)
        resource_id = summary.id
    rows = UsageQuery(conn).all(
        category=args.category,
        resource_id=resource_id,
        mod_guid=args.mod_guid,
        limit=args.limit,
        offset=args.offset,
    )
    payload = {
        "count": len(rows),
        "category": args.category,
        "resource_id": resource_id,
        "mod_guid": args.mod_guid,
        "usages": [_usage_obj(u) for u in rows],
    }
    lines = [f"Usages: {len(rows)}"]
    lines += [f"  {_usage_line(u)}" for u in rows]
    _emit(args, payload, "\n".join(lines) if rows else None)
    return 0


def cmd_usage_categories(conn, args) -> int:
    resource_id = None
    if args.resource is not None:
        summary = ResourceQuery(conn).resolve(args.resource)
        if summary is None:
            return _not_found("Resource", args.resource)
        resource_id = summary.id
    stats = UsageQuery(conn).category_stats(
        resource_id=resource_id, mod_guid=args.mod_guid
    )
    payload = {
        "scope": {"resource_id": resource_id, "mod_guid": args.mod_guid},
        "categories": [_category_stats_obj(s) for s in stats],
    }
    lines = ["Category statistics (usage / resources / MODs):"]
    for s in stats:
        lines.append(
            f"  {s.category:<9} usages={s.usage_count:<5}"
            f" resources={s.resource_count:<4} mods={s.mod_count}"
        )
    _emit(args, payload, "\n".join(lines))
    return 0


def cmd_unknown_properties(conn, args) -> int:
    resource_id = None
    if args.resource is not None:
        summary = ResourceQuery(conn).resolve(args.resource)
        if summary is None:
            return _not_found("Resource", args.resource)
        resource_id = summary.id
    props = UsageQuery(conn).unknown_properties(
        resource_id=resource_id, mod_guid=args.mod_guid
    )
    payload = {
        "count": len(props),
        "scope": {"resource_id": resource_id, "mod_guid": args.mod_guid},
        "properties": props,
    }
    lines = [f"Unknown properties: {len(props)}"]
    lines += [f"  {p}" for p in props]
    _emit(args, payload, "\n".join(lines) if props else None)
    return 0


_HANDLERS = {
    "resources": cmd_resources,
    "resource": cmd_resource,
    "resource-mods": cmd_resource_mods,
    "resource-plugins": cmd_resource_plugins,
    "resource-authors": cmd_resource_authors,
    "mods": cmd_mods,
    "mod": cmd_mod,
    "mod-resources": cmd_mod_resources,
    "mod-usages": cmd_mod_usages,
    "authors": cmd_authors,
    "author": cmd_author,
    "author-resources": cmd_author_resources,
    "plugins": cmd_plugins,
    "plugin": cmd_plugin,
    "plugin-resources": cmd_plugin_resources,
    "missing-mods": cmd_missing_mods,
    "orphan-mods": cmd_orphan_mods,
    "duplicates": cmd_duplicates,
    "usages": cmd_usages,
    "usage-categories": cmd_usage_categories,
    "unknown-properties": cmd_unknown_properties,
}


# ---------------------------------------------------------------------------
# parser / dispatch
# ---------------------------------------------------------------------------


def add_query_parser(sub) -> None:
    """把 ``query`` 子命令注册到 ``main.py`` 的 subparsers。"""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="以 JSON 输出（字段稳定）")

    query = sub.add_parser(
        "query", help="只读查询（Phase 1.3-B；数据全部来自 Query Layer，不改数据库）"
    )
    qsub = query.add_subparsers(dest="query_command", required=True)

    resources = qsub.add_parser("resources", parents=[common], help="基础资源列表（可筛选）")
    resources.add_argument("--type", dest="resource_type", default=None, help="resource_type")
    resources.add_argument("--game", default=None, help="游戏格式：KKS / KK")
    resources.add_argument("--library", type=int, default=None, help="library_id")
    resources.add_argument("--status", default=None, help="scan_status：present/missing/error/new")
    resources.add_argument(
        "--needs-review", action="store_true", default=None, help="只看待确认资源"
    )
    resources.add_argument("--mod", dest="mod_guid", default=None, help="按使用的 MOD guid 过滤")
    resources.add_argument(
        "--plugin", dest="plugin_guid", default=None, help="按使用的插件 guid 过滤"
    )
    resources.add_argument("--category", default=None, help="按 property 语义类别过滤")
    mods_group = resources.add_mutually_exclusive_group()
    mods_group.add_argument(
        "--with-mods", dest="has_mods", action="store_const", const=True, default=None,
        help="只看使用了至少一个 MOD 的资源",
    )
    mods_group.add_argument(
        "--without-mods", dest="has_mods", action="store_const", const=False,
        help="只看没有使用任何 MOD 的资源",
    )
    resources.add_argument("--order", default="id", help="排序字段（id/name/file_size/…）")
    resources.add_argument("--desc", action="store_true", help="降序")
    resources.add_argument("--limit", type=int, default=None, help="最多返回多少条")
    resources.add_argument("--offset", type=int, default=0, help="分页偏移")

    resource = qsub.add_parser("resource", parents=[common], help="单资源详情（id/路径/key）")
    resource.add_argument("target", help="资源 id、file_path、file_path_key 或 relative_path")

    for name, helptext in (
        ("resource-mods", "某资源使用的 MOD（汇总）"),
        ("resource-plugins", "某资源使用的插件"),
        ("resource-authors", "某资源的作者（含 authors_raw）"),
    ):
        p = qsub.add_parser(name, parents=[common], help=helptext)
        p.add_argument("target", help="资源 id 或路径")

    qsub.add_parser("mods", parents=[common], help="本地已安装的 MOD 列表")

    mod = qsub.add_parser("mod", parents=[common], help="单 MOD 详情")
    mod.add_argument("guid")

    mod_res = qsub.add_parser("mod-resources", parents=[common], help="MOD → 使用它的资源")
    mod_res.add_argument("guid")

    mod_usages = qsub.add_parser("mod-usages", parents=[common], help="MOD → 逐槽位 usage")
    mod_usages.add_argument("guid")
    mod_usages.add_argument("--category", default=None, help="按语义类别过滤")

    qsub.add_parser("authors", parents=[common], help="作者列表")

    author = qsub.add_parser("author", parents=[common], help="单作者详情（名字或 id）")
    author.add_argument("target")

    author_res = qsub.add_parser(
        "author-resources", parents=[common], help="作者 → 资源"
    )
    author_res.add_argument("target")

    qsub.add_parser("plugins", parents=[common], help="插件列表")

    plugin = qsub.add_parser("plugin", parents=[common], help="单插件详情")
    plugin.add_argument("guid")

    plugin_res = qsub.add_parser(
        "plugin-resources", parents=[common], help="插件 → 资源"
    )
    plugin_res.add_argument("guid")

    qsub.add_parser("missing-mods", parents=[common], help="被引用但本地未安装的 MOD")
    qsub.add_parser("orphan-mods", parents=[common], help="本地已安装但无人引用的 MOD")

    qsub.add_parser(
        "duplicates",
        parents=[common],
        help="字节完全相同的资源组（byte-duplicate，只读派生；不含语义等价判断）",
    )

    usages = qsub.add_parser("usages", parents=[common], help="全库 usage 查询")
    usages.add_argument("--resource", default=None, help="限定资源（id/路径）")
    usages.add_argument("--mod", dest="mod_guid", default=None, help="限定 MOD guid")
    usages.add_argument("--category", default=None, help="限定语义类别")
    usages.add_argument("--limit", type=int, default=None)
    usages.add_argument("--offset", type=int, default=0)

    cats = qsub.add_parser(
        "usage-categories", parents=[common], help="按语义类别统计（usage/资源/MOD）"
    )
    cats.add_argument("--resource", default=None, help="限定资源（id/路径）")
    cats.add_argument("--mod", dest="mod_guid", default=None, help="限定 MOD guid")

    unknown = qsub.add_parser(
        "unknown-properties", parents=[common], help="无法归类的原始 property"
    )
    unknown.add_argument("--resource", default=None, help="限定资源（id/路径）")
    unknown.add_argument("--mod", dest="mod_guid", default=None, help="限定 MOD guid")


def dispatch_query(args) -> int:
    """执行 ``query`` 子命令；只读，且把 Query Layer 的 ValueError 变成参数错误。"""
    handler = _HANDLERS.get(getattr(args, "query_command", None))
    if handler is None:  # pragma: no cover - argparse 已保证
        return 2
    conn = _open_conn()
    try:
        return handler(conn, args)
    except ValueError as exc:
        print(f"参数错误：{exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()


__all__ = ["add_query_parser", "dispatch_query"]
