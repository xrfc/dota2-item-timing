"""Boundary and leakage checks; runnable with unittest when pytest is unavailable."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from dota_items.data.cleaning import clean_match
from dota_items.data.contracts import PreparationConfig
from dota_items.data.features import extract_samples
from dota_items.data.pipeline import build_samples, prepare, prepare_one
from dota_items.data.preprocessing import fit_preprocessor, transform_features
from dota_items.storage import read_json, write_json
from dota_items.workflow.cli import main
from dota_items.workflow.contracts import Labels
from dota_items.workflow.datasets import build_dataset
from dota_items.workflow.jobs import train
from dota_items.workflow.validation import validate_match
from dota_items.workflow.workspace import Workspace


def fixture(match_id=100):
    return {
        "_fixture": "Synthetic unit test; not expert data",
        "match_id": match_id,
        "duration": 120,
        "players": [
            {
                "player_slot": 0,
                "hero_id": 44,
                "purchase_log": [{"time": -10, "key": "tango"}, {"time": 60, "key": "boots"}],
                "purchase_coverage": {
                    "start_seconds": 0.0,
                    "end_seconds": 120.0,
                    "source": "synthetic fixture construction",
                },
                "position_log": [{"time": t, "x": t * 2, "y": t * 3} for t in range(0, 121, 10)],
                "economy_log": [{"time": t, "gold": 500 + t} for t in range(0, 121, 10)],
            }
        ],
    }


def samples(raw, config=None):
    config = config or PreparationConfig()
    cleaned, quality = clean_match(raw, config)
    return extract_samples(cleaned, quality, config)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = Workspace(self.root / "workspace")
        self.workspace.init()
        self.config = PreparationConfig()

    def write(self, value, name="input.json"):
        path = self.root / name
        write_json(path, value)
        return path

    def test_future_changes_never_change_past_features(self):
        original = fixture()
        changed = copy.deepcopy(original)
        player = changed["players"][0]
        for log in ("position_log", "economy_log"):
            for row in player[log]:
                if row["time"] > 30:
                    for key in set(row) - {"time"}:
                        row[key] += 10000
        player["purchase_log"][1]["key"] = "desolator"
        before, old_labels, _ = samples(original)
        after, new_labels, _ = samples(changed)
        self.assertEqual(before[:2], after[:2])
        self.assertNotEqual(old_labels[1], new_labels[1])

    def test_feature_refs_are_at_or_before_cutoff(self):
        from dota_items.workflow.validation import resolve_ref

        raw = fixture()
        _, _, traces = samples(raw)
        for row in traces:
            for ref in row["feature_refs"]:
                self.assertLessEqual(resolve_ref(raw, ref)["time"], row["cutoff_seconds"])

    def test_cutoff_purchase_is_history_not_future(self):
        x, y, _ = samples(fixture())
        self.assertEqual(x[2]["recent_purchase_count"], 2)
        self.assertEqual(y[2]["item_action"], "no_purchase")
        self.assertFalse(y[-1]["item_mask"])
        self.assertEqual(y[-1]["item_reason"], "right_censored")

    def test_unknown_coverage_only_supervises_observed_positive_events(self):
        raw = fixture()
        del raw["players"][0]["purchase_coverage"]
        _, y, _ = samples(raw)
        self.assertTrue(y[0]["item_mask"])
        self.assertEqual(y[0]["item_reason"], "next_observed_purchase")
        self.assertFalse(y[2]["item_mask"])
        self.assertEqual(y[2]["item_reason"], "coverage_unknown")

    def test_missing_and_stale_observations_are_null_with_masks(self):
        raw = fixture()
        raw["players"][0]["position_log"] = [{"time": 0, "x": 1, "y": 2}]
        raw["players"][0].pop("economy_log")
        x, y, _ = samples(raw)
        self.assertEqual(x[1]["x"], 1)
        self.assertIsNone(x[2]["x"])
        self.assertEqual(x[2]["x_missing"], 1)
        self.assertIsNone(x[0]["gold"])
        self.assertFalse(y[0]["route_mask"])

    def test_invalid_rows_quarantine_without_changing_input(self):
        raw = fixture()
        raw["players"][0]["position_log"].append({"time": -0.5, "x": 1, "y": 1})
        raw["players"][0]["economy_log"][0]["gold"] = True
        original = copy.deepcopy(raw)
        cleaned, quality = clean_match(raw, self.config)
        self.assertEqual(raw, original)
        self.assertEqual(quality["quarantined"], 2)
        self.assertIsNone(cleaned["players"][0]["economy_log"][0]["gold"])
        with self.assertRaises(ValueError):
            clean_match(raw, PreparationConfig(invalid_policy="reject"))

    def test_nonfinite_and_bad_purchase_invalidate_coverage(self):
        raw = fixture()
        raw["players"][0]["purchase_log"].append({"time": float("nan"), "key": "boots"})
        cleaned, quality = clean_match(raw, self.config)
        self.assertIsNone(cleaned["players"][0]["purchase_coverage"])
        self.assertEqual(quality["quarantined"], 1)

    def test_conflicting_states_removed_exact_duplicates_collapsed_purchases_preserved(self):
        raw = fixture()
        player = raw["players"][0]
        player["position_log"] += [{"time": 0, "x": 100, "y": 0}, dict(player["position_log"][1])]
        player["purchase_log"].append(dict(player["purchase_log"][0]))
        cleaned, quality = clean_match(raw, self.config)
        self.assertEqual(len(cleaned["players"][0]["position_log"]), 12)
        self.assertEqual(len(cleaned["players"][0]["purchase_log"]), 3)
        self.assertEqual(quality["quarantined"], 2)

    def test_simultaneous_different_purchases_are_ambiguous(self):
        raw = fixture()
        raw["players"][0]["purchase_log"].append({"time": 60, "key": "desolator"})
        self.assertEqual(samples(raw)[1][0]["item_reason"], "simultaneous_purchases")
        self.assertFalse(samples(raw)[1][0]["item_mask"])

    def test_bad_structure_limits_and_strict_config(self):
        for key, value in (("match_id", True), ("duration", -1), ("players", [])):
            raw = fixture()
            raw[key] = value
            with self.assertRaises(ValueError):
                clean_match(raw, self.config)
        with self.assertRaises(ValueError):
            PreparationConfig(step_seconds=True)
        with self.assertRaises(ValueError):
            samples(fixture(), PreparationConfig(max_samples_per_match=1))
        with self.assertRaises(ValueError):
            clean_match(fixture(), PreparationConfig(max_rows_per_channel=1))

    def test_normalized_validation_rejects_negative_observation_time(self):
        raw = fixture()
        raw["players"][0]["position_log"][0]["time"] = -0.5
        with self.assertRaises(ValueError):
            validate_match(self.write(raw))

    def test_prepare_idempotence_integrity_and_raw_preservation(self):
        source = self.write(fixture())
        first = prepare_one(self.workspace, source, self.config)
        second = prepare_one(self.workspace, source, self.config)
        self.assertEqual(first["preparation_id"], second["preparation_id"])
        folder = Path(first["path"])
        self.assertEqual((folder / "input.json").read_bytes(), source.read_bytes())
        self.assertTrue(self.workspace.doctor()["ok"])
        (folder / "features.jsonl").write_text("changed")
        self.assertFalse(self.workspace.doctor()["ok"])

    def test_prepare_cleans_invalid_input_and_batch_continues(self):
        raw = fixture()
        raw["players"][0]["position_log"].reverse()
        raw["players"][0]["economy_log"][0]["gold"] = -5
        inbox = self.root / "inbox"
        inbox.mkdir()
        write_json(inbox / "good.json", raw)
        (inbox / "bad.json").write_text("broken")
        result = prepare(self.workspace, inbox, self.config)
        self.assertFalse(result["ok"])
        self.assertEqual(result["results"][1]["status"], "prepared")
        self.assertEqual(result["results"][1]["quarantined"], 1)
        self.assertEqual(len(self.workspace.catalog()["matches"]), 1)

    def test_demo_file_uses_parser_then_same_preparation_pipeline(self):
        source = self.root / "one.dem"
        source.write_bytes(b"PBDEMS2test")
        normalized = self.write(fixture())
        with patch(
            "dota_items.data.pipeline.ingest_demo",
            return_value={
                "normalized_json": str(normalized),
                "demo_sha256": "a" * 64,
            },
        ) as parser:
            result = prepare(self.workspace, source, self.config)
        parser.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertGreater(result["results"][0]["samples"], 0)

    def build(self):
        for match_id in range(100, 106):
            self.workspace.import_json(self.write(fixture(match_id)))
            self.workspace.annotate(
                match_id,
                Labels(
                    tier="synthetic",
                    patch="synthetic",
                    role=1,
                    player_slots=[0],
                    label_source="test",
                ),
            )
        frozen = build_dataset(self.workspace, patch="synthetic", role=1, allow_synthetic=True)
        return build_samples(self.workspace, frozen["dataset_id"], self.config)

    def test_train_only_preprocessing_roundtrip_unknown_hero_and_no_mutation(self):
        train_x, _, _ = samples(fixture())
        heldout = copy.deepcopy(train_x)
        for row in heldout:
            row["gold"] = 1e8
            row["hero_id"] = 999
        state = fit_preprocessor(train_x)
        expected = copy.deepcopy(state)
        transformed = transform_features(heldout, json.loads(json.dumps(state)))
        self.assertTrue(np.isfinite(transformed).all())
        self.assertTrue((transformed[:, -1] == 0).all())
        self.assertEqual(state, expected)
        self.assertEqual(fit_preprocessor(train_x), state)
        self.assertFalse(np.allclose(transform_features(train_x, state), transformed))

    def test_frozen_splits_arrays_and_preprocessor_match_training_rows(self):
        result = self.build()
        manifest, folder = self.workspace.dataset(result["dataset_id"])
        groups = [
            set(r["match_id"] for r in manifest["matches"] if r["split"] == s)
            for s in ("train", "validation", "test")
        ]
        self.assertFalse(groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])
        rows = [
            json.loads(line) for line in (folder / "train.features.jsonl").read_text().splitlines()
        ]
        state = read_json(folder / "preprocessor.json")
        self.assertEqual(state, fit_preprocessor(rows))
        with np.load(folder / "train.npz", allow_pickle=False) as arrays:
            self.assertTrue(np.isfinite(arrays["X"]).all())
            np.testing.assert_allclose(arrays["X"], transform_features(rows, state))
            self.assertTrue((arrays["item_target"][~arrays["item_mask"]] == -1).all())
        again = build_samples(self.workspace, result["source_dataset_id"], self.config)
        self.assertEqual(result["dataset_id"], again["dataset_id"])

    def test_changed_holdout_cannot_change_train_artifact(self):
        first = self.build()
        manifest, original = self.workspace.dataset(first["dataset_id"])
        heldout = {r["match_id"] for r in manifest["matches"] if r["split"] != "train"}
        other = Workspace(self.root / "other")
        other.init()
        for match_id in range(100, 106):
            raw = fixture(match_id)
            if match_id in heldout:
                for row in raw["players"][0]["economy_log"]:
                    row["gold"] += 1000000
            other.import_json(self.write(raw))
            other.annotate(
                match_id,
                Labels(
                    tier="synthetic",
                    patch="synthetic",
                    role=1,
                    player_slots=[0],
                    label_source="test",
                ),
            )
        frozen = build_dataset(other, patch="synthetic", role=1, allow_synthetic=True)
        second = build_samples(other, frozen["dataset_id"], self.config)
        target = Path(second["path"])
        self.assertEqual(
            (original / "preprocessor.json").read_bytes(),
            (target / "preprocessor.json").read_bytes(),
        )
        self.assertEqual((original / "train.npz").read_bytes(), (target / "train.npz").read_bytes())

    def test_training_adapter_receives_prepared_arrays(self):
        result = self.build()
        trainer = self.root / "trainer.py"
        trainer.write_text("""import argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser()
for k in ("dataset","output","config"): p.add_argument("--"+k,type=Path)
a=p.parse_args()
with np.load(a.dataset/"train.npz",allow_pickle=False) as batch:
    assert len(batch["X"]) > 0 and batch["item_mask"].any()
(a.output/"weights.bin").write_bytes(b"interface-test-only")
(a.output/"model.json").write_text(json.dumps({"schema_version":"coach-model/1",
"framework":"test","feature_schema":"coach-features/1","tasks":["item"],
"artifacts":["weights.bin"],"metrics":{}}))
""")
        self.assertEqual(
            train(self.workspace, result["dataset_id"], trainer)["status"], "succeeded"
        )

    def test_cli_prepare_initializes_workspace(self):
        self.assertEqual(
            main(["--workspace", str(self.root / "new"), "prepare", str(self.write(fixture()))]), 0
        )


if __name__ == "__main__":
    unittest.main()
