"""Protect the boundary between source-extraction candidates and recommendation labels."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from export_cold_start import ROOT, build_candidates


class ColdStartTests(unittest.TestCase):
    def test_outputs_are_exact_source_excerpts_and_all_held(self):
        rows = build_candidates()
        self.assertEqual(len(rows), 734)
        self.assertEqual(len({r["group_id"] for r in rows}), 127)
        self.assertEqual(len({r["sample_id"] for r in rows}), len(rows))
        for row in rows:
            self.assertFalse(row["training_allowed"])
            self.assertEqual(row["input"], row["output"])
            self.assertNotIn("capability_review_signals", row["output"])
            value = json.loads((ROOT / row["source"]["file"]).read_text(encoding="utf-8"))
            for token in row["source"]["pointer"].strip("/").split("/"):
                value = value[int(token)] if isinstance(value, list) else value[token]
            self.assertEqual(value["name"], row["ability_name"])
            # Removing HTML tags is the only normalization of official wording.
            from build_profiles import plain

            self.assertEqual(plain(value["desc_loc"]), row["output"]["description"])

    def test_modified_source_is_rejected_before_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = json.loads((ROOT / "source-manifest.json").read_text(encoding="utf-8"))
            first = manifest["records"][0]
            destination = root / first["file"]
            destination.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / first["file"], destination)
            destination.write_bytes(destination.read_bytes() + b" ")
            (root / "source-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
                build_candidates(root)


if __name__ == "__main__":
    unittest.main()
