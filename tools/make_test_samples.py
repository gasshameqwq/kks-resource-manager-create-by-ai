"""把选定的 A–J 测试样本复制到 kksmannerscanlike 目录（源目录只读）。

依据 ``tools/probe_cards.py`` 生成的卡片索引，把每类样本所需的
角色卡（以及必要时的 zipmod）复制到独立子文件夹，并生成一份清单
``00_样本清单.md``。

用法::

    python tools/make_test_samples.py <chara_index.json> <zipmod_index.json> <目标目录>
"""

from __future__ import annotations

import json
import os
import shutil
import sys

GAME = r"G:\shuang\xinkks\KoikatuSunshine-Game\KoikatuSunshine"
CHARA_ROOT = os.path.join(GAME, "UserData", "chara")

# src 为相对 UserData\chara 的路径；dest 为样本子文件夹内的相对路径（默认取文件名）。
SAMPLES: list[dict] = [
    {
        "key": "A",
        "folder": "A_普通角色卡_无MOD",
        "desc": "基础角色卡：内置 MOD 依赖列表为空，用于验证最基本的卡片识别 / 缩略图 / 元数据。",
        "cards": [
            {"src": r"female\动漫角色\魔法少女小圆\魔法少女小圆 - 鹿目圆.png"},
            {"src": r"female\赌牌游戏\碧蓝航线\碧蓝航线 - 罗德尼.png"},
        ],
        "mods": [],
    },
    {
        "key": "B",
        "folder": "B_带MOD角色卡",
        "desc": "带 MOD 的角色卡：卡片依赖外部 zipmod（发饰、服装、配饰），用于检测「角色 → MOD」依赖。",
        "cards": [
            {"src": r"female\动漫角色\魔法少女小圆\魔法少女小圆 - 美树沙耶香.png"},
            {"src": r"female\动漫角色\魔法少女小圆\魔法少女小圆 - 佐仓杏子.png"},
        ],
        "mods": ["com.Quokka.sisterveilb", "com.Quokka.crossstaff", "com.Quokka.chinadresstop"],
    },
    {
        "key": "C",
        "folder": "C_自定义眼睛",
        "desc": "眼睛资源识别：瞳孔 / 上下眼线贴图来自 MOD（ChaFileFace.Pupil1/2、eyelineUpId 指向 MOD）。",
        "cards": [
            {"src": r"female\轻文小说\没有黄段子的无聊世界\没有黄段子的无聊世界 - 华城绫女.png"},
            {"src": r"female\常规游戏\天结堡主\天结堡主 - 岚燐结骑.png"},
        ],
        "mods": ["com.gf.collection", "RCL_circuit.Mod.RanrinYuiki"],
    },
    {
        "key": "D",
        "folder": "D_皮肤身体贴图",
        "desc": "贴图资源识别：身体皮肤 / 细节贴图来自 MOD（ChaFileBody.detailId 等），并含卡片内嵌贴图。",
        "cards": [
            {"src": r"female\漫画角色\政宗君的复仇\政宗君的复仇 - 安达垣爱姬.png"},
            {"src": r"female\漫画角色\请问您今天要来点兔子吗\请问您今天要来点兔子吗 - 保登心爱.png"},
        ],
        "mods": ["com.Blanketman.AdditionalSkinMod"],
    },
    {
        "key": "E",
        "folder": "E_角色加衣服MOD",
        "desc": "服装资源关系：服装槽（outfit*.ChaFileClothes.*）指向 MOD，用于判断「角色 ↔ 服装 MOD」关系。",
        "cards": [
            {"src": r"female\轻文小说\青春猪头少年系列\青春猪头少年系列 - 古贺朋绘.png"},
            {"src": r"female\轻文小说\不死者之王\不死者之王 - 夏提雅 布拉德弗伦.png"},
        ],
        "mods": ["shinyBunny", "com.Quokka.classicmaidskirt"],
    },
    {
        "key": "F",
        "folder": "F_同作者多角色",
        "desc": "作者 / 资源关联：同一作者（卡内 marco.authordata = Evaan）发布的多张角色卡，用于按作者聚合。",
        "cards": [
            {"src": r"female\Koikatu_F_20201023022200944_Hermione_Evaan.png"},
            {"src": r"female\Koikatu_F_20230324192530956_Tatsumaki_Evaan.png"},
            {"src": r"female\Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png"},
        ],
        "mods": ["ryo2003.stiletto"],
    },
    {
        "key": "G",
        "folder": "G_孤立MOD_无角色卡",
        "desc": "孤立资源：样本本身就是 MOD —— 这些 zipmod 的 GUID 不存在于任何角色卡的依赖列表中，"
                "用于测试「有 MOD、无角色卡」的孤立资源识别。",
        "cards": [],
        "mods": ["NoHair", "elven_panst", "koikatu.AltSlot.co_bot_19"],
    },
    {
        "key": "H",
        "folder": "H_共享MOD多角色",
        "desc": "共享依赖：同一个 MOD 被两张角色卡同时引用，用于测试「一 MOD → 多角色」的反向关联。",
        "cards": [
            {"src": r"female\明日方舟\明日方舟 - 红豆.png"},
            {"src": r"female\赌牌游戏\FATE\FATE - 长尾景虎.png"},
        ],
        "mods": ["com.Quokka.naginata"],
    },
    {
        "key": "I",
        "folder": "I_文件名混乱重名",
        "desc": "Scanner 不能依赖简单命名：包含同名不同目录、同名不同时间戳、带空格 / 无意义文件名。",
        "cards": [
            {"src": r"female\KoikatsuSun_F_20260905140632481_Higashiyama Kobeni.png",
             "dest": r"同名不同时间戳\KoikatsuSun_F_20260905140632481_Higashiyama Kobeni.png"},
            {"src": r"female\KoikatsuSun_F_20260905140632862_Higashiyama Kobeni.png",
             "dest": r"同名不同时间戳\KoikatsuSun_F_20260905140632862_Higashiyama Kobeni.png"},
            {"src": r"female\Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png",
             "dest": r"同名不同目录\female\Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png"},
            {"src": r"old\female\Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png",
             "dest": r"同名不同目录\old_female\Koikatu_F_20240209185711407_Kugisaki Nobara_Evaan.png"},
            {"src": r"female\[Yeeted] Sora .png", "dest": r"混乱命名\[Yeeted] Sora .png"},
            {"src": r"female\KK_317794.png", "dest": r"混乱命名\KK_317794.png"},
        ],
        "mods": [],
    },
    {
        "key": "J",
        "folder": "J_复杂完整角色",
        "desc": "综合测试：MOD 数量、插件数量与内嵌贴图都很多的高复杂度角色。",
        "cards": [{"src": r"female\轻文小说\刀剑神域\刀剑神域 - 绀野木棉季.png"}],
        "mods": [],
    },
]


def main() -> int:
    chara_index_path, zipmod_index_path, target_root = sys.argv[1:4]
    cards = {r["path"]: r for r in json.load(open(chara_index_path, encoding="utf-8"))}
    zipmods = json.load(open(zipmod_index_path, encoding="utf-8"))
    by_guid: dict[str, list] = {}
    for row in zipmods:
        if row.get("guid"):
            by_guid.setdefault(row["guid"], []).append(row)

    os.makedirs(target_root, exist_ok=True)
    report: list[str] = [
        "# Koikatu Sunshine 测试样本清单（A–J）",
        "",
        "所有文件均由游戏目录**复制**而来，原游戏内容未做任何修改。",
        "依赖信息来自卡片内置数据（`com.bepis.sideloader.universalautoresolver`）。",
        "",
    ]
    copied = 0

    for sample in SAMPLES:
        folder = os.path.join(target_root, sample["folder"])
        os.makedirs(folder, exist_ok=True)
        report.append(f"## {sample['key']}. {sample['folder'].split('_', 1)[1]}")
        report.append("")
        report.append(sample["desc"])
        report.append("")

        for card in sample["cards"]:
            src = os.path.join(CHARA_ROOT, card["src"])
            if not os.path.isfile(src):
                print(f"!! 缺少文件: {src}")
                continue
            dest_rel = card.get("dest") or os.path.basename(src)
            dest = os.path.join(folder, dest_rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
            rec = cards.get(src, {})
            mods = sorted({m["ModID"] for m in rec.get("mods") or [] if m.get("ModID")})
            report.append(f"- `{dest_rel}`  ←  `UserData\\chara\\{card['src']}`")
            report.append(
                f"  - 角色名：{rec.get('name')}　类型：{rec.get('card_kind')}"
                f"　大小：{rec.get('size'):,} 字节　内嵌贴图：{rec.get('embed_png_kex', 0)}"
            )
            report.append(
                f"  - 插件 {len(rec.get('plugins') or [])} 个；唯一 MOD {len(mods)} 个"
                + (f"：{', '.join('`' + m + '`' for m in mods[:8])}" if mods else "")
            )
            if rec.get("authors"):
                report.append(f"  - 卡作者：{', '.join(rec['authors'])}")

        if sample["mods"]:
            mod_dir = os.path.join(folder, "MOD")
            os.makedirs(mod_dir, exist_ok=True)
            report.append("")
            report.append("  依赖 MOD（来自游戏 mods 目录，仅复制相关文件）：")
            for guid in sample["mods"]:
                rows = by_guid.get(guid)
                if not rows:
                    report.append(f"  - `{guid}` —— 未在 mods 目录找到对应 zipmod")
                    continue
                for row in rows:
                    dest = os.path.join(mod_dir, row["file"])
                    shutil.copy2(row["path"], dest)
                    copied += 1
                    report.append(f"  - `{guid}` → `MOD\\{row['file']}`（{row['size']:,} 字节）")
        report.append("")

    report_path = os.path.join(target_root, "00_样本清单.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(report))
    print(f"已复制 {copied} 个文件到 {target_root}")
    print(f"清单：{report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
