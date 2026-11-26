"""Workspace lifecycle tests run the public CLI without external dependencies."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "paper-innovation" / "scripts" / "ideation_ctl.py"


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        sandbox = tempfile.TemporaryDirectory(prefix="ideation-workspace-")
        self.addCleanup(sandbox.cleanup)
        self.parent = Path(sandbox.name).resolve()
        self.work = self.parent / "research topic"

    def call(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(CLI), *map(str, args), "--json"],
            cwd=self.parent, capture_output=True, encoding="utf-8", check=False,
        )

    def init(self, topic="Market evidence", *args):
        return self.call("init", "--dir", self.work, "--topic", topic, *args)

    def test_init_is_idempotent_and_refuses_unrelated_topics(self):
        self.assertEqual(self.init("Market evidence", "--mode", "single", "--claim", "phenomenon").returncode, 0)
        record = self.work / "02_candidate_proposals.md"
        record.write_text("The author's partial work.\n", encoding="utf-8")
        retry = self.init()
        self.assertEqual(json.loads(retry.stdout)["skipped"], 6)
        for topic, args in (("Another topic", ()), ("Market evidence", ("--claim", "theory"))):
            attempt = self.init(topic, *args)
            self.assertEqual(attempt.returncode, 2)
        self.assertEqual(record.read_text(encoding="utf-8"), "The author's partial work.\n")

    def test_two_same_topic_initializers_publish_complete_templates(self):
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: self.init("Same topic", "--mode", "single"), range(2)))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(sum(len(json.loads(r.stdout)["written"]) for r in results), 6)
        self.assertEqual(len(list(self.work.glob("*.md"))), 6)
        for artifact in self.work.glob("*.md"):
            self.assertIn("Same topic", artifact.read_text(encoding="utf-8"))

    def test_two_different_topics_cannot_mix_content_in_one_directory(self):
        topics = ["First topic", "Second topic"]
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda t: self.init(t, "--mode", "single"), topics))
        self.assertEqual(sorted(r.returncode for r in results), [0, 2])
        chosen = json.loads((self.work / ".ideation.json").read_text(encoding="utf-8"))["topic"]
        for artifact in self.work.glob("*.md"):
            self.assertIn(chosen, artifact.read_text(encoding="utf-8"))

    def test_symlink_parent_never_receives_a_new_study(self):
        target = self.parent / "target"
        target.mkdir()
        alias = self.parent / "alias"
        try:
            alias.symlink_to(target, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                self.skipTest("Directory symlinks unavailable")
            # Windows directory junctions do not require Developer Mode.
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-NonInteractive", "-Command",
                 "New-Item -ItemType Junction -Path $env:IDEATION_ALIAS -Target $env:IDEATION_TARGET | Out-Null"],
                env={**os.environ, "IDEATION_ALIAS": str(alias), "IDEATION_TARGET": str(target)},
                capture_output=True,
            )
            if result.returncode:
                self.skipTest("Neither directory symlinks nor junctions are available")
        self.work = alias / "new-study"
        attempt = self.init()
        self.assertEqual(attempt.returncode, 2, attempt.stdout)
        self.assertFalse((target / "new-study").exists())


if __name__ == "__main__":
    unittest.main()
