#!/usr/bin/env python3
"""Local zero-dependency workflow helper for the `paper-innovation` skill.

Commands:
    init   --dir <path> --topic <str> [--journal <str>] [--force]
    status --dir <path> [--json]
    check  --dir <path> --gate <1|2|3|4> [--min-papers <int>] [--strict] [--json]

Exit codes:
    0  Validation/command succeeded
    1  Gate failure (or warnings present under --strict)
    2  Malformed arguments, missing templates, or unsafe path error
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_ROOT / "templates"

ARTIFACT_FILES = [
    "01_assumption_failure_matrix.md",
    "02_candidate_proposals.md",
    "03_redteam_verdict.md",
    "04_mvp_verification.md",
    "05_internal_flaw_memo.md",
    "06_final_contributions.md",
]

PLACEHOLDER_RE = re.compile(r"【[^】\n]+】|\bTODO\b|\bTBD\b")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:\-\|]+\|\s*$")
STRUCTURAL_LIMITATIONS = [
    "Structural gate checks verify artifact completeness, placeholder removal, and cross-file referential integrity.",
    "Passing a gate does not certify mathematical proof, literature novelty, empirical truth, or peer-review acceptance.",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_placeholders(text: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        for match in PLACEHOLDER_RE.finditer(line):
            hits.append((idx, match.group(0)))
    return hits


def extract_table_rows(section_text: str) -> list[list[str]]:
    """Return non-header, non-separator rows of the first Markdown table in section_text."""
    rows: list[list[str]] = []
    lines = section_text.splitlines()
    in_table = False
    saw_sep = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if not in_table:
                in_table = True
                saw_sep = False
                continue
            if not saw_sep and TABLE_SEP_RE.match(stripped):
                saw_sep = True
                continue
            if saw_sep:
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if any(cells):
                    rows.append(cells)
        elif in_table and saw_sep:
            break
    return rows


def extract_section(text: str, heading_pattern: str) -> str:
    """Extract body under a Markdown heading matching heading_pattern until next same/higher heading."""
    lines = text.splitlines()
    start_idx = None
    level = 0
    pattern = re.compile(heading_pattern)
    for idx, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and pattern.search(m.group(2)):
            start_idx = idx + 1
            level = len(m.group(1))
            break
    if start_idx is None:
        return ""
    body: list[str] = []
    for line in lines[start_idx:]:
        m = re.match(r"^(#{1,6})\s+", line)
        if m and len(m.group(1)) <= level:
            break
        body.append(line)
    return "\n".join(body)


def split_subsections(text: str, heading_regex: str) -> list[tuple[str, str]]:
    """Split text into (title, body) tuples for headings matching heading_regex."""
    lines = text.splitlines()
    rx = re.compile(heading_regex)
    indices: list[tuple[int, str, int]] = []
    for idx, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and rx.search(m.group(2)):
            indices.append((idx, m.group(2).strip(), len(m.group(1))))
    results: list[tuple[str, str]] = []
    for i, (start, title, lvl) in enumerate(indices):
        end = len(lines)
        for j in range(start + 1, len(lines)):
            m = re.match(r"^(#{1,6})\s+", lines[j])
            if m and len(m.group(1)) <= lvl:
                end = j
                break
        results.append((title, "\n".join(lines[start + 1 : end])))
    return results


def extract_conflict_ids(text_01: str) -> set[str]:
    ids: set[str] = set()
    for title, _ in split_subsections(text_01, r"矛盾\s*C\d+"):
        m = re.search(r"\b(C\d+)\b", title)
        if m:
            ids.add(m.group(1))
    return ids


def extract_proposal_ids(text_02: str) -> list[str]:
    ids: list[str] = []
    for title, _ in split_subsections(text_02, r"方案\s*P\d+"):
        m = re.search(r"\b(P\d+)\b", title)
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


def cmd_init(args: argparse.Namespace) -> int:
    target_dir = Path(args.dir).resolve()
    if target_dir.is_symlink():
        print(f"[ERROR] Refusing to write into symlink directory: {target_dir}", file=sys.stderr)
        return 2
    target_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    replacements = {
        "{{TOPIC}}": args.topic,
        "{{JOURNAL}}": args.journal,
        "{{DATE}}": today,
    }

    created = 0
    skipped = 0
    for filename in ARTIFACT_FILES:
        src = TEMPLATES_DIR / filename
        if not src.is_file():
            print(f"[ERROR] Missing bundled template: {src}", file=sys.stderr)
            return 2
        dst = target_dir / filename
        if dst.is_symlink():
            print(f"[ERROR] Refusing to overwrite symlink file: {dst}", file=sys.stderr)
            return 2
        if dst.exists() and not args.force:
            print(f"[SKIP] {dst.name} already exists (use --force to overwrite)")
            skipped += 1
            continue
        content = read_text(src)
        for token, value in replacements.items():
            content = content.replace(token, value)
        dst.write_text(content, encoding="utf-8")
        print(f"[INIT] Created {dst}")
        created += 1

    print(
        f"\nInitialized ideation workspace at: {target_dir} "
        f"(created={created}, skipped={skipped})"
    )
    return 0


def summarize_artifact(filename: str, text: str) -> str:
    if filename.startswith("01_"):
        v_rows = extract_table_rows(extract_section(text, r"纵向"))
        h_rows = extract_table_rows(extract_section(text, r"横向"))
        conflicts = extract_conflict_ids(text)
        return f"papers={len(v_rows)}, cross_tools={len(h_rows)}, conflicts={len(conflicts)}"
    if filename.startswith("02_"):
        proposals = extract_proposal_ids(text)
        return f"proposals={len(proposals)} ({', '.join(proposals) if proposals else 'none'})"
    if filename.startswith("03_"):
        rows = extract_table_rows(extract_section(text, r"总览裁决表"))
        verdicts = [r[5] for r in rows if len(r) >= 6]
        return f"verdicts={len(rows)} ({', '.join(verdicts) if verdicts else 'none'})"
    if filename.startswith("04_"):
        rows = extract_table_rows(extract_section(text, r"四组强制对照"))
        return f"benchmark_rows={len(rows)}"
    if filename.startswith("05_"):
        rows = extract_table_rows(extract_section(text, r"局限|风险清单"))
        return f"logged_risks={len(rows)} [INTERNAL ONLY]"
    if filename.startswith("06_"):
        contribs = re.findall(
            r"^\s*\d+\.\s+", extract_section(text, r"凝练版|Contributions"), flags=re.M
        )
        m_rows = extract_table_rows(extract_section(text, r"总控映射表"))
        return f"contributions={len(contribs)}, mapped_rows={len(m_rows)}"
    return "-"


def cmd_status(args: argparse.Namespace) -> int:
    target_dir = Path(args.dir).resolve()
    if not target_dir.exists():
        msg = {"exists": False, "dir": str(target_dir), "artifacts": []}
        if args.json:
            print(json.dumps(msg, ensure_ascii=False, indent=2))
        else:
            print(f"[MISSING] Directory does not exist: {target_dir}")
        return 1

    records: list[dict[str, Any]] = []
    for filename in ARTIFACT_FILES:
        path = target_dir / filename
        if not path.is_file():
            records.append(
                {"artifact": filename, "state": "MISSING", "placeholders": None, "details": "-"}
            )
            continue
        text = read_text(path)
        ph = find_placeholders(text)
        state = "READY" if not ph else "DRAFT"
        records.append(
            {
                "artifact": filename,
                "state": state,
                "placeholders": len(ph),
                "details": summarize_artifact(filename, text),
            }
        )

    if args.json:
        print(
            json.dumps(
                {
                    "exists": True,
                    "dir": str(target_dir),
                    "artifacts": records,
                    "limitations": STRUCTURAL_LIMITATIONS,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"Ideation Workspace Status: {target_dir}\n")
    print(f"{'Artifact':<34} {'State':<10} {'Placeholders':<14} Details")
    print("-" * 96)
    for rec in records:
        ph_str = "-" if rec["placeholders"] is None else str(rec["placeholders"])
        print(f"{rec['artifact']:<34} {rec['state']:<10} {ph_str:<14} {rec['details']}")
    return 0


def require_clean_file(
    target_dir: Path, filename: str, errors: list[str]
) -> str | None:
    path = target_dir / filename
    if not path.is_file():
        errors.append(f"Missing required artifact: {filename}")
        return None
    text = read_text(path)
    ph = find_placeholders(text)
    if ph:
        sample = ", ".join(f"L{ln}:{tok}" for ln, tok in ph[:5])
        extra = f" (+{len(ph) - 5} more)" if len(ph) > 5 else ""
        errors.append(
            f"{filename} still contains {len(ph)} unfilled placeholder(s): {sample}{extra}"
        )
    return text


def check_gate_1(target_dir: Path, min_papers: int) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {}

    t1 = require_clean_file(target_dir, "01_assumption_failure_matrix.md", errors)
    defined_conflicts: set[str] = set()
    if t1 is not None:
        v_rows = extract_table_rows(extract_section(t1, r"纵向"))
        stats["vertical_papers"] = len(v_rows)
        if len(v_rows) < min_papers:
            errors.append(
                f"01_assumption_failure_matrix.md: vertical matrix has {len(v_rows)} paper(s), "
                f"minimum required is {min_papers}."
            )
        elif len(v_rows) < 15:
            warnings.append(
                f"Vertical matrix has {len(v_rows)} paper(s); 15-30 recent papers are recommended."
            )

        # Verify source provenance & read-depth tags when 7-column schema is used
        full_text_cnt = 0
        abstract_only_cnt = 0
        untagged_rows = 0
        for row in v_rows:
            joined = " ".join(row)
            has_ft = bool(re.search(r"\bfull[\-\s]?text\b", joined, flags=re.I))
            has_ao = bool(re.search(r"\babstract[\-\s]?only\b", joined, flags=re.I))
            if has_ft:
                full_text_cnt += 1
            elif has_ao:
                abstract_only_cnt += 1
            else:
                untagged_rows += 1
        stats["full_text_papers"] = full_text_cnt
        stats["abstract_only_papers"] = abstract_only_cnt
        if untagged_rows > 0:
            warnings.append(
                f"01_assumption_failure_matrix.md: {untagged_rows} row(s) missing read-depth tag ('full-text' or 'abstract-only')."
            )
        if v_rows and abstract_only_cnt > len(v_rows) * 0.5:
            warnings.append(
                f"Over half of vertical papers ({abstract_only_cnt}/{len(v_rows)}) are 'abstract-only'; "
                "core conflicts and M1 SOTA should be backed by full-text reading."
            )

        h_rows = extract_table_rows(extract_section(t1, r"横向"))
        stats["cross_domain_tools"] = len(h_rows)
        if len(h_rows) < 2:
            errors.append(
                f"01_assumption_failure_matrix.md: horizontal cross-domain table has {len(h_rows)} row(s), "
                "require at least 2 to prevent domain fixation."
            )

        defined_conflicts = extract_conflict_ids(t1)
        stats["defined_conflicts"] = sorted(defined_conflicts)
        if len(defined_conflicts) < 2:
            errors.append(
                f"01_assumption_failure_matrix.md: found {len(defined_conflicts)} structural conflict(s) (C1..), "
                "require at least 2 (recommended 3-5)."
            )

    t2 = require_clean_file(target_dir, "02_candidate_proposals.md", errors)
    if t2 is not None:
        proposals = split_subsections(t2, r"方案\s*P\d+")
        stats["proposals"] = len(proposals)
        if len(proposals) < 2:
            errors.append(
                f"02_candidate_proposals.md: found {len(proposals)} candidate proposal(s), "
                "require at least 2 differentiated candidates (recommended 3-4)."
            )
        elif len(proposals) < 3:
            warnings.append("Only 2 proposals provided; 3-4 orthogonal candidates are recommended.")

        operator_sets: list[frozenset[str]] = []
        for title, body in proposals:
            ops = frozenset(re.findall(r"\b(O[1-6])\b", body))
            if not ops:
                errors.append(f"Proposal '{title}' must cite at least one construction operator (O1-O6).")
            else:
                operator_sets.append(ops)

            # Cross-file referential integrity: cited conflicts C\d+ must exist in 01
            cited_conflicts = set(re.findall(r"\b(C\d+)\b", body))
            if not cited_conflicts:
                errors.append(f"Proposal '{title}' must reference a structural conflict ID (e.g., C1) from 01.")
            elif defined_conflicts:
                missing_c = sorted(cited_conflicts - defined_conflicts)
                if missing_c:
                    errors.append(
                        f"Proposal '{title}' references undefined conflict ID(s) {missing_c} "
                        f"(defined in 01: {sorted(defined_conflicts)})."
                    )

            if not re.search(r"强朴素适配|Naive\s+Adaptation", body, flags=re.I):
                errors.append(f"Proposal '{title}' must specify a Strong Naive Baseline (Naive Adaptation).")
            if not re.search(r"证伪条件|区分性预测|Discriminating\s+Prediction", body, flags=re.I):
                warnings.append(f"Proposal '{title}' should state an explicit falsification condition.")
            if not re.search(r"w/o", body, flags=re.I):
                errors.append(f"Proposal '{title}' must define at least one explicit ablation variant (w/o ...).")

        if len(operator_sets) >= 2 and len(set(operator_sets)) == 1:
            warnings.append(
                "Anti-homogenization warning: all proposals use the exact same operator set "
                f"{sorted(operator_sets[0])}; diversify operators for orthogonal routes."
            )

    return errors, warnings, stats


def check_gate_2(target_dir: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {}

    t3 = require_clean_file(target_dir, "03_redteam_verdict.md", errors)
    if t3 is None:
        return errors, warnings, stats

    # Cross-file referential integrity: every P\d+ from 02 must be judged in 03
    p2_path = target_dir / "02_candidate_proposals.md"
    expected_proposals = extract_proposal_ids(read_text(p2_path)) if p2_path.is_file() else []

    rows = extract_table_rows(extract_section(t3, r"总览裁决表"))
    if len(rows) < 2:
        errors.append(
            f"03_redteam_verdict.md: summary verdict table has {len(rows)} row(s), require >= 2."
        )

    reviewed_proposals: list[str] = []
    verdict_counts = {"PASS": 0, "REVISE": 0, "KILL": 0}
    for row in rows:
        pm = re.search(r"\b(P\d+)\b", row[0])
        if pm:
            reviewed_proposals.append(pm.group(1))
        verdict_cell = row[5] if len(row) >= 6 else " ".join(row)
        vm = re.search(r"\b(PASS|REVISE|KILL)\b", verdict_cell)
        if not vm:
            errors.append(f"03_redteam_verdict.md: missing PASS/REVISE/KILL verdict in row: {row[0]}")
        else:
            verdict_counts[vm.group(1)] += 1

    stats["verdicts"] = verdict_counts
    if expected_proposals:
        missing_p = [p for p in expected_proposals if p not in reviewed_proposals]
        if missing_p:
            errors.append(
                f"03_redteam_verdict.md: silently dropped proposal(s) from 02_candidate_proposals.md: {missing_p}."
            )

    if not re.search(r"去外壳抽象检索词|同构查重", t3):
        errors.append("03_redteam_verdict.md: missing Gate 1 stripped-shell isomorphic search log.")

    if verdict_counts["PASS"] > 0:
        if not re.search(r"最强版本|Steelman", t3, flags=re.I):
            warnings.append("03_redteam_verdict.md: recommended to include Steelman ('最强版本') before attacking.")
        if not re.search(r"强朴素基线.*M2|\bM2\b", t3):
            errors.append("03_redteam_verdict.md: PASS proposal(s) must register explicit Strong Naive Baseline M2.")
        if not re.search(r"虚假胜出|Apparent-Win|Artifact", t3, flags=re.I):
            errors.append(
                "03_redteam_verdict.md: PASS proposal(s) must include Premortem Apparent-Win Artifact Audit ('虚假胜出排查')."
            )
        if not re.search(r"审稿攻击点|Top\s*2", t3, flags=re.I):
            errors.append("03_redteam_verdict.md: PASS proposal(s) must document top reviewer attack points.")
    else:
        warnings.append("No proposal achieved PASS; expect targeted revision or returning to Phase 1-2.")

    if not re.search(r"决策点\s*1", t3):
        errors.append("03_redteam_verdict.md: missing Human Decision Gate 1 sign-off section.")

    return errors, warnings, stats


def check_gate_3(target_dir: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {}

    t4 = require_clean_file(target_dir, "04_mvp_verification.md", errors)
    if t4 is not None:
        if not re.search(r"预注册|Advance", t4, flags=re.I):
            errors.append(
                "04_mvp_verification.md: missing Pre-Registered Advance/Revise/Stop decision rule."
            )
        if not re.search(r"不可判定|合理性核验|Indeterminate", t4, flags=re.I):
            errors.append(
                "04_mvp_verification.md: missing Indeterminate Outcome / baseline sanity check."
            )
        if not re.search(r"虚假胜出|Apparent-Win|Artifact", t4, flags=re.I):
            errors.append(
                "04_mvp_verification.md: missing Apparent-Win Artifact Audit ('虚假胜出排查')."
            )

        bench_section = extract_section(t4, r"四组强制对照")
        rows = extract_table_rows(bench_section)
        stats["benchmark_rows"] = len(rows)
        first_cols = " ".join(r[0] for r in rows)
        for req in ("M0", "M1", "M2", "M3"):
            if not re.search(rf"\b{req}\b", first_cols):
                errors.append(
                    f"04_mvp_verification.md: benchmark table is missing required competitor '{req}'."
                )
        if not re.search(r"w/o", first_cols, flags=re.I):
            errors.append("04_mvp_verification.md: benchmark table must include at least one ablation row ('w/o').")
        if not re.search(r"情况\s*[ABC]", t4):
            errors.append("04_mvp_verification.md: missing explicit triage classification (情况 A / B / C).")

    t5 = require_clean_file(target_dir, "05_internal_flaw_memo.md", errors)
    if t5 is not None:
        if not re.search(r"INTERNAL\s+ONLY|严禁直接写入正文", t5, flags=re.I):
            errors.append("05_internal_flaw_memo.md: missing INTERNAL ONLY non-manuscript isolation header.")
        risk_rows = extract_table_rows(extract_section(t5, r"局限|风险清单"))
        stats["logged_risks"] = len(risk_rows)
        if len(risk_rows) < 1:
            errors.append("05_internal_flaw_memo.md: must log at least 1 concrete limitation/boundary risk (R1..).")

    return errors, warnings, stats


def check_gate_4(target_dir: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {}

    t6 = require_clean_file(target_dir, "06_final_contributions.md", errors)
    if t6 is None:
        return errors, warnings, stats

    if not re.search(r"英文拟题", t6) or not re.search(r"中文拟题", t6):
        errors.append("06_final_contributions.md: must include both English and Chinese concrete titles.")

    contrib_sec = extract_section(t6, r"凝练版|Contributions")
    contribs = re.findall(r"^\s*\d+\.\s+\S+", contrib_sec, flags=re.M)
    stats["contributions"] = len(contribs)
    if len(contribs) < 2:
        errors.append(f"06_final_contributions.md: found {len(contribs)} contribution(s), require 2-3.")
    elif len(contribs) > 3:
        warnings.append(
            f"Found {len(contribs)} contributions; top engineering journals favor 2-3 tightly coupled contributions."
        )

    map_rows = extract_table_rows(extract_section(t6, r"总控映射表"))
    stats["mapped_rows"] = len(map_rows)
    if len(map_rows) < 2:
        errors.append(
            f"06_final_contributions.md: master mapping table has {len(map_rows)} row(s), require >= 2."
        )

    if not re.search(r"术语克制", t6):
        errors.append("06_final_contributions.md: missing Terminology Restraint check section.")

    if not re.search(r"严禁.*05_internal_flaw_memo|不会传入正文|DO NOT pass.*05_internal_flaw_memo", t6, flags=re.I):
        warnings.append(
            "06_final_contributions.md: explicitly confirm that 05_internal_flaw_memo.md is excluded from manuscript handoff."
        )

    return errors, warnings, stats


def cmd_check(args: argparse.Namespace) -> int:
    target_dir = Path(args.dir).resolve()
    if not target_dir.is_dir():
        if args.json:
            print(
                json.dumps(
                    {"valid": False, "gate": args.gate, "errors": [f"Directory not found: {target_dir}"]},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"[FAIL] Ideation directory not found: {target_dir}", file=sys.stderr)
        return 1

    gate = args.gate
    if gate == 1:
        errors, warnings, stats = check_gate_1(target_dir, args.min_papers)
    elif gate == 2:
        errors, warnings, stats = check_gate_2(target_dir)
    elif gate == 3:
        errors, warnings, stats = check_gate_3(target_dir)
    elif gate == 4:
        errors, warnings, stats = check_gate_4(target_dir)
    else:
        print(f"[ERROR] Unsupported gate: {gate}", file=sys.stderr)
        return 2

    passed = (not errors) and (not (args.strict and warnings))

    if args.json:
        payload = {
            "gate": gate,
            "dir": str(target_dir),
            "valid": passed,
            "strict": args.strict,
            "errors": errors,
            "warnings": warnings,
            "statistics": stats,
            "limitations": STRUCTURAL_LIMITATIONS,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if passed else 1

    print(f"=== Paper Innovation Gate {gate} Check ({target_dir}) ===")
    for w in warnings:
        print(f"[WARN] {w}")
    for e in errors:
        print(f"[FAIL] {e}")

    if not passed:
        reason = f"{len(errors)} error(s)"
        if args.strict and warnings:
            reason += f", {len(warnings)} warning(s) under --strict"
        print(f"\nGate {gate} FAILED ({reason}).")
        return 1

    print(f"\nGate {gate} PASSED.")
    if gate == 2:
        print("Next: Pause for Human Decision Gate 1 before starting Phase 4 MVP coding.")
    elif gate == 3:
        print("Next: Pause for Human Decision Gate 2 with 04_mvp_verification.md and 05_internal_flaw_memo.md.")
    elif gate == 4:
        print(
            "Handoff ready: Pass 04_mvp_verification.md and 06_final_contributions.md downstream.\n"
            "DO NOT pass 05_internal_flaw_memo.md to manuscript drafting."
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scaffold and validate `paper-innovation` ideation artifacts (local, deterministic, zero-dependency)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Scaffold ideation/ Markdown templates for a new topic.")
    p_init.add_argument("--dir", default="ideation", help="Target ideation directory (default: ideation)")
    p_init.add_argument("--topic", required=True, help="Research topic or focal scenario")
    p_init.add_argument("--journal", default="IEEE TPWRS / TSTE / MPCE", help="Target journal(s)")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing files")
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="Show artifact readiness and counts.")
    p_status.add_argument("--dir", default="ideation", help="Target ideation directory")
    p_status.add_argument("--json", action="store_true", help="Emit machine-readable JSON status")
    p_status.set_defaults(func=cmd_status)

    p_check = sub.add_parser("check", help="Validate hard structural & cross-file invariants for Gate 1-4.")
    p_check.add_argument("--dir", default="ideation", help="Target ideation directory")
    p_check.add_argument("--gate", type=int, choices=[1, 2, 3, 4], required=True, help="Gate number (1-4)")
    p_check.add_argument(
        "--min-papers",
        type=int,
        default=10,
        help="Minimum paper rows required in Gate 1 vertical matrix (default: 10)",
    )
    p_check.add_argument("--strict", action="store_true", help="Treat warnings as gate failures")
    p_check.add_argument("--json", action="store_true", help="Emit machine-readable JSON validation report")
    p_check.set_defaults(func=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
