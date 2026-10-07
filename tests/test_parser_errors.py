"""Phase 1.2-B 验收：错误处理（synthetic malformed fixtures）。

核心要求：**单个文件解析失败只能影响该文件**，解析器永远返回结果对象，
绝不把异常抛给调用方（将来 Scanner 因此不会被一个坏文件带崩）。

合成样本只在内存 / 临时目录里构造，真实样本目录一个字节都不动。
"""

from __future__ import annotations

import struct
import sys
import zipfile
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.parsers import parse_bytes, parse_card, parse_zipmod  # noqa: E402
from core.parsers import zipmod as zipmod_mod  # noqa: E402


# ---------------------------------------------------------------------------
# 合成素材
# ---------------------------------------------------------------------------


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def make_plain_png() -> bytes:
    """一张结构合法、但**没有**卡片尾部数据的 PNG。"""
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    raw = b"\x00" + b"\xff\x00\x00\xff"
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


def make_card_tail(
    marker: str = "【KoiKatuCharaSun】",
    *,
    blocks: list[tuple[str, bytes]] | None = None,
    lst_len_override: int | None = None,
    region_len_override: int | None = None,
    region: bytes | None = None,
    product_no: int = 100,
) -> bytes:
    """手工拼一个卡片尾部（只测容器层与块层容错）。

    ``blocks`` 给出若干 ``(块名, 块字节)``，会按顺序拼成数据区并生成对应的 lstInfo；
    也可以直接用 ``region`` 指定原始数据区字节。
    """
    import msgpack

    entries = []
    if blocks:
        pos = 0
        chunks = []
        for name, payload in blocks:
            entries.append(
                {"name": name, "version": "0.0.0", "pos": pos, "size": len(payload)}
            )
            pos += len(payload)
            chunks.append(payload)
        if region is None:
            region = b"".join(chunks)
    if region is None:
        region = b""
    if not entries and region:
        entries = [{"name": "Parameter", "version": "0.0.0", "pos": 0, "size": len(region)}]
    if not entries:
        entries = [{"name": "Parameter", "version": "0.0.0", "pos": 0, "size": 0}]

    lst = msgpack.packb({"lstInfo": entries})
    out = struct.pack("<i", product_no)
    out += bytes([len(marker.encode())]) + marker.encode()
    version = "0.0.0"
    out += bytes([len(version)]) + version.encode()
    face = b"\xff\xd8\xff\xe0" + b"\x00" * 16
    out += struct.pack("<i", len(face)) + face
    out += struct.pack("<i", lst_len_override if lst_len_override is not None else len(lst))
    out += lst
    out += struct.pack("<i", region_len_override if region_len_override is not None else len(region))
    out += struct.pack("<i", 0)  # file-level reserved
    out += region
    return out


def make_valid_card_bytes() -> bytes:
    """一张能被解析器接受的合成卡片（自带一段可解码的 Parameter 块）。"""
    return make_plain_png() + make_card_tail(blocks=[("Parameter", _param_frame())])


def _param_frame(
    lastname: str = "測試", firstname: str = "角色", personality: int = 1
) -> bytes:
    """构造一个 ``[int32 长度][msgpack]`` 形态的 Parameter 块。"""
    import msgpack

    payload = msgpack.packb(
        {
            "version": "0.0.6",
            "lastname": lastname,
            "firstname": firstname,
            "nickname": lastname,
            "personality": personality,
        }
    )
    return struct.pack("<i", len(payload)) + payload


# ---------------------------------------------------------------------------
# 卡片：错误输入
# ---------------------------------------------------------------------------


def test_non_png_bytes_fail_cleanly():
    result = parse_bytes(b"this is definitely not a png", "not-a-png.png")
    assert result.parse_status == "failed"
    assert result.success is False
    assert "PNG" in (result.error or "")


def test_plain_png_without_card_tail_fails_cleanly():
    result = parse_bytes(make_plain_png(), "plain.png")
    assert result.parse_status == "failed"
    assert result.error is not None
    assert "尾部" in result.error


def test_truncated_png_fails_cleanly():
    data = make_valid_card_bytes()
    result = parse_bytes(data[: len(data) // 2], "truncated.png")
    assert result.parse_status == "failed"
    assert result.error


def test_truncated_card_tail_fails_cleanly():
    """尾部被截断（数据区长度超出实际剩余字节）。"""
    data = make_plain_png() + make_card_tail(region=b"\x81\xa1a\x01")
    result = parse_bytes(data[:-2], "truncated-tail.png")
    assert result.parse_status == "failed"
    assert "越界" in (result.error or "") or "解析失败" in (result.error or "")


def test_broken_lst_info_fails_cleanly():
    """lstInfo 长度被改坏 → 单文件失败，但绝不抛异常。"""
    data = make_plain_png() + make_card_tail(region=b"", lst_len_override=99999)
    result = parse_bytes(data, "bad-lstinfo.png")
    assert result.parse_status == "failed"
    assert result.error


def test_broken_region_length_fails_cleanly():
    data = make_plain_png() + make_card_tail(region=b"", region_len_override=10**6)
    result = parse_bytes(data, "bad-region.png")
    assert result.parse_status == "failed"
    assert result.error


def test_broken_noncritical_block_does_not_fail_whole_card():
    """关键块（Parameter）正常、另一个块是垃圾 → 整卡仍应解析成功。

    这正对应真实场景：``Custom`` / ``Coordinate`` 里混有嵌套 binary 帧，
    某个块解不动时不能把整张卡判死。
    """
    junk = b"\xc1" * 64  # 0xc1 是 msgpack 保留字节，必定解不动
    data = make_plain_png() + make_card_tail(
        blocks=[("Parameter", _param_frame("測試", "角色")), ("Coordinate", junk)]
    )
    result = parse_bytes(data, "junk-block.png")

    assert result.success, f"非关键块损坏不应导致整卡失败：{result.error}"
    assert result.name == "測試角色"
    assert result.card_marker == "KoiKatuCharaSun"
    assert any("Coordinate" in w for w in result.warnings), "损坏块必须留下 warning"


def test_unknown_marker_is_partial_not_silently_normalized():
    import msgpack

    param = msgpack.packb({"lastname": "X", "firstname": "Y"})
    frame = struct.pack("<i", len(param)) + param
    data = make_plain_png() + make_card_tail(marker="【KoiKatuCoordinate】", region=frame)
    result = parse_bytes(data, "coordinate-card.png")

    assert result.card_marker == "KoiKatuCoordinate"
    assert result.card_type is None
    assert result.parse_status == "partial"
    assert any("marker" in w for w in result.warnings)


def test_missing_file_returns_result_not_exception(tmp_path: Path):
    result = parse_card(tmp_path / "does-not-exist.png")
    assert result.parse_status == "failed"
    assert result.error


def test_parsing_many_bad_files_never_raises(tmp_path: Path):
    """把一堆坏文件丢给解析器：逐个返回结果，整体不崩。"""
    samples = {
        "empty.png": b"",
        "text.png": b"not a png at all",
        "half.png": make_plain_png()[:20],
        "plain.png": make_plain_png(),
        "bad_lst.png": make_plain_png() + make_card_tail(lst_len_override=10**6),
        "bad_region.png": make_plain_png() + make_card_tail(region_len_override=10**6),
        "truncated.png": make_valid_card_bytes()[:40],
    }
    for name, payload in samples.items():
        (tmp_path / name).write_bytes(payload)

    results = [parse_card(tmp_path / name) for name in samples]
    assert len(results) == len(samples)
    assert all(r.parse_status in ("ok", "partial", "failed") for r in results)
    # 至少「合法但无卡片尾部」这条要能给出明确原因
    plain = next(r for r in results if r.path.endswith("plain.png"))
    assert plain.parse_status == "failed" and plain.error


# ---------------------------------------------------------------------------
# ZIPMOD：错误输入
# ---------------------------------------------------------------------------


def test_corrupt_zip_fails_cleanly(tmp_path: Path):
    path = tmp_path / "corrupt.zipmod"
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 40 + b"garbage")
    result = parse_zipmod(path)
    assert result.parse_status == "failed"
    assert result.is_zipmod is False
    assert result.error


def test_non_zip_file_fails_cleanly(tmp_path: Path):
    path = tmp_path / "not-a-zip.zipmod"
    path.write_bytes(b"hello world")
    result = parse_zipmod(path)
    assert result.parse_status == "failed"
    assert result.error


def test_zip_without_manifest_is_not_a_zipmod(tmp_path: Path):
    path = tmp_path / "no-manifest.zipmod"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("readme.txt", "hello")
    result = parse_zipmod(path)
    assert result.parse_status == "failed"
    assert result.is_zipmod is False
    assert "manifest.xml" in (result.error or "")


def test_broken_manifest_xml_fails_cleanly(tmp_path: Path):
    path = tmp_path / "broken-manifest.zipmod"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.xml", "<manifest><guid>unterminated")
    result = parse_zipmod(path)
    assert result.parse_status == "failed"
    assert result.is_zipmod is True  # manifest 存在，但内容坏了
    assert "XML" in (result.error or "")


def test_manifest_without_guid_is_partial(tmp_path: Path):
    path = tmp_path / "no-guid.zipmod"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.xml", "<manifest><name>No GUID</name></manifest>")
    result = parse_zipmod(path)
    assert result.parse_status == "partial"
    assert result.guid is None
    assert any("guid" in w for w in result.warnings)


def test_manifest_attribute_style_is_supported(tmp_path: Path):
    path = tmp_path / "attr-style.zipmod"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "manifest.xml",
            '<manifest guid="com.example.attr" name="Attr" author="Me" version="2.0" />',
        )
    result = parse_zipmod(path)
    assert result.parse_status == "ok"
    assert result.guid == "com.example.attr"
    assert result.name == "Attr"
    assert result.author == "Me"
    assert result.version == "2.0"


def test_manifest_in_subdirectory_is_found(tmp_path: Path):
    path = tmp_path / "nested.zipmod"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("sub/manifest.xml", "<manifest><guid>com.example.nested</guid></manifest>")
    result = parse_zipmod(path)
    assert result.parse_status == "ok"
    assert result.guid == "com.example.nested"
    assert result.manifest_entry == "sub/manifest.xml"


def test_missing_zipmod_file_returns_result_not_exception(tmp_path: Path):
    result = parse_zipmod(tmp_path / "nope.zipmod")
    assert result.parse_status == "failed"
    assert result.error


def test_encrypted_manifest_fails_cleanly(tmp_path: Path):
    """加密 ZIP：zipfile 会抛 RuntimeError，解析器必须转成明确错误。"""
    path = tmp_path / "encrypted.zipmod"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.xml", "<manifest><guid>com.example.enc</guid></manifest>")

    # 直接构造一个「读 manifest 时抛 RuntimeError」的假 ZipFile
    class _FakeZipFile:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def namelist(self):
            return ["manifest.xml"]

        def read(self, _name):
            raise RuntimeError("File 'manifest.xml' is encrypted, password required")

    original = zipmod_mod.zipfile.ZipFile
    zipmod_mod.zipfile.ZipFile = _FakeZipFile  # type: ignore[assignment]
    try:
        result = zipmod_mod._parse_stream(None, "encrypted.zipmod")
    finally:
        zipmod_mod.zipfile.ZipFile = original  # type: ignore[assignment]

    assert result.parse_status == "failed"
    assert "加密" in (result.error or "")


def test_parsing_many_bad_zipmods_never_raises(tmp_path: Path):
    (tmp_path / "a.zipmod").write_bytes(b"not a zip")
    (tmp_path / "b.zipmod").write_bytes(b"")
    with zipfile.ZipFile(tmp_path / "c.zipmod", "w") as zf:
        zf.writestr("x.txt", "x")
    with zipfile.ZipFile(tmp_path / "d.zipmod", "w") as zf:
        zf.writestr("manifest.xml", "not xml at all <<<")

    results = [parse_zipmod(p) for p in sorted(tmp_path.iterdir())]
    assert len(results) == 4
    assert all(r.parse_status == "failed" for r in results)
    assert all(r.error for r in results)
