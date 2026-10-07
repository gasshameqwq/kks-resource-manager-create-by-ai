"""真实样本夹具。

Phase 1.2-B 的验收测试必须跑在**真实样本**上（见 docs/phase1/SAMPLE_ANALYSIS.md 与
docs/phase1/PHASE1_2_REPORT.md）。样本目录不在仓库里，因此：

- 默认路径为下面的 ``DEFAULT_SAMPLE_ROOT``；
- 可用环境变量 ``KKS_RM_SAMPLE_DIR`` 覆盖；
- 目录不存在时相关测试 **skip 并给出明确原因**（不会假装通过）。

``sample_root`` 夹具还会在**会话开始时记录全部文件的 sha256**、结束时再算一次并断言
完全一致 —— 这是「Parser 只读、绝不修改真实样本」的自动化证据。
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

DEFAULT_SAMPLE_ROOT = Path(
    r"G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike"
)

_CHUNK = 1 << 20


def sample_dir() -> Path:
    return Path(os.environ.get("KKS_RM_SAMPLE_DIR", str(DEFAULT_SAMPLE_ROOT)))


def hash_tree(root: Path) -> dict[str, str]:
    """对目录下每个文件做 sha256（只读）。"""
    digests: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        h = hashlib.sha256()
        with path.open("rb") as fh:
            while True:
                block = fh.read(_CHUNK)
                if not block:
                    break
                h.update(block)
        digests[path.relative_to(root).as_posix()] = h.hexdigest()
    return digests


@pytest.fixture(scope="session")
def sample_root() -> Path:
    root = sample_dir()
    if not root.is_dir():
        pytest.skip(
            f"真实样本目录不存在：{root}"
            "（可用环境变量 KKS_RM_SAMPLE_DIR 指定）"
        )

    before = hash_tree(root)
    yield root
    after = hash_tree(root)

    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    assert not (added or removed or changed), (
        "真实样本目录在测试期间被修改！"
        f" 新增={added} 删除={removed} 内容变化={changed}"
    )


@pytest.fixture(scope="session")
def sample_files(sample_root: Path) -> dict[str, list[Path]]:
    """按扩展名把样本文件分组。"""
    return {
        "cards": sorted(sample_root.rglob("*.png")),
        "zipmods": sorted(sample_root.rglob("*.zipmod")),
    }
