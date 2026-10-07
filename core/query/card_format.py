"""卡片游戏格式（KK / KKS）映射 —— Phase 1.3-A 查询层。

``resources.card_marker`` 保存卡片容器头里的 marker（去掉外围的【】）。
实测取值：``KoiKatuCharaSun``（KKS）/ ``KoiKatuChara``（KK）。
marker **只描述格式、不是身份**：同一角色可以同时存在 KK 与 KKS 两个文件
（见 docs/phase1/SAMPLE_ANALYSIS.md 的 I 组样本）。

本模块把「游戏」与「marker 字符串」集中映射，避免查询层各处硬编码 marker 字面量。
"""

from __future__ import annotations

GAME_KKS = "KKS"
GAME_KK = "KK"

CARD_MARKER_KKS = "KoiKatuCharaSun"
CARD_MARKER_KK = "KoiKatuChara"

GAMES: tuple[str, ...] = (GAME_KKS, GAME_KK)

_MARKER_BY_GAME: dict[str, str] = {
    GAME_KKS: CARD_MARKER_KKS,
    GAME_KK: CARD_MARKER_KK,
}
_GAME_BY_MARKER: dict[str, str] = {
    CARD_MARKER_KKS: GAME_KKS,
    CARD_MARKER_KK: GAME_KK,
}


def card_marker_for_game(game: str) -> str:
    """把游戏名（KKS / KK，大小写不敏感）映射成 ``card_marker`` 取值。"""
    try:
        key = game.strip().upper()
    except AttributeError:
        raise ValueError(f"未知游戏格式：{game!r}（可选 {GAMES}）") from None
    if key not in _MARKER_BY_GAME:
        raise ValueError(f"未知游戏格式：{game!r}（可选 {GAMES}）")
    return _MARKER_BY_GAME[key]


def game_for_card_marker(marker: str | None) -> str | None:
    """把 ``card_marker`` 反查成游戏名；非卡片（如 zipmod 的 NULL）返回 ``None``。"""
    if not marker:
        return None
    return _GAME_BY_MARKER.get(marker.strip())


__all__ = [
    "GAME_KKS",
    "GAME_KK",
    "GAMES",
    "CARD_MARKER_KKS",
    "CARD_MARKER_KK",
    "card_marker_for_game",
    "game_for_card_marker",
]
