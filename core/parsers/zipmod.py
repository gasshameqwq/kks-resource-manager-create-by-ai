"""只读 ZIPMOD 解析器。

判定规则（依据真实样本，见 docs/phase1/SAMPLE_ANALYSIS.md）
---------------------------------------------------
- **只认「ZIP 内存在 manifest.xml」的文件是 ZIPMOD**。扩展名只用来找候选，
  不作为判定依据；文件名/目录名完全不参与类型判断。
- 只提取 manifest 里**已确认可靠**的字段：guid / name / author / version / website。
- **不解析** zipmod 内部资源文件（属 Phase 2）。
- 损坏 ZIP、缺 manifest、manifest 无法解析、加密 ZIP —— 全部返回明确的
  ``parse_status`` + ``error``，**绝不抛异常**。
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from core.parsers.models import (
    PARSE_FAILED,
    PARSE_OK,
    PARSE_PARTIAL,
    ZipmodParseResult,
)

MANIFEST_FILENAME = "manifest.xml"

# manifest 里我们只认这些字段（其余一律忽略，避免把不可靠信息写进库）
_MANIFEST_FIELDS = ("guid", "name", "author", "version", "website")


def find_manifest_entry(names: list[str]) -> str | None:
    """在压缩包条目里找 manifest.xml（优先根目录）。"""
    candidates = [n for n in names if Path(n).name.lower() == MANIFEST_FILENAME]
    if not candidates:
        return None
    root = [n for n in candidates if "/" not in n and "\\" not in n]
    return (root or candidates)[0]


def parse_manifest_xml(raw: bytes) -> dict[str, str]:
    """解析 manifest.xml，返回已确认字段。XML 非法时抛 ``ElementTree.ParseError``。

    同时支持两种写法（真实样本里两种都存在）::

        <manifest guid="..." name="..." />     <- 属性式
        <manifest><guid>...</guid></manifest>  <- 子元素式
    """
    root = ElementTree.fromstring(raw)  # 失败由调用方处理
    fields: dict[str, str] = {}

    # 注意：标签「存在但为空」与「不存在」是两件事 ——
    # 实测 NoHair.zipmod 的 author 就是空标签，必须原样保留成 ""（而不是 None）。
    for tag in _MANIFEST_FIELDS:
        value = root.get(tag)
        if value is not None:
            fields[tag] = value.strip()

    for node in root.iter():
        tag = str(node.tag).split("}")[-1].lower()  # 去掉 XML 命名空间
        if tag in _MANIFEST_FIELDS and tag not in fields:
            fields[tag] = (node.text or "").strip()
    return fields


def parse_bytes(raw: bytes, path_label: str = "<bytes>") -> ZipmodParseResult:
    """解析内存中的 ZIP 字节（synthetic / 损坏样本测试用）。"""
    import io

    return _parse_stream(io.BytesIO(raw), path_label)


def _parse_stream(stream, path_label: str) -> ZipmodParseResult:
    result = ZipmodParseResult(path=path_label)
    try:
        zf = zipfile.ZipFile(stream)
    except zipfile.BadZipFile as exc:
        result.error = f"不是合法的 ZIP 文件：{exc}"
        return result
    except OSError as exc:
        result.error = f"读取 ZIP 失败：{exc}"
        return result
    except Exception as exc:  # noqa: BLE001 - 任何意外都不许崩
        result.error = f"打开 ZIP 失败：{type(exc).__name__}: {exc}"
        return result

    with zf:
        try:
            names = zf.namelist()
        except Exception as exc:  # noqa: BLE001
            result.error = f"读取 ZIP 条目失败：{type(exc).__name__}: {exc}"
            return result

        manifest_entry = find_manifest_entry(names)
        if manifest_entry is None:
            result.error = "ZIP 内没有 manifest.xml（不认定为 ZIPMOD）"
            return result

        result.is_zipmod = True
        result.manifest_entry = manifest_entry

        try:
            raw = zf.read(manifest_entry)
        except RuntimeError as exc:
            # zipfile 对加密条目会抛 RuntimeError("File ... is encrypted")
            result.error = f"manifest.xml 无法读取（可能被加密）：{exc}"
            return result
        except Exception as exc:  # noqa: BLE001
            result.error = f"manifest.xml 读取失败：{type(exc).__name__}: {exc}"
            return result

    try:
        fields = parse_manifest_xml(raw)
    except ElementTree.ParseError as exc:
        result.error = f"manifest.xml 不是合法 XML：{exc}"
        return result
    except Exception as exc:  # noqa: BLE001
        result.error = f"manifest.xml 解析失败：{type(exc).__name__}: {exc}"
        return result

    result.guid = fields.get("guid")
    result.name = fields.get("name")
    result.author = fields.get("author")
    result.version = fields.get("version")
    result.website = fields.get("website")

    if not result.guid:
        result.warnings.append("manifest.xml 里没有 guid（无法作为 MOD 唯一键）")
        result.parse_status = PARSE_PARTIAL
        return result

    result.parse_status = PARSE_OK
    return result


def parse_zipmod(path: str | Path) -> ZipmodParseResult:
    """只读解析一个 zipmod 文件。IO 失败也返回结果对象，不抛异常。"""
    target = Path(path)
    try:
        with target.open("rb") as fh:
            return _parse_stream(fh, str(target))
    except OSError as exc:
        return ZipmodParseResult(
            path=str(target), parse_status=PARSE_FAILED, error=f"读取失败：{exc}"
        )


__all__ = [
    "MANIFEST_FILENAME",
    "find_manifest_entry",
    "parse_manifest_xml",
    "parse_bytes",
    "parse_zipmod",
]
