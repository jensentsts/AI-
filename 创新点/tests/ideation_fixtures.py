"""Small synthetic evidence packets used to test structure and provenance."""

from pathlib import Path
import re


SCRIPTS = Path(__file__).resolve().parents[1] / "paper-innovation" / "scripts"
MATRIX = "01_assumption_failure_matrix.md"
PROPOSALS = "02_candidate_proposals.md"
VERDICTS = "03_redteam_verdict.md"
VERIFICATION = "04_mvp_verification.md"
MEMO = "05_internal_flaw_memo.md"
FINAL = "06_final_contributions.md"
CALL_HEADERS = ("ID", "Supplied inputs", "Use of output")


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def update(path, before, after):
    content = path.read_text(encoding="utf-8")
    if before not in content:
        raise AssertionError(f"Fixture target missing in {path.name}: {before!r}")
    write(path, content.replace(before, after, 1))


def fill(path, **values):
    content = path.read_text(encoding="utf-8")
    for field, value in values.items():
        marker = f"<!-- field:{field} -->"
        pattern = re.compile(rf"^(.*?{re.escape(marker)}.*?\*\*[:：]).*?$", re.M)
        content, changed = pattern.subn(lambda match: f"{match[1]} {value}", content)
        if changed != 1:
            raise AssertionError(f"Expected one {marker} in {path.name}, got {changed}")
    write(path, content)


def table(headers, rows):
    def line(cells):
        return "| " + " | ".join(cells) + " |"

    return "\n".join([line(headers), line(["---"] * len(headers)), *(line(row) for row in rows)])


def fields(**values):
    return "\n".join(f"- <!-- field:{key} --> **{key}**: {value}" for key, value in values.items())


def section(title, marker, content, *, level=2):
    return f"{'#' * level} {title}\n<!-- section:{marker} -->\n\n{content}\n"


def replace_table(path, new_table, *, section=None):
    content = path.read_text(encoding="utf-8")
    suffix = content
    if section:
        _, _, suffix = content.partition(f"<!-- section:{section} -->")
    match = re.search(r"^\|.*(?:\n\|.*)+", suffix, re.M)
    if not match:
        raise AssertionError(f"Fixture table missing in {path.name}: {section}")
    update(path, match.group(), new_table)


def local_pdf(path, finding):
    """Create a one-page local source with a real page pinpoint."""
    stream = f"BT /F1 12 Tf 72 720 Td ({finding}) Tj ET\n".encode("ascii")
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"endstream",
    )
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
    xref = len(data)
    data.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    data.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


TOPICS = {
    "method": "Storage dispatch with delayed telemetry",
    "theory": "A terminal reserve bound for storage schedules",
    "phenomenon": "Different generator responses to negative prices",
}


PRIOR_FINDINGS = {
    "method": "A rolling controller updates reserves when fresh telemetry becomes available",
    "theory": "The common state variable satisfies a nonnegative lower bound",
    "phenomenon": "Aggregate generator output falls in some negative price hours",
}


OWN_PROBLEMS = {
    "method": "The scheduling team needs a reserve that accounts for stale telemetry during missed updates.",
    "theory": "Operations requested a terminal schedule that can cover an extra 1 MWh reserve obligation.",
    "phenomenon": "The operator observed divergent output at two co-located plants during a negative-price hour.",
}


NEW_DELTAS = {
    "method": "Size the reserve by observation age; L1 p. 1 keeps its value fixed between updates.",
    "theory": "Add a terminal reserve obligation; L1 p. 1 gives only a nonnegative state bound.",
    "phenomenon": "Compare linked plant-hour exposure and instruction records; L1 p. 1 aggregates output across plants.",
}


CALL_FIXTURES = {
    "method": (
        "baseline", "Hourly schedules, reserve configuration, and telemetry timestamps",
        "Each schedule uses the same cutoff and feasible dispatch bounds", "Hourly reserve schedule",
        "Eight synthetic hours with stale telemetry in hours 3–5 and the fixed reserve configuration.",
        "Use the returned schedule as M1 and re-score its cost and violations on the shared replay.",
    ),
    "theory": (
        "theorem", "Storage state and bounds on the state domain", "The state has a nonnegative lower bound",
        "Whether a given state meets the established bound",
        "Evaluate the common interval from 0 to 2 MWh at the proposed witness x = 0.5 MWh.",
        "Compare the returned feasibility judgment with the terminal reserve obligation on the same witness.",
    ),
    "phenomenon": (
        "observation", "Hourly generator outputs and nodal prices", "Meter readings share the same hour and node",
        "Change in aggregate output during the negative-price window",
        "Use hourly meter readings for plants A and B in the shared negative-price interval.",
        "Use the aggregate change as the reference before comparing output by settlement exposure and dispatch order.",
    ),
}


PROPOSAL_ARGUMENTS = {
    "method": {
        "m1": "L1 p. 1: rolling controller v1 frozen at shared tuning.",
        "m2": "Extend the rolling controller with a fixed reserve from the same input stream.",
        "prediction": "Observation age lowers dispatch cost at equal feasibility under telemetry configuration C4.",
        "falsifier": "Reject the claim if the saving against M2 falls below 5 USD or violations increase.",
        "ablation": "M3 w/o delay bound keeps the tuning and uses a fixed reserve.",
        "ablation_outcome": "Removing the age bound increases cost by at least 3 USD.",
    },
    "theory": {
        "implication": "On 0 <= x <= 2, x >= 1 implies L1 p. 1's x >= 0. Check the converse on the same interval.",
        "witness": "A common feasible x = 0.5 satisfies the old inequality but refutes the converse.",
    },
    "phenomenon": {
        "rival_explanation_a": "Settlement exposure changes the generator's incentive to produce.",
        "rival_explanation_b": "A dispatch instruction mandates reduced production.",
        "prediction_a": "Only a plant with merchant exposure reduces output without an order.",
        "prediction_b": "Reduction occurs only in plant-hours with a matched dispatch order.",
        "data_observation": "Join hourly output, settlement terms, and dispatch orders by plant and hour.",
    },
}


def populate_literature(workspace, claim, *, proposals=("P1",), literature_rows=1,
                        missing_locator=False, duplicate_locator=False, recurring=False):
    """Write local full-text provenance and the candidate claim it motivates."""
    finding = PRIOR_FINDINGS[claim]
    year = 1992 if claim == "theory" else 2025
    role, inputs, preconditions, output, supplied_inputs, use_of_output = CALL_FIXTURES[claim]
    rows = []
    for index in range(1, literature_rows + 1):
        work = f"L{index}" if not missing_locator else "L1"
        path = f"papers/现场-{index:02d}.pdf"
        locator = f"10.99999/local-fixture-{index:02d}"
        if duplicate_locator:
            locator = "https://doi.org/10.99999/FIXTURE-SAME" if index % 2 else "doi:10.99999/fixture-same"
        if missing_locator:
            locator, path = "", ""
        else:
            local_pdf(workspace / path, f"Synthetic source {work}: {finding}")
        rows.append((work, f"{year} Fixture proceedings", locator, path, "full-text", work,
                     finding, f"{work} p. 1", "reported"))
    refs = range(1, (literature_rows if recurring else 1) + 1)
    anchors = ", ".join(f"L{n}" for n in refs)
    pinpoints = "; ".join(f"L{n} p. 1" for n in refs)
    literature = table(
        ("Work ID", "Year/journal", "Canonical locator", "Local full-text path", "Depth",
         "Evidence source IDs", "Finding/claim", "Pinpoints", "Evidence status"), rows,
    )
    scope = "original-theory" if claim == "theory" else "hypothesis"
    if recurring:
        scope = "recurring"
    conflicts = "### Structural conflict C1\n" + fields(
        claim_scope=scope,
        evidence_status="reported" if recurring or claim == "theory" else "pending",
        evidence_sources=anchors, pinpoints=pinpoints, observation=finding,
        falsifier="Compare the closest baseline and candidate under the same observation cutoff.",
    )
    if missing_locator:
        conflicts += "\n\n### Structural conflict C2\n" + fields(
            claim_scope="hypothesis", evidence_status="pending", evidence_sources="L1", pinpoints="L1 p. 1",
            observation="Hourly averaging could remove short violations.",
            falsifier="Reject if violation counts remain equal under five-minute sampling.",
        )
    source_note = "own evidence/initial question.md"
    write(workspace / source_note, f"# Observation\n\n{OWN_PROBLEMS[claim]}\n")
    write(workspace / MATRIX, "\n\n".join((
        "# 01 Evidence matrix\n" + fields(search_log="Local synthetic sources, indexed 2026-11-26"),
        section("Vertical literature", "literature_table", literature),
        section("Independent idea origins", "idea_origins", table(
            ("ID", "Origin type", "Independent problem", "Own source anchor"),
            (("Q1", "user", OWN_PROBLEMS[claim], f"`{source_note}` § Observation"),),
        )),
        section("Literature objects", "literature_objects", table(
            ("ID", "Role", "Inputs", "Preconditions", "Known operation", "Outputs", "Applicability boundary"),
            (("L1", role, inputs, preconditions, finding, output, "Within the supplied domain and assumptions"),),
        )),
        section("Horizontal tools", "cross_domain_table", table(
            ("Tool", "Abstract structure", "Source", "Benefit", "Transfer constraint"),
            (("T1", "bounded-state replay", "Synthetic source L1 p. 1", "Compare under identical bounds", "Time alignment"),
             ("T2", "paired observations", "Methods note in the local fixture", "Hold common factors fixed", "Missing records")),
        )),
        section("Structural conflicts", "conflicts", conflicts),
    )))
    candidates = ["# 02 Candidate proposals"]
    bindings = section("Callable bindings", "call_bindings", table(
        CALL_HEADERS, (("L1", supplied_inputs, use_of_output),),
    ), level=3)
    for number, proposal in enumerate(proposals, 1):
        candidates.append(f"## Proposal {proposal}\n" + fields(
            claim=claim, claim_statement=TOPICS[claim], conflict_ids="C1", operators=f"O{number}",
            origin_ids="Q1", calls="L1", novel_delta=NEW_DELTAS[claim], generation="author-supplied",
            **PROPOSAL_ARGUMENTS[claim],
        ) + "\n\n" + bindings.rstrip())
    write(workspace / PROPOSALS, "\n\n".join(candidates) + "\n")


def populate_redteam(workspace, claim, *, proposals=("P1",), selected=("P1",), verdict="PASS"):
    alternative, planned_evidence = {
        "method": (
            "M2 uses a fixed reserve under identical cutoffs, constraints, seeds, and tuning budgets.",
            "Replay timestamps from the frozen input, then check the five benchmark rows against raw metrics.",
        ),
        "theory": (
            "L1 p. 1 states a nonnegative lower bound. Check implication in each direction on [0, 2].",
            "Record a proof of the forward implication and a witness refuting the converse on the common domain.",
        ),
        "phenomenon": (
            "A dispatch instruction could explain reduced output. Compare instructions and output by plant-hour.",
            "Join the meter data to both settlement terms and instructions, and mark both predictions explicitly.",
        ),
    }[claim]
    comparator_key = {"method": "m2", "theory": "strongest_prior", "phenomenon": "alternate_explanation"}[claim]
    priority = "1" if verdict == "PASS" else "—"
    summary = table(
        ("Proposal ID", "Claim", "Route", "Gate status", "Verdict", "Reason", "Priority"),
        ((pid, claim, TOPICS[claim], "checked", verdict, "Scope aligned against source L1 p. 1", priority)
         for pid in proposals),
    )
    reports = []
    for pid in proposals:
        if verdict == "PASS":
            branch = {
                "verification_artifacts": planned_evidence,
                "risks": "1. Input truncation may bias results; 2. Repeatability requires a new observation window.",
            }
        else:
            branch = {"kill_defer_reason": "L1 already establishes the same claim on the common domain."}
        reports.append(f"### Review {pid}\n" + fields(
            steelman=f"A narrow, testable claim on {TOPICS[claim].lower()} under the shared observation window.",
            prior_query="Bounded-state replay, reserve constraints, and delayed or missing observation",
            prior_sources="Local full-text evidence register and the bibliography available for L1",
            prior_date="2026-11-26",
            prior_scope="Compared titles, abstracts and full texts in this local fixture corpus, including older sources.",
            prior_result="L1 p. 1 is the closest locally available comparator.",
            prior_relation="INDEPENDENT" if verdict == "PASS" else "KNOWN",
            prior_difference=NEW_DELTAS[claim] if verdict == "PASS" else "L1 p. 1 already establishes the proposed claim.",
            **{comparator_key: alternative},
            **branch,
        ))
    decision = fields(selected=", ".join(selected))
    write(workspace / VERDICTS, "\n\n".join((
        "# 03 Red-team review\n" + fields(isolation="independent"),
        section("Verdict summary", "verdict_table", summary),
        section("Reviews", "reviews", "\n\n".join(reports)),
        section("Human Decision 1", "decision1", decision),
    )))


CLAIM_RULES = {
    "method": {
        "advance": "M3 saves at least 5 USD versus M2 at 0% violations; the ablation loses 3 USD.",
        "revise": "M3 saves at least 2 USD but less than 5 USD at unchanged feasibility.",
        "stop": "M3 saves less than 2 USD or has any additional hard violation.",
        "indeterminate": "A forecast timestamp is absent or the M2 input replay fails.",
    },
    "theory": {
        "advance": "The new inequality implies the old one, with a feasible witness for strictness.",
        "revise": "The implication requires a positive initial storage level.",
        "stop": "The two inequalities imply each other under the stated assumptions.",
        "indeterminate": "A witness fails the common bounds or a quantifier is unresolved.",
    },
    "phenomenon": {
        "advance": "With no dispatch order, output falls only for generators exposed to negative prices.",
        "revise": "The divergence holds only for hourly settlements.",
        "stop": "Both contract classes reduce output identically without dispatch orders.",
        "indeterminate": "Settlement terms or dispatch instructions cannot be joined to a meter row.",
    },
}


METHOD_ROWS = [
    ("M0", "Day-ahead schedule", "105", "4", "1"),
    ("M1", "Rolling controller v1 with frozen tuning", "102", "0", "8"),
    ("M2", "Rolling controller with a fixed reserve", "100", "0", "9"),
    ("M3", "Rolling controller with delay-dependent reserve", "94", "0", "10"),
    ("M3 w/o delay bound", "Restore the fixed reserve at identical tuning", "99", "0", "9"),
]


def preregister(workspace, run, claim):
    path = run / VERIFICATION
    fill(path, **CLAIM_RULES[claim])
    if claim == "method":
        script = (run / "evidence" / "replay.py").relative_to(workspace).as_posix()
        write(workspace / script, f"from pprint import pprint\n\npprint({METHOD_ROWS!r})\n")
        fill(
            path, case="Eight hourly intervals with stale telemetry on hours 3–5.",
            data_origin="synthetic-proxy v1, eight intervals from a bounded dispatch toy model.",
            m1_origin="simplified-proxy of L1; verifies deadline handling on the toy model only.",
            comparison="M0 is open loop; M1 re-solves; M2 adds fixed reserve; M3 sizes reserve by age. "
            "The ablation restores the fixed reserve. Same constraints, timestamp cutoffs, seed 7 and budget.",
            script=f"`{script}`", command=f"Run `python {script}` from the workspace root.",
            primary_metric="Cost (USD)", metric_direction="min", min_difference="5",
        )
    elif claim == "theory":
        fill(
            path, case="Every storage schedule with capacity 2 MWh must satisfy terminal reserve x >= 1 MWh.",
            assumptions="Both inequalities use the same real state 0 <= x <= 2 MWh.",
            comparator="L1 p. 1 gives x >= 0 MWh. Compare the two implications on [0, 2].",
            comparison="Subtract the bounds and check x = 0.5 against both.",
        )
    else:
        fill(
            path, case="Two co-located generators during one negative-price hour.",
            prediction_a="Merchant exposure predicts reduction only at the exposed generator.",
            prediction_b="A dispatch instruction predicts reduction only with a matching order.",
            acquisition="Join settlement terms, pre-hour and hourly output, and instructions by plant-hour.",
        )


def record_observations(workspace, run, claim, *, blank_method_metrics=False):
    path = run / VERIFICATION
    suffix = {"method": "metrics.csv", "theory": "witness.md", "phenomenon": "observations.csv"}[claim]
    evidence = run / "evidence" / suffix
    fill(path, raw=f"`{evidence.relative_to(workspace).as_posix()}`")
    if claim == "method":
        headers = ("编号", "实测方法定义及版本", "Cost (USD)", "Violation rate (%)", "Runtime (ms)")
        rows = [row[:2] + ("", "", "") for row in METHOD_ROWS] if blank_method_metrics else METHOD_ROWS
        replace_table(path, table(headers, rows), section="evidence")
        write(evidence, ",".join(headers) + "\n" + "\n".join(",".join(row) for row in rows) + "\n")
        fill(path, scaling="One 8-interval instance only. No scaling estimate is made.",
             uncertainty="One deterministic replay at seed 7; the result has no sampling interval.")
        basis = "M3 saves 6 USD against M2 at 0% violations; removing the age bound loses 5 USD."
    elif claim == "theory":
        write(evidence, "# Witness check\n\nx = 0.5 MWh satisfies 0 <= x <= 2 and x >= 0, but violates x >= 1.\n")
        fill(path, locator="line 3", witness="x = 0.5 is within the common bounds and satisfies L1's lower bound only.")
        basis = "The forward implication follows by transitivity; the witness refutes the converse."
    else:
        write(evidence, "hour,plant,exposure,previous_MW,actual_MW,order\n01,A,merchant,5,2,none\n01,B,fixed,5,5,none\n")
        replace_table(path, table(
            ("预测编号", "实际观察或判别所缺的记录", "局部证据定位", "结论"),
            (("A", "Only the merchant plant reduced output", "line 2", "supports"),
             ("B", "Neither plant received an order", "lines 2–3", "contradicts")),
        ), section="evidence")
        basis = "The merchant plant reduces output by 3 MW with no recorded dispatch order."
    fill(
        path, sanity=f"Rechecked the timestamps or shared constraints in {suffix}, lines 2–3.",
        artifacts="Comparison uses the same observation window and explicit inclusion rules.",
        outcome="ADVANCE", decision_basis=basis, boundary="The conclusion is limited to this synthetic case.",
    )


def record_risks(run):
    memo = run / MEMO
    fill(
        memo, rigor="The fixture establishes a local comparison under its stated bounds.",
        sensitivity="An hour with missing telemetry would remove the comparison window.",
        extension="Recheck the assumptions on additional independent observations.",
    )
    replace_table(memo, table(
        ("风险编号", "局限或证据缺口", "触发条件、观察及定位", "可能的审稿质疑", "可选处置"),
        (("R1", "An unlogged event could defeat matching", "When the join fails; see 04 §4",
          "External validity changes across observation windows", "Restrict the claim to matched windows"),),
    ), section="risks")


def approve(run, decision="advance"):
    update(run / VERIFICATION, f"[ ] <!-- decision:{decision}", f"[x] <!-- decision:{decision}")
    memo = run / MEMO
    fill(memo, author="Lin, fixture author", approval_date="2026-11-26")
    replace_table(memo, table(
        ("风险编号", "作者确认的处置或公开主张边界"),
        (("R1", "Restrict the interpretation to explicitly observed conditions."),),
    ), section="author_response")


FINAL_CLAIMS = {
    "method": ("On the replay, the delay-aware reserve saves 6 USD at unchanged violation rate.",
               "The no-delay-bound ablation isolates a 5 USD increase for the same schedule.",
               "04#evidence:M2 and 04#evidence:M3", "04#evidence:M3-w/o-delay-bound"),
    "theory": ("The terminal reserve bound implies the previous nonnegative bound on the common interval.",
               "The 0.5 MWh witness satisfies the previous bound and violates the terminal reserve bound.",
               "04#evidence:witness", "04#evidence:locator"),
    "phenomenon": ("In the observed hour only the exposed generator decreased output.",
                   "The matched instruction log distinguishes the contract and dispatch predictions in that hour.",
                   "04#evidence:A", "04#evidence:B"),
}


def populate_final(run, claim, *, checklist=True):
    path = run / FINAL
    first, second, anchor_one, anchor_two = FINAL_CLAIMS[claim]
    fill(
        path, english_title=TOPICS[claim], chinese_title="电力系统运行边界与最小验证",
        story=first, established_terms="Power, reserve, dispatch, observation window", new_terms="无",
    )
    update(path, "1. {{FILL:贡献 1 的具体主张}}", f"1. {first}")
    update(path, "2. {{FILL:贡献 2 的具体主张}}", f"2. {second}")
    replace_table(path, table(
        ("贡献编号", "对应问题和证据范围", "章节与公式或主张", "图表或推导锚点", "后续验证任务", "04 已有证据锚点"),
        (("C1", first, "§2 setup", "Figure 1", "Check another observation window", anchor_one),
         ("C2", second, "§3 comparison", "Table 1", "Repeat under a second configuration", anchor_two)),
    ), section="mapping")
    if checklist:
        for item in ("review", "evidence", "scope", "memo"):
            update(path, f"[ ] <!-- check:{item}", f"[x] <!-- check:{item}")
