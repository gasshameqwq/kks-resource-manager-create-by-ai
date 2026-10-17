# KKS Resource Manager

> **Koikatsu Sunshine 本地资源管理器** — 本地优先、默认只读、可人工修正。
>
> 当前状态：**Phase 3.4（User Classification & Search）实施完成，待用户验收**
> （契约 FROZEN 2026-10-17；实施报告见
> [docs/phase3/PHASE3_4_CLOSURE_REPORT.md](./docs/phase3/PHASE3_4_CLOSURE_REPORT.md)）
> · 已封存：Phase 1 / Phase 2（`phase-2.4-closed`）/ Phase 3.0 · 3.0.2 · 3.1 · 3.2 · 3.3
> · 下一步：Phase 3.4 用户验收；3.5 及以后仍为**待规划方向（未冻结）**
> · schema `v2` · Python 3.11+ · 测试基线 `943 passed`（Phase 3.4 实施轮实测，来源
> [docs/phase3/PHASE3_4_LOG.md](./docs/phase3/PHASE3_4_LOG.md) §5.2）
>
> 各阶段状态与权威文档入口以 [docs/PROJECT_STATE.md](./docs/PROJECT_STATE.md) 为准。

这不是「角色卡分类器」，而是一个**本地、可搜索、可分类、可关联的 KKS 资源数据库**，
角色卡只是其中一种资源。设计目标是从任意一端都能查询：

```
角色 → 用了什么 MOD？      MOD → 被谁使用？
作者 → 发布了什么？        Collection → 包含什么？
标签 → 对应什么？
```

---

## 三条硬性约束

| 约束 | 含义 |
| :--- | :--- |
| **本地优先** | 全部数据本地处理，运行时零网络请求、零云 AI / API 依赖 |
| **默认只读** | 扫描与解析绝不移动 / 删除 / 修改用户原始文件；文件操作必须由用户明确触发 |
| **可人工修正** | 自动识别只写「可可靠确认」的结论，其余落 `unknown` + `needs_review`，交给用户确认 |
| **位置与分类分离** | 打标签 / 加入 Collection **不移动文件、不改文件名** |

---

## 快速开始

GUI 与命令行入口并存：`python main.py gui` 启动 PyQt6 界面（Phase 1.4 起的只读 GUI），
其余为命令行子命令。数据库自检只用标准库 `sqlite3`，不需要第三方依赖。

```bash
# 启动图形界面（PyQt6；界面只调用 core/，不含业务逻辑）
python main.py gui

# 初始化或升级数据库，打印结构摘要
python main.py --init-db

# 打印路径、数据库状态、FTS 状态与已添加的 Library（数据库不存在时自动初始化）
python main.py --info

# 版本号
python main.py --version
```

### 管理扫描根目录（Phase 1.1）

```bash
# 添加一个或多个根目录（目录只会被读取，不会被修改）
python main.py library add "D:/KKS/Cards"
python main.py library add "D:/KKS/Cards" "E:/Downloads/KKS" --notes 备用

# 列出已添加的 Library（含资源统计与上次扫描时间）
python main.py library list

# 暂停 / 启用
python main.py library disable 2
python main.py library enable 2

# 删除：默认只预览影响，加 --yes 才真正执行（不会删除任何文件）
python main.py library remove 2
python main.py library remove 2 --yes
```

临时离线的盘符可以加 `--allow-missing` 跳过目录存在性检查。

### 扫描并入库（Phase 1.2-C）

```bash
# 扫描全部启用的 Library（增量：size + mtime 未变就跳过，不重解析）
python main.py scan

# 只扫某一个库（可用 id 或根目录路径）
python main.py scan 1
python main.py scan "D:/KKS/Cards"

# 忽略增量捷径，全部重新解析
python main.py scan 1 --full
```

扫描**只读**：不移动 / 重命名 / 删除任何文件，也不写缓存；文件消失只标记
`scan_status='missing'`，不删数据库行。

### 人工修正资源字段（Phase 3.1）

```bash
# 展示名覆盖 / 清除（只写数据库，不改文件名）
python main.py resource set-display-name 12 "白峰一乃"
python main.py resource set-display-name 12 --clear

# 用户备注
python main.py resource set-notes 12 "来自 2024 年合集"
python main.py resource set-notes 12 --clear

# 用户类型修正（type_source 切换为 user，重扫不覆盖）
python main.py resource set-type 12 character_card
```

以上命令经 `core.app.ResourceWriteService` 写入，遵循「用户数据 / 机器事实分离」：
Scanner 重扫不会覆盖用户值。Tag / Favorite 的**写 API 已在 Phase 3.2 落地**
（`core.app.TagWriteService`），但用户入口属后续阶段。

Phase 1.4 起 `main.py` 会挂接 PyQt6 主窗口，核心逻辑始终留在 `core/`。

```bash
# 依赖（Phase 1.2 起才真正用到 msgpack / Pillow / PyQt6）
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 验收与测试

```bash
# 首选：pytest 验收套件（表结构 / 约束 / 事务 / FTS 回填 / Library / CLI）
.venv\Scripts\python.exe -m pytest -q

# 无 Python 环境时的备用通道：用 Node 直接抽取 DDL 并在内存库中实测
node tools/validate_schema.mjs
node tools/check_model_sync.mjs
```

两条通道的验收结果记录在 [docs/PHASE0_REPORT.md](./docs/PHASE0_REPORT.md)。

---

## 项目结构

```
kks-resource-manager/
├── core/                 # 核心逻辑（不 import PyQt6，可无 UI 测试）
│   ├── app_paths.py      # 数据目录 / 数据库 / 缩略图 / 日志路径
│   ├── models/           # 领域模型（dataclass）
│   ├── database/         # schema.py（版本化 DDL）+ db.py（连接 / 事务 / 初始化 / 归一化）
│   ├── library/          # Library 管理：libraries 表 CRUD（Phase 1.1）
│   ├── scanner/          # 目录遍历 + 增量扫描        （Phase 1）
│   ├── parsers/          # KKS/KK 卡片解析            （Phase 1）
│   ├── mod/              # 空壳模块（MOD manifest 实际在 parsers/zipmod.py）
│   ├── thumbnails/       # 缩略图缓存（只写 data/thumbnail_cache/）
│   ├── duplicate/        # 空壳模块（byte-duplicate 为 Query 层只读派生）
│   └── classification/   # 识别优先级 Level 1–4
├── ui/                   # 界面层：只调用 core/，不含业务逻辑
├── tests/                # pytest：核心逻辑必须可无 UI 测试
├── tools/                # 开发辅助脚本（validate_schema.mjs / check_model_sync.mjs 等）
├── docs/                 # 架构文档 / Phase 报告 / 第三方许可
├── data/                 # 运行时数据（.gitignore 忽略）
└── main.py               # 入口（自检 + library 子命令）
```

**依赖方向严格单向**：`ui/ → core/`，`core/` 永不反向依赖 UI。

---

## 技术选型

| 层 | 选型 | 理由 |
| :--- | :--- | :--- |
| 语言 | Python 3.11+ | 与参考项目 KKTools 一致，最大化复用其卡片解析内核 |
| UI | PyQt6 | Windows 桌面表现成熟（Phase 1 起） |
| 数据库 | SQLite（标准库 `sqlite3`） | 零部署、单文件、可承载数万行 |
| 二进制解析 | `msgpack` | KKS/KK 卡片尾部数据块是 MessagePack |
| 图片 | Pillow | 缩略图生成与 PNG 校验 |
| 全文检索 | FTS5 `trigram` + LIKE 回退 | 支持中日文子串；FTS 不可用时自动退化 |

---

## 路线图

| Phase | 内容 | 状态 |
| :--- | :--- | :--- |
| **0** | 架构与项目初始化（文档 + 骨架 + schema） | ✅ 已完成 |
| 1 | 扫描 + KKS/KK 卡片识别 + SQLite + 只读 GUI 浏览器 | ✅ 已完成并收尾（PHASE 1 = CLOSED） |
| 2 | MOD / 卡片解析 + Content Identity（sha256）+ Byte-duplicate（只读派生）+ 查询暴露 | ✅ 已完成并收尾（tag `phase-2.4-closed`） |
| 3 | 用户数据 / 机器事实分离 + Tag 体系（Phase 3 首期） | 🚧 3.0 · 3.0.2 · 3.1 · 3.2 已完成（tag `phase-3.2-closed`）；**3.3 已完成（CLOSED / CONDITIONAL PASS，tag `phase-3.3-closed`）**；**3.4 实施完成，待用户验收（契约 FROZEN）**；3.5 及以后**待规划（未冻结）** |
| 4 | 重复检测 + 资源关系 | ⏳ 早期路线图占位：byte-duplicate 已在 Phase 2 完成；其余未重新论证 |
| 5 | 批量文件操作（Preview / Confirm / Undo） | ⏳ 早期路线图占位，未论证 |
| 6 | 性能优化 + 测试 + Windows 打包 | ⏳ 早期路线图占位，未论证 |

每完成一个 Phase 必须：跑测试 → 修错误 → 确认旧功能未被破坏 → 更新 README → 才进入下一阶段。
Phase 3 的**路线图（整体）仍未冻结**：Phase 3.3 与 Phase 3.4 均有已冻结的 Contract
（3.3 已按其 §10.1 完成实施并经用户接受验收，结论为 **CONDITIONAL PASS**；3.4 已实施完成，
待用户验收）——**冻结 ≠ 实施授权，也 ≠ 阶段完成**，更不代表整个 Phase 3 路线图已冻结。
来源与权威级别见 [docs/PROJECT_STATE.md](./docs/PROJECT_STATE.md) §4；Phase 3.3 的冻结记录见
[docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md](./docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md) §19；
Phase 3.4 的冻结记录见
[docs/phase3/PHASE3_4_IMPLEMENTATION_CONTRACT.md](./docs/phase3/PHASE3_4_IMPLEMENTATION_CONTRACT.md) §12，
实施报告见 [docs/phase3/PHASE3_4_CLOSURE_REPORT.md](./docs/phase3/PHASE3_4_CLOSURE_REPORT.md)。

---

## 文档

| 文档 | 内容 |
| :--- | :--- |
| [docs/WORKFLOW.md](./docs/WORKFLOW.md) | 长期协作规范（角色职责 / 标准流程与任务指令 / 暂停条件 / 文档职责摘要与分层 / 审核结论与阶段状态 / Git 授权与收尾） |
| [docs/PROJECT_STATE.md](./docs/PROJECT_STATE.md) | **当前状态、文档职责登记与权威文档入口**（基线 / 已完成阶段 / 未冻结路线图 / 未决证据） |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | 分层、数据模型、关键设计决策、迁移约定 |
| [docs/PHASE0_REPORT.md](./docs/PHASE0_REPORT.md) | Phase 0 验收报告（实测输出、已知缺口、Phase 1 进入条件） |
| [docs/phase1/PHASE1_REPORT.md](./docs/phase1/PHASE1_REPORT.md) | Phase 1 报告（1.1 已完成 + 两个 P1 修复 + 后续步骤） |
| [docs/phase1/SAMPLE_ANALYSIS.md](./docs/phase1/SAMPLE_ANALYSIS.md) | 真实样本只读分析（Phase 1.2 前置：容器格式、Ground Truth、Scanner 需求） |
| [docs/phase1/PHASE1_2_REPORT.md](./docs/phase1/PHASE1_2_REPORT.md) | Phase 1.2 报告（1.2-A Schema v2 已完成；1.2-B Parser 待开始） |
| [docs/phase1/PHASE1_3_REPORT.md](./docs/phase1/PHASE1_3_REPORT.md) | Phase 1.3 报告（数据模型审计 + 只读 Query Layer；schema v2 未改） |
| [docs/phase1/PHASE1_3C_AUDIT.md](./docs/phase1/PHASE1_3C_AUDIT.md) | Phase 1.3-C 设计审计（Preview / Thumbnail 与 Review / 待确认；本轮不实现） |
| [docs/phase1/PHASE1_3C1_REPORT.md](./docs/phase1/PHASE1_3C1_REPORT.md) | Phase 1.3-C-1 报告（PreviewService：缩略图缓存，只写缓存不碰源文件） |
| [docs/phase1/PHASE1_3C2_REPORT.md](./docs/phase1/PHASE1_3C2_REPORT.md) | Phase 1.3-C-2 报告（Review Reason：只读派生「为什么需要人工查看」） |
| [docs/phase1/PHASE1_4A_REPORT.md](./docs/phase1/PHASE1_4A_REPORT.md) | Phase 1.4-A 报告（只读 Search Core：FTS5 trigram + LIKE 回退） |
| [docs/phase1/PHASE1_4A1_REPORT.md](./docs/phase1/PHASE1_4A1_REPORT.md) | Phase 1.4-A.1 报告（把 relative_path 纳入检索面） |
| [docs/phase1/PHASE1_4B1_REPORT.md](./docs/phase1/PHASE1_4B1_REPORT.md) | Phase 1.4-B.1 报告（Libraries 只读查询：列表 + 资源计数） |
| [docs/phase1/PHASE1_4B2_REPORT.md](./docs/phase1/PHASE1_4B2_REPORT.md) | Phase 1.4-B.2 报告（ResourceQuery.has_missing_mods 只读筛选） |
| [docs/phase1/PHASE1_4B3_REPORT.md](./docs/phase1/PHASE1_4B3_REPORT.md) | Phase 1.4-B.3 报告（Browse Read Model：编排 + 行模型，无自有 SQL） |
| [docs/phase1/PHASE1_4C1_REPORT.md](./docs/phase1/PHASE1_4C1_REPORT.md) | Phase 1.4-C-1 报告（PyQt6 GUI 骨架：三栏 + BrowseService 链路） |
| [docs/phase1/PHASE1_4C2_REPORT.md](./docs/phase1/PHASE1_4C2_REPORT.md) | Phase 1.4-C-2 报告（搜索 / 筛选 / 排序 / 有界加载更多） |
| [docs/phase1/PHASE1_4C3_REPORT.md](./docs/phase1/PHASE1_4C3_REPORT.md) | Phase 1.4-C-3 报告（QThreadPool 异步缩略图 + epoch 防串图） |
| [docs/phase1/PHASE1_4C4_REPORT.md](./docs/phase1/PHASE1_4C4_REPORT.md) | Phase 1.4-C-4 报告（只读资源详情面板：9 个区域 + Preview 复用） |
| [docs/phase1/PHASE1_4C4_DESIGN_REVIEW.md](./docs/phase1/PHASE1_4C4_DESIGN_REVIEW.md) | Phase 1.4-C-4 设计评审（DetailPanel 信息架构与 core 缺口评估） |
| [docs/phase1/PHASE1_4C5_REPORT.md](./docs/phase1/PHASE1_4C5_REPORT.md) | Phase 1.4-C-5 报告（MOD/作者/插件 → 资源 反向查询 + 闭环） |
| [docs/phase1/PHASE1_4C_CLOSURE_REPORT.md](./docs/phase1/PHASE1_4C_CLOSURE_REPORT.md) | Phase 1.4-C 收尾报告（能力清单 / 只读不变量 / P2 / non-goals） |
| [docs/phase1/PHASE1_5_DESIGN_REVIEW.md](./docs/phase1/PHASE1_5_DESIGN_REVIEW.md) | Phase 1.5 设计评审（GUI Setup & Scan：Library 管理 + 扫描，含 12 项问答） |
| [docs/phase1/PHASE1_5A_REPORT.md](./docs/phase1/PHASE1_5A_REPORT.md) | Phase 1.5-A 报告（GUI Library 管理：Add / Enable / Disable / Remove + 薄 application 层） |
| [docs/phase1/PHASE1_5B_REPORT.md](./docs/phase1/PHASE1_5B_REPORT.md) | Phase 1.5-B 报告（GUI 扫描：ScanWorker + 后台执行 + 完成后统一刷新 + Remove 竞态防护） |
| [docs/phase1/PHASE1_FINAL_REPORT.md](./docs/phase1/PHASE1_FINAL_REPORT.md) | Phase 1 最终 Closure 报告（审计清单 / 不变量 / P2-P3 / PHASE 1 = CLOSED） |
| [docs/phase2/PHASE2_FINAL_CLOSURE_REPORT.md](./docs/phase2/PHASE2_FINAL_CLOSURE_REPORT.md) | Phase 2 最终 Closure 报告（Content Identity / Byte-duplicate / 查询暴露；PHASE 2 = CLOSED） |
| [docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md](./docs/phase2/PHASE2_0_C_ARCHITECTURE_DESIGN.md) | Phase 2.0-C 架构设计（身份模型 / 不变式 C1–C8 / 修订路线图） |
| [docs/phase3/PHASE3_0_CONTRACT.md](./docs/phase3/PHASE3_0_CONTRACT.md) | Phase 3 首期 Architecture / Scope Contract（**FROZEN**，最高权威） |
| [docs/phase3/PHASE3_0_DECISION_REPORT.md](./docs/phase3/PHASE3_0_DECISION_REPORT.md) | Phase 3.0 决策报告（D1–D5；`display_name` 现行语义见 Contract §3.1） |
| [docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md](./docs/phase3/PHASE3_0_2_SEARCH_TAXONOMY_ARCHITECTURE_REVIEW.md) | Phase 3.0.2 搜索与分类设计评审（未冻结工作路线来源） |
| [docs/phase3/PHASE3_1_CLOSURE_REPORT.md](./docs/phase3/PHASE3_1_CLOSURE_REPORT.md) | Phase 3.1 Closure（User Write Foundation = CLOSED / PASS） |
| [docs/phase3/PHASE3_2_CLOSURE_REPORT.md](./docs/phase3/PHASE3_2_CLOSURE_REPORT.md) | Phase 3.2 Closure（Tag System = CLOSED / PASS） |
| [docs/phase3/PHASE3_2_LOG.md](./docs/phase3/PHASE3_2_LOG.md) | Phase 3.2 实施日志（含最终状态索引） |
| [docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md](./docs/phase3/PHASE3_3_IMPLEMENTATION_CONTRACT.md) | Phase 3.3 实施契约（**FROZEN**，2026-10-13；实施已完成并经用户接受验收 = CONDITIONAL PASS） |
| [docs/phase3/PHASE3_3_CLOSURE_REPORT.md](./docs/phase3/PHASE3_3_CLOSURE_REPORT.md) | Phase 3.3 Closure（Search & Query Foundation = **CLOSED / CONDITIONAL PASS**；含开放事项与证据来源说明） |
| [docs/phase3/PHASE3_3_LOG.md](./docs/phase3/PHASE3_3_LOG.md) | Phase 3.3 实施日志（测试记录、证据修订说明与开放事项登记） |
| [docs/phase3/PHASE3_0_OPEN_EVIDENCE.md](./docs/phase3/PHASE3_0_OPEN_EVIDENCE.md) | U1–U5 证据缺口登记（**未解决**，本轮不执行取证） |
| [docs/THIRD_PARTY.md](./docs/THIRD_PARTY.md) | 第三方来源与 License 合规 |

---

## 许可与声明

本项目为个人本地工具，与 Illusion / ILLUSION 及 *Koikatsu Sunshine* 官方无隶属关系。
第三方代码来源与许可见 [docs/THIRD_PARTY.md](./docs/THIRD_PARTY.md)。
