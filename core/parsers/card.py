"""只读 KKS/KK 角色卡解析器。

容器结构（22 张真实卡片逐字节验证，见 docs/phase1/SAMPLE_ANALYSIS.md）::

    [标准 PNG 数据流 ... 到 IEND 结束]
    [int32 LE]  productNo
    [7bit 变长长度 + UTF-8] card marker     例如 "【KoiKatuCharaSun】"
    [7bit 变长长度 + UTF-8] card version    例如 "0.0.0"
    [int32 LE]  面部预览图字节数 + 图像（JPEG 或 PNG，两种都实测存在）
    [int32 LE]  lstInfo 长度 + msgpack {"lstInfo":[{name,version,pos,size}...]}
    [int32 LE]  data region 长度
    [int32 LE]  file-level reserved（实测恒为 0）
    [数据区]    按 lstInfo 的 pos/size 排列

本模块的硬性约定
----------------
- **只读**：只 ``open(path, "rb")``，不写入、不移动、不生成缓存。
- **按 ``pos`` 排序**读取数据块：lstInfo 的列表顺序**不是**物理顺序
  （实测 ``KKEx`` 排在列表第一位，物理位置在最后）。
- **数据区容错**：数据区是「msgpack 对象流 + ``[int32 长度][msgpack]`` 分帧 +
  嵌套 binary 帧」的混合体，一个块**不一定是**一个 msgpack。
- **非关键块失败不影响整卡**：Parameter / About / KKEx 任一失败只记 warning。
- **不做类型推断**：不判断 eyes / skin / hair / clothes，也不做高 ID 来源启发式。
- **不区分游戏外的 marker**：``KoiKatuCharaSun`` 与 ``KoiKatuChara`` 原样保留。
"""

from __future__ import annotations

import struct
from pathlib import Path

import msgpack

from core.parsers.models import (
    AUTHORS_PLUGIN_GUID,
    CHARACTER_CARD_MARKERS,
    MODLIST_PLUGIN_GUID,
    PARSE_FAILED,
    PARSE_OK,
    PARSE_PARTIAL,
    CharacterCardParseResult,
    LstInfoEntry,
    ModDependencyRecord,
)
from core.models import partition_authors

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SOI = b"\xff\xd8\xff"
IEND_TYPE = "IEND"  # PNG 块类型是 4 字节 ASCII，读出来是 str

# 数据区里每张内嵌贴图都是一张完整 PNG —— 直接数 PNG 签名即可。
# 主图在 IEND 之前、面部预览图在数据区之前，因此都不计入。
_EMBEDDED_PNG_SIGNATURE = PNG_SIGNATURE

# 容错扫描的安全上限（防止损坏文件导致死循环）
_MAX_OBJECTS = 20000
_MAX_BLOCK_SCAN_STEPS = 8_000_000


# ---------------------------------------------------------------------------
# 基础读取
# ---------------------------------------------------------------------------


def _i32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<i", buf, off)[0]


def read_png_chunks(data: bytes) -> tuple[list[dict], int | None]:
    """遍历 PNG 块，返回 (块列表, IEND 之后的偏移)。找不到 IEND 返回 (..., None)。"""
    if not data.startswith(PNG_SIGNATURE):
        return [], None
    chunks: list[dict] = []
    off = len(PNG_SIGNATURE)
    while off + 8 <= len(data):
        length = struct.unpack_from(">I", data, off)[0]
        ctype = data[off + 4 : off + 8].decode("latin-1", "replace")
        chunks.append({"type": ctype, "length": length, "offset": off})
        off += 12 + length
        if ctype == IEND_TYPE:
            return chunks, off
        if off <= 0 or off > len(data):  # 越界，损坏
            return chunks, None
    return chunks, None


def _read_dotnet_string(buf: bytes, pos: int) -> tuple[str, int]:
    """读取 .NET BinaryReader.ReadString 风格字符串：7bit 变长长度 + UTF-8。

    实测 marker（21 字节）与 version（5 字节）都很短，因此与「单字节长度」等价；
    这里用变长写法以便容忍更长字符串。
    """
    length = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError("字符串长度前缀越界")
        byte = buf[pos]
        pos += 1
        length |= (byte & 0x7F) << shift
        if not byte & 0x80:
            break
        shift += 7
        if shift > 28:
            raise ValueError("字符串长度前缀异常")
    if pos + length > len(buf):
        raise ValueError("字符串内容越界")
    return buf[pos : pos + length].decode("utf-8", "replace"), pos + length


# ---------------------------------------------------------------------------
# 数据区容错解码
# ---------------------------------------------------------------------------


def _first_object(buf: bytes) -> tuple[object | None, int]:
    """解出 buf 开头的第一个 msgpack 对象，返回 (对象, 消耗字节数)。"""
    unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
    unpacker.feed(buf)
    try:
        obj = next(iter(unpacker))
    except Exception:  # noqa: BLE001 - 容错：任何解码失败都视为「这里不是对象」
        return None, 0
    return obj, unpacker.tell()


def decode_block(buf: bytes) -> tuple[list, list[str]]:
    """容错解码一个数据块，返回 (对象列表, 警告列表)。

    依次尝试三种形态，任一形态失败都不会抛异常：

    1. 整块就是一个 msgpack 对象（例如 ``About`` / ``Parameter``）；
    2. ``[int32 长度][msgpack]`` 分帧序列（例如 ``Custom``）；
    3. 裸 msgpack 对象流 + 逐字节重同步（例如 ``Coordinate`` 里的嵌套 binary 帧）。
    """
    if not buf:
        return [], ["数据块为空"]

    warnings: list[str] = []

    obj, used = _first_object(buf)
    if obj is not None and used == len(buf):
        return [obj], warnings

    objects: list = []
    pos = 0
    steps = 0
    resynced = 0
    end = len(buf)
    while pos < end and len(objects) < _MAX_OBJECTS:
        steps += 1
        if steps > _MAX_BLOCK_SCAN_STEPS:
            warnings.append("数据块扫描超过安全上限，已提前停止")
            break

        # 形态 2：长度前缀帧
        if pos + 4 <= end:
            length = _i32(buf, pos)
            if 0 < length <= end - pos - 4:
                inner, used_inner = _first_object(buf[pos + 4 : pos + 4 + length])
                if inner is not None and used_inner == length:
                    objects.append(inner)
                    pos += 4 + length
                    continue

        # 形态 3：裸 msgpack 对象
        obj, used = _first_object(buf[pos:])
        if obj is not None and used > 0:
            objects.append(obj)
            pos += used
            continue

        pos += 1
        resynced += 1

    if resynced:
        warnings.append(f"数据块内有 {resynced} 字节无法解码（已跳过）")
    if not objects:
        warnings.append("数据块内没有可解码的 msgpack 对象")
    return objects, warnings


# ---------------------------------------------------------------------------
# 字段抽取（全部容错）
# ---------------------------------------------------------------------------


def _as_text(value) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", "replace")
    return None


def _as_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _iter_dicts(blocks: dict[str, list]):
    for name in ("Parameter", "About", "KKEx", "Custom", "Coordinate", "Status"):
        for obj in blocks.get(name, ()):
            if isinstance(obj, dict):
                yield name, obj
    for name, objs in blocks.items():
        if name in ("Parameter", "About", "KKEx", "Custom", "Coordinate", "Status"):
            continue
        for obj in objs:
            if isinstance(obj, dict):
                yield name, obj


def _extract_parameter(result: CharacterCardParseResult, blocks: dict[str, list]) -> None:
    for _name, obj in _iter_dicts({"Parameter": blocks.get("Parameter", [])}):
        if "lastname" not in obj and "firstname" not in obj:
            continue
        result.lastname = _as_text(obj.get("lastname"))
        result.firstname = _as_text(obj.get("firstname"))
        result.nickname = _as_text(obj.get("nickname"))
        result.personality = _as_int(obj.get("personality"))
        combined = f"{result.lastname or ''}{result.firstname or ''}".strip()
        result.name = combined or result.nickname
        return
    result.warnings.append("Parameter 块里没有找到角色名（lastname/firstname）")


def _extract_about(result: CharacterCardParseResult, blocks: dict[str, list]) -> None:
    # 实测差异：KKS 卡片有 About 块；KK（原版）卡片**根本没有 About 块**
    # （old_female 的 lstInfo 只有 Coordinate/Custom/KKEx/Parameter/Status）。
    # 「这个格式没有该块」不是解析失败，因此缺失时只留 None，不计入 warnings。
    if "About" not in blocks:
        return
    for _name, obj in _iter_dicts({"About": blocks.get("About", [])}):
        if "userID" not in obj and "dataID" not in obj:
            continue
        result.user_id = _as_text(obj.get("userID"))
        result.data_id = _as_text(obj.get("dataID"))
        return
    result.warnings.append("About 块存在但无法解码出 userID/dataID")


def _extract_kkex(
    result: CharacterCardParseResult, blocks: dict[str, list]
) -> dict | None:
    """解析 KKEx 插件表；返回插件字典（失败返回 None）。"""
    kkex: dict | None = None
    for obj in blocks.get("KKEx", ()):
        if isinstance(obj, dict):
            kkex = obj
            break
    if kkex is None:
        result.warnings.append("KKEx 块缺失或无法解码（插件与 MOD 依赖信息不可用）")
        return None

    result.plugin_guids = [str(k) for k in kkex]

    entry = kkex.get(MODLIST_PLUGIN_GUID)
    if entry is None:
        # 卡片没有 sideloader 键 = 该卡确实没有 MOD 依赖（实测如罗德尼）。
        # 这是正常状态，不是解析失败 —— 依赖列表留空即可。
        return kkex

    info: list = []
    if isinstance(entry, list):
        for part in entry:
            if isinstance(part, dict) and isinstance(part.get("info"), list):
                info = part["info"]
                break
    if not info and not isinstance(entry, list):
        result.warnings.append(f"{MODLIST_PLUGIN_GUID} 的数据结构不符合预期（非列表）")
        return kkex

    unique: list[str] = []
    undecodable = 0
    for raw in info:
        record = raw
        if isinstance(raw, (bytes, bytearray)):
            record, used = _first_object(bytes(raw))
            if record is None or used != len(raw):
                undecodable += 1
                continue
        if not isinstance(record, dict):
            undecodable += 1
            continue
        mod_id = _as_text(record.get("ModID")) or ""
        result.dependencies.append(
            ModDependencyRecord(
                mod_id=mod_id,
                property=_as_text(record.get("Property")) or "",
                slot=_as_int(record.get("Slot")),
                local_slot=_as_int(record.get("LocalSlot")),
                category_no=_as_int(record.get("CategoryNo")),
                author=_as_text(record.get("Author")),
                website=_as_text(record.get("Website")),
                name=_as_text(record.get("Name")),
            )
        )
        if mod_id and mod_id not in unique:
            unique.append(mod_id)

    result.unique_mod_guids = unique
    if undecodable:
        result.warnings.append(f"{undecodable} 条依赖记录无法解码（已跳过）")
    return kkex


def _decode_authors_payload(payload) -> list[str] | None:
    """把 ``marco.authordata`` 的 Authors 负载解成字符串列表；无法识别返回 None。

    实测负载是 **bytes**（内含一段 msgpack 列表），这里同时容忍直接给出列表的情况。
    """
    value = payload
    if isinstance(value, (bytes, bytearray)):
        value, used = _first_object(bytes(value))
        if value is None or used == 0:
            return None
    if isinstance(value, (list, tuple)):
        # 只保留字符串项；非字符串不猜测、不强行转换
        return [item for item in value if isinstance(item, str)]
    return None


def _extract_authors(
    result: CharacterCardParseResult, kkex: dict | None
) -> None:
    """从 ``KKEx["marco.authordata"]`` 读取作者。

    - 卡片**没有**这个键 → 正常情况（真实样本 22 张里有 10 张如此），不记 warning、不失败。
    - 结构损坏 → 只记 warning（按非关键 KKEx 数据的容错规则），不影响整卡主要结果。
    - 作者一律**从卡内读取**，绝不根据文件名 / 目录名推断。
    """
    if kkex is None:
        return
    entry = kkex.get(AUTHORS_PLUGIN_GUID)
    if entry is None:
        return

    payload = None
    if isinstance(entry, list) and len(entry) >= 2 and isinstance(entry[1], dict):
        payload = entry[1].get("Authors")
    elif isinstance(entry, dict):  # 容忍少见的直接字典形态
        payload = entry.get("Authors")

    decoded = _decode_authors_payload(payload)
    if decoded is None:
        result.warnings.append(
            f"{AUTHORS_PLUGIN_GUID} 的作者数据无法识别（已忽略，不影响其它字段）"
        )
        return

    real, _placeholders, raw = partition_authors(decoded)
    result.authors = real
    result.authors_raw = raw


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def parse_bytes(data: bytes, path_label: str = "<bytes>") -> CharacterCardParseResult:
    """解析内存中的卡片字节。synthetic / 损坏样本测试也走这里。"""
    result = CharacterCardParseResult(path=path_label)

    if not data.startswith(PNG_SIGNATURE):
        result.error = "不是 PNG 文件（缺少 PNG 签名）"
        return result

    chunks, png_end = read_png_chunks(data)
    if png_end is None:
        result.error = "PNG 结构不完整（未找到 IEND）"
        return result

    trailing = data[png_end:]
    if not trailing:
        result.error = "PNG 没有卡片尾部数据（不是 KKS/KK 卡片）"
        return result

    # ---- 容器头（关键结构，失败即整卡失败）----
    try:
        pos = 0
        result.product_no = _i32(trailing, pos)
        pos += 4
        raw_marker, pos = _read_dotnet_string(trailing, pos)
        result.card_marker_raw = raw_marker
        result.card_marker = raw_marker.strip("【】")
        result.card_version, pos = _read_dotnet_string(trailing, pos)

        face_len = _i32(trailing, pos)
        pos += 4
        if face_len < 0 or pos + face_len > len(trailing):
            raise ValueError(f"面部预览图长度越界：{face_len}")
        face = trailing[pos : pos + face_len]
        pos += face_len
        result.face_preview_size = face_len
        if face.startswith(PNG_SIGNATURE):
            result.face_preview_kind = "png"
        elif face.startswith(JPEG_SOI):
            result.face_preview_kind = "jpeg"
        else:
            result.face_preview_kind = "unknown"

        lst_len = _i32(trailing, pos)
        pos += 4
        if lst_len < 0 or pos + lst_len > len(trailing):
            raise ValueError(f"lstInfo 长度越界：{lst_len}")
        lst_obj = msgpack.unpackb(
            trailing[pos : pos + lst_len], raw=False, strict_map_key=False
        )
        pos += lst_len
        if not isinstance(lst_obj, dict) or not isinstance(lst_obj.get("lstInfo"), list):
            raise ValueError("lstInfo 结构不符合预期")

        region_len = _i32(trailing, pos)
        pos += 4
        result.file_level_reserved = _i32(trailing, pos)
        pos += 4
        if region_len < 0 or pos + region_len > len(trailing):
            raise ValueError(f"数据区长度越界：{region_len}")
        region = trailing[pos : pos + region_len]
    except Exception as exc:  # noqa: BLE001 - 关键结构损坏 → 单文件失败
        result.parse_status = PARSE_FAILED
        result.error = f"卡片容器解析失败：{type(exc).__name__}: {exc}"
        return result

    result.region_bytes = len(region)
    result.region_covers_to_eof = (pos + region_len) == len(trailing)

    # ---- 判定卡片类型（不归一化 marker）----
    if result.card_marker in CHARACTER_CARD_MARKERS:
        result.card_type = "character_card"
    else:
        result.warnings.append(f"未知卡片 marker：{result.card_marker!r}")

    # ---- lstInfo：必须按 pos 排序 ----
    entries: list[LstInfoEntry] = []
    for item in lst_obj["lstInfo"]:
        if not isinstance(item, dict):
            continue
        entries.append(
            LstInfoEntry(
                name=str(item.get("name", "")),
                version=str(item.get("version", "")),
                pos=_as_int(item.get("pos")) or 0,
                size=_as_int(item.get("size")) or 0,
            )
        )
    result.lst_info_reordered = [e.pos for e in entries] != sorted(e.pos for e in entries)
    entries.sort(key=lambda e: e.pos)
    result.lst_info = entries

    # ---- 逐块容错解码 ----
    blocks: dict[str, list] = {}
    for entry in entries:
        if not entry.name:
            continue
        segment = region[entry.pos : entry.pos + entry.size]
        if len(segment) != entry.size:
            result.warnings.append(
                f"数据块 {entry.name} 越界（声明 {entry.size} 字节，实际 {len(segment)} 字节）"
            )
        result.block_sizes[entry.name] = entry.size
        objects, warnings = decode_block(segment)
        blocks[entry.name] = objects
        for warning in warnings:
            result.warnings.append(f"数据块 {entry.name}：{warning}")

    # ---- 字段抽取（任一失败只记 warning）----
    def safe(label: str, func):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001 - 非关键块失败不影响整卡
            result.warnings.append(
                f"{label} 解析异常（已忽略）：{type(exc).__name__}: {exc}"
            )
            return None

    safe("Parameter", lambda: _extract_parameter(result, blocks))
    safe("About", lambda: _extract_about(result, blocks))
    kkex_obj = safe("KKEx", lambda: _extract_kkex(result, blocks))
    safe("作者信息", lambda: _extract_authors(result, kkex_obj))

    # ---- 内嵌贴图：只计数 ----
    result.embedded_texture_count = region.count(_EMBEDDED_PNG_SIGNATURE)

    result.parse_status = PARSE_PARTIAL if result.warnings else PARSE_OK
    if result.parse_status == PARSE_PARTIAL and not result.name:
        # 连角色名都没有，基本可以认定不是有效的 KKS/KK 角色卡尾部
        result.parse_status = PARSE_FAILED
        result.error = result.error or "未能从卡片中提取到任何角色信息"
    return result


def parse_card(path: str | Path) -> CharacterCardParseResult:
    """只读解析一个卡片文件。IO 失败也返回结果对象，不抛异常。"""
    target = Path(path)
    try:
        data = target.read_bytes()
    except OSError as exc:
        return CharacterCardParseResult(
            path=str(target), parse_status=PARSE_FAILED, error=f"读取失败：{exc}"
        )
    return parse_bytes(data, path_label=str(target))


__all__ = ["parse_card", "parse_bytes", "decode_block", "read_png_chunks"]
