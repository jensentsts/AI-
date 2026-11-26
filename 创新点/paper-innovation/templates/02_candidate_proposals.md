# 02 Candidate Proposals

- **研究主题 / Topic**：{{TOPIC}}
- **目标期刊 / Journal**：{{JOURNAL}}
- **日期 / Date**：{{DATE}}
- **How to use**：Start with one proposal. Copy the whole section and assign the next exact ID (`P2`, `P1-v2`, etc.) when the selected mode requires more proposals. `full` needs at least two candidates; `single`, `revision`, and `local-pdf` may use one.
- **Source rule**：Papers are callable objects only. Do not use an author’s outlook, future-work paragraph, or unexecuted suggestion as the origin of a new idea. If an author-supplied idea overlaps a prior work, stop or revise it and record the difference. A familiar problem, constraint, observation, or derivation may be an independent origin when its provenance is recorded.
- **Generation order**：A fresh generator receives the independent Q-origin brief plus sanitized L interfaces, then returns a neutral `idea_draft`. It may choose L calls and must record their supplied inputs and output use in the bindings table; it does not see raw 01 papers or receive their outlook as idea prompts. Afterward, the evidence coordinator adds and verifies C IDs, raw M1 citations, pinpoints, and source provenance. The coordinator may validate the generator’s source and delta but must not rewrite them or retrofit an L call.

## Proposal P1
<!-- section:proposal_P1 -->
- <!-- field:claim --> **Claim type**：{{FILL:method, theory, or phenomenon}}
- <!-- field:claim_statement --> **Research claim**：{{FILL:one specific, falsifiable sentence}}
- <!-- field:conflict_ids --> **Structural conflict IDs**：{{FILL:C1, etc. from 01}}
- <!-- field:origin_ids --> **Independent origin IDs**：{{FILL:one or more Q IDs}}
- <!-- field:calls --> **Called literature-object IDs**：{{FILL:L1 list, or NONE}}
- <!-- field:novel_delta --> **Novel delta beyond those objects**：{{FILL:the exact operation, assumption, boundary, or result that changes}}
- <!-- field:generation --> **Generation**：{{FILL:fresh or author-supplied}}
- <!-- field:brief_sha256 --> **Safe-brief SHA-256 (fresh proposals only)**：

### Callable bindings

The generator records each selected L ID, supplied inputs, and how the returned output is used. Leave this table empty when `calls` is `NONE`.

<!-- section:call_bindings -->
| ID | Supplied inputs | Use of output |
| :--- | :--- | :--- |

### Method claim fields (fill only when Claim type is `method`)
- <!-- field:operators --> **Construction operator(s)**：
- <!-- field:m1 --> **M1: closest full-text method, source ID, and pinpoint**：
- <!-- field:m2 --> **Strong naive baseline**：
- <!-- field:prediction --> **Discriminating prediction and observable metric**：
- <!-- field:falsifier --> **Falsifier: condition and observable result that would refute the claim**：
- <!-- field:ablation --> **Ablation variant**：
- <!-- field:ablation_outcome --> **Expected ablation outcome**：

### Theory claim fields (fill only when Claim type is `theory`)
- <!-- field:implication --> **Implication test against the closest prior result**：
- <!-- field:witness --> **Witness or counterexample for the claimed boundary**：

### Phenomenon claim fields (fill only when Claim type is `phenomenon`)
- <!-- field:rival_explanation_a --> **Rival explanation A**：
- <!-- field:rival_explanation_b --> **Rival explanation B**：
- <!-- field:prediction_a --> **Different prediction under explanation A**：
- <!-- field:prediction_b --> **Different prediction under explanation B**：
- <!-- field:data_observation --> **Data and observation that separate the explanations**：

### Risks
- <!-- field:risks --> **Known technical, data, proof, and scale risks**：
