"""只读卡片 / zipmod 探针（Phase 1.2 前的样本分析工具，**不是** Scanner）。

⚠️ 本文件是 **Phase 1.2-B 之前的分析期探针**，保留作历史证据与交叉验证之用。
正式实现见 ``core/parsers/``（``card.py`` / ``zipmod.py`` / ``models.py``）——
那里才是权威逻辑，本文件的结论已与它逐项对齐。

用途：把一个 KKS/KK 卡片文件拆解成结构化事实，供人工核对与写报告。
它只 ``open(path, "rb")`` 读取字节，**不写入、不修改、不生成任何缓存文件**。

    python tools/inspect_card.py <文件或目录> [--json]

实测确认的卡片容器结构（见 docs/phase1/SAMPLE_ANALYSIS.md）::

    [PNG 数据流 ... 到 IEND 结束]
    [int32]  productNo
    [u8 长度 + UTF-8] marker       例如 "【KoiKatuCharaSun】"
    [u8 长度 + UTF-8] 卡片版本     例如 "0.0.0"
    [int32]  面部预览图长度 + JPEG 字节
    [int32]  lstInfo 长度 + msgpack {"lstInfo": [{name,version,pos,size}...]}
    [int32]  数据区长度
    [int32]  保留字段（实测为 0）
    [数据区] 各块按 lstInfo 的 pos/size 排列

数据区内部是 msgpack 对象流，夹杂 ``[int32 长度][msgpack]`` 分帧的二进制块，
因此本工具用「逐字节重同步」的方式容错抽取对象。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

import msgpack

PNG_SIG = b"\x89PNG\r\n\x1a\n"

# 关心这些关键字：命中即认为是有意义的业务信息
WATCH_KEYS = (
    "lastname",
    "firstname",
    "nickname",
    "userID",
    "dataID",
    "sideloader",
    "info",
    "author",
)


# ---------------------------------------------------------------------------
# 基础
# ---------------------------------------------------------------------------


def _i32(buf: bytes, off: int) -> int:
    return struct.unpack("<i", buf[off : off + 4])[0]


def _u8str(buf: bytes, off: int) -> tuple[str, int]:
    n = buf[off]
    return buf[off + 1 : off + 1 + n].decode("utf-8", "replace"), off + 1 + n


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def quick_hash(path: Path, head: int = 64 * 1024, tail: int = 64 * 1024) -> str:
    """轻量指纹：大小 + 首尾块。用于去重预筛，不读全文件。"""
    size = path.stat().st_size
    h = hashlib.sha256()
    h.update(struct.pack("<Q", size))
    with path.open("rb") as fh:
        h.update(fh.read(head))
        if size > head + tail:
            fh.seek(-tail, 2)
            h.update(fh.read(tail))
    return h.hexdigest()[:32]


def _pack_objects(buf: bytes, base: int = 0, limit: int = 4000) -> list[dict]:
    """容错抽取：逐字节重同步，收集能独立解码的 msgpack 对象。"""
    found: list[dict] = []
    p = 0
    end = len(buf)
    while p < end and len(found) < limit:
        un = msgpack.Unpacker(raw=False, strict_map_key=False)
        un.feed(buf[p:])
        try:
            obj = next(iter(un))
        except Exception:
            p += 1
            continue
        consumed = un.tell()
        if consumed <= 0:
            p += 1
            continue
        found.append({"offset": base + p, "consumed": consumed, "obj": obj})
        p += consumed
    return found


def _summarize_obj(obj, depth: int = 0, max_depth: int = 2):
    if isinstance(obj, dict):
        if depth >= max_depth:
            return f"<map {len(obj)}>"
        return {str(k): _summarize_obj(v, depth + 1, max_depth) for k, v in list(obj.items())[:20]}
    if isinstance(obj, list):
        if depth >= max_depth:
            return f"<list {len(obj)}>"
        return [_summarize_obj(v, depth + 1, max_depth) for v in obj[:8]]
    if isinstance(obj, (bytes, bytearray)):
        return f"<bin {len(obj)}>"
    if isinstance(obj, str) and len(obj) > 200:
        return obj[:200] + f"...<+{len(obj) - 200}>"
    return obj


# ---------------------------------------------------------------------------
# PNG
# ---------------------------------------------------------------------------


def read_png_chunks(data: bytes) -> tuple[list[dict], int | None]:
    if not data.startswith(PNG_SIG):
        return [], None
    chunks: list[dict] = []
    off = len(PNG_SIG)
    while off + 8 <= len(data):
        length = struct.unpack(">I", data[off : off + 4])[0]
        ctype = data[off + 4 : off + 8].decode("latin-1", "replace")
        chunks.append({"type": ctype, "length": length, "offset": off})
        off += 12 + length
        if ctype == "IEND":
            return chunks, off
    return chunks, None


# ---------------------------------------------------------------------------
# 卡片
# ---------------------------------------------------------------------------


def parse_card(path: Path) -> dict:
    data = path.read_bytes()
    result: dict = {
        "file": path.name,
        "path": str(path),
        "size": len(data),
        "ext": path.suffix.lower(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "quick_hash": quick_hash(path),
        "kind": None,
        "error": None,
    }

    chunks, png_end = read_png_chunks(data)
    result["png_chunks"] = chunks
    result["png_end"] = png_end
    if png_end is None:
        result["kind"] = "not_png"
        return result

    trailing = data[png_end:]
    result["trailing_bytes"] = len(trailing)
    if not trailing:
        result["kind"] = "png_only"
        return result

    try:
        p = 0
        product_no = _i32(trailing, p)
        p += 4
        marker, p = _u8str(trailing, p)
        card_version, p = _u8str(trailing, p)
        face_len = _i32(trailing, p)
        p += 4
        face = trailing[p : p + face_len]
        p += face_len
        lst_len = _i32(trailing, p)
        p += 4
        lst_info = msgpack.unpackb(
            trailing[p : p + lst_len], raw=False, strict_map_key=False
        )
        p += lst_len
        region_len = _i32(trailing, p)
        p += 4
        reserved = _i32(trailing, p)
        p += 4
        region = trailing[p : p + region_len]
        region_base = png_end + p
    except Exception as exc:  # noqa: BLE001 - 探针要能容错
        result["kind"] = "png_with_trailing_unknown"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    result.update(
        {
            "kind": "card",
            "product_no": product_no,
            "marker": marker,
            "card_version": card_version,
            "face_jpeg_bytes": face_len,
            "face_jpeg_ok": face[:4] == b"\xff\xd8\xff\xe0",
            "face_jpeg_tail": face[-2:].hex(),
            "lst_info": lst_info.get("lstInfo", []),
            "region_len": region_len,
            "region_reserved": reserved,
            "region_bytes": len(region),
            "region_covers_to_eof": p + region_len == len(trailing),
        }
    )

    objects = _pack_objects(region, base=region_base)
    result["object_count"] = len(objects)
    result["_objects"] = objects

    # 按 lstInfo 分块再抽一遍，便于把「插件表」「角色名」等定位到具体块
    blocks: dict[str, list[dict]] = {}
    for entry in result["lst_info"]:
        start = int(entry.get("pos", 0))
        size = int(entry.get("size", 0))
        seg = region[start : start + size]
        blocks[str(entry.get("name"))] = _pack_objects(seg, base=region_base + start)
    result["block_object_counts"] = {k: len(v) for k, v in blocks.items()}
    result["_blocks"] = blocks

    # ---- 定向抽取 ----
    result["name"] = _find_name(objects)
    result["user_id"] = _find_scalar(objects, "userID")
    result["data_id"] = _find_scalar(objects, "dataID")
    plugins = _find_plugins(objects, blocks)
    result["plugins"] = plugins
    result["plugin_count"] = len(plugins)
    assignments = _find_mod_assignments(objects, blocks)
    result["_mod_assignments"] = assignments
    result["mod_assignments"] = len(assignments)
    unique_ids: list[str] = []
    for a in assignments:
        if a["mod_id"] not in unique_ids:
            unique_ids.append(a["mod_id"])
    result["unique_mod_ids"] = unique_ids
    result["unique_mod_count"] = len(unique_ids)
    result["bin_blobs"] = _count_bins(objects)
    result["nested_bins"] = _count_bins_recursive(objects)
    result["embedded_texture_like"] = _count_embedded_textures(objects)
    result["author_like_keys"] = _find_keys_containing(objects, "author")
    result["eye_slots"] = _find_face_slots(objects)
    return result


def _find_name(objects: list[dict]) -> str | None:
    for item in objects:
        obj = item["obj"]
        if isinstance(obj, dict) and "lastname" in obj and "firstname" in obj:
            return f"{obj.get('lastname', '')}{obj.get('firstname', '')}"
    return None


def _find_scalar(objects: list[dict], key: str):
    for item in objects:
        obj = item["obj"]
        if isinstance(obj, dict) and key in obj and not isinstance(obj[key], (dict, list)):
            return obj[key]
    return None


def _find_keys_containing(objects: list[dict], needle: str) -> list[str]:
    hits: list[str] = []
    for item in objects:
        obj = item["obj"]
        if isinstance(obj, dict):
            for k in obj:
                if needle in str(k) and str(k) not in hits:
                    hits.append(str(k))
    return hits


def _find_plugins(objects: list[dict], blocks: dict[str, list[dict]] | None = None) -> list[str]:
    """插件表：优先看 KKEx 块（插件键 → 插件数据），否则退化为全文扫描。"""
    candidates: list[list[str]] = []
    if blocks and "KKEx" in blocks:
        for item in blocks["KKEx"]:
            obj = item["obj"]
            if isinstance(obj, dict):
                candidates.append([str(k) for k in obj])
    for item in objects:
        obj = item["obj"]
        if isinstance(obj, dict) and len(obj) <= 40:
            keys = [str(k) for k in obj]
            if any("." in k for k in keys):
                candidates.append(keys)
    best: list[str] = []
    for keys in candidates:
        if len(keys) > len(best):
            best = keys
    return best


def _find_mod_assignments(
    objects: list[dict], blocks: dict[str, list[dict]] | None = None
) -> list[dict]:
    """解析 sideloader 插件的依赖表。

    实测结构：``{"com.bepis.sideloader.universalautoresolver": [版本, {"info": [...]}]}``，
    其中 ``info`` 的每一项是**逐槽位记录**（本身又是 msgpack 二进制），字段为::

        ModID / Slot / LocalSlot / Property / CategoryNo / Author / Website / Name

    ``Property`` 指出该 MOD 被用在哪（如 ``outfit6.accessory10.ChaFileAccessory.PartsInfo.id``）。
    同一 MOD 被多个槽位引用时会出现多条记录 —— 所以「唯一 MOD 数」必须按 ModID 去重。
    """
    raw_records: list = []
    pool = list(objects)
    if blocks and "KKEx" in blocks:
        pool = list(blocks["KKEx"]) + pool
    for item in pool:
        obj = item["obj"]
        if not isinstance(obj, dict):
            continue
        for k, v in obj.items():
            if "sideloader" not in str(k).lower():
                continue
            if isinstance(v, list):
                for part in v:
                    if isinstance(part, dict) and "info" in part:
                        info = part["info"]
                        if isinstance(info, list):
                            raw_records = info
    out: list[dict] = []
    for rec in raw_records:
        if isinstance(rec, (bytes, bytearray)):
            try:
                rec = msgpack.unpackb(bytes(rec), raw=False, strict_map_key=False)
            except Exception:
                continue
        if not isinstance(rec, dict):
            continue
        out.append(
            {
                "mod_id": str(rec.get("ModID", "")),
                "property": str(rec.get("Property", "")),
                "slot": rec.get("Slot"),
                "local_slot": rec.get("LocalSlot"),
                "category_no": rec.get("CategoryNo"),
                "author": rec.get("Author"),
                "website": rec.get("Website"),
                "name": rec.get("Name"),
            }
        )
    return out


def _count_bins_recursive(nodes, depth: int = 0) -> int:
    """递归统计二进制块（卡片内嵌贴图疑似以 bin 形式挂在各部件下）。"""
    if depth > 12:
        return 0
    total = 0
    for item in nodes:
        obj = item["obj"] if isinstance(item, dict) and "obj" in item else item
        total += _walk_bins(obj, depth)
    return total


def _walk_bins(obj, depth: int, min_size: int = 256) -> int:
    if depth > 12:
        return 0
    if isinstance(obj, (bytes, bytearray)):
        return 1 if len(obj) >= min_size else 0
    if isinstance(obj, dict):
        return sum(_walk_bins(v, depth + 1, min_size) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return sum(_walk_bins(v, depth + 1, min_size) for v in obj)
    return 0


def _find_face_slots(objects: list[dict]) -> dict:
    """面部槽位 id（眼睛相关）。这些 id 是否指向 MOD 需要在 Phase 1.2 再验证。"""
    wanted = (
        "pupil",
        "hlUpId",
        "hlDownId",
        "whiteId",
        "eyelineUpId",
        "eyelineDownId",
        "eyebrowId",
        "headId",
        "skinId",
        "detailId",
    )
    for item in objects:
        obj = item["obj"]
        if not isinstance(obj, dict) or "shapeValueFace" not in obj:
            continue
        out: dict = {}
        for k in wanted:
            if k not in obj:
                continue
            v = obj[k]
            if isinstance(v, list) and v and isinstance(v[0], dict):
                v = [{"id": p.get("id")} for p in v]
            out[k] = v
        return out
    return {}


def _count_embedded_textures(objects: list[dict]) -> int:
    """统计卡片内嵌贴图。待验证：需与样本清单声明的「内嵌贴图」数量对齐。"""
    total = 0
    for item in objects:
        obj = item["obj"]
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (bytes, bytearray)) and len(v) > 512:
                    total += 1
        elif isinstance(obj, (bytes, bytearray)) and len(obj) > 512:
            total += 1
    return total


def _count_bins(objects: list[dict]) -> int:
    return sum(1 for item in objects if isinstance(item["obj"], (bytes, bytearray)))


# ---------------------------------------------------------------------------
# zipmod
# ---------------------------------------------------------------------------


def parse_zipmod(path: Path) -> dict:
    info: dict = {
        "file": path.name,
        "path": str(path),
        "size": path.stat().st_size,
        "ext": path.suffix.lower(),
        "sha256": sha256_file(path),
        "quick_hash": quick_hash(path),
        "kind": "zipmod",
        "entries": [],
        "manifest": None,
    }
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            info["entries"] = names[:200]
            info["entry_count"] = len(names)
            manifest_name = next(
                (n for n in names if n.lower().endswith("manifest.xml")), None
            )
            if manifest_name:
                raw = zf.read(manifest_name)
                info["manifest_raw"] = raw.decode("utf-8", "replace")
                info["manifest_name"] = manifest_name
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def parse_manifest_fields(xml_text: str) -> dict:
    """极简 manifest.xml 字段抽取（不引入 XML 依赖假设，按标记切分）。"""
    fields: dict = {}
    for tag in ("guid", "name", "author", "version", "website", "description", "game"):
        start = xml_text.find(f"<{tag}>")
        if start < 0:
            continue
        start += len(tag) + 2
        end = xml_text.find(f"</{tag}>", start)
        if end > 0:
            fields[tag] = xml_text[start:end].strip()
    return fields


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def iter_targets(target: Path):
    if target.is_dir():
        yield from sorted(p for p in target.rglob("*") if p.is_file())
    else:
        yield target


def analyze(path: Path) -> dict:
    if path.suffix.lower() in (".zipmod", ".zip"):
        info = parse_zipmod(path)
        if info.get("manifest_raw"):
            info["manifest_fields"] = parse_manifest_fields(info["manifest_raw"])
        return info
    if path.suffix.lower() == ".png":
        return parse_card(path)
    return {
        "file": path.name,
        "path": str(path),
        "size": path.stat().st_size,
        "ext": path.suffix.lower(),
        "kind": "other",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="inspect_card", description=__doc__)
    ap.add_argument("target", help="卡片 / zipmod 文件，或包含它们的目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--objects", action="store_true", help="附带抽取到的对象清单")
    args = ap.parse_args(argv)

    results = [analyze(p) for p in iter_targets(Path(args.target))]

    def clean(item: dict) -> dict:
        out = {k: v for k, v in item.items() if not k.startswith("_")}
        if args.objects and "_objects" in item:
            out["objects"] = [
                {"offset": o["offset"], "consumed": o["consumed"], "obj": _summarize_obj(o["obj"])}
                for o in item["_objects"]
            ]
        return out

    payload = [clean(r) for r in results]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        for item in payload:
            print("=" * 78)
            for k, v in item.items():
                if k in ("entries", "manifest_raw"):
                    continue
                print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
