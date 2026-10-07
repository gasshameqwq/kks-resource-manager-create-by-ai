"""文件字节哈希工具 —— Phase 2.1（Content Identity）。

只对**文件原始字节**做 SHA-256（不掺入 path / name / metadata / dataID），
流式分块读取，返回 **64 位小写十六进制**字符串。

约束
----
- **只读**：只 ``open(path, "rb")``，绝不写回 / 移动 / 重命名 / 删除文件。
- **不做类型判断**：本模块只算哈希，不解析文件内容。
- **不吞异常**：``OSError``（文件消失 / 无权限等）原样抛给调用方，
  由 Scanner 按既有 IO 失败语义处理。

参考：``docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md`` §5（Content Identity）、
§13.3（C1–C8 不变式）。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# 分块大小：沿用 ``tests/conftest.py`` 的 1 MiB 约定，避免整文件驻留内存。
_DEFAULT_CHUNK_SIZE = 1 << 20


def sha256_of_file(
    path: str | Path, *, chunk_size: int = _DEFAULT_CHUNK_SIZE
) -> str:
    """返回 ``path`` 所指文件原始字节的 SHA-256（64 位小写十六进制）。"""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


__all__ = ["sha256_of_file"]
