# `paper-innovation` v2.0：论文创新点构造与验证

本 Skill 以用户要检验的研究主张为起点，记录来源和证据状态，再安排候选构造、红队审查、前瞻验证与论文交接。它支持工程、优化、控制、电力/能源、应用数学与应用 AI 研究。六个构造算子只用于方法路线；理论和现象主张使用各自对应的检验。构思采用上下文隔离：从 `01`/批量 `00` 只导出经审核的问题来源和接口。论文型 `L#` 必须已有全文、稳定标识和精确定位；没有合格来源时可只凭独立 `Q#` 构思。原始题名、摘要、论文原文和 Future Work 不提供给新方案生成器；红队再独立检查原始来源。

## 目录

```text
创新点/
├── README.md
└── paper-innovation/
    ├── SKILL.md                         # v2.0 入口、路由、门控与人类决策
    ├── references/
    │   ├── 01-literature-dissection.md  # 来源、证据状态、检索与回溯
    │   ├── 02-construction-operators.md # 主张分流与 O1–O6 方法算子
    │   ├── 03-redteam-reviewer2.md      # 独立红队、Steelman、先例与基线审计
    │   ├── 04-mvp-and-convergence.md   # 预注册、验证、作者审批与交接
    │   └── 05-context-isolation.md     # 问题/来源防火墙、隔离生成与红队核新
    ├── templates/                       # 各阶段产物模板
    │   └── idea_draft.md                # 隔离生成用的空白草稿模板
    └── scripts/
        └── ideation_ctl.py              # 本地工作区 CLI
```

## 安装

可把整个 `paper-innovation` 目录复制到 Agent Skills 目录，或用目录联接保持与本仓库同步。以下示例的仓库路径是本项目当前路径；如仓库位置不同，替换为实际绝对路径。

```powershell
$skillSource = (Resolve-Path 'E:\__ai__\焚诀\创新点\paper-innovation').Path
$skillTarget = Join-Path $env:USERPROFILE '.agents\skills\paper-innovation'
New-Item -ItemType Directory -Force $skillTarget | Out-Null
Get-ChildItem -LiteralPath $skillSource | Copy-Item -Destination $skillTarget -Recurse -Force
```

如希望源码更新即时反映到安装目录：

```powershell
$skillSource = (Resolve-Path 'E:\__ai__\焚诀\创新点\paper-innovation').Path
$skillTarget = Join-Path $env:USERPROFILE '.agents\skills\paper-innovation'
New-Item -ItemType Directory -Force (Split-Path $skillTarget) | Out-Null
New-Item -ItemType Junction -Path $skillTarget -Target $skillSource
```

## 从任意课题目录调用

将 Skill 脚本绝对路径和课题目录分别保存。项目产物写到项目自己的 `ideation`，不要放在 Skill 目录。

```powershell
$ctl = (Resolve-Path 'E:\__ai__\焚诀\创新点\paper-innovation\scripts\ideation_ctl.py').Path
$dir = 'E:\workspace\project-a\ideation'

python "$ctl" init --dir "$dir" --topic '高比例新能源下的在线协调控制' --journal 'IEEE TPWRS' --mode full --claim method
python "$ctl" status --dir "$dir"
python "$ctl" check --dir "$dir" --gate 1
```

复制安装后，把 `$ctl` 改为对应安装目录中 `scripts\ideation_ctl.py` 的绝对路径。`init` 默认 `--mode full`；模式可选 `full`、`single`、`batch`、`revision`、`local-pdf`，主张可选 `method`、`theory`、`phenomenon`。批量的 `--claim` 只是默认类型，每行按自身主张选择。同一目录的主题或模式不符时，`init` 默认拒绝重用。升级 v1.1 工作区时先复制留档，在新目录初始化 v2.0；逐条为旧主张补上“原文报告 / 已复现 / 待检验”状态、定位与来源类型。旧测量保留为回顾性/探索性记录，不倒填预注册锁定或前瞻阈值；新一轮验证使用新版本、重新红队审查和锁定。

`01` 的来源字段审核完成后，再为新候选准备隔离简报：

```powershell
python "$ctl" prepare-ideas --dir "$dir"
```

### 批量初筛

`batch` 初始化只创建 `00_screening.md`。每行填写候选编号、主张类型、最接近工作及重叠点、数据/基准、最低成本检验、`KEEP / DROP / DEFER` 和理由。先审核问题来源与可调用文献对象，再运行 `prepare-ideas`；新建的非继承上下文只接收 CLI 报告的不可变快照与空白 `idea_draft.md`，不接收工作中的 `00`。协调者把返回草稿写入 `00`，再补最接近工作、C 编号和 M1 等审查字段。至少记录一项真实决定后运行 `--screen`；零条 `KEEP` 也可通过初筛。每个保留项另建独立的 `single` 工作区：

```powershell
$batch = 'E:\workspace\project-a\batch-screen'
python "$ctl" init --dir "$batch" --topic '候选方向初筛' --journal 'IEEE TPWRS' --mode batch --claim method
# 在 00_screening.md 填写并审核问题/来源允许字段
python "$ctl" prepare-ideas --dir "$batch"
# 新上下文仅使用不可变简报快照和空白 idea_draft.md 生成草稿
# 协调者回填草稿、补来源审查字段后再检查
python "$ctl" check --dir "$batch" --screen
python "$ctl" init --dir 'E:\workspace\project-a\ideation-P2' --topic '候选方向 P2' --journal 'IEEE TPWRS' --mode single --claim method
```

### 并行候选与返修版

在非 batch 工作区的 `02_candidate_proposals.md` 中已有候选后，用 `start` 建立提案专属的 `04–06` 文件；创建产物本身不要求候选先 `PASS`。始终对该候选运行 `lock-prereg` 和 `check` 时传入相同 `--proposal`。提案专属文件写在 `runs/<提案编号>/`，`01–03` 共用。任何测量都必须等到候选 `PASS` 且作者在决策点 1 实际选中。

```powershell
python "$ctl" start --dir "$dir" --proposal P2
python "$ctl" lock-prereg --dir "$dir" --proposal P2
python "$ctl" check --dir "$dir" --proposal P2 --gate 3
python "$ctl" check --dir "$dir" --proposal P2 --gate 4
```

不传 `--proposal` 会使用兼容旧工作区的根目录 `04–06`；不要用这个路径存放并行提案或修订版。预注册锁定后若更改规则，建新提案版本（如 `P1-v2`），另做红队审查、取得作者的版本选择并重新锁定；旧结果仍为探索性证据。

## 路由与人类决策

- `full` 从研究问题开始；`single` 核验单题；`batch` 先廉价比较多题；`revision` 根据拒稿意见或旧结果重建路线；`local-pdf` 从现有本地语料入手。
- Gate 1–4 逐级累积。Gate 2 可包含 `PASS`、`REVISE`、`KILL` 的有效组合；所有候选都被有证据的 `KILL` 时可正常停止，不做 MVP。
- 决策点 1 由作者选中实际 `PASS` 候选后，才可开始该路线的测量。决策点 2 由作者在预注册验证后决定锁定、返修或停止。门控不会替作者作决定。
- Gate 3 可整理完整的 `REVISE`/`STOP` 结果供作者审阅，但不能交接稿件。Gate 4 要求作者选择并批准 `ADVANCE`，确认内部风险处置和适用边界，并完成证据引用与贡献映射。

项目级参考文献目标按期刊与稿件类型执行；焚诀写作规范目标为总量不少于 25 篇、目标期刊论文至少 10 篇。这不是 Skill 的通用门控阈值。细则见 [Skill 入口](paper-innovation/SKILL.md)及[参考文档](paper-innovation/references/)。
