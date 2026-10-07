"""资源解析层 —— Phase 1.2-B：只读 Parser（**不含 Scanner / 入库 / UI**）。

已实现
------
- ``card.py``：KKS/KK 角色卡（PNG + MessagePack 尾部）只读解析。
- ``zipmod.py``：ZIPMOD（``manifest.xml``）只读解析。
- ``models.py``：结构化结果 dataclass（``CharacterCardParseResult`` /
  ``ZipmodParseResult``）。

硬性约束
--------
- **只读**：只打开文件读字节，绝不写回、移动、重命名、删除。
- **不做类型推断**：不判断 eyes / skin / hair / clothes，也不做高 ID 来源启发式。
- 失败只影响单个文件：所有入口都返回结果对象，不把异常抛给调用方。

参考：``docs/phase1/SAMPLE_ANALYSIS.md``（22 张真实卡 + 13 个 zipmod 的实测结论）。

尚未实现（后续阶段）
--------------------
- ``scene_card``：场景卡内嵌角色与场景级依赖（Phase 2）。
- Scanner / 数据库入库（Phase 1.2-C）。
"""

from core.parsers.card import decode_block, parse_bytes, parse_card, read_png_chunks
from core.parsers.models import (
    CHARACTER_CARD_MARKERS,
    MODLIST_PLUGIN_GUID,
    PARSE_FAILED,
    PARSE_OK,
    PARSE_PARTIAL,
    CharacterCardParseResult,
    LstInfoEntry,
    ModDependencyRecord,
    ZipmodParseResult,
)
from core.parsers.zipmod import (
    find_manifest_entry,
    parse_manifest_xml,
    parse_zipmod,
)

__all__ = [
    # 模型
    "CharacterCardParseResult",
    "ZipmodParseResult",
    "ModDependencyRecord",
    "LstInfoEntry",
    "PARSE_OK",
    "PARSE_PARTIAL",
    "PARSE_FAILED",
    "CHARACTER_CARD_MARKERS",
    "MODLIST_PLUGIN_GUID",
    # 卡片
    "parse_card",
    "parse_bytes",
    "decode_block",
    "read_png_chunks",
    # zipmod
    "parse_zipmod",
    "parse_manifest_xml",
    "find_manifest_entry",
]
