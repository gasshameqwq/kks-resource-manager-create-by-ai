"""PreviewService —— Phase 1.3-C-1：派生缩略图缓存。

定位
----
Preview 是**可丢弃的派生数据**（disposable derived data），不是资源事实、不是资源身份：

    GUI / caller ─► PreviewService ─► data/thumbnail_cache/<cache_key>.webp

因此本模块：

- **只读源文件**（``Image.open``），绝不写回 / 移动原始资源；
- **绝不写数据库**（不接受 sqlite 连接、不执行 SQL）；删掉整个 cache 不影响库；
- 只依赖 Pillow 与项目现有的路径归一化（``core.database.db.normalize_path_key``）；
- 不调用解析器 / 扫描器，不解析卡片内部结构，不提取内嵌图片。

本阶段唯一的 preview 来源
------------------------
**角色卡的主 PNG 文件本身**（PNG 数据流到 ``IEND`` 结束，其后的卡片尾部字节被 Pillow 忽略）。
``.zipmod`` / 非图片资源 / 非 character_card 资源一律 ``unsupported``——
即使 zipmod 包内恰好有图片，本阶段也不提取。

cache key
---------
``sha256(file_path_key + "\\n" + size + "\\n" + mtime)[:32]``

> 这是 **filesystem-state cache key**，**不是 content identity**：它只描述
> 「某个路径、某个大小、某个修改时间」的当前状态；不使用资源 id / dataID / 名称 / 作者，
> 也不读取文件内容做 content hash。
"""

from __future__ import annotations

import hashlib
import os
import stat as stat_module
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from core import app_paths
from core.database import db as database

# ---- preview 状态 -----------------------------------------------------------

PREVIEW_UNSUPPORTED = "unsupported"  # 该类型/来源没有实现 preview（zipmod、非 character_card…）
PREVIEW_MISSING = "missing"          # 源文件不存在 / 不是普通文件（或 cache 尚未生成）
PREVIEW_READY = "ready"              # cache 存在且通过图片有效性检查
PREVIEW_FAILED = "failed"            # 支持，但读取/解码/生成失败（**不落库、不留永久记录**）

# ---- 支持的来源 -------------------------------------------------------------

# 本阶段唯一支持的资源类型（提供 resource_type 时按类型判断）。
SUPPORTED_RESOURCE_TYPES: tuple[str, ...] = ("character_card",)
# 本阶段唯一支持的源文件扩展名（只给路径、无法判断类型时按扩展名判断）。
SUPPORTED_EXTENSIONS: tuple[str, ...] = (".png",)

# ---- 生成参数 ---------------------------------------------------------------

# 缩略图最大边（保持纵横比，**不放大**低分辨率图）。项目此前未规定尺寸，
# 这里取一个明确、简单的默认值：最长边 ≤ 256px。
DEFAULT_MAX_SIZE: tuple[int, int] = (256, 256)
DEFAULT_WEBP_QUALITY = 90

# 源文件读取/解码可能抛出的错误（IO、损坏、截断、解码炸弹…）。
# 只把这些「坏文件」类错误转成 ``failed``；真正的编程错误（如 TypeError）照常抛出。
_SOURCE_ERRORS: tuple[type[BaseException], ...] = (
    OSError,                       # 读取失败 / 权限 / 截断（含 PIL.UnidentifiedImageError）
    ValueError,                    # 部分解码路径
    SyntaxError,                   # 个别格式的解码错误
    Image.DecompressionBombError,  # 解压炸弹保护
)


def preview_cache_key(file_path_key: str, size: int, mtime: float) -> str:
    """filesystem-state cache key（**不是** content identity）。

    输入是「归一化路径 + 当前文件大小 + 当前 mtime」：
    size/mtime 变化 → key 变化 → 自然失效。不使用资源 id，也不读取文件内容。
    """
    payload = f"{file_path_key}\n{int(size)}\n{float(mtime)!r}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class PreviewStatus:
    """一次 preview 查询/生成的结果。

    ``state`` 取 ``unsupported`` / ``missing`` / ``ready`` / ``failed``。
    ``failed`` 只是本次调用的 transient result，**不会被持久化**（下次仍可重试）。
    """

    state: str
    cache_key: str | None = None
    path: Path | None = None
    reason: str | None = None

    @property
    def is_ready(self) -> bool:
        return self.state == PREVIEW_READY

    @property
    def is_supported(self) -> bool:
        return self.state != PREVIEW_UNSUPPORTED


class PreviewService:
    """把角色卡主 PNG 渲染成 ``data/thumbnail_cache/<cache_key>.webp``。

    ``source`` 可以是：

    - 文件路径（``str`` / ``Path``）；或
    - 任何带 ``file_path`` 属性的对象（如 Query Layer 的 ``ResourceSummary``，
      可选 ``extension`` / ``resource_type`` 字段）。

    本类**不接收数据库连接**，结构上保证不写 SQLite，也不触碰资源表里的缩略图列。
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        *,
        max_size: tuple[int, int] = DEFAULT_MAX_SIZE,
        webp_quality: int = DEFAULT_WEBP_QUALITY,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else app_paths.thumbnail_dir()
        self.max_size = (int(max_size[0]), int(max_size[1]))
        self.webp_quality = int(webp_quality)

    # ---- cache key / path ----------------------------------------------

    def cache_key(self, source: Any) -> str | None:
        """按当前文件 stat 值计算该资源的 cache key；不支持 / 无法 stat 时返回 ``None``。"""
        path, extension, resource_type = self._resolve(source)
        if not self._supported(resource_type, extension):
            return None
        return self._stat_key(path)

    def cache_path(self, source: Any) -> Path | None:
        """该资源当前状态对应的 cache 文件路径；不支持 / 无法 stat 时返回 ``None``。"""
        cache_key = self.cache_key(source)
        return self.path_for_key(cache_key) if cache_key else None

    def path_for_key(self, cache_key: str) -> Path:
        """cache key 对应的缓存文件路径（``<cache_key>.webp``）。"""
        return self.cache_dir / f"{cache_key}.webp"

    def is_supported(self, source: Any) -> bool:
        """该源是否属于本阶段支持的 preview 来源（character_card / PNG）。"""
        _, extension, resource_type = self._resolve(source)
        return self._supported(resource_type, extension)

    # ---- 查询 / 生成 ----------------------------------------------------

    def status(self, source: Any) -> PreviewStatus:
        """**不生成**，只看当前状态。

        - 不支持的来源（zipmod / 非 character_card / 非图片）→ ``unsupported``
        - 源文件不存在 / 不是普通文件 → ``missing``
        - 源存在但 stat 失败 → ``failed``
        - cache 存在且可读 → ``ready``
        - cache 尚未生成 → ``missing``
        """
        path, extension, resource_type = self._resolve(source)
        if not self._supported(resource_type, extension):
            return PreviewStatus(
                PREVIEW_UNSUPPORTED,
                reason=f"unsupported source: type={resource_type or '-'} ext={extension or '-'}",
            )
        if not path.is_file():
            return PreviewStatus(PREVIEW_MISSING, reason=f"source not a file: {path}")
        cache_key = self._stat_key(path)
        if cache_key is None:
            return PreviewStatus(PREVIEW_FAILED, reason=f"cannot stat source: {path}")
        cache_path = self.path_for_key(cache_key)
        if self._is_valid_cache(cache_path):
            return PreviewStatus(PREVIEW_READY, cache_key, cache_path)
        return PreviewStatus(
            PREVIEW_MISSING, cache_key, cache_path, reason="cache not generated"
        )

    def get_or_generate(self, source: Any) -> PreviewStatus:
        """取 preview：cache 命中 → ``ready``；否则生成（``missing → generate → ready/failed``）。

        源文件缺失时不尝试生成，直接返回 ``missing``。
        """
        path, extension, resource_type = self._resolve(source)
        if not self._supported(resource_type, extension):
            return PreviewStatus(
                PREVIEW_UNSUPPORTED,
                reason=f"unsupported source: type={resource_type or '-'} ext={extension or '-'}",
            )
        if not path.is_file():
            return PreviewStatus(PREVIEW_MISSING, reason=f"source not a file: {path}")
        cache_key = self._stat_key(path)
        if cache_key is None:
            return PreviewStatus(PREVIEW_FAILED, reason=f"cannot stat source: {path}")
        cache_path = self.path_for_key(cache_key)
        if self._is_valid_cache(cache_path):
            return PreviewStatus(PREVIEW_READY, cache_key, cache_path)
        return self.generate(source)

    def generate(self, source: Any) -> PreviewStatus:
        """强制（重新）生成一次 preview。

        失败只返回 ``failed``：不写数据库、不留半成品、不留永久 failure marker，下次仍可重试。
        """
        path, extension, resource_type = self._resolve(source)
        if not self._supported(resource_type, extension):
            return PreviewStatus(
                PREVIEW_UNSUPPORTED,
                reason=f"unsupported source: type={resource_type or '-'} ext={extension or '-'}",
            )
        if not path.is_file():
            return PreviewStatus(PREVIEW_MISSING, reason=f"source not a file: {path}")
        cache_key = self._stat_key(path)
        if cache_key is None:
            return PreviewStatus(PREVIEW_FAILED, reason=f"cannot stat source: {path}")

        cache_path = self.path_for_key(cache_key)
        try:
            with Image.open(path) as image:
                thumbnail = self._render_thumbnail(image)
                self._atomic_save(thumbnail, cache_path)
        except _SOURCE_ERRORS as exc:
            return PreviewStatus(
                PREVIEW_FAILED,
                cache_key,
                cache_path,
                reason=f"{type(exc).__name__}: {exc}",
            )
        # 生成后必须能被 Pillow 重新打开并验证（杜绝 0 字节 / 损坏缓存）。
        if not self._is_valid_cache(cache_path):
            return PreviewStatus(
                PREVIEW_FAILED, cache_key, cache_path, reason="cache failed validation after write"
            )
        return PreviewStatus(PREVIEW_READY, cache_key, cache_path)

    def invalidate(self, source: Any) -> bool:
        """删除该源当前状态对应的 cache 文件；返回是否真的删除了。"""
        cache_path = self.cache_path(source)
        if cache_path is None:
            return False
        try:
            cache_path.unlink()
            return True
        except OSError:
            return False

    # ---- GC -------------------------------------------------------------

    def gc(self, valid_keys: Iterable[str]) -> int:
        """删除 cache 中「不再对应当前资源 cache key」的旧缩略图，返回删除数量。

        只处理 ``thumbnail_cache/*.webp``；绝不触碰资源文件 / 数据库 / 样本。
        """
        valid = {str(key) for key in valid_keys}
        if not self.cache_dir.is_dir():
            return 0
        removed = 0
        for candidate in self.cache_dir.glob("*.webp"):
            if candidate.stem in valid:
                continue
            try:
                candidate.unlink()
                removed += 1
            except OSError:
                continue
        return removed

    def known_keys(self) -> set[str]:
        """当前 cache 目录里已有的 key 集合（调试 / 测试用）。"""
        if not self.cache_dir.is_dir():
            return set()
        return {path.stem for path in self.cache_dir.glob("*.webp")}

    # ---- 内部工具 -------------------------------------------------------

    @staticmethod
    def _resolve(source: Any) -> tuple[Path, str, str | None]:
        """把 ``source`` 解析成 ``(Path, 小写扩展名, resource_type|None)``。"""
        if isinstance(source, (str, Path)):
            path = Path(source)
            return path, path.suffix.lower(), None
        file_path = getattr(source, "file_path", None)
        if not file_path:
            raise TypeError("source 必须是路径字符串/Path，或带 file_path 属性的对象")
        path = Path(str(file_path))
        extension = getattr(source, "extension", None) or path.suffix
        resource_type = getattr(source, "resource_type", None)
        return path, str(extension).lower(), (str(resource_type) if resource_type else None)

    @staticmethod
    def _supported(resource_type: str | None, extension: str) -> bool:
        """支持判断：给了类型就按类型（须同时是 PNG），否则按扩展名。"""
        if resource_type is not None:
            return (
                resource_type in SUPPORTED_RESOURCE_TYPES
                and extension in SUPPORTED_EXTENSIONS
            )
        return extension in SUPPORTED_EXTENSIONS

    def _stat_key(self, path: Path) -> str | None:
        """按当前实际文件 stat 值算 key；不是普通文件 / 无法 stat 返回 ``None``。"""
        try:
            info = path.stat()
        except OSError:
            return None
        if not stat_module.S_ISREG(info.st_mode):
            return None
        return preview_cache_key(
            database.normalize_path_key(str(path)), info.st_size, info.st_mtime
        )

    @staticmethod
    def _is_valid_cache(cache_path: Path) -> bool:
        """cache 是否可读：不存在 → False；损坏 → 删除并 False。"""
        if not cache_path.is_file():
            return False
        try:
            with Image.open(cache_path) as image:
                image.verify()
                image.load()
            return True
        except Exception:  # noqa: BLE001 - 损坏的派生文件直接删除
            try:
                cache_path.unlink()
            except OSError:
                pass
            return False

    def _render_thumbnail(self, image: Image.Image) -> Image.Image:
        """统一缩略图：保留 alpha、保持纵横比、最长边 ≤ max_size、不放大。"""
        has_alpha = image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        )
        converted = image.convert("RGBA" if has_alpha else "RGB")
        # Pillow 的 thumbnail() 只缩小、不放大。
        converted.thumbnail(self.max_size, Image.Resampling.LANCZOS)
        return converted

    def _atomic_save(self, image: Image.Image, cache_path: Path) -> None:
        """临时文件 + 原子替换，避免留下半截 webp。"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        temp_path = cache_path.with_name(
            f".{cache_path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        )
        try:
            image.save(temp_path, format="WEBP", quality=self.webp_quality)
            os.replace(temp_path, cache_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass


__all__ = [
    "PreviewService",
    "PreviewStatus",
    "preview_cache_key",
    "PREVIEW_UNSUPPORTED",
    "PREVIEW_MISSING",
    "PREVIEW_READY",
    "PREVIEW_FAILED",
    "SUPPORTED_RESOURCE_TYPES",
    "SUPPORTED_EXTENSIONS",
    "DEFAULT_MAX_SIZE",
    "DEFAULT_WEBP_QUALITY",
]
