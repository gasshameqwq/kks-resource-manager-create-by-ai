"""Phase 1.3-C-1：PreviewService 测试。

覆盖：cache key（deterministic / size / mtime / 不依赖 resource.id）、真实 22 卡生成、
有效 WebP、cache hit、invalidation、corruption、generation failure + retry、unsupported、
missing、delete/rebuild、GC，以及只读不变量（schema / Parser / Scanner / 样本 / 数据库 /
``resources.thumbnail_path`` 未被写入）。
"""

from __future__ import annotations

import hashlib
import inspect
import os
import shutil
import sys
import types
import zipfile
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import app_paths  # noqa: E402
from core.database import db as database  # noqa: E402
from core.database import schema as schema_mod  # noqa: E402
from core.library import LibraryStore  # noqa: E402
from core.scanner import LibraryScanner  # noqa: E402
from core.thumbnails import (  # noqa: E402
    DEFAULT_MAX_SIZE,
    PREVIEW_FAILED,
    PREVIEW_MISSING,
    PREVIEW_READY,
    PREVIEW_UNSUPPORTED,
    PreviewService,
    preview_cache_key,
)
from core.thumbnails import service as service_mod  # noqa: E402
from tests import builders  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def service(tmp_path: Path) -> PreviewService:
    return PreviewService(cache_dir=tmp_path / "thumbnail_cache")


def _write_png(path: Path, size: tuple[int, int] = (64, 64), color=(120, 60, 200)) -> Path:
    Image.new("RGB", size, color).save(path, format="PNG")
    return path


def _card(path: Path, *, resource_type: str = "character_card"):
    """模拟 Query Layer 的 ResourceSummary（只带 PreviewService 用到的字段）。"""
    return types.SimpleNamespace(
        file_path=str(path), extension=path.suffix.lower(), resource_type=resource_type, id=1
    )


# ---------------------------------------------------------------------------
# 1-4. cache key
# ---------------------------------------------------------------------------


def test_cache_key_deterministic_and_32_hex() -> None:
    k1 = preview_cache_key("d:/kks/a.png", 123, 456.5)
    k2 = preview_cache_key("d:/kks/a.png", 123, 456.5)
    assert k1 == k2
    assert len(k1) == 32 and all(c in "0123456789abcdef" for c in k1)


def test_cache_key_changes_with_size() -> None:
    base = preview_cache_key("d:/kks/a.png", 100, 1.0)
    assert preview_cache_key("d:/kks/a.png", 101, 1.0) != base


def test_cache_key_changes_with_mtime() -> None:
    base = preview_cache_key("d:/kks/a.png", 100, 1.0)
    assert preview_cache_key("d:/kks/a.png", 100, 2.0) != base
    assert preview_cache_key("d:/kks/b.png", 100, 1.0) != base  # 路径也是 key 的一部分


def test_cache_key_does_not_use_resource_id(service: PreviewService, tmp_path: Path) -> None:
    png = _write_png(tmp_path / "card.png")
    first = types.SimpleNamespace(file_path=str(png), extension=".png", resource_type="character_card", id=1)
    second = types.SimpleNamespace(file_path=str(png), extension=".png", resource_type="character_card", id=987654)
    assert service.cache_key(first) == service.cache_key(second)


def test_cache_key_and_cache_path_api(service: PreviewService, tmp_path: Path) -> None:
    png = _write_png(tmp_path / "card.png")
    key = service.cache_key(png)
    assert key is not None
    assert service.cache_path(png) == service.path_for_key(key)
    # 不支持的来源 → 两者都是 None
    assert service.cache_key(tmp_path / "x.zipmod") is None
    assert service.cache_path(tmp_path / "x.zipmod") is None


# ---------------------------------------------------------------------------
# 5-6. 真实 22 卡生成
# ---------------------------------------------------------------------------


def test_all_real_cards_generate_valid_webp(service: PreviewService, sample_files) -> None:
    cards = sample_files["cards"]
    assert len(cards) == 22

    digests_before = {card: _sha256(card) for card in cards}
    ready = 0
    for card in cards:
        status = service.get_or_generate(card)
        assert status.state == PREVIEW_READY, (card, status)
        assert status.path is not None and status.path.is_file()
        with Image.open(status.path) as image:
            assert image.format == "WEBP"
            width, height = image.size
            assert max(width, height) <= max(DEFAULT_MAX_SIZE)
            assert max(width, height) == max(DEFAULT_MAX_SIZE)
        ready += 1
    assert ready == 22
    # 源 PNG 一个字节都不能变
    assert {card: _sha256(card) for card in cards} == digests_before


def test_real_card_as_resource_summary_is_supported(
    service: PreviewService, sample_files
) -> None:
    status = service.get_or_generate(_card(sample_files["cards"][0]))
    assert status.state == PREVIEW_READY


def test_small_source_is_not_upscaled(service: PreviewService, tmp_path: Path) -> None:
    small = _write_png(tmp_path / "small.png", size=(32, 48))
    status = service.get_or_generate(small)
    assert status.state == PREVIEW_READY
    with Image.open(status.path) as image:
        assert image.size == (32, 48)


# ---------------------------------------------------------------------------
# 7. cache hit
# ---------------------------------------------------------------------------


def test_cache_hit_does_not_regenerate(
    service: PreviewService, sample_files, monkeypatch
) -> None:
    card = sample_files["cards"][0]
    assert service.status(card).state == PREVIEW_MISSING

    calls = {"n": 0}
    original = service._render_thumbnail

    def counting(image):
        calls["n"] += 1
        return original(image)

    monkeypatch.setattr(service, "_render_thumbnail", counting)

    first = service.get_or_generate(card)
    assert first.state == PREVIEW_READY and calls["n"] == 1
    second = service.get_or_generate(card)
    assert second.state == PREVIEW_READY
    assert second.path == first.path
    assert calls["n"] == 1, "cache 命中不得重新生成"


# ---------------------------------------------------------------------------
# 8. invalidation
# ---------------------------------------------------------------------------


def test_invalidation_on_mtime_and_size(
    service: PreviewService, sample_files, tmp_path: Path
) -> None:
    source = tmp_path / "copy.png"
    shutil.copyfile(sample_files["cards"][0], source)

    first = service.get_or_generate(source)
    assert first.state == PREVIEW_READY
    old_key = first.cache_key

    stat = source.stat()
    os.utime(source, (stat.st_atime, stat.st_mtime + 100))
    changed_mtime = service.status(source)
    assert changed_mtime.state == PREVIEW_MISSING and changed_mtime.cache_key != old_key
    assert service.get_or_generate(source).state == PREVIEW_READY

    key_before = service.cache_key(source)
    with source.open("ab") as handle:
        handle.write(b"\x00")
    changed_size = service.status(source)
    assert changed_size.state == PREVIEW_MISSING and changed_size.cache_key != key_before
    assert service.get_or_generate(source).state == PREVIEW_READY


# ---------------------------------------------------------------------------
# 9. corruption
# ---------------------------------------------------------------------------


def test_corrupt_cache_is_deleted_and_regenerated(
    service: PreviewService, sample_files
) -> None:
    card = sample_files["cards"][0]
    first = service.get_or_generate(card)
    assert first.state == PREVIEW_READY

    first.path.write_bytes(b"this is not a webp")
    rebuilt = service.get_or_generate(card)
    assert rebuilt.state == PREVIEW_READY
    assert rebuilt.path == first.path
    with Image.open(rebuilt.path) as image:
        image.load()
        assert image.format == "WEBP"


# ---------------------------------------------------------------------------
# 10-11. generation failure + retry
# ---------------------------------------------------------------------------


def test_generation_failure_leaves_no_cache_and_can_retry(
    service: PreviewService, tmp_path: Path
) -> None:
    bad = tmp_path / "not-an-image.png"
    bad.write_bytes(b"definitely not a png")

    failed = service.get_or_generate(bad)
    assert failed.state == PREVIEW_FAILED
    assert failed.reason
    assert list(service.cache_dir.glob("*.webp")) == []  # 不留半成品 / 最终 cache
    assert service.get_or_generate(bad).state == PREVIEW_FAILED  # 没有永久 failure marker

    _write_png(bad)  # 修复源文件
    assert service.get_or_generate(bad).state == PREVIEW_READY  # 可以 retry


# ---------------------------------------------------------------------------
# 12. unsupported
# ---------------------------------------------------------------------------


def test_unsupported_zipmod_even_with_internal_image(
    service: PreviewService, sample_files, tmp_path: Path
) -> None:
    assert service.get_or_generate(sample_files["zipmods"][0]).state == PREVIEW_UNSUPPORTED

    zipped = tmp_path / "mod.zipmod"
    with zipfile.ZipFile(zipped, "w") as archive:
        archive.writestr("manifest.xml", "<manifest><guid>x</guid></manifest>")
        archive.writestr("preview.png", builders.tiny_png())
    assert service.get_or_generate(zipped).state == PREVIEW_UNSUPPORTED
    assert list(service.cache_dir.glob("*.webp")) == []


def test_type_aware_support(service: PreviewService, tmp_path: Path) -> None:
    png = _write_png(tmp_path / "x.png")
    card = _card(png, resource_type="character_card")
    mod = _card(png, resource_type="mod")
    # 给了类型就按类型：非 character_card → unsupported
    assert service.get_or_generate(card).state == PREVIEW_READY
    assert service.get_or_generate(mod).state == PREVIEW_UNSUPPORTED
    # 只给路径（无类型）→ 回退到扩展名：PNG 支持
    assert service.is_supported(png) is True
    assert service.is_supported(tmp_path / "x.zipmod") is False


# ---------------------------------------------------------------------------
# 13. missing source
# ---------------------------------------------------------------------------


def test_missing_source_returns_missing(service: PreviewService, tmp_path: Path) -> None:
    absent = tmp_path / "does-not-exist.png"
    assert service.get_or_generate(absent).state == PREVIEW_MISSING
    assert service.status(absent).state == PREVIEW_MISSING
    assert service.generate(absent).state == PREVIEW_MISSING


# ---------------------------------------------------------------------------
# 14. delete / rebuild
# ---------------------------------------------------------------------------


def test_cache_can_be_deleted_and_rebuilt(service: PreviewService, sample_files) -> None:
    card = sample_files["cards"][0]
    first = service.get_or_generate(card)
    assert first.state == PREVIEW_READY

    shutil.rmtree(service.cache_dir)
    assert service.status(card).state == PREVIEW_MISSING
    rebuilt = service.get_or_generate(card)
    assert rebuilt.state == PREVIEW_READY and rebuilt.path.is_file()


# ---------------------------------------------------------------------------
# 15. GC
# ---------------------------------------------------------------------------


def test_gc_removes_only_stale_files(service: PreviewService, sample_files) -> None:
    status = service.get_or_generate(sample_files["cards"][0])
    assert status.state == PREVIEW_READY

    service.cache_dir.mkdir(parents=True, exist_ok=True)
    stale = service.cache_dir / "deadbeefdeadbeefdeadbeefdeadbeef.webp"
    stale.write_bytes(b"stale")

    assert service.gc(valid_keys={status.cache_key}) == 1
    assert status.path.is_file(), "有效 cache 不能被删"
    assert not stale.exists()


# ---------------------------------------------------------------------------
# 16-20. 只读不变量
# ---------------------------------------------------------------------------


def test_schema_version_unchanged() -> None:
    assert schema_mod.SCHEMA_VERSION == 2
    assert sorted(schema_mod.MIGRATIONS) == [1, 2]


def test_service_is_structurally_isolated() -> None:
    """PreviewService 不依赖 Parser/Scanner/Query Layer，也不访问数据库。"""
    source = inspect.getsource(service_mod)
    assert "core.parsers" not in source
    assert "core.scanner" not in source
    assert "core.query" not in source
    assert ".execute(" not in source
    assert "thumbnail_path" not in source


def test_preview_does_not_modify_database_or_thumbnail_path(
    tmp_path: Path, sample_root: Path
) -> None:
    db_file = tmp_path / "appdata" / "kks_resource_manager.db"
    database.initialize(db_file)
    conn = database.connect(db_file)
    try:
        library = LibraryStore(conn).add(sample_root, name="真实样本")
        LibraryScanner(conn).scan(library.id)
        file_paths = [r["file_path"] for r in conn.execute("SELECT file_path FROM resources")]
    finally:
        conn.close()

    before = _sha256(db_file)
    service = PreviewService(cache_dir=tmp_path / "cache")
    for file_path in file_paths:
        service.get_or_generate(file_path)
    after = _sha256(db_file)

    assert before == after, "PreviewService 不得修改数据库"

    conn = database.connect(db_file)
    try:
        written = conn.execute(
            "SELECT count(*) AS c FROM resources WHERE thumbnail_path IS NOT NULL"
        ).fetchone()["c"]
    finally:
        conn.close()
    assert written == 0, "resources.thumbnail_path 必须保持未写入"


def test_default_cache_dir_is_app_thumbnail_dir() -> None:
    assert PreviewService().cache_dir == app_paths.thumbnail_dir()
