"""Literature and independent-review gates for paper-innovation.

This module is deliberately local and dependency-free. It validates the evidence
record and proposal-by-proposal red-team record; it does not decide whether a
scientific claim is true or novel.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    from ideation_context import proposal_records
    from ideation_markdown import PID, field, has_value, placeholders, section, table
except ImportError:  # package-style import in local checks
    from .ideation_context import proposal_records
    from .ideation_markdown import PID, field, has_value, placeholders, section, table


MODES = {"full", "single", "revision", "local-pdf", "batch"}
PID_RE = re.compile(rf"(?P<pid>{PID})")
CONFLICT_RE = re.compile(r"\bC[1-9]\d*\b")
OPERATOR_RE = re.compile(r"\bO[1-6]\b")
DOI_RE = re.compile(r"(?i)(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)")
ARXIV_RE = re.compile(r"(?i)(?:arxiv\s*:\s*)(\d{4}\.\d{4,5})(?:v\d+)?|(?<![0-9./])(?P<bare>\d{4}\.\d{4,5})(?:v\d+)?")
OLD_ARXIV_RE = re.compile(r"(?i)\b([a-z.-]+/\d{7})(?:v\d+)?\b")
PII_RE = re.compile(r"(?i)\b(?:PII\s*:\s*)?([A-Z]\d{15,20})\b")
SOURCE_ID_RE = re.compile(r"(?i)(?<![A-Za-z0-9])(?:L|R|S|E)\d+[A-Za-z]?(?![A-Za-z0-9])|\[(\d{1,4})\]")
PINPOINT_RE = re.compile(
    r"(?i)(?:\bp(?:p|ages?)?\.?\s*\d+|\b(?:eq(?:uation)?|fig(?:ure)?|table|sec(?:tion)?|thm|theorem|lemma)\.?\s*\(?[\w.-]+|"
    r"第\s*\d+\s*页|公式\s*\(?[\w.-]+|图\s*\d+|表\s*\d+|定理\s*\d+)"
)
NO_HIT_RE = re.compile(r"(?i)no\s+hits?|no\s+relevant\s+results?|未检出|未命中|无命中|没有检出")
DATE_RE = re.compile(r"(?:20\d{2}[-/年]\d{1,2}(?:[-/月]\d{1,2}日?)?|20\d{2})")


def _read(root: Path, filename: str) -> tuple[str | None, str | None]:
    path = root / filename
    if not path.is_file():
        return None, f"Missing required artifact: {filename}"
    try:
        return path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeError) as exc:
        return None, f"Could not read {filename}: {exc}"


def _normal(value: str) -> str:
    value = re.sub(r"<!--.*?-->", "", value)
    value = re.sub(r"[`*_~]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _header_index(header: list[str], *patterns: str) -> int | None:
    for idx, label in enumerate(header):
        norm = _normal(label).lower()
        if any(re.search(pattern, norm, re.I) for pattern in patterns):
            return idx
    return None


def _cell(row: list[str], idx: int | None, fallback: int | None = None) -> str:
    pos = idx if idx is not None else fallback
    return row[pos].strip() if pos is not None and pos < len(row) else ""


def _table_records(text: str, key: str, heading_regex: str) -> tuple[list[str], list[list[str]]]:
    return table(section(text, key, heading_regex))


def _heading_sections(text: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    lines = text.splitlines()
    found: list[tuple[int, int, str]] = []
    for idx, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match and pattern.search(match.group(2)):
            found.append((idx, len(match.group(1)), match.group(2).strip()))
    result: list[tuple[str, str]] = []
    for start, level, title in found:
        end = len(lines)
        for idx in range(start + 1, len(lines)):
            match = re.match(r"^(#{1,6})\s+", lines[idx])
            if match and len(match.group(1)) <= level:
                end = idx
                break
        result.append((title, "\n".join(lines[start + 1 : end]).strip()))
    return result


def _proposal_sections(text: str) -> list[tuple[str, str, str]]:
    return [(pid, title, body) for pid, title, body in proposal_records(text) if pid]


def _review_sections(text: str) -> list[tuple[str, str, str]]:
    candidates = _heading_sections(text, re.compile(r"(?:review|红队审查|幸存方案|方案)", re.I))
    result: list[tuple[str, str, str]] = []
    for title, body in candidates:
        match = PID_RE.search(title)
        if match and not re.match(r"[A-Za-z0-9_.-]", title[match.end() : match.end() + 1]):
            result.append((match.group("pid"), title, body))
    return result


def _exact_id_match(text: str, proposal_id: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(proposal_id)}(?![A-Za-z0-9_.-])", text))


def _field(text: str, key: str, labels: tuple[str, ...] = ()) -> str:
    for label in labels or (r"$a",):
        value = field(text, key, label)
        if has_value(value):
            return value.strip()
    return ""


def _field_any(text: str, keys: tuple[str, ...], labels: tuple[str, ...] = ()) -> str:
    for key in keys:
        value = _field(text, key, labels)
        if has_value(value):
            return value
    return ""


def _claim_kind(value: str) -> str:
    normalized = _normal(value).lower()
    if re.search(r"\bmethod\b|方法|算法|模型改进", normalized):
        return "method"
    if re.search(r"\btheory\b|theorem|理论|定理|命题|边界刻画", normalized):
        return "theory"
    if re.search(r"\bphenomenon\b|现象|机理解释|经验规律", normalized):
        return "phenomenon"
    return "unknown"


def _proposal_claim(proposal_text: str) -> str:
    explicit = _field_any(
        proposal_text,
        ("claim", "claim_type"),
        (r"claim\s*type|主张类型|研究主张类别",),
    )
    if explicit:
        return _claim_kind(explicit)
    # Legacy completed method proposals expose M1 and a naive-adaptation field.
    old_m1 = _field_any(proposal_text, ("m1",), (r"最强现有\s*SOTA|\bM1\b",))
    old_m2 = _field_any(
        proposal_text,
        ("m2", "naive_adaptation"),
        (r"强朴素适配|naive\s+adaptation|强朴素基线",),
    )
    if old_m1 and old_m2:
        return "method"
    return "unknown"


def proposal_claims(root: Path) -> dict[str, str]:
    """Return proposal ID -> claim family (`method`, `theory`, `phenomenon`)."""
    text, _ = _read(root, "02_candidate_proposals.md")
    if text is None:
        return {}
    return {pid: _proposal_claim(body) for pid, _, body in _proposal_sections(text)}


def _row_dict(header: list[str], row: list[str]) -> dict[str, str]:
    return {_normal(label).lower(): row[idx].strip() if idx < len(row) else "" for idx, label in enumerate(header)}


def _get_by_header(record: dict[str, str], patterns: tuple[str, ...]) -> str:
    if isinstance(patterns, str):
        patterns = (patterns,)
    for label, value in record.items():
        if any(re.search(pattern, label, re.I) for pattern in patterns):
            return value
    return ""


def _source_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in SOURCE_ID_RE.finditer(text):
        token = match.group(0)
        numeric = match.group(1)
        tokens.add(numeric if numeric else token.upper())
    return tokens


def _stable_locator(value: str) -> set[str]:
    locators: set[str] = set()
    doi_matches = list(DOI_RE.finditer(value))
    for match in doi_matches:
        doi = match.group(1).rstrip(".,;:")
        while doi.endswith(")") and doi.count(")") > doi.count("("):
            doi = doi[:-1]
        doi = doi.rstrip("]}").lower()
        locators.add("doi:" + doi)
    arxiv_text = value
    for match in reversed(doi_matches):
        arxiv_text = arxiv_text[: match.start()] + (" " * (match.end() - match.start())) + arxiv_text[match.end() :]
    for match in ARXIV_RE.finditer(arxiv_text):
        locators.add("arxiv:" + (match.group(1) or match.group("bare")).lower())
    for match in OLD_ARXIV_RE.finditer(value):
        locators.add("arxiv-old:" + match.group(1).lower())
    for match in PII_RE.finditer(value):
        locators.add("pii:" + match.group(1).lower())
    return locators


def _local_file(root: Path, value: str, any_extension: bool = False) -> tuple[str | None, bool]:
    """Return an existing local paper path, allowing quoted paths outside root."""
    cleaned = value.strip().strip("\"'").strip("`").strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1].strip()
    cleaned = re.sub(r"^(?:path|file|本地路径)\s*[:：]\s*", "", cleaned, flags=re.I)
    suffix_pattern = r"[A-Za-z0-9]+" if any_extension else r"(?:pdf|txt|md)"
    candidates = [cleaned] if re.search(rf"\.{suffix_pattern}$", cleaned, re.I) else []
    if not candidates:
        candidates = re.findall(
            rf"(?i)(?:[A-Za-z]:[\\/]|\.{1,2}[\\/]|[^\s<>|]+[\\/])[^<>|]*?\.{suffix_pattern}(?=$|[\s,)])",
            value,
        )
    for candidate in candidates:
        candidate = candidate.strip().strip("\"'`*_[]{}.,;:")
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            path = root / path
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved.is_file():
            return str(resolved).lower(), True
        return str(resolved).lower(), False
    return None, False


def _paper_identifier(record: dict[str, str], row: list[str], root: Path) -> tuple[str | None, bool, set[str]]:
    locator = _get_by_header(record, (r"canonical\s*locator", r"doi", r"arxiv", r"pii", r"溯源标识", r"source\s*locator"))
    local = _get_by_header(record, (r"local.*(?:path|file)|本地.*(?:路径|文件)"))
    all_locator_text = " ".join((locator, local))
    locators = _stable_locator(all_locator_text)
    if not locators and locator:
        locator_path, locator_path_exists = _local_file(root, locator)
        if locator_path:
            if locator_path_exists:
                locators.add("file:" + locator_path)
            else:
                return None, False, set()
    if locators:
        local_name, local_ok = _local_file(root, local)
        if local_name:
            if local_ok:
                locators.add("file:" + local_name)
        return sorted(locators)[0], (local_ok if local_name else True), locators
    local_name, local_ok = _local_file(root, all_locator_text)
    if local_name:
        locators.add("file:" + local_name)
        return "file:" + local_name, local_ok, locators
    return None, False, set()


def _depth_value(record: dict[str, str], row: list[str]) -> str:
    value = _get_by_header(record, (r"depth|reading\s*depth|阅读深度"))
    if not value:
        value = " ".join(row)
    normalized = value.lower().replace("–", "-").replace("—", "-")
    if re.search(r"\bfull[\s-]?text\b|全文", normalized):
        return "full-text"
    if re.search(r"\babstract[\s-]?only\b|仅摘要|摘要", normalized):
        return "abstract-only"
    return ""


def _paper_refs(record: dict[str, str], row: list[str]) -> set[str]:
    sources = _get_by_header(record, (r"evidence\s*source\s*ids?|source\s*ids?|证据来源编号|来源编号"))
    if not sources:
        sources = _get_by_header(record, (r"work\s*id|paper\s*id|编号|文献编号"))
    if not sources and row:
        sources = row[0]
    return _source_tokens(sources)


def _literature_table(root: Path, text: str | None = None) -> tuple[list[str], list[list[str]]]:
    if text is None:
        text, _ = _read(root, "01_assumption_failure_matrix.md")
    if text is None:
        return [], []
    return _table_records(text, "literature_table", r"literature|vertical|文献矩阵|文献register")


def registered_source_ids(root: Path) -> set[str]:
    """Return only source IDs backed by rows in the 01 literature register."""
    header, rows = _literature_table(root)
    return set().union(*(_paper_refs(_row_dict(header, row), row) for row in rows)) if rows else set()


def callable_source_ids(root: Path, text: str | None = None) -> set[str]:
    """Return L IDs with a real locator, full-text depth, and per-source pinpoint.

    `text` may supply a batch 00 literature register using the same table anchor.
    This function checks registry metadata and local-path existence only; it never
    opens or reads paper contents.
    """
    header, rows = _literature_table(root, text)
    callable_ids: set[str] = set()
    for row in rows:
        record = _row_dict(header, row)
        identifier, local_exists, _ = _paper_identifier(record, row, root)
        depth = _depth_value(record, row)
        refs = _paper_refs(record, row)
        pinpoints = _get_by_header(record, (r"pinpoints?|pinpoint\s*\(s\)|页码|原文位置",))
        pinpoint_ok = _valid_pinpoints(pinpoints, refs)[0]
        if len(refs) == 1 and PINPOINT_RE.search(pinpoints):
            # A single source ID on this table row scopes its unprefixed pinpoint.
            pinpoint_ok = True
        if not identifier or depth != "full-text" or not pinpoint_ok:
            continue
        callable_ids.update(ref for ref in refs if re.fullmatch(r"L[1-9]\d*", ref))
    return callable_ids


def _valid_pinpoints(pinpoints: str, source_ids: set[str]) -> tuple[bool, set[str]]:
    pinpoint_sources = _source_tokens(pinpoints)
    if not source_ids:
        return bool(PINPOINT_RE.search(pinpoints)), pinpoint_sources
    valid_sources: set[str] = set()
    for source_id in source_ids:
        match = re.search(rf"(?<![A-Za-z0-9]){re.escape(source_id)}(?![A-Za-z0-9])", pinpoints, re.I)
        if not match:
            continue
        tail = pinpoints[match.end() :]
        next_source = re.search(r"(?:\b(?:L|R|S|E)\d+[A-Za-z]?\b|\[\d+\])", tail, re.I)
        entry = tail[: next_source.start()] if next_source else tail.split(";", 1)[0].split("；", 1)[0]
        if PINPOINT_RE.search(entry):
            valid_sources.add(source_id)
    return source_ids.issubset(valid_sources), pinpoint_sources


def _status(value: str) -> str:
    normalized = _normal(value).lower()
    if re.search(r"\breported\b|原文已报告", normalized):
        return "reported"
    if re.search(r"\breproduced\b|自己已复现", normalized):
        return "reproduced"
    if re.search(r"\bpending\b|待检验", normalized):
        return "pending"
    return ""


def _scope(value: str) -> str:
    normalized = _normal(value).lower()
    if re.search(r"recurr|repeated|cross[- ]paper|跨多篇|共现|反复", normalized):
        return "recurring"
    if re.search(r"original[- ]theory|original|原始|原著|经典理论", normalized):
        return "original-theory"
    if re.search(r"hypothesis|假设|待检验", normalized):
        return "hypothesis"
    return ""


class _DisjointSet:
    def __init__(self, count: int) -> None:
        self.parent = list(range(count))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[b] = a


def _conflict_sections(text: str) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    for title, body in _heading_sections(text, re.compile(r"(?:conflict|矛盾)", re.I)):
        match = CONFLICT_RE.search(title)
        if match:
            result.append((match.group(0).upper(), title, body))
    return result


def _conflict_ids_from_value(value: str) -> set[str]:
    return {match.group(0).upper() for match in CONFLICT_RE.finditer(value)}


def _check_conflicts(
    text_01: str,
    root: Path,
    full_text_work_ids: set[str],
    source_to_work: dict[str, str],
    paper_ids: set[str],
    errors: list[str],
    warnings: list[str],
) -> list[str]:
    conflicts = _conflict_sections(text_01)
    ids = [cid for cid, _, _ in conflicts]
    duplicates = sorted({cid for cid in ids if ids.count(cid) > 1})
    if duplicates:
        errors.append(f"01_assumption_failure_matrix.md: duplicate conflict ID(s): {duplicates}.")
    if not conflicts:
        errors.append("01_assumption_failure_matrix.md: add at least one evidence-backed conflict or hypothesis section.")
        return []

    for conflict_id, _, body in conflicts:
        scope = _field_any(body, ("claim_scope", "scope"), (r"claim\s*scope|evidence\s*scope|主张范围|证据范围",))
        # `pending` is a valid evidence-state enum even though generic placeholder
        # detection treats that word as an unfinished free-text value.
        status_value = field(body, "evidence_status", r"evidence\s*status|证据状态")
        status = _status(status_value)
        refs = _source_tokens(_field_any(body, ("evidence_sources", "source_ids"), (r"evidence\s*source|source\s*ids?|受影响代表文献|证据来源",)))
        pinpoints = _field_any(body, ("pinpoints", "pinpoint"), (r"pinpoint|页码|公式图表位置|原文位置",))
        observation = _field_any(body, ("observation", "observed_result"), (r"observation|observed|原文观察|观测结果",))
        falsifier = _field_any(body, ("falsifier",), (r"falsifier|证伪|推翻条件",))
        result_artifact = _field_any(body, ("result_artifact", "artifact"), (r"result\s*artifact|result\s*file|复现结果文件|结果产物",))
        has_status_marker = bool(re.search(r"<!--\s*field:evidence_status\s*-->", body, re.I))
        has_scope_marker = bool(re.search(r"<!--\s*field:claim_scope\s*-->", body, re.I))
        if not scope and has_scope_marker:
            errors.append(f"01_assumption_failure_matrix.md: {conflict_id} must declare scope as recurring, original-theory, or hypothesis.")
        if not status:
            if has_status_marker:
                errors.append(f"01_assumption_failure_matrix.md: {conflict_id} must declare evidence status as reported, reproduced, or pending.")
            elif refs and _valid_pinpoints(pinpoints, refs)[0]:
                # Legacy formats can establish reported evidence only with actual pinpoint locations.
                status = "reported"
            else:
                errors.append(f"01_assumption_failure_matrix.md: {conflict_id} needs an explicit evidence status or legacy pinpoint evidence.")
        normalized_scope = _scope(scope)
        if not normalized_scope and not has_scope_marker:
            # Legacy entries without scope are treated as single-source claims unless
            # three distinct cited works actually appear; no date cutoff is applied.
            works = {source_to_work[ref] for ref in refs if ref in source_to_work}
            normalized_scope = "recurring" if len(works) >= 3 else "original-theory"
        elif not normalized_scope:
            errors.append(f"01_assumption_failure_matrix.md: {conflict_id} has an unrecognized scope.")
        if not refs:
            errors.append(f"01_assumption_failure_matrix.md: {conflict_id} has no cited evidence source ID.")
        unknown = sorted(ref for ref in refs if ref not in paper_ids)
        if unknown:
            errors.append(f"01_assumption_failure_matrix.md: {conflict_id} cites unknown source ID(s) {unknown}.")
        if status == "reported":
            if not refs:
                errors.append(f"01_assumption_failure_matrix.md: reported {conflict_id} needs cited source IDs.")
            ok, _ = _valid_pinpoints(pinpoints, refs)
            if refs and not ok:
                errors.append(f"01_assumption_failure_matrix.md: reported {conflict_id} needs a page/equation/figure/table pinpoint for each cited work.")
        elif status == "reproduced":
            if not observation:
                errors.append(f"01_assumption_failure_matrix.md: reproduced {conflict_id} needs the observed result.")
            path, exists = _local_file(root, result_artifact, any_extension=True)
            if not result_artifact or not path or not exists:
                errors.append(f"01_assumption_failure_matrix.md: reproduced {conflict_id} needs an existing result artifact path.")
        elif status == "pending":
            if not observation:
                errors.append(f"01_assumption_failure_matrix.md: pending {conflict_id} needs the observation to collect.")
            if not falsifier:
                errors.append(f"01_assumption_failure_matrix.md: pending {conflict_id} needs a stated falsifier.")
        is_recurring = normalized_scope == "recurring"
        if is_recurring and status != "pending":
            distinct_full = {source_to_work[ref] for ref in refs if ref in source_to_work and source_to_work[ref] in full_text_work_ids}
            if len(distinct_full) < 3:
                errors.append(
                    f"01_assumption_failure_matrix.md: recurring {conflict_id} needs 3 distinct cited full-text sources; found {len(distinct_full)}."
                )
            if refs and not _valid_pinpoints(pinpoints, refs)[0]:
                errors.append(f"01_assumption_failure_matrix.md: recurring {conflict_id} needs a pinpoint for every cited source ID.")
    return ids


def _check_proposal_fields(
    pid: str,
    body: str,
    claim: str,
    defined_conflicts: set[str],
    paper_ids: set[str],
    full_text_source_ids: set[str],
    source_to_work: dict[str, str],
    full_text_work_ids: set[str],
    full_text_locators: set[str],
    errors: list[str],
) -> set[str]:
    claim_value = _field_any(body, ("claim_statement", "claim_text"), (r"research\s*claim|falsifiable\s*claim|研究主张|可证伪主张",))
    if not claim_value:
        errors.append(f"Proposal {pid}: write one concrete, falsifiable research claim.")

    conflict_value = _field_any(body, ("conflict_ids", "conflicts"), (r"conflict\s*ids?|结构性矛盾编号|瞄准的结构性矛盾",))
    cited_conflicts = _conflict_ids_from_value(conflict_value)
    if not cited_conflicts:
        errors.append(f"Proposal {pid}: cite C IDs in the dedicated conflict-ID field.")
    elif defined_conflicts and cited_conflicts - defined_conflicts:
        errors.append(f"Proposal {pid}: references undefined conflict ID(s) {sorted(cited_conflicts - defined_conflicts)}.")

    operator_value = _field_any(body, ("operators", "operator"), (r"construction\s*operators?|构造算子|采用构造算子",))
    operators = {m.group(0).upper() for m in OPERATOR_RE.finditer(operator_value)} if claim == "method" else set()
    if claim == "method" and not operators:
        errors.append(f"Proposal {pid} (method): list O1–O6 only in the dedicated operators field.")

    if claim == "method":
        m1 = _field_any(body, ("m1",), (r"\bM1\b|strongest\s*(?:existing\s*)?SOTA|最强现有",))
        m2 = _field_any(body, ("m2", "naive_adaptation"), (r"\bM2\b|naive\s*adaptation|强朴素适配|强朴素基线",))
        prediction = _field_any(body, ("prediction",), (r"discriminating\s*prediction|区分性预测|可区分预测",))
        falsifier = _field_any(body, ("falsifier",), (r"falsif|证伪|直接证伪条件",))
        ablation = _field_any(body, ("ablation",), (r"ablation|消融变体",))
        ablation_outcome = _field_any(body, ("ablation_outcome",), (r"预期退化|ablation.*outcome|消融.*指标",))
        if not m1:
            errors.append(f"Proposal {pid} (method): identify M1 with a matrix source ID or stable locator and pinpoint.")
        else:
            m1_refs = _source_tokens(m1)
            m1_locators = _stable_locator(m1)
            m1_full_text = bool(m1_refs & full_text_source_ids) or any(
                source_to_work.get(ref) in full_text_work_ids for ref in m1_refs
            )
            if not (m1_full_text or m1_locators & full_text_locators):
                errors.append(f"Proposal {pid} (method): M1 must cite a known full-text work in the literature matrix.")
            if not PINPOINT_RE.search(m1):
                errors.append(f"Proposal {pid} (method): give M1 a page, equation, figure, table, or theorem pinpoint.")
        if not m2:
            errors.append(f"Proposal {pid} (method): define the strong naive M2 baseline and its matched information/constraint/budget.")
        if not prediction:
            errors.append(f"Proposal {pid} (method): state a discriminating prediction with an observable metric or condition.")
        if not falsifier:
            errors.append(f"Proposal {pid} (method): state a genuine falsifier tied to an observable result and condition.")
        if not ablation:
            errors.append(f"Proposal {pid} (method): name at least one explicit w/o ablation.")
        if not ablation_outcome:
            errors.append(f"Proposal {pid} (method): predict the concrete ablation outcome or metric that should worsen.")
    elif claim == "theory":
        implication = _field_any(body, ("implication", "implication_test"), (r"implication|logical\s*relation|推论关系|蕴含|推出关系",))
        witness = _field_any(body, ("witness", "counterexample_witness"), (r"witness|counterexample|见证点|反例见证",))
        if not implication:
            errors.append(f"Proposal {pid} (theory): state the implication test against the closest prior result.")
        if not witness:
            errors.append(f"Proposal {pid} (theory): provide a witness/counterexample field for any strict-boundary claim.")
    elif claim == "phenomenon":
        data = _field_any(body, ("data_observation", "data"), (r"data\s*(?:source|observation)|可用数据|观测数据",))
        rival_a = _field_any(body, ("rival_explanation_a", "explanation_a"), (r"rival\s*explanation\s*A|解释\s*A",))
        rival_b = _field_any(body, ("rival_explanation_b", "explanation_b"), (r"rival\s*explanation\s*B|解释\s*B",))
        if not (rival_a and rival_b):
            errors.append(f"Proposal {pid} (phenomenon): give at least two rival explanations.")
        pred_a = _field_any(body, ("prediction_a", "rival_prediction_a"), (r"prediction\s*A|预测\s*A",))
        pred_b = _field_any(body, ("prediction_b", "rival_prediction_b"), (r"prediction\s*B|预测\s*B",))
        if not (pred_a and pred_b):
            errors.append(f"Proposal {pid} (phenomenon): state different predictions that separate the rivals.")
        if not data:
            errors.append(f"Proposal {pid} (phenomenon): identify the data/observation needed to distinguish the explanations.")
    else:
        errors.append(f"Proposal {pid}: claim type must be method, theory, or phenomenon.")
    return operators


def check_gate_1(root: Path, min_papers: int, mode: str) -> tuple[list[str], list[str], dict[str, Any]]:
    """Validate literature provenance, conflict evidence, and proposal-specific gates."""
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {"mode": mode, "handoff_ready": False}
    if mode not in MODES:
        return [f"Unsupported mode {mode!r}; expected one of {sorted(MODES)}."], warnings, stats

    t1, error = _read(root, "01_assumption_failure_matrix.md")
    if error:
        errors.append(error)
    if t1 is None:
        return errors, warnings, stats
    remaining = placeholders(t1)
    if remaining:
        sample = ", ".join(f"L{line}:{token}" for line, token in remaining[:5])
        errors.append(f"01_assumption_failure_matrix.md: {len(remaining)} unfilled placeholder(s): {sample}.")

    header, rows = _table_records(t1, "literature_table", r"literature|纵向|文献.*矩阵|文献.*register")
    stats["literature_rows"] = len(rows)
    min_required = max(1, min_papers)
    if len(rows) < min_required:
        errors.append(f"01_assumption_failure_matrix.md: has {len(rows)} literature row(s); {mode} mode requires at least {min_required}.")
    if mode == "full" and len(rows) < 15:
        warnings.append(f"Full exploration has {len(rows)} row(s); the target literature survey is commonly 15–30 works.")

    duplicate_rows: dict[str, int] = {}
    seen_locators: dict[str, int] = {}
    locator_owner: dict[str, int] = {}
    row_key_owner: dict[str, int] = {}
    disjoint = _DisjointSet(len(rows))
    row_data: list[dict[str, Any]] = []
    paper_ids: set[str] = set()
    source_owner: dict[str, int] = {}
    missing_provenance = 0
    missing_depth = 0
    missing_evidence_ids = 0
    for idx, row in enumerate(rows, 1):
        record = _row_dict(header, row)
        row_key = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", _normal(" ".join(row)).lower())
        duplicate_rows[row_key] = duplicate_rows.get(row_key, 0) + 1
        if row_key in row_key_owner:
            disjoint.union(idx - 1, row_key_owner[row_key])
        else:
            row_key_owner[row_key] = idx - 1
        identifier, local_exists, locator_set = _paper_identifier(record, row, root)
        local_cell = _get_by_header(record, r"local.*(?:path|file)|本地.*(?:路径|文件)")
        local_path, local_path_exists = _local_file(root, local_cell) if local_cell else (None, True)
        if not identifier:
            missing_provenance += 1
            errors.append(f"01_assumption_failure_matrix.md: row {idx} is missing a DOI/arXiv/PII or an existing local paper path.")
        if local_cell and (not local_path or not local_path_exists):
            errors.append(f"01_assumption_failure_matrix.md: row {idx} names a local source path that does not exist as a file.")
        for locator in locator_set:
            if locator in seen_locators:
                errors.append(f"01_assumption_failure_matrix.md: duplicate canonical locator in rows {seen_locators[locator]} and {idx}: {locator}.")
                disjoint.union(idx - 1, seen_locators[locator] - 1)
            else:
                seen_locators[locator] = idx
            if locator in locator_owner:
                disjoint.union(idx - 1, locator_owner[locator])
            else:
                locator_owner[locator] = idx - 1

        refs = _paper_refs(record, row)
        if not refs:
            missing_evidence_ids += 1
            errors.append(f"01_assumption_failure_matrix.md: row {idx} is missing its evidence source ID (for example L1).")
        duplicate_ids = sorted(ref for ref in refs if ref in source_owner)
        if duplicate_ids:
            errors.append(f"01_assumption_failure_matrix.md: source ID(s) reused by another literature row: {duplicate_ids}.")
        paper_ids.update(refs)
        for ref in refs:
            source_owner.setdefault(ref, idx - 1)

        depth = _depth_value(record, row)
        if not depth:
            missing_depth += 1
            errors.append(f"01_assumption_failure_matrix.md: row {idx} needs a full-text or abstract-only read-depth tag.")
        row_data.append({
            "refs": refs,
            "depth": depth,
            "locators": locator_set,
            "local_pdf": bool(local_path_exists and local_path and local_path.lower().endswith(".pdf")),
        })

    duplicate_row_indexes = [count for count in duplicate_rows.values() if count > 1]
    if duplicate_row_indexes:
        errors.append(f"01_assumption_failure_matrix.md: found {sum(n - 1 for n in duplicate_row_indexes)} duplicate literature row(s).")
    source_to_work: dict[str, str] = {}
    full_text_work_ids: set[str] = set()
    full_text_source_ids: set[str] = set()
    full_text_locators: set[str] = set()
    abstract_work_ids: set[str] = set()
    local_pdf_work_ids: set[str] = set()
    unique_work_ids: set[str] = set()
    for idx, info in enumerate(row_data):
        work_id = f"work:{disjoint.find(idx)}"
        unique_work_ids.add(work_id)
        for ref in info["refs"]:
            source_to_work.setdefault(ref, work_id)
        if info["depth"] == "full-text":
            full_text_work_ids.add(work_id)
            full_text_source_ids.update(info["refs"])
            full_text_locators.update(info["locators"])
        elif info["depth"] == "abstract-only":
            abstract_work_ids.add(work_id)
        if info["local_pdf"]:
            local_pdf_work_ids.add(work_id)
    abstract_work_ids -= full_text_work_ids
    stats.update({
        "unique_papers": len(unique_work_ids),
        "full_text_papers": len(full_text_work_ids),
        "abstract_only_papers": len(abstract_work_ids),
        "missing_provenance": missing_provenance,
        "missing_read_depth": missing_depth,
        "missing_evidence_source_ids": missing_evidence_ids,
        "local_pdf_sources": len(local_pdf_work_ids),
    })
    if abstract_work_ids and len(abstract_work_ids) > max(1, len(unique_work_ids) // 2):
        warnings.append("More than half of the literature rows are abstract-only; anchor core claims in full texts.")
    if mode == "local-pdf" and not local_pdf_work_ids:
        errors.append("local-pdf mode requires at least one existing local PDF in the literature register.")

    conflict_ids = _check_conflicts(t1, root, full_text_work_ids, source_to_work, paper_ids, errors, warnings)
    stats["conflicts"] = len(conflict_ids)
    conflict_set = set(conflict_ids)
    required_conflicts = 1
    if len(conflict_set) < required_conflicts:
        errors.append(f"01_assumption_failure_matrix.md: {mode} mode needs at least {required_conflicts} distinct conflict/hypothesis section(s).")

    t2, error = _read(root, "02_candidate_proposals.md")
    if error:
        errors.append(error)
        return errors, warnings, stats
    assert t2 is not None
    proposal_ph = placeholders(t2)
    if proposal_ph:
        sample = ", ".join(f"L{line}:{token}" for line, token in proposal_ph[:5])
        errors.append(f"02_candidate_proposals.md: {len(proposal_ph)} unfilled placeholder(s): {sample}.")
    records = proposal_records(t2)
    proposals = [(pid, title, body) for pid, title, body in records if pid]
    invalid_headings = [title for pid, title, _ in records if not pid]
    if invalid_headings:
        errors.append(f"02_candidate_proposals.md: malformed proposal ID(s) in heading(s): {invalid_headings}.")
    ids = [pid for pid, _, _ in proposals]
    duplicates = sorted({pid for pid in ids if ids.count(pid) > 1})
    if duplicates:
        errors.append(f"02_candidate_proposals.md: duplicate proposal ID(s): {duplicates}.")
    min_candidates = 2 if mode == "full" else 1
    if len(proposals) < min_candidates:
        errors.append(f"02_candidate_proposals.md: {mode} mode requires at least {min_candidates} candidate proposal(s); found {len(proposals)}.")
    stats["proposals"] = len(proposals)
    operator_sets: list[set[str]] = []
    has_method = False
    claims: dict[str, str] = {}
    for pid, _, body in proposals:
        claim = _proposal_claim(body)
        claims[pid] = claim
        operators = _check_proposal_fields(
            pid, body, claim, conflict_set, paper_ids, full_text_source_ids, source_to_work,
            full_text_work_ids, full_text_locators, errors
        )
        if claim == "method":
            has_method = True
            if operators:
                operator_sets.append(operators)
    if mode == "full" and has_method:
        _, tool_rows = _table_records(t1, "cross_domain_table", r"cross.domain|横向|工具检索")
        stats["cross_domain_tools"] = len(tool_rows)
        if len(tool_rows) < 2:
            errors.append("Full method exploration needs at least two cross-domain tool records.")
    else:
        _, tool_rows = _table_records(t1, "cross_domain_table", r"cross.domain|横向|工具检索")
        stats["cross_domain_tools"] = len(tool_rows)
    if mode == "full" and len(operator_sets) >= 2 and len(set(map(frozenset, operator_sets))) == 1:
        errors.append("Full exploration needs meaningfully diverse operator sets across at least two proposals.")
    stats["proposal_claims"] = claims
    stats["operator_sets"] = {pid: sorted(_operators_for(body)) for pid, _, body in proposals if claims.get(pid) == "method"}
    return errors, warnings, stats


def _operators_for(body: str) -> set[str]:
    value = _field_any(body, ("operators", "operator"), (r"construction\s*operators?|构造算子|采用构造算子",))
    return {match.group(0).upper() for match in OPERATOR_RE.finditer(value)}


def _verdict_table(root: Path) -> tuple[str | None, list[str], list[list[str]]]:
    text, error = _read(root, "03_redteam_verdict.md")
    if text is None:
        return None, [], []
    header, rows = _table_records(text, "verdict_table", r"summary\s*verdict|总览裁决表")
    return text, header, rows


def _table_pid(header: list[str], row: list[str]) -> str | None:
    idx = _header_index(header, r"proposal\s*(?:id|number)?|方案(?:编号)?|候选编号")
    value = _cell(row, idx, 0)
    token = value.strip().strip("`*_ ")
    match = PID_RE.fullmatch(token)
    return match.group("pid") if match else None


def _table_verdict(header: list[str], row: list[str]) -> str | None:
    idx = _header_index(header, r"final\s*verdict|verdict|裁决|最终判断")
    value = _cell(row, idx, 5 if len(row) >= 6 else None)
    token = _normal(value).strip("`*_ ").upper()
    return token if token in {"PASS", "REVISE", "KILL", "DEFER"} else None


def verdicts(root: Path) -> dict[str, str]:
    """Return proposal ID -> red-team verdict from the 03 summary table."""
    _, header, rows = _verdict_table(root)
    result: dict[str, str] = {}
    for row in rows:
        pid = _table_pid(header, row)
        decision = _table_verdict(header, row)
        if pid and decision:
            result[pid] = decision
    return result


def _approved_from_explicit(text: str) -> tuple[set[str], bool, bool]:
    raw = field(text, "selected", r"author\s*approved|selected\s*proposal|作者批准进入验证|批准进入验证的方案")
    if not has_value(raw):
        return set(), False, True
    if re.search(r"(?i)退回|revise|回到阶段|no\s+advance|暂不|不进入", raw):
        return set(), True, True
    selected, valid = _parse_id_list(raw)
    return selected, True, valid


def _parse_id_list(raw: str) -> tuple[set[str], bool]:
    cleaned = re.sub(r"\s+", " ", raw).strip().strip("`*_ ")
    if not cleaned or re.search(r"(?i)退回|revise|回到阶段|no\s+advance|暂不|不进入", cleaned):
        return set(), True
    tokens = [token for token in re.split(r"\s*(?:[,;，；+&、/]|\band\b|和)\s*|\s+", cleaned) if token]
    if not tokens:
        return set(), False
    ids: set[str] = set()
    valid = True
    parsed: list[str] = []
    for token in tokens:
        token = token.strip("`*_()[]{} ")
        match = PID_RE.fullmatch(token)
        if match:
            ids.add(match.group("pid"))
            parsed.append(match.group("pid"))
        else:
            valid = False
    if len(parsed) != len(ids):
        valid = False
    return ids, valid


def _approved_from_legacy(text: str) -> tuple[set[str], bool, bool]:
    approved: set[str] = set()
    saw_decision = False
    valid_all = True
    for line in text.splitlines():
        if not re.search(r"^\s*[-*+]\s*\[x\]", line, re.I):
            continue
        option = re.search(r"(?:选项|option)\s*([ABC])\s*[:：]?", line, re.I)
        if not option:
            continue
        saw_decision = True
        if option.group(1).upper() == "C":
            continue
        tail = line[option.end() :]
        tokens = re.findall(r"(?<![A-Za-z0-9])P[1-9]\d*(?:[-_.][A-Za-z0-9]+|[a-z])*(?![A-Za-z0-9])", tail)
        ids: set[str] = set()
        valid = bool(tokens)
        for token in tokens:
            match = PID_RE.fullmatch(token)
            if match:
                ids.add(match.group("pid"))
            else:
                valid = False
        if valid:
            approved.update(ids)
        else:
            valid_all = False
    return approved, saw_decision, valid_all


def _author_selection(text: str) -> tuple[set[str], bool, bool]:
    explicit, has_decision, valid = _approved_from_explicit(text)
    if has_decision:
        return explicit, has_decision, valid
    return _approved_from_legacy(text)


def approved_proposals(root: Path) -> set[str]:
    """Return IDs explicitly selected by the author; blank templates select none."""
    text, _ = _read(root, "03_redteam_verdict.md")
    if text is None:
        return set()
    explicit, has_decision, _ = _approved_from_explicit(text)
    if has_decision:
        return explicit
    legacy, _, _ = _approved_from_legacy(text)
    return legacy


def _review_field(body: str, keys: tuple[str, ...], labels: tuple[str, ...]) -> str:
    return _field_any(body, keys, labels)


def _substantive(value: str) -> bool:
    return has_value(value)


def _candidate_files(root: Path, errors: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    text, error = _read(root, "02_candidate_proposals.md")
    if error:
        errors.append(error)
        return {}, {}
    assert text is not None
    sections = _proposal_sections(text)
    ids = [pid for pid, _, _ in sections]
    duplicates = sorted({pid for pid in ids if ids.count(pid) > 1})
    if duplicates:
        errors.append(f"02_candidate_proposals.md: duplicate proposal ID(s): {duplicates}.")
    return ({pid: body for pid, _, body in sections}, {pid: _proposal_claim(body) for pid, _, body in sections})


def _review_match_body(reviews: list[tuple[str, str, str]], proposal_id: str) -> str | None:
    matches = [body for pid, title, body in reviews if pid == proposal_id and _exact_id_match(title, proposal_id)]
    return matches[0] if len(matches) == 1 else None


def _header_reason(header: list[str], row: list[str]) -> str:
    idx = _header_index(header, r"reason|rationale|理由|简述")
    return _cell(row, idx)


def check_gate_2(root: Path, mode: str) -> tuple[list[str], list[str], dict[str, Any]]:
    """Validate one exact verdict and independent evidence dossier per candidate."""
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {"mode": mode, "handoff_ready": False}
    if mode not in MODES:
        return [f"Unsupported mode {mode!r}; expected one of {sorted(MODES)}."], warnings, stats

    t3, header, rows = _verdict_table(root)
    if t3 is None:
        errors.append("Missing required artifact: 03_redteam_verdict.md")
        return errors, warnings, stats
    remaining = placeholders(t3)
    if remaining:
        sample = ", ".join(f"L{line}:{token}" for line, token in remaining[:5])
        errors.append(f"03_redteam_verdict.md: {len(remaining)} unfilled placeholder(s): {sample}.")

    candidates, claims = _candidate_files(root, errors)
    expected = set(candidates)
    stats["candidate_ids"] = sorted(expected)
    stats["verdict_rows"] = len(rows)
    if not rows:
        errors.append("03_redteam_verdict.md: verdict table is empty; every proposal needs an explicit verdict row.")
    row_ids: list[str] = []
    decisions: dict[str, str] = {}
    row_reasons: dict[str, str] = {}
    for row_num, row in enumerate(rows, 1):
        pid = _table_pid(header, row)
        decision = _table_verdict(header, row)
        if not pid:
            errors.append(f"03_redteam_verdict.md: verdict row {row_num} has no exact proposal ID.")
            continue
        row_ids.append(pid)
        if pid not in expected:
            errors.append(f"03_redteam_verdict.md: verdict row references unknown proposal {pid}.")
        if not decision:
            errors.append(f"03_redteam_verdict.md: proposal {pid} needs one verdict: PASS, REVISE, KILL, or DEFER.")
        else:
            decisions[pid] = decision
        row_reasons[pid] = _header_reason(header, row)
    duplicates = sorted({pid for pid in row_ids if row_ids.count(pid) > 1})
    if duplicates:
        errors.append(f"03_redteam_verdict.md: duplicate verdict row(s) for {duplicates}.")
    for missing in sorted(expected - set(row_ids)):
        errors.append(f"03_redteam_verdict.md: missing exact verdict row for proposal {missing}.")
    for extra in sorted(set(row_ids) - expected):
        # Already reported above, kept separate from omitted proposal checks.
        stats.setdefault("unknown_verdict_ids", []).append(extra)

    review_sections = _review_sections(t3)
    review_ids = [pid for pid, _, _ in review_sections]
    review_duplicates = sorted({pid for pid in review_ids if review_ids.count(pid) > 1})
    if review_duplicates:
        errors.append(f"03_redteam_verdict.md: duplicate detailed reviews for {review_duplicates}.")
    for unknown_review in sorted(set(review_ids) - expected):
        errors.append(f"03_redteam_verdict.md: detailed review references unknown proposal {unknown_review}.")
    literature_ids = registered_source_ids(root)
    for pid in sorted(expected):
        decision = decisions.get(pid)
        body = _review_match_body(review_sections, pid)
        if body is None:
            errors.append(f"03_redteam_verdict.md: proposal {pid} needs one matching independent review section.")
            continue
        steelman = _review_field(body, ("steelman",), (r"steelman|最强版本复述|最强版本",))
        if not _substantive(steelman):
            errors.append(f"03_redteam_verdict.md: proposal {pid} needs a per-ID steelman.")
        query = _review_field(body, ("prior_query",), (r"prior\s*search\s*query|exact\s*query|检索词",))
        sources = _review_field(body, ("prior_sources",), (r"prior\s*search\s*sources?|databases?\s*(?:searched)?|检索源",))
        search_date = _review_field(body, ("prior_date",), (r"prior\s*search\s*date|actual\s*search\s*date|检索日期",))
        scope = _review_field(body, ("prior_scope",), (r"prior\s*search\s*boundary|search\s*scope|检索边界",))
        result = _review_field(body, ("prior_result",), (r"prior\s*search\s*result|search\s*result|检索结果",))
        if not all(has_value(value) for value in (query, sources, search_date, scope, result)):
            errors.append(f"03_redteam_verdict.md: proposal {pid} needs actual query, sources, date, scope, and result fields for prior search.")
        if search_date and not DATE_RE.search(search_date):
            errors.append(f"03_redteam_verdict.md: proposal {pid} prior search needs its actual calendar date or year.")
        if result and not NO_HIT_RE.search(result):
            result_refs = _source_tokens(result)
            if result_refs and not result_refs.issubset(literature_ids):
                errors.append(f"03_redteam_verdict.md: proposal {pid} prior result cites source ID(s) absent from 01: {sorted(result_refs - literature_ids)}.")
            elif not result_refs and not _stable_locator(result):
                errors.append(f"03_redteam_verdict.md: proposal {pid} prior result needs a stable locator or an explicit bounded no-hit result.")

        relation = field(body, "prior_relation", r"prior\s*relation|prior\s*status")
        relation = re.sub(r"\s+", "", relation).upper()
        prior_difference = _review_field(body, ("prior_difference",), (r"difference\s*from\s*closest|prior\s*difference|closest\s*work|substantive\s*difference",))
        if relation not in {"INDEPENDENT", "KNOWN", "PRIOR-SUGGESTED", "UNCLEAR"}:
            errors.append(f"03_redteam_verdict.md: proposal {pid} prior relation must be INDEPENDENT, KNOWN, PRIOR-SUGGESTED, or UNCLEAR.")
        if not prior_difference:
            errors.append(f"03_redteam_verdict.md: proposal {pid} needs an actual comparison with the closest implementation and author outlook.")
        if decision == "PASS" and relation != "INDEPENDENT":
            errors.append(f"03_redteam_verdict.md: proposal {pid} cannot PASS unless its prior relation is INDEPENDENT.")

        claim = claims.get(pid, "unknown")
        if claim == "method":
            baseline = _review_field(body, ("m2", "baseline_or_alternative"), (r"\bM2\b|strong\s*naive|强朴素",))
            if not _substantive(baseline):
                errors.append(f"03_redteam_verdict.md: method proposal {pid} needs its own strong naive baseline construction.")
        elif claim == "theory":
            prior = _review_field(body, ("strongest_prior", "baseline_or_alternative"), (r"strongest\s*prior|closest\s*theorem|最接近.*(?:命题|定理)|既有结论",))
            if not _substantive(prior):
                errors.append(f"03_redteam_verdict.md: theory proposal {pid} needs a cited strongest prior result and implication test.")
        elif claim == "phenomenon":
            alternative = _review_field(body, ("alternate_explanation", "baseline_or_alternative"), (r"alternate\s*explanation|rival\s*explanation|竞争解释|替代解释",))
            if not _substantive(alternative):
                errors.append(f"03_redteam_verdict.md: phenomenon proposal {pid} needs a serious rival explanation.")
        else:
            errors.append(f"03_redteam_verdict.md: proposal {pid} has no recognized claim type in 02.")

        if decision == "PASS":
            artifacts = _review_field(body, ("verification_artifacts", "artifacts"), (r"verification\s*artifacts?|planned\s*artifacts?|验证产物|验证文件",))
            risks = _review_field(body, ("risks", "risk_mitigation"), (r"risks?|risk\s*and\s*mitigation|风险.*缓解|主要风险",))
            if not _substantive(artifacts):
                errors.append(f"03_redteam_verdict.md: PASS proposal {pid} needs concrete planned verification artifacts.")
            if not _substantive(risks):
                errors.append(f"03_redteam_verdict.md: PASS proposal {pid} needs a concrete risk and mitigation record.")
        elif decision in {"KILL", "DEFER"}:
            reason = _review_field(body, ("kill_defer_reason", "reason"), (r"kill\s*/?\s*defer\s*reason|reason\s*for\s*(?:kill|defer)|淘汰.*原因|暂缓.*原因",)) or row_reasons.get(pid, "")
            if not _substantive(reason):
                errors.append(f"03_redteam_verdict.md: {decision} proposal {pid} needs a specific recorded reason.")
        elif decision == "REVISE":
            action = _review_field(body, ("revise_action", "kill_defer_reason"), (r"revision\s*action|revise\s*action|返修动作|需要修正",))
            if not _substantive(action):
                errors.append(f"03_redteam_verdict.md: REVISE proposal {pid} needs a bounded revision action and reason.")

    pass_ids = {pid for pid, decision in decisions.items() if decision == "PASS"}
    counts = {name: sum(1 for value in decisions.values() if value == name) for name in ("PASS", "REVISE", "KILL", "DEFER")}
    stats["verdict_counts"] = counts
    stats["pass_ids"] = sorted(pass_ids)
    selection, has_author_decision, selection_valid = _author_selection(t3)
    stats["selected_for_verification"] = sorted(selection)
    if has_author_decision and not selection_valid:
        errors.append("03_redteam_verdict.md: author selection must contain exact proposal IDs, or a clear return/no-advance decision.")
    unknown_selected = sorted(selection - expected)
    not_passed = sorted(selection - pass_ids)
    if unknown_selected:
        errors.append(f"03_redteam_verdict.md: author selection names unknown proposal ID(s) {unknown_selected}.")
    if not_passed:
        errors.append(f"03_redteam_verdict.md: author may advance only PASS proposal(s); invalid selection {not_passed}.")
    stats["approval_pending"] = not has_author_decision
    stats["handoff_ready"] = bool(selection) and not errors
    stats["review_sections"] = len(review_sections)
    return errors, warnings, stats

