# {{TOPIC}} 候选题初筛

- **目标期刊**：{{JOURNAL}}
- **记录日期**：{{DATE}}
- <!-- field:batch_generation --> **本轮生成方式**：

审查作者已给出的题时填 `author-supplied`。有新构思时填 `fresh` 或 `mixed`，先登记独立问题与可调用的文献对象，运行 `prepare-ideas`。将输出的快照和空白候选表交给未读原文的新会话。

## 可以产生研究问题的独立来源

<!-- section:idea_origins -->
每条 Q 填一种来源类型，作者原始问题用 `user`，现场观测用 `observation`，实际约束用 `constraint`，独立推导用 `derivation`。留下原话或可回查的记录。把原文作者的展望放入下方的查证表。

| ID | Origin type | Independent problem | Own source anchor |
| --- | --- | --- | --- |

## 可调用的已知文献对象

<!-- section:literature_objects -->
每条 L 从 `method`、`theorem`、`data`、`constraint`、`baseline`、`observation` 选一种角色。写出输入、成立前提、已知操作、输出及边界。当前尚无调用时保留空表。

| ID | Role | Inputs | Preconditions | Known operation | Outputs | Applicability boundary |
| --- | --- | --- | --- | --- | --- | --- |

## 查证用的来源记录

<!-- section:literature_table -->
对用到的 L 记录原文定位。本表给查证者使用，构思简报只导出上一张表的接口。无 L 时此表留空。

| Work ID | Canonical locator | Local full-text path | Depth | Pinpoints |
| --- | --- | --- | --- | --- |

### 原作者已经提出的后续工作

原文若明确建议相同路线，在此留下出处，供查重时逐项比对。

| Work ID | Future Work | Page or section |
| --- | --- | --- |

## 初筛记录

<!-- section:screening -->
逐题选择主张类型。比较运行决策或计算性能时选 `method`，声称可行域严格收紧、命题等价或定理成立时选 `theory`，从观测区分机制时选 `phenomenon`。同一批可使用不同类型。初筛结论用 `KEEP`、`DROP` 或 `DEFER`。若尚缺关键证据，在依据栏写明何种新材料值得重开。

| 方案 | 研究主张 | 最接近工作及重叠点 | 可取得的数据或基准 | 最小判别试验 | 结论 | 依据 |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | {{FILL:主张类型}} | {{FILL:工作和出处或已有检索的边界}} | {{FILL:可得字段与缺项}} | {{FILL:区分两种结果的检验}} | {{FILL:初筛结论}} | {{FILL:支持此决定的事实}} |

## 候选来源与作者增量

对保留的候选以及本轮新构思的候选，另写一个三级标题，例如“方案 P1”。按 02 模板记录 `origin_ids`、`calls`、`novel_delta`、`generation`，新构思加 `brief_sha256`。仅审查作者给定且全部淘汰或暂缓的题，可以在初筛表直接结束。
