"""Verification, preregistration, and handoff checks for the selected proposal."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path

from ideation_markdown import PID, field, has_value, section, table
from ideation_review import approved_proposals, proposal_claims, verdicts


REPORT = "04_mvp_verification.md"
MEMO = "05_internal_flaw_memo.md"
HANDOFF = "06_final_contributions.md"
PREREG = r"预注册判定规则|Preregistration|Pre-registration"
DESIGN = r"算例与公平|同口径比较设计|竞争解释与观察设计|Verification Design|Test Design"
EVIDENCE = r"四组强制对照|实测结果与对照|实际推导或见证|实际观察与预测|Evidence|Results Table"
AUDIT = r"虚假胜出排查|理论边界与假象排查|观察质量与替代解释排查|Audit"
RESULT = r"结果分流|证据分流|Outcome|Triage"
DECISION = r"人类决策点\s*2|Human Decision\s*(?:Gate\s*)?2"
RISK_ID = r"R[1-9]\d*"
UNRESOLVED = re.compile(
    r"^(?:未测(?:量)?|未运行|(?:尚)?未验证|未判定|尚未判定|不可判定|无法判断|未完成|"
    r"无数据|未获得|缺失|仅占位|待签字|not measured|unmeasured|not run|"
    r"not available|not tested|not (?:yet )?verified|inconclusive|unresolved|none|null|nan|n/?a)"
    r"(?:$|[。.!:：]|(?:\s+yet)?\s*$)",
    re.I,
)
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
METRIC = re.compile(
    rf"\s*({NUMBER})\s*%?(?:\s*(?:±|\+/-)\s*({NUMBER})\s*%?)?\s*"
)
ABA = re.compile(r"M3\s+w/o\s+(.+)", re.I)
TASK = re.compile(r"^\s*[-+*]\s+\[([ xX])\]\s*(.+)$")
LEGACY_FILL = re.compile(r"【(?:审稿人质疑点|处置建议|由人类决策后记录[^】]*)】")
OUTCOME_ALIASES = {
    "ADVANCE": "ADVANCE", "REVISE": "REVISE", "STOP": "STOP", "PENDING": "PENDING",
    "INCONCLUSIVE": "PENDING", "不可判定": "PENDING", "未测": "PENDING",
}


def _plain(value: str) -> str:
    return value.strip().strip("\x60*_\"'").strip()


def _present(value: str) -> bool:
    return has_value(value) and not LEGACY_FILL.search(value) and not UNRESOLVED.match(_plain(value))


def _read(work: Path, name: str, errors: list[str]) -> str:
    path = work / name
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        errors.append(f"{name}: unable to read artifact as UTF-8.")
        return ""
    errors.append(f"Missing required artifact: {name}")
    return ""


def _metadata(text: str) -> str:
    return re.split(r"(?m)^#{2,6}\s", text, maxsplit=1)[0]


def _proposal(text: str) -> str:
    value = field(_metadata(text), "proposal", r"对应方案|锁定验证方案与状态|最终方案|^Proposal(?: ID)?$")
    if not _present(value):
        return ""
    # The older report also allowed a parenthesized lifecycle after the ID.
    match = re.fullmatch(rf"({PID})(?:\s*[（(][^()（）]+[）)])?", value.replace("\x60", "").strip())
    return match[1] if match else ""


def _claim(text: str) -> str:
    return _plain(field(_metadata(text), "claim", r"主张类型|Claim Type")).lower()


def _require(text: str, keys: dict[str, str], label: str, errors: list[str]) -> dict[str, str]:
    values = {key: field(text, key, pattern) for key, pattern in keys.items()}
    for key, value in values.items():
        if not _present(value):
            errors.append(f"{label}: missing or unfilled {key}.")
    return values


def _provenance(value: str, options: str) -> bool:
    match = re.match(rf"^({options})(?=$|[\s:：、，,;(（])", _plain(value), re.I)
    return bool(match and _present(_plain(value)[match.end():].strip(" :：、，,;()（）")))


def _margin(value: str) -> float | None:
    value = _plain(value)
    if not re.fullmatch(NUMBER, value):
        return None
    margin = float(value)
    return margin if math.isfinite(margin) and margin > 0 else None


def _plan(root: Path, text: str, proposal: str | None, errors: list[str]) -> tuple[str, str, str]:
    selected, claim = _proposal(text), _claim(text)
    if not selected:
        errors.append(f"{REPORT}: identify the selected proposal in the proposal field.")
    elif proposal and selected != proposal:
        errors.append(f"{REPORT}: proposal {selected} does not match selected run {proposal}.")

    if not claim and re.search(r"(?m)^# 04 预注册最小原型仿真验证报告", text):
        claim = "method"
    if claim not in {"method", "theory", "phenomenon"}:
        errors.append(f"{REPORT}: declare claim type method, theory, or phenomenon.")
    if selected:
        registered_claim = proposal_claims(root).get(selected)
        if not registered_claim:
            errors.append(f"{REPORT}: {selected} is missing from the candidate proposals.")
        elif registered_claim != claim:
            errors.append(f"{REPORT}: claim {claim or '(missing)'} differs from 02's {registered_claim} for {selected}.")
        if verdicts(root).get(selected) != "PASS":
            errors.append(f"{REPORT}: {selected} must have a PASS verdict in 03.")
        elif selected not in approved_proposals(root):
            errors.append(f"{REPORT}: {selected} still needs a positive, checked Human Decision 1 in 03.")

    prereg = section(text, "prereg", PREREG)
    design = section(text, "design", DESIGN)
    rules = _require(prereg, {
        "advance": r"^Advance", "revise": r"^Revise", "stop": r"^Stop",
        "indeterminate": r"不可判定|Indeterminate",
    }, f"{REPORT} preregistration", errors)
    normalized_rules = [_plain(rules[key]).casefold() for key in ("advance", "revise", "stop")]
    if all(normalized_rules) and len(set(normalized_rules)) != 3:
        errors.append(f"{REPORT}: Advance, Revise and Stop need distinct decision conditions.")
    if claim == "method":
        values = _require(design, {
            "case": r"算例和工况|最小标准测试系统|Benchmark and Cases",
            "data_origin": r"数据来源|Data Origin|Dataset Provenance",
            "m1_origin": r"M1.*来源|M1 Provenance",
            "comparison": r"公平对比口径|Comparison Protocol",
            "primary_metric": r"主指标（表头）|Primary Metric",
            "metric_direction": r"主指标优化方向|Metric Direction",
            "min_difference": r"相对 M2 的最小实际意义差值|Minimum Meaningful Difference",
            "script": r"复现脚本路径|Reproduction Script",
            "command": r"运行命令|Reproduction Command|Run Command",
        }, f"{REPORT} method design", errors)
        for key, options in {
            "data_origin": "standard-benchmark|synthetic-proxy|observational-data",
            "m1_origin": "official-code|reimplemented-verified|simplified-proxy",
        }.items():
            if _present(values[key]) and not _provenance(values[key], options):
                errors.append(f"{REPORT}: {key} needs a provenance tag ({options}) and concrete detail.")
        if _present(values["primary_metric"]) and not _with_unit(values["primary_metric"]):
            errors.append(f"{REPORT}: primary_metric needs the exact benchmark header including its unit.")
        if _present(values["metric_direction"]) and _plain(values["metric_direction"]).lower() not in {"min", "max"}:
            errors.append(f"{REPORT}: metric_direction must be min or max.")
        if _present(values["min_difference"]) and _margin(values["min_difference"]) is None:
            errors.append(f"{REPORT}: min_difference must be a positive finite difference in the primary metric's units.")
    elif claim == "theory":
        _require(design, {
            "case": r"待验证命题|Proposition",
            "assumptions": r"共同假设|Common Assumptions",
            "comparator": r"最接近.*结论|Closest Comparator",
            "comparison": r"验证路线|Comparison Strategy",
        }, f"{REPORT} theory design", errors)
    elif claim == "phenomenon":
        values = _require(design, {
            "case": r"现象及观察单元|Phenomenon and Observational Unit",
            "prediction_a": r"解释 A 与预测|Prediction A",
            "prediction_b": r"解释 B 与预测|Prediction B",
            "acquisition": r"记录采集口径|Acquisition Protocol",
        }, f"{REPORT} phenomenon design", errors)
        prediction_a = _plain(values["prediction_a"]).casefold()
        prediction_b = _plain(values["prediction_b"]).casefold()
        if _present(prediction_a) and prediction_a == prediction_b:
            errors.append(f"{REPORT}: preregister two distinct competing predictions.")

    plan = "\n\n".join(
        "\n".join(line.rstrip() for line in item.splitlines()).strip()
        for item in (prereg, design)
    )
    return selected, claim, plan


def prereg_plan(root: Path, work: Path, proposal: str | None) -> tuple[str, str, list[str]]:
    """Read the selected proposal and the preregistration/design text to hash."""
    errors: list[str] = []
    text = _read(work, REPORT, errors)
    if not text:
        if not errors:
            errors.append(f"{REPORT}: empty report.")
        return "", "", errors
    selected, _, plan = _plan(root, text, proposal, errors)
    return selected, plan, errors


def _lock_is_valid(work: Path, selected: str, plan: str, errors: list[str]) -> bool:
    path = work / ".prereg_lock.json"
    if not path.is_file():
        errors.append(f"{REPORT}: missing preregistration lock. Run lock-prereg before collecting results.")
        return False
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(lock, dict):
            raise ValueError
        dt.datetime.fromisoformat(lock["locked_at"].replace("Z", "+00:00"))
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        errors.append(f"{REPORT}: malformed preregistration lock.")
        return False
    digest = hashlib.sha256(plan.encode("utf-8")).hexdigest()
    if not selected or lock.get("proposal") != selected or lock.get("sha256") != digest:
        errors.append(f"{REPORT}: preregistration or design has changed since locking, or the lock belongs to another proposal.")
        return False
    return True


def _local_path(root: Path, value: str, key: str, errors: list[str]) -> Path | None:
    if not _present(value):
        return None
    value = _plain(value)
    if value.startswith(("\\\\", "//")) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", value):
        errors.append(f"{REPORT}: {key} must use a local file path.")
        return None
    path = Path(value)
    try:
        resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
        if not path.is_absolute() and not resolved.is_relative_to(root.resolve()):
            errors.append(f"{REPORT}: {key} relative path must resolve inside the ideation directory.")
            return None
        if resolved.name.casefold() in {REPORT, MEMO, HANDOFF, ".prereg_lock.json"}:
            errors.append(f"{REPORT}: {key} must point to a separate evidence or script file.")
            return None
        if resolved.is_file() and resolved.stat().st_size > 0:
            return resolved
    except (OSError, RuntimeError, ValueError):
        pass
    errors.append(f"{REPORT}: {key} is missing, empty, or unavailable as a local file: {value}")
    return None


def _measured_mean(value: str) -> float | None:
    value = _plain(value).replace("−", "-").replace("％", "%")
    match = METRIC.fullmatch(value)
    if not match:
        return None
    mean = float(match[1])
    spread = float(match[2]) if match[2] is not None else 0.0
    return mean if math.isfinite(mean) and math.isfinite(spread) and spread >= 0 else None


def _with_unit(title: str) -> bool:
    match = re.search(r"[（(\[]([^()\[\]（）]+)[）)\]]\s*$", _plain(title))
    return _present(title) and bool(match and match.start() and _present(match[1]))


def _evidence_outcome(text: str) -> str:
    result = section(text, "result", RESULT)
    value = _plain(field(result, "outcome", r"分流|Outcome|Triage")).upper()
    if value in OUTCOME_ALIASES:
        return OUTCOME_ALIASES[value]
    legacy = re.match(r"^情况\s*([ABC])\s*[：:]", value)
    return {"A": "ADVANCE", "B": "REVISE", "C": "STOP"}[legacy[1]] if legacy else "PENDING"


def has_recorded_results(text: str, claim: str) -> bool:
    """Detect observations already recorded in 04 before the first locking operation."""
    if _evidence_outcome(text) != "PENDING" or _decision2(text, []) != "PENDING":
        return True
    evidence = section(text, "evidence", EVIDENCE)
    if claim == "theory":
        return _present(field(evidence, "witness", r"证明与反例结果|Proof or Witness Result"))
    _, rows = table(evidence)
    if claim == "phenomenon":
        return any(len(row) >= 2 and _present(row[1]) for row in rows)
    return any(_measured_mean(value) is not None for row in rows for value in row[2:])


def _method_evidence(
    root: Path, text: str, evidence: str, audit: str, raw: Path | None, outcome: str,
    errors: list[str], stats: dict,
) -> None:
    design = section(text, "design", DESIGN)
    script = _local_path(root, field(design, "script", r"复现脚本路径|Reproduction Script"), "script", errors)
    if raw and script == raw:
        errors.append(f"{REPORT}: raw result and reproduction script must be different files.")
    header, rows = table(evidence)
    stats["benchmark_rows"] = len(rows)
    if len(header) < 5 or not all(_with_unit(name) for name in header[2:]):
        errors.append(
            f"{REPORT}: benchmark needs at least three measured columns with named units "
            "(including feasibility and compute cost)."
        )
    primary_metric = _plain(field(design, "primary_metric", r"主指标（表头）|Primary Metric"))
    matches = [column for column, name in enumerate(header[2:], 2) if _plain(name) == primary_metric]
    if len(matches) != 1:
        errors.append(f"{REPORT}: primary_metric must match exactly one measured header.")
    primary_column = matches[0] if len(matches) == 1 else None
    methods: set[str] = set()
    primary_means: dict[str, float] = {}
    ablation_recorded = False
    for row in rows:
        name = _plain(row[0])
        ablation = ABA.fullmatch(name)
        valid_ablation = bool(ablation and _present(ablation[1]))
        ablation_recorded |= valid_ablation
        if name not in {"M0", "M1", "M2", "M3"} and not valid_ablation:
            errors.append(f"{REPORT}: unrecognized benchmark row {name or '(blank)'}.")
        if name in methods:
            errors.append(f"{REPORT}: duplicate benchmark row {name}.")
        methods.add(name)
        if len(row) != len(header) or len(row) < 5:
            errors.append(f"{REPORT}: benchmark row {name or '(blank)'} has the wrong number of cells.")
            continue
        if not _present(row[1]):
            errors.append(f"{REPORT}: benchmark row {name} needs an actual method definition.")
        for column in range(2, len(header)):
            mean = _measured_mean(row[column])
            if mean is None:
                errors.append(f"{REPORT}: benchmark row {name}, {header[column]}: expected a finite measured value.")
            elif column == primary_column and name in {"M2", "M3"}:
                primary_means[name] = mean
    for name in sorted({"M0", "M1", "M2", "M3"} - methods):
        errors.append(f"{REPORT}: missing required benchmark row {name}.")
    if not ablation_recorded:
        errors.append(f"{REPORT}: include one or more named M3 w/o ablation rows.")
    if len(primary_means) == 2:
        direction = _plain(field(design, "metric_direction", r"主指标优化方向|Metric Direction")).lower()
        margin = _margin(field(design, "min_difference", r"相对 M2 的最小实际意义差值|Minimum Meaningful Difference"))
        if direction in {"min", "max"} and margin is not None:
            improvement = primary_means["M3"] - primary_means["M2"]
            if direction == "min":
                improvement = -improvement
            reached = improvement >= margin or math.isclose(improvement, margin, rel_tol=1e-9)
            if math.isfinite(improvement):
                stats["primary_improvement"] = improvement
            stats.update(primary_metric=primary_metric, min_difference=margin, margin_reached=reached)
            if outcome == "ADVANCE" and not reached:
                errors.append(f"{REPORT}: M3 does not meet the preregistered {margin:g} improvement over M2 in {primary_metric}.")
    _require(audit, {
        "scaling": r"规模探针或适用边界|Scaling Probe or Scope",
        "uncertainty": r"不确定性与判定限制|Uncertainty",
    }, f"{REPORT} method audit", errors)


def _phenomenon_evidence(evidence: str, outcome: str, errors: list[str], stats: dict) -> None:
    header, rows = table(evidence)
    stats["observation_rows"] = len(rows)
    readings: dict[str, str] = {}
    for row in rows:
        key = _plain(row[0]).upper()
        if len(header) != 4 or len(row) != 4 or key not in {"A", "B"} or key in readings:
            errors.append(f"{REPORT}: observation table needs one four-cell row for each prediction, A and B.")
            continue
        status = _plain(row[3]).lower()
        readings[key] = status
        if not all(_present(value) for value in row[1:3]):
            errors.append(f"{REPORT}: prediction {key} requires an actual observation and a locator.")
        if status not in {"supports", "contradicts", "unresolved"}:
            errors.append(f"{REPORT}: prediction {key} needs supports, contradicts, or unresolved.")
    if set(readings) != {"A", "B"}:
        errors.append(f"{REPORT}: compare both preregistered predictions against the observations.")
    elif all(status == "unresolved" for status in readings.values()):
        errors.append(f"{REPORT}: neither prediction was resolved by the recorded observations.")
    elif outcome == "ADVANCE" and set(readings.values()) != {"supports", "contradicts"}:
        errors.append(f"{REPORT}: ADVANCE needs distinguishing evidence for one prediction against the other.")


def _decision2(text: str, errors: list[str]) -> str:
    decision = section(text, "decision2", DECISION)
    options = {
        "ADVANCE": r"锁定进入阶段\s*5|^Advance\b",
        "REVISE": r"继续沿残差微调|继续修订|^Revise\b",
        "STOP": r"果断弃题止损|停止当前方案|^Stop\b",
    }
    checked: list[str] = []
    seen: set[str] = set()
    for line in decision.splitlines():
        task = TASK.match(line)
        if not task:
            continue
        marker = re.search(r"<!--\s*decision:(advance|revise|stop)\s*-->", task[2], re.I)
        key = marker[1].upper() if marker else next(
            (key for key, pattern in options.items() if re.search(pattern, _plain(task[2]), re.I)), ""
        )
        if not key or key in seen:
            errors.append(f"{REPORT}: duplicated or unrecognized Human Decision 2 option.")
        seen.add(key)
        if task[1].lower() == "x":
            checked.append(key)
    if seen != set(options):
        errors.append(f"{REPORT}: Human Decision 2 must include Advance, Revise and Stop checkbox options.")
    if len(checked) > 1:
        errors.append(f"{REPORT}: Human Decision 2 requires one choice at most.")
    return checked[0] if len(checked) == 1 and checked[0] else "PENDING"


def _memo(text: str, selected: str, errors: list[str], stats: dict) -> dict[str, list[str]]:
    if not re.search(r"INTERNAL\s+ONLY|严禁直接写入正文", _metadata(text), re.I):
        errors.append(f"{MEMO}: missing INTERNAL ONLY header.")
    if not selected or _proposal(text) != selected:
        errors.append(f"{MEMO}: proposal must match the selected verification report.")
    _, rows = table(section(text, "risks", r"局限|风险清单|Risk Register"))
    risks: dict[str, list[str]] = {}
    for row in rows:
        name = _plain(row[0])
        if len(row) != 5 or not re.fullmatch(RISK_ID, name) or name in risks:
            errors.append(f"{MEMO}: use unique risk IDs with five cells per row (for example, R1).")
            continue
        if not all(_present(value) for value in row[1:]):
            errors.append(f"{MEMO}: fill the limitation, evidence, reviewer concern and possible treatment for {name}.")
        risks[name] = row
    stats["logged_risks"] = len(risks)
    if not risks:
        errors.append(f"{MEMO}: log at least one concrete risk.")
    _require(section(text, "boundaries", r"严谨性与敏感度|理论推导严谨性|Rigor and Sensitivity"), {
        "rigor": r"严谨性边界|严格证明.*工程近似|Rigor Boundary",
        "sensitivity": r"敏感因素|关键超参数与收敛稳定性|Sensitivity",
        "extension": r"扩展风险|对大算例扩展的预判风险|Extension Risk",
    }, f"{MEMO} pre-decision boundaries", errors)
    return risks


def _verify(root: Path, work: Path, proposal: str | None) -> tuple[list[str], list[str], dict, str, str, dict]:
    errors: list[str] = []
    warnings: list[str] = []
    stats = {"outcome": "PENDING", "decision2": "PENDING", "prereg_locked": False}
    text = _read(work, REPORT, errors)
    memo = _read(work, MEMO, errors)
    selected = ""
    if text:
        selected, claim, plan = _plan(root, text, proposal, errors)
        outcome = _evidence_outcome(text)
        decision = _decision2(text, errors)
        stats.update(proposal=selected, claim=claim, reported_outcome=outcome, decision2=decision)
        stats["prereg_locked"] = _lock_is_valid(work, selected, plan, errors)
        if outcome == "PENDING":
            errors.append(f"{REPORT}: verification is pending or inconclusive. Complete the evidence before decision review.")
        if decision == "ADVANCE" and outcome != "ADVANCE":
            errors.append(f"{REPORT}: Human Decision 2 cannot advance a non-ADVANCE evidence outcome.")
        before_evidence = len(errors)
        evidence = section(text, "evidence", EVIDENCE)
        audit = section(text, "audit", AUDIT)
        result = section(text, "result", RESULT)
        raw_value = _require(evidence, {
            "raw": r"原始结果路径|原始观测路径|证明或见证文件|Raw (?:Results|Observations)|Proof or Witness File",
        }, f"{REPORT} evidence", errors)["raw"]
        raw = _local_path(root, raw_value, "raw", errors)
        _require(audit, {
            "sanity": r"基线合理性核验|共同条件核验|记录质量检查|Sanity Check|Common Conditions|Record Quality",
            "artifacts": r"对比假象排查|替代解释排查|替代解释复核|Artifacts Audit|Alternative Explanations",
        }, f"{REPORT} audit", errors)
        _require(result, {
            "decision_basis": r"^依据$|Decision Basis",
            "boundary": r"可对外主张的边界|Public Claim Scope",
        }, f"{REPORT} evidence outcome", errors)
        if claim == "method":
            _method_evidence(root, text, evidence, audit, raw, outcome, errors, stats)
        elif claim == "theory":
            _require(evidence, {
                "locator": r"定位|Locator",
                "witness": r"证明与反例结果|Proof or Witness Result",
            }, f"{REPORT} worked theory evidence", errors)
        elif claim == "phenomenon":
            _phenomenon_evidence(evidence, outcome, errors, stats)
        if len(errors) == before_evidence and claim in {"method", "theory", "phenomenon"}:
            stats["outcome"] = outcome
    elif not any(REPORT in error for error in errors):
        errors.append(f"{REPORT}: empty report.")
    risks = _memo(memo, selected, errors, stats) if memo else {}
    if not memo and not any(MEMO in error for error in errors):
        errors.append(f"{MEMO}: empty memo.")
    return errors, warnings, stats, text, memo, risks


def check_gate_3(root: Path, work: Path, proposal: str | None) -> tuple[list[str], list[str], dict]:
    """Check completed evidence and memo-ready state, without requiring author approval."""
    errors, warnings, stats, _, _, _ = _verify(root, work, proposal)
    return errors, warnings, stats


def _author_response(memo: str, risks: dict[str, list[str]], errors: list[str]) -> None:
    response = section(memo, "author_response", r"作者批复记录|Author Response")
    signed = _require(response, {
        "author": r"批复作者|^Author$",
        "approval_date": r"批复日期|Approval Date",
    }, f"{MEMO} post-decision approval", errors)
    if _present(signed["approval_date"]):
        approval_date = _plain(signed["approval_date"])
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", approval_date):
                raise ValueError
            dt.date.fromisoformat(approval_date)
        except ValueError:
            errors.append(f"{MEMO}: author approval date must use YYYY-MM-DD.")
    _, rows = table(response)
    dispositions: dict[str, str] = {}
    seen: set[str] = set()
    for row in rows:
        risk = _plain(row[0])
        if len(row) != 2 or risk not in risks or risk in seen:
            errors.append(f"{MEMO}: author approval table has an unknown, duplicated or malformed risk row.")
            continue
        seen.add(risk)
        if _present(row[1]):
            dispositions[risk] = row[1]
        else:
            errors.append(f"{MEMO}: author has not recorded a disposition for {risk}.")
    if set(risks) - set(dispositions):
        errors.append(f"{MEMO}: post-decision approval needs a disposition for every recorded risk.")


def _report_anchors(report: str) -> set[tuple[str, str]]:
    evidence = section(report, "evidence", EVIDENCE)
    audit = section(report, "audit", AUDIT)
    result = section(report, "result", RESULT)
    fields = (
        ("evidence", evidence, {
            "raw": r"原始结果路径|原始观测路径|证明或见证文件|Raw (?:Results|Observations)|Proof or Witness File",
            "locator": r"定位|Locator",
            "witness": r"证明与反例结果|Proof or Witness Result",
        }),
        ("audit", audit, {
            "sanity": r"基线合理性核验|共同条件核验|记录质量检查|Sanity Check|Common Conditions|Record Quality",
            "artifacts": r"对比假象排查|替代解释排查|替代解释复核|Artifacts Audit|Alternative Explanations",
            "scaling": r"规模探针或适用边界|Scaling Probe or Scope",
            "uncertainty": r"不确定性与判定限制|Uncertainty",
        }),
        ("result", result, {
            "outcome": r"分流|Outcome|Triage",
            "decision_basis": r"^依据$|Decision Basis",
            "boundary": r"可对外主张的边界|Public Claim Scope",
        }),
    )
    verified = {
        (section_id, key)
        for section_id, body, keys in fields
        for key, label in keys.items()
        if _present(field(body, key, label))
    }
    _, rows = table(evidence)
    for row in rows:
        key = _plain(row[0])
        if re.fullmatch(r"M[0-3]|[AB]", key, re.I) and all(_present(value) for value in row[1:]):
            verified.add(("evidence", key.lower()))
        elif ABA.fullmatch(key) and all(_present(value) for value in row[1:]):
            verified.add(("evidence", re.sub(r"\s+", "-", key).lower()))
    return verified


def _handoff_map(text: str, report: str, errors: list[str], stats: dict) -> None:
    contributions = section(text, "contributions", r"凝练版|^.*贡献$|Contributions")
    items = re.findall(r"(?m)^\s*([1-9]\d*)[.)]\s+(\S[^\n]*)", contributions)
    stats["contributions"] = len(items)
    if not 2 <= len(items) <= 3:
        errors.append(f"{HANDOFF}: record two or three numbered contributions.")
    ids = {str(n) for n in range(1, len(items) + 1)}
    if {number for number, _ in items} != ids or not all(_present(value) for _, value in items):
        errors.append(f"{HANDOFF}: each numbered contribution needs a filled statement and sequential identifier.")
    if len({_plain(value).casefold() for _, value in items}) != len(items):
        errors.append(f"{HANDOFF}: contribution statements must be distinct.")
    header, rows = table(section(text, "mapping", r"总控映射表|贡献与证据映射|Contribution.*Mapping"))
    stats["mapped_rows"] = len(rows)
    verified = _report_anchors(report)
    mapped: set[str] = set()
    for row in rows:
        identifier = re.fullmatch(r"(?:C|贡献\s*)([1-9]\d*)(?:\s*[（(][^（）()]+[）)])?", _plain(row[0]))
        number = identifier[1] if identifier else ""
        if len(header) != 6 or len(row) != 6 or number not in ids or number in mapped:
            errors.append(f"{HANDOFF}: invalid or duplicated six-cell map row {row[0] or '(blank)'}.")
            continue
        mapped.add(number)
        if not all(_present(value) for value in row[1:]):
            errors.append(f"{HANDOFF}: contribution C{number} needs a complete mapping and an existing 04 evidence anchor.")
            continue
        pointers = re.findall(r"\b04(?:_mvp_verification\.md)?#([a-z]+):([\w/-]+)", row[-1].lower())
        if not pointers or any(pointer not in verified for pointer in pointers):
            errors.append(f"{HANDOFF}: contribution C{number} must point to a filled 04 field or row (for example, 04#result:boundary).")
    if len(rows) != len(items) or ids != mapped:
        errors.append(f"{HANDOFF}: add exactly one mapping row for each contribution.")


def _handoff_tasks(text: str, errors: list[str]) -> None:
    checklist = section(text, "checklist", r"写作移交|Handoff Checklist")
    expected = {
        "review": r"独立红队|Independent Review",
        "evidence": r"MVP 四组对照|Verification Evidence",
        "scope": r"术语克制|Claim Scope",
        "memo": r"全部缺陷与边界|Internal Memo",
    }
    actions: dict[str, bool] = {}
    for line in checklist.splitlines():
        item = TASK.match(line)
        if not item:
            continue
        marker = re.search(r"<!--\s*check:(review|evidence|scope|memo)\s*-->", item[2], re.I)
        key = marker[1].lower() if marker else next(
            (key for key, pattern in expected.items() if re.search(pattern, item[2], re.I)), ""
        )
        if not key or key in actions:
            errors.append(f"{HANDOFF}: duplicated or unrecognized handoff confirmation.")
        actions[key] = item[1].lower() == "x"
    for key in expected:
        if not actions.get(key):
            errors.append(f"{HANDOFF}: handoff confirmation {key} must be checked.")


def _check_no_memo_copy(text: str, name: str, private: list[str], errors: list[str]) -> None:
    exclusion = re.compile(r"严禁.*移交|不会传入|禁止进入|排除|exclude|do not (?:pass|include)", re.I)
    memo_reference = re.compile(rf"\]\([^)\n]*{re.escape(MEMO)}|!\[\[[^\]\n]*{re.escape(MEMO)}", re.I)
    unsafe_reference = memo_reference.search(text) or (
        name == HANDOFF and any(
            MEMO in line.casefold() and not exclusion.search(line) for line in text.splitlines()
        )
    )
    if unsafe_reference or re.search(r"(?m)^.+INTERNAL ONLY", text, re.I):
        errors.append(f"{name}: do not link, embed or reproduce the internal memo in a public handoff artifact.")
    corpus = re.sub(r"\s+", " ", text).casefold()
    for item in private:
        quote = re.sub(r"\s+", " ", _plain(item)).casefold()
        if (len(quote) >= 24 or len(re.findall(r"[\u3400-\u9fff]", quote)) >= 12) and quote in corpus:
            errors.append(f"{name}: private memo commentary appears verbatim in a public handoff artifact.")
            break


def check_gate_4(root: Path, work: Path, proposal: str | None) -> tuple[list[str], list[str], dict]:
    """Require passed verification, both author decisions, and a complete public handoff."""
    errors, warnings, stats, report, memo, risks = _verify(root, work, proposal)
    if stats["outcome"] != "ADVANCE" or stats["decision2"] != "ADVANCE":
        errors.append(f"{REPORT}: handoff requires an ADVANCE outcome and the author's checked ADVANCE decision.")
    num_errors = len(errors)
    if memo:
        _author_response(memo, risks, errors)
    stats["author_approved"] = bool(memo and risks and len(errors) == num_errors)
    text = _read(work, HANDOFF, errors)
    if not text:
        if not any(HANDOFF in error for error in errors):
            errors.append(f"{HANDOFF}: empty handoff.")
        return errors, warnings, stats
    if not stats.get("proposal") or _proposal(text) != stats["proposal"]:
        errors.append(f"{HANDOFF}: final proposal must match the selected report.")
    if not _claim(text) or _claim(text) != stats.get("claim"):
        errors.append(f"{HANDOFF}: claim type must match the selected report.")
    for token in ("{{TOPIC}}", "{{JOURNAL}}", "{{DATE}}"):
        if token in _metadata(text):
            errors.append(f"{HANDOFF}: unfilled metadata {token}.")
    _require(section(text, "titles", r"拟定论文题目|论文题目与主线|Paper Titles"), {
        "english_title": r"英文拟题|English Title",
        "chinese_title": r"中文拟题|Chinese Title",
        "story": r"论文主线|Paper Narrative",
    }, f"{HANDOFF} titles", errors)
    _require(section(text, "terms", r"术语|Terminology"), {
        "established_terms": r"复用.*术语|复用的行业确定化常态表述|Established Terms",
        "new_terms": r"必要的新命名|保留的有限原创命名|New Terms",
    }, f"{HANDOFF} terminology", errors)
    _handoff_map(text, report, errors, stats)
    _handoff_tasks(text, errors)
    private = [value for row in risks.values() for value in row[3:5]]
    _check_no_memo_copy(report, REPORT, private, errors)
    _check_no_memo_copy(text, HANDOFF, private, errors)
    return errors, warnings, stats
