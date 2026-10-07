# Phase 2.0-C Architecture & Schema Design

> 阶段：Phase 2.0-C（Design / Architecture Review，**只读 + 设计**）
> 日期：2026-10-07
> 输入：仓库当前实际代码 + `docs/PHASE2_0_A_BASELINE_REVIEW.md` + `docs/phase2/PHASE2_0_B_RESEARCH.md` + Git 当前状态
> 本阶段产出：**仅本文件**。未修改 schema / migration / models / parser / scanner /
> ResourceStore / Query Layer / GUI / CLI / tests / 配置；未新增依赖；未删除死代码；
> 未创建 schema v3；未执行 migration；未改动 Git 历史。

---

## 0. Git Baseline

只读执行（未执行任何写 Git 命令）：

```text
$ git status
On branch main
Untracked files:
        docs/phase2/

$ git log --oneline --decorate -10
5987a0f (HEAD -> main) chore: close phase 1 baseline

$ git rev-parse HEAD
5987a0f12d795d4c31de43cf50b9a1a0123e6beb

$ git branch --show-current
main

$ git remote -v      -> （空：无 remote）
$ git tag            -> （空：无 tag）

$ git ls-files --others --exclude-standard
docs/phase2/PHASE2_0_B_RESEARCH.md
```

与预期基线的对照：

| 项 | 预期 | 实际 | 结论 |
| :--- | :--- | :--- | :--- |
| branch | `main` | `main` | 一致 |
| HEAD | `5987a0f` | `5987a0f` | 一致 |
| working tree | clean | **有 1 个未跟踪文件**：`docs/phase2/PHASE2_0_B_RESEARCH.md`（Phase 2.0-B 的产出，尚未提交） | 唯一偏差 |
| remote | none | none | 一致 |
| tag | none | none | 一致 |

记录：

1. HEAD 仍是 Phase 1 baseline（`5987a0f`），Phase 1 与 Phase 2.0-A 在同一提交内；
   Phase 2.0-B 报告为未跟踪状态。**本阶段不提交、不改写历史。**
2. 该「未跟踪文件」是 **Phase 2.0-B 的既有产出**，不是本阶段引入的改动；
   本阶段没有修改、移动、删除它。

---

## 1. Design Inputs

### 1.1 文档输入

- `docs/PHASE2_0_A_BASELINE_REVIEW.md`（Phase 1 真实基线，16 张表 / 四条纪律 / F1–F16 观察）
- `docs/phase2/PHASE2_0_B_RESEARCH.md`（14 个外部项目研究 + Q-F1…Q-V3 问题清单）

### 1.2 代码输入（本阶段重新核对，逐项确认）

| # | 输入 | 核对结果 |
| :-- | :--- | :--- |
| 1 | `resources.file_path_key` | `TEXT NOT NULL UNIQUE`（v1）⇒ **跨库全局唯一** |
| 2 | `resources.sha256` | 列存在 + `idx_resources_sha256`；**全仓零写入** |
| 3 | `resources.quick_hash` | 列存在 + `idx_resources_quick_hash`；**全仓零写入** |
| 4 | `resources.content_key` | 列存在 + `idx_resources_content_key`；**全仓零写入** |
| 5 | `mods.guid` | `TEXT NOT NULL UNIQUE` |
| 6 | `mods.version` | `TEXT`（自由字符串） |
| 7 | `mods.resource_id` | FK → `resources(id)` `ON DELETE SET NULL` |
| 8 | `resource_mods` | PK(`resource_id`,`mod_guid`)；`relation` CHECK `uses|embeds`，写入恒为 `uses` |
| 9 | `resource_mod_usages` | PK(`resource_id`,`mod_guid`,`property`)；逐槽位使用事实 |
| 10 | `duplicate_groups` | `group_type` CHECK `file|content`；`hash_key`；`status` CHECK `suggested|confirmed|dismissed`；**零写入者** |
| 11 | `duplicate_members` | PK(`group_id`,`resource_id`)；`similarity`；`is_canonical`；**零写入者** |
| 12 | `tags` | `name_key UNIQUE`；**零写入者 / 零 Query API / 零 GUI** |
| 13 | `resource_tags` | PK(`resource_id`,`tag_id`)；同上 |
| 14 | `collections` | `name_key UNIQUE`；同上 |
| 15 | `resource_collections` | PK(`resource_id`,`collection_id`)；同上 |
| 16 | `core/classification/` | **仅 docstring 空壳**，`__all__ = []`；无实现、无调用方 |
| 17 | Parser 分类逻辑 | `card.py`：marker → `character_card` 或 `None`（→ `unknown`）；`zipmod.py`：无 `card_type` |
| 18 | Scanner 增量判定 | `(file_path_key, file_size, modified_time)` 全等则跳过解析（`_MTIME_EPSILON=1e-6`） |
| 19 | ResourceStore upsert | 卡片/zipmod 按 `file_path_key` 分支 INSERT/UPDATE；mods 按 `ON CONFLICT(guid) DO UPDATE` |
| 20 | Query Layer SELECT-only | `_execute_select` 只放行 `select` / `with`，否则抛 `ReadOnlyViolation` |

### 1.3 本阶段新增的本地证据（只读实验）

对真实样本目录 `G:\shuang\xinkks\KoikatuSunshine-Game\kksmannerscanlike` 做**只读**解析与哈希
（不写库、不改样本）：

| 事实 | 实测值 |
| :--- | :--- |
| 样本文件 | **36**（22 `.png` + 13 `.zipmod` + 1 `.md`） |
| 总体积 / 最大单文件 | **93.7 MB** / 15.4 MB |
| 卡片 marker 分布 | **KKS 21 / KK 1** |
| 卡片 dataID | 21/22 有；**distinct = 20** |
| 同名角色 | `HigashiyamaKobeni` ×3、`KugisakiNobara` ×3 |
| **字节重复组（sha256 相同）** | **1 组**：同 basename 位于不同目录，`sha256=ee44ba20…`、dataID 相同 |
| **同大小但内容不同** | `HigashiyamaKobeni` 两条均为 **481,250 B**，sha256 不同（`fe62d0c5…` vs `6bbe6b19…`） |
| 同角色跨格式 | `KugisakiNobara`：KKS(`ee44ba20…`) vs KK(`87436741…`)，**KK 无 dataID** |
| zipmod | 13 个；**guid distinct = 13（0 碰撞）**；每包 `manifest.xml` **恰好 1 个**；嵌套压缩包 **0 个** |
| mod version | 13 个全部非空，含自由值 **`"0"`** |
| 引用关系 | 卡片引用 **144** 个 guid；已安装 13；**缺失 134**；**孤立 3**（NoHair / elven_panst / koikatu.AltSlot.co_bot_19） |
| 全量 sha256 耗时 | **0.249 s**（≈ **376 MB/s**，93.7 MB） |
| 回归基线 | `pytest -q` → **671 passed**（33.37 s，0 failed / 0 skipped） |

> 这些证据用于**决定**设计，而不是装饰设计。

---

## 2. Design Principles

本设计遵循（与任务 §二十一 一致）：

1. 不为架构完整而增加实体；
2. 不因外部项目有某功能就认为本项目也需要；
3. **没有数据源的关系不建立**；
4. **没有真实样本支持的复杂模型不提前实现**；
5. Path / Content / Logical identity 必须分清；
6. Byte duplicate / MOD duplicate / semantic duplicate 必须分清；
7. Resource→MOD usage 与 MOD→MOD dependency 必须分清；
8. schema v2 永远冻结（`_V1_SQL` / `_V2_SQL` 不得回改）；
9. 不顺手修 Phase 1 technical debt；
10. 本阶段不写功能代码。

决策方法：

```text
证据（代码 / 样本 / 测试）→ 决定 → 理由 → 影响
若证据不足 → 明确写 INSUFFICIENT EVIDENCE，并给出「触发条件」
```

---

## 3. Identity Architecture

### 3.1 正式定义（逐概念回答全部 9 个问题）

**Library**

- 独立实体：**是**。稳定 ID：`libraries.id`（代理键）+ `root_path_key`（唯一业务键）。
- identity 字段：归一化根路径（`normalize_path_key`）。metadata：`name` / `notes` / `enabled` / `last_scan_at`。
- 多实体同 path：**否**（`root_path_key UNIQUE`）。多 path 指向同一 logical：不适用。
- 多 resource 同 content：不适用。多 MOD version 共存：不适用。
- identity 跨 Library 全局：是（唯一键全局）。受 path 改变影响：**是**（改根路径＝另一个 Library）。

**Path**

- 独立实体：**否** —— 它是 **Resource 的属性**（`file_path` 展示值 + `file_path_key` 归一化键）。
- 稳定 ID：无自有 ID。identity：不适用（它是别的东西的身份来源）。metadata：无。
- 受 path 改变影响：不适用。

**File**

- 独立实体：**否**（Phase 2 决定，见 §4）。当前 File ≡ Resource。
- 稳定 ID：无自有 ID（借用 Resource）。identity：不适用。

**Content**

- 独立实体：**否** —— 它是 Resource 上的**派生值**（`resources.sha256`），不是一个实体、没有表、没有 ID。
- 多 resource 拥有相同 content：**是**（这正是「字节重复」的定义）。
- identity 跨 Library 全局：值本身与 Library 无关。

**Resource**

- 独立实体：**是**。稳定 ID：`resources.id`。业务身份：`resources.file_path_key`（`UNIQUE`，**跨 Library 全局**）。
- metadata：`resource_type` / `type_source` / `name` / `display_name` / `file_size` / `modified_time` / `extension` / `card_marker` / `parse_status` / `scan_status` / `needs_review` / `metadata_json` / `relative_path` / 以及（Phase 2 起）`sha256`。
- 多实体同 path：**否**。多 path 指向同一 logical resource：**当前不建模**（不存在 logical-resource 实体）。
- 多 resource 同 content：**是**（允许，且可被查询）。
- identity 跨 Library 全局：**是**。受 path 改变影响：**是**（改名/移动 ⇒ 新 path key ⇒ 新行，旧行转 `missing`）。

**MOD**

- 独立实体：**是**。稳定 ID：`mods.id`。业务身份：`mods.guid`（`UNIQUE`，全局）。
- metadata：`name` / `author` / `version` / `website` / `file_path` / `file_path_key` / `library_id`。
- 多实体同 guid：**否**。多 path 指向同一 MOD：**不会共存**（guid 唯一 ⇒ 后扫到的文件成为该 MOD 的「当前文件」）。
- identity 跨 Library 全局：**是**。受 path 改变影响：**否**（身份是 guid，不是路径）。

**MOD Version**

- 独立实体：**否**（Phase 2 决定，见 §6）—— 它是 `mods.version` 上的**metadata 属性**（自由字符串）。
- 多 MOD version 共存：**不允许**（方案 A）。

**Author**

- 独立实体：**是**。稳定 ID：`authors.id`。业务身份：`authors.name_key`（`UNIQUE`，`trim + casefold`）。
- metadata：`name`（显示写法）/ `notes`。多实体同 name_key：**否**。多 resource 同 author：**是**（`resource_authors`）。
- identity 跨 Library 全局：**是**。受 path 改变影响：**否**。

### 3.2 横切回答

| 问题 | 答案 |
| :--- | :--- |
| 允许多个实体拥有相同 path？ | **否**（`resources.file_path_key UNIQUE`） |
| 允许多个 path 指向同一个 logical resource？ | **当前不建模**（无 logical-resource 实体；字节相同的两份副本是两行） |
| 允许多个 resource 拥有相同 content？ | **是**（Phase 2 起可查询） |
| 允许多个 MOD version 共存？ | **否**（Phase 2） |
| identity 是否跨 Library 全局？ | Resource / MOD / Author = **是**；Library = 自身全局唯一 |
| identity 是否受 file path 改变影响？ | Resource = **是**；MOD = **否**；Author = **否**；Content = **否** |

### 3.3 Identity Relationship Diagram（最终）

```text
                       ┌──────────────────────────────────────┐
                       │ Library                              │
                       │ identity: root_path_key (UNIQUE)     │
                       └───────────────┬──────────────────────┘
                                       │ resources.library_id  (0..1, SET NULL)
                                       ▼
    Path (属性)  ───────────────►  ┌────────────────────────────────────┐
    file_path (display)           │ Resource                           │
    file_path_key (UNIQUE,        │ identity: file_path_key (GLOBAL)   │
    cross-library)                │ id: resources.id                   │
                                  └──┬────────┬─────────┬──────────────┘
                                     │        │         │
              sha256 (派生值, 非实体) │        │         └─ resource_plugins ──► Plugin (字符串键)
                                     ▼        │
                              ┌────────────┐  │  resource_authors
                              │ Content    │  │        └───────────────────► Author
                              │ = sha256   │  │                              identity: name_key (UNIQUE)
                              │ (无表/无ID)│  │
                              └────────────┘  │  resource_mods / resource_mod_usages
                                              └───────────────────► MOD
                                                                    identity: guid (UNIQUE)
                                                                         │
                                                    mods.version ────────┘
                                                    = MOD Version
                                                    (属性, 非实体, 自由字符串)

  File ≡ Resource（Phase 2，1:1）
  本图刻意不含：File 实体、Content 实体、MOD Version 实体、MOD→MOD 边、logical-resource 实体
```

---

## 4. File / Resource Model

### 4.1 三种情况的最终判断

| 情况 | 定义 | 是否采用 | 依据 |
| :--- | :--- | :--- | :--- |
| **A** | `File = Resource`（1:1） | ✅ **采用** | 真样本 22 卡 / 13 zipmod 全部 1:1；13 个 zipmod **每包恰好 1 个 manifest、0 个嵌套压缩包**；同域 KKManager 也是 1:1 |
| B | `Resource 1:N File` | ❌ 不采用 | 无任何样本支持；本项目没有「派生文件 / sidecar」这类真实成员 |
| C | 其他（N:1 / N:M） | ❌ 不采用 | 无样本、无数据源 |

**注意**：PhotoPrism / Immich 的 1:N 是因为它们真有「原图 + 缩略图 + sidecar」；
本项目至今没有任何一个资源对应多份物理文件的实例，因此**不引入 File 实体**。

### 4.2 Q-F1｜多库路径重复的语义

- **Question**：同一物理文件出现在两个 Library 时，期望语义是什么？
- **Current Evidence**：`resources.file_path_key` 是 `UNIQUE` 且**不含 library_id**；
  `upsert_*` 在任何一次扫描里都会无条件 `UPDATE library_id`。真样本只有 1 个 Library；
  工作库 `data/` 为 0 个 Library。**没有多库交集样本**。
- **Decision**：**保持现状**（路径身份全局唯一，`library_id` 为「最后扫描到它的库」）；
  **不**在本阶段引入 per-library 的文件实例。多库语义标记为 **INSUFFICIENT EVIDENCE**。
- **Reason**：把 file identity 拆成 per-library 需要 File 实体（已被 §4.1 否决），
  属于「没有样本支持的复杂模型」；同时 Library Remove 语义（资源保留、`library_id` 置空）
  已依赖「资源可以不属于任何库」这一既有行为。
- **Impact**：`file_path_key UNIQUE` 保持不变；多库重叠路径的行为**必须在文档中写明**
  （当前是「改挂」而不是「两份记录」）。
- **Trigger（何时重开）**：真实出现「两个 Library 的根目录互相包含 / 有文件同时落在两库」的
  样本或用户报告时，重新评估。

### 4.3 Q-F2｜是否需要「一个逻辑资源对应多份物理文件」

- **Question**：KKS 真实资源是否需要 1:N / N:1？
- **Current Evidence**：22 张卡 = 22 个文件；13 个 zipmod = 13 个文件；每个 zipmod 内
  `manifest.xml` 计数恒为 1；无嵌套 zipmod/zip。**不存在 1:N 或 N:1 实例**。
- **Decision**：**保持 File = Resource（1:1）**，Phase 2 不建 `files` 表。
- **Reason**：证据为「反向证据」（样本中一次都没出现），且同域参考实现同为 1:1；
  引入 File 层会改变 scanner / store / query / GUI 的整条链路，收益却无实例支撑。
- **Impact**：scanner 的「一文件一事务」、`file_path_key` 唯一键、Query Layer 的
  `ResourceSummary` 契约全部不变；Phase 2 无需任何 File 相关 schema。

### 4.4 path identity 归属

| 问题 | 结论 |
| :--- | :--- |
| path identity 该属于 File 还是 Resource？ | 属于 **Resource**（因为 File 不是实体） |
| `file_path_key UNIQUE` 是否继续存在？ | **是**，不变（v1 冻结） |
| 若将来拆分 File/Resource 会怎样？ | path identity 会**迁移到 File**；这是未来的事，本设计不预做 |

### 4.5 File Entity **不提前引入**（Phase 2 冻结）

明确冻结：

| 可能的未来诱因 | Phase 2 的处理 |
| :--- | :--- |
| 未来可能出现**多 Library 重叠**（同一文件落在两个库） | **不**据此增加 File Entity；先按 §4.2 的触发条件重新评估 |
| 未来可能出现**一个逻辑资源对应多个文件**（1:N） | **不**据此增加 File Entity；先按 §4.3 的触发条件取得真实样本 |
| 未来可能出现**一个文件对应多个逻辑资源**（N:1） | 同上 |

- Phase 2 **不新增** `files` 表、不新增 `resource_files` 关联表、
  不把 `file_path_key` 从 `resources` 迁出；
- `file_path_key UNIQUE` 继续作为 Resource 的业务身份（§3.1、§13.2）；
- 重新评估的**唯一入口**是本文档 §4.2 / §4.3 已写明的触发条件
  （出现真实多库重叠样本，或出现 1:N / N:1 的真实实例），
  且必须走一次新的设计评审，而不是在实现阶段顺手改动。

**Reason**：设计原则 #4（没有真实样本支持的复杂模型不提前实现）；
样本反向证据（22 卡 + 13 zipmod 全部 1:1，每包 1 manifest）与同域参考实现一致。

---

## 5. Content Identity

### 5.1 Q-H1｜三个字段分别是什么（KEEP / DEPRECATED / UNUSED）

| 字段 | 设计决定 | 定义（Phase 2 生效） | 理由 |
| :--- | :--- | :--- | :--- |
| `resources.sha256` | **KEEP** | **唯一的 byte-content identity**：对文件**原始字节**做 SHA-256，存 64 位小写十六进制；只有它参与「内容相同」判定 | 现有列 + 现有索引可直接使用；外部共识（restic/Immich/Hydrus）都是「内容即字节哈希」 |
| `resources.quick_hash` | **DEPRECATED / UNUSED** | 在 Phase 2 中**不是一个概念**：不写、不读、不删除；若未来出现大库性能压力，再作为**非身份**的预筛缓存**重新设计** | 现状零写入；新增第二个「像身份」的值会让实现者混淆；真样本全量哈希仅 0.249 s，**无性能证据**需要预筛 |
| `resources.content_key` | **DEPRECATED / UNUSED** | 在 Phase 2 中**不是一个概念**：不写、不读、不删除；「逻辑同一」已确认**当前不可计算**（§5.4），因此不为其定义新语义 | 它的注释指向「卡片内容摘要」这一**语义身份**，而 2.0-B 已证明该语义在当前证据下不可得 |

#### 5.1.1 术语统一（唯一权威表述）

```text
quick_hash   = deprecated / unused
content_key  = deprecated / unused
```

- **Phase 2 不写、不读、不删除**这两个字段；
- 它们**不是** Phase 2 的动作项，**不得**在 Phase 2.1 / 2.2 / 2.3 中被清理；
- **真正的删除属于未来一个独立的 schema cleanup 阶段**（候选方案见 §11.3），
  该阶段不在 Phase 2 范围内；
- 关于它们的任何其他措辞（例如「Phase 2 删除」「立即移除」）**以本小节为准**。

> 本阶段只做决定，不改 schema（§11 给出的是未来的清理路径，**不是** Phase 2 的动作）。

### 5.2 Q-H2｜hash 何时计算

- **Question**：首次扫描？增量？按需？后台？大文件阈值？
- **Current Evidence**：Scanner 的增量门是 `(file_path_key, file_size, modified_time)`；
  真样本 93.7 MB 全量 SHA-256 = **0.249 s（≈376 MB/s）**；最大单文件 15.4 MB。
- **Decision**：**与解析同频** ——
  `新增文件` 或 `(size, mtime) 变化` 或 `mode="full"` ⇒ **解析并计算 sha256**；
  文件未变（增量跳过）⇒ **不重算**，沿用已存哈希。
  **不设大小阈值**，不在后台单独排队，不做「按需惰性计算」。
- **Reason**：复用现有增量门 = 不引入第二套失效语义；样本耗时表明当前规模无需优化；
  阈值/后台策略属于**没有证据支撑的复杂度**。
- **Impact**：`scan_records` 统计口径不变（`parsed` 计数已能代表「本次重解析并重算哈希」的文件数）。
- **Revision trigger**：若真实大库（如 ≥10 GB 或 ≥5,000 文件）导致扫描耗时不可接受，
  再评估后台计算 / 阈值 / 惰性计算 —— 届时需**实测基准**，不是猜测。

### 5.3 Q-H3｜hash invalidation

| 事件 | 是否触发重算 | 说明 |
| :--- | :--- | :--- |
| `size` 变化 | ✅ 重算 | 增量门直接失效 |
| `mtime` 变化 | ✅ 重算 | 增量门直接失效（容差 1e-6） |
| `path` 变化（移动/改名） | ✅（以**新行**形式） | 新 `file_path_key` ⇒ 新资源行 ⇒ 计算哈希；旧行转 `missing`（当前**不识别为「移动」**） |
| 文件被替换但 `size` 与 `mtime` 都不变 | ❌ **不重算** | 这是既有增量门的已知盲区（Phase 1 不变式），本设计**不改变**它 |
| `mode="full"` | ✅ 全部重算 | 现有语义 |
- **Decision**：只承认「由 (size, mtime) 变化或 full 扫描触发」这一条失效路径。
- **Reason**：任何更强的失效判定（如信任 mtime 之外的元数据）都会改写 Phase 1 的扫描不变式。
- **Impact**：`sha256` 的可信范围 = 「与写入该行时记录的内容状态一致」；
  该盲区必须写进 invariant（§13）与验证矩阵（§14）。

### 5.4 Q-H4｜byte-identical / same character / same MOD 必须分开

真样本同时给出了三者的**反例**：

| 概念 | 判据 | 真样本实例 | 结论 |
| :--- | :--- | :--- | :--- |
| **byte-identical** | `sha256` 相同 | `Kugisaki Nobara` 两份同名文件（不同目录）sha256 相同 | ✅ 可判定（Phase 2 起） |
| **same character（重导出）** | 语义相同、字节不同 | `HigashiyamaKobeni` 两条：**同为 481,250 B，sha256 不同、dataID 不同** | ❌ **NOT DETECTABLE WITH CURRENT EVIDENCE** |
| **same character（跨格式）** | KKS / KK 同一角色 | `KugisakiNobara`：KKS `ee44ba20…` vs KK `87436741…`（KK 卡**没有 dataID**） | ❌ NOT DETECTABLE |
| **same MOD** | `guid` 相同 | 样本 0 例 | ✅ 可判定（但 Phase 2 不建模多版本，§6） |

- **Decision**：`sha256` **仅**代表 byte-identical；**不代表**同角色、**不代表**同 MOD。
  `dataID` **继续只作 metadata**（真样本中它与字节一致，但 KK 卡完全没有它，
  且 Phase 1 已确认同一角色不同导出会得到不同 dataID —— 单凭这一点就不能作为身份）。
- **Reason**：把三种语义合并成一个「content identity」会在产品语义上造成
  「相同角色被误判为重复」或「不同资源被误合并」。
- **Impact**：任何面向用户的「重复」文案必须限定为「**字节完全相同**」；
  同角色/跨格式判定**不进入 Phase 2**。

### 5.5 Q-H5｜hash 存哪里

- **Question**：`resources` 还是独立 `content` 实体？
- **Current Evidence**：`resources.sha256` + `idx_resources_sha256` 已存在且零写入；
  File ≡ Resource（§4）。
- **Decision**：**保留在 `resources`**，**不建 content 实体/表**。
- **Reason**：
  1. File ≡ Resource ⇒ 一个资源恰好一份字节内容，没有必要再引一层；
  2. 「哪些资源字节相同」是**可查询的派生结果**（`GROUP BY sha256`），
     与 `duplicate_groups` 的定位重合，独立实体只会制造第二个真相来源；
  3. 独立 content 实体只有在「内容本身有独立生命周期/元数据（如分块存储、共享引用计数）」
     时才有价值 —— 本项目只做索引，不做存储。
- **Impact**：Query Layer 可以直接在 `ResourceSummary` 上暴露 `sha256`（可选），
  不改变现有 DTO 语义；`resources` 行仍是唯一事实来源。

### 5.6 H6｜SHA-256 读取一致性规则（read-consistency）

**问题**：计算 SHA-256 需要读完整文件；如果读的过程中文件被外部程序改写，
算出来的哈希就**不描述任何稳定状态**，写库会污染内容身份。

**规则（Phase 2.1 必须实现）**：

```text
1. 读取前记录：size_before, mtime_before（即 Scanner 已经 stat 到的那一对）
2. 读取文件全部字节并计算 SHA-256
3. 计算完成后重新 stat：size_after, mtime_after
4. 若 size_after != size_before 或 mtime_after != mtime_before
      -> 本次 hash 不得写入数据库（丢弃），该文件按「已变化」处理
5. 比较与容差沿用 Scanner 现有语义（mtime 容差 _MTIME_EPSILON = 1e-6）
6. 处理方式沿用现有 changed / 失败路径：不新增文件锁、不新增 watcher、
   不引入重试系统或队列；下一次扫描自然会重新处理该文件
```

**边界与理由**：

- 该规则**不**改变增量门：命中增量跳过的文件根本不读，也就不涉及本规则；
- 该规则**不**试图消除「同 size 同 mtime 被替换」的既有盲区（§5.3），
  只保证「写进库的哈希确实对应我们读过的那份字节」；
- 「检测到变化」**不等于**失败：沿用现有语义，该文件本次不产生新哈希，
  数据库保持既有状态，扫描继续处理其它文件（失败隔离不被破坏）。

**Decision**：**采纳**（写入 §13.3 Content invariant 与 §14 验证矩阵）。

---

## 6. MOD / Version Model

### 6.1 Q-M1｜GUID 是什么

- **Question**：GUID 是否代表 logical MOD？
- **Current Evidence**：`mods.guid` 为 `UNIQUE`；真样本 13 个 zipmod ⇒ **13 个 distinct guid（0 碰撞）**；
  同域 KKManager 的 `ModInfoBase` 也以 `Guid` 为逻辑键，并按 `Guid` 分组处理重复。
- **Decision**：**是** —— GUID = logical MOD 身份；`mods` 表 = 一个 GUID 一行。
- **Reason**：同域实践 + 本项目现有 schema + 零反例，三者一致。
- **Impact**：`resource_mods` / `resource_mod_usages` 继续以 `mod_guid` 作为跨表引用键（不变）。

### 6.2 Q-M2｜同 GUID 是否允许多版本共存

| 方案 | 定义 | 采用 |
| :--- | :--- | :--- |
| **A** | `GUID = logical MOD`，只保留当前版本 | ✅ **采用** |
| B | `MOD` + 独立 `MOD Version` 实体，一个 MOD 多个 Version | ❌ 不采用 |
| C | 其他 | ❌ 不采用 |

- **Question**：一个 GUID 是否允许多个 version 共存？
- **Current Evidence**：**真样本 0 例同 GUID 多版本**（13/13 distinct）；
  `ON CONFLICT(guid) DO UPDATE` 使多版本必然塌成一行；同域 KKManager 视同 GUID 为重复并只保留一份。
- **Decision**：**不允许共存（方案 A）**；多版本建模标记为 **INSUFFICIENT EVIDENCE**。
- **Reason**：引入 Version 实体需要（1）新的表与唯一约束、（2）Resource↔Version 的关联语义、
  （3）version 比较语义 —— 而 manifest 的 version 是自由字符串（真样本里存在 `"0"`），
  KKS 也没有任何依赖约束需要版本比较。**没有数据源、没有样本、没有产品需求**，三者同时缺失。
- **Impact（方案 A 的后果，必须写明）**：
  1. `mods` 行 = 「当前已知版本」；重扫到新版本会**覆盖** `version`/`name`/`author`/`file_path` 等字段，
     **不保留历史**（与 Phase 1 现状一致）；
  2. 若同一 GUID 的两个 zipmod 文件**同时存在**，`mods` 只会指向其中一个（最后扫描到的），
     另一个仍作为 `resources(type='mod')` 存在但**不再有 `mods` 行**指向它 ——
     这是一条**已知且可观测的后果**，列为 Open Question（§17），本阶段不新增机制。
- **不做的三件事**：不建 `mod_versions` 表；不加 `mods` 历史表 / audit 表；
  不引入 version 比较（排序/约束）语义。

### 6.3 Q-M3｜是否需要保留「旧版本曾被扫到」的历史

- **Question**：现状的静默覆盖是否可接受？是否需要 audit？
- **Current Evidence**：`mods` 只有 `created_at` / `updated_at`，没有历史表；
  Phase 1 明确「不做审计」；真实样本 0 例触发。
- **Decision**：**Phase 2 不做历史/审计**；覆盖行为**正式承认为产品语义**
  （「mods 表保存该 GUID 当前已知的 manifest 信息」）。
- **Reason**：没有用户需求、没有样本触发；审计需要额外的表与保留策略，属于「为完整而加实体」。
- **Impact**：`mods.updated_at` 成为唯一的时间证据；文档必须写明覆盖语义。
- **Revision trigger**：出现「用户想看到同一个 MOD 的多个版本」的真实请求时重新评估。

### 6.4 MOD Version 在 Phase 2 **保持关闭**（不得因 SHA-256 / duplicate 重新打开）

为消除歧义，明确冻结以下四条（Phase 2 全程有效）：

```text
GUID        = logical MOD identity（mods.guid UNIQUE）
mods        = one row per GUID
version     = current manifest metadata（mods.version，自由字符串）
同 GUID 多文件 / 多版本的现有覆盖语义 = 保持不变
```

- **不引入** `MOD Version` 实体、**不引入** `MOD Instance` 实体、**不引入**历史 / audit 表；
- **不因为**新增 `sha256` 或字节重复能力而改变 MOD 侧的模型 ——
  内容身份描述的是「文件字节」，与「MOD 逻辑身份」是两个维度（§5.4）；
- 同 GUID 出现多个 zipmod 文件时，现有行为（`mods` 指向最后扫描到的那一个）**保持不变**，
  该情形仍列在 Open Question（§17.3 OQ-3），等待真实触发条件。

**Reason**：真样本 0 例同 GUID 多版本；manifest 的 version 无比较语义；
Phase 2 的新增能力（哈希 / 字节重复）**不产生**对版本建模的任何需求。

---

## 7. Relationship Model

### 7.1 Q-D1｜是否建立 MOD→MOD dependency graph

- **Question**：当前 Phase 2 是否建立 MOD→MOD 依赖图？
- **Current Evidence**：
  1. 本项目 `parse_manifest_xml` 只认 `guid / name / author / version / website`——**无依赖字段**；
  2. 同域 KKManager 的 `ModInfoBase` 字段同样只有 guid/name/version/author/description/website/games；
  3. 卡片侧的 144 个 guid 引用是「**卡片使用了哪些 mod**」，不是「mod 需要哪些 mod」；
  4. 13 个已安装 MOD 中 3 个孤立（无任何卡片引用），134 个被引用但缺失 —— 这些数字全部是 usage 语义。
- **Decision**：**NO** —— Phase 2 **不建立** MOD→MOD 依赖图，**不新增任何依赖表/边表**。
- **Reason**：**没有数据源就没有关系**（设计原则 #3）。CKAN 的依赖来自中央元数据仓库、
  Fabric 的依赖来自 `fabric.mod.json`，本项目两者都不存在。
- **Impact**：`resource_mods` / `resource_mod_usages` 继续作为**唯一**的跨实体边；
  「缺失 MOD」仍然只表示「卡片引用了本地没有的 guid」，**不表示依赖缺失**。

### 7.2 Q-D2｜`resource_mods.relation` 的 `uses` / `embeds`

- **Question**：这两个值是否继续存在？
- **Current Evidence**：v1 CHECK 已允许 `uses|embeds`；写入层**硬编码 `uses`**；
  `embeds` 全仓零写入。
- **Decision**：**KEEP（原样保留，不启用、不删除）**。
- **Reason**：v1 schema 已冻结，「改 CHECK」需要重建表，成本 > 收益；
  该值当前无害且被 Query Layer 视作普通字段。
- **Impact**：`relation` 在 Phase 2 之后仍然是常量 `'uses'`；
  文档需注明「`embeds` 为历史保留值，当前无生产者」。

### 7.3 Q-D3｜`resource_mod_usages` 是否保持现有语义

- **Question**：逐槽位使用事实是否会被「统一关系表」替代？
- **Current Evidence**：`resource_mod_usages` 是权威使用事实（PK 含 `property`），
  Query Layer 的 property 语义分类、`has_missing_mods`、详情面板都建立在它之上；
  真样本 22 张卡引用 144 个 guid，验证过 134 缺失 / 3 孤立的口径。
- **Decision**：**保持不变**；**不引入 generic relation table**。
- **Reason**：`resource_mod_usages`（卡片用在哪）与未来的「依赖」（mod 需要谁）
  是语义不同的两类边；把它们塞进一张通用关系表只会让两种语义互相污染，
  且会破坏 Query Layer / GUI 的既有契约。
- **Impact**：Phase 2 的关系层**零 schema 变化**。

---

## 8. Duplicate Model

### 8.1 三类重复必须分开

| # | 类别 | 判据 | 真样本证据 | 当前能否判定 |
| :-- | :--- | :--- | :--- | :--- |
| 1 | **Byte duplicate** | `sha256(A) == sha256(B)` | ✅ 1 组：`Kugisaki Nobara` 同名两文件（不同目录），sha256 与 dataID 均相同 | ✅ Phase 2 起可判定 |
| 2 | **Same MOD identity** | `guid(A) == guid(B)`，version/bytes 可不同 | ❌ 0 例（13 zipmod / 13 distinct guid） | ⚠️ 可判定（guid），但**Phase 2 不建模多版本**；同 GUID 双文件目前会塌成「一个 mods 行」 |
| 3 | **Same logical character / resource** | 语义相同、字节不同 | ✅ 有：`HigashiyamaKobeni` 两条 481,250 B 但 sha256 不同；`KugisakiNobara` KKS vs KK | ❌ **NOT DETECTABLE WITH CURRENT EVIDENCE** |

### 8.2 Q-U1｜Phase 2 的「重复」定义包含哪几类

- **Question**：Phase 2 是否把三类都算重复？
- **Current Evidence**：见 §8.1 表格；第 3 类既无判据也无样本可验证的算法；
  第 2 类虽有 `guid` 判据，但样本 0 例，且方案 A 已决定不建模多版本（§6）。
- **Decision**：
  - **第 1 类（byte）⇒ 纳入 Phase 2**（依赖 §5 的内容身份）；
  - **第 2 类（same GUID）⇒ 不纳入 Phase 2 的「重复」功能**（其语义已在 §6 定为「同一 logical MOD」）；
  - **第 3 类（logical）⇒ 明确排除**，标记 **NOT DETECTABLE WITH CURRENT EVIDENCE**。
- **Reason**：只有第 1 类同时具备「稳定判据 + 真实样本 + 零新数据源需求」。
- **Impact**：Phase 2 的重复功能范围 = **字节完全相同**；GUI/CLI 文案必须照此措辞。

### 8.3 Q-U2｜现有 `group_type`（`file` / `content`）是否足够

- **Question**：是否需要新增 `logical` 类型？
- **Current Evidence**：`duplicate_groups.group_type` CHECK 为 `file|content`，
  `hash_key` 注释写「sha256 或 content_key」；两值**均零写入**；
  `content_key` 已在本设计中被判定为 **deprecated / unused**（§5.1.1）。
- **Decision**：**保持两值不变**，且**在 Phase 2 不使用这两张表**（见 §8.4）。
  **不新增 `logical` 类型**。
- **Reason**：新增 `logical` 会为一个已被证明**不可计算**的语义留下一个空槽
  （设计原则 #4）；`file` / `content` 的历史语义与 `hash_key` 一起保留即可。
- **Impact**：v1 的 CHECK 不变；`duplicate_groups.hash_key` 的注释将来需随 `content_key`
  的处置一并说明（属 Phase 1 债务，本阶段不修改）。

### 8.4 Q-U3｜duplicate = derived query 还是 persisted entity

| 维度 | Derived query（`GROUP BY sha256`） | Persisted entity（`duplicate_groups/members`） |
| :--- | :--- | :--- |
| 可重复计算 | ✅ 随时重算，结果必然与数据一致 | ⚠️ 需保证组与资源状态同步（资源被删/改后要维护） |
| 历史状态 | ❌ 无历史（只反映当前） | ✅ 可保留 suggested/confirmed |
| 用户确认 / dismissed / canonical | ❌ 无处存放 | ✅ `status` + `is_canonical` 原生支持 |
| 性能 | ✅ 有 `idx_resources_sha256`，样本规模下微不足道 | ⚠️ 需要写入 + 维护成本 |
| Migration complexity | ✅ 零 | ⚠️ 需要生产者 + 生命周期规则 |

- **Question**：Phase 2 采用哪种？
- **Current Evidence**：两张表自 v1 起零写入；没有任何用户确认/忽略/canonical 的需求证据。
- **Decision**：**Phase 2 = Derived query**。
  `duplicate_groups` / `duplicate_members` **保持原样、不写入、不删除**（继续预留）。
- **Reason**：
  1. 字节重复的真相**已经**存在于 `resources.sha256`，派生查询不会产生第二真相来源；
  2. 用户确认类需求（dismiss / canonical）**目前没有任何证据**，
     为之落库等于「为完整而加实体」；
  3. 一旦将来真的需要「用户确认/忽略」，再把派生结果**提升**为持久组，
     迁移路径清晰（现有两张表就是为此预留的）。
- **Impact**：Phase 2 的重复能力 = `ResourceQuery` 新增一个只读派生查询
  （例如按 sha256 分组列出重复资源）；GUI/CLI 只消费该结果，不写库。
- **提升为 persisted 的触发条件**：出现「用户要标记某组不是重复 / 要指定保留项」的真实需求。

---

## 9. Classification Model

### 9.1 Q-C1｜是否建立独立 classification layer

- **Question**：保持 parser-driven、建立独立分类层、还是其他？
- **Current Evidence**：
  1. `core/classification/` 是**仅 docstring 的空壳**（`__all__ = []`），**全仓无调用方**；
  2. 实际类型来源：`parsers/card.py` 用 marker 判定 `character_card`；
     `scanner/store.py` 对 zipmod 硬编码 `'mod'`；其余落 `unknown`；
  3. 真样本 22 张卡**全部解析成功、marker 全部可识别**（21 KKS + 1 KK）——**没有一个需要推断的案例**；
  4. 外部研究（2.0-B §7）显示：没有任何成熟项目把分类做成独立于解析器的通用层。
- **Decision**：**A. 保持 parser-driven**；**不建立**独立 classification layer；
  `core/classification/` 的存废列入 Open Question（§17），**不在 Phase 2 处理**。
- **Reason**：无调用方、无失败案例、无外部先例 —— 三者同时缺失时引入引擎是纯粹的架构装饰。
- **Impact**：Phase 2 不新增分类相关模块、表或字段。

### 9.2 未来类型如何演进（保持 parser-driven 的前提下）

| `resource_type` | 现状 | 未来如何支持 |
| :--- | :--- | :--- |
| `character_card` | ✅ 已产出（marker 命中） | 维持；新增 marker 只需扩 `CHARACTER_CARD_MARKERS` + 解析逻辑 |
| `mod` | ✅ 已产出（zipmod + manifest + guid） | 维持 |
| `outfit_card` | ❌ 未产出（enum 允许） | 需要**新的解析器**（服装卡格式），不是分类层 |
| `scene_card` | ❌ 未产出（`parsers/__init__` 明写「Phase 2」） | 同样需要解析器；届时由解析器直接给出类型 |
| `unknown` | ✅ 默认值 | 维持；由 `needs_review` + review reason 提示用户 |

`needs_review` 的现有规则（`parse_status != ok` 或 `name` 为空）与
`ResourceQuery.review_reasons()` 的只读推导**保持不变**；Phase 2 不改变其语义。

---

## 10. Tags / Collections Decision

### 10.1 Q-C2｜Tags / Collections 是否进入 Phase 2

- **Question**：Phase 2 是否包含 tags / collections？
- **Current Evidence**：
  1. 四张表（`tags` / `resource_tags` / `collections` / `resource_collections`）自 v1 起存在，
     **零写入者、零 Query API、零 GUI**；
  2. 外部研究（2.0-B）显示它们是**用户组织层**（PhotoPrism 相册/标签、Hydrus 标签、beets 标签），
     与 identity / dependency 主线正交；
  3. 没有任何真实用户需求或样本证据表明现在需要分类组织；
     工作库 `data/` 目前是空的（0 资源）。
- **Decision**：**不进入 Phase 2（OUT OF SCOPE）**；四张表**保持原样**。
- **Reason**：
  1. 它们解决的问题（用户怎么组织自己的库）**不是** Phase 2 的问题（身份与重复）；
  2. 它们**不依赖**新的 identity architecture（`resource_id` 已足够），因此不会被 Phase 2 阻塞；
  3. 纳入会同时放大范围（需要写入 API + 查询 + GUI + 交互确认），
     而「已经有表」**不是**现在实现的理由。
- **Impact**：Phase 2 零 schema 变化；Tags/Collections 顺延到用户组织相关阶段（§15/§16）。
- **若将来纳入，需要补什么**（仅记录，不设计）：写入 API（`core` 侧）、Query 投影、
  GUI 入口、以及「加标签/入 Collection 不移动文件」的既有语义。

---

## 11. Schema v3 Design

### 11.1 核心结论：**Phase 2 不需要 schema v3**

逐项核对 Phase 2 的设计需求与现有 schema：

| Phase 2 需求 | 需要的 schema | 现有 schema 是否已满足 |
| :--- | :--- | :--- |
| 内容身份（byte） | 一个可写的 sha256 列 + 索引 | ✅ `resources.sha256` + `idx_resources_sha256` |
| 字节重复查询 | 同上（`GROUP BY sha256`） | ✅ 无需新表 |
| MOD 身份（方案 A） | `mods.guid UNIQUE` | ✅ 已有 |
| Resource→MOD 使用关系 | `resource_mods` / `resource_mod_usages` | ✅ 已有，语义不变 |
| MOD→MOD 依赖 | —— | ❌ **不需要**（无数据源，§7.1） |
| 分类 | —— | ✅ parser-driven，不需要 schema |
| Tags / Collections | —— | ❌ 不在 Phase 2 范围 |

⇒ **Phase 2 的全部设计需求都落在既有 schema 内**；`SCHEMA_VERSION` 在 Phase 2 期间**保持 2**。

**因此本阶段不创建 v3，也不建议在 Phase 2 创建 v3。**

### 11.2 唯一的 schema 相关决定：两个字段 = deprecated / unused（删除推迟到未来独立阶段）

§5.1 的一致表述是（以 §5.1.1 为准）：

```text
quick_hash   = deprecated / unused
content_key  = deprecated / unused
```

- **Phase 2 不写、不读、不删除**这两个字段；它们**不是** Phase 2 的动作项；
- 它们**当前零写入**，存在的唯一坏处是「命名上像身份字段」；
- 因此 Phase 2 只通过（a）本文档的显式声明 +（b）验证矩阵中的断言（§14）防止误用；
- **真正的删除属于未来一个独立的 schema cleanup 阶段**（§11.3 是该阶段的候选设计），
  该阶段**不在 Phase 2 范围**内。

### 11.3 未来独立 schema cleanup 阶段的候选 v3 设计（**不属于 Phase 2**）

本节描述的是**未来某个独立的 schema cleanup 阶段**的候选方案，
用于把那两个 `deprecated / unused` 列真正移除。
**Phase 2 不执行、不触发、不计划这个阶段**；此处仅记录设计以备将来使用。

若该阶段被正式立项，v3 的最小内容如下（**仅为设计，不执行**）：

```sql
-- v3（可选）：移除两个从未写入、且与「内容身份」语义冲突的列
DROP INDEX IF EXISTS idx_resources_quick_hash;
DROP INDEX IF EXISTS idx_resources_content_key;
ALTER TABLE resources DROP COLUMN quick_hash;
ALTER TABLE resources DROP COLUMN content_key;
```

约束与前置条件（设计要点）：

1. **不得**修改 `_V1_SQL` / `_V2_SQL`；只能**新增** `_V3_SQL` + `MIGRATIONS[3]`；
2. `DROP INDEX IF EXISTS` 幂等；`DROP COLUMN` **不幂等** ⇒ 实现阶段必须像
   `db._add_column_if_missing` 一样，先查 `column_names()` 再决定是否执行
   （新增 `_drop_column_if_present`）；
3. `DROP COLUMN` 要求 SQLite ≥ 3.35，且被索引 / 被 CHECK 引用的列不能直接删；
   本设计中两列**先删索引再删列**，且它们不在任何 CHECK / 生成列 / FTS 触发器中
   （FTS 只引用 `display_name/name/author/series/description/notes`）；
4. 若目标环境 SQLite < 3.35，唯一替代是「12 步表重建」——**不推荐**
   （`resources` 被 8 张表以 FK 引用，重建风险显著高于收益）；
5. **不涉及** CREATE TABLE / DROP TABLE / 新 UNIQUE / 新 FOREIGN KEY / 新 CHECK。

> 明确声明：**该清理不属于 Phase 2 范围**（§15）。

---

## 12. Migration Strategy

### 12.1 Q-V1｜Phase 2 的迁移策略

- **Question**：若需要 schema v3，迁移策略是什么？
- **Current Evidence**：§11.1 已证明 Phase 2 **不需要** v3；当前
  `SCHEMA_VERSION = 2`、`MIGRATIONS = {1, 2}`、`MIGRATION_ADDED_COLUMNS = {2: card_marker}`。
- **Decision**：**Phase 2 不执行任何迁移**；`SCHEMA_VERSION` 保持 2。
  同时给出「将来若做 v3」的完整迁移与回滚设计（下方 12.2–12.4），以备使用。
- **Reason**：没有 schema 变更需求时执行迁移，等于制造风险而不产生价值。
- **Impact**：Phase 2 的所有工作都在 v2 上完成；671 项回归与真实样本只读不变量直接沿用。

### 12.2 迁移顺序与幂等性（设计，供未来使用）

```text
Schema v1  →  Schema v2  →  Schema v3
（永不回改）   （永不回改）    （仅新增）
```

- 顺序：`initialize()` 依 `sorted(MIGRATIONS)` 依次应用**大于当前版本**的迁移；
- 加列：沿用 `_add_column_if_missing`（先查 `PRAGMA table_info`）；
- 删列（v3）：新增 `_drop_column_if_present`（同样先查列是否存在）；
- 删索引：`DROP INDEX IF EXISTS` 天然幂等；
- 迁移标记：应用后写 `app_meta.schema_version`（现有机制）。

### 12.3 两类数据库的升级路径（设计）

| 起点 | 路径 | 结果 |
| :--- | :--- | :--- |
| **已有 v2 库**（含真实数据） | 只应用 v3：删索引 → 删两列 | 数据零丢失（两列本来恒为 NULL）；`sha256` 值保留 |
| **全新空库** | v1 建表 → v2 加列/索引 → v3 删列 | 净效果 = 不含 `quick_hash` / `content_key` 的 v2 等价结构 |

### 12.4 Rollback（必须区分 code rollback 与 database rollback）

**Code rollback**

```text
git checkout <Phase 2 之前的提交>      # 本设计下即 5987a0f（Phase 1 baseline）
```

**Database rollback**（v3 → v2，设计 SQL）

```sql
ALTER TABLE resources ADD COLUMN quick_hash TEXT;
ALTER TABLE resources ADD COLUMN content_key TEXT;
CREATE INDEX IF NOT EXISTS idx_resources_quick_hash ON resources(quick_hash);
CREATE INDEX IF NOT EXISTS idx_resources_content_key ON resources(content_key);
```

关键事实（决定回滚难度）：

1. **v2 代码从不读取这两列**（全仓零写入、零读取），因此
   **v3 之后的数据库对 v2 代码仍然可用** —— 代码回滚**不强制**要求数据库回滚；
2. 数据库回滚**没有数据损失**（两列在 v1–v3 期间恒为 NULL）；
3. v3 写入的 `sha256` 值在回滚到 v2 代码后**仍然安全**（v2 代码不读它，也不会覆盖它）；
4. 回滚前建议先备份 `data/kks_resource_manager.db`（SQLite 单文件 + WAL 需一并处理）。

> 「git 回滚」**不能**代替数据库回滚说明，上表两者已分开列出。

---

## 13. Invariants

### 13.1 Path

- **P1** A path is an attribute, never an entity.
- **P2** A path is identified by its normalized key (`file_path_key` = expand + absolutize +
  separator-normalized + casefolded).
- **P3** No two Resource rows may share a `file_path_key` (global, across all Libraries).
- **P4** Changing a path (rename/move) produces a **different** path key; it must never be
  silently treated as the same Resource.

### 13.2 File / Resource

- **F1** In Phase 2, File ≡ Resource: exactly one physical file backs one Resource.
- **F2** A Resource must always have exactly one `file_path_key`.
- **F3** Scanning must never create a second Resource row for an already-known path key.
- **F4** A Resource whose file disappears is marked `scan_status='missing'`; the row is never deleted.

### 13.3 Content

- **C1** Content is a derived value, not an entity: it has no table and no ID.
- **C2** `resources.sha256` is the SHA-256 of the file's **exact bytes**, stored as 64 lowercase
  hex characters.
- **C3** A sha256 value must only be written together with the `file_size` / `modified_time`
  of the same read — a stored hash always describes the stored file state.
- **C4** sha256 equality means **byte-identical only**; it must never be presented as
  "same character", "same MOD", or "same logical resource".
- **C5** `quick_hash` / `content_key` are **deprecated / unused** (see §5.1.1). Phase 2 must
  **not write, not read, and not delete** them; their removal belongs to a future independent
  schema cleanup phase, never to Phase 2.
- **C6** No hash may be computed from anything other than the file bytes (no name, no path,
  no metadata, no dataID).
- **C7 (read-consistency)** A computed SHA-256 may only be written to the database if
  `size` and `mtime` are **unchanged across the read**:
  record `(size_before, mtime_before)` → read bytes / compute hash →
  re-check `(size_after, mtime_after)`; if either differs, **the hash must be discarded**
  and the file is treated as "changed" using the existing Scanner semantics
  (mtime tolerance `_MTIME_EPSILON = 1e-6`). No file locks, no watcher, no retry system.
- **C8** A stored hash always describes the exact byte content that was read while
  `(size, mtime)` remained stable; C7 must never be weakened by "hash anyway".

### 13.4 Resource

- **R1** One Resource identity = one `file_path_key`; `resources.id` is the stable surrogate ID.
- **R2** `resource_type` is decided by the Parser (card) or the store's zipmod rule; the DB CHECK
  is the only additional constraint.
- **R3** User-confirmed types (`type_source='user'`) must survive re-scans (existing behavior).
- **R4** `scan_status` and `parse_status` are orthogonal; a resource may be `present` + `failed`.

### 13.5 MOD

- **M1** One logical MOD identity is identified by GUID.
- **M2** `mods.guid` must stay unique: a MOD version must never create a second logical MOD.
- **M3** A re-scan of the same GUID updates the **current known manifest** of that MOD
  (`mods` row = current state); the design accepts this overwrite as product semantics.
- **M4** MOD identity is independent of file path: moving the zipmod must not create a new MOD.
- **M5** `resource_mods` / `resource_mod_usages` reference MODs **by GUID string**, never by `mods.id`.

### 13.6 Version

- **V1** Version is an attribute of a MOD (`mods.version`), not an entity.
- **V2** Version strings are free-form and must never be compared, sorted, or used as identity.
- **V3** Multiple versions of the same GUID must not coexist in Phase 2.

### 13.7 Duplicate

- **D1** Byte duplicate = identical `sha256` over identical-size files; it is a **derived**
  relationship in Phase 2.
- **D2** `duplicate_groups` / `duplicate_members` are reserved and must stay unwritten in Phase 2.
- **D3** No duplicate result may imply deletion; scanning/analysis never removes resources or files.
- **D4** "Same character" / "same logical resource" is **not** computed in Phase 2.

### 13.8 Relationship

- **X1** `resource_mod_usages` (per-slot usage) is the authoritative "card uses MOD" fact.
- **X2** `resource_mods` is the aggregate rollup (PK `resource_id` + `mod_guid`).
- **X3** There is **no** MOD→MOD edge in Phase 2; "missing MOD" means "referenced but not installed",
  never "dependency unsatisfied".
- **X4** A resource may reference a MOD that has no `mods` row (not installed); `mod_id` stays NULL.
- **X5** No generic Entity/Relation table may be introduced for File/Content/MOD/Duplicate/Dependency.

### 13.9 Scanner / Read-only

- **S1** The incremental gate stays `(file_path_key, file_size, modified_time)`.
- **S2** Hash is computed iff the file is (re)parsed: new file, changed size/mtime, or `mode='full'`.
- **S3** Scanner and Parser must never modify, move, rename, or delete user files.
- **S4** Relations are rebuilt (delete-then-insert) inside the same per-file transaction.

---

## 14. Validation Matrix

> 本阶段只**设计**测试矩阵，不实现测试。

### 14.1 Existing regression（必须保持）

| 检查 | 现状 | Phase 2 目标 |
| :--- | :--- | :--- |
| `pytest -q` | 671 passed（本次实测 33.37 s） | 不得回归；新增用例只能追加 |
| `node tools/validate_schema.mjs` | 16 表 / 全项 OK / exit 0 | 继续通过（Phase 2 无 schema 变更） |
| `node tools/check_model_sync.mjs` | exit 0 | 继续通过 |
| 真实样本只读不变量 | `tests/conftest.py::sample_root` sha256 前后一致 | 继续通过（哈希计算不得写入样本） |

### 14.2 Identity

| 用例 | 期望 |
| :--- | :--- |
| path change（改名/移动） | 新 path key ⇒ 新 Resource 行；旧行转 `missing`；不视为同一资源 |
| content unchanged（重扫同文件） | 走增量跳过；`sha256` 不变、不重算 |
| content changed（同路径改内容） | size/mtime 变化 ⇒ 重解析 ⇒ `sha256` 更新 |
| same content, different path | 两个 Resource 行、相同 `sha256`；派生重复查询能成组 |
| same GUID, different version | 仍只有 1 个 `mods` 行；`version` 被覆盖为最新（方案 A 语义） |
| same version, different path | 同一 GUID ⇒ 仍 1 个 `mods` 行；记录「另一个 mod 类型资源行无 mods 指向」的现状 |
| duplicate file（真样本场景） | 派生查询返回该组；两组 sha256 相同、dataID 相同 |
| 同大小不同内容（真样本场景） | **不得**被判为重复（481,250 B 两条） |
| 跨格式同角色（真样本场景） | **不得**被判为重复（KKS vs KK） |
| **hash 读取一致性（C7）** | 若文件在计算期间被改写（`size`/`mtime` 变化），本次 hash **不写入**数据库，且不产生错误状态；下一次扫描重新处理该文件 |

### 14.3 Scanner

| 用例 | 期望 |
| :--- | :--- |
| incremental scan | 未变文件跳过解析、不重算哈希 |
| full scan | 全部重解析并重算哈希；无重复行 |
| unchanged file | `scan_records.files_skipped` 增长 |
| modified file | `files_changed` 增长；关系重建无残留 |
| moved file | 新行 inserted；旧行 missing（当前不识别为 move） |
| deleted file | 仅标记 `missing`，不删行、不删文件 |
| **读取期间文件变化（C7）** | 本次不写 hash、不写资源变更，沿用既有 changed/失败语义；扫描继续处理其它文件；不引入锁 / watcher / 重试 |
| 读取一致性不改变增量门 | 未变文件仍按 `(path_key, size, mtime)` 跳过，不读取、不计算哈希 |

### 14.4 Read-only

| 用例 | 期望 |
| :--- | :--- |
| 扫描/哈希不修改用户文件 | 样本目录 sha256 + size + mtime 前后一致 |
| 预览缓存写入范围 | 仅 `data/thumbnail_cache/`；不触碰资源与数据库 |
| Query Layer | 任何非 SELECT/WITH 语句抛 `ReadOnlyViolation` |

### 14.5 Database

| 用例 | 期望 |
| :--- | :--- |
| v2 → v3 migration（若将来执行） | 只应用 v3；两列被移除；数据零丢失 |
| fresh v3 database | v1 → v2 → v3 顺序正确；净结构不含被删列 |
| migration idempotency | 重复运行不报 duplicate column / no such column |
| constraints | `file_path_key` / `mods.guid` / `authors.name_key` 唯一性仍生效 |
| indexes | `idx_resources_sha256` 存在；被删列的索引不再存在 |
| Phase 2 期间 | `SCHEMA_VERSION == 2` 且 `MIGRATIONS == {1,2}` **不得变化** |

### 14.6 Q-V2｜验证基线是否足够

- **Question**：现有 671 passed + 两个 Node 脚本是否足以覆盖新增能力？
- **Current Evidence**：现有套件已覆盖 schema / 约束 / 事务 / FTS / Library / Scanner /
  Parser / Query / Browse / GUI / 只读边界；新增能力只有「哈希写入」与「派生重复查询」两项。
- **Decision**：**不够，但缺口很小且明确** —— 需补充 §14.2 的 9 个 identity 用例、
  §14.3 的 moved/deleted 用例、以及 §14.5 的「Phase 2 期间 schema 不得变化」断言。
- **Reason**：现有套件对「内容身份」与「字节重复」零覆盖（因为该能力此前不存在）；
  其余维度已有覆盖。
- **Impact**：Phase 2.1 / 2.2 的验收必须包含上表新增用例；真实样本用例继续以
  「样本目录 sha256 前后一致」作为只读证据。

---

## 15. Phase 2 Scope Freeze

### 15.1 IN SCOPE

1. **Content Identity（byte）**：在扫描重解析时写入 `resources.sha256`；
   定义并强制其 invariant（§13.3）；不改变增量门。
2. **Byte-Duplicate 能力（派生）**：只读查询「哪些资源字节完全相同」；
   不落库、不删除、不提供 canonical/dismiss。
3. **Query / CLI / GUI 的最小暴露**：让上述两项可被浏览（具体形式由实现阶段决定）。
4. **回归与验证**：§14 矩阵，含真实样本只读不变量。

### 15.2 OUT OF SCOPE

| 项 | 结论 | 理由 |
| :--- | :--- | :--- |
| schema v3 | **不做** | Phase 2 全部需求落在 v2 内（§11.1） |
| `quick_hash` / `content_key` | **DEPRECATED / UNUSED**：Phase 2 不写、不读、不删除 | 真正删除属未来独立的 schema cleanup 阶段，不在 Phase 2（§5.1.1、§11.2） |
| MOD Version 实体 / 多版本共存 | **不做** | INSUFFICIENT EVIDENCE（0 例同 GUID） |
| MOD→MOD dependency graph | **不做** | 无数据源（manifest 无依赖字段） |
| 版本约束 / 求解器 | **不做** | 依赖不存在 ⇒ 约束无意义 |
| classification layer | **不做** | 无调用方、无失败案例（§9） |
| Tags / Collections | **不做** | 与身份主线正交，无需求证据（§10） |
| perceptual / semantic duplicate | **不做** | NOT DETECTABLE WITH CURRENT EVIDENCE（§8.1） |
| 网络元数据 / 自动下载 / 自动更新 | **不做** | 违反「本地优先、零网络」硬约束 |
| 游戏安装 / VFS / load order | **不做** | 本项目不管理安装 |
| AI 分类 | **不做** | 违反「禁止云端 AI」约束 |
| 自动删除 / 批量文件操作 | **不做** | 违反「默认只读」；删除属 Phase 5 |
| 云同步 / 多用户 | **不做** | 本项目是单机单用户工具 |
| File 实体 / 1:N 拆分 | **不做** | 无样本证据（§4） |
| 通用 Entity/Relation 抽象 | **不做** | 明确禁止，除非证据证明必要（本设计证明不必要） |

---

## 16. Revised Phase 2 Roadmap

由于本设计**取消了** MOD Version / Dependency / Classification / Tags / schema v3，
Phase 2 的规模显著小于原设想，原建议顺序不再成立。按最终设计重排：

```text
Phase 2.0-C   Architecture & Schema Design      ← 本阶段（不写功能代码）
      ↓
Phase 2.1     Content Identity Foundation
              （扫描重解析时写 sha256；含 C7 读取一致性规则；
                invariant + §14.2/14.3 测试）
      ↓
Phase 2.2     Byte-Duplicate Capability
              （只读派生查询；不落库）
      ↓
Phase 2.3     Query / CLI / GUI Surfacing
              （把 sha256 与重复组暴露给用户；最小改动）
      ↓
Phase 2.4     Phase 2 Final Audit
              （回归 + 只读不变量 + 范围核对 + 收尾报告）
```

与原建议顺序的差异及原因：

| 原建议 | 本设计 | 原因 |
| :--- | :--- | :--- |
| Identity Foundation 在前 | 并入 2.1 | 本设计的「身份基础」= 内容身份；File/MOD/Author 身份已在 Phase 1 定型 |
| Content Identity 独立一步 | 成为 2.1 | 它是唯一需要 core 改动的能力 |
| MOD Identity / Version | **删除** | 方案 A 已由现有 schema 满足，无实现工作 |
| Duplicate Foundation | 保留为 2.2，但**缩小为字节重复** | logical duplicate 不可判定 |
| Relationship / Dependency | **删除** | 无数据源 |
| Classification | **删除** | 保持 parser-driven |
| Query / GUI Integration | 保留为 2.3 | 需要把新能力暴露给用户 |
| Phase 2 Final Audit | 保留为 2.4 | 与 Phase 1 的验收纪律一致 |

---

## 17. Open Questions

### 17.1 Q-V3｜Git 基线是否需要加固

- **Question**：Phase 2 是否需要先打 label / 加远端？
- **Current Evidence**：`main` @ `5987a0f` 是**唯一提交**；无 remote、无 tag；
  Phase 2.0-B 报告仍是未跟踪文件；reflog 只有 1 条记录。
- **Decision**：**Phase 2.0-C 不做任何 Git 操作**（禁止项）。
  但**建议在进入 Phase 2.1 之前**，由用户执行：① 提交 `docs/phase2/` 两个报告；
  ② 为 Phase 1 基线打 tag（例如 `phase-1-closed`）。
- **Reason**：Phase 2 会首次写入 `sha256` 等数据；一旦需要回退，
  「一个提交点 + 无 tag」的回退粒度太粗。
- **Impact**：属流程建议，不改变任何代码与 schema；不执行则回退仍依赖 `5987a0f`。

### 17.2 逐项答案索引（Q-F1 … Q-V3）

| 编号 | 主题 | 答案位置 | 结论摘要 |
| :--- | :--- | :--- | :--- |
| Q-F1 | 多库路径重复语义 | §4.2 | 保持现状；**INSUFFICIENT EVIDENCE**；给出重开触发条件 |
| Q-F2 | 1:N / N:1 文件模型 | §4.3 | 保持 1:1（样本反向证据 + 同域一致） |
| Q-H1 | 三个哈希字段 | §5.1、§5.1.1 | `sha256` KEEP（唯一内容身份）；`quick_hash` / `content_key` = **deprecated / unused**（Phase 2 不写不读不删） |
| Q-H2 | 哈希计算时机 | §5.2 | 与解析同频；无阈值、无后台 |
| Q-H3 | 哈希失效 | §5.3 | 仅由 size / mtime 变化或 full 触发；同尺寸同 mtime 替换是已知盲区 |
| Q-H4 | 三种「相同」的区分 | §5.4 | 仅 byte-identical 可判；same character = NOT DETECTABLE |
| Q-H5 | 哈希存储位置 | §5.5 | 留在 `resources`；不建 content 实体 |
| Q-H6 | SHA-256 读取一致性 | §5.6、§13.3 C7、§14.2/14.3 | 读前/读后校验 size+mtime；变化则丢弃本次 hash；沿用既有 changed 语义（无锁 / 无 watcher / 无重试） |
| Q-M1 | GUID 语义 | §6.1 | GUID = logical MOD 身份 |
| Q-M2 | 多版本共存 | §6.2 | 方案 A（不共存）；**INSUFFICIENT EVIDENCE** |
| Q-M3 | 版本历史 / 覆盖 | §6.3 | 不做历史/审计；覆盖是产品语义 |
| Q-D1 | MOD→MOD 依赖图 | §7.1 | **NO**（无数据源） |
| Q-D2 | `relation` 的 `uses/embeds` | §7.2 | KEEP（保留，不启用） |
| Q-D3 | `resource_mod_usages` 语义 | §7.3 | 保持不变；不引入通用关系表 |
| Q-U1 | 重复包含哪几类 | §8.2 | 仅 byte duplicate；same GUID 不作为重复功能；logical 排除 |
| Q-U2 | `group_type` 是否足够 | §8.3 | 保持两值；不新增 `logical` |
| Q-U3 | 派生 vs 持久 | §8.4 | **Derived query**；两张表继续预留 |
| Q-C1 | 分类层 | §9.1 | A. 保持 parser-driven |
| Q-C2 | Tags / Collections | §10.1 | **不进入 Phase 2** |
| Q-V1 | schema v3 与迁移 | §11、§12 | **Phase 2 不需要 v3**；给出未来 v3 的迁移与回滚设计 |
| Q-V2 | 验证基线 | §14.6 | 需补 identity / moved-deleted / schema-冻结断言 |
| Q-V3 | Git 基线加固 | §17.1 | 本阶段不动 Git；建议进 2.1 前提交 + 打 tag |

### 17.3 其余开放问题（带触发条件，不在 Phase 2 处理）

| # | 开放问题 | 触发条件 |
| :-- | :--- | :--- |
| OQ-1 | 多库路径交集应如何表达（改挂 vs 两条记录 vs per-library 实例） | 出现两库重叠的真实样本 |
| OQ-2 | 大库下的哈希策略（后台 / 阈值 / 惰性） | 实测扫描耗时不可接受（需基准数据） |
| OQ-3 | 同 GUID 两个 zipmod 文件时，`mods` 只指向一个的现状是否需要产品化处理 | 真实出现该情形 |
| OQ-4 | 「同角色重导出 / 跨格式」是否需要用户可见的相似提示 | 出现真实用户需求或可靠数据源 |
| OQ-5 | byte-duplicate 是否需要用户确认（dismiss / canonical）⇒ 提升为持久组 | 出现用户要标记「不是重复 / 保留这份」的需求 |
| OQ-6 | `quick_hash` / `content_key`（deprecated / unused）何时真正删除 | 未来独立 schema cleanup 阶段立项时（候选设计见 §11.3） |
| OQ-7 | `core/classification/` 空壳的最终处置（实现 / 删除 / 保留为文档） | Phase 1 债务清理排期；必须先确认无真实分类失败案例 |
| OQ-8 | 插件是否需要独立实体表（现为 `resource_plugins.plugin_guid` 字符串键） | 出现「插件需要自身元数据/版本」的需求 |
| OQ-9 | `resources.source` / `resources.series` 两个从未写入的列如何处置 | 同 OQ-6 的清理阶段 |
| OQ-10 | 同 size 同 mtime 但内容被替换的盲区是否需要更强失效判据 | 出现误判报告（现为 Phase 1 既有不变式） |

---

## 18. Final Decision

### 18.1 冻结的设计决定

| # | 决定 | 一句话 |
| :-- | :--- | :--- |
| 1 | **File ≡ Resource（1:1）** | 不建 File 实体；**不提前**为多 Library 重叠或 1:N 增加 File Entity（§4.5，仅在触发条件出现后重评） |
| 2 | **Path 是属性，不是实体** | `file_path_key` 继续作为 Resource 的业务身份（全局唯一） |
| 3 | **Content 是派生值，不是实体** | 内容身份 = `resources.sha256`（byte-identical） |
| 4 | **`sha256` KEEP（唯一内容身份）** | `quick_hash` / `content_key` = **deprecated / unused**；Phase 2 不写、不读、不删除 |
| 5 | **哈希与解析同频** | 复用 `(size, mtime)` 增量门，无阈值、无后台 |
| 6 | **GUID = logical MOD，方案 A** | 同 GUID 不共存、不保留历史、覆盖即语义；**不因 sha256/duplicate 重新打开**（§6.4） |
| 7 | **Version 是属性，不是实体** | 自由字符串，不比较、不排序、不作身份；不引入 Version / Instance / 历史表（§6.4） |
| 8 | **SHA-256 读取一致性（C7）** | 读前/读后校验 size+mtime；变化则丢弃本次 hash（§5.6、§13.3） |
| 9 | **无 MOD→MOD 依赖图** | manifest 无依赖字段 ⇒ 无数据源 |
| 10 | **`resource_mods` / `resource_mod_usages` 语义不变** | 不引入通用关系表 |
| 11 | **重复 = 派生查询，仅 byte duplicate** | `duplicate_*` 两张表继续预留、不写入 |
| 12 | **Classification 保持 parser-driven** | 不建独立层 |
| 13 | **Tags / Collections 不进入 Phase 2** | 与身份主线正交 |
| 14 | **Phase 2 不需要 schema v3** | 所有需求落在 v2 内；`SCHEMA_VERSION` 保持 2 |
| 15 | **不引入任何 Generic Entity / Relation 抽象** | 证据不支持 |

### 18.2 结束条件核对

| 结束条件 | 状态 |
| :--- | :--- |
| 运行必要的只读验证 | ✅ `git status/log/rev-parse/branch/remote/tag`；`pytest -q` → **671 passed**（33.37 s）；真实样本只读解析 + 哈希 + zipmod 内容检查 |
| 确认没有功能代码被修改 | ✅ `git status` 仅显示 `docs/phase2/`（其中含本阶段新增文件与 2.0-B 既有文件）；无已跟踪文件被修改 |
| 唯一新增文件 | ✅ 本阶段只新增 `docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md` |
| 未创建 schema v3 / 未执行 migration | ✅ `SCHEMA_VERSION = 2` 未改动；无 migration 执行 |
| 未改动 Git 历史 | ✅ 未提交、未 reset/clean/checkout/rebase、未 push、未创建 remote |

### 18.3 收尾补遗（2026-10-07，仅文档）

在 Phase 2.0-C 判定 PASS 之后，按审阅意见对本文档做了 **4 项极小范围收尾**，
未触碰任何功能代码 / schema / migration / Git：

| # | 补遗内容 | 落点 |
| :-- | :--- | :--- |
| 1 | **SHA-256 读取一致性规则**（读前 `size_before/mtime_before` → 计算 → 读后 `size_after/mtime_after`；不一致则本次 hash 不写库；沿用既有 changed/失败语义，不加锁 / 不加 watcher / 不做重试系统） | §5.6、§13.3 **C7/C8**、§14.2 / §14.3 验证矩阵、§16 Phase 2.1 说明 |
| 2 | **`quick_hash` / `content_key` 术语统一为 deprecated / unused**；Phase 2 不写、不读、不删除；真正删除属未来独立 schema cleanup 阶段 | §5.1、新 §5.1.1、§8.3、§11.2、§11.3、§13.3 C5、§15.2、§17 索引、§17.3 OQ-6、§18.1 |
| 3 | **MOD Version 在 Phase 2 保持关闭**（GUID = logical MOD；`mods` = one row per GUID；version = current manifest metadata；同 GUID 多文件/多版本的现有覆盖语义不变；不引入 MOD Version / MOD Instance / 历史表） | 新增 §6.4、§18.1 第 6/7 条 |
| 4 | **File = Resource 设计保持不变**（不提前引入 File Entity；仅在 §4.2 / §4.3 定义的触发条件出现后才重新评估） | 新增 §4.5、§18.1 第 1 条 |

以上 4 项**均为设计文本补充**，不改变 §18.1 的既有冻结决定，也不扩大 Phase 2 范围。

### 18.4 结论

- 21 个问题（Q-F1 … Q-V3）**逐项回答**，格式统一为
  Question / Current Evidence / Decision / Reason / Impact；
- 证据不足的两项（多库路径语义、同 GUID 多版本共存）**明确标注 INSUFFICIENT EVIDENCE**，
  并给出「触发条件」而不是猜测；
- 身份架构（Path / File / Content / Resource / MOD / MOD Version / Author / Library）
  **已正式定义**并给出最终关系图（§3.3）；
- 设计纪律全部遵守：**没有**为了完整而增加实体，**没有**建立无数据源的关系，
  **没有**引入通用 Entity/Relation，**没有**提前实现复杂模型；
- 本阶段**没有**写出任何功能代码，也**没有**创建 schema v3。

```text
PHASE 2.0-C = PASS
```

（本阶段到此结束：不进入 Phase 2.1，不修改任何功能代码、schema、migration 或 Git 历史。）
