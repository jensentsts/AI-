"""Exercise the installed-style CLI from unrelated directories with isolated workspaces."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ideation_fixtures import (
    CALL_HEADERS, FINAL, MATRIX, MEMO, PROPOSALS, SCRIPTS, TOPICS, VERDICTS, VERIFICATION,
    approve, fill, populate_final, populate_literature, populate_redteam, preregister,
    record_observations, record_risks, replace_table, table, update, write,
)


class IdeationCliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ideation-tests-")
        self.addCleanup(tmp.cleanup)
        self.scratch = Path(tmp.name)
        self.caller = self.scratch / "unrelated cwd"
        self.caller.mkdir()
        self.workspace = self.scratch / "课题甲" / "ideation"

    def command(self, name, *args, workspace=None, code=0):
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / "ideation_ctl.py"), name,
             "--dir", str(workspace if workspace is not None else self.workspace), *args],
            cwd=self.caller, capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, code, f"{name} {args}\n{result.stdout}\n{result.stderr}")
        return result.stdout

    def gate_report(self, gate, *, code=0, proposal=None, workspace=None, strict=True):
        args = ["--gate", str(gate), "--json"]
        if strict:
            args.append("--strict")
        if proposal:
            args += ["--proposal", proposal]
        result = json.loads(self.command("check", *args, workspace=workspace, code=code))
        self.assertEqual(result["gate"], gate)
        self.assertIs(result["valid"], code == 0, result)
        return result

    def check(self, gate, **kwargs):
        result = self.gate_report(gate, **kwargs)
        return "\n".join(result.get("errors", []) + result.get("warnings", []))

    def init(self, claim="method", *, mode="single", workspace=None):
        self.command("init", "--topic", TOPICS[claim], "--mode", mode, "--claim", claim, workspace=workspace)

    def reviewed(self, claim="method", *, workspace=None, proposals=("P1",), selected=("P1",), verdict="PASS"):
        workspace = workspace or self.workspace
        self.init(claim, workspace=workspace)
        populate_literature(workspace, claim, proposals=proposals)
        populate_redteam(workspace, claim, proposals=proposals, selected=selected, verdict=verdict)

    def lock(self, claim="method", *, workspace=None, proposal=None):
        workspace = workspace or self.workspace
        run = workspace / "runs" / proposal if proposal else workspace
        preregister(workspace, run, claim)
        args = ["--proposal", proposal] if proposal else []
        self.command("lock-prereg", *args, workspace=workspace)
        return run

    def verified(self, *, blank_method_metrics=False):
        self.reviewed()
        run = self.lock()
        record_observations(self.workspace, run, "method", blank_method_metrics=blank_method_metrics)
        record_risks(run)
        return run

    def test_each_claim_has_a_gate_1_through_4_path(self):
        for claim in TOPICS:
            with self.subTest(claim=claim):
                workspace = self.scratch / claim / "ideation"
                self.reviewed(claim, workspace=workspace)
                self.check(1, workspace=workspace)
                self.check(2, workspace=workspace)
                run = self.lock(claim, workspace=workspace)
                record_observations(workspace, run, claim)
                record_risks(run)
                self.check(3, workspace=workspace)
                approve(run)
                populate_final(run, claim)
                self.check(4, workspace=workspace)
                status = json.loads(self.command("status", "--json", workspace=workspace))
                self.assertEqual(status["proposals"], {"P1": "locked"})
        self.assertEqual(list(self.caller.iterdir()), [])

    def test_gate1_rejects_fifteen_copies_of_full_text_without_source(self):
        self.init(mode="full")
        populate_literature(self.workspace, "method", proposals=("P1", "P2", "P3"),
                            literature_rows=15, missing_locator=True)
        diagnostics = self.check(1, code=1)
        self.assertRegex(diagnostics, r"(?i)missing a DOI|locator|溯源|来源|标识")
        self.assertRegex(diagnostics, r"(?i)duplicate literature row|重复.*文献")

    def test_gate1_counts_the_same_canonical_work_only_once(self):
        self.init()
        populate_literature(self.workspace, "method", literature_rows=3, duplicate_locator=True, recurring=True)
        report = self.gate_report(1, code=1)
        diagnostics = "\n".join(report["errors"])
        self.assertEqual(report["statistics"]["unique_papers"], 1)
        self.assertRegex(diagnostics, r"(?i)duplicate.*locator|重复.*来源")
        self.assertRegex(diagnostics, r"(?i)C1.*3.*full.text.*found 1|C1.*3.*全文")

    def test_gate1_requires_explicit_evidence_for_recurring_conflict(self):
        self.init()
        populate_literature(self.workspace, "method", recurring=True, literature_rows=3)
        self.check(1)
        matrix = self.workspace / MATRIX
        update(matrix, "L1 p. 1; L2 p. 1; L3 p. 1", "L1 p. 1; L2; L3 p. 1")
        diagnostics = self.check(1, code=1)
        self.assertRegex(diagnostics, r"(?i)C1.*pinpoint|C1.*定位")
        update(matrix, "L1 p. 1; L2; L3 p. 1", "L1 p. 1; L2 p. 1; L3 p. 1")
        # Downgrade one source to an abstract and keep the same three references.
        update(matrix, "papers/现场-02.pdf | full-text", "papers/现场-02.pdf | abstract-only")
        diagnostics = self.check(1, code=1)
        self.assertRegex(diagnostics, r"(?i)C1|evidence|full.text|全文|证据")

    def test_local_pdf_mode_accepts_an_existing_absolute_path_with_spaces(self):
        self.init(mode="local-pdf")
        populate_literature(self.workspace, "method")
        pdf = self.scratch / "existing library" / "archive_paper copy.pdf"
        pdf.parent.mkdir()
        (self.workspace / "papers" / "现场-01.pdf").rename(pdf)
        update(self.workspace / MATRIX, "10.99999/local-fixture-01 | papers/现场-01.pdf", f" | `{pdf}`")
        report = self.gate_report(1)
        self.assertEqual(report["statistics"]["local_pdf_sources"], 1)

    def test_gate1_rejects_literature_object_as_sole_idea_origin(self):
        self.reviewed()
        self.check(1)
        update(self.workspace / PROPOSALS, "**origin_ids**: Q1", "**origin_ids**: L1")
        diagnostics = self.check(1, code=1)
        self.assertRegex(diagnostics, r"(?i)origin|Q[0-9#]|来源|起点")

    def test_gate1_requires_a_binding_for_each_called_literature_object(self):
        self.reviewed()
        self.check(1)
        replace_table(self.workspace / PROPOSALS, table(CALL_HEADERS, ()), section="call_bindings")
        diagnostics = self.check(1, code=1)
        self.assertRegex(diagnostics, r"(?i)(binding|绑定).*(L1|calls)|(L1|calls).*(binding|绑定)")

    def test_legacy_and_number_only_proposals_also_need_independent_origins(self):
        for heading in ("备选方案（P2）", "P2"):
            with self.subTest(heading=heading):
                self.reviewed(proposals=("P1", "P2"), selected=("P1",))
                path = self.workspace / PROPOSALS
                first, second = path.read_text(encoding="utf-8").split("## Proposal P2")
                write(path, first + "## " + heading + second)
                self.check(1)
                write(path, first + "## " + heading + second.replace("**origin_ids**: Q1", "**origin_ids**: L1"))
                self.assertIn("P2 lineage", self.check(1, code=1))

    def test_gate2_rejects_a_verdict_for_a_different_proposal_version(self):
        for other in ("P1-v2", "P1-draft"):
            with self.subTest(other=other):
                self.reviewed()
                update(self.workspace / VERDICTS, "| P1 |", f"| {other} |")
                diagnostics = self.check(2, code=1)
                self.assertRegex(diagnostics, r"(?i)P1|exact proposal ID|提案编号")

    def test_gate2_all_kill_is_valid_and_cannot_enter_verification(self):
        self.reviewed(selected=(), verdict="KILL")
        report = self.gate_report(2, strict=False)
        self.assertFalse(report["statistics"]["handoff_ready"])
        self.check(3, code=1)

    def test_gate2_rejects_pass_when_review_reports_prior_suggestion(self):
        self.reviewed()
        self.check(2)
        update(self.workspace / VERDICTS, "**prior_relation**: INDEPENDENT", "**prior_relation**: PRIOR-SUGGESTED")
        diagnostics = self.check(2, code=1)
        self.assertRegex(diagnostics, r"(?i)PRIOR-SUGGESTED|INDEPENDENT|先行文献|独立")

    def test_gate3_rejects_a_complete_table_of_empty_measurements(self):
        self.verified(blank_method_metrics=True)
        diagnostics = self.check(3, code=1)
        self.assertIn("M2", diagnostics)
        self.assertRegex(diagnostics, r"(?i)metric|cost|measure|数值|指标|度量")

    def test_gate3_rejects_advance_when_measurements_miss_the_locked_margin(self):
        run = self.verified()
        update(run / VERIFICATION, "| 94 | 0 | 10 |", "| 98 | 0 | 10 |")
        update(run / "evidence" / "metrics.csv", ",94,0,10", ",98,0,10")
        diagnostics = self.check(3, code=1)
        self.assertRegex(diagnostics, r"(?i)M3.*improvement.*M2|M3.*门槛")

    def test_gate3_needs_completed_observations_after_lock(self):
        self.reviewed()
        self.lock()
        diagnostics = self.check(3, code=1)
        self.assertRegex(diagnostics, r"(?i)PENDING|待验证|未完成")

    def test_gate3_accepts_unsigned_memo_and_gate4_requires_author_response(self):
        run = self.verified()
        self.assertIn("{{FILL:作者署名}}", (run / MEMO).read_text(encoding="utf-8"))
        self.check(3)
        populate_final(run, "method")
        self.check(4, code=1)
        update(run / VERIFICATION, "[ ] <!-- decision:advance", "[x] <!-- decision:advance")
        diagnostics = self.check(4, code=1)
        self.assertRegex(diagnostics, r"(?i)author|approval|批复|署名")

    def test_gate4_rejects_directory_with_only_final_document(self):
        self.init()
        populate_final(self.workspace, "method", checklist=False)
        other = self.scratch / "课题乙"
        write(other / FINAL, (self.workspace / FINAL).read_text(encoding="utf-8"))
        diagnostics = self.check(4, workspace=other, code=1)
        self.assertRegex(diagnostics, r"(?i)0[1-5]_|selection|证据|方案|裁决")

    def test_gate4_rejects_stopped_work_even_with_approved_handoff(self):
        run = self.verified()
        approve(run, decision="stop")
        populate_final(run, "method")
        fill(run / VERIFICATION, outcome="STOP", decision_basis="M3 violates an additional constraint.")
        self.check(3)
        diagnostics = self.check(4, code=1)
        self.assertRegex(diagnostics, r"(?i)ADVANCE|STOP|晋级|停止")

    def test_gate4_checks_handoff_confirmations_and_internal_memo_isolation(self):
        run = self.verified()
        approve(run)
        populate_final(run, "method", checklist=False)
        diagnostics = self.check(4, code=1)
        self.assertRegex(diagnostics, r"(?i)check|confirmation|勾选|确认")
        private_comment = "External validity changes across observation windows"
        fill(run / FINAL, story=f"The scope is limited to this synthetic replay. {private_comment}")
        for item in ("review", "evidence", "scope", "memo"):
            update(run / FINAL, f"[ ] <!-- check:{item}", f"[x] <!-- check:{item}")
        diagnostics = self.check(4, code=1)
        self.assertRegex(diagnostics, r"(?i)private|memo|泄漏|备忘录")

    def test_gate4_requires_a_real_verification_anchor_for_each_contribution(self):
        run = self.verified()
        approve(run)
        populate_final(run, "method")
        update(run / FINAL, "| 04#evidence:M2 and 04#evidence:M3 |", "| 04#evidence:M9 and 04#evidence:M3 |")
        diagnostics = self.check(4, code=1)
        self.assertRegex(diagnostics, r"(?i)contribution C1.*04|C1.*锚点")

    def test_an_unfilled_workspace_draft_cannot_pass_the_gates(self):
        self.init()
        for gate in range(1, 5):
            with self.subTest(gate=gate):
                self.check(gate, code=1)

    def test_preregistration_edits_are_rejected_after_observation(self):
        run = self.verified()
        self.check(3)
        lock_file = run / ".prereg_lock.json"
        saved_lock = lock_file.read_bytes()
        fill(run / VERIFICATION, advance="M3 saves merely 1 USD at equal feasibility.")
        diagnostics = self.check(3, code=1)
        self.assertRegex(diagnostics, r"(?i)lock|prereg|hash|预注册|锁定")
        self.command("lock-prereg", code=2)
        self.assertEqual(lock_file.read_bytes(), saved_lock)

    def test_recorded_results_cannot_be_preregistered_retroactively(self):
        self.reviewed()
        preregister(self.workspace, self.workspace, "method")
        record_observations(self.workspace, self.workspace, "method")
        raw = self.command("lock-prereg", "--json", code=2)
        self.assertRegex(raw, r"(?i)results are already recorded|结果.*已有")
        self.assertFalse((self.workspace / ".prereg_lock.json").exists())

    def test_independent_proposal_version_cannot_inherit_another_lock(self):
        self.reviewed(proposals=("P1", "P1-v2"), selected=("P1", "P1-v2"))
        self.command("start", "--proposal", "P1")
        self.command("start", "--proposal", "P1-v2")
        first = self.lock(proposal="P1")
        second = self.workspace / "runs" / "P1-v2"
        preregister(self.workspace, second, "method")
        for run in (first, second):
            record_observations(self.workspace, run, "method")
            record_risks(run)
        self.check(3, proposal="P1")
        diagnostics = self.check(3, proposal="P1-v2", code=1)
        self.assertRegex(diagnostics, r"(?i)lock|prereg|预注册|锁定")

    def test_batch_screening_accepts_zero_survivors(self):
        self.init(mode="batch")
        path = self.workspace / "00_screening.md"
        replace_table(path, table(
            ("方案", "研究主张", "最接近工作及重叠点", "可取得的数据或基准", "最小判别试验", "结论", "依据"),
            (("P1", "method", "Local replay already uses the same reserve rule", "A toy replay is available",
              "Compare constraint definitions", "DROP", "No substantive distinction from the closest route"),
             ("P2", "phenomenon", "The association appears in an earlier public report", "No matched records",
              "Join generator-hour dispatch and settlement data", "DEFER", "No traceable dispatch orders")),
        ), section="screening")
        self.command("check", "--screen", "--json", "--strict", code=1)
        fill(path, batch_generation="author-supplied")
        output = json.loads(self.command("check", "--screen", "--json", "--strict"))
        self.assertIs(output["valid"], True, output)

    def test_legacy_workspace_survives_init_and_status(self):
        original = "# 01 假设—权衡—失效矩阵\n\n## 一、纵向文献矩阵\n\n| 编号 | 来源 |\n| --- | --- |\n| [1] | full-text |\n"
        old_path = self.workspace / MATRIX
        write(old_path, original)
        write(self.workspace / PROPOSALS, "# 02 候选创新方案书\n\n## 方案 P1：储能调度\n")
        status = json.loads(self.command("status", "--json"))
        self.assertTrue(status["exists"])
        self.assertIn(MATRIX, [record["artifact"] for record in status["artifacts"]])
        self.command("init", "--topic", "Migrated research")
        self.assertEqual(old_path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
