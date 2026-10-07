# KKS Resource Manager

> **Koikatsu Sunshine 本地资源管理器** — 本地优先、默认只读、可人工修正。
>
> 当前状态：**Phase 1.5-B 已完成（GUI 扫描：增量 / 全量 + 后台 worker + 完成后统一刷新）**
> · 下一阶段：Phase 1.5-C/D（进度 / 取消 / 文件监控，需真实证据驱动）或直接进入 Phase 2
> · schema `v2` · Python 3.11+

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

还没有 GUI：入口是命令行。数据库自检只用标准库 `sqlite3`，不需要第三方依赖。

```bash
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
│   ├── mod/              # zipmod manifest / GUID     （Phase 2）
│   ├── thumbnails/       # 缩略图缓存                 （Phase 1）
│   ├── duplicate/        # 重复检测                   （Phase 4）
│   └── classification/   # 识别优先级 Level 1–4       （Phase 1 起）
├── ui/                   # 界面层：只调用 core/，Phase 1 实现
├── tests/                # pytest：核心逻辑必须可无 UI 测试
├── tools/                # 开发辅助脚本（validate_schema.mjs）
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
| 1 | 扫描 + KKS/KK 卡片识别 + SQLite + 基础浏览器 | 🚧 1.1–1.3 ✅；**1.4 只读 GUI 全部完成并收尾 ✅**；**1.5-A GUI Library 管理 ✅**；**1.5-B GUI 扫描 ✅** |
| 2 | MOD 索引 + GUID + 依赖关系 | — |
| 3 | 分类 + 标签 + 作者 + Collection | — |
| 4 | 重复检测 + 资源关系 | — |
| 5 | 批量文件操作（Preview / Confirm / Undo） | — |
| 6 | 性能优化 + 测试 + Windows 打包 | — |

每完成一个 Phase 必须：跑测试 → 修错误 → 确认旧功能未被破坏 → 更新 README → 才进入下一阶段。

---

## 文档

| 文档 | 内容 |
| :--- | :--- |
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
| [docs/THIRD_PARTY.md](./docs/THIRD_PARTY.md) | 第三方来源与 License 合规 |

---

## 许可与声明

本项目为个人本地工具，与 Illusion / ILLUSION 及 *Koikatsu Sunshine* 官方无隶属关系。
第三方代码来源与许可见 [docs/THIRD_PARTY.md](./docs/THIRD_PARTY.md)。
