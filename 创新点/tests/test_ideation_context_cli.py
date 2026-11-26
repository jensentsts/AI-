"""Exercise the projection and provenance checks through a fresh CLI process."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "paper-innovation" / "scripts" / "ideation_ctl.py"

Q_TABLE = """## Independent origins
<!-- section:idea_origins -->
| ID | Origin type | Independent problem | Own source anchor |
| --- | --- | --- | --- |
| Q1 | observation | 同一时段两个场站的减发量不同 | 现场值班记录第 17 行 |
"""
L_TABLE = """## Callable objects
<!-- section:literature_objects -->
| ID | Role | Inputs | Preconditions | Known operation | Outputs | Applicability boundary |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | method | 场站的功率序列 | 采样时钟一致 | 聚合每小时出力 | 各时段功率和 | 聚合值无法识别减发原因 |
"""
SCREEN_TABLE = """- <!-- field:batch_generation --> **本轮生成方式**：fresh

## 初筛记录
<!-- section:screening -->
| ID | Claim | Prior | Resources | Test | Outcome | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | phenomenon | L1 给出聚合方法 | 场站计量与指令记录 | 比较指令到达前后的出力 | KEEP | 两种解释给出不同的可检验预测 |
"""
RAW = """## 原文与审查笔记
标题 ORIGINAL-TITLE-DO-NOT-EXPORT
摘要 ORIGINAL-ABSTRACT-DO-NOT-EXPORT
作者展望 SOURCE-OUTLOOK-DO-NOT-EXPORT
https://example.invalid/source-id/raw-review

## Reviewer source register
<!-- section:literature_table -->
| Work ID | Canonical locator | Local full-text path | Depth | Pinpoints |
| --- | --- | --- | --- | --- |
| L1 | | evidence-1.md | full-text | p. 1 |
| L2 | | evidence-2.md | full-text | p. 2 |
"""
DELTA = "按指令到达顺序配对减发事件，在相同电价时段区分两种机制。"


def lineage(digest, origin="Q1", calls="L1", delta=DELTA):
    bindings = ["| ID | Supplied inputs | Use of output |", "| --- | --- | --- |"]
    if calls != "NONE":
        bindings.append(f"| {calls} | 两场站同一时段的观测 | 聚合后逐对比较减发量 |")
    return f"""### 方案 P1
- <!-- field:origin_ids --> **独立来源**：{origin}
- <!-- field:calls --> **调用的对象**：{calls}
- <!-- field:novel_delta --> **作者增量**：{delta}
- <!-- field:generation --> **生成方式**：fresh
- <!-- field:brief_sha256 --> **使用的简报**：{digest}

#### 调用明细
<!-- section:call_bindings -->
""" + "\n".join(bindings) + "\n"


class ContextWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="innovation-inputs-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.study = self.root / "study"
        self.call("init", "--topic", "市场观测", "--mode", "batch", expected=0)
        self.input = self.study / "00_screening.md"
        (self.study / "evidence-1.md").write_text("Synthetic known method. Page 1.", encoding="utf-8")
        (self.study / "evidence-2.md").write_text("Synthetic data description. Page 2.", encoding="utf-8")
        self.record(Q_TABLE + "\n" + L_TABLE + "\n" + SCREEN_TABLE + "\n" + RAW)

    def call(self, command, *options, expected):
        result = subprocess.run(
            [sys.executable, "-B", str(CLI), command, "--dir", str(self.study), *options, "--json"],
            cwd=self.root, capture_output=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def record(self, text):
        self.input.write_text(text, encoding="utf-8")

    def test_export_contains_only_question_and_callable_interface(self):
        response = self.call("prepare-ideas", expected=0)
        snapshot = Path(response["snapshot"]).read_text(encoding="utf-8")
        self.assertEqual(response["sha256"], hashlib.sha256(snapshot.encode("utf-8")).hexdigest())
        for allowed in ("Q1", "L1", "同一时段两个场站的减发量不同", "聚合每小时出力"):
            self.assertIn(allowed, snapshot)
        for forbidden in ("ORIGINAL-TITLE", "ORIGINAL-ABSTRACT", "SOURCE-OUTLOOK", "example.invalid", "P1", "指令到达前后的出力"):
            self.assertNotIn(forbidden, snapshot)
        self.assertEqual(snapshot, Path(response["context"]).read_text(encoding="utf-8"))
        self.assertEqual(Path(response["template"]).name, "idea_draft.md")
        self.assertTrue(Path(response["template"]).is_file())

    def test_returning_a_fresh_candidate_requires_the_actual_immutable_snapshot(self):
        raw = self.input.read_text(encoding="utf-8")
        self.call("check", "--screen", "--strict", expected=1)
        receipt = self.call("prepare-ideas", expected=0)
        self.record(raw + "\n" + lineage(receipt["sha256"]))
        self.call("check", "--screen", "--strict", expected=0)
        self.record(raw + "\n" + lineage("a" * 64))
        self.call("check", "--screen", "--strict", expected=1)
        self.record(raw + "\n" + lineage(receipt["sha256"]))
        Path(receipt["snapshot"]).write_text("改写过的简报", encoding="utf-8")
        self.call("check", "--screen", "--strict", expected=1)

    def test_new_objects_do_not_reassign_the_contents_of_an_existing_snapshot(self):
        first = self.call("prepare-ideas", expected=0)
        original = self.input.read_text(encoding="utf-8")
        extra = "| L2 | data | 气象测量 | 时钟统一 | 获取气温 | 同时段气温 | 数据限于场内 |"
        newer = original.replace(L_TABLE, L_TABLE.rstrip() + "\n" + extra + "\n")
        self.record(newer)
        second = self.call("prepare-ideas", expected=0)
        self.assertNotEqual(first["sha256"], second["sha256"])
        self.assertTrue(Path(first["snapshot"]).is_file())
        self.record(newer + "\n" + lineage(first["sha256"], calls="L2"))
        self.call("check", "--screen", "--strict", expected=1)
        self.record(newer + "\n" + lineage(first["sha256"], calls="L1"))
        self.call("check", "--screen", "--strict", expected=0)

    def test_external_outlook_is_neither_an_origin_nor_a_callable_operation(self):
        original = self.input.read_text(encoding="utf-8")
        for bad in (
            original.replace("Q1 | observation", "Q1 | future-work"),
            original.replace("聚合每小时出力", "Future work: forecast a missing observation"),
            original.replace("Known operation | Outputs", "Known operation | Paper outlook | Outputs"),
        ):
            with self.subTest():
                self.record(bad)
                self.call("prepare-ideas", expected=1)

    def test_an_unmarked_copy_of_authors_outlook_cannot_be_moved_into_an_origin_or_object(self):
        outlook = "利用场站之间的调度指令时差估计减发的因果效应"
        original = self.input.read_text(encoding="utf-8") + "\n## Future Work\n" + outlook + "。\n"
        for old in ("同一时段两个场站的减发量不同", "聚合每小时出力"):
            with self.subTest(target=old):
                self.record(original.replace(old, outlook))
                self.call("prepare-ideas", expected=1)

    def test_unread_work_cannot_be_imported_as_an_implemented_operation(self):
        original = self.input.read_text(encoding="utf-8")
        self.record(original.replace("evidence-1.md | full-text", "evidence-1.md | abstract-only"))
        self.call("prepare-ideas", expected=1)

    def test_question_without_papers_can_generate_and_papers_without_question_cannot(self):
        raw = self.input.read_text(encoding="utf-8")
        self.record(raw.replace(Q_TABLE.splitlines()[-1], ""))
        self.call("prepare-ideas", expected=1)
        question_only = raw.replace(L_TABLE.splitlines()[-1], "").replace(RAW, "")
        self.record(question_only)
        receipt = self.call("prepare-ideas", expected=0)
        self.assertEqual(receipt["objects"], [])
        self.record(question_only + "\n" + lineage(receipt["sha256"], calls="NONE"))
        self.call("check", "--screen", "--strict", expected=0)

    def test_reported_result_can_be_called_but_cannot_be_claimed_as_new(self):
        finding = "逐场站汇总每一小时内的有效观测来计算平均出力"
        raw = self.input.read_text(encoding="utf-8").replace("Depth | Pinpoints", "Depth | Finding or claim | Pinpoints")
        raw = raw.replace("| --- | --- | --- | --- | --- |\n| L1 | | evidence-1", "| --- | --- | --- | --- | --- | --- |\n| L1 | | evidence-1")
        raw = raw.replace("full-text | p. 1", f"full-text | {finding} | p. 1").replace("full-text | p. 2", "full-text | 另一项已知结果 | p. 2")
        self.record(raw)
        receipt = self.call("prepare-ideas", expected=0)
        self.record(raw + "\n" + lineage(receipt["sha256"], delta=finding))
        self.call("check", "--screen", "--strict", expected=1)
        self.record(raw.replace("聚合每小时出力", finding))
        self.call("prepare-ideas", expected=0)

    def test_shipped_proposal_table_accepts_inputs_and_output_use(self):
        receipt = self.call("prepare-ideas", expected=0)
        template = (Path(receipt["template"]).parent / "02_candidate_proposals.md").read_text(encoding="utf-8")
        bindings = template.split("### Callable bindings", 1)[1].split("\n### ", 1)[0].rstrip()
        raw = self.input.read_text(encoding="utf-8")
        candidate = lineage(receipt["sha256"]).split("#### 调用明细", 1)[0]
        self.record(raw + "\n" + candidate + "#### Callable bindings" + bindings + "\n| L1 | 两场站同一时段的观测 | 做配对比较 |\n")
        self.call("check", "--screen", "--strict", expected=0)


if __name__ == "__main__":
    unittest.main()
