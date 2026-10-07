"""只读索引游戏内 zipmod：文件名 / 大小 / manifest GUID。

用法::

    python tools/index_zipmods.py <游戏根目录> <输出.json> [--skip SoundMods ...]

zipmod 即 zip 压缩包（部分带密码，此时无法读 manifest，guid 记为 null）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import zipfile

GUID_RE = re.compile(rb"<guid>(.*?)</guid>", re.S)


def read_guid(path: str) -> str | None:
    try:
        with zipfile.ZipFile(path) as zf:
            if "manifest.xml" in zf.namelist():
                return GUID_RE.search(zf.read("manifest.xml")).group(1).decode("utf-8", "replace").strip()
    except Exception:  # noqa: BLE001
        return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game_root")
    ap.add_argument("output")
    ap.add_argument("--skip", nargs="*", default=["SoundMods"])
    args = ap.parse_args()

    mods_dir = os.path.join(args.game_root, "mods")
    rows = []
    for dirpath, _dirs, names in os.walk(mods_dir):
        if any(s in dirpath for s in args.skip):
            continue
        for n in names:
            if not n.lower().endswith(".zipmod"):
                continue
            full = os.path.join(dirpath, n)
            rows.append(
                {
                    "path": full,
                    "file": n,
                    "size": os.path.getsize(full),
                    "guid": read_guid(full),
                    "dir": os.path.relpath(dirpath, mods_dir),
                }
            )
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False)
    print(f"{len(rows)} zipmods -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
