"""Phase 3.1 Step 3 —— effective display name 的 core 权威实现与 UI 委托。

依据：`docs/phase3/PHASE3_1_IMPLEMENTATION_CONTRACT.md` §4 / §7 Step 3 / §8。

覆盖：
- ``ResourceSummary.effective_display_name`` 的业务定义（含 ``==name`` 仍是 override、
  历史空白字符串按「无 override」处理）；
- ``ResourceSummary.title`` 的展示回退链（effective → relative 文件名 → file_path）；
- UI ``display_title`` 与 core 对同一资源结果完全一致（UI 不再自带 fallback chain）。
"""

from __future__ import annotations

import pytest

from core.query import ResourceSummary
from ui.resource_model import display_title


def _summary(**overrides) -> ResourceSummary:
    base = dict(
        id=1,
        resource_type="character_card",
        name=None,
        display_name=None,
        file_path="D:/x/y/z.png",
        relative_path="a\\b\\c.png",
        extension=".png",
        card_marker=None,
        file_size=None,
        modified_time=None,
        library_id=None,
        scan_status="present",
        parse_status="ok",
        needs_review=False,
    )
    base.update(overrides)
    return ResourceSummary(**base)


# ---------------------------------------------------------------------------
# effective_display_name（业务定义）
# ---------------------------------------------------------------------------


def test_effective_display_name_uses_non_null_override():
    assert _summary(name="Alice", display_name="Custom").effective_display_name == "Custom"


def test_effective_display_name_equal_to_name_is_still_override():
    """``display_name == name`` 仍是有效 override（不得用相等性判断）。"""
    summary = _summary(name="Alice", display_name="Alice")
    assert summary.display_name is not None
    assert summary.effective_display_name == "Alice"
    assert summary.title == "Alice"


def test_effective_display_name_falls_back_to_name_when_null():
    assert _summary(name="Alice", display_name=None).effective_display_name == "Alice"


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n  "])
def test_effective_display_name_treats_historical_blank_as_no_override(blank):
    """历史遗留的空白 display_name 读取时视为没有 override（不迁移）。"""
    assert _summary(name="Alice", display_name=blank).effective_display_name == "Alice"


def test_effective_display_name_is_none_when_both_missing():
    assert _summary(name=None, display_name=None).effective_display_name is None


# ---------------------------------------------------------------------------
# title（展示回退链）
# ---------------------------------------------------------------------------


def test_title_prefers_effective_display_name():
    assert _summary(name="N", display_name="D").title == "D"


def test_title_falls_back_to_name():
    assert _summary(name="N", display_name=None).title == "N"


def test_title_falls_back_to_relative_path_filename():
    summary = _summary(name=None, display_name=None, relative_path="a\\b\\c.png")
    assert summary.title == "c.png"


def test_title_falls_back_to_file_path():
    summary = _summary(name=None, display_name=None, relative_path=None)
    assert summary.title == "D:/x/y/z.png"


def test_title_handle_both_name_and_display_name_blank():
    summary = _summary(name="", display_name="  ", relative_path="a\\b\\c.png")
    assert summary.effective_display_name == ""
    assert summary.title == "c.png"


# ---------------------------------------------------------------------------
# UI 与 Core 一致
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "N", "display_name": "D"},
        {"name": "Alice", "display_name": "Alice"},
        {"name": "N", "display_name": None},
        {"name": "N", "display_name": ""},
        {"name": "N", "display_name": "   "},
        {"name": None, "display_name": None},
        {"name": "", "display_name": ""},
        {"name": None, "display_name": None, "relative_path": None},
        {"name": None, "display_name": "D", "relative_path": None},
    ],
)
def test_ui_display_title_matches_core(overrides):
    """UI 与 core 对同一资源必须得到完全一致的 effective display name / 标题。"""
    summary = _summary(**overrides)
    assert display_title(summary) == summary.title
