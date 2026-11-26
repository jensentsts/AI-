# 04 预注册最小验证报告与决策点 2

- **研究主题**：{{TOPIC}}
- **目标期刊**：{{JOURNAL}}
- **建档日期**：{{DATE}}
- <!-- field:proposal --> **对应方案**：{{PROPOSAL}}
- <!-- field:claim --> **主张类型**：{{CLAIM}}

## 一、预注册判定规则
<!-- section:prereg -->

在获取比较结果前锁定本节和第二节。写出可改变决策的条件，确定采用哪个指标和工况。

- <!-- field:advance --> **Advance**：{{FILL:晋级门槛，包括相对 M2 的实际意义、数值阈值与单位、可行性及消融要求}}
- <!-- field:revise --> **Revise**：{{FILL:可定位、值得修正的局部失利及修正边界}}
- <!-- field:stop --> **Stop**：{{FILL:何时停止投入，含最低效果或硬约束底线}}
- <!-- field:indeterminate --> **不可判定条件**：{{FILL:基线不合理、关键记录缺失或配置异常时如何暂停判断}}

## 二、最小算例与公平比较设计
<!-- section:design -->

- <!-- field:case --> **算例和工况**：{{FILL:数据集版本、规模、关键子集及保留的病灶条件}}
- <!-- field:data_origin --> **数据来源**：{{FILL:standard-benchmark、synthetic-proxy 或 observational-data，加来源与版本；后两类写明代理边界或运营记录覆盖范围}}
- <!-- field:m1_origin --> **M1 复现来源**：{{FILL:official-code、reimplemented-verified 或 simplified-proxy，加来源、版本及核验范围}}
- <!-- field:comparison --> **公平对比口径**：{{FILL:M0/M1/M2/M3 定义、相同信息和硬约束、种子、调参预算、运行配置及消融变量}}
- <!-- field:primary_metric --> **主指标（表头）**：{{FILL:完整照录实测表中主指标列标题，包括单位}}
- <!-- field:metric_direction --> **主指标优化方向**：{{FILL:min 或 max}}
- <!-- field:min_difference --> **相对 M2 的最小实际意义差值**：{{FILL:用主指标列的单位填写正数；比率指标的绝对差用百分点或同尺度的原数值}}
- <!-- field:script --> **复现脚本路径**：{{FILL:相对 ideation 根目录或绝对的本地文件路径}}
- <!-- field:command --> **运行命令**：{{FILL:从哪个工作目录运行哪条命令，包括必需参数}}

## 三、实测结果与对照
<!-- section:evidence -->

- <!-- field:raw --> **原始结果路径**：{{FILL:可复核下表的原始本地文件，路径相对 ideation 根目录或使用绝对路径}}

每个已测单元格填写有限数字，可用均值 ± 标准差。列标题标出单位，无单位的指标标为“无量纲”。删去无关的额外指标或额外消融行。未测或不可判定的结果保留原状，在第五节记录 PENDING 和缺口。

| 编号 | 实测方法定义及版本 | {{FILL:主指标（单位）}} | {{FILL:可行性或约束指标（单位）}} | {{FILL:计算开销指标（单位）}} |
| --- | --- | --- | --- | --- |
| M0 | {{FILL:传统基线}} | {{FILL:数值}} | {{FILL:数值}} | {{FILL:数值}} |
| M1 | {{FILL:最接近方法及复现版本}} | {{FILL:数值}} | {{FILL:数值}} | {{FILL:数值}} |
| M2 | {{FILL:红队登记的强朴素适配基线}} | {{FILL:数值}} | {{FILL:数值}} | {{FILL:数值}} |
| M3 | {{FILL:完整方法}} | {{FILL:数值}} | {{FILL:数值}} | {{FILL:数值}} |
| M3 w/o {{FILL:模块}} | {{FILL:去掉的机制及其他保持的条件}} | {{FILL:数值}} | {{FILL:数值}} | {{FILL:数值}} |

## 四、虚假胜出排查
<!-- section:audit -->

- <!-- field:sanity --> **基线合理性核验**：{{FILL:检验原始输出量级、配置或复现的一项观察及定位}}
- <!-- field:artifacts --> **对比假象排查**：{{FILL:同等调参、信息可见性与容差的实测核验，说明种子或工况稳定性}}
- <!-- field:uncertainty --> **不确定性与判定限制**：{{FILL:说明不同种子或工况的波动，或说明单次测量不足以判断的范围}}
- <!-- field:scaling --> **规模探针或适用边界**：{{FILL:两个规模的耗时或内存及其定位，或陈述单规模限制和结论范围}}

## 五、证据分流
<!-- section:result -->

- <!-- field:outcome --> **分流**：PENDING
- <!-- field:decision_basis --> **依据**：{{FILL:填写 ADVANCE、REVISE、STOP 或 PENDING；将观察与预注册规则逐项对应，指出结果定位与未满足项}}
- <!-- field:boundary --> **可对外主张的边界**：{{FILL:用可核验的表述写清目前得到的结论和未验证的范围}}

残差修订另开轮次并保留原报告。修改已锁定的判定条件时记录为探索性修订。

## 六、人类决策点 2
<!-- section:decision2 -->

作者结合独立的内部备忘录单选。提交待审时可留空。

- [ ] <!-- decision:advance --> **锁定进入阶段 5**
- [ ] <!-- decision:revise --> **指定范围后继续修订**
- [ ] <!-- decision:stop --> **停止当前方案**
