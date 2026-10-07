"""合成样本构造器（只在内存 / 临时目录里使用，绝不碰真实样本目录）。

用于 Scanner 的 synthetic tests：造出结构合法但内容可控的卡片与 zipmod。
"""

from __future__ import annotations

import struct
import zipfile
import zlib
from pathlib import Path

import msgpack

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SOI = b"\xff\xd8\xff\xe0"
MODLIST_PLUGIN = "com.bepis.sideloader.universalautoresolver"

MARKER_SUN = "【KoiKatuCharaSun】"
MARKER_KK = "【KoiKatuChara】"


# ---------------------------------------------------------------------------
# PNG
# ---------------------------------------------------------------------------


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def tiny_png() -> bytes:
    """一张最小的合法 PNG（1×1）。"""
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    raw = b"\x00" + b"\xff\x00\x00\xff"
    return (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


def write_plain_png(path: Path) -> Path:
    """普通 PNG：结构合法，但**没有**卡片尾部数据。"""
    path.write_bytes(tiny_png())
    return path


def write_broken_png(path: Path) -> Path:
    """损坏的 PNG：签名对，但块结构不完整。"""
    path.write_bytes(PNG_SIGNATURE + b"\x00\x00\x00\x0dIHDR" + b"junk")
    return path


# ---------------------------------------------------------------------------
# 卡片
# ---------------------------------------------------------------------------


def _short_string(text: str) -> bytes:
    payload = text.encode("utf-8")
    return bytes([len(payload)]) + payload


def _frame(payload: bytes) -> bytes:
    """``[int32 长度][msgpack]`` 形态的块（真实样本的 Custom 块就是这样）。"""
    return struct.pack("<i", len(payload)) + payload


def build_card_bytes(
    *,
    lastname: str = "測試",
    firstname: str = "角色",
    marker: str = MARKER_SUN,
    user_id: str | None = "11111111-1111-1111-1111-111111111111",
    data_id: str | None = "22222222-2222-2222-2222-222222222222",
    plugin_guids: tuple[str, ...] = ("moreAccessories",),
    dependencies: tuple[tuple[str, str, int | None], ...] = (),
    authors: tuple[str, ...] | None = None,
    broken_authors: bool = False,
    embedded_pngs: int = 0,
    product_no: int = 100,
) -> bytes:
    """构造一张结构合法的卡片字节。

    - ``user_id=None`` 时**不生成 About 块**（模拟 KK 卡片）。
    - ``dependencies`` 是 ``(mod_guid, property, slot)`` 三元组列表。
    - ``authors=None`` 时**不生成** `marco.authordata`（模拟没有作者数据的卡）；
      给了列表就按真实结构 ``[版本, {"Authors": <msgpack bytes>}]`` 写入。
    - ``broken_authors=True`` 时写入一份无法解码的作者负载（用于容错测试）。
    - ``embedded_pngs`` 决定数据区里塞几张 PNG（用于内嵌贴图计数）。
    """
    blocks: list[tuple[str, bytes]] = []

    parameter = msgpack.packb(
        {
            "version": "0.0.6",
            "lastname": lastname,
            "firstname": firstname,
            "nickname": lastname,
            "personality": 8,
        }
    )
    blocks.append(("Parameter", _frame(parameter)))

    if user_id is not None:
        about = msgpack.packb(
            {
                "version": "0.0.0",
                "language": 0,
                "userID": user_id,
                "dataID": data_id,
                "ExtendedSaveData": None,
            }
        )
        blocks.append(("About", about))

    coordinate = msgpack.packb(
        {
            "version": "0.0.0",
            "textures": tiny_png() * embedded_pngs,
        }
    )
    blocks.append(("Coordinate", coordinate))

    records = [
        msgpack.packb(
            {
                "ModID": mod_guid,
                "Slot": slot,
                "LocalSlot": slot,
                "Property": prop,
                "CategoryNo": 0,
                "Author": None,
                "Website": None,
                "Name": None,
            }
        )
        for mod_guid, prop, slot in dependencies
    ]
    kkex: dict = {MODLIST_PLUGIN: [0, {"info": records}]}
    for guid in plugin_guids:
        kkex[guid] = [0, {}]
    if broken_authors:
        kkex["marco.authordata"] = [1, {"Authors": b"\xc1\xc1\xc1"}]
    elif authors is not None:
        kkex["marco.authordata"] = [1, {"Authors": msgpack.packb(list(authors))}]
    blocks.append(("KKEx", msgpack.packb(kkex)))

    region = b""
    entries = []
    for name, payload in blocks:
        entries.append(
            {"name": name, "version": "0.0.0", "pos": len(region), "size": len(payload)}
        )
        region += payload
    lst = msgpack.packb({"lstInfo": entries})

    face = JPEG_SOI + b"\x00" * 16
    tail = struct.pack("<i", product_no)
    tail += _short_string(marker)
    tail += _short_string("0.0.0")
    tail += struct.pack("<i", len(face)) + face
    tail += struct.pack("<i", len(lst)) + lst
    tail += struct.pack("<i", len(region))
    tail += struct.pack("<i", 0)  # file-level reserved
    tail += region
    return tiny_png() + tail


def write_card(path: Path, **kwargs) -> Path:
    path.write_bytes(build_card_bytes(**kwargs))
    return path


# ---------------------------------------------------------------------------
# ZIPMOD
# ---------------------------------------------------------------------------


def manifest_xml(guid: str, name: str = "Test Mod", author: str = "Tester",
                 version: str = "1.0", website: str | None = None) -> str:
    parts = [f"<guid>{guid}</guid>", f"<name>{name}</name>",
             f"<author>{author}</author>", f"<version>{version}</version>"]
    if website:
        parts.append(f"<website>{website}</website>")
    return "<manifest>" + "".join(parts) + "</manifest>"


def write_zipmod(path: Path, guid: str, **kwargs) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.xml", manifest_xml(guid, **kwargs))
        zf.writestr("abdata/list.txt", "dummy")
    return path


def write_zip_without_manifest(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("readme.txt", "just a zip")
    return path


def write_broken_zip(path: Path) -> Path:
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 32 + b"not really a zip")
    return path
