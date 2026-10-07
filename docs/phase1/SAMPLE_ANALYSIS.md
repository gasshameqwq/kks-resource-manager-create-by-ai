# 真实样本只读分析报告（Phase 1.2 前置）

> 样本根目录：`G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike`
> 分析日期：2026-10-06 · 只读分析，**未实现、未修改任何 Scanner 代码**
> 分析工具：`tools/inspect_card.py`（本轮新增，只读探针，不是 Scanner）
> 环境：`.venv` · CPython 3.12.10 · SQLite 3.49.1 · msgpack 1.2.3

## 三类标注约定

全文严格区分三种信息，**不混用**：

| 标记 | 含义 |
| :--- | :--- |
| **【用户声明】** | 来自 `00_样本清单.md`，是你写的意图，不是我从字节验证的结论 |
| **【可验证事实】** | 我从实际文件字节 / 结构中读出来的，可复现 |
| **【推测 / 待验证】** | 目前无法可靠确认，或需要额外样本/实验才能定论 |

---

## 0. 方法与本轮边界

| 项 | 说明 |
| :--- | :--- |
| 读取方式 | 全部 `open(path,"rb")` 只读；未写入、未移动、未重命名、未删除任何样本文件 |
| 未产生副作用 | 未在样本目录生成缩略图、缓存或索引文件 |
| 未做的事 | 没有实现 Scanner；没有改动 `core/`、`ui/`、`tests/` 的任何业务代码 |
| 新增文件 | 仅 `tools/inspect_card.py`（只读探针）与本报告 |
| 解析方式 | 先用真实字节反推容器结构，再据此提取；不套用任何未经样本验证的format假设 |

### 0.1 交叉验证：与既有工具的一致性

准备样本时（19:07–19:17）项目里已有 4 个脚本：`tools/probe_cards.py`、
`tools/index_zipmods.py`、`tools/select_samples.py`、`tools/make_test_samples.py`。
本轮**独立**实现了解析逻辑（`tools/inspect_card.py`），并与它们互相印证：

| 项 | `probe_cards.py`（既有） | `inspect_card.py`（本轮） | 结论 |
| :--- | :--- | :--- | :--- |
| 数据区起点 | `lst_pos + used + 8` | `lstInfo 长度 + int32 保留` | **完全一致** |
| 内嵌贴图 | 全文 PNG 数 `embedded_png` | 数据区 PNG 数 | 数值等价（见下） |
| 唯一 MOD | `mod_ids`（按 ModID 去重） | `unique_mod_ids` | 一致 |
| zipmod GUID | zip 内 `manifest.xml` 的 `<guid>` | 同 | 一致 |

**「内嵌贴图」口径现已确认**：`probe_cards.py` 记录全文 PNG 计数 `embedded_png`，
清单里的数字 = `embedded_png − 1（主图）− 1（面部预览若为 PNG）`，
等价于本报告的「**数据区 PNG 签名数**」。
两种独立实现给出相同结果，22/22 与清单吻合 → 该指标定义**可以固定下来**。

> 既有工具还记录了一条重要边界：`index_zipmods.py` 注释说明
> **部分 zipmod 带密码，此时读不到 manifest、guid 记为 null**。
> 本样本集 13 个 zipmod 全部可正常读取（**无加密样本**）→ 「加密 zipmod」仍是**待验证**项。

---

## 1. 卡片容器格式（本轮实测反推）

这一节全部是 **【可验证事实】**，是对 22 张卡片逐字节验证后得到的结构：

```text
[标准 PNG 数据流 ... 直到 IEND 结束]
[int32 LE]  productNo              实测 = 100 (0x64)
[u8 长度 + UTF-8 字符串] marker     实测 "【KoiKatuCharaSun】" 或 "【KoiKatuChara】"
[u8 长度 + UTF-8 字符串] 卡片版本   实测 "0.0.0"
[int32 LE] 面部预览图字节数 + 图像
[int32 LE] lstInfo 块长度 + msgpack {"lstInfo":[{name,version,pos,size}...]}
[int32 LE] 数据区长度
[int32 LE] 保留字段（22 张卡实测均为 0）
[数据区]   按 lstInfo 的 pos/size 排列
```

**关键实测发现（都与直觉不同，必须记录）：**

1. **面部预览图有两种格式**：22 张卡中既有 **JPEG**（`ffd8ffe0`，如鹿目圆/佐仓杏子/美树沙耶香）也有 **PNG**（`89504e47`，如罗德尼/岚燐结骑）。
   → 【可验证事实】不能写死「面部一定是 JPEG」。
2. **数据区紧跟一个 file 级 int32 保留字段**：早先少算 4 字节会导致 region 末尾被截断、msgpack 解码越界。修正后数据区**正好覆盖到文件末尾**（22/22 张卡 `region_covers_to_eof = True`）。
3. **lstInfo 块顺序与物理顺序不同**：文件里 `KKEx` 排在第一位，但它的 `pos` 是最大的（物理上在最后）。**必须按 pos 排序，不能按列表顺序**。
4. **数据区内部是「msgpack 对象流 + `[int32 长度][msgpack]` 分帧」的混合体**，还存在嵌套二进制帧。因此解析必须容错重同步，不能假设「一个块 = 一个 msgpack」。

### 1.1 各块语义（实测）

| lstInfo 块名 | 实测内容 | 版本 |
| :--- | :--- | :--- |
| `Custom` | 面部（`shapeValueFace`/`pupil`/`eyeline*`）+ 身体（`shapeValueBody`/`skinId`/`detailId`） | 0.0.0 / 0.0.3 |
| `Coordinate` | 7 套服装槽位数据（衣服/配饰），含内嵌贴图 | 0.0.0 |
| `Parameter` | 角色名 `lastname`/`firstname`/`nickname`、性格、生日等 | 0.0.6 |
| `Status` | 服装状态、`coordinateType` 等 | 0.0.0 |
| `About` | `userID`（作者 id）、`dataID`（存档 id） | 0.0.0 |
| `KKEx` | **插件表**：插件 GUID → 插件数据（含 MOD 依赖表） | 3 |

> **补充（Phase 1.2-B 实测）**：**KK（原版）卡片没有 `About` 块。**
> 样本 `I_.../同名不同目录/old_female/...Kugisaki Nobara_Evaan.png`（marker `【KoiKatuChara】`）
> 的 lstInfo 只有 5 个块（`Coordinate / Custom / KKEx / Parameter / Status`），
> 而同目录的 KKS 版本有 6 个（多出 `About`）。
> 因此 **KK 卡片的 `userID` / `dataID` 不可得**，这是格式差异而非解析失败。

### 1.2 依赖表结构（本报告最关键的发现）

`KKEx` 里 `com.bepis.sideloader.universalautoresolver` 的值是 `[版本, {"info": [...记录]}]`，
每条记录本身又是一段 msgpack，字段实测为：

```text
ModID / Slot / LocalSlot / Property / CategoryNo / Author / Website / Name
```

**【可验证事实】同一条 MOD 会被**逐槽位**记录多次**。例如「美树沙耶香」有 4 条记录，
但 `ModID` 全是 `com.Quokka.sisterveilb` → **唯一 MOD = 1**。

> 这正是「唯一 MOD 数」与「记录条数」必须分开的原因：22 张卡的
> **插件数与唯一 MOD 数与你的清单 100% 吻合**，靠的就是按 `ModID` 去重。

`Property` 字段示例（真实取值）：

```text
ChaFileFace.eyelineUpId
ChaFileFace.Pupil1 / Pupil2
ChaFileBody.detailId
outfit6.ChaFileClothes.ClothesTop / ClothesBot / ClothesPants
outfit6.accessory10.ChaFileAccessory.PartsInfo.id
```

→ **「眼睛 / 皮肤 / 衣服 / 配饰」这些语义存在于 `Property` 里，而不是存在于文件名里。**

---

## A. Sample Inventory

**【可验证事实】** 共 36 个文件（35 个样本 + 1 份清单），10 组。`sha256` 取前 12 位。

### A.1 角色卡（22 张，全部为 PNG 容器）

| # | 路径（相对样本根） | 字节 | sha256 | marker | 卡内角色名 | 插件 | 唯一MOD | 内嵌PNG | 面部图 |
| :--- | :--- | ---: | :--- | :--- | :--- | ---: | ---: | ---: | :--- |
| 1 | A_普通角色卡_无MOD/碧蓝航线 - 罗德尼.png | 233763 | 25926ac2ce05 | KoiKatuCharaSun | HMSRodney | 1 | 0 | 0 | PNG |
| 2 | A_普通角色卡_无MOD/魔法少女小圆 - 鹿目圆.png | 157358 | f88d0ba483a1 | KoiKatuCharaSun | 鹿目まどか | 2 | 0 | 0 | JPEG |
| 3 | B_带MOD角色卡/魔法少女小圆 - 美树沙耶香.png | 159955 | 2a53906505f5 | KoiKatuCharaSun | 美樹さやか | 2 | 1 | 0 | JPEG |
| 4 | B_带MOD角色卡/魔法少女小圆 - 佐仓杏子.png | 169212 | 78185642e67e | KoiKatuCharaSun | 佐倉杏子 | 2 | 3 | 0 | JPEG |
| 5 | C_自定义眼睛/没有黄段子的无聊世界 - 华城绫女.png | 246701 | 07a31990e623 | KoiKatuCharaSun | KajoAyame | 2 | 1 | 0 | PNG |
| 6 | C_自定义眼睛/天结堡主 - 岚燐结骑.png | 423851 | ad4f1db639b7 | KoiKatuCharaSun | 嵐燐結騎 | 2 | 1 | 0 | PNG |
| 7 | D_皮肤身体贴图/政宗君的复仇 - 安达垣爱姬.png | 294316 | d08f5e9d7b7f | KoiKatuCharaSun | 安達垣愛姫 | 2 | 1 | 0 | PNG |
| 8 | D_皮肤身体贴图/请问您今天要来点兔子吗 - 保登心爱.png | 478953 | 26944051dfdd | KoiKatuCharaSun | 保登心愛 | 4 | 2 | 7 | PNG |
| 9 | E_角色加衣服MOD/青春猪头少年系列 - 古贺朋绘.png | 271897 | 42bd3c8cf2b1 | KoiKatuCharaSun | 古賀朋絵 | 2 | 1 | 0 | PNG |
| 10 | E_角色加衣服MOD/不死者之王 - 夏提雅 布拉德弗伦.png | 434722 | 7ea434070336 | KoiKatuCharaSun | 夏提雅·布拉德弗伦 | 3 | 1 | 0 | PNG |
| 11 | F_同作者多角色/Koikatu_F_..._Hermione_Evaan.png | 3994829 | 33feaea0ef88 | KoiKatuCharaSun | GrangerHermione | 17 | 20 | 10 | PNG |
| 12 | F_同作者多角色/Koikatu_F_..._Tatsumaki_Evaan.png | 11901737 | 3f8f29f386c1 | KoiKatuCharaSun | Tatsumaki | 19 | 19 | 10 | PNG |
| 13 | F_同作者多角色/Koikatu_F_..._Kugisaki Nobara_Evaan.png | 7671306 | ee44ba20c191 | KoiKatuCharaSun | KugisakiNobara | 18 | 13 | 17 | PNG |
| 14 | H_共享MOD多角色/明日方舟 - 红豆.png | 474952 | 09c413784595 | KoiKatuCharaSun | 新倉ようこ | 10 | 26 | 1 | PNG |
| 15 | H_共享MOD多角色/FATE - 长尾景虎.png | 617327 | d2a8084b7a56 | KoiKatuCharaSun | KagemitsuNagao | 10 | 25 | 0 | PNG |
| 16 | I_.../同名不同时间戳/..._140632481_Higashiyama Kobeni.png | 481250 | fe62d0c571af | KoiKatuCharaSun | HigashiyamaKobeni | 14 | 42 | 0 | PNG |
| 17 | I_.../同名不同时间戳/..._140632862_Higashiyama Kobeni.png | 481250 | 6bbe6b195ba1 | KoiKatuCharaSun | HigashiyamaKobeni | 14 | 42 | 0 | PNG |
| 18 | I_.../同名不同目录/female/Koikatu_F_..._Kugisaki Nobara_Evaan.png | 7671306 | ee44ba20c191 | KoiKatuCharaSun | KugisakiNobara | 18 | 13 | 17 | PNG |
| 19 | I_.../同名不同目录/old_female/Koikatu_F_..._Kugisaki Nobara_Evaan.png | 7660027 | 874367419c2e | **KoiKatuChara** | KugisakiNobara | 17 | 13 | 17 | PNG |
| 20 | I_文件名混乱重名/混乱命名/[Yeeted] Sora .png | 6711474 | 155876d26ca7 | KoiKatuCharaSun | IkushimaSora | 14 | 17 | 22 | PNG |
| 21 | I_文件名混乱重名/混乱命名/KK_317794.png | 417069 | e9e21708b84d | KoiKatuCharaSun | HigashiyamaKobeni | 12 | 43 | 0 | PNG |
| 22 | J_复杂完整角色/刀剑神域 - 绀野木棉季.png | 9792516 | bca0f33123a2 | KoiKatuCharaSun | ユウキ | 21 | 31 | 120 | PNG |

> 第 13 与第 18 行 `sha256` 完全相同 → **跨目录的同一份文件**（见 C 组分析）。
> 第 11/12 行路径中的 `...` 为省略的时间戳段，完整名见原始目录。

### A.2 MOD（13 个 zipmod，全部是 zip 且含 `manifest.xml`）

| # | 路径（相对） | 字节 | sha256 | GUID | name | author | version |
| :--- | :--- | ---: | :--- | :--- | :--- | :--- | :--- |
| 1 | B_带MOD角色卡/MOD/[Quokka] Sister Veil b 1.0.zipmod | 755562 | daa6afd4cd21 | com.Quokka.sisterveilb | Sister_veil_b | Quokka | 1.0 |
| 2 | B_带MOD角色卡/MOD/[Quokka] Accessory Cross Staff 1.0.zipmod | 278860 | 0190d60893e9 | com.Quokka.crossstaff | Cross_staff | Quokka | 1.0 |
| 3 | B_带MOD角色卡/MOD/[Quokka] China Dress Top 1.0.zipmod | 896314 | c642b6f8b3f7 | com.Quokka.chinadresstop | China_dress_top | Quokka | 1.0 |
| 4 | C_自定义眼睛/mod/[GF] Character Texture Pack v1.7.3.zipmod | 6300854 | 45dbf8658c2a | com.gf.collection | GF mods | GF | 1.7.3 |
| 5 | C_自定义眼睛/mod/[RCL_circuit] Ranrin-Yuiki ....zipmod | 16169745 | fee26f587b3d | RCL_circuit.Mod.RanrinYuiki | Ranrin-Yuiki Amayui Castle Meister | RCL_circuit | 1.0 |
| 6 | D_皮肤身体贴图/MOD/[Blanketman] Additional Skin Pack v2.3.zipmod | 5046334 | b70f3ae67c75 | com.Blanketman.AdditionalSkinMod | Additional Skin Pack | Blanketman | 2.3 |
| 7 | E_角色加衣服MOD/MOD/[essu] shinyBunny v1.zipmod | 3185898 | 22c1c81a3938 | shinyBunny | shinyBunny | essu | 1.0 |
| 8 | E_角色加衣服MOD/MOD/[Quokka] Classic Maid Skirt 1.0.zipmod | 2287606 | b0a79fb8c284 | com.Quokka.classicmaidskirt | Classic_maid_skirt | Quokka | 1.0 |
| 9 | F_同作者多角色/MOD/[ryo2003] VanillaEx Stiletto1 v1.0.zipmod | 222743 | d919a9f83542 | ryo2003.stiletto | VanillaEx Stiletto | ryo2003 | 1.0 |
| 10 | G_孤立MOD_无角色卡/MOD/NoHair.zipmod | 1408 | fbbe1eab3e4a | NoHair | NoHair Head | *(空)* | 0 |
| 11 | G_孤立MOD_无角色卡/MOD/[ucklline] Elven Panst.zipmod | 1473 | 960978dfa994 | elven_panst | elven_panst | ucklline | 1.5 |
| 12 | G_孤立MOD_无角色卡/MOD/[Unknown] koikatu.AltSlot.co_bot_19.zipmod | 1251 | b8c83eac9bb8 | koikatu.AltSlot.co_bot_19 | koikatu.AltSlot.co_bot_19 | Unknown | 1.0 |
| 13 | H_共享MOD多角色/MOD/[Quokka] Accessory Naginata 1.0.zipmod | 2377088 | 23ae4740684a | com.Quokka.naginata | Naginata | Quokka | 1.0 |

**【可验证事实】** 13/13 个 zipmod 都含 `manifest.xml`；GUID 与你清单里写的映射**逐条一致**。

**【可验证事实】数据质量边界情况**：`NoHair.zipmod` 的 `author` 为空、`version` 为 `0`；
`KOIKATU.CHARAMAKER...` 这类 GUID 大小写不统一（如 `RCL_circuit.Mod.RanrinYuiki`、
`koikatu.AltSlot.co_bot_19`、`shinyBunny`）→ **GUID 不能假设全小写或全为点分格式**。

---

## B. 每个样本的详细分析（A–J）

每组格式：**用户声明 → 实际验证 → 是否一致 → Scanner 能否自动识别 → 备注**。

### A. 普通角色卡_无MOD

#### A-1 `碧蓝航线 - 罗德尼.png`

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | 角色名 HMSRodney；KoiKatuCharaSun；233,763 字节；内嵌贴图 0；插件 1；唯一 MOD 0 |
| 【可验证事实】 | 字节 233,763；marker `【KoiKatuCharaSun】`；`Parameter.lastname/firstname` → **HMSRodney**；KKEx 键仅 `moreAccessories`（1 个）；无 sideloader 键 → 依赖记录 0；数据区 PNG 签名 0 |
| 是否一致 | **完全一致** |
| Scanner 可自动识别 | 类型 / 名字 / 插件数 / 唯一 MOD 数 / 内嵌贴图数 —— 全部可 |
| 备注 | 面部预览图是 **PNG**（不是 JPEG）。卡片**没有** sideloader 键，说明「0 依赖」有两种形态：无键 或 有空列表 |

#### A-2 `魔法少女小圆 - 鹿目圆.png`

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | 角色名 鹿目まどか；KoiKatuCharaSun；157,358 字节；内嵌贴图 0；插件 2；唯一 MOD 0 |
| 【可验证事实】 | 全部吻合；KKEx = `{com.bepis.sideloader.universalautoresolver, moreAccessories}`；sideloader 值 `[0, {"info": []}]` → **空列表**；`About.userID`=`c43c4055-…`、`dataID`=`07ee7d46-…`；面部图 JPEG |
| 是否一致 | **完全一致** |
| Scanner 可自动识别 | 全部可 |
| 备注 | 【推测/待验证】面部 `eyelineUpId = 1900`、`pupil.id = 35` 属于高位 id，看起来像 MOD 槽位，但该卡 sideloader 列表为空。**该 id 是否真由 MOD 提供，证据不足**，需要一张「确定使用 MOD 眼线」的对照卡才能定论 |

### B. 带MOD角色卡

#### B-1 `魔法少女小圆 - 美树沙耶香.png`

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | カ美樹さやか；159,955 字节；插件 2；唯一 MOD 1 = `com.Quokka.sisterveilb` |
| 【可验证事实】 | 吻合。依赖表 **4 条记录**，但 `ModID` 全为 `com.Quokka.sisterveilb` → 唯一 MOD = 1。`Property` 指向 `outfit6.accessory10/11/12` 与 `outfit2.accessory1` |
| 是否一致 | **一致** |
| Scanner 可自动识别 | ✅ 唯一 MOD 数必须按 `ModID` 去重；✅ 用到的槽位可从 `Property` 取出 |
| 备注 | **「1 个 MOD 被 4 个槽位引用」** —— 这条关系如果只存 `ref_count=4` 会丢失「用在哪」 |

#### B-2 `魔法少女小圆 - 佐仓杏子.png`

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | 佐倉杏子；169,212 字节；插件 2；唯一 MOD 3 = `com.Quokka.chinadresstop`、`com.Quokka.crossstaff`、`com.ymgpt.acc_earrings_top` |
| 【可验证事实】 | 吻合。5 条记录 → 去重后正好这 3 个 GUID，`Property` 分别落在 `outfit5/outfit6.ChaFileClothes.ClothesTop`、`outfit6.accessory10/11`、`outfit6.accessory15` |
| 是否一致 | **一致** |
| Scanner 可自动识别 | ✅ |
| 备注 | **缺失依赖实测**：`com.ymgpt.acc_earrings_top` 在样本目录里**没有对应 zipmod**。这验证了 v1 schema 「主键用 `mod_guid`、`mod_id` 可为 NULL」的设计是必需的 |

### C. 自定义眼睛

#### C-1 `没有黄段子的无聊世界 - 华城绫女.png`

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | KajoAyame；246,701 字节；插件 2；唯一 MOD 1 = `com.gf.collection`；瞳孔/上下眼线贴图来自 MOD |
| 【可验证事实】 | 吻合。3 条记录同一 GUID，`Property` 实测为 **`ChaFileFace.eyelineUpId`、`ChaFileFace.Pupil1`、`ChaFileFace.Pupil2`** —— 与声明里的字面描述完全对上 |
| 是否一致 | **一致** |
| Scanner 可自动识别 | ✅ **「这是眼睛资源」可以从 `Property` 前缀 `ChaFileFace.` 可靠判定**（不是靠文件名） |
| 备注 | 文件名含「没有黄段子的无聊世界」（动漫名），与「眼睛」毫无关系 —— 靠文件名必然误判 |

#### C-2 `天结堡主 - 岚燐结骑.png`

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | 嵐燐結騎；423,851 字节；插件 2；唯一 MOD 1 = `RCL_circuit.Mod.RanrinYuiki` |
| 【可验证事实】 | 吻合。**13 条记录 → 去重后 1 个 GUID**；其中 3 条是面部（同上三个 `Property`），其余落在服装/配饰槽位 |
| 是否一致 | **一致** |
| Scanner 可自动识别 | ✅ |
| 备注 | 同一个 MOD 同时提供眼睛 + 服装时，「资源类型」不能只给一个标签 —— 需要**多槽位**表达 |

### D. 皮肤身体贴图

#### D-1 `政宗君的复仇 - 安达垣爱姬.png`

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | 安達垣愛姫；294,316 字节；插件 2；唯一 MOD 1 = `com.Blanketman.AdditionalSkinMod`；贴图来自 `ChaFileBody.detailId` |
| 【可验证事实】 | 吻合。唯一 1 条记录，`Property` 实测 `ChaFileBody.detailId` |
| 是否一致 | **一致** |
| Scanner 可自动识别 | ✅ 身体/皮肤语义可由 `ChaFileBody.` 前缀判定 |
| 备注 | 内嵌贴图 0，但依赖皮肤 MOD —— **「用了皮肤 MOD」与「卡内自带皮肤贴图」是两件不同的事** |

#### D-2 `请问您今天要来点兔子吗 - 保登心爱.png`

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | 保登心愛；478,953 字节；内嵌贴图 7；插件 4；唯一 MOD 2 = `com.Blanketman.AdditionalSkinMod`、`com.Blanketman.NonLightStockings` |
| 【可验证事实】 | 全部吻合：插件 4（多出 `KSOX`、`KCOX` 两个贴图类插件）；内嵌贴图 **7**；两条依赖记录分别落在 `ChaFileBody.detailId` 与 `outfit6.ChaFileClothes.ClothesPants` |
| 是否一致 | **一致** |
| Scanner 可自动识别 | ✅ 内嵌贴图数可（数据区 PNG 数） |
| 备注 | ① 卡里有皮肤 MOD 依赖 **同时** 有 7 张内嵌贴图，两类信息并存；② `com.Blanketman.NonLightStockings` **在样本里没有对应 zipmod** → 又一个缺失依赖实例；③ `KSOX`/`KCOX` 插件内部也存有 PNG 贴图（【可验证事实】：KSOX 值里含 `EyeOver` → PNG 字节） |

### E. 角色加衣服MOD

#### E-1 `青春猪头少年系列 - 古贺朋绘.png`

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | 古賀朋絵；271,897 字节；插件 2；唯一 MOD 1 = `shinyBunny` |
| 【可验证事实】 | 吻合。`Property` = `outfit6.ChaFileClothes.ClothesTop` |
| 是否一致 | **一致** |
| Scanner 可自动识别 | ✅ `outfit{N}.ChaFileClothes.Clothes*` → 服装 |
| 备注 | MOD GUID `shinyBunny` **不含点、看起来像普通名字**，但它是合法 zipmod GUID（manifest 实测）。**不能用「是否点分」来判断是不是 MOD** |

#### E-2 `不死者之王 - 夏提雅 布拉德弗伦.png`

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | 夏提雅·布拉德弗伦；434,722 字节；插件 3；唯一 MOD 1 = `com.Quokka.classicmaidskirt` |
| 【可验证事实】 | 吻合。2 条记录 → 1 个 GUID，`Property` = `outfit3.…ClothesBot` 与 `outfit6.…ClothesBot` |
| 是否一致 | **一致** |
| Scanner 可自动识别 | ✅ |
| 备注 | 角色名含特殊字符「·」，`nickname`/`firstname` 与显示名一致 —— 需确认展示名用哪一个（【待验证】Phase 1.4 的展示策略） |

### F. 同作者多角色

| 文件 | 声明插件/MOD/贴图 | 实测 | 一致 |
| :--- | :--- | :--- | :--- |
| Hermione_Evaan | 17 / 20 / 10 | 17 / 20 / 10 | ✅ |
| Tatsumaki_Evaan | 19 / 19 / 10 | 19 / 19 / 10 | ✅ |
| Kugisaki Nobara_Evaan | 18 / 13 / 17 | 18 / 13 / 17 | ✅ |

**【可验证事实】作者字段来源明确**：三张卡的 `KKEx["marco.authordata"]` 实测为
`{"Authors": <msgpack>}`，解出 `['[Unknown]', 'Evaan']` —— 与声明「卡作者：[Unknown], Evaan」**完全一致**。

| 项 | 内容 |
| :--- | :--- |
| Scanner 可自动识别 | ✅ 作者可从 `marco.authordata` 插件读取；✅ 三张卡共享同一作者 → 可按作者聚合 |
| 备注 | ① `[Unknown]` 是**哨兵值**，聚合时必须过滤或降权，否则会把大量无关卡归到同一「作者」；② 作者是**列表**（可多人），而 v1 schema 的 `resources.author` 是单个文本字段 —— **需要表达多个作者**；③ `ryo2003.stiletto` 在 F 组有 zipmod，但实测只被 Tatsumaki / 两张 Kobeni / KK_317794 引用，**不被 Hermione 与 Kugisaki 引用** → 「放在同一目录」≠「被引用」 |

### G. 孤立MOD_无角色卡

| 文件 | 声明 GUID | 实测 GUID | 被多少张卡引用 |
| :--- | :--- | :--- | ---: |
| NoHair.zipmod | NoHair | `NoHair` | **0** |
| [ucklline] Elven Panst.zipmod | elven_panst | `elven_panst` | **0** |
| [Unknown] koikatu.AltSlot.co_bot_19.zipmod | koikatu.AltSlot.co_bot_19 | `koikatu.AltSlot.co_bot_19` | **0** |

| 项 | 内容 |
| :--- | :--- |
| 是否一致 | **一致**（3/3 在全部 22 张卡里都没有被引用） |
| Scanner 可自动识别 | ✅ 「有 MOD、无角色引用」= 孤立 MOD，可直接从反向索引得出 |
| 备注 | 这组的 `manifest.xml` 本身也是**最小样本**（1.2–1.5 KB 的 zipmod）：说明存在「只有 manifest、几乎没有内容」的 MOD |

### H. 共享MOD多角色

| 项 | 红豆 | 长尾景虎 |
| :--- | :--- | :--- |
| 【用户声明】 | 新倉ようこ；474,952；插件 10；MOD 26；贴图 1 | KagemitsuNagao；617,327；插件 10；MOD 25；贴图 0 |
| 【可验证事实】 | **全部一致** | **全部一致** |
| 共享 MOD | `com.Quokka.naginata` @ `outfit0.accessory4.ChaFileAccessory.PartsInfo.id` | `com.Quokka.naginata` @ `outfit4.accessory56.ChaFileAccessory.PartsInfo.id` |
| 是否一致 | **一致**：同一个 MOD 被两张卡引用，且用在**不同槽位** | |
| Scanner 可自动识别 | ✅ 反向关联（MOD → 多角色）可由依赖表构建 | |
| 备注 | 全样本共出现 **144 个唯一 MOD GUID**；被 ≥2 张卡共享的有多个，例如 `com.Blanketman.AdditionalSkinMod` 被 **12 张卡**使用、`moderchan.CharamakerSupportMOD` 12 张、`yamadamod.nohairB` 12 张 —— 共享是**常态而非特例** |

### I. 文件名混乱重名

#### I-1 同名不同时间戳（两张 Kobeni）

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | 两张同名；角色名 HigashiyamaKobeni；481,250 字节；贴图 0；插件 14；MOD 42 |
| 【可验证事实】 | 元数据全部一致；`size` 完全相同；**`quick_hash` 完全相同**；**`sha256` 不同**；逐字节比对：**仅 25 个字节不同，集中在一段 36 字节区间** |
| 差异位置 | 实测差异正好落在 `About.dataID`：<br>A = `7ccadc8f-ea05-4b02-8966-…`，B = `921d7ce6-e2ae-431d-aba0-…` |
| 是否一致 | 一致（时间戳不同、其他相同） |
| Scanner 可自动识别 | ⚠️ **这是本样本集最重要的技术风险**：轻量指纹会把它们判为同一文件（假阳性），sha256 又会判为「不同」（对用户语义而言是假阴性） |
| 备注 | `dataID` 每次保存都会变（【推测/待验证】需再验证），所以它**不能**当身份标识，也**不能**用来判重 |

#### I-2 同名不同目录（三张 Kugisaki）

| 位置 | marker | 字节 | 插件 | MOD | sha256 |
| :--- | :--- | ---: | ---: | ---: | :--- |
| F_同作者多角色/ | KoiKatuCharaSun | 7671306 | 18 | 13 | `ee44ba20c191…` |
| I_…/同名不同目录/female/ | KoiKatuCharaSun | 7671306 | 18 | 13 | `ee44ba20c191…`（**与 F 组完全相同**） |
| I_…/同名不同目录/old_female/ | **KoiKatuChara** | 7660027 | 17 | 13 | `874367419c2e…` |

| 项 | 内容 |
| :--- | :--- |
| Scanner 可自动识别 | ✅ 真重复（sha256 相同）可识别；✅ 跨游戏版本（marker 不同）可识别 |
| 备注 | 「同一角色、两个游戏版本（KK / KKS）」是真实存在的形态。**marker 不同 = 不能当作同一份文件的重复**，但属于同一角色的版本族 |

#### I-3 混乱命名

| 文件 | 【用户声明】 | 【可验证事实】 | 备注 |
| :--- | :--- | :--- | :--- |
| `[Yeeted] Sora .png` | IkushimaSora；6,711,474；插件 14；MOD 17；贴图 22 | 全部一致 | 文件名只有 `Sora`，且有**前导方括号 + 空格 + 扩展名前空格**；卡内真名 `IkushimaSora` |
| `KK_317794.png` | HigashiyamaKobeni；417,069；插件 12；MOD 43；作者 Azurou | 全部一致 | 文件名**完全不含角色名**，全靠数字；作者列表**只有 `['Azurou']`**（另两张 Kobeni 是 `['Azurou','Anonymous']`） |

| 项 | 内容 |
| :--- | :--- |
| 是否一致 | 一致 |
| Scanner 可自动识别 | ✅ 名字/作者必须从卡内读，不能信文件名 |
| 备注 | 同一角色 `HigashiyamaKobeni` 在本样本里出现 **3 次**（两张时间戳卡 + KK_317794），三者插件数/MOD 数都不同（14/42、14/42、12/43）→ **「同一角色」不等于「同一张卡」** |

### J. 复杂完整角色

#### J-1 `刀剑神域 - 绀野木棉季.png`

| 项 | 内容 |
| :--- | :--- |
| 【用户声明】 | ユウキ；9,792,516 字节；内嵌贴图 120；插件 21；MOD 31；作者 Anonymous |
| 【可验证事实】 | 全部一致：marker KoiKatuCharaSun；`Parameter` → ユウキ；插件 21；唯一 MOD 31（220 条记录）；数据区 PNG 120 张；`marco.authordata` → `['Anonymous']` |
| 是否一致 | **完全一致** |
| Scanner 可自动识别 | ✅ 全部可 |
| 备注 | **220 条记录 → 31 个唯一 MOD**，去重比 7.1:1。若不去重，MOD 统计会严重虚高。文件 9.8 MB 中约 7.9 MB 是 `TextureDictionary` 贴图数据 |

---

## C. Ground Truth 草案

下表是**基于实测**建立的 Ground Truth 草案（不是照抄清单）。
「Scanner 应能识别」列 = Phase 1.2 最低要求。

| 组 | 实际包含的资源 | 类型判定依据 | 可验证关系 | Scanner 应能识别 |
| :--- | :--- | :--- | :--- | :--- |
| **A** | 2 张角色卡；0 个 MOD 文件 | marker `【KoiKatuCharaSun】` | 鹿目圆有 sideloader 键但列表为空；罗德尼无 sideloader 键 | 类型=角色卡；名字；插件数；唯一MOD=0（两种空形态都要处理） |
| **B** | 2 张角色卡 + 3 个 zipmod | marker + manifest GUID | 沙耶香→`sisterveilb`(×4槽位)；杏子→`chinadresstop`/`crossstaff`/`ymgpt.acc_earrings_top`(其中 1 个**无 zipmod**) | 唯一MOD去重；槽位来源；**缺失依赖标记** |
| **C** | 2 张角色卡 + 2 个 zipmod | marker + manifest GUID | 面部三属性 `ChaFileFace.eyelineUpId`/`Pupil1`/`Pupil2` 指向 MOD | 把「眼睛」判定为**槽位语义**而非文件类型 |
| **D** | 2 张角色卡 + 1 个 zipmod | marker + manifest GUID | `ChaFileBody.detailId` → 皮肤 MOD；心爱另有 `NonLightStockings`(**无 zipmod**) 与 7 张内嵌贴图 | 区分「依赖皮肤MOD」与「卡内自带贴图」 |
| **E** | 2 张角色卡 + 2 个 zipmod | marker + manifest GUID | `outfit{N}.ChaFileClothes.ClothesTop/ClothesBot/ClothesPants` → 服装 MOD | 服装槽位 → MOD 的映射 |
| **F** | 3 张角色卡 + 1 个 zipmod | marker + manifest GUID + `marco.authordata` | 三张卡同为作者 `Evaan`（`[Unknown]` 为哨兵）；`ryo2003.stiletto` 在本组存在但**不被这三张卡引用** | 多作者解析；按作者聚合；「目录里有 MOD ≠ 被引用」 |
| **G** | 3 个 zipmod，**0 张角色卡** | manifest GUID | 三个 GUID 在 22 张卡中出现 **0 次** | 孤立 MOD 识别（有 mod、无引用） |
| **H** | 2 张角色卡 + 1 个 zipmod | marker + manifest GUID | `com.Quokka.naginata` 被两张卡引用，槽位不同（`outfit0.accessory4` / `outfit4.accessory56`） | 反向关联 MOD→多角色；共享计数 |
| **I** | 6 张角色卡 | marker + sha256 + Parameter | ① Kobeni ×2：仅 `dataID` 差 25 字节；② Kugisaki ×2：sha256 **完全相同**（跨目录真重复）；③ Kugisaki KK 版：marker 不同；④ 同角色 `HigashiyamaKobeni` 共 3 张卡（14/42、14/42、12/43） | 真重复判定；近重复判定；**不得用文件名/时间戳判重** |
| **J** | 1 张角色卡 | marker + manifest GUID | 220 条依赖记录 → 31 个唯一 MOD；120 张内嵌贴图 | 高复杂度下的去重与性能 |

### C.1 Ground Truth 的「不可断言」部分

以下**明确写进 Ground Truth 作为未决项**，避免以后被当成已知事实：

- 22 张卡中「内嵌贴图」的业务含义尚未定义（只能确认「数据区含 N 张 PNG」）。
  无法断言它们属于眼睛/皮肤/衣服中的哪一类。
- 卡内 `Pupil1/Pupil2/eyelineUpId` 的高位 id 是否**总是**来自 MOD，未验证。
- 各 zipmod 的**内容**（衣服/配饰/皮肤）只从 manifest 的 name/author 得到，
  尚未验证 zipmod 内部是否声明它占用哪个槽位。

---

## D. 资源类型分类候选

### D.1 可以从字节**可靠**判定的（建议 Phase 1.2 做）

| 候选类型 | 判定依据（实测可行） | 置信 |
| :--- | :--- | :--- |
| `character_card` | PNG 尾部 marker = `【KoiKatuCharaSun】` / `【KoiKatuChara】` | 高（L1 级） |
| 卡片所属游戏/格式 | marker 字符串本身（Sun / 非 Sun） | 高 |
| `mod`（zipmod） | zip 且含 `manifest.xml`，可读出 `guid` | 高（L2 级） |
| `plugin`（非 MOD） | KKEx 键，且该 GUID **不在**任何 zipmod 的 manifest 里 | 中高 |
| 内嵌贴图数量 | 数据区内 PNG 签名计数（**22/22 与声明一致**） | 高 |
| 孤立 MOD | MOD 存在但无任何卡片引用 | 高 |
| 缺失依赖 | 卡片依赖的 GUID 在本地 MOD 库中不存在 | 高 |

### D.2 只能作为**槽位语义**（不是文件类型）的

| 语义 | 判定依据 | 说明 |
| :--- | :--- | :--- |
| 眼睛 | `Property` 前缀 `ChaFileFace.`（`Pupil1/2`、`eyelineUpId`…） | 属于「卡 × MOD @ 槽位」的标签 |
| 皮肤 / 身体 | `Property` 前缀 `ChaFileBody.` | 同上 |
| 衣服 | `Property` 含 `.ChaFileClothes.Clothes(Top/Bot/Pants)` | 同上 |
| 配饰 | `Property` 含 `.ChaFileAccessory.PartsInfo.id` | 同上 |
| 头发 | `Property` 含 `ChaFileHair` / 相关槽位（本样本出现 `HeadMod`） | **【待验证】** 样本中未直接观测到该前缀 |

> **这是本报告最重要的架构结论**：
> 「眼睛 / 皮肤 / 衣服 / 配饰」在真实数据里是**卡片与 MOD 的关系属性**，
> 不是某个 PNG 文件的类型。把 PNG 文件强行分类成 `eyes`/`skin` 会与真实结构错位。

### D.3 当前**不建议**自动判定的

- ❌ 把一个独立 PNG 判为「眼睛资源 / 皮肤资源」—— 样本中不存在这类独立文件，无从验证。
- ❌ 用 MOD 文件名（`[GF] Character Texture Pack`）推断内容类型 —— 名字与实际用途不符（GF 包在本样本里用于**眼线/瞳孔**）。
- ❌ 用目录名推断类型（`C_自定义眼睛/mod/` 里放的是通用贴图包）。
- ❌ 用 MOD GUID 是否点分判断是不是 MOD（`shinyBunny` 反例）。

---

## E. 资源关系模型（实测支撑）

```text
角色卡 ──1:N──► 依赖记录 (每槽位一条) ──N:1──► MOD(guid)
   │                     │
   │                     └─ Property = 槽位路径（眼睛/皮肤/衣服/配饰语义在这里）
   │
   ├──1:N──► 插件 (KKEx 键；多数不是 MOD)
   ├──1:N──► 内嵌贴图 (数据区 PNG，只知数量)
   ├──N:M──► 作者 (marco.authordata，可多人，含 [Unknown] 哨兵)
   └──N:M──► 重复组 (sha256 真重复 / 近重复)

MOD(guid) ──N:M──► 角色卡   （反向：一 MOD 被多角色共享；实测最高 12 张卡共用 1 个 MOD）
```

**实测到的具体关系形态（可直接作为测试断言）：**

| 形态 | 实例 | 期望的 Scanner 行为 |
| :--- | :--- | :--- |
| 一个角色 → 多个 MOD | 佐仓杏子 → 3 个 | 生成 3 条唯一关系 |
| 一个 MOD → 多个槽位（同一角色） | 沙耶香 `sisterveilb` ×4 槽位 | 1 条唯一关系 + 保留 4 处槽位 |
| 一个 MOD → 多个角色 | `naginata` → 红豆 + 长尾景虎；`AdditionalSkinMod` → 12 张卡 | 反向索引能列出全部卡片 |
| 一个 MOD → 跨类别槽位 | 岚燐结骑：同一 MOD 同时用于面部与服装 | 关系可带多个槽位语义 |
| 依赖但未安装 | `ymgpt.acc_earrings_top`、`NonLightStockings` | 关系存在、`mod_id` 为空、标记「缺失」 |
| MOD 存在但无人用 | G 组 3 个 | 标记孤立 MOD |
| 完全重复（跨目录） | Kugisaki：F 组 = female 组 | 同一文件只入库一次（`file_path_key` 唯一） |
| 近重复（仅 dataID 不同） | 两张 Kobeni | 建议组，不自动合并 |

---

## F. Phase 1.2 Scanner 必须解决的问题

按优先级排列，每条都有实测依据。

**F1（阻塞级）非 ASCII / 特殊文件名**
样本里 22 张卡**全部**是中文或日文名，含空格、`·`、`[` `]`、甚至「扩展名前有空格」（`[Yeeted] Sora .png`）。
→ 必须用 UTF-8 正确处理路径，不能用 locale 编码；`relative_path` 要原样保留。

**F2（阻塞级）解析必须容错，且不能假设分帧**
数据区是 msgpack 对象流 + `[int32 长度][msgpack]` 混合分帧，还有嵌套二进制帧。
→ 「一个块 = 一个 msgpack」的假设会在多数卡上直接失败。

**F3（阻塞级）lstInfo 必须按 pos 排序**
实测 `KKEx` 在列表里排第一但物理位置在最后。
→ 按列表顺序读会把数据块错位（本报告正是踩过这个坑）。

**F4（阻塞级）文件级 int32 保留字段**
数据区前有 1 个 int32 保留字段（实测=0）。少读 4 字节会导致数据区末尾截断、解码越界。

**F5（高）唯一 MOD 必须按 ModID 去重**
220 条记录 → 31 个唯一 MOD（7.1:1）。不去重会让 MOD 统计严重虚高。

**F6（高）区分「插件」与「MOD」**
卡片有 1–21 个**插件**（`moreAccessories`、`KSOX`、`KCOX`、`marco.authordata`…），
但它们**不是** zipmod，没有 manifest。只有 sideloader 表里的 ModID 才是 MOD 依赖。

**F7（高）判重不能用轻量指纹、不能用文件名**
实测反例：两张 Kobeni `size` 与 `quick_hash` 完全相同但内容差 25 字节；
Kugisaki 两份 `sha256` 完全相同但路径不同；同角色 `HigashiyamaKobeni` 有 3 张不同的卡。

**F8（高）增量扫描的判定字段**
样本中「两张 Kobeni」时间戳不同、内容差 25 字节 —— 仅靠 `(path,size,mtime)` 足够（mtime 不同），
但**若同一文件被重新保存而 mtime 未变**，就会漏更新。【待验证】需真实场景验证。

**F9（中）跨游戏版本**
同一角色存在 `【KoiKatuChara】`(KK) 与 `【KoiKatuCharaSun】`(KKS) 两个版本，
插件数 17 vs 18、字节数 7660027 vs 7671306。
→ 要在数据里保留 marker，不能把两者当成同一份文件。

**F10（中）zipmod 与 zip 的区分**
13 个 zipmod 全是 zip；但**并非所有 zip 都是 zipmod**（Phase 2 问题，此处登记）。
判定依据应为「zip 内存在 `manifest.xml`」。

**F11（中）性能**
单卡最大 11.9 MB（其中 7.9 MB 是内嵌贴图），22 张合计约 76 MB。
→ 首批扫描必须走事务批量写入（Phase 1.1 已备好 `db.transaction`），
且**不要**在首扫默认计算全量 sha256（用户既有约束）。

**F12（中）数据质量兜底**
实测遇到：`author` 为空、`version` 为 `0`、GUID 大小写不一、`[Unknown]` 哨兵作者。
→ 不能因为字段缺失就判定解析失败。

---

## G. 当前无法可靠识别的信息

以下各项**证据不足，需要额外样本 / 实验 / 解析器支持**，Phase 1.2 不得猜测实现：

| # | 无法确定的项 | 已掌握的证据 | 需要什么才能定论 |
| :--- | :--- | :--- | :--- |
| G1 | ~~「内嵌贴图」的业务含义~~ **【已解决】** | 见 §0.1：与 `probe_cards.py` 的口径交叉验证一致 = 数据区 PNG 数 | 已确认，可写入测试断言 |
| G2 | 内嵌贴图属于哪一类（眼睛/皮肤/衣服） | 贴图混在 Coordinate/Custom 与 KSOX/KCOX 等插件里 | 需要能定位「贴图 ↔ 部件」的样本或解析器 |
| G3 | `Pupil1/2`、`eyelineUpId` 高位 id 是否等于「来自 MOD」 | 鹿目圆 eyelineUpId=1900 但 MOD 列表为空 | 一张已知使用 MOD 眼线 + 一张纯原版眼线的对照卡 |
| G4 | `KSOX` / `KCOX` / `materialeditor.TextureDictionary` 的结构语义 | 已确认内部含 PNG 字节；`TextureDictionary` 是嵌套 msgpack | 这些插件的格式文档或更多样本 |
| G5 | zipmod 内部是否声明它提供哪个槽位 | 只读到 manifest 的 guid/name/author/version | 需要检查 zipmod 内其它文件（本阶段未做，属 Phase 2） |
| G6 | 未安装 MOD 的「可推断信息」有多少 | 卡内记录里 `Author`/`Website`/`Name` 实测为 `null` | 需要一张卡片自带 MOD 元数据的样本 |
| G7 | `dataID` 是否每次保存都变 | 两张 Kobeni 只差 `dataID` 25 字节 | 同一角色连续两次保存的实验 |
| G8 | 角色身份是否可用「名字 + 作者」唯一确定 | 同角色 HigashiyamaKobeni 有 3 张不同的卡 | 明确「同一角色」的业务定义 |
| G9 | 面部预览图的格式规律 | 实测 3 张 JPEG / 19 张 PNG | 是否与制作工具或版本相关 |
| G10 | `Coordinate` 块内 7 个槽位的固定含义 | 观测到 `outfit0..outfit6` 共 7 组 | 确认索引→槽位名映射表 |
| G11 | 加密 zipmod 的处理 | `index_zipmods.py` 注释指出「部分 zipmod 带密码，读不到 manifest」；本样本 13 个**全部未加密** | 需要 1 个加密 zipmod 样本 |
| G12 | 超过 7 套服装（DLC 追加槽位） | 本样本全部为 `outfit0..outfit6` | 需要含追加服装槽位的样本 |

---

## H. Phase 1.2 Scanner MVP 建议

> 只做「扫描 + 卡片识别 + 入库」，**不做** UI、不做 MOD 内容解析、不做文件操作。

### H.1 建议的解析流水线

```text
遍历 Library 根目录（只读）
   ↓ 按扩展名/魔数筛候选（.png / .zipmod / .zip）
   ↓ 增量判定 (file_path_key, file_size, modified_time) → 跳过未变
   ↓
PNG: 读 PNG 块 → 找 IEND → 解析尾部容器
       ├ marker  → 类型 (character_card 等) + 游戏版本
       ├ lstInfo → 记录块清单
       ├ Parameter → 角色名
       ├ About    → userID / dataID
       ├ KKEx     → 插件表 + sideloader 依赖（按 ModID 去重 + 槽位）
       └ 数据区 PNG 计数 → 内嵌贴图数
ZIP: 找 manifest.xml → guid/name/author/version
   ↓ 全部写入内存缓冲
   ↓ 单个事务批量入库（db.transaction）
   ↓ 写入 scan_records 统计
```

### H.2 MVP 必须做到的（可直接用本样本集验收）

| # | 能力 | 验收标准 |
| :--- | :--- | :--- |
| 1 | 类型识别 | 22 张卡全部识别为 `character_card` 且 marker 正确；13 个 zipmod 全部识别为 `mod` |
| 2 | 名字提取 | 22 张卡的名字与清单一致（含日文/中文/含 `·`） |
| 3 | 插件数 | 22/22 与清单一致 |
| 4 | 唯一 MOD 数 | 22/22 与清单一致（去重后） |
| 5 | 内嵌贴图数 | 22/22 与清单一致（数据区 PNG 计数） |
| 6 | 依赖关系 | 生成 (卡 → MOD @ 槽位) 关系；能列出缺 MOD（`ymgpt.acc_earrings_top` 等） |
| 7 | 共享关系 | 能回答「`com.Quokka.naginata` 被哪两张卡使用」 |
| 8 | 孤立 MOD | G 组 3 个 MOD 被标记为无卡片引用 |
| 9 | 真重复 | Kugisaki 的两份（F 组 / I 组 female）被识别为同一文件，只入库一次 |
| 10 | 只读保证 | 扫描后样本目录的所有文件 sha256 不变（可用扫描前后快照对比验证） |

### H.3 MVP 明确**不做**的

- ❌ 不解析内嵌贴图的内容与归属（G1/G2/G4 待定）
- ❌ 不解析 zipmod 内部结构（Phase 2）
- ❌ 不自动判定「眼睛/皮肤/衣服」为资源类型，只作为**槽位标签**记录（D.2）
- ❌ 不做任何文件移动/重命名/删除
- ❌ 不做 UI

---

## I. 测试用例建议

建议直接把本样本集作为夹具（**只读引用**，不复制进仓库）。

### I.1 单元级

| 用例 | 输入 | 期望 |
| :--- | :--- | :--- |
| 容器解析 | 鹿目圆.png | marker/版本/面部长度/lstInfo 6 项 全部正确 |
| 数据区边界 | 任意 22 张卡 | `region` 恰好覆盖到文件末尾（`region_covers_to_eof`） |
| 分帧容错 | 心爱.png（7 张内嵌 PNG） | 不因嵌套帧抛异常 |
| 名字解析 | 22 张卡 | 与清单名字逐一相等 |
| marker 区分 | Kugisaki old_female | 识别为 `KoiKatuChara`（KK），不与 Sun 混同 |
| 唯一 MOD 去重 | 沙耶香（4 条→1）、ユウキ（220 条→31） | 去重正确 |
| 槽位解析 | 华城绫女 | 得到 `ChaFileFace.eyelineUpId` / `Pupil1` / `Pupil2` |
| 缺失依赖 | 佐仓杏子 | `ymgpt.acc_earrings_top` 标记为未安装 |
| 内嵌贴图计数 | 22 张卡 | 与清单的 0/1/7/10/17/22/120 逐一相等 |
| zipmod manifest | 13 个 zipmod | guid/name/author/version 全部正确 |
| 空 author | NoHair.zipmod | 解析成功，author 为空不报错 |

### I.2 集成级（对完整样本目录跑一次）

| 用例 | 期望 |
| :--- | :--- |
| 全量首扫 | 22 卡 + 13 mod 入库；`scan_records` 统计正确 |
| 二次扫描 | 全部 skip，`files_new = 0` |
| 重复检测 | Kugisaki 两份 → 1 个 duplicate group（`suggested`，**不删除**） |
| 近重复 | 两张 Kobeni → 不因 `quick_hash` 相同而误判为真重复 |
| 反向索引 | 查询 `com.Quokka.naginata` → 命中红豆 + 长尾景虎 |
| 孤立 MOD | 查询无引用 MOD → 命中 G 组 3 个 |
| 只读校验 | 扫描前后对全部 36 个文件做 sha256 快照对比，必须完全一致 |

### I.3 建议加入的回归护栏

1. **样本文件哈希基线**：把 36 个文件的 sha256 写成清单，任何测试运行前后都要校验，
   防止「测试改了用户文件」这类事故。
2. **性能预算**：22 张卡（76 MB）首扫应在可接受时间内完成；批量写入必须走 `db.transaction`
   （Phase 1.1 已有性能冒烟测试）。
3. **编码护栏**：所有路径按 UTF-8 处理；断言日文名 `ユウキ`、`嵐燐結騎` 原样入库。

---

## J. 对现有 Phase 1.1 数据模型的差距分析

**只指出问题，未改动任何 schema。** 下列差距都是本样本集实测暴露的。

| # | 差距 | 证据 | 影响 | 建议（待你决定） |
| :--- | :--- | :--- | :--- | :--- |
| J1 | **无「插件」表** | 每张卡 1–21 个插件，都不是 zipmod | 插件信息无处安放 | 加 `resource_plugins` 表，或先放 `metadata_json` |
| J2 | **依赖关系丢失槽位** | 沙耶香 4 条记录→1 个 MOD，`Property` 各不同 | 「这个 MOD 用在哪」丢失 | 加 `resource_mod_usages(resource_id, mod_guid, property, slot, category_no)`，或把槽位列表存 `metadata_json` |
| J3 | **`ref_count` 语义不足** | 220 条记录 vs 31 唯一 MOD | `ref_count` 无法表达「几处槽位 + 哪些槽位」 | 明确 `ref_count` = 槽位记录数；另设唯一 MOD 视图 |
| J4 | **作者只能存单个** | `marco.authordata` = `['[Unknown]','Evaan']` | 多作者无法表达 | `resources.author` 保留原始串，`author_id` 必要时指向主作者；或建 `resource_authors` |
| J5 | **哨兵作者 `[Unknown]`** | 多张卡含该值 | 会把无关卡聚成一类 | 解析时过滤/降权，并记录到 `notes` 或日志 |
| J6 | **无「游戏版本」字段** | KK vs KKS 同角色两份 | 无法区分版本族 | 放入 `metadata_json`（如 `card_marker`），或新增列 |
| J7 | **重复检测键不足** | quick_hash 假阳性；仅 dataID 不同的近重复 | 判重不可靠 | 真重复用 `sha256`；近重复用 `content_key`（需定义：忽略 dataID 后的内容摘要） |
| J8 | **`dataID` 不能当身份** | 两卡仅差 dataID | 若拿它做唯一键会每保存一次就产生「新文件」 | 明确 `dataID` 只作为元数据存储 |
| J9 | **内嵌贴图无处记录** | 卡片内 0–120 张 PNG | 无法统计/展示 | 先在 `metadata_json` 存计数；将来若要逐张管理再建表 |
| J10 | **`resource_type` CHECK 里的 `skin/eyes/hair/accessory` 与实际不符** | 实测这些语义属于槽位，不属于文件 | 会诱导 Scanner 错误分类 | 保留枚举（未来可能有独立资源），但**明确禁止**用它给 PNG 分类 |
| J11 | **`mods` 表缺 `manifest` 之外的元数据** | manifest 有 `website`/`description`/`game` 字段 | 已建的列基本够用 | 无需改动，仅确认解析写入 |
| J12 | **zipmod 与资源的关系** | zipmod 文件本身也是「一个文件」 | 同一文件会同时是 `resources` 行和 `mods` 行 | 明确：zipmod → 1 条 `resources(type='mod')` + 1 条 `mods`，用 `mods.resource_id` 关联 |

### J.1 建议的最小 schema 变更（**暂不执行，等你确认**）

如果要让 1.2 的关系不失真，最小改动是新增一张表：

```sql
-- 建议（v2 迁移）：卡 → MOD 的逐槽位使用记录
CREATE TABLE resource_mod_usages (
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    mod_guid    TEXT    NOT NULL,
    property    TEXT    NOT NULL,   -- 例：outfit6.accessory10.ChaFileAccessory.PartsInfo.id
    slot        INTEGER,
    local_slot  INTEGER,
    category_no INTEGER,
    PRIMARY KEY (resource_id, mod_guid, property)
);
```

以及 `metadata_json` 中约定存放：`card_marker`、`plugin_count`、`embedded_texture_count`、
`plugin_guids`、`authors`、`user_id`、`data_id`。

> ⚠️ 这些都是**建议**，本轮没有执行任何 `schema.py` 改动；需要你决定后再进 Phase 1.2。

---

## 结论：Phase 1.2 Scanner 正式编码前还需要补充什么？

### 已经足够、可以直接开工的部分

以下事实已被 22 张卡 + 13 个 MOD **100% 验证**，可以直接写进 Scanner：

1. 卡片容器结构（PNG + productNo + marker + 版本 + 面部图 + lstInfo + 保留字段 + 数据区）
2. 卡片类型判定（marker）
3. 角色名（`Parameter.lastname/firstname`）
4. 唯一 MOD 判定（sideloader 表按 `ModID` 去重）—— **22/22 与你的清单一致**
5. 插件数（KKEx 键数）—— **22/22 一致**
6. 内嵌贴图数（数据区 PNG 计数）—— **22/22 一致**
7. zipmod 元数据（manifest guid/name/author/version）—— **13/13 一致**
8. 槽位语义（`Property` 前缀 → 眼睛/身体/衣服/配饰）—— 声明中 C/D/E 三组的描述逐条对上
9. 共享 MOD / 孤立 MOD / 缺失 MOD 三种关系形态

### 仍需要你补充的信息或样本

| # | 需要补充 | 为什么 | 建议形式 |
| :--- | :--- | :--- | :--- |
| 1 | ~~「内嵌贴图」的原始定义~~ **【已解决】** | 已与 `tools/probe_cards.py` 的口径交叉验证一致（§0.1） | 无需再补充 |
| 2 | **一张「已知使用 MOD 眼线」的对照卡 + 一张纯原版眼线卡** | 才能确定 `eyelineUpId=1900` 这类高位 id 是否等价于「来自 MOD」（G3） | 2 张卡 |
| 3 | **一张「同一角色重新保存一次」的卡（或同一卡的两次保存）** | 才能确认 `dataID` 是否每次保存都变（G7），以及 `mtime` 是否会变 | 2 个文件 |
| 4 | **一张「同一文件被重新保存但 mtime 未变」的样本** | 才能验证增量扫描 `(path,size,mtime)` 是否会漏更新（F8） | 1 组 |
| 5 | **一张含「头发 / 发饰」MOD 的卡** | 样本里只出现过 `HeadMod` 这类字样，未直接观测到 `ChaFileHair` 槽位前缀（D.2） | 1–2 张卡 |
| 6 | **至少一个「独立存在的眼睛/皮肤贴图文件」**（不是卡） | 当前所有样本里的眼睛/皮肤语义都在卡片依赖里；若要支持「独立的贴图资源」，现有样本无法验证其形态 | 若干文件 |
| 7 | **一个「内容与文件名明显不符」的 zipmod** 及其被引用情况 | 验证 Scanner 只能信 manifest、不能信文件名 | 1–2 个 |
| 8 | **`KSOX` / `KCOX` / `materialeditor` 贴图插件的格式说明（或更多样本）** | 决定 Phase 1.2 是否要解析卡内贴图内容（G2/G4） | 文档或 3+ 样本 |
| 9 | **你的「缺失 MOD」判定口径** | 样本中 `ymgpt.acc_earrings_top`、`NonLightStockings` 属缺失；需确认是否要区分「本样本集缺失」与「本机游戏目录缺失」 | 一句话规则 |
| 10 | **是否允许 Phase 1.2 做 schema v2 迁移**（J1/J2 两张表） | 否则槽位关系只能塞进 `metadata_json`，后续查询会麻烦 | 决策 |
| 11 | **1 个加密 zipmod 样本** | 现有 13 个全部未加密，无法验证「读不到 manifest」时的降级行为（G11） | 1 个 zipmod |

### 一句话结论

> 本样本集**足以支撑 Phase 1.2 Scanner 的 MVP 开工**：
> 容器格式、类型判定、角色名、唯一 MOD 数、插件数、内嵌贴图数、zipmod 元数据、
> 槽位语义、共享/孤立/缺失三种关系形态，全部 100% 验证通过。
> 仍建议在编码前先确认的是**第 2 项（高位 id 是否等同 MOD 来源）**与
> **第 10 项（是否允许 schema v2 迁移）**；其中第 2 项只影响「眼睛来源」这一条判定，
> 不阻塞主流程，可以先用 `待验证` 标记跳过。
