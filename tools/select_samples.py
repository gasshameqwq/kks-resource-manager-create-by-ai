"""从卡片索引中筛选 A–J 测试样本候选（只读，仅打印报告）。

用法::

    python tools/select_samples.py <index.json> [sample ...]

``index.json`` 由 ``tools/probe_cards.py`` 生成。
"""

from __future__ import annotations

import collections
import json
import os
import re
import sys

GENERIC_MODS = {"moderchan.CharamakerSupportMOD"}
CLOTHES_RE = re.compile(r"ChaFileClothes\.(Clothes[A-Za-z0-9]+)$")


def name(path: str) -> str:
    return os.path.basename(path)


def folder(path: str) -> str:
    return os.path.basename(os.path.dirname(path))


def uniq_mods(rec: dict) -> set:
    return {m["ModID"] for m in rec.get("mods") or [] if m.get("ModID")}


def real_mods(rec: dict) -> list:
    return [m for m in rec.get("mods") or [] if m.get("ModID") not in GENERIC_MODS]


def props(rec: dict) -> set:
    return set((rec.get("mod_properties") or {}).keys())


def has_clothes_mod(rec: dict) -> bool:
    return any(CLOTHES_RE.search(m.get("Property") or "") for m in real_mods(rec))


def has_eye_mod(rec: dict) -> bool:
    return any(
        "Pupil" in (m.get("Property") or "") or "eyeline" in (m.get("Property") or "")
        for m in real_mods(rec)
    )


def has_body_tex(rec: dict) -> bool:
    keys = props(rec)
    if any(
        k.endswith(("detailId", "underhairId", "sunburnId", "PaintID1", "PaintID2",
                    "PaintLayoutID1", "PaintLayoutID2"))
        for k in keys
    ):
        return True
    return bool(
        {"KSOX", "KCOX", "Marco.SkinEffects"} & set(rec.get("plugins") or [])
        and (rec.get("embed_png_kex") or 0) > 3
    )


def line(rec: dict, extra: str = "") -> str:
    return (
        f"    {rec['size']:>10,}  kex={rec.get('kex_size') or 0:>9,}  "
        f"png={rec.get('embed_png_kex') or 0:>3}  "
        f"nmod={len(uniq_mods(rec)):>3}  {(rec.get('name') or '')[:20]:20s} "
        f"{folder(rec['path'])[:16]:16s} {name(rec['path'])[:46]} {extra}"
    )


def main() -> int:
    index_path = sys.argv[1]
    wanted = set(sys.argv[2:]) or {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J"}
    idx = json.load(open(index_path, encoding="utf-8"))
    ok = [r for r in idx if r.get("parse_status") == "ok"]

    if "A" in wanted:
        print("=== A 普通角色卡（0 MOD，KKS）===")
        for r in sorted((r for r in ok if not r.get("mods") and r.get("game") == "KKS"),
                        key=lambda r: r["size"])[:15]:
            print(line(r))
        print("  合计:", sum(1 for r in ok if not r.get("mods") and r.get("game") == "KKS"))

    if "B" in wanted:
        print("=== B 带 MOD 的角色卡（1–6 个 MOD）===")
        cand = [r for r in ok if 1 <= len(uniq_mods(r)) <= 6]
        for r in sorted(cand, key=lambda r: r["size"])[:15]:
            print(line(r, ",".join(sorted(uniq_mods(r)))[:60]))
        print("  合计:", len(cand))

    if "C" in wanted:
        print("=== C 带自定义眼睛（Pupil/eyeline 依赖 MOD）===")
        cand = [r for r in ok if has_eye_mod(r)]
        for r in sorted(cand, key=lambda r: (len(uniq_mods(r)), r["size"]))[:15]:
            eye = [m["Property"] + "=" + (m["ModID"] or "") for m in real_mods(r)
                   if "Pupil" in (m.get("Property") or "") or "eyeline" in (m.get("Property") or "")]
            print(line(r, ";".join(eye)[:70]))
        print("  合计:", len(cand))

    if "D" in wanted:
        print("=== D 带皮肤/身体贴图（body 贴图属性或 overlay 插件 + 内嵌贴图）===")
        cand = [r for r in ok if has_body_tex(r) and (r.get("embed_png_kex") or 0) > 2]
        for r in sorted(cand, key=lambda r: -int(r.get("embed_png_kex") or 0))[:15]:
            print(line(r))
        print("  合计:", len(cand))

    if "E" in wanted:
        print("=== E 角色 + 衣服 MOD（outfit*.ChaFileClothes.* 指向 MOD）===")
        cand = [r for r in ok if has_clothes_mod(r)]
        for r in sorted(cand, key=lambda r: (len(uniq_mods(r)), r["size"]))[:15]:
            cl = [m["Property"] + "=" + (m["ModID"] or "") for m in real_mods(r)
                  if CLOTHES_RE.search(m.get("Property") or "")]
            print(line(r, ";".join(cl)[:70]))
        print("  合计:", len(cand))

    if "F" in wanted:
        print("=== F 同作者多个角色（文件名/作者标签）===")
        by_author = collections.defaultdict(list)
        for r in ok:
            m = re.search(r"Koikatu(?:Sun)?_F_\d+_(.+?)(?:_([A-Za-z0-9.]+))?\.png$", name(r["path"]))
            if m and m.group(2):
                by_author[m.group(2)].append(r)
            for a in r.get("authors") or []:
                if a not in ("[Unknown]", "Anonymous", "unknown", "anonymous"):
                    by_author[a].append(r)
        for a, rs in sorted(by_author.items(), key=lambda kv: -len(kv[1]))[:15]:
            print(f"  -- 作者 {a}  ({len(rs)} 张)")
            for r in rs[:5]:
                print(line(r))

    if "H" in wanted:
        print("=== H 同一 MOD 被多个角色使用 ===")
        users = collections.defaultdict(list)
        for r in ok:
            for mid in uniq_mods(r) - GENERIC_MODS:
                users[mid].append(r)
        shared = [(m, rs) for m, rs in users.items() if 2 <= len(rs) <= 5]
        shared.sort(key=lambda kv: (len(kv[1]), kv[0]))
        for m, rs in shared[:12]:
            print(f"  -- MOD {m}  被 {len(rs)} 张使用")
            for r in rs[:4]:
                print(line(r))
        print("  合计 2–5 人共享的 MOD:", len(shared))

    if "I" in wanted:
        print("=== I 文件名混乱 / 重名 ===")
        by_name = collections.defaultdict(list)
        for r in ok:
            by_name[name(r["path"])].append(r)
        dup_names = {k: v for k, v in by_name.items() if len(v) > 1}
        # 显示名重复（去掉时间戳后同名）
        norm = collections.defaultdict(list)
        for r in ok:
            norm[re.sub(r"\d{6,}", "#", name(r["path"]))].append(r)
        norm_dup = {k: v for k, v in norm.items() if len(v) > 1}
        print("  完全同名:", len(dup_names), " 归一化后同名:", len(norm_dup))
        for k, v in list(norm_dup.items())[:12]:
            print(f"  -- {k[:56]}  ({len(v)} 张)")
            for r in v[:3]:
                print(line(r))
        messy = [r for r in ok if re.match(r"^[A-Za-z0-9_\- ]{0,12}\.png$", name(r["path"]))
                 or " " in name(r["path"])[:-4] or "　" in name(r["path"])]
        print("  混乱名示例:")
        for r in messy[:10]:
            print(line(r))

    if "J" in wanted:
        print("=== J 复杂完整角色（MOD 数 / 内嵌贴图最多）===")
        for r in sorted(ok, key=lambda r: -(len(uniq_mods(r)) * 2 + int(r.get("embed_png_kex") or 0)))[:12]:
            print(line(r))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
