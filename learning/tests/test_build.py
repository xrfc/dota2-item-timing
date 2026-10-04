"""Learning checks stay independent of the production package and its dependencies."""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LEARNING = Path(__file__).resolve().parents[1]
PROJECT = LEARNING.parent
SPEC = importlib.util.spec_from_file_location("learning_build", LEARNING / "build.py")
assert SPEC is not None and SPEC.loader is not None
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)
ENGINEERING = PROJECT / "docs" / "roadmap.md"
PRACTICE = LEARNING / "docs" / "roadmap.md"


class RoadmapTests(unittest.TestCase):
    def test_supported_formats_and_dependency_identity(self):
        tasks = build.parse_roadmap(
            "## Engineering\n"
            "- [x] W01：Launcher\n"
            "| V04 Continue/shrink | 待做 | Check scope |\n"
            "| D01 Evidence | 部分 | Hash check | Independent verification |\n"
            "## Practice\n"
            "| L01 / 已完成 | Define：field a\\|b | 无；ML01 | Contract |\n"
            "| L02 / 待做 | Trace data | L01；D01 | Evidence |\n"
        )
        indexed = {task["id"]: task for task in tasks}
        self.assertEqual(indexed["W01"]["status"], "done")
        self.assertEqual(indexed["V04"]["title"], "Continue/shrink")
        self.assertEqual(indexed["D01"]["status"], "partial")
        self.assertEqual(indexed["L01"]["dependencies"], [])
        self.assertIn("a|b", indexed["L01"]["description"])
        self.assertEqual(indexed["L02"]["dependencies"], ["L01"])
        self.assertEqual(indexed["L02"]["section"], "Practice")

    def test_invalid_plans_are_rejected(self):
        cases = [
            "## No tasks\nProse only",
            "| D01 Evidence | strange | Hash |",
            "- [x] W01：One\n- [ ] W01：Duplicate",
            "| L02 / 待做 | Trace | L01 | Evidence |",
            "| L01 / 待做 | One | L02 | Evidence |\n| L02 / 待做 | Two | L01 | Evidence |",
            "| D01 Evidence | 待做 |",
        ]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(ValueError):
                build.parse_roadmap(text)

    def test_current_catalog_resolves_real_tasks_choices_and_files(self):
        data = build.build_learning_data(ENGINEERING, PRACTICE)
        ids = {task["id"] for task in data["tasks"]}
        self.assertEqual(len(ids), len(data["tasks"]))
        choices = {choice["id"] for choice in data["choices"]}
        for component in data["components"]:
            self.assertTrue(set(component["tasks"] + component["learning"]) <= ids)
            self.assertTrue(set(component["technology"]) <= choices)
            self.assertTrue(all((PROJECT / path).is_file() for path in component["files"]))
        self.assertEqual(data["roadmap_sha256"], build.file_hash(ENGINEERING))
        self.assertEqual(data["learning_roadmap_sha256"], build.file_hash(PRACTICE))

    def test_engineering_and_practice_progress_remain_separate(self):
        original = build.build_learning_data(ENGINEERING, PRACTICE)
        with tempfile.TemporaryDirectory() as folder:
            engineering = Path(folder) / "engineering.md"
            practice = Path(folder) / "practice.md"
            engineering.write_text(ENGINEERING.read_text(encoding="utf-8"), encoding="utf-8")
            text = PRACTICE.read_text(encoding="utf-8").replace("/ 待做 |", "/ 已完成 |")
            practice.write_text(text, encoding="utf-8")
            practiced = build.build_learning_data(engineering, practice)
            self.assertEqual(
                [component["state"] for component in original["components"]],
                [component["state"] for component in practiced["components"]],
            )
            self.assertTrue(
                all(
                    task["status"] == "done"
                    for task in practiced["tasks"]
                    if task["track"] == "learning"
                )
            )
            text = engineering.read_text(encoding="utf-8")
            text = text.replace("| D01 证据校验 | 部分 |", "| D01 证据校验 | 已完成 |")
            text = text.replace("| D05 数据质量 | 部分 |", "| D05 数据质量 | 已完成 |")
            engineering.write_text(text, encoding="utf-8")
            delivered = build.build_learning_data(engineering, PRACTICE)
            evidence = next(
                component for component in delivered["components"] if component["id"] == "evidence"
            )
            self.assertEqual(evidence["state"], "ready")
            self.assertTrue(
                all(
                    task["status"] == "pending"
                    for task in delivered["tasks"]
                    if task["track"] == "learning"
                )
            )


class GenerationTests(unittest.TestCase):
    def test_embedded_data_is_safe_and_template_tokens_remain_literal(self):
        data = build.build_learning_data(ENGINEERING, PRACTICE)
        hostile = '</script><img src=x onerror="alert(1)">{{JS}}{{LABS}}&\u2028\u2029'
        data["tasks"][0]["title"] = hostile
        page = build.render_learning(data)
        match = re.search(
            r'<script id="learning-data" type="application/json">(.*?)</script>', page, re.S
        )
        self.assertIsNotNone(match)
        payload = match[1]
        self.assertNotIn("<", payload)
        self.assertNotIn("\u2028", payload)
        self.assertEqual(json.loads(payload)["tasks"][0]["title"], hostile)
        self.assertNotIn('<img src=x onerror="alert(1)">', page)
        self.assertIn("{{JS}}{{LABS}}", payload)

    def test_output_and_manifest_cannot_overwrite_either_roadmap(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("practice.md", "practice.manifest.json"):
                source = Path(folder) / name
                source.write_bytes(PRACTICE.read_bytes())
                before = source.read_bytes()
                output = source if name.endswith(".md") else source.with_name("practice.html")
                with self.assertRaisesRegex(ValueError, "cannot overwrite"):
                    build.generate_learning(ENGINEERING, source, output)
                self.assertEqual(source.read_bytes(), before)

    def test_generator_produces_a_self_contained_page_and_matching_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "nested" / "index.html"
            result = build.generate_learning(ENGINEERING, PRACTICE, output)
            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            page = output.read_text(encoding="utf-8")
            self.assertIn("globalThis.CoachLearning", page)
            self.assertNotRegex(page, r"<script[^>]+src=")
            self.assertNotRegex(page, r"<link[^>]+stylesheet")
            self.assertEqual(manifest["roadmap_sha256"], build.file_hash(ENGINEERING))
            self.assertEqual(manifest["learning_roadmap_sha256"], build.file_hash(PRACTICE))

    def test_cli_runs_from_a_different_directory_without_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "page.html"
            result = subprocess.run(
                [sys.executable, "-I", str(LEARNING / "build.py"), "--output", str(output)],
                cwd=folder,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["page"], str(output.resolve()))
            self.assertTrue(output.is_file())

    def test_missing_sources_do_not_leave_partial_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "page.html"
            with self.assertRaisesRegex(ValueError, "Roadmap not found"):
                build.generate_learning(Path(folder) / "missing.md", PRACTICE, output)
            self.assertFalse(output.exists())

    def test_optional_workspace_summary_is_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            (workspace / "workspace.json").write_text("{}", encoding="utf-8")
            (workspace / "catalog.json").write_text('{"matches": {"1": {}}}', encoding="utf-8")
            (workspace / "datasets" / "one").mkdir(parents=True)
            before = {path: path.read_bytes() for path in workspace.rglob("*") if path.is_file()}
            summary = build.build_learning_data(ENGINEERING, PRACTICE, workspace)["workspace"]
            self.assertTrue(summary["available"])
            self.assertEqual(summary["matches"], 1)
            self.assertEqual(summary["datasets"], 1)
            self.assertEqual(
                before, {path: path.read_bytes() for path in workspace.rglob("*") if path.is_file()}
            )
            (workspace / "catalog.json").write_text("invalid json", encoding="utf-8")
            self.assertFalse(
                build.build_learning_data(ENGINEERING, PRACTICE, workspace)["workspace"][
                    "available"
                ]
            )


if __name__ == "__main__":
    unittest.main()
