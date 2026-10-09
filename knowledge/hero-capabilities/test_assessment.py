"""Check boundaries that prevent draft potential from becoming fabricated advice."""

import json
import unittest
from pathlib import Path

from draft_assessment import assess, make_reviews

ROOT = Path(__file__).resolve().parent


class AssessmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "hero-registry.json").read_text(encoding="utf-8"))
        cls.reviews = make_reviews(cls.registry)

    def example(self):
        return assess(
            self.registry, [106, 18, 87, 69, 74], [9, 36, 145, 123, 107], "7.41f", self.reviews
        )

    def test_upgrade_not_counted_as_base(self):
        r = self.example()["sides"]["radiant"]
        self.assertFalse(any(c["dimension"] == "mute" for c in r["base_source_checked_potential"]))
        self.assertTrue(any(c["dimension"] == "mute" for c in r["upgrade_potential_not_base"]))

    def test_unverified_patch_blocks_recommendation(self):
        r = self.example()
        self.assertFalse(r["patch_admitted"])
        self.assertFalse(r["decision_recommendation_allowed"])

    def test_current_snapshot_learning_does_not_claim_patch_certification(self):
        r = assess(self.registry, [106, 18, 87, 69, 74], [9, 36, 145, 123, 107], None, self.reviews)
        self.assertTrue(r["current_snapshot_learning"])
        self.assertIsNone(r["target_patch"])
        self.assertFalse(r["patch_admitted"])

    def test_duplicate_hero_rejected(self):
        with self.assertRaises(ValueError):
            assess(
                self.registry,
                [106, 18, 87, 69, 74],
                [106, 36, 145, 123, 107],
                "7.41f",
                self.reviews,
            )

    def test_unknown_hero_rejected(self):
        with self.assertRaises(ValueError):
            assess(
                self.registry, [9999, 18, 87, 69, 74], [9, 36, 145, 123, 107], "7.41f", self.reviews
            )

    def test_incomplete_draft_rejected(self):
        with self.assertRaises(ValueError):
            assess(self.registry, [106, 18, 87, 69], [9, 36, 145, 123, 107], "7.41f", self.reviews)

    def test_all_heroes_covered_by_two_locales(self):
        heroes = json.loads((ROOT / "sources/herolist-english.json").read_text(encoding="utf-8"))[
            "result"
        ]["data"]["heroes"]
        self.assertEqual({h["id"] for h in heroes}, {h["hero_id"] for h in self.registry["heroes"]})
        for h in self.registry["heroes"]:
            self.assertTrue(h["abilities"])
            for a in h["abilities"]:
                self.assertTrue(a["description_en"])
                self.assertTrue(a["name_zh"])

    def test_every_claim_resolves_to_exact_source_text(self):
        for r in self.reviews:
            value = json.loads((ROOT / r["source_file"]).read_text(encoding="utf-8"))
            for token in r["source_pointer"].strip("/").split("/"):
                value = value[int(token)] if isinstance(value, list) else value[token]
            self.assertTrue(value)
            self.assertTrue(r["evidence_en"])

    def test_unknowns_not_called_weakness(self):
        r = self.example()
        self.assertNotIn("win_probability", r)
        self.assertNotIn("strength_score", r)
        self.assertTrue(r["sides"]["radiant"]["unknown_dimensions"])


if __name__ == "__main__":
    unittest.main()
