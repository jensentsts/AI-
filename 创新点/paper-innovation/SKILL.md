---
name: paper-innovation
description: >-
  以可追溯证据、可证伪预测和作者决策构造、评估与收敛论文创新点。适用于工程、优化、控制、电力能源、应用数学与应用 AI 研究；支持完整选题、单题核验、批量初筛、拒稿返修和本地 PDF 调研。
---

# Paper Innovation Constructor（paper-innovation）v2.0

围绕作者希望读者相信的**具体主张**，组织文献、构造候选、独立审查、前瞻验证与论文交接。候选生成与原始论文材料隔离：用户问题、观察、约束和独立推导以 `Q#` 记录；论文型 `L#` 仅由来源台账中全文已读、有稳定标识和精确定位的研究对象形成可调用接口。若无合格 `L#`，可从独立 `Q#` 构思并标 `calls=NONE`。原始题名、摘要、全文和作者 Future Work 仅留在独立证据/审查登记，绝不进入构思简报。候选结论须由实际来源或实验支持；脚本只检查结构与记录，不证明新颖性、数学正确性或经验真实性。详见[上下文隔离协议](references/05-context-isolation.md)。

> 工程张力 → 已有方法的具体边界 → 可检验的候选机制 → 对强朴素基线的区分性预测 → 与证据相称的贡献表述

## 先选入口与主张

保留用户已给出的想法、数据边界、研究偏好和授权。根据任务直接选合适入口；已给过的授权不重复索取。按用户请求开展相应研究，并遵守明确的浏览、数据、预算与服务限制；受环境限制无法获取的内容标为待检验。决策点 1 的路线选择与决策点 2 的验证处置必须由作者明确决定。

| `--mode` | 适用情况 | 起步方式 |
| --- | --- | --- |
| `full`（默认） | 从问题和文献开始构造路线 | 阶段 1–5 |
| `single` | 已有一个想法，需要核验、红队和验证 | 单候选也可；直接保存其来源和边界 |
| `batch` | 比较多条选题或构思 | 先只建 `00_screening.md`，初筛后逐条开单题工作区 |
| `revision` | 根据拒稿意见或既有结果修订路线 | 保留原决定、评语和新旧主张的对应关系 |
| `local-pdf` | 用户已有本地 PDF 集 | 先清点本地语料；检索来源与未覆盖范围照实记录 |

入口与研究主张分开选择：`--claim method`（方法）、`theory`（理论）、`phenomenon`（现象）。若贡献本身是集合包含、严格更强的不等式、等价关系或定理，即使它嵌在工程算法里也选 `theory`；若主张在实际决策/观测结果或求解器性能上产生改善，选 `method`。现象主张解释观测机制时选 `phenomenon`。批量初始化的 `--claim` 只是默认值，每一行必须按其实际贡献单独标记，建立单题工作区时再传对应类型。六个构造算子只用于**方法路线**；理论主张检验假设、推论、参数域和见证，现象主张检验竞争机制、可区分预测与可取得数据。

## 工作区与 CLI

脚本可从任何课题工作目录调用；`$ctl` 指向已安装 Skill 的绝对路径，`$dir` 是课题自己的输出目录。不要把项目产物写进 Skill 安装目录。

```powershell
$ctl = (Resolve-Path 'E:\__ai__\焚诀\创新点\paper-innovation\scripts\ideation_ctl.py').Path
$dir = 'E:\workspace\project-a\ideation'

python "$ctl" init --dir "$dir" --topic '高比例新能源下的在线协调控制' --journal 'IEEE TPWRS' --claim method
python "$ctl" status --dir "$dir"
python "$ctl" check --dir "$dir" --gate 1
```

此例的 `$ctl` 是仓库内安装路径；复制安装后将它改为实际安装位置的绝对路径。`init` 默认 `--mode full`，也可显式传 `--mode full|single|batch|revision|local-pdf`。同一目录若主题或模式与已有工作区不符，默认拒绝重用；先选正确项目目录，不要靠覆盖抹去历史。v1.1 工作区升级时先复制留档并在新目录初始化 v2.0；逐条为旧主张补上“原文报告 / 已复现 / 待检验”状态、定位与来源类型。升级前已做的测量保留为回顾性/探索性结果，不倒填预注册锁定或前瞻阈值。旧数据只能作为来源链接；要开展新一轮验证，另立候选版本、重新审查并锁定。

批量模式先填写初筛表。每行记录候选编号、主张类型、最接近工作及重叠点、可用数据/基准、最低成本检验、`KEEP / DROP / DEFER` 与理由。至少做出一项实际决定后可检查；零条 `KEEP` 也是有效结论。为每个保留项在独立目录建立单题工作区：

```powershell
$batch = 'E:\workspace\project-a\batch-screen'
python "$ctl" init --dir "$batch" --topic '候选方向初筛' --journal 'IEEE TPWRS' --mode batch --claim method
# 先在 00_screening.md 留下并审核 Q/L 允许字段
python "$ctl" prepare-ideas --dir "$batch"
# 新上下文只用打印的不可变快照与空白 idea_draft.md 生成草稿
# 协调者将草稿移入 00，之后补最接近工作等审查信息，再初筛
python "$ctl" check --dir "$batch" --screen
python "$ctl" init --dir 'E:\workspace\project-a\ideation-P2' --topic '候选方向 P2' --journal 'IEEE TPWRS' --mode single --claim method
```

在非 batch 工作区中，`start` 为 `02_candidate_proposals.md` 中已有的候选准备隔离产物；创建这些文件本身不要求先 `PASS`。例如：

```powershell
python "$ctl" start --dir "$dir" --proposal P2
```

多候选或返修版本必须显式传 `--proposal`。共享的 `01–03` 留在工作区根目录，候选专属 `04–06` 放在 `runs/P2/`。不带 `--proposal` 是兼容旧工作区根目录 `04–06` 的路径；不要用它承载并行候选或修订版。测量阶段仍须先有红队 `PASS` 及作者在决策点 1 的实际选择。

每项测量开始前，把已填写且稳定的判定规则锁定。锁定后修改必须形成新版本（例如 `P1-v2`），重新红队审查、获得对应的人类选择并重新锁定；没有预注册锁定证明的既有结果标作探索性结果。

```powershell
python "$ctl" lock-prereg --dir "$dir" --proposal P2
python "$ctl" check --dir "$dir" --proposal P2 --gate 3
python "$ctl" check --dir "$dir" --proposal P2 --gate 4
```

常用检查：`status --dir ...`、`check --gate 1|2|3|4`、`check --screen`。门控逐级累积，门控通过仅表示材料满足脚本定义的结构要求。

## 阶段与人类决策

按需读取对应参考文档，保存研究产物及来源定位。主张、预测、判断与每条证据分别标为：**原文报告**（唯一标识与页码/公式/图表）、**已复现**（数据、条件、脚本/原始记录路径）或**待检验**（明示推断及可能推翻它的观察）。证据路径可相对 `ideation` 根目录或为绝对路径。

1. **文献解剖** — [参考 01](references/01-literature-dissection.md)。冻结用户种子；用近期代表作作为检索起点，再沿引文追溯最接近工作及原始结果，不设年份截断。整理假设、权衡、失效与来源，不把摘要当全文证据。审核允许字段后运行 `prepare-ideas --dir <课题目录>`，导出构思简报。
2. **构造候选** — [参考 02](references/02-construction-operators.md)与[上下文隔离协议](references/05-context-isolation.md)。新生成只在不继承历史的上下文中提供 CLI 打印的不可变快照与空白 `idea_draft.md`；随后由协调者将草稿移入 `02` 或 `00`，再补 C 编号、M1 与来源 DOI 等审查字段，保留原始问题和作者增量。每个 `P` 记录 `origin_ids`（`Q#`）、`calls`（`L#` 或 `NONE`，附具体输入→输出用法）、`novel_delta` 与 `generation`，fresh 候选另记 `brief_sha256`。按 `claim` 选择检验，只有方法路线使用 `O1–O6`。对单题认真审查即可，不为凑数强造多个方案；批量题先低成本初筛。
3. **红队审查** — 在独立上下文先准确复述候选能成立的最强主张，再审查同构先例、实际意义、替代假设、物理边界和强朴素基线。逐题登记 `PASS`、`REVISE`、`KILL` 或 `DEFER`。全部候选均有依据地淘汰或暂缓时，可在此结束。[参考 03](references/03-redteam-reviewer2.md)
4. **前瞻验证** — [参考 04](references/04-mvp-and-convergence.md)。在测量前锁定预注册；根据主张类型设计最低成本且能推翻主张的测试。Gate 3 需要作者在决策点 1 实际选中 `PASS` 路线；`REVISE`/`STOP` 可整理完整材料供作者决策，但不能进入论文交接。
5. **贡献与交接** — 继续读[参考 04](references/04-mvp-and-convergence.md)。Gate 4 仅用于作者已批准且结果为 `ADVANCE` 的路线；核对证据、作者对内部风险的处置、最终贡献与稿件映射。

**决策点 1**（红队后、任何测量前）：呈交所有候选裁决、关键证据、风险和低成本下一步，等待作者明确选择与开工授权。若全数被可靠 `KILL`，提交止损结论即可。**决策点 2**（预注册验证后）：呈交原始结果、误差/不确定性、预注册判定和内部缺陷备忘录，等待作者选择锁定、返修或停止。不得自动替作者选题，也不得把阶段 2/3 的 `PASS` 当作写论文的许可。

## 迁移边界

- 六算子 `O1–O6` 是**方法构造工具**，不是理论或现象研究的必要清单。
- 近期文献是当前研究面的起点；检查同构、命题先例及根源时须继续沿引用回溯，不以“近五年”当作证据边界。
- 参考文献数量依目标期刊和项目要求设定。焚诀当前写作规范中的“总量不少于 25 篇、目标期刊论文至少 10 篇”是项目目标，不是 Skill 的普遍门槛。
- 方法比较报告主指标、方向、实际意义阈值、测量不确定性与各基线的实现/来源；不使用固定“85%–90%”作为通用淘汰线。声称可扩展时再做两个规模点的探针并报告运行时间、内存和条件。
- 内部风险备忘录只供作者审阅。作者确认的适用边界，才可写入稿件设定并作为研究对象的正向定义；未确认的风险不能静默变成稿件事实。

## 文件索引

| 文件 | 内容 |
| --- | --- |
| [参考 01](references/01-literature-dissection.md) | 溯源、证据状态、跨文献查重与本地检索工具 |
| [参考 02](references/02-construction-operators.md) | 约束阶梯、六个方法构造算子、主张类型分流 |
| [参考 03](references/03-redteam-reviewer2.md) | 隔离审查、Steelman、基线、显著性与假设审计 |
| [参考 04](references/04-mvp-and-convergence.md) | 预注册、不同主张的检验、人类闸门与论文交接 |
| [参考 05](references/05-context-isolation.md) | 仅导出审查后的问题/来源接口、隔离生成、残差与新颖性判定 |
| [`templates/`](templates/) | 初始化工作区使用的材料模板 |
| [`templates/idea_draft.md`](templates/idea_draft.md) | 候选生成用的空白、主张中性草稿模板；只与不可变简报快照一起进入新上下文 |
| [`scripts/ideation_ctl.py`](scripts/ideation_ctl.py) | `init`、`prepare-ideas`、`start`、`status`、`check`、`lock-prereg` 的本地命令入口 |
