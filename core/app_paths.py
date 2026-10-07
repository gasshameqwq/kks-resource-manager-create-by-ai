"""应用路径解析：统一管理数据目录、数据库文件、缩略图缓存与日志目录。

规则：
- 打包成 exe 后，数据放在 exe 所在目录（便携式，符合本项目的本地化定位）。
- 源码运行时，数据放在项目根的 ``data/`` 下。
- 允许用环境变量 ``KKS_RM_DATA_DIR`` 覆盖，便于测试与多库切换。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "KKSResourceManager"

_ENV_DATA_DIR = "KKS_RM_DATA_DIR"


def app_root() -> Path:
    """应用根目录：exe 所在目录（打包时）或项目根（源码运行时）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """可写数据目录。"""
    override = os.environ.get(_ENV_DATA_DIR)
    if override:
        return Path(override).expanduser().resolve()
    return app_root() / "data"


def db_path() -> Path:
    """SQLite 数据库文件路径。"""
    return data_dir() / "kks_resource_manager.db"


def thumbnail_dir() -> Path:
    """缩略图缓存目录（缓存文件，可随时重建/删除）。"""
    return data_dir() / "thumbnail_cache"


def logs_dir() -> Path:
    """运行日志目录。"""
    return data_dir() / "logs"


def ensure_dirs() -> Path:
    """确保运行时目录存在，返回数据目录。"""
    for path in (data_dir(), thumbnail_dir(), logs_dir()):
        path.mkdir(parents=True, exist_ok=True)
    return data_dir()
