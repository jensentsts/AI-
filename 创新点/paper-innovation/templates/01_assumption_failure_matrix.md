# 01 Literature Evidence and Assumption–Failure Matrix

- **研究主题 / Topic**：{{TOPIC}}
- **目标期刊 / Journal**：{{JOURNAL}}
- **日期 / Date**：{{DATE}}
- **检索范围 / Search scope**：{{FILL:databases, query terms, date window, and exclusion boundary}}
- **检索前的人类种子思路 / Frozen human seed**：{{FILL:write the initial intuition, or “none”}}

Before the search, record the target claim, available measurements, required but missing data, and the solver or time budget where relevant. Keep the original wording of the author's question for the provenance check.

## 0. Independent idea origins

Use `user`, `observation`, `constraint`, or `derivation`. Give the author's original question, an observation record, an actual constraint, or an independently dated derivation. Record the provenance even if the question was supplied after the search.

<!-- section:idea_origins -->
| ID | Origin type | Independent problem | Own source anchor |
| :--- | :--- | :--- | :--- |

## 0.1 Literature as callable objects

Choose the object's role from `method`, `theorem`, `data`, `constraint`, `baseline`, or `observation`. Reuse its work ID from the evidence register and specify what it takes, what it returns, and when it applies. Leave the table empty when no object is needed.

<!-- section:literature_objects -->
| ID | Role | Inputs | Preconditions | Known operation | Outputs | Applicability boundary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |

## 1. Unique-paper evidence register

Use one row per work. `Work ID` and `Evidence source IDs` are citation keys (for example `L1`). Give each work a DOI, arXiv ID, PII, or an existing local paper path. Mark the reading depth exactly `full-text` or `abstract-only`. Pinpoint findings to pages, equations, figures, tables, or theorems. The validator counts canonical works once even when aliases or duplicate rows recur. Older original papers and theories remain eligible evidence.

<!-- section:literature_table -->
| Work ID | Year / journal / title | Canonical locator (DOI / arXiv / PII) | Local full-text path (optional) | Depth | Evidence source IDs | Finding or claim | Pinpoint(s) | Evidence status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| L1 | {{FILL:year, venue, and short title}} | {{FILL:stable DOI, arXiv ID, or PII}} |  | {{FILL:full-text or abstract-only}} | {{FILL:L1}} | {{FILL:one finding, assumption, or reported result}} | {{FILL:L1 p. X / Eq. (Y) / Fig. Z / Theorem N}} | {{FILL:reported, reproduced, or pending}} |

### Author outlooks for the independent reviewer

When the authors explicitly suggest a next step relevant to the project, record it with its source location here. The reviewer uses this entry to check prior suggestions, including paraphrases. This table stays outside the generation brief.

| Work ID | Future Work | Page or section |
| --- | --- | --- |

## 2. Cross-domain tools (required for full method exploration)

For `full` mode with a method claim, add at least two tools from distinct neighboring fields. State the abstract structure, source, benefit, and hard migration barrier. Other claim families and focused modes may leave this table empty.

<!-- section:cross_domain_table -->
| Tool ID | Abstract mathematical or system structure | Source work ID / locator | Advantage | Migration barrier (units, timing, observability, discreteness, nonconvexity, scale) |
| :--- | :--- | :--- | :--- | :--- |

## 3. Conflict and hypothesis records

Copy a section for each additional `C` ID. Full exploration needs at least two distinct records. Choose scope `recurring`, `original-theory`, or `hypothesis`; choose evidence status `reported`, `reproduced`, or `pending`. A recurring literature conflict needs at least three distinct full-text works, each with a pinpoint. An original result can cite its source without a recency cutoff. A hypothesis may begin with one source, but must name an observation and a falsifier.

### Structural conflict C1
<!-- section:conflict_C1 -->
- <!-- field:claim --> **Claim / conflict statement**：{{FILL:state the precise assumption, trade-off, failure, or hypothesis}}
- <!-- field:claim_scope --> **Claim scope**：{{FILL:recurring, original-theory, or hypothesis}}
- <!-- field:evidence_status --> **Evidence status**：{{FILL:reported, reproduced, or pending}}
- <!-- field:evidence_sources --> **Evidence source IDs**：{{FILL:L1; L2; L3, as applicable}}
- <!-- field:pinpoints --> **Pinpoints by source**：{{FILL:L1 p. X; L2 Eq. (Y); L3 Fig. Z}}
- <!-- field:observation --> **Observed result or discriminating observation**：{{FILL:what was reported, reproduced, or can be observed}}
- <!-- field:falsifier --> **Falsifier, if still a hypothesis**：
- <!-- field:result_artifact --> **Existing result artifact, if reproduced**：

## 4. Evidence interpretation

Use `reported` only for a result located in the cited source, `reproduced` only with your own case and result location, and `pending` for an inference that still needs a test. Record missing data as a boundary on the claim. Do not treat a search gap as evidence that no earlier theory exists.
