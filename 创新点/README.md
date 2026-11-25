# `paper-innovation` — 论文创新点构造与实证验证 Skill (v1.1)

面向工程、优化、控制、电力/能源系统与应用数学等方向的顶刊论文（IEEE TPWRS / TSTE / MPCE、Automatica、CSEE 等），用于替代传统的发散式头脑风暴（如 `scientific-brainstorming`），并在架构上吸收了开放 Agent Skills 规范与科学方法论校验工程实践（去除了生物医学/冗余打分/过度防御包袱）。

核心闭环：**双线文献解剖（带溯源与精读深度）→ 约束阶梯与 6 大工程构造算子（含五维不变量核查）→ 独立审稿人-2 红队（Steelman + 三道闸门 + 事前验尸）→ 预注册最小原型仿真（MVP + 虚假胜出排查 + 残差迭代）→ 三层贡献收敛移交**。

---

## 目录结构

```text
创新点/
├── README.md                                  # 本说明与安装指南
└── paper-innovation/                          # 标准 Agent Skill 可直接安装目录
    ├── SKILL.md                               # Skill 入口、对象/生命周期规范与渐进披露调度
    ├── references/
    │   ├── 01-literature-dissection.md        # 阶段 1：人类种子冻结、纵向病灶与溯源、横向借刀、防提示注入
    │   ├── 02-construction-operators.md       # 阶段 2：约束阶梯、O1–O6 算子、五维不变量核查、反同质化
    │   ├── 03-redteam-reviewer2.md            # 阶段 3：独立上下文审稿人-2、Steelman、M2 构造与事前验尸
    │   └── 04-mvp-and-convergence.md          # 阶段 4–5：预注册判定、不可判定核验、虚假胜出排查、贡献封装
    ├── templates/                             # 标准化 Markdown 产物模板（自动初始化至课题 ideation/）
    │   ├── 01_assumption_failure_matrix.md
    │   ├── 02_candidate_proposals.md
    │   ├── 03_redteam_verdict.md
    │   ├── 04_mvp_verification.md
    │   ├── 05_internal_flaw_memo.md           # 仅对内汇报缺陷，与正文写作物理隔离
    │   └── 06_final_contributions.md
    └── scripts/
        └── ideation_ctl.py                    # 零依赖 Python CLI：init / status / check --gate 1..4 (--strict / --json)
```

---

## 安装与启用方式

将 `paper-innovation/` 整个文件夹复制（或软链接）到你所用 Agent 的 skills 目录即可跨项目全局调用：

### 1. 全局安装（推荐，适用于 Antigravity / Codex / Claude Code 等 `.agents/skills` 标准）

```powershell
# 方式 A：直接复制
Copy-Item -Recurse -Force ".\创新点\paper-innovation" "$env:USERPROFILE\.agents\skills\paper-innovation"

# 方式 B：目录联接（修改仓库内源码后全局实时同步）
New-Item -ItemType Junction -Path "$env:USERPROFILE\.agents\skills\paper-innovation" -Target (Resolve-Path ".\创新点\paper-innovation")
```

### 2. 项目级安装（仅在某个具体课题仓库内生效）

```powershell
New-Item -ItemType Directory -Force ".agents\skills" | Out-Null
Copy-Item -Recurse -Force "<焚诀路径>\创新点\paper-innovation" ".agents\skills\paper-innovation"
```

---

## 使用示例

安装后，在任意研究项目中直接触发 `/paper-innovation` 或说明“用 `paper-innovation` 构思论文创新点”：

```text
请使用 paper-innovation skill 为当前课题构造创新点：
- 研究主题：高比例新能源接入下含构网型变流器的频率稳定在线协调控制
- 目标期刊：IEEE TPWRS / TSTE
- 已有条件：本地有 IEEE 39 节点仿真基准与 paper_search_tools
```

Agent 将自动调用 `scripts/ideation_ctl.py init` 初始化 `ideation/` 目录，按阶段执行调研、构造、独立红队证伪与预注册 MVP 实测，并在 **决策点 1（红队后）** 与 **决策点 2（MVP 后）** 暂停等待你的专业拍板。
