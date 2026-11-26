#!/usr/bin/env python3
"""Initialize, screen, preregister and check research proposals. Python 3.9+, stdlib."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

from ideation_context import brief_digest, build_brief, lineage_errors, proposal_sections
from ideation_evidence import check_gate_3, check_gate_4, has_recorded_results, prereg_plan
from ideation_markdown import PID, field, has_value, placeholders, section, table
from ideation_review import callable_source_ids, check_gate_1, check_gate_2, proposal_claims, verdicts

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
MATRIX = "01_assumption_failure_matrix.md"
CANDIDATES = "02_candidate_proposals.md"
REVIEW = "03_redteam_verdict.md"
VERIFICATION = "04_mvp_verification.md"
MEMO = "05_internal_flaw_memo.md"
HANDOFF = "06_final_contributions.md"
ARTIFACT_FILES = [MATRIX, CANDIDATES, REVIEW, VERIFICATION, MEMO, HANDOFF]
SCREEN = "00_screening.md"
CONFIG = ".ideation.json"
LOCK = ".prereg_lock.json"
BRIEF = "idea_context.md"
CLAIMS = ("method", "theory", "phenomenon")
MODES = ("full", "single", "batch", "revision", "local-pdf")
DEFAULT_JOURNAL = "IEEE TPWRS / TSTE / MPCE"
LIMITATIONS = ["Checks verify recorded evidence and decisions. Scientific novelty, proof validity and causal identification require independent review."]


def read_if_present(path):
    return path.read_text(encoding="utf-8-sig") if path.is_file() else ""


def safe_destination(path):
    """Check the supplied path before resolving symlinks or Windows junctions."""
    path = Path(os.path.abspath(path.expanduser()))
    for entry in (path, *path.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise ValueError(f"Choose a regular project directory; linked write destination: {entry}")
    return path


def publish(path, data, replace=False):
    """Publish complete bytes; competing initializers do not overwrite the winner."""
    safe_destination(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".ideation-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(data)
            handle.flush()
        if replace:
            os.replace(temp, path)
        else:
            try:
                # Windows rename refuses an existing destination and also works on FAT.
                if os.name == "nt":
                    os.rename(temp, path)
                else:
                    os.link(temp, path)
            except FileExistsError:
                return False
        return True
    finally:
        Path(temp).unlink(missing_ok=True)


def as_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def config(root):
    path = root / CONFIG
    if path.exists():
        data = json.loads(read_if_present(path))
        if (not isinstance(data, dict) or data.get("version") != 2 or data.get("mode") not in MODES
                or data.get("claim") not in CLAIMS
                or not all(isinstance(data.get(k), str) and data[k].strip() for k in ("topic", "journal", "date"))
                or ("min_papers" in data and (type(data["min_papers"]) is not int or data["min_papers"] < 1))):
            raise ValueError(f"Invalid {CONFIG} settings in {root}")
        return data
    legacy = read_if_present(root / MATRIX)
    return {"version": 1, "topic": field(legacy, "topic", r"研究主题|topic"),
            "journal": field(legacy, "journal", r"目标期刊|journal"),
            "mode": "full", "claim": "method", "date": dt.date.today().isoformat()}


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("expected an integer >= 1")
    return number


def proposal_id(value):
    if not re.fullmatch(PID, value):
        raise argparse.ArgumentTypeError("expected a proposal ID such as P1 or P1-v2")
    return value


def minimum(args, data):
    return args.min_papers or data.get("min_papers") or (10 if data["mode"] == "full" else 1)


def render(filename, settings, proposal):
    source = filename
    if filename == VERIFICATION and settings["claim"] != "method":
        source = f'04_{settings["claim"]}.md'
    text = (TEMPLATES / source).read_text(encoding="utf-8-sig")
    values = dict(settings, proposal=proposal)
    return re.sub(r"\{\{(TOPIC|JOURNAL|MODE|CLAIM|PROPOSAL|DATE)\}\}",
                  lambda m: values[m[1].lower()], text)


def scaffold(work, files, contents, force=False):
    for filename in files:
        target = safe_destination(work / filename)
        if target.exists() and not target.is_file():
            raise ValueError(f"Expected an artifact file at {target}")
    created = []
    for filename in files:
        target = work / filename
        if not force and target.is_file():
            continue
        if publish(target, contents[filename], replace=force):
            created.append(filename)
    return {"dir": str(work), "written": created, "skipped": len(files) - len(created)}


def emit(args, data, message=None):
    print(as_json(data).rstrip() if args.json or message is None else message)


def init(args):
    root = safe_destination(Path(args.dir))
    old = config(root)
    existing = (root / CONFIG).exists()
    settings = {"version": 2, "topic": args.topic.strip(),
                "journal": args.journal or old["journal"] or DEFAULT_JOURNAL,
                "mode": args.mode or old["mode"], "claim": args.claim or old["claim"],
                "date": old.get("date") or dt.date.today().isoformat()}
    if not settings["topic"]:
        raise ValueError("Supply a nonempty topic.")
    if args.min_papers or old.get("min_papers"):
        settings["min_papers"] = args.min_papers or old["min_papers"]
    if existing and any(settings.get(k) != old.get(k) for k in ("topic", "journal", "mode", "claim", "min_papers")):
        raise ValueError("This directory already belongs to a different topic or configuration. Choose a new --dir.")
    if not existing and old["topic"] and old["topic"] != settings["topic"]:
        raise ValueError(f"Existing artifacts belong to '{old['topic']}'. Choose a new --dir.")
    if settings["mode"] == "batch" and any((root / f).exists() for f in ARTIFACT_FILES):
        raise ValueError("Initialize a batch in a separate directory from a full research record.")
    files = [SCREEN] if settings["mode"] == "batch" else ARTIFACT_FILES
    if args.force and ((root / LOCK).exists() or (root / "runs").exists()):
        raise ValueError("This project has saved runs. Choose a new --dir to start another topic.")
    pid = "P1" if settings["mode"] in ("single", "revision", "local-pdf") else "{{FILL:获批的方案编号}}"
    contents = {name: render(name, settings, pid) for name in files}
    if not existing and not publish(root / CONFIG, as_json(settings)) and config(root) != settings:
        raise ValueError("Another initialization selected a different configuration. Choose a new --dir.")
    result = scaffold(root, files, contents, args.force)
    emit(args, result, f"Initialized {root} (written={len(result['written'])}, skipped={result['skipped']})")
    return 0


def start(args):
    root = safe_destination(Path(args.dir))
    data = config(root)
    known = proposal_claims(root)
    if args.proposal not in known or known[args.proposal] not in CLAIMS:
        raise ValueError(f"Define the proposal and its claim in {CANDIDATES} before starting {args.proposal}.")
    if verdicts(root).get(args.proposal) == "KILL":
        raise ValueError(f"{args.proposal} was killed. Register the new proposal version for a revision.")
    work = safe_destination(root / "runs" / args.proposal)
    data = dict(data, claim=known[args.proposal], date=dt.date.today().isoformat())
    contents = {name: render(name, data, args.proposal) for name in ARTIFACT_FILES[3:]}
    result = scaffold(work, ARTIFACT_FILES[3:], contents)
    emit(args, result, f"Proposal {args.proposal}: {work} (written={len(result['written'])}, skipped={result['skipped']})")
    return 0


def verified_briefs(root, proposals):
    """Only a previously exported, content-addressed brief may attest a fresh generation."""
    snapshots = {}
    for digest in set(re.findall(r"(?i)\b[a-f0-9]{64}\b", proposals)):
        digest = digest.lower()
        path = root / "contexts" / (digest + ".md")
        if path.is_file():
            content = read_if_present(path)
            if brief_digest(content) == digest:
                snapshots[digest] = content
    return snapshots


def generation_inputs(root, source):
    brief, errors, stats = build_brief(source)
    if stats["objects"]:
        missing = set(stats["objects"]) - callable_source_ids(root, text=source)
        if missing:
            errors.append("Callable object(s) lack a full-text source and pinpoint in the reviewer register: "
                          + ", ".join(sorted(missing)))
    return brief, errors, stats


def prepare_ideas(args):
    root = safe_destination(Path(args.dir))
    data = config(root)
    source = SCREEN if data["mode"] == "batch" else MATRIX
    brief, errors, stats = generation_inputs(root, read_if_present(root / source))
    if errors:
        emit(args, {"valid": False, "errors": errors}, "\n".join(errors))
        return 1
    digest = brief_digest(brief)
    context_path = safe_destination(root / BRIEF)
    archive_path = safe_destination(root / "contexts" / (digest + ".md"))
    if context_path.exists() and read_if_present(context_path) != brief:
        previous = read_if_present(context_path)
        previous_archive = root / "contexts" / (brief_digest(previous) + ".md")
        if not previous_archive.is_file() or read_if_present(previous_archive) != previous:
            raise ValueError(f"{BRIEF} contains unrecognized edits. Move those notes aside before preparing a brief.")
    if not publish(archive_path, brief) and read_if_present(archive_path) != brief:
        raise ValueError("The archived brief differs from its recorded digest. Check the project context files.")
    if not context_path.is_file() or read_if_present(context_path) != brief:
        publish(context_path, brief, replace=True)
    draft = TEMPLATES / "idea_draft.md"
    info = {"valid": True, "sha256": digest, "context": str(context_path), "snapshot": str(archive_path),
            "template": str(draft),
            "origins": list(stats["origins"]), "objects": list(stats["objects"])}
    emit(args, info, f"Inputs for a fresh generator:\n{archive_path}\n{draft}\nSHA-256 {digest}")
    return 0


def provenance(root, source, proposals):
    _, errors, stats = generation_inputs(root, source)
    if not errors:
        errors.extend(lineage_errors(proposals, stats["origins"], stats["objects"],
                                     exported_sha256=verified_briefs(root, proposals), source_text=source))
    return errors


def check_screen(root):
    data = read_if_present(root / SCREEN)
    errors, decisions = [], {}
    body = section(data, "screening", r"初筛记录|screening")
    _, rows = table(body)
    if not rows:
        errors.append(f"{SCREEN}: fill at least one candidate row, including rejected or deferred ideas.")
    for n, row in enumerate(rows, 1):
        if len(row) != 7:
            errors.append(f"{SCREEN}: row {n} needs all seven columns.")
            continue
        pid, claim, prior, resources, test, verdict, reason = [c.strip().strip('`').strip() for c in row]
        if not re.fullmatch(PID, pid) or pid in decisions:
            errors.append(f"{SCREEN}: invalid or duplicate proposal ID in row {n}: {pid}")
        if claim not in CLAIMS or verdict not in ("KEEP", "DROP", "DEFER"):
            errors.append(f"{SCREEN}: {pid} needs a valid claim and KEEP, DROP or DEFER.")
        for label, value in zip(("closest work", "data availability", "discriminating test", "reason"),
                                (prior, resources, test, reason)):
            if not has_value(value):
                errors.append(f"{SCREEN}: {pid} lacks {label}.")
        decisions[pid] = verdict
    survivors = [p for p, v in decisions.items() if v == "KEEP"]
    generation = field(data, "batch_generation", r"本轮生成方式|batch generation").strip().strip("`")
    if generation not in ("fresh", "author-supplied", "mixed"):
        errors.append(f"{SCREEN}: batch_generation must be fresh, author-supplied or mixed.")
    dossiers = proposal_sections(data)
    by_id = {pid: body for pid, body in dossiers}
    required = set(decisions) if generation in ("fresh", "mixed") else set(survivors)
    for missing in sorted(required - by_id.keys()):
        errors.append(f"{SCREEN}: {missing} needs an origin, literature calls and an independent contribution record.")
    if len(by_id) != len(dossiers) or by_id.keys() - decisions.keys():
        errors.append(f"{SCREEN}: provenance must name a unique candidate in the screening table.")
    modes = {field(body, "generation", "生成方式").strip().strip("`") for body in by_id.values()}
    if generation in ("fresh", "author-supplied") and modes - {generation}:
        errors.append(f"{SCREEN}: each proposal's generation must match the declared {generation} batch.")
    if generation == "mixed" and modes != {"author-supplied", "fresh"}:
        errors.append(f"{SCREEN}: a mixed batch must identify the fresh and author-supplied proposals.")
    if dossiers:
        errors.extend(provenance(root, data, data))
    return errors, [], {"decisions": decisions, "survivors": survivors}


def gates(root, work, proposal, data, min_papers, last):
    results = {1: check_gate_1(root, min_papers, data["mode"])}
    matrix = read_if_present(root / MATRIX)
    proposals = read_if_present(root / CANDIDATES)
    if matrix and proposals:
        results[1][0].extend(provenance(root, matrix, proposals))
    if last >= 2:
        results[2] = check_gate_2(root, data["mode"])
    if last >= 3:
        results[3] = check_gate_3(root, work, proposal)
    if last >= 4:
        results[4] = check_gate_4(root, work, proposal)
    return results


def cumulative(stages):
    errors, warnings = {}, {}
    for stage, (err, warn, _) in stages.items():
        for message in err:
            errors.setdefault(message, f"Gate {stage}: {message}")
        warnings.update(dict.fromkeys(warn))
    return list(errors.values()), list(warnings)


def check(args):
    root = Path(args.dir).expanduser().resolve()
    if not root.is_dir():
        emit(args, {"valid": False, "gate": args.gate, "errors": [f"Directory not found: {root}"]},
             f"Directory not found: {root}")
        return 1
    data = config(root)
    work = root / "runs" / args.proposal if args.proposal else root
    if args.screen:
        if data["mode"] != "batch":
            raise ValueError("--screen is for a batch workspace created using init --mode batch.")
        if args.proposal:
            raise ValueError("--screen checks the whole batch; omit --proposal.")
        errors, warnings, stats = check_screen(root)
        stages = {}
    else:
        if data["mode"] == "batch":
            raise ValueError("Check the batch with --screen, then initialize a single workspace for each survivor.")
        stages = gates(root, work, args.proposal, data, minimum(args, data), args.gate)
        errors, warnings = cumulative(stages)
        stats = stages[args.gate][2]
    valid = not errors and not (args.strict and warnings)
    label = "screen" if args.screen else args.gate
    payload = {"gate": label, "dir": str(work), "valid": valid, "strict": args.strict, "errors": errors,
               "warnings": warnings, "statistics": stats,
               "stages": {n: {"valid": not e and not (args.strict and w), "statistics": s}
                          for n, (e, w, s) in stages.items()}, "limitations": LIMITATIONS}
    messages = [*(f"[FAIL] {e}" for e in errors), *(f"[WARN] {w}" for w in warnings),
                f"Gate {label} {'PASSED' if valid else 'FAILED'}."]
    if valid and args.gate == 4:
        messages.append(f"Handoff ready: share {VERIFICATION} and {HANDOFF} for the selected proposal.")
    emit(args, payload, "\n".join(messages))
    return 0 if valid else 1


def lock_prereg(args):
    root = safe_destination(Path(args.dir))
    work = safe_destination(root / "runs" / args.proposal) if args.proposal else root
    data = config(root)
    if data["mode"] == "batch":
        raise ValueError("A batch screen has no protocol. Initialize a survivor separately.")
    stages = gates(root, work, args.proposal, data, minimum(args, data), 2)
    errors, _ = cumulative(stages)
    proposal, plan, plan_errors = prereg_plan(root, work, args.proposal)
    errors.extend(plan_errors)
    if errors:
        emit(args, {"valid": False, "errors": errors}, "\n".join(errors))
        return 1
    digest = hashlib.sha256(plan.encode("utf-8")).hexdigest()
    path = safe_destination(work / LOCK)
    record = {"proposal": proposal, "sha256": digest,
              "locked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    if not path.exists():
        text = read_if_present(work / VERIFICATION)
        claim = proposal_claims(root).get(proposal, data["claim"])
        if has_recorded_results(text, claim):
            raise ValueError("Results are already recorded. Keep them exploratory and preregister a new prospective version.")
        publish(path, as_json(record))
    actual = json.loads(read_if_present(path))
    if not isinstance(actual, dict) or actual.get("proposal") != proposal or actual.get("sha256") != digest:
        raise ValueError("A different plan is already locked. Preserve this run and register a new proposal version.")
    emit(args, {"valid": True, **actual}, f"Preregistered {proposal} at {actual.get('locked_at')} (sha256={digest}).")
    return 0


def status(args):
    root = Path(args.dir).expanduser().resolve()
    if not root.is_dir():
        emit(args, {"exists": False, "dir": str(root), "artifacts": []}, f"[MISSING] {root}")
        return 1
    data = config(root)
    work = root / "runs" / args.proposal if args.proposal else root
    proposal_states, stage_ok, stage_statistics = {}, {}, {}
    if data["mode"] == "batch":
        if args.proposal:
            raise ValueError("View the full screening table with status; omit --proposal in batch mode.")
        errors, _, stats = check_screen(root)
        files = [(root / SCREEN, not errors)]
        proposal_states = stats["decisions"]
        details = {SCREEN: f"candidates={len(proposal_states)}, kept={len(stats['survivors'])}"}
    else:
        stages = gates(root, work, args.proposal, data, minimum(args, data), 4)
        valid = True
        for n, (errors, _, statistics) in stages.items():
            valid = valid and not errors
            stage_ok[n] = valid
            stage_statistics[n] = statistics
        files = [(root / MATRIX, stage_ok[1]), (root / CANDIDATES, stage_ok[1]),
                 (root / REVIEW, stage_ok[2]), (work / VERIFICATION, stage_ok[3]),
                 (work / MEMO, stage_ok[3]), (work / HANDOFF, stage_ok[4])]
        for pid in proposal_claims(root):
            proposal_states[pid] = "literature-grounded" if stage_ok[1] else "draft"
        lit, review, verification, final = (stage_statistics[n] for n in range(1, 5))
        details = {
            MATRIX: f"unique_papers={lit.get('unique_papers', 0)}, full_text={lit.get('full_text_papers', 0)}",
            CANDIDATES: f"proposals={len(proposal_states)}",
            REVIEW: f"verdicts={review.get('verdict_counts', {})}",
            VERIFICATION: f"outcome={verification.get('outcome', 'PENDING')}, decision={verification.get('decision2', 'PENDING')}",
            MEMO: f"risks={verification.get('logged_risks', 0)}",
            HANDOFF: f"contributions={final.get('contributions', 0)}, mapped={final.get('mapped_rows', 0)}",
        }
        if stage_ok[2]:
            for pid, result in verdicts(root).items():
                state = {"PASS": "redteam-passed", "KILL": "killed", "DEFER": "deferred",
                         "DEFERRED": "deferred", "REVISE": "revise"}.get(result)
                if state:
                    proposal_states[pid] = state
            # Summarize other runs as well as the currently displayed artifacts.
            targets = [(work, args.proposal)]
            if not args.proposal and (root / "runs").is_dir():
                targets.extend((p, p.name) for p in sorted((root / "runs").iterdir())
                               if p.is_dir() and re.fullmatch(PID, p.name))
            for target, pid in targets:
                e3, _, s3 = stages[3] if target == work else check_gate_3(root, target, pid)
                active = s3.get("proposal") or pid
                if e3 or active not in proposal_states:
                    continue
                e4, _, _ = stages[4] if target == work else check_gate_4(root, target, pid)
                state = "mvp-tested"
                if not e4:
                    state = "locked"
                elif s3.get("outcome") == "STOP" and str(s3.get("decision2", "")).lower() == "stop":
                    state = "killed"
                proposal_states[active] = state
    artifacts = []
    for path, ready in files:
        text = read_if_present(path)
        state = "MISSING" if not path.is_file() else ("READY" if ready and text.strip() else "DRAFT")
        artifacts.append({"artifact": path.name, "state": state,
                          "placeholders": len(placeholders(text)) if path.is_file() else None,
                          "details": details[path.name]})
    report = {"exists": True, "dir": str(work), "mode": data["mode"], "claim": data["claim"],
              "artifacts": artifacts, "proposals": proposal_states, "gates": stage_ok,
              "statistics": stage_statistics, "limitations": LIMITATIONS}
    message = [f"{data['mode']} workspace: {work}", *(f"{a['state']:<8} {a['artifact']}  {a['details']}" for a in artifacts),
               *(f"{pid}: {state}" for pid, state in proposal_states.items())]
    emit(args, report, "\n".join(message))
    return 0


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    commands = {}
    for name, fn in (("init", init), ("start", start), ("prepare-ideas", prepare_ideas),
                     ("status", status), ("check", check), ("lock-prereg", lock_prereg)):
        cmd = sub.add_parser(name)
        cmd.set_defaults(func=fn)
        cmd.add_argument("--dir", default="ideation", help="Research workspace (relative to the current project)")
        cmd.add_argument("--json", action="store_true")
        if name not in ("start", "prepare-ideas"):
            cmd.add_argument("--min-papers", type=positive_int,
                             help="Unique literature minimum; full default 10, focused modes 1")
        if name not in ("init", "prepare-ideas"):
            cmd.add_argument("--proposal", required=name == "start", type=proposal_id,
                             help="Use runs/ID for the proposal's verification and handoff")
        commands[name] = cmd
    cmd = commands["init"]
    cmd.add_argument("--topic", required=True)
    cmd.add_argument("--journal")
    cmd.add_argument("--mode", choices=MODES)
    cmd.add_argument("--claim", choices=CLAIMS)
    cmd.add_argument("--force", action="store_true", help="Rebuild templates in the same unsigned topic")
    cmd = commands["check"]
    group = cmd.add_mutually_exclusive_group(required=True)
    group.add_argument("--gate", type=int, choices=(1, 2, 3, 4))
    group.add_argument("--screen", action="store_true")
    cmd.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    return result


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as error:
        if args.json:
            print(as_json({"valid": False, "errors": [str(error)]}).rstrip())
        else:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
