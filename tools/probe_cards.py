"""只读探测 Koikatu / Koikatu Sunshine 角色卡尾部数据。

用途：为 Phase 1.2 的测试样本选取提供依据。读取每张卡内置的：

- 卡片类型标记（【KoiKatuChara】/【KoiKatuCharaSun】...）
- 角色姓名（Parameter 块）
- 卡作者（marco.authordata -> Authors）
- MOD 依赖列表（com.bepis.sideloader.universalautoresolver -> info，
  每项含 ModID / Property / Author / Name）
- 插件数据键（ExtensibleSaveFormat）
- 内嵌 PNG 贴图数量

本脚本严格遵守项目「只读」约束：只打开文件读取字节，绝不写回原文件。

卡片尾部结构（逆向结果，base 为块区起点）::

    [PNG1 主图][int32][marker 字符串][version 字符串][PNG2 头像]
    [int32 lstLen][lstInfo msgpack]        # {lstInfo:[{name,version,pos,size}, ...]}
    [int32 块区总大小][int32 保留]
    [区块数据...]                          # base = lstInfo 结束 + 8

区块按 lstInfo 的 pos/size 排列；子块多为 ``[int32 len][msgpack]``，
其中 KKEx 区的内容本身即 msgpack（插件 GUID -> [version, data]）。
"""

from __future__ import annotations

import argparse
import json
import os
import struct
from collections import Counter

import msgpack

MARKER_PREFIX = "【KoiKatuChara"
LSTINFO_SIG = b"\x81\xa7lstInfo"
PNG_SIG = b"\x89PNG\r\n\x1a\n"
MODLIST_KEY = "com.bepis.sideloader.universalautoresolver"


def _read_string(buf: bytes, pos: int) -> tuple[str, int]:
    """读取 .NET BinaryReader.ReadString（7bit 长度前缀 + UTF-8）。"""
    length = 0
    shift = 0
    while True:
        b = buf[pos]
        pos += 1
        length |= (b & 0x7F) << shift
        if not b & 0x80:
            break
        shift += 7
    return buf[pos : pos + length].decode("utf-8", "replace"), pos + length


def _first_object(buf: bytes):
    """解出 buf 开头的第一个 msgpack 对象，返回 (obj, 消耗字节数)。"""
    unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
    unpacker.feed(buf)
    try:
        obj = next(unpacker)
    except Exception:
        return None, 0
    return obj, unpacker.tell()


def _scan_subblocks(data: bytes, pos: int, size: int) -> list:
    """按 [int32 len][msgpack] 扫描一个区块，返回其中的 msgpack 对象列表。"""
    objs = []
    end = pos + size
    while pos + 4 <= end:
        ln = struct.unpack_from("<i", data, pos)[0]
        if ln <= 0 or pos + 4 + ln > end + 4:
            return objs
        obj, used = _first_object(data[pos + 4 : pos + 4 + ln])
        if obj is None:
            return objs
        objs.append(obj)
        pos += 4 + ln
    return objs


def _decode_region(data: bytes, start: int, size: int) -> list:
    """解码一个区块。区块要么是原生 msgpack，要么是若干 [int32 len][msgpack]。"""
    region = data[start : start + size]
    obj, used = _first_object(region)
    if obj is not None and used >= size - 8:
        return [obj]
    return _scan_subblocks(region, 0, size)


def parse_card(path: str) -> dict:
    with open(path, "rb") as fh:
        data = fh.read()

    result: dict = {
        "path": path,
        "size": len(data),
        "card_kind": None,
        "game": None,
        "version": None,
        "name": None,
        "lastname": None,
        "firstname": None,
        "nickname": None,
        "authors": [],
        "plugins": [],
        "mods": [],
        "mod_ids": [],
        "mod_properties": {},
        "embedded_png": data.count(PNG_SIG),
        "parse_status": "ok",
        "error": None,
    }

    marker_pos = data.find(MARKER_PREFIX.encode("utf-8"))
    if marker_pos < 0:
        result["parse_status"] = "failed"
        result["error"] = "marker not found"
        return result

    # marker 之前 4 字节是 int32；marker 本身是 7bit 长度前缀字符串。
    try:
        marker, after_marker = _read_string(data, marker_pos - 1)
        version, _ = _read_string(data, after_marker)
        result["card_kind"] = marker.strip("【】")
        result["version"] = version
        result["game"] = "KKS" if marker.endswith("Sun】") else "KK"
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"marker parse: {exc}"

    lst_pos = data.find(LSTINFO_SIG)
    if lst_pos < 0:
        result["parse_status"] = "partial"
        result["error"] = (result["error"] or "") + " lstInfo not found"
        return result

    lst_len = struct.unpack_from("<i", data, lst_pos - 4)[0]
    lst, used = _first_object(data[lst_pos : lst_pos + lst_len])
    if not isinstance(lst, dict) or "lstInfo" not in lst:
        result["parse_status"] = "failed"
        result["error"] = "lstInfo decode failed"
        return result

    base = lst_pos + used + 8
    blocks = {e["name"]: e for e in lst["lstInfo"]}

    # --- 角色姓名：Parameter 区块 ---
    param = blocks.get("Parameter")
    if param:
        for obj in _decode_region(data, base + param["pos"], param["size"]):
            if isinstance(obj, dict) and ("lastname" in obj or "firstname" in obj):
                result["lastname"] = obj.get("lastname")
                result["firstname"] = obj.get("firstname")
                result["nickname"] = obj.get("nickname")
                result["name"] = f"{obj.get('lastname', '')}{obj.get('firstname', '')}".strip() or obj.get("nickname")
                break

    # --- KKEx：插件数据 + MOD 依赖列表 ---
    kex_entry = blocks.get("KKEx")
    kex = None
    if kex_entry:
        start = base + kex_entry["pos"]
        kex, _ = _first_object(data[start : start + kex_entry["size"]])
        if not isinstance(kex, dict):
            kex = None
        result["kex_size"] = kex_entry["size"]
        result["embed_png_kex"] = data[
            start : start + kex_entry["size"]
        ].count(PNG_SIG)
    result["block_sizes"] = {k: v["size"] for k, v in blocks.items()}
    if isinstance(kex, dict):
        result["plugins"] = sorted(kex.keys())
        for key in ("marco.authordata",):
            entry = kex.get(key)
            if isinstance(entry, list) and len(entry) == 2 and isinstance(entry[1], dict):
                authors = entry[1].get("Authors")
                if isinstance(authors, (bytes, bytearray)):
                    authors, _ = _first_object(bytes(authors))
                if isinstance(authors, list):
                    result["authors"] = [a for a in authors if isinstance(a, str)]
        entry = kex.get(MODLIST_KEY)
        if isinstance(entry, list) and len(entry) == 2 and isinstance(entry[1], dict):
            mods = []
            for raw in entry[1].get("info", []) or []:
                obj = raw
                if isinstance(raw, (bytes, bytearray)):
                    obj, _ = _first_object(bytes(raw))
                if isinstance(obj, dict):
                    mods.append(
                        {
                            "ModID": obj.get("ModID"),
                            "Property": obj.get("Property"),
                            "Author": obj.get("Author"),
                            "Name": obj.get("Name"),
                        }
                    )
            result["mods"] = mods
            result["mod_ids"] = sorted({m["ModID"] for m in mods if m["ModID"]})
            result["mod_properties"] = dict(Counter(m["Property"] for m in mods if m["Property"]))

    return result


def iter_cards(root: str):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".png"):
                yield os.path.join(dirpath, name)


def main() -> int:
    ap = argparse.ArgumentParser(description="只读解析 Koikatu/KKS 角色卡")
    ap.add_argument("paths", nargs="+", help="卡片文件或目录")
    ap.add_argument("--json", help="将结果写入 JSON 文件")
    ap.add_argument("--limit", type=int, default=0, help="最多处理多少张卡")
    args = ap.parse_args()

    targets = []
    for p in args.paths:
        if os.path.isdir(p):
            targets.extend(sorted(iter_cards(p)))
        else:
            targets.append(p)
    if args.limit:
        targets = targets[: args.limit]

    results = []
    for i, path in enumerate(targets, 1):
        try:
            results.append(parse_card(path))
        except Exception as exc:  # noqa: BLE001
            results.append({"path": path, "parse_status": "failed", "error": repr(exc)})
        if i % 25 == 0:
            print(f"  ... {i}/{len(targets)}", file=__import__("sys").stderr)

    payload = json.dumps(results, ensure_ascii=False, indent=1)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(payload)
        print(f"wrote {len(results)} records -> {args.json}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
