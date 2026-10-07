# Phase 2.0-B — Phase 2 外部项目研究与设计输入收集

> 阶段：Phase 2.0-B（Research，**只读 + 外部研究**）
> 日期：2026-10-07
> 本阶段产出：**仅本文件**。未修改 schema / migration / models / parser / scanner /
> ResourceStore / Query Layer / GUI / CLI / tests / 配置；未新增依赖；未删除死代码；
> 未实现 hash / duplicate / dependency graph / tags / collections / classification。
> 本阶段**不产出** Phase 2 设计、不产出 schema v3。

---

## 0. Git Baseline（先决条件）

只读执行结果（未执行 reset / clean / checkout / rebase 等任何破坏性命令）：

```text
$ git status
On branch main
nothing to commit, working tree clean

$ git log --oneline --decorate -10
5987a0f (HEAD -> main) chore: close phase 1 baseline

$ git rev-parse HEAD
5987a0f12d795d4c31de43cf50b9a1a0123e6beb

$ git branch --show-current
main

$ git remote -v      -> （无输出：没有配置远端）
$ git tag            -> （无输出：没有 tag）
$ git reflog -5      -> 5987a0f HEAD@{0}: commit (initial): chore: close phase 1 baseline
```

确认与记录：

1. 仓库已进入 Git 版本控制；HEAD = `5987a0f`，分支 `main`，工作区干净。
2. HEAD 对应 **Phase 1 CLOSED 基线**（提交信息 `chore: close phase 1 baseline`）。
3. 该基线是**单一初始提交**：Phase 1 全部代码与 Phase 2.0-A 报告在**同一个提交**里，
   不存在「只含 Phase 1、不含 2.0-A」的独立提交点。
4. 无远端、无 tag、reflog 只有这一条记录 ⇒ 有版本历史，但**没有异地备份 / 标签锚点**。
5. 无「非 Phase 2 变更」需要记录——工作区干净，没有未提交改动。

### 0.1 与任务描述不符的两处事实（原样记录，不做修改）

| 任务描述 | 实际状态（以代码/文件系统为准） |
| :--- | :--- |
| `docs/phase2/PHASE2_0_A_BASELINE_REVIEW.md` 已确认 | 实际路径为 **`docs/PHASE2_0_A_BASELINE_REVIEW.md`**（在 `docs/` 根下，654 行，已被 `5987a0f` 提交收录）；`docs/phase2/` 目录在本阶段之前**不存在** |
| 需确认 Git 基线 | 已确认；仓库是**单提交**初始历史（无远端 / 无 tag） |

> 说明：本阶段**只允许新增** `docs/phase2/PHASE2_0_B_RESEARCH.md`，因此**没有**移动、
> 重命名或补交 2.0-A 报告；上述差异仅作记录，供后续阶段决定是否整理。

---

## 1. Research Scope

本阶段目标：**为 Phase 2 设计收集可靠依据**，而不是实现 Phase 2、也不是冻结设计。

研究的问题域（任务给定的 8 个方向，本报告逐一对应）：

1. Identity System — 系统的身份分层是否足够
2. 内容级身份 / Hash — 是否应建立真正的 content identity
3. Duplicate Detection 的基础能力
4. MOD Identity / Version — 同 GUID 多版本问题
5. Resource / File 边界 — 1:1 是否应被打破
6. Dependency Model 的演进 — Resource→MOD 之外是否需要 MOD→MOD
7. Tags / Collections 是否进入 Phase 2
8. Classification System 的正式化

研究方法与纪律：

- 以 **KKS Resource Manager 当前真实约束**为判断基准（依据 `docs/PHASE2_0_A_BASELINE_REVIEW.md`
  与本次重新核对的代码事实）；
- **外部项目只作为证据来源**，不作为采用理由：报告中每条「可借鉴」都配了可点击来源；
- 抓取方式：`raw.githubusercontent.com` 读取各项目 README / 规范文档 / 关键源码文件
  （GitHub REST API 已触发匿名限额，改用 raw + HTML 目录通道，未使用任何 token）；
- 对**未能核实**的内容明确标注「未核实」，不凭印象断言（见 §11）。

---

## 2. GitHub Projects Reviewed

| Project | 类型 | 研究重点 | 可借鉴点 | 不适合点 |
| :--- | :--- | :--- | :--- | :--- |
| [IllusionMods/KKManager](https://github.com/IllusionMods/KKManager) | **同域** Mod/插件/卡片管理器（KKS/KK 系） | MOD identity、版本、重复 zipmod、卡片浏览 | `ModInfoBase` = **物理文件 + GUID + version + games**；同 `Guid` 分组去重、按版本取新；同文件名按 mtime 取新 | 它的「重复处理」是**删除文件**；本项目默认只读，不能照搬行为 |
| [Nexus-Mods/Vortex](https://github.com/Nexus-Mods/Vortex) | 通用 Mod Manager（250+ 游戏） | 冲突、load order、profile、多游戏元数据 | 把「冲突解决」「load order」提升为一等概念；profile = 一组启用的 mod | 依赖中央站点（Nexus）+ 各游戏 extension；本项目**零网络**，无法复用其数据来源 |
| [ModOrganizer2/modorganizer](https://github.com/ModOrganizer2/modorganizer) | 通用 Mod Manager（虚拟文件系统） | 安装/卸载生命周期、安装器格式 | 「install / uninstall 可逆」的产品语义；安装器插件化（FOMOD/BAIN/bundle/omod） | 强依赖 VFS 与安装目标目录；本项目不安装、不改游戏目录 |
| [ebkr/r2modmanPlus](https://github.com/ebkr/r2modmanPlus) | Thunderstore 生态 Mod Manager | profile、导出、更新检测 | 「profile 导出/分享」「查看并更新过期 mod」是用户真实工作流 | 以 Thunderstore 在线包为中心（下载/更新），与本地只读定位冲突 |
| [KSP-CKAN/CKAN](https://github.com/KSP-CKAN/CKAN) | **依赖解析**型 Mod 管理器（含 [Spec.md](https://github.com/KSP-CKAN/CKAN/blob/master/Spec.md)） | identity / version / **依赖与冲突关系** | 关系词汇表：`depends / recommends / suggests / supports / conflicts / replaced_by / provides`；`version = [epoch:]mod_version`；`install[{file, install_to}]` | 依赖信息来自**中央元数据库**；KKS 没有这一层（见 §5） |
| [FabricMC/fabric-loader](https://github.com/FabricMC/fabric-loader) | Mod 加载器（元数据 + 依赖判定） | 依赖/冲突/版本谓词 | [`ModMetadata`](https://github.com/FabricMC/fabric-loader/blob/HEAD/src/main/java/net/fabricmc/loader/api/metadata/ModMetadata.java)：`getId / getVersion / getProvides / getDepends / getConflicts / getBreaks` 六件套 | 依赖由 `fabric.mod.json` **显式声明**；KKS zipmod 没有等价字段 |
| [IllusionMods/BepisPlugins](https://github.com/IllusionMods/BepisPlugins) | Illusion 系必备插件集（含 Sideloader） | zipmod / manifest 生态来源 | 说明 KKS/KK 的 zipmod 生态建立在 BepInEx + Sideloader 之上（manifest.xml 即此生态） | 插件包本身与「资源库」无关 |
| [photoprism/photoprism](https://github.com/photoprism/photoprism) | 数字资产 / 媒体库 | **Photo（逻辑）↔ File（物理）**、hash、sidecar | [`File`](https://github.com/photoprism/photoprism/blob/HEAD/internal/entity/file.go) 明文「belongs to a photo」，含 `PhotoID` FK、`FileHash`(索引)、`FilePrimary`、**`FileSidecar`**、(FileName,FileRoot) 唯一 | 面向照片/视频与 AI 标注；其相册/标签工作流远超本项目所需 |
| [immich-app/immich](https://github.com/immich-app/immich) | 数字资产 / 媒体库 | **Asset ↔ AssetFile**、checksum 唯一约束 | [`asset.table.ts`](https://github.com/immich-app/immich/blob/main/server/src/schema/tables/asset.table.ts)：`checksum`(sha1) **按 (owner, library) 唯一**；[`asset-file.table.ts`](https://github.com/immich-app/immich/blob/main/server/src/schema/tables/asset-file.table.ts)：`(assetId, type, isEdited)` 唯一 | 多用户 / 多云 / 移动端同步模型；本项目是单机单库 |
| [hydrusnetwork/hydrus](https://github.com/hydrusnetwork/hydrus) | 个人媒体库（标签驱动） | **内容身份**、重复/近似重复判定 | [`docs/duplicates.md`](https://github.com/hydrusnetwork/hydrus/blob/master/docs/duplicates.md)：potential duplicates（phash + VPTree + hamming）→ confirmed **duplicates** vs **alternates**；每组一个 "king"；**A=B、B=C ⇒ A=C 传递闭包** | 图像感知哈希体系；KKS 的重复问题不是「长得像」，而是「同一个 mod / 同一张卡」（见 §6） |
| [beetbox/beets](https://github.com/beetbox/beets) | 媒体库（音乐） | 元数据驱动的库 + 标签 | 「库 = 长期维护的元数据集合」；导入即自动纠错/补全元数据 | 元数据来自 MusicBrainz 等**在线源**；本项目零网络（其 Item/Album 细节本次未抓取核实，见 §11） |
| [adrianlopezroche/fdupes](https://github.com/adrianlopezroche/fdupes) | 重复文件检测 | **判定漏斗**：size → 摘要 → 字节比对 | man page 明文：`comparing file sizes and MD5 signatures, followed by a byte-by-byte comparison`；`-H` 区分硬链接 | CLI 工具、无持久模型；不产生可查询的「重复组」实体 |
| [sahib/rmlint](https://github.com/sahib/rmlint) | 重复文件/目录检测 | hash vs 字节比对、缓存、去重策略 | README：`Paranoia mode for those who do not trust hashsums`；`Caching and replaying`；`Search for files only newer than a certain mtime` | 面向「清理磁盘空间」；有交互式删除脚本输出 |
| [qarmin/czkawka](https://github.com/qarmin/czkawka) | 重复/相似文件检测（GUI） | 多模式重复判定 | README：duplicates 按 **name / size / hash**；similar images（非完全相同）；music duplicates 按 **tags 或内容** | 面向「删除多余文件」；多模式 UI 复杂度高 |
| [restic/restic](https://github.com/restic/restic) | 备份（内容寻址存储） | **内容即身份**、分块去重、不可变 | [`doc/design.rst`](https://github.com/restic/restic/blob/HEAD/doc/design.rst)：`Blob` = 数据 + **SHA-256** + 长度；`Storage ID` = 内容 SHA-256；内容寻址、写入即不可变 | 备份/加密/CAS 是另一领域的复杂度；本项目不需要去重存储层 |

> 共 14 个项目，覆盖任务给定的 4 个类别。URL 均为可点击的 GitHub 链接。

---

## 3. Identity Architecture Comparison

外部项目实际使用的身份分层（按「最细 → 最粗」）：

| 身份层 | 代表项目（来源） | 关键事实 |
| :--- | :--- | :--- |
| **Path identity** | fdupes / rmlint / czkawka 的**输入层** | 路径只用来「找到文件」；判定重复时一律回到内容/摘要（fdupes man page） |
| **File identity（物理文件）** | PhotoPrism `File`、Immich `AssetFile` | 物理文件是**从属实体**，带 `path` / `size` / `hash`，属于上层逻辑实体（PhotoID / assetId） |
| **Content identity（内容）** | restic `Storage ID`、Immich `checksum`、Hydrus `hash` | restic：名字就是内容 SHA-256；Immich：`checksum` 有**唯一约束**（按 owner+library） |
| **Logical resource identity** | PhotoPrism `Photo`、Immich `Asset`、Hydrus `File(hash)` | 逻辑实体是用户操作对象；物理文件可有多个（原始/派生/sidecar） |
| **Mod identity** | CKAN `identifier`、Fabric `getId()`、KKManager `Guid` | 都是一个**稳定的逻辑键**，供其它实体引用 |
| **Version identity** | CKAN `version=[epoch:]mod_version`、Fabric `getVersion()`、KKManager `Version` | 版本是**逻辑实体上的属性**，不是新的逻辑实体；CKAN 还定义了版本可比较语义 |
| **Instance / package identity** | CKAN `install[{file, install_to}]`、Immich `(assetId,type,isEdited)`、KKManager `ModInfoBase.Location` | 「同一逻辑实体的某一个具体载体/安装形态」——这一层**在成熟项目里普遍存在** |

对 KKS Resource Manager 的映射（当前代码事实）：

| 本项目字段 | 属于哪一层 | 结论 |
| :--- | :--- | :--- |
| `resources.file_path_key` | Path identity（唯一约束） | **同时充当 File identity 与 Resource identity** |
| `resources.file_size` / `modified_time` | 扫描/增量字段 | 不构成身份 |
| `resources.sha256` / `quick_hash` / `content_key` | 预留的 Content identity | **零写入**，当前无身份能力 |
| `mods.guid` | Mod identity | 与 CKAN/Fabric/KKManager 一致 |
| `mods.version` | Version（属性） | 与成熟项目一致，只是没有比较语义 |
| `authors.name_key` | 作者身份 | 归一化键，成熟项目常见做法 |
| （无表） | Instance / package identity | 本项目**缺这一层**（见 §4、§5） |

**研究结论**：外部项目的身份分层是「逻辑实体 + 内容身份 + 物理实例」三层；本项目目前只有
「路径身份」一层，`mods` 里 `guid` + `version` + `file_path` 三者被塞进同一行。

---

## 4. File / Resource Model Comparison

| 项目 | 关系 | 证据 |
| :--- | :--- | :--- |
| PhotoPrism | **Photo 1:N File**（且区分 primary / sidecar） | `File` 注释「image or sidecar file that belongs to a photo」+ `PhotoID` 外键 + `FilePrimary` / `FileSidecar` |
| Immich | **Asset 1:N AssetFile** | `asset-file.table.ts` 有 `assetId` + `type`(AssetFileType) + `isEdited`，唯一键 `(assetId,type,isEdited)` |
| Hydrus | 逻辑上 **File = 内容哈希**；URL/标签与文件是 N:M | `docs/duplicates.md` 以文件为单位判定重复；标签系统独立于文件位置 |
| beets | 库 = 元数据实体（未核实其 Item/Album 与文件的基数） | README 仅说明「catalogs your collection」 |
| KKManager | **1 文件 = 1 mod**（`ModInfoBase` 同时持有 `Location(FileInfo)` 与 `Guid`），重复 GUID 视为要清理的重复 | `ModInfoBase.cs`、`ZipmodTools.cs` |
| fdupes / rmlint / czkawka | 文件即被检测对象（N 个路径 ↔ 1 份内容） | fdupes man page |

四种基数在外部项目中的存在情况：

| 基数 | 是否有成熟先例 | 本项目当前 | 本项目是否有证据需要 |
| :--- | :--- | :--- | :--- |
| File = Resource | 有（KKManager，同域） | 现状 | — |
| File ≠ Resource（1:N，逻辑→物理） | 有（PhotoPrism / Immich） | 无 | 真实样本未出现一个资源多份文件 |
| N:1（一个文件含多个逻辑资源） | 未在本次抓取中核实 | 无 | 未出现 |
| N:M | 有（Hydrus：文件↔URL/标签） | 无 | 不作为资源模型需求 |

**研究结论（针对任务 §五-1 的问题）**：

- 成熟项目之所以把 File 与 Resource 分开，是因为它们**确实存在**「一个逻辑实体多份物理文件」
  （原图 + 派生缩略图 + sidecar 元数据文件；视频原片 + 转码片）；
- KKS 领域里，**同域参考实现 KKManager 本身也没有做这个分离**——它把 zipmod 文件与
  mod 信息绑定为一个对象，靠 `Guid` 归组；
- 本项目当前 1:1 并非「设计缺陷」，而是与同域实践一致；真正的缺陷是
  **路径唯一性是跨库全局的**（Phase 2.0-A §12 F6），那属于另一个问题（多库语义），
  不是 File/Resource 边界问题。

结论：**File ≠ Resource 的正式分离在本阶段没有证据支持**；是否需要，
应由 §10 的问题清单在 2.0-C 用真实数据回答。

---

## 5. MOD / Dependency Model Comparison

### 5.1 身份与版本

| 项目 | 逻辑身份 | 版本 | 多版本共存？ |
| :--- | :--- | :--- | :--- |
| KKManager（同域） | `Guid` | `Version`（字符串） | **不共存**：`ZipmodTools.SideloaderCleanupByManifest` 按 `Guid` 分组，保留最新版本、删除旧的 |
| CKAN | `identifier`（全局唯一） | `[epoch:]mod_version`，可比较 | 元数据库保留多版本历史；本地安装集只落地一份 |
| Fabric | `getId()` | `getVersion()`（版本谓词可比较） | 加载器按依赖解析选择 |
| Vortex / MO2 / r2modman | 以「已安装的 mod 条目」为单位 | 以 package/version 展示 | 由管理器维护启用/停用与 profile，而非让同名多版本共存于一个槽位 |

**本项目对照**：`mods.guid UNIQUE` ⇒ 同 GUID 多版本**塌成一行**；`upsert_mod_resource` 用
`ON CONFLICT(guid) DO UPDATE`，后扫到的覆盖前面的 manifest 字段。这与 KKManager 的
「同 GUID 只保留一份」在**最终状态**上一致，差别在于 KKManager 会主动清理重复文件，
而本项目会静默覆盖字段（旧版本信息丢失）。

### 5.2 依赖与冲突

| 项目 | 依赖数据来源 | 关系类型 | 版本约束 |
| :--- | :--- | :--- | :--- |
| CKAN | **中央元数据库**（作者提交 .ckan） | depends / recommends / suggests / supports / conflicts / provides / replaced_by | 有（min_version 等） |
| Fabric | **mod 自带 `fabric.mod.json`** | depends / conflicts / breaks / provides | 有（版本谓词） |
| KKManager（同域） | **无** —— manifest 只有 guid/name/author/version/website | 无 mod→mod 依赖概念 | 无 |
| 本项目 | 卡片 KKEx 块里的 `ModID` 列表 | Resource→MOD（`uses`） | 无 |

关键事实：KKS zipmod 的 manifest.xml **不包含依赖字段**。本项目 `parse_manifest_xml`
的 `_MANIFEST_FIELDS` 只有 `guid / name / author / version / website`；
同域参考实现 KKManager 的 `ModInfoBase` 字段也只有 `guid/name/version/author/description/website/games`。

**研究结论**：CKAN 与 Fabric 的依赖体系都建立在「**存在依赖声明**」这一前提上；
KKS 生态**不存在这个前提**（除非未来引入作者侧或社区侧元数据）。因此：

- 「统一 dependency edge / version constraint」在本项目**没有数据源**；
- `resource_mod_usages` 表达的是「**卡片用了哪个 mod**」（使用事实），与
  「mod 依赖 mod」（前置关系）是**语义不同的两类边**，不能简单合并；
- CKAN 的 `depends / conflicts` 词汇表可以作为**命名参考**，
  但不应据此在 Phase 2 建图引擎。

---

## 6. Duplicate Model Comparison

| 项目 | exact duplicate | content / logical duplicate | 近似重复 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| fdupes | size → MD5 → **逐字节** | 同左 | 无 | 漏斗式判定（man page） |
| rmlint | 默认 hash；`paranoia` 用字节比对兜底 | 同左；还支持重复目录 | 无 | 支持缓存/重放、mtime 过滤 |
| czkawka | name / size / **hash** | 同左 | 有（相似图片、相似视频、音乐按标签或内容） | 多模式 |
| Hydrus | 内容哈希（隐含） | **confirmed duplicates**（不同质量/分辨率的同一来源）vs **alternates**（相关但不等价） | 有（phash + VPTree + hamming） | 每组一个 "king"；关系**传递闭包** |
| restic | 内容分块哈希 | 内容寻址，天然去重 | 无 | 面向存储层 |
| KKManager（同域） | **同 GUID 的多个 zipmod 文件** | 同 GUID 视为同一 mod 的不同版本 | 无 | 按版本/路径约定保留一份并删除其余 |
| 本项目（预留） | `duplicate_groups(group_type='file')` | `group_type='content'` + `hash_key` | 无 | `status` = suggested/confirmed/dismissed；`duplicate_members.is_canonical` |

关键对照：

- 通用重复检测器把「重复」定义为**内容相同**（byte/hash）；
- 同域 KKManager 把「重复」定义为**逻辑身份相同**（同 GUID）；
- 两者在 KKS 场景里指向**不同的东西**：
  - 同一张卡被导出两次（字节不同、dataID 不同）⇒ 内容哈希**判不出来**；
  - 同一个 mod 的两个版本（字节不同、GUID 相同）⇒ 内容哈希也**判不出来**，GUID 能判出来；
  - 同一文件的两个副本（字节相同）⇒ 内容哈希能判出来。

**研究结论（针对任务 §五-5）**：本项目的「重复」至少是三个不同问题
（同内容副本 / 同逻辑 mod 多版本 / 同角色多张卡），**不应该用一个机制覆盖**；
而现有预留 schema（`group_type` 已有 `file|content` 两值）在结构上只能覆盖其中一部分。

---

## 7. Classification Model Comparison

| 项目 | 分类方式 | 证据 |
| :--- | :--- | :--- |
| PhotoPrism | **metadata-driven**（EXIF/sidecar）+ 媒体类型；可选 AI 标注 | README + `File` 中的 `FileSidecar` / `FileHash` / 大量 EXIF 字段 |
| Immich | **enum + metadata**（`AssetType` / `AssetStatus` / `AssetVisibility` + EXIF 表） | `asset.table.ts` 的列与 `enums.ts` |
| Hydrus | **filetype + 用户标签**；不做自动语义分类 | README + 仓库内 `docs/filetypes.md`（本次确认该文件存在） |
| CKAN / Fabric | 分类 = **元数据字段**（tags / 依赖关系），不是独立层 | Spec / ModMetadata |
| beets | 元数据驱动 + 在线数据库匹配 | README |
| 同域：KKManager | **解析驱动**：读 manifest / 文件类型，不做规则推理 | `ModInfoBase` 由 manifest 构造 |
| 同域：本项目（现状） | **parser-driven**：marker → `character_card`；zipmod → `'mod'`（store 硬编码）；其余落 `unknown` | Phase 2.0-A §4.1、§12 F1 |

**研究结论**：成熟项目中**没有一个**把「Classification」做成独立于解析器的通用层；
分类要么来自解析结果（同域实践），要么来自外部元数据（在线库）。本项目的
`AUTO_DETECTABLE_TYPES` + `unknown` + `needs_review` 与同域实践一致，属于
「只写可靠结论」策略。`core/classification/` 目前是**文档概念**，尚无证据表明需要
独立的 Level 1–4 推断层（样本中 marker 全部可靠）。

---

## 8. Findings Applicable to KKS Resource Manager

> 以下只写**研究结论**，不实现、不设计 schema。

**A. ID-1｜内容身份是 Phase 2 中「性价比最高」的候选能力（研究层面）**

- 本项目**已有**三个预留列（`sha256` / `quick_hash` / `content_key`），零写入；
- 外部项目的共识是「内容身份 = 稳定、可复算、与路径无关」（restic / Immich / Hydrus）；
- 引入内容身份**不需要**打破 File = Resource 的现状（这一点与 §4 结论相容）。

**A. ID-2｜「逻辑身份」在同域已经确定：MOD 用 GUID**

- 同域参考实现用 `Guid` 作为 mod 的逻辑键，并用它组织重复清理；
- 本项目 `mods.guid UNIQUE` 与之一致，方向无需改变。

**A. ID-3｜「安装实例 / 载体」这一层在本项目缺失，但同域实践也没做**

- CKAN / Immich 有明确的 instance 层（`install[{file,install_to}]`、`(assetId,type,isEdited)`）；
- KKManager 把它压缩为「一个文件 = 一个 mod」；
- 本项目与 KKManager 一致 ⇒ **不是必须补的层**，属可选演进。

**A. DUP-1｜重复问题必须分成三类分别对待**

- 同内容副本（字节相同）→ 可用内容哈希；
- 同逻辑 mod 多版本（GUID 相同、字节不同）→ 必须用 GUID + version，哈希无效；
- 同角色多张卡（语义相同、字节不同）→ 两者都无效。

**A. DEP-1｜依赖图在本项目没有数据源（最重要的一条）**

- KKS zipmod manifest 没有依赖字段（本项目 parser 字段 + 同域 KKManager 字段均可证）；
- 因此 CKAN / Fabric 式的 dependency graph / version constraint **在当前数据下无法落地**；
- 本项目唯一可靠的「跨实体边」是卡片使用事实（Resource→MOD），它应当保持
  与「依赖」不同的语义。

**A. CLS-1｜分类应继续留在解析层，而不是抽成独立层**

- 外部无先例、同域无需求、样本无失败案例。

**A. TAG-1｜Tags / Collections 有充分先例，但与 Phase 2 的核心问题正交**

- PhotoPrism / Hydrus / beets 都把标签/相册作为用户组织层；
- 本项目表结构已存在（`tags` / `collections` + 关联表），**缺的只是写入者与读取 API**；
- 它依赖的是「用户交互模型」，不是身份/依赖模型 ⇒ 与 Phase 2 的 identity 主线可分阶段。

**A. BASE-1｜Git 基线可用但仍需加固**

- 有 HEAD 可回退（`5987a0f`），但只有一次提交、无 tag、无远端；
- 若 Phase 2 引入 schema v3，建议先建立**明确的基线 label**（本报告只记录事实与风险，
  不执行任何 git 写操作）。

---

## 9. Findings NOT Applicable

> 明确记录**不应搬进来**的设计，以及原因。

| 不适用项 | 来源 | 不适合的原因 |
| :--- | :--- | :--- |
| 中央元数据仓库 / 在线依赖解析 | [CKAN Spec](https://github.com/KSP-CKAN/CKAN/blob/master/Spec.md) | 本项目硬约束「运行时零网络」；且 KKS 没有对应的公共元数据库 |
| Mod 依赖图 / 版本约束求解 | CKAN / Fabric | **没有数据源**：manifest.xml 无依赖字段（§5.2） |
| 自动下载 / 更新 mod | KKManager、r2modman | 违反「本地优先、零网络」；本项目是**只读索引**而非安装器 |
| 安装到游戏目录 / 虚拟文件系统 | MO2、Vortex、KKManager | 本项目明确定位「位置与分类分离、不动文件」，不管理安装 |
| 感知哈希 / 近似图片查重（phash、VPTree、hamming） | Hydrus | KKS 的重复问题不是「图片长得像」；且卡片的 PNG 尾部含可变 dataID，感知哈希无意义 |
| 内容分块 / 内容寻址存储（CDC、CAS） | restic | 备份/存储层复杂度；本项目只做索引，不做存储 |
| 多用户 / 权限 / 云同步模型 | Immich | 本项目是单机单用户本地工具 |
| 批量删除重复文件 | fdupes / rmlint / czkawka / KKManager | 违反「默认只读」「不自动删除」；删除必须留到 Phase 5 且走 Preview / Confirm / Undo |
| 把 File 与 Resource 拆成两层 | PhotoPrism / Immich | 它们有真实的 1:N 场景；本项目与同域 KKManager 都是 1:1，且**无样本证据**支持拆分 |
| 独立 Classification Engine / AI 分类 | PhotoPrism（AI 标注） | 违反「运行时零云 AI」；同域实践是解析驱动 |
| 版本可比较语义（epoch / 谓词） | CKAN / Fabric | 需要依赖求解才有意义；本项目 manifest 的 version 是自由字符串，无比较需求 |

---

## 10. Design Questions for Phase 2.0-C

> 要求：**可验证**、**能影响 schema / architecture**、**必须在设计冻结前回答**。
> 本节不给出任何最终 schema 或方案。

### 10.1 File / Resource 边界

1. **Q-F1**：当一个文件的路径同时出现在两个 Library 中时，期望语义是什么？
   （现状：`resources.file_path_key` 跨库唯一 ⇒ 第二次扫描会把行的 `library_id` **改挂**。）
   需要多少真实多库数据才能判定？（当前样本 1 库、工作库 0 库）
2. **Q-F2**：是否存在「一个物理文件对应多个逻辑资源」或反向的真实样例？
   （例如卡片合集包、嵌套 zipmod、场景卡内含角色卡）——需要样本扫描证据，否则保持 1:1。

### 10.2 内容身份 / Hash

3. **Q-H1**：三个预留列 `sha256` / `quick_hash` / `content_key` 各自的**语义边界**是什么？
   是否合并为单一概念？（现状：三列皆零写入，`content_key` 的注释指向 Phase 4）
4. **Q-H2**：哈希**何时计算**？（首扫全量 / 增量时补算 / 仅按需 / 仅超过阈值）
   需要真实大库的**扫描耗时基准**（Phase 1 样本仅 35 文件 / 184ms，不足以判断）。
5. **Q-H3**：哈希**何时失效重算**？失效判据是 `(file_size, modified_time)` 还是 mtime 变化即失效？
   内容改回原状的场景是否需要处理？
6. **Q-H4**：卡片类型是否要参与内容身份？（卡片 PNG 尾部含 dataID，重存即变 ⇒
   「同内容」不等于「同角色」，必须明确二者不是一回事。）
7. **Q-H5**：哈希写入位置是 `resources` 还是独立表？对 `scan_records` /
   增量语义是否有影响？（不得改变「size + mtime 决定是否重解析」的既有不变量。）

### 10.3 MOD 身份 / 版本

8. **Q-M1**：`mods.guid` 保持唯一（GUID = 逻辑 mod）这一约定是否需要正式写进架构文档？
9. **Q-M2**：同 GUID 多版本**是否需要共存为多个实体**？
   必须先取得「真实样本中出现重复 GUID」的证据（当前 13 mods、0 重复），
   否则它是**没有触发条件**的问题。
10. **Q-M3**：若不需要共存，是否需要保留「旧版本曾被扫到」的历史？
    （现状是 `ON CONFLICT(guid) DO UPDATE` **静默覆盖** manifest 字段。）

### 10.4 Dependency

11. **Q-D1**：在 manifest 无依赖字段的前提下，是否**放弃** mod→mod 依赖？
    （若答案是「放弃」，Phase 2 不应引入依赖图结构。）
12. **Q-D2**：`resource_mods.relation` 的 `embeds` 值是否要正式启用或删除？
    （现状 CHECK 允许，写入层恒为 `uses`。）
13. **Q-D3**：`resource_mod_usages`（逐槽位使用事实）在 Phase 2 是否**语义不变**？
    它是否会被新的「通用关系表」替代？（若替代，会破坏 Query Layer 与 GUI 契约。）

### 10.5 Duplicate

14. **Q-U1**：Phase 2 的「重复」定义包含哪几类？（同内容副本 / 同 GUID 多版本 / 同角色多卡）
    每一类分别需要什么身份基础（哈希 / GUID / 无）？
15. **Q-U2**：`duplicate_groups.group_type` 的两个既有取值（`file` / `content`）是否足够？
    若需要「逻辑重复」，是新增取值还是复用 `content`？（现状两值均无写入者。）
16. **Q-U3**：重复判定是**只读推导**（像 `review_reasons`）还是**落库的组**？
    两种选择的成本差异是什么？

### 10.6 Classification / Tags / Collections

17. **Q-C1**：`core/classification/` 空壳应如何处理？（实现 / 删除 / 保留为文档占位）
    无论哪种，都必须先确认没有真实分类失败案例。
18. **Q-C2**：Tags / Collections 是否进入 Phase 2？依据是「用户组织需求」还是「身份主线」？
    是否需要先有真实使用数据？

### 10.7 迁移与验证

19. **Q-V1**：若 Phase 2 需要 schema v3，迁移策略是什么？
    （`MIGRATION_ADDED_COLUMNS` 只支持幂等加列；新增表走 DDL；回滚证据如何取得？）
20. **Q-V2**：验证基线如何扩展？现有 671 passed + 两个 Node 脚本是否足以覆盖
    新增的 hash / duplicate 能力？（特别是**真实样本只读不变量** sha256 前后一致。）
21. **Q-V3**：Git 基线是否需要先打 label / 加远端？（`5987a0f` 是唯一提交点，
    Phase 2 一旦引入 v3，回退依赖这一条记录。）

---

## 11. 研究局限与未核实项（诚实边界）

为避免把印象当成证据，以下内容本次**没有**取得可引用来源，报告中未据此下结论：

- Vortex 的依赖/冲突**数据模型细节**：只读到 README（提到 auto-sorting、conflict
  resolution、profiles），其扩展 API 文档在 Nexus 侧 wiki，未抓取；
- MO2 的 VFS / 覆盖优先级实现细节：README 未覆盖（只确认「易安装/易卸载」与安装器插件体系）；
- beets 的 Item / Album 与文件基数：`beets/library.py` 返回 404（模块已重构），未抓取到；
  beets 仅按 README 作为「元数据驱动媒体库」的例证；
- Immich 的 `AssetFileType` 具体枚举值未逐值核实，仅确认存在 `type` +
  `(assetId, type, isEdited)` 唯一约束；
- r2modman / Thunderstore `manifest.json` 的依赖字段格式未取得源码级证据，
  报告中只按 README 描述其 profile / 更新检测能力；
- Paperless-ngx 的 README 未覆盖 checksum / 标签模型，因此**未纳入**本次结论；
- GitHub REST API 因匿名限额（HTTP 403）不可用，本报告所有来源均通过
  `raw.githubusercontent.com` 与 `github.com` HTML 目录页获取。

---

## 12. 结论

- **Git 基线确认**：`main` @ `5987a0f`，工作区干净，HEAD = Phase 1 CLOSED；
  记录了两处与任务描述不符的事实（A 报告路径、单提交历史），**未做任何修改**。
- **外部项目研究完成**：14 个项目，覆盖 Mod Manager / 资产库 / 重复检测 / 依赖模型
  四类，每条结论均附可点击来源。
- **研究结果有明确来源**：全部来自本次实际抓取的 README / 规范文档 / 关键源码
  （局限与未核实项见 §11）。
- **对 KKS Resource Manager 的适用性已逐项判断**：§8 适用项、§9 不适用项，
  每条注明原因。
- **未修改功能代码**：本阶段唯一新增文件即本报告。

```text
PHASE 2.0-B = PASS
```

（本阶段到此结束；不进入 Phase 2.0-C，不给出 Phase 2 设计，不修改任何功能代码。）


